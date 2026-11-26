import { Hono } from 'hono';
import type { AppContextEnv } from '../types';
import { createSession, requireAdmin, requireEditorOrAdmin } from '../lib/auth';
import { encryptSecret, hashPassword, verifyPassword } from '../lib/crypto';
import { DEFAULT_AI_PROMPT_TEMPLATE, runAiGenerationCycle } from '../services/ai-generator';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';

export const adminRoutes = new Hono<AppContextEnv>();

async function logAdminActivity(
  db: D1Database,
  userId: number,
  action: string,
  entityType: string,
  entityId?: number,
  entityName?: string
) {
  await db
    .prepare('INSERT INTO activity_logs (user_id, action, entity_type, entity_id, entity_name) VALUES (?, ?, ?, ?, ?)')
    .bind(userId, action, entityType, entityId ?? null, entityName ?? null)
    .run();
}

adminRoutes.get('/login', (c) => {
  const user = c.get('user');
  if (user && (user.is_admin || user.role === 'editor')) return c.redirect('/admin/dashboard');
  const error = c.req.query('error') || '';
  return c.html(
    renderPageLayout(
      { title: 'অ্যাডমিন লগইন', user: null },
      `<section class="auth-section"><div class="container auth-card">
        <h1>অ্যাডমিন প্যানেল লগইন</h1>
        ${error ? `<div class="alert error">${escapeHtml(error)}</div>` : ''}
        <form method="POST" action="/admin/login" class="stack-form">
          <label>ইউজারনেম বা ইমেইল <input type="text" name="username" required></label>
          <label>পাসওয়ার্ড <input type="password" name="password" required></label>
          <button type="submit" class="btn btn-primary btn-block">লগইন</button>
        </form>
      </div></section>`
    )
  );
});

adminRoutes.post('/login', async (c) => {
  const form = await c.req.parseBody();
  const username = String(form.username || '').trim();
  const password = String(form.password || '');

  const row = await c.env.DB.prepare(
    "SELECT id, password_hash, role, is_admin, is_active_user FROM users WHERE (LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)) AND (role IN ('admin', 'editor') OR is_admin = 1)"
  )
    .bind(username, username)
    .first<{ id: number; password_hash: string; role: string; is_admin: number; is_active_user: number }>();

  if (!row || !row.is_active_user || !(await verifyPassword(password, row.password_hash))) {
    return c.redirect('/admin/login?error=Invalid+admin+credentials');
  }

  await createSession(c, row.id);
  return c.redirect('/admin/dashboard');
});

adminRoutes.use('/dashboard*', requireEditorOrAdmin);
adminRoutes.use('/classes*', requireEditorOrAdmin);
adminRoutes.use('/subjects*', requireEditorOrAdmin);
adminRoutes.use('/chapters*', requireEditorOrAdmin);
adminRoutes.use('/questions*', requireEditorOrAdmin);
adminRoutes.use('/short-questions*', requireEditorOrAdmin);
adminRoutes.use('/cq-questions*', requireEditorOrAdmin);
adminRoutes.use('/papers*', requireEditorOrAdmin);
adminRoutes.use('/bank*', requireAdmin);
adminRoutes.use('/users*', requireAdmin);
adminRoutes.use('/ai-generator*', requireAdmin);
adminRoutes.use('/activity-log*', requireAdmin);

adminRoutes.get('/', (c) => c.redirect('/admin/dashboard'));

adminRoutes.get('/dashboard', async (c) => {
  const user = c.get('user')!;
  const [classesC, subjectsC, chaptersC, mcqC, sqC, cqC, papersC, modC] = await Promise.all([
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM classes').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM subjects').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM chapters').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM questions').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM short_questions').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM cq_questions').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM generated_papers').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM moderation_queue WHERE decision IS NULL').first<{ cnt: number }>(),
  ]);

  return c.html(
    renderPageLayout(
      { title: 'Admin Dashboard', user },
      `<section class="page-section"><div class="container">
        <h1>অ্যাডমিন ড্যাশবোর্ড</h1>
        <div class="feature-grid mt-2">
          <div class="card"><h3>শ্রেণি / বিষয় / অধ্যায়</h3><p>${classesC?.cnt || 0} / ${subjectsC?.cnt || 0} / ${chaptersC?.cnt || 0}</p><a href="/admin/classes" class="btn btn-sm btn-outline">ম্যানেজ</a></div>
          <div class="card"><h3>প্রশ্ন (MCQ / SQ / CQ)</h3><p>${mcqC?.cnt || 0} / ${sqC?.cnt || 0} / ${cqC?.cnt || 0}</p><a href="/admin/questions" class="btn btn-sm btn-outline">ম্যানেজ</a></div>
          <div class="card"><h3>তৈরিকৃত প্রশ্নপত্র</h3><p>${papersC?.cnt || 0}</p><a href="/admin/papers" class="btn btn-sm btn-outline">দেখুন</a></div>
          <div class="card"><h3>মডারেশন কিউ</h3><p>${modC?.cnt || 0} অপেক্ষমাণ</p><a href="/admin/bank" class="btn btn-sm btn-primary">রিভিউ</a></div>
        </div>
        <div class="row-actions mt-3">
          <a href="/admin/questions/bulk-upload" class="btn btn-primary">JSON বাল্ক আপলোড</a>
          <a href="/admin/ai-generator" class="btn btn-outline">AI জেনারেটর</a>
          <a href="/admin/users" class="btn btn-outline">ইউজার ম্যানেজমেন্ট</a>
          <a href="/admin/activity-log" class="btn btn-ghost">অ্যাক্টিভিটি লগ</a>
        </div>
      </div></section>`
    )
  );
});

adminRoutes.get('/classes', async (c) => {
  const rows = await c.env.DB.prepare('SELECT * FROM classes ORDER BY "order", id').all<{ id: number; name: string; name_bn: string | null; level: string | null; is_active: number }>();
  return c.html(
    renderPageLayout(
      { title: 'Classes - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container">
        <h1>শ্রেণি ম্যানেজমেন্ট</h1>
        <form method="POST" action="/admin/classes/add" class="card row-actions mt-2">
          <input type="text" name="name" placeholder="Class 11" required>
          <input type="text" name="name_bn" placeholder="একাদশ শ্রেণি">
          <input type="text" name="level" placeholder="Higher Secondary">
          <button type="submit" class="btn btn-primary">যোগ করুন</button>
        </form>
        <div class="card mt-2"><table class="data-table"><tbody>
          ${(rows.results || []).map((r) => `<tr><td>${r.id}</td><td>${escapeHtml(r.name)} (${escapeHtml(r.name_bn || '')})</td><td><form method="POST" action="/admin/classes/delete/${r.id}"><button class="btn btn-sm btn-danger">ডিলিট</button></form></td></tr>`).join('')}
        </tbody></table></div>
      </div></section>`
    )
  );
});

adminRoutes.post('/classes/add', async (c) => {
  const form = await c.req.parseBody();
  const name = String(form.name || '').trim();
  if (!name) return c.json({ error: 'Name required' }, 400);
  const ins = await c.env.DB.prepare('INSERT INTO classes (name, name_bn, level) VALUES (?, ?, ?)')
    .bind(name, String(form.name_bn || ''), String(form.level || ''))
    .run();
  await logAdminActivity(c.env.DB, c.get('user')!.numeric_id, 'add', 'class', Number(ins.meta.last_row_id), name);
  return c.redirect('/admin/classes');
});

adminRoutes.post('/classes/delete/:id', requireAdmin, async (c) => {
  const id = Number(c.req.param('id'));
  await c.env.DB.prepare('DELETE FROM classes WHERE id = ?').bind(id).run();
  await logAdminActivity(c.env.DB, c.get('user')!.numeric_id, 'delete', 'class', id);
  return c.redirect('/admin/classes');
});

adminRoutes.get('/questions', async (c) => {
  const rows = await c.env.DB.prepare(
    `SELECT q.id, q.question_text, q.question_type, q.correct_answer, q.board, q.year, ch.name_bn as chapter_name
     FROM questions q LEFT JOIN chapters ch ON ch.id = q.chapter_id ORDER BY q.id DESC LIMIT 50`
  ).all<{ id: number; question_text: string; question_type: string; correct_answer: string; board: string | null; year: number | null; chapter_name: string | null }>();
  return c.html(
    renderPageLayout(
      { title: 'Questions - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container">
        <div class="row-between">
          <h1>MCQ প্রশ্ন তালিকা (সর্বশেষ ৫০)</h1>
          <a href="/admin/questions/bulk-upload" class="btn btn-primary">বাল্ক আপলোড</a>
        </div>
        <div class="card mt-2"><table class="data-table"><tbody>
          ${(rows.results || []).map((q) => `<tr><td>#${q.id}</td><td>${escapeHtml(q.question_text.slice(0, 120))}</td><td>${escapeHtml(q.correct_answer)}</td><td><form method="POST" action="/admin/questions/delete/${q.id}"><button class="btn btn-sm btn-danger">ডিলিট</button></form></td></tr>`).join('')}
        </tbody></table></div>
      </div></section>`
    )
  );
});

adminRoutes.post('/questions/add', async (c) => {
  const body = (await c.req.json().catch(() => null)) || (await c.req.parseBody());
  const qText = String(body.question_text || '').trim();
  const chapterId = Number(body.chapter_id);
  if (!qText || !chapterId) return c.json({ error: 'question_text and chapter_id required' }, 400);

  let opts = body.answer_options;
  if (typeof opts === 'string') {
    try {
      opts = JSON.parse(opts);
    } catch {
      opts = opts.split('|').map((s: string) => s.trim());
    }
  }
  const ins = await c.env.DB.prepare(
    `INSERT INTO questions (question_text, question_type, sub_options, final_prompt, answer_options, correct_answer, explanation, board, year, chapter_id, created_by)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      qText,
      String(body.question_type || 'simple'),
      body.sub_options ? JSON.stringify(body.sub_options) : null,
      body.final_prompt ? String(body.final_prompt) : null,
      JSON.stringify(opts || []),
      String(body.correct_answer || ''),
      body.explanation ? String(body.explanation) : null,
      body.board ? String(body.board) : null,
      body.year ? Number(body.year) : null,
      chapterId,
      c.get('user')!.numeric_id
    )
    .run();

  return c.json({ success: true, id: Number(ins.meta.last_row_id) }, 201);
});

adminRoutes.post('/questions/delete/:id', requireAdmin, async (c) => {
  const id = Number(c.req.param('id'));
  await c.env.DB.prepare('DELETE FROM questions WHERE id = ?').bind(id).run();
  await logAdminActivity(c.env.DB, c.get('user')!.numeric_id, 'delete', 'question', id);
  return c.redirect('/admin/questions');
});

adminRoutes.get('/questions/bulk-upload', async (c) => {
  const chapters = await c.env.DB.prepare(
    'SELECT ch.id, ch.name_bn, ch.name, s.name_bn as sub_bn FROM chapters ch JOIN subjects s ON s.id = ch.subject_id LIMIT 100'
  ).all<{ id: number; name_bn: string | null; name: string; sub_bn: string | null }>();
  return c.html(
    renderPageLayout(
      { title: 'Bulk Upload - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>JSON বাল্ক প্রশ্ন আপলোড</h1>
        <form method="POST" action="/admin/questions/bulk-upload" class="stack-form">
          <label>অধ্যায়
            <select name="chapter_id" required>
              ${(chapters.results || []).map((ch) => `<option value="${ch.id}">${escapeHtml(ch.sub_bn || '')} — ${escapeHtml(ch.name_bn || ch.name)}</option>`).join('')}
            </select>
          </label>
          <label>JSON অ্যারে
            <textarea name="json_data" rows="10" required placeholder='[{"question_text":"...","type":"simple","answer_options":["a","b","c","d"],"correct_answer":"a","explanation":"..."}]'></textarea>
          </label>
          <button type="submit" class="btn btn-primary">আপলোড করুন</button>
        </form>
      </div></section>`
    )
  );
});

adminRoutes.post('/questions/bulk-upload', async (c) => {
  let chapterId = 0;
  let items: Array<Record<string, unknown>> = [];
  const ct = c.req.header('content-type') || '';
  if (ct.includes('application/json')) {
    const body = (await c.req.json()) as { chapter_id?: number; questions?: Array<Record<string, unknown>> };
    chapterId = Number(body.chapter_id);
    items = body.questions || [];
  } else {
    const form = await c.req.parseBody();
    chapterId = Number(form.chapter_id);
    items = JSON.parse(String(form.json_data || '[]'));
  }

  if (!chapterId || !Array.isArray(items) || items.length === 0) {
    return c.json({ error: 'Valid chapter_id and JSON array required' }, 400);
  }

  const stmts = items
    .filter((q) => q.question_text && Array.isArray(q.answer_options) && q.correct_answer)
    .map((q) =>
      c.env.DB.prepare(
        `INSERT INTO questions (question_text, question_type, sub_options, final_prompt, answer_options, correct_answer, explanation, board, year, chapter_id, created_by)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      ).bind(
        String(q.question_text),
        q.type === 'complex' ? 'complex' : 'simple',
        q.type === 'complex' ? JSON.stringify(q.sub_options || []) : null,
        q.type === 'complex' ? String(q.final_prompt || 'নিচের কোনটি সঠিক?') : null,
        JSON.stringify(q.answer_options),
        String(q.correct_answer),
        q.explanation ? String(q.explanation) : null,
        q.board ? String(q.board) : null,
        q.year ? Number(q.year) : null,
        chapterId,
        c.get('user')!.numeric_id
      )
    );

  if (stmts.length > 0) await c.env.DB.batch(stmts);
  if (ct.includes('application/json')) return c.json({ success: true, imported: stmts.length });
  return c.redirect('/admin/questions');
});

adminRoutes.get('/bank', async (c) => {
  return c.html(
    renderPageLayout(
      { title: 'Bank Moderation - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container">
        <h1>টিচার প্রশ্ন ব্যাংক মডারেশন</h1>
        <div id="modQueueList" class="mt-2">লোড হচ্ছে...</div>
      </div></section>
      <script>
      async function loadQueue(){
        const r = await fetch('/api/v1/admin/bank/moderation/queue');
        const d = await r.json();
        document.getElementById('modQueueList').innerHTML = (d.items || []).map(item => \`
          <div class="card mt-2">
            <p><strong>#\${item.id} (\${item.teacher_name})</strong>: \${item.question?.question_text || ''}</p>
            <div class="row-actions">
              <button class="btn btn-sm btn-primary" onclick="decide(\${item.id},'approved')">অনুমোদন</button>
              <button class="btn btn-sm btn-danger" onclick="decide(\${item.id},'rejected')">বাতিল</button>
            </div>
          </div>\`).join('') || '<div class="card">কোনো অপেক্ষমাণ প্রশ্ন নেই।</div>';
      }
      async function decide(id, decision){
        await fetch('/api/v1/admin/bank/moderation/' + id + '/decide', {
          method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ decision })
        });
        loadQueue();
      }
      loadQueue();
      </script>`
    )
  );
});

adminRoutes.get('/papers', async (c) => {
  const rows = await c.env.DB.prepare('SELECT id, title, question_count, download_count, created_at FROM generated_papers ORDER BY id DESC LIMIT 50').all<{
    id: number;
    title: string | null;
    question_count: number | null;
    download_count: number;
    created_at: string;
  }>();
  return c.html(
    renderPageLayout(
      { title: 'Papers - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>তৈরিকৃত প্রশ্নপত্রসমূহ</h1>
        <table class="data-table mt-2"><tbody>
          ${(rows.results || []).map((p) => `<tr><td>#${p.id}</td><td>${escapeHtml(p.title || 'Untitled')}</td><td>${p.question_count || 0} Q</td><td>${p.download_count} DL</td><td><a href="/papers/${p.id}/studio">Open</a></td></tr>`).join('')}
        </tbody></table>
      </div></section>`
    )
  );
});

adminRoutes.get('/users', async (c) => {
  const rows = await c.env.DB.prepare('SELECT id, username, email, role, is_active_user, created_at FROM users ORDER BY id DESC LIMIT 100').all<{
    id: number;
    username: string;
    email: string;
    role: string;
    is_active_user: number;
    created_at: string;
  }>();
  return c.html(
    renderPageLayout(
      { title: 'Users - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>ইউজার ম্যানেজমেন্ট</h1>
        <table class="data-table mt-2"><tbody>
          ${(rows.results || []).map((u) => `<tr><td>#${u.id}</td><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.email)}</td><td>${escapeHtml(u.role)}</td></tr>`).join('')}
        </tbody></table>
      </div></section>`
    )
  );
});

adminRoutes.post('/users/add', async (c) => {
  const body = (await c.req.json().catch(() => null)) || (await c.req.parseBody());
  const username = String(body.username || '').trim();
  const email = String(body.email || '').trim().toLowerCase();
  const password = String(body.password || '');
  const role = ['admin', 'editor', 'teacher'].includes(String(body.role)) ? String(body.role) : 'editor';
  if (!username || !email || password.length < 6) return c.json({ error: 'Invalid user data' }, 400);

  const pwHash = await hashPassword(password);
  const ins = await c.env.DB.prepare(
    `INSERT INTO users (public_uid, username, email, display_name, password_hash, role, is_admin, created_by_id)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(crypto.randomUUID(), username, email, username, pwHash, role, role === 'admin' ? 1 : 0, c.get('user')!.numeric_id)
    .run();
  return c.json({ success: true, id: Number(ins.meta.last_row_id) }, 201);
});

adminRoutes.get('/ai-generator', async (c) => {
  const cfg = await c.env.DB.prepare('SELECT * FROM ai_generator_config LIMIT 1').first<{
    api_provider: string;
    model_name: string;
    questions_per_request: number;
    is_running: number;
    total_questions_generated: number;
    total_duplicates_skipped: number;
    total_errors: number;
  }>();
  const logs = await c.env.DB.prepare('SELECT * FROM ai_generator_logs ORDER BY id DESC LIMIT 20').all<{
    id: number;
    status: string;
    questions_generated: number;
    error_message: string | null;
    created_at: string;
  }>();

  return c.html(
    renderPageLayout(
      { title: 'AI Generator - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container">
        <h1>AI প্রশ্ন জেনারেটর (Cloudflare Cron)</h1>
        <div class="card mt-2">
          <p>স্ট্যাটাস: <strong>${cfg?.is_running ? 'চলমান' : 'বন্ধ'}</strong> | মোট তৈরি: ${cfg?.total_questions_generated || 0} | ডুপ্লিকেট: ${cfg?.total_duplicates_skipped || 0}</p>
          <form method="POST" action="/admin/ai-generator/settings" class="stack-form mt-2">
            <label>Provider <select name="api_provider"><option value="gemini">Gemini</option><option value="openai">OpenAI</option></select></label>
            <label>Model <input type="text" name="model_name" value="${escapeHtml(cfg?.model_name || 'gemini-2.0-flash')}"></label>
            <label>API Key (Leave blank to keep existing) <input type="password" name="api_key"></label>
            <label>Questions per run <input type="number" name="questions_per_request" value="${cfg?.questions_per_request || 5}"></label>
            <button type="submit" class="btn btn-primary">সেটিংস সেভ</button>
          </form>
          <div class="row-actions mt-2">
            <form method="POST" action="/admin/ai-generator/start"><button class="btn btn-primary">Cron চালু করুন</button></form>
            <form method="POST" action="/admin/ai-generator/stop"><button class="btn btn-danger">Cron বন্ধ করুন</button></form>
            <form method="POST" action="/admin/ai-generator/run-now"><button class="btn btn-outline">এখনই চালান</button></form>
          </div>
        </div>
        <div class="card mt-3">
          <h3>সাম্প্রতিক লগ</h3>
          <table class="data-table"><tbody>
            ${(logs.results || []).map((l) => `<tr><td>#${l.id}</td><td>${escapeHtml(l.status)}</td><td>+${l.questions_generated}</td><td>${escapeHtml(l.error_message || '')}</td></tr>`).join('')}
          </tbody></table>
        </div>
      </div></section>`
    )
  );
});

adminRoutes.post('/ai-generator/settings', async (c) => {
  const form = await c.req.parseBody();
  const provider = String(form.api_provider || 'gemini');
  const model = String(form.model_name || 'gemini-2.0-flash');
  const qPerReq = Number(form.questions_per_request) || 5;
  const rawKey = String(form.api_key || '').trim();
  const encKey = rawKey ? await encryptSecret(rawKey, c.env.ENCRYPTION_KEY || '') : null;

  const existing = await c.env.DB.prepare('SELECT id FROM ai_generator_config LIMIT 1').first<{ id: number }>();
  if (!existing) {
    await c.env.DB.prepare(
      'INSERT INTO ai_generator_config (api_key, api_provider, model_name, prompt_template, questions_per_request) VALUES (?, ?, ?, ?, ?)'
    )
      .bind(encKey, provider, model, DEFAULT_AI_PROMPT_TEMPLATE, qPerReq)
      .run();
  } else {
    await c.env.DB.prepare(
      `UPDATE ai_generator_config SET api_key = COALESCE(?, api_key), api_provider = ?, model_name = ?, questions_per_request = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?`
    )
      .bind(encKey, provider, model, qPerReq, existing.id)
      .run();
  }
  return c.redirect('/admin/ai-generator');
});

adminRoutes.post('/ai-generator/start', async (c) => {
  await c.env.DB.prepare('UPDATE ai_generator_config SET is_running = 1').run();
  return c.redirect('/admin/ai-generator');
});

adminRoutes.post('/ai-generator/stop', async (c) => {
  await c.env.DB.prepare('UPDATE ai_generator_config SET is_running = 0').run();
  return c.redirect('/admin/ai-generator');
});

adminRoutes.post('/ai-generator/run-now', async (c) => {
  await runAiGenerationCycle(c.env, true);
  return c.redirect('/admin/ai-generator');
});

adminRoutes.get('/activity-log', async (c) => {
  const rows = await c.env.DB.prepare('SELECT * FROM activity_logs ORDER BY id DESC LIMIT 100').all<{
    id: number;
    action: string;
    entity_type: string;
    entity_id: number | null;
    entity_name: string | null;
    created_at: string;
  }>();
  return c.html(
    renderPageLayout(
      { title: 'Activity Log - Admin', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>অ্যাডমিন অ্যাক্টিভিটি লগ</h1>
        <table class="data-table mt-2"><tbody>
          ${(rows.results || []).map((a) => `<tr><td>${escapeHtml(a.created_at)}</td><td>${escapeHtml(a.action)}</td><td>${escapeHtml(a.entity_type)} #${a.entity_id ?? ''}</td><td>${escapeHtml(a.entity_name || '')}</td></tr>`).join('')}
        </tbody></table>
      </div></section>`
    )
  );
});
