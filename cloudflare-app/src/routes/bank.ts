import { Hono } from 'hono';
import type { AppContextEnv } from '../types';
import { requireTeacher } from '../lib/auth';
import { computeTextHash } from '../lib/bengali';
import {
  findDuplicates,
  getOrCreateProfile,
  recalculateReputation,
  refreshProfileCounters,
  evaluateAndAwardBadges,
} from '../lib/bank-helpers';
import { rateLimit } from '../lib/rate-limit';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';

export const bankPageRoutes = new Hono<AppContextEnv>();
export const bankApiRoutes = new Hono<AppContextEnv>();

interface BankQuestionRow {
  id: number;
  teacher_id: string;
  class_id: number | null;
  subject_id: number | null;
  chapter_id: number | null;
  question_type: string;
  question_text: string;
  answer: string | null;
  explanation: string | null;
  answer_options: string | null;
  correct_answer: string | null;
  stem: string | null;
  part_ka: string | null;
  part_kha: string | null;
  part_ga: string | null;
  part_gha: string | null;
  marks_ka: number | null;
  marks_kha: number | null;
  marks_ga: number | null;
  marks_gha: number | null;
  topic: string | null;
  difficulty: string;
  marks: number;
  board: string | null;
  year: number | null;
  visibility: string;
  status: string;
  origin: string;
  source_question_id: number | null;
  usage_count: number;
  download_count: number;
  rating_total: number;
  rating_count: number;
  text_hash: string | null;
  is_active: number;
  created_at: string;
}

export function serializeBankQuestion(row: BankQuestionRow, includeAnswer = false) {
  const avgRating = row.rating_count > 0 ? Math.round((row.rating_total / row.rating_count) * 100) / 100 : 0;
  const out: Record<string, unknown> = {
    id: row.id,
    teacher_id: row.teacher_id,
    class_id: row.class_id,
    subject_id: row.subject_id,
    chapter_id: row.chapter_id,
    question_type: row.question_type,
    question_text: row.question_text,
    topic: row.topic,
    difficulty: row.difficulty,
    marks: row.marks,
    board: row.board,
    year: row.year,
    visibility: row.visibility,
    status: row.status,
    origin: row.origin,
    source_question_id: row.source_question_id,
    usage_count: row.usage_count,
    download_count: row.download_count,
    average_rating: avgRating,
    rating_count: row.rating_count,
    created_at: row.created_at,
  };
  if (row.question_type === 'MCQ') {
    out.answer_options = row.answer_options ? JSON.parse(row.answer_options) : [];
    if (includeAnswer) out.correct_answer = row.correct_answer;
  }
  if (row.question_type === 'CQ') {
    out.stem = row.stem;
    out.part_ka = row.part_ka;
    out.part_kha = row.part_kha;
    out.part_ga = row.part_ga;
    out.part_gha = row.part_gha;
    out.marks_ka = row.marks_ka;
    out.marks_kha = row.marks_kha;
    out.marks_ga = row.marks_ga;
    out.marks_gha = row.marks_gha;
  }
  if (includeAnswer) {
    out.answer = row.answer;
    out.explanation = row.explanation;
  }
  return out;
}

// ── Bank Pages ────────────────────────────────────────────────────────────

bankPageRoutes.get('/bank', async (c) => {
  const user = c.get('user');
  const html = renderPageLayout(
    {
      title: 'কমিউনিটি প্রশ্ন ব্যাংক',
      user,
      activeNav: 'bank',
      breadcrumbs: [{ label: 'হোম', href: '/' }, { label: 'প্রশ্ন ব্যাংক' }],
      extraScripts: '<script src="/js/bank.js"></script>',
    },
    `<section class="page-section"><div class="container">
      <div class="page-hero">
        <div>
          <h1>শিক্ষক প্রশ্ন ব্যাংক ব্রাউজ ও সার্চ করুন</h1>
          <p>সারা বাংলাদেশের শিক্ষকদের শেয়ার করা NCTB প্রশ্ন দেখুন, সেভ করুন এবং নিজের প্রশ্নপত্রে ব্যবহার করুন।</p>
        </div>
        <div class="hero-actions">
          <a href="/bank/question/new" class="btn btn-primary">+ নতুন প্রশ্ন জমা দিন</a>
          <a href="/bank/library" class="btn btn-outline">আমার লাইব্রেরি</a>
          <a href="/bank/leaderboard" class="btn btn-ghost">লিডারবোর্ড</a>
        </div>
      </div>

      <div class="card">
        <div class="grid-3">
          <input type="text" id="bankSearchInput" placeholder="কীওয়ার্ড দিয়ে সার্চ করুন...">
          <select id="bankTypeFilter">
            <option value="">সব ধরন</option>
            <option value="MCQ">MCQ</option>
            <option value="SQ">সংক্ষিপ্ত (SQ)</option>
            <option value="CQ">সৃজনশীল (CQ)</option>
          </select>
          <button type="button" class="btn btn-primary" id="bankSearchBtn">সার্চ</button>
        </div>
      </div>

      <div id="bankList" class="mt-3"></div>
    </div></section>`
  );
  return c.html(html);
});

bankPageRoutes.get('/bank/question/new', requireTeacher, async (c) => {
  const classesRes = await c.env.DB.prepare('SELECT id, name, name_bn FROM classes WHERE is_active = 1 ORDER BY "order"').all<{
    id: number;
    name: string;
    name_bn: string | null;
  }>();
  return c.html(
    renderPageLayout(
      { title: 'নতুন প্রশ্ন যোগ করুন', user: c.get('user'), activeNav: 'bank' },
      `<section class="page-section"><div class="container card">
        <h1>প্রশ্ন ব্যাংকে প্রশ্ন যোগ করুন</h1>
        <form id="bankNewForm" class="stack-form">
          <div class="grid-3">
            <label>ধরন
              <select id="bqType"><option value="MCQ">MCQ</option><option value="SQ">সংক্ষিপ্ত</option><option value="CQ">সৃজনশীল</option></select>
            </label>
            <label>শ্রেণি
              <select id="bqClass"><option value="">-- শ্রেণি --</option>${(classesRes.results || []).map((cl) => `<option value="${cl.id}">${escapeHtml(cl.name_bn || cl.name)}</option>`).join('')}</select>
            </label>
            <label>পাবলিশ মোড
              <select id="bqVisibility"><option value="private">প্রাইভেট</option><option value="public">পাবলিক (রিভিউ/প্রকাশ)</option></select>
            </label>
          </div>
          <label>প্রশ্ন / উদ্দীপক <textarea id="bqText" rows="3" required></textarea></label>
          <div id="bqMcqFields">
            <div class="grid-2">
              <input type="text" id="bqOpt1" placeholder="অপশন ক">
              <input type="text" id="bqOpt2" placeholder="অপশন খ">
              <input type="text" id="bqOpt3" placeholder="অপশন গ">
              <input type="text" id="bqOpt4" placeholder="অপশন ঘ">
            </div>
            <label>সঠিক উত্তর (অপশনের সাথে মিল রেখে) <input type="text" id="bqCorrect"></label>
          </div>
          <label>ব্যাখ্যা (ঐচ্ছিক) <textarea id="bqExpl" rows="2"></textarea></label>
          <button type="submit" class="btn btn-primary">সংরক্ষণ করুন</button>
        </form>
        <p id="bqStatus" class="mt-2"></p>
      </div></section>
      <script>
      document.getElementById('bankNewForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const type = document.getElementById('bqType').value;
        const body = {
          question_type: type,
          class_id: Number(document.getElementById('bqClass').value) || null,
          question_text: document.getElementById('bqText').value,
          stem: document.getElementById('bqText').value,
          answer_options: [document.getElementById('bqOpt1').value, document.getElementById('bqOpt2').value, document.getElementById('bqOpt3').value, document.getElementById('bqOpt4').value],
          correct_answer: document.getElementById('bqCorrect').value,
          explanation: document.getElementById('bqExpl').value,
          visibility: document.getElementById('bqVisibility').value
        };
        const r = await fetch('/api/v1/bank/questions', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
        const d = await r.json();
        document.getElementById('bqStatus').textContent = r.ok ? 'প্রশ্ন সংরক্ষিত হয়েছে! স্ট্যাটাস: ' + d.visibility : (d.error || 'Error');
      });
      </script>`
    )
  );
});

bankPageRoutes.get('/bank/library', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare(
    `SELECT bq.* FROM teacher_library tl JOIN bank_questions bq ON bq.id = tl.question_id WHERE tl.teacher_id = ? ORDER BY tl.saved_at DESC`
  )
    .bind(user.id)
    .all<BankQuestionRow>();
  return c.html(
    renderPageLayout(
      { title: 'আমার লাইব্রেরি', user, activeNav: 'bank' },
      `<section class="page-section"><div class="container">
        <h1>আমার সেভ করা প্রশ্নসমূহ</h1>
        ${(rows.results || []).map((q) => `<div class="card mt-2"><strong>${escapeHtml(q.question_type)}</strong>: ${escapeHtml(q.question_text)}</div>`).join('') || '<div class="card"><p class="muted">আপনার লাইব্রেরিতে এখনো কোনো প্রশ্ন নেই।</p></div>'}
      </div></section>`
    )
  );
});

bankPageRoutes.get('/bank/profile', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const profile = await getOrCreateProfile(c.env.DB, user.id, user.display_name);
  const badges = await c.env.DB.prepare('SELECT * FROM teacher_badges WHERE teacher_id = ?')
    .bind(user.id)
    .all<{ badge_name: string; badge_icon: string }>();

  return c.html(
    renderPageLayout(
      { title: 'টিচার প্রোফাইল ও ব্র্যান্ডিং', user, activeNav: 'bank' },
      `<section class="page-section"><div class="container">
        <div class="card">
          <h1>${escapeHtml(profile.display_name || user.display_name)}</h1>
          <p>র‍্যাংক: <strong>${escapeHtml(profile.contributor_rank)}</strong> | রেপুটেশন: <strong>${profile.reputation_score}</strong> | প্রকাশিত প্রশ্ন: <strong>${profile.questions_published}</strong></p>
          <p>ব্যাজসমূহ: ${(badges.results || []).map((b) => `${b.badge_icon} ${escapeHtml(b.badge_name)}`).join(' • ') || 'এখনো কোনো ব্যাজ নেই'}</p>
        </div>
        <div class="card mt-3">
          <h3>প্রতিষ্ঠানের ডিফল্ট ব্র্যান্ডিং (প্রিন্ট স্টুডিওর জন্য)</h3>
          <form id="brandForm" class="stack-form">
            <label>প্রতিষ্ঠানের নাম <input type="text" id="brInst" value="${escapeHtml(profile.institute_name || '')}"></label>
            <label>উপশিরোনাম <input type="text" id="brSub" value="${escapeHtml(profile.institute_subtitle || '')}"></label>
            <label>লোগো URL <input type="text" id="brLogo" value="${escapeHtml(profile.logo_url || '')}"></label>
            <label>ওয়াটারমার্ক <input type="text" id="brWm" value="${escapeHtml(profile.watermark_text || '')}"></label>
            <button type="submit" class="btn btn-primary">ব্র্যান্ডিং সেভ করুন</button>
          </form>
          <p id="brStatus" class="mt-2"></p>
        </div>
      </div></section>
      <script>
      document.getElementById('brandForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const r = await fetch('/api/auth/branding', {
          method:'PUT', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            institute_name: document.getElementById('brInst').value,
            institute_subtitle: document.getElementById('brSub').value,
            logo_url: document.getElementById('brLogo').value,
            watermark_text: document.getElementById('brWm').value
          })
        });
        document.getElementById('brStatus').textContent = r.ok ? 'সেভ হয়েছে!' : 'ত্রুটি হয়েছে';
      });
      </script>`
    )
  );
});

bankPageRoutes.get('/bank/teacher/:userId', async (c) => {
  const targetId = c.req.param('userId');
  const profile = await c.env.DB.prepare('SELECT * FROM teacher_profiles WHERE user_id = ?')
    .bind(targetId)
    .first<{ display_name: string | null; contributor_rank: string; reputation_score: number; questions_published: number }>();
  if (!profile) return c.notFound();
  return c.html(
    renderPageLayout(
      { title: profile.display_name || 'Teacher Profile', user: c.get('user'), activeNav: 'bank' },
      `<section class="page-section"><div class="container card">
        <h1>${escapeHtml(profile.display_name || 'Anonymous Teacher')}</h1>
        <p>${escapeHtml(profile.contributor_rank)} • রেপুটেশন: ${profile.reputation_score} • প্রকাশিত প্রশ্ন: ${profile.questions_published}</p>
      </div></section>`
    )
  );
});

bankPageRoutes.get('/bank/notifications', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const notifs = await c.env.DB.prepare(
    'SELECT * FROM teacher_notifications WHERE teacher_id = ? ORDER BY created_at DESC LIMIT 50'
  )
    .bind(user.id)
    .all<{ id: number; title: string; body: string | null; is_read: number; created_at: string }>();
  return c.html(
    renderPageLayout(
      { title: 'নোটিফিকেশন', user, activeNav: 'bank' },
      `<section class="page-section"><div class="container">
        <h1>নোটিফিকেশন</h1>
        ${(notifs.results || []).map((n) => `<div class="card mt-2"><strong>${escapeHtml(n.title)}</strong><p>${escapeHtml(n.body || '')}</p></div>`).join('') || '<div class="card"><p class="muted">কোনো নতুন নোটিফিকেশন নেই।</p></div>'}
      </div></section>`
    )
  );
});

bankPageRoutes.get('/bank/leaderboard', async (c) => {
  const rows = await c.env.DB.prepare(
    'SELECT user_id, display_name, reputation_score, contributor_rank, questions_published FROM teacher_profiles ORDER BY reputation_score DESC LIMIT 50'
  ).all<{ user_id: string; display_name: string | null; reputation_score: number; contributor_rank: string; questions_published: number }>();
  return c.html(
    renderPageLayout(
      { title: 'টিচার লিডারবোর্ড', user: c.get('user'), activeNav: 'bank' },
      `<section class="page-section"><div class="container card">
        <h1>সেরা শিক্ষক অবদানকারী লিডারবোর্ড</h1>
        <table class="data-table mt-2">
          <thead><tr><th>#</th><th>শিক্ষক</th><th>র‍্যাংক</th><th>প্রকাশিত</th><th>রেপুটেশন</th></tr></thead>
          <tbody>
            ${(rows.results || []).map((t, i) => `<tr><td>${i + 1}</td><td><a href="/bank/teacher/${escapeHtml(t.user_id)}">${escapeHtml(t.display_name || 'Teacher')}</a></td><td>${escapeHtml(t.contributor_rank)}</td><td>${t.questions_published}</td><td>${t.reputation_score}</td></tr>`).join('')}
          </tbody>
        </table>
      </div></section>`
    )
  );
});

// ── Bank JSON APIs (/api/v1/bank/*) ───────────────────────────────────────

bankApiRoutes.get('/profile', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const profile = await getOrCreateProfile(c.env.DB, user.id, user.display_name);
  const badges = await c.env.DB.prepare('SELECT badge_slug, badge_name, badge_icon, awarded_at FROM teacher_badges WHERE teacher_id = ?')
    .bind(user.id)
    .all();
  return c.json({ ...profile, badges: badges.results || [] });
});

bankApiRoutes.put('/profile', requireTeacher, async (c) => {
  const user = c.get('user')!;
  await getOrCreateProfile(c.env.DB, user.id, user.display_name);
  const body = (await c.req.json().catch(() => ({}))) as { display_name?: string };
  if (body.display_name) {
    await c.env.DB.prepare('UPDATE teacher_profiles SET display_name = ? WHERE user_id = ?')
      .bind(body.display_name.trim().slice(0, 200), user.id)
      .run();
  }
  const updated = await getOrCreateProfile(c.env.DB, user.id);
  return c.json(updated);
});

bankApiRoutes.get('/teachers/:userId/profile', async (c) => {
  const userId = c.req.param('userId');
  const profile = await c.env.DB.prepare('SELECT * FROM teacher_profiles WHERE user_id = ?').bind(userId).first();
  if (!profile) return c.json({ error: 'Teacher not found' }, 404);
  const badges = await c.env.DB.prepare('SELECT badge_slug, badge_name, badge_icon, awarded_at FROM teacher_badges WHERE teacher_id = ?')
    .bind(userId)
    .all();
  return c.json({ ...profile, badges: badges.results || [] });
});

bankApiRoutes.get('/leaderboard', async (c) => {
  const rows = await c.env.DB.prepare(
    'SELECT user_id, display_name, reputation_score, contributor_rank, questions_published, is_trusted FROM teacher_profiles ORDER BY reputation_score DESC LIMIT 50'
  ).all();
  return c.json({ teachers: rows.results || [] });
});

bankApiRoutes.post('/questions', requireTeacher, rateLimit(60, 60, 'bank_create_q'), async (c) => {
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as Record<string, unknown>;
  const qType = String(body.question_type || 'MCQ').toUpperCase();
  if (!['MCQ', 'SQ', 'CQ'].includes(qType)) {
    return c.json({ error: 'question_type must be MCQ, SQ, or CQ' }, 400);
  }
  const questionText = String(body.question_text || body.stem || '').trim();
  if (!questionText) return c.json({ error: 'question_text is required' }, 400);

  const profile = await getOrCreateProfile(c.env.DB, user.id, user.display_name);
  const requestedVis = String(body.visibility || 'private');
  const textHash = await computeTextHash(questionText);

  let visibility = 'private';
  let status = 'draft';
  if (requestedVis === 'public') {
    if (profile.is_trusted) {
      visibility = 'public';
      status = 'approved';
    } else {
      visibility = 'pending';
      status = 'submitted';
    }
  }

  const ins = await c.env.DB.prepare(
    `INSERT INTO bank_questions (
       teacher_id, class_id, subject_id, chapter_id, question_type, question_text,
       answer, explanation, answer_options, correct_answer,
       stem, part_ka, part_kha, part_ga, part_gha, marks_ka, marks_kha, marks_ga, marks_gha,
       topic, difficulty, marks, board, year, visibility, status, origin, text_hash, published_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      user.id,
      body.class_id ? Number(body.class_id) : null,
      body.subject_id ? Number(body.subject_id) : null,
      body.chapter_id ? Number(body.chapter_id) : null,
      qType,
      questionText,
      body.answer ? String(body.answer) : null,
      body.explanation ? String(body.explanation) : null,
      qType === 'MCQ' ? JSON.stringify(body.answer_options || []) : null,
      qType === 'MCQ' ? String(body.correct_answer || '') : null,
      qType === 'CQ' ? String(body.stem || questionText) : null,
      body.part_ka ? String(body.part_ka) : null,
      body.part_kha ? String(body.part_kha) : null,
      body.part_ga ? String(body.part_ga) : null,
      body.part_gha ? String(body.part_gha) : null,
      body.marks_ka ? Number(body.marks_ka) : 1,
      body.marks_kha ? Number(body.marks_kha) : 2,
      body.marks_ga ? Number(body.marks_ga) : 3,
      body.marks_gha ? Number(body.marks_gha) : 4,
      body.topic ? String(body.topic) : null,
      String(body.difficulty || 'medium'),
      Number(body.marks) || (qType === 'CQ' ? 10 : qType === 'SQ' ? 2 : 1),
      body.board ? String(body.board) : null,
      body.year ? Number(body.year) : null,
      visibility,
      status,
      String(body.origin || 'manual'),
      textHash,
      visibility === 'public' ? new Date().toISOString() : null
    )
    .run();

  const qId = Number(ins.meta.last_row_id);

  if (visibility === 'pending') {
    await c.env.DB.prepare('INSERT INTO moderation_queue (question_id, submitted_by, priority) VALUES (?, ?, 5)')
      .bind(qId, user.id)
      .run();
  }

  const updatedProf = await refreshProfileCounters(c.env.DB, user.id);
  if (visibility === 'public') {
    await recalculateReputation(c.env.DB, user.id);
    await evaluateAndAwardBadges(c.env.DB, updatedProf);
  }

  const row = await c.env.DB.prepare('SELECT * FROM bank_questions WHERE id = ?').bind(qId).first<BankQuestionRow>();
  return c.json(serializeBankQuestion(row!, true), 201);
});

bankApiRoutes.get('/questions', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare(
    'SELECT * FROM bank_questions WHERE teacher_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 100'
  )
    .bind(user.id)
    .all<BankQuestionRow>();
  return c.json({ items: (rows.results || []).map((r) => serializeBankQuestion(r, true)) });
});

bankApiRoutes.get('/questions/:id', async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user');
  const row = await c.env.DB.prepare('SELECT * FROM bank_questions WHERE id = ? AND is_active = 1')
    .bind(id)
    .first<BankQuestionRow>();
  if (!row) return c.json({ error: 'Not found' }, 404);
  if (row.visibility !== 'public' && (!user || row.teacher_id !== user.id)) {
    return c.json({ error: 'Not found' }, 404);
  }
  return c.json(serializeBankQuestion(row, Boolean(user)));
});

bankApiRoutes.put('/questions/:id', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  const existing = await c.env.DB.prepare('SELECT * FROM bank_questions WHERE id = ? AND teacher_id = ? AND is_active = 1')
    .bind(id, user.id)
    .first<BankQuestionRow>();
  if (!existing) return c.json({ error: 'Not found' }, 404);

  const body = (await c.req.json().catch(() => ({}))) as Record<string, unknown>;
  const qText = body.question_text !== undefined ? String(body.question_text) : existing.question_text;
  const hash = await computeTextHash(qText);

  await c.env.DB.prepare(
    `UPDATE bank_questions SET question_text = ?, explanation = COALESCE(?, explanation),
     answer_options = COALESCE(?, answer_options), correct_answer = COALESCE(?, correct_answer),
     text_hash = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?`
  )
    .bind(
      qText,
      body.explanation !== undefined ? String(body.explanation) : null,
      body.answer_options ? JSON.stringify(body.answer_options) : null,
      body.correct_answer !== undefined ? String(body.correct_answer) : null,
      hash,
      id
    )
    .run();

  const updated = await c.env.DB.prepare('SELECT * FROM bank_questions WHERE id = ?').bind(id).first<BankQuestionRow>();
  return c.json(serializeBankQuestion(updated!, true));
});

bankApiRoutes.delete('/questions/:id', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  const res = await c.env.DB.prepare('UPDATE bank_questions SET is_active = 0 WHERE id = ? AND teacher_id = ?')
    .bind(id, user.id)
    .run();
  if (!res.meta.changes) return c.json({ error: 'Not found' }, 404);
  await refreshProfileCounters(c.env.DB, user.id);
  return c.json({ success: true });
});

bankApiRoutes.get('/browse/classes', async (c) => {
  const rows = await c.env.DB.prepare('SELECT id, name, name_bn FROM classes WHERE is_active = 1 ORDER BY "order"').all();
  return c.json({ classes: rows.results || [] });
});

bankApiRoutes.get('/browse/subjects/:classId', async (c) => {
  const classId = Number(c.req.param('classId'));
  const rows = await c.env.DB.prepare('SELECT id, name, name_bn FROM subjects WHERE class_id = ? AND is_active = 1 ORDER BY "order"')
    .bind(classId)
    .all();
  return c.json({ subjects: rows.results || [] });
});

bankApiRoutes.get('/browse/chapters/:subjectId', async (c) => {
  const subjectId = Number(c.req.param('subjectId'));
  const rows = await c.env.DB.prepare('SELECT id, name, name_bn, chapter_number FROM chapters WHERE subject_id = ? AND is_active = 1 ORDER BY "order"')
    .bind(subjectId)
    .all();
  return c.json({ chapters: rows.results || [] });
});

bankApiRoutes.get('/browse/chapters/:chapterId/questions', async (c) => {
  const chapterId = Number(c.req.param('chapterId'));
  const qType = c.req.query('type');
  let sql = "SELECT * FROM bank_questions WHERE chapter_id = ? AND visibility = 'public' AND is_active = 1";
  const binds: unknown[] = [chapterId];
  if (qType) {
    sql += ' AND question_type = ?';
    binds.push(qType.toUpperCase());
  }
  sql += ' ORDER BY usage_count DESC, id DESC LIMIT 50';
  const rows = await c.env.DB.prepare(sql).bind(...binds).all<BankQuestionRow>();
  return c.json({ items: (rows.results || []).map((r) => serializeBankQuestion(r, Boolean(c.get('user')))) });
});

bankApiRoutes.get('/search', async (c) => {
  const q = (c.req.query('q') || '').trim();
  const qType = (c.req.query('type') || '').trim().toUpperCase();
  const limit = Math.min(Number(c.req.query('limit')) || 25, 60);

  let rows: BankQuestionRow[] = [];
  if (q) {
    // Use FTS5 with fallback to LIKE if FTS query syntax has special chars
    try {
      const ftsQuery = q.replace(/["'*]/g, ' ').trim();
      let sql = `SELECT bq.* FROM bank_questions_fts fts
                 JOIN bank_questions bq ON bq.id = fts.rowid
                 WHERE bank_questions_fts MATCH ? AND bq.visibility = 'public' AND bq.is_active = 1`;
      const binds: unknown[] = [ftsQuery];
      if (qType && ['MCQ', 'SQ', 'CQ'].includes(qType)) {
        sql += ' AND bq.question_type = ?';
        binds.push(qType);
      }
      sql += ' LIMIT ?';
      binds.push(limit);
      const res = await c.env.DB.prepare(sql).bind(...binds).all<BankQuestionRow>();
      rows = res.results || [];
    } catch {
      let sql = "SELECT * FROM bank_questions WHERE visibility = 'public' AND is_active = 1 AND (question_text LIKE ? OR topic LIKE ?)";
      const binds: unknown[] = [`%${q}%`, `%${q}%`];
      if (qType && ['MCQ', 'SQ', 'CQ'].includes(qType)) {
        sql += ' AND question_type = ?';
        binds.push(qType);
      }
      sql += ' LIMIT ?';
      binds.push(limit);
      const res = await c.env.DB.prepare(sql).bind(...binds).all<BankQuestionRow>();
      rows = res.results || [];
    }
  } else {
    let sql = "SELECT * FROM bank_questions WHERE visibility = 'public' AND is_active = 1";
    const binds: unknown[] = [];
    if (qType && ['MCQ', 'SQ', 'CQ'].includes(qType)) {
      sql += ' AND question_type = ?';
      binds.push(qType);
    }
    sql += ' ORDER BY created_at DESC LIMIT ?';
    binds.push(limit);
    const res = await c.env.DB.prepare(sql).bind(...binds).all<BankQuestionRow>();
    rows = res.results || [];
  }

  return c.json({ items: rows.map((r) => serializeBankQuestion(r, Boolean(c.get('user')))) });
});

bankApiRoutes.get('/questions/:id/duplicate-check', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const row = await c.env.DB.prepare('SELECT question_text FROM bank_questions WHERE id = ?').bind(id).first<{ question_text: string }>();
  if (!row) return c.json({ error: 'Not found' }, 404);
  const dupes = await findDuplicates(c.env.DB, row.question_text, id);
  return c.json({ has_duplicates: dupes.length > 0, duplicates: dupes });
});

bankApiRoutes.post('/questions/:id/use', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  await c.env.DB.prepare(
    "INSERT OR IGNORE INTO question_interactions (question_id, teacher_id, action_type) VALUES (?, ?, 'used')"
  )
    .bind(id, user.id)
    .run();
  await c.env.DB.prepare('UPDATE bank_questions SET usage_count = usage_count + 1 WHERE id = ?').bind(id).run();
  return c.json({ success: true });
});

bankApiRoutes.post('/questions/:id/save', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  await c.env.DB.prepare('INSERT OR IGNORE INTO teacher_library (teacher_id, question_id) VALUES (?, ?)')
    .bind(user.id, id)
    .run();
  await c.env.DB.prepare(
    "INSERT OR IGNORE INTO question_interactions (question_id, teacher_id, action_type) VALUES (?, ?, 'saved')"
  )
    .bind(id, user.id)
    .run();
  return c.json({ success: true });
});

bankApiRoutes.delete('/questions/:id/save', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  await c.env.DB.prepare('DELETE FROM teacher_library WHERE teacher_id = ? AND question_id = ?')
    .bind(user.id, id)
    .run();
  return c.json({ success: true });
});

bankApiRoutes.post('/questions/:id/rate', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as { rating?: number };
  const rating = Math.min(5, Math.max(1, Number(body.rating) || 5));

  const existing = await c.env.DB.prepare(
    "SELECT id, rating_value FROM question_interactions WHERE question_id = ? AND teacher_id = ? AND action_type = 'rated'"
  )
    .bind(id, user.id)
    .first<{ id: number; rating_value: number | null }>();

  if (existing) {
    const delta = rating - (existing.rating_value || 0);
    await c.env.DB.prepare('UPDATE question_interactions SET rating_value = ? WHERE id = ?').bind(rating, existing.id).run();
    await c.env.DB.prepare('UPDATE bank_questions SET rating_total = rating_total + ? WHERE id = ?').bind(delta, id).run();
  } else {
    await c.env.DB.prepare(
      "INSERT INTO question_interactions (question_id, teacher_id, action_type, rating_value) VALUES (?, ?, 'rated', ?)"
    )
      .bind(id, user.id, rating)
      .run();
    await c.env.DB.prepare('UPDATE bank_questions SET rating_total = rating_total + ?, rating_count = rating_count + 1 WHERE id = ?')
      .bind(rating, id)
      .run();
  }
  return c.json({ success: true, rating });
});

bankApiRoutes.post('/questions/:id/copy', requireTeacher, async (c) => {
  const id = Number(c.req.param('id'));
  const user = c.get('user')!;
  const src = await c.env.DB.prepare("SELECT * FROM bank_questions WHERE id = ? AND visibility = 'public' AND is_active = 1")
    .bind(id)
    .first<BankQuestionRow>();
  if (!src) return c.json({ error: 'Question not found' }, 404);

  const ins = await c.env.DB.prepare(
    `INSERT INTO bank_questions (teacher_id, class_id, subject_id, chapter_id, question_type, question_text, answer, explanation, answer_options, correct_answer, stem, part_ka, part_kha, part_ga, part_gha, marks_ka, marks_kha, marks_ga, marks_gha, topic, difficulty, marks, board, year, visibility, status, origin, source_question_id, text_hash)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'private', 'draft', 'copied', ?, ?)`
  )
    .bind(
      user.id, src.class_id, src.subject_id, src.chapter_id, src.question_type, src.question_text,
      src.answer, src.explanation, src.answer_options, src.correct_answer, src.stem,
      src.part_ka, src.part_kha, src.part_ga, src.part_gha, src.marks_ka, src.marks_kha, src.marks_ga, src.marks_gha,
      src.topic, src.difficulty, src.marks, src.board, src.year, src.id, src.text_hash
    )
    .run();

  return c.json({ success: true, copied_id: Number(ins.meta.last_row_id) }, 201);
});

bankApiRoutes.get('/library', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare(
    'SELECT bq.* FROM teacher_library tl JOIN bank_questions bq ON bq.id = tl.question_id WHERE tl.teacher_id = ? ORDER BY tl.saved_at DESC'
  )
    .bind(user.id)
    .all<BankQuestionRow>();
  return c.json({ items: (rows.results || []).map((r) => serializeBankQuestion(r, true)) });
});

bankApiRoutes.get('/notifications', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare('SELECT * FROM teacher_notifications WHERE teacher_id = ? ORDER BY created_at DESC LIMIT 50')
    .bind(user.id)
    .all();
  return c.json({ notifications: rows.results || [] });
});

bankApiRoutes.post('/notifications/:id/read', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  await c.env.DB.prepare('UPDATE teacher_notifications SET is_read = 1 WHERE id = ? AND teacher_id = ?')
    .bind(id, user.id)
    .run();
  return c.json({ success: true });
});

bankApiRoutes.post('/notifications/read-all', requireTeacher, async (c) => {
  const user = c.get('user')!;
  await c.env.DB.prepare('UPDATE teacher_notifications SET is_read = 1 WHERE teacher_id = ?').bind(user.id).run();
  return c.json({ success: true });
});
