import { Hono } from 'hono';
import type { AppContextEnv } from '../types';
import { requireTeacher } from '../lib/auth';
import { rateLimit } from '../lib/rate-limit';

export const apiRoutes = new Hono<AppContextEnv>();

export const DAILY_GENERATION_LIMIT = 10;

export async function getUserCredits(db: D1Database, userId: string) {
  const todayPrefix = new Date().toISOString().slice(0, 10);
  const row = await db
    .prepare('SELECT COUNT(*) as cnt FROM generation_logs WHERE user_id = ? AND created_at >= ?')
    .bind(userId, `${todayPrefix}T00:00:00Z`)
    .first<{ cnt: number }>();
  const used = row?.cnt || 0;
  return {
    used,
    limit: DAILY_GENERATION_LIMIT,
    remaining: Math.max(0, DAILY_GENERATION_LIMIT - used),
  };
}

apiRoutes.get('/classes', async (c) => {
  const rows = await c.env.DB.prepare(
    'SELECT id, name, name_bn, level, "order" FROM classes WHERE is_active = 1 ORDER BY "order", id'
  ).all();
  return c.json(rows.results || []);
});

apiRoutes.get('/subjects/:classId', async (c) => {
  const classId = Number(c.req.param('classId'));
  const rows = await c.env.DB.prepare(
    'SELECT id, name, name_bn, code, "order" FROM subjects WHERE class_id = ? AND is_active = 1 ORDER BY "order", id'
  )
    .bind(classId)
    .all();
  return c.json(rows.results || []);
});

apiRoutes.get('/chapters/:subjectId', async (c) => {
  const subjectId = Number(c.req.param('subjectId'));
  const rows = await c.env.DB.prepare(
    'SELECT id, name, name_bn, chapter_number, "order" FROM chapters WHERE subject_id = ? AND is_active = 1 ORDER BY "order", chapter_number, id'
  )
    .bind(subjectId)
    .all();
  return c.json(rows.results || []);
});

apiRoutes.post('/questions/count', rateLimit(60, 60, 'api_qcount'), async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as { chapter_ids?: number[] };
  const chapterIds = (body.chapter_ids || []).map(Number).filter(Number.isFinite);
  if (chapterIds.length === 0) return c.json({ count: 0 });
  const placeholders = chapterIds.map(() => '?').join(',');
  const row = await c.env.DB.prepare(
    `SELECT COUNT(*) as cnt FROM questions WHERE chapter_id IN (${placeholders}) AND is_active = 1`
  )
    .bind(...chapterIds)
    .first<{ cnt: number }>();
  return c.json({ count: row?.cnt || 0 });
});

apiRoutes.get('/short-questions/count', async (c) => {
  const subjectId = Number(c.req.query('subject_id'));
  const chapterId = Number(c.req.query('chapter_id'));
  let sql = 'SELECT COUNT(*) as cnt FROM short_questions WHERE is_active = 1';
  const params: number[] = [];
  if (Number.isFinite(subjectId) && subjectId > 0) {
    sql += ' AND subject_id = ?';
    params.push(subjectId);
  }
  if (Number.isFinite(chapterId) && chapterId > 0) {
    sql += ' AND chapter_id = ?';
    params.push(chapterId);
  }
  const row = await c.env.DB.prepare(sql).bind(...params).first<{ cnt: number }>();
  return c.json({ count: row?.cnt || 0 });
});

apiRoutes.get('/cq-questions/count', async (c) => {
  const subjectId = Number(c.req.query('subject_id'));
  const chapterId = Number(c.req.query('chapter_id'));
  let sql = 'SELECT COUNT(*) as cnt FROM cq_questions WHERE is_active = 1';
  const params: number[] = [];
  if (Number.isFinite(subjectId) && subjectId > 0) {
    sql += ' AND subject_id = ?';
    params.push(subjectId);
  }
  if (Number.isFinite(chapterId) && chapterId > 0) {
    sql += ' AND chapter_id = ?';
    params.push(chapterId);
  }
  const row = await c.env.DB.prepare(sql).bind(...params).first<{ cnt: number }>();
  return c.json({ count: row?.cnt || 0 });
});

apiRoutes.get('/stats', async (c) => {
  const [classes, subjects, chapters, questions, papers] = await Promise.all([
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM classes WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM subjects WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM chapters WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM questions WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM generated_papers').first<{ cnt: number }>(),
  ]);
  return c.json({
    classes: classes?.cnt || 0,
    subjects: subjects?.cnt || 0,
    chapters: chapters?.cnt || 0,
    questions: questions?.cnt || 0,
    papers_generated: papers?.cnt || 0,
  });
});

apiRoutes.get('/credits', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const credits = await getUserCredits(c.env.DB, user.id);
  return c.json(credits);
});

apiRoutes.post('/uploads/logo', requireTeacher, async (c) => {
  const form = await c.req.parseBody();
  const file = form.file;
  if (!(file instanceof File)) {
    return c.json({ error: 'No image file provided.' }, 400);
  }
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'].includes(file.type)) {
    return c.json({ error: 'Only PNG, JPEG, WebP, or SVG allowed.' }, 400);
  }
  if (file.size > 512 * 1024) {
    return c.json({ error: 'Logo file must be under 512KB.' }, 400);
  }

  const user = c.get('user')!;
  const buf = await file.arrayBuffer();
  if (c.env.PROSNO_R2) {
    const ext = file.type.split('/')[1].replace('+xml', '');
    const key = `logos/${user.id}/${Date.now()}.${ext}`;
    await c.env.PROSNO_R2.put(key, buf, { httpMetadata: { contentType: file.type } });
    return c.json({ url: `/api/uploads/r2/${key}` });
  }

  // Fallback: base64 data URI when R2 is not bound
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  const dataUri = `data:${file.type};base64,${btoa(bin)}`;
  return c.json({ url: dataUri });
});

apiRoutes.get('/uploads/r2/*', async (c) => {
  if (!c.env.PROSNO_R2) return c.notFound();
  const key = c.req.path.replace('/api/uploads/r2/', '');
  const obj = await c.env.PROSNO_R2.get(key);
  if (!obj) return c.notFound();
  return new Response(obj.body, {
    headers: { 'Content-Type': obj.httpMetadata?.contentType || 'application/octet-stream' },
  });
});
