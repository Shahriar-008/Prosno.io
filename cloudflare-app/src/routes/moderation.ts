import { Hono } from 'hono';
import type { AppContextEnv } from '../types';
import { requireAdmin } from '../lib/auth';
import { createNotification, postApprovalRefresh } from '../lib/bank-helpers';
import { serializeBankQuestion } from './bank';

export const moderationRoutes = new Hono<AppContextEnv>();

moderationRoutes.use('*', requireAdmin);

moderationRoutes.get('/moderation/queue', async (c) => {
  const page = Math.max(1, Number(c.req.query('page')) || 1);
  const perPage = Math.min(100, Math.max(1, Number(c.req.query('per_page')) || 20));
  const sort = c.req.query('sort') || 'oldest';
  const offset = (page - 1) * perPage;

  const orderBy =
    sort === 'priority'
      ? 'mq.priority ASC, mq.submitted_at ASC'
      : sort === 'newest'
      ? 'mq.submitted_at DESC'
      : 'mq.submitted_at ASC';

  const [totalRow, rowsRes] = await Promise.all([
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM moderation_queue WHERE decision IS NULL').first<{ cnt: number }>(),
    c.env.DB.prepare(
      `SELECT mq.*, bq.*, mq.id as queue_id, tp.display_name as teacher_name, tp.is_trusted as teacher_trusted, tp.approved_questions_count as teacher_approved_count
       FROM moderation_queue mq
       JOIN bank_questions bq ON bq.id = mq.question_id
       LEFT JOIN teacher_profiles tp ON tp.user_id = mq.submitted_by
       WHERE mq.decision IS NULL
       ORDER BY ${orderBy}
       LIMIT ? OFFSET ?`
    )
      .bind(perPage, offset)
      .all<Record<string, unknown>>(),
  ]);

  const total = totalRow?.cnt || 0;
  const items = (rowsRes.results || []).map((r) => ({
    id: r.queue_id,
    question_id: r.question_id,
    submitted_by: r.submitted_by,
    submitted_at: r.submitted_at,
    decision: r.decision,
    priority: r.priority,
    teacher_name: r.teacher_name || String(r.submitted_by).slice(0, 8),
    teacher_trusted: Boolean(r.teacher_trusted),
    teacher_approved_count: r.teacher_approved_count || 0,
    question: serializeBankQuestion(r as unknown as Parameters<typeof serializeBankQuestion>[0], true),
  }));

  return c.json({ items, total, page, pages: Math.ceil(total / perPage) });
});

moderationRoutes.get('/moderation/:queueId', async (c) => {
  const queueId = Number(c.req.param('queueId'));
  const mq = await c.env.DB.prepare('SELECT * FROM moderation_queue WHERE id = ?').bind(queueId).first<{
    id: number;
    question_id: number;
    submitted_by: string;
    submitted_at: string;
    decision: string | null;
    admin_notes: string | null;
    priority: number;
  }>();
  if (!mq) return c.json({ error: 'Queue item not found' }, 404);

  const bq = await c.env.DB.prepare('SELECT * FROM bank_questions WHERE id = ?').bind(mq.question_id).first();
  const teacher = await c.env.DB.prepare('SELECT * FROM teacher_profiles WHERE user_id = ?').bind(mq.submitted_by).first();
  return c.json({
    ...mq,
    question: bq ? serializeBankQuestion(bq as unknown as Parameters<typeof serializeBankQuestion>[0], true) : null,
    teacher,
  });
});

moderationRoutes.post('/moderation/:queueId/decide', async (c) => {
  const queueId = Number(c.req.param('queueId'));
  const adminUser = c.get('user')!;
  const mq = await c.env.DB.prepare('SELECT * FROM moderation_queue WHERE id = ?').bind(queueId).first<{
    id: number;
    question_id: number;
    submitted_by: string;
    decision: string | null;
  }>();
  if (!mq) return c.json({ error: 'Queue item not found' }, 404);
  if (mq.decision) return c.json({ error: 'Already decided' }, 400);

  const body = (await c.req.json().catch(() => ({}))) as { decision?: string; admin_notes?: string };
  const decision = body.decision;
  if (decision !== 'approved' && decision !== 'rejected') {
    return c.json({ error: 'decision must be approved or rejected' }, 400);
  }

  const bq = await c.env.DB.prepare('SELECT id, teacher_id, question_text FROM bank_questions WHERE id = ?')
    .bind(mq.question_id)
    .first<{ id: number; teacher_id: string; question_text: string }>();
  if (!bq) return c.json({ error: 'Associated question not found' }, 404);

  const adminNotes = body.admin_notes || '';
  await c.env.DB.prepare(
    `UPDATE moderation_queue SET decision = ?, reviewed_by = ?, reviewed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), admin_notes = ? WHERE id = ?`
  )
    .bind(decision, adminUser.id, adminNotes, queueId)
    .run();

  if (decision === 'approved') {
    await c.env.DB.prepare(
      `UPDATE bank_questions SET visibility = 'public', status = 'approved', published_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), rejection_reason = NULL WHERE id = ?`
    )
      .bind(bq.id)
      .run();
  } else {
    await c.env.DB.prepare(
      `UPDATE bank_questions SET visibility = 'rejected', status = 'rejected', rejected_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), rejection_reason = ? WHERE id = ?`
    )
      .bind(adminNotes, bq.id)
      .run();
  }

  const newlyAwarded = await postApprovalRefresh(
    c.env.DB,
    bq.teacher_id,
    { id: bq.id, question_text: bq.question_text, rejection_reason: adminNotes },
    decision
  );

  const pendingRow = await c.env.DB.prepare('SELECT COUNT(*) as cnt FROM moderation_queue WHERE decision IS NULL').first<{ cnt: number }>();

  return c.json({
    message: `Question ${decision}`,
    queue_id: queueId,
    question_id: bq.id,
    decision,
    newly_awarded_badges: newlyAwarded,
    pending_in_queue: pendingRow?.cnt || 0,
  });
});

moderationRoutes.get('/teachers', async (c) => {
  const rows = await c.env.DB.prepare('SELECT * FROM teacher_profiles ORDER BY reputation_score DESC LIMIT 100').all();
  return c.json({ items: rows.results || [] });
});

moderationRoutes.get('/teachers/:userId', async (c) => {
  const userId = c.req.param('userId');
  const profile = await c.env.DB.prepare('SELECT * FROM teacher_profiles WHERE user_id = ?').bind(userId).first();
  if (!profile) return c.json({ error: 'Teacher not found' }, 404);
  const recent = await c.env.DB.prepare(
    'SELECT * FROM bank_questions WHERE teacher_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 20'
  )
    .bind(userId)
    .all();
  return c.json({
    ...profile,
    recent_questions: (recent.results || []).map((r) => serializeBankQuestion(r as unknown as Parameters<typeof serializeBankQuestion>[0], true)),
  });
});

moderationRoutes.patch('/teachers/:userId/trust', async (c) => {
  const userId = c.req.param('userId');
  const adminUser = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as { is_trusted?: boolean };
  if (body.is_trusted === undefined) return c.json({ error: 'is_trusted (bool) is required' }, 400);

  const profile = await c.env.DB.prepare('SELECT * FROM teacher_profiles WHERE user_id = ?').bind(userId).first();
  if (!profile) return c.json({ error: 'Teacher not found' }, 404);

  const trusted = Boolean(body.is_trusted);
  if (trusted) {
    await c.env.DB.prepare(
      `UPDATE teacher_profiles SET is_trusted = 1, trust_granted_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), trust_granted_by = ? WHERE user_id = ?`
    )
      .bind(adminUser.id, userId)
      .run();
    await createNotification(c.env.DB, {
      teacherId: userId,
      notifType: 'trust_granted',
      title: 'You are now a Trusted Teacher! 🎉',
      body: 'An admin granted you Trusted status. Your future questions publish directly without moderation.',
    });
  } else {
    await c.env.DB.prepare('UPDATE teacher_profiles SET is_trusted = 0, trust_granted_at = NULL, trust_granted_by = NULL WHERE user_id = ?')
      .bind(userId)
      .run();
  }

  return c.json({ message: `Trust ${trusted ? 'granted' : 'revoked'}`, user_id: userId, is_trusted: trusted });
});

moderationRoutes.get('/stats', async (c) => {
  const [totalQ, publicQ, pendingQ, totalT, trustedT, pendingMod] = await Promise.all([
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM bank_questions WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare("SELECT COUNT(*) as cnt FROM bank_questions WHERE visibility = 'public' AND is_active = 1").first<{ cnt: number }>(),
    c.env.DB.prepare("SELECT COUNT(*) as cnt FROM bank_questions WHERE visibility = 'pending' AND is_active = 1").first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM teacher_profiles').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM teacher_profiles WHERE is_trusted = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM moderation_queue WHERE decision IS NULL').first<{ cnt: number }>(),
  ]);
  return c.json({
    total_questions: totalQ?.cnt || 0,
    public_questions: publicQ?.cnt || 0,
    pending_questions: pendingQ?.cnt || 0,
    total_teachers: totalT?.cnt || 0,
    trusted_teachers: trustedT?.cnt || 0,
    pending_moderation: pendingMod?.cnt || 0,
  });
});
