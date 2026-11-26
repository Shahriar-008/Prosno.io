import { Hono } from 'hono';
import { getCookie, setCookie } from 'hono/cookie';
import type { AppContextEnv, McqQuestionPayload } from '../types';
import { requireTeacher } from '../lib/auth';
import { randomToken } from '../lib/crypto';
import { rateLimit } from '../lib/rate-limit';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';
import { toBengaliNumeral } from '../lib/bengali';

export const quizRoutes = new Hono<AppContextEnv>();

interface QuizRow {
  id: number;
  join_code: string;
  title: string;
  question_set_id: number | null;
  teacher_user_id: string;
  questions_json: string;
  time_limit_minutes: number;
  shuffle_questions: number;
  shuffle_options: number;
  show_results_to_students: number;
  status: 'waiting' | 'active' | 'ended';
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

interface QuizSessionRow {
  id: number;
  quiz_id: number;
  student_name: string;
  session_token: string;
  score: number;
  total_questions: number;
  responses_json: string | null;
  time_taken_seconds: number | null;
  status: 'joined' | 'in_progress' | 'submitted';
  joined_at: string;
  submitted_at: string | null;
}

function deterministicShuffle<T>(arr: T[], seedStr: string): { items: T[]; order: number[] } {
  // Simple deterministic PRNG (xorshift32) seeded from seedStr
  let seed = 2166136261;
  for (let i = 0; i < seedStr.length; i++) {
    seed ^= seedStr.charCodeAt(i);
    seed = Math.imul(seed, 16777619);
  }
  const order = arr.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    const j = Math.abs(seed) % (i + 1);
    [order[i], order[j]] = [order[j], order[i]];
  }
  return { items: order.map((idx) => arr[idx]), order };
}

async function generateJoinCode(db: D1Database): Promise<string> {
  for (let i = 0; i < 50; i++) {
    const code = String(Math.floor(1000 + Math.random() * 9000));
    const existing = await db.prepare('SELECT id FROM quizzes WHERE join_code = ?').bind(code).first();
    if (!existing) return code;
  }
  throw new Error('Could not generate unique join code');
}

quizRoutes.post('/create', requireTeacher, rateLimit(20, 3600, 'quiz_create'), async (c) => {
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) return c.json({ error: 'No data provided.' }, 400);

  const setId = Number(body.question_set_id);
  if (!setId) return c.json({ error: 'No question set selected.' }, 400);

  const qs = await c.env.DB.prepare('SELECT * FROM question_sets WHERE id = ? AND user_id = ?')
    .bind(setId, user.id)
    .first<{ id: number; name: string; questions_json: string }>();
  if (!qs) return c.json({ error: 'Question set not found.' }, 404);

  const parsedQs = JSON.parse(qs.questions_json || '[]') as McqQuestionPayload[];
  if (parsedQs.length === 0) return c.json({ error: 'Question set is empty.' }, 400);

  const joinCode = await generateJoinCode(c.env.DB);
  const title = String(body.title || qs.name).slice(0, 200);
  const timeLimit = Math.min(Number(body.time_limit) || 30, 120);

  const ins = await c.env.DB.prepare(
    `INSERT INTO quizzes (join_code, title, question_set_id, teacher_user_id, questions_json, time_limit_minutes, shuffle_questions, shuffle_options, show_results_to_students)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      joinCode,
      title,
      qs.id,
      user.id,
      qs.questions_json,
      timeLimit,
      body.shuffle_questions === false ? 0 : 1,
      body.shuffle_options === false ? 0 : 1,
      body.show_results === false ? 0 : 1
    )
    .run();

  return c.json({
    success: true,
    quiz: {
      id: Number(ins.meta.last_row_id),
      join_code: joinCode,
      title,
      status: 'waiting',
      time_limit_minutes: timeLimit,
      question_count: parsedQs.length,
    },
    lobby_url: `/quiz/${joinCode}/lobby`,
  });
});

quizRoutes.get('/my-quizzes', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare(
    `SELECT q.*, (SELECT COUNT(*) FROM quiz_sessions s WHERE s.quiz_id = q.id) as student_count
     FROM quizzes q WHERE q.teacher_user_id = ? ORDER BY q.created_at DESC`
  )
    .bind(user.id)
    .all<QuizRow & { student_count: number }>();
  return c.json({
    quizzes: (rows.results || []).map((q) => ({
      id: q.id,
      join_code: q.join_code,
      title: q.title,
      status: q.status,
      student_count: q.student_count,
      time_limit_minutes: q.time_limit_minutes,
      question_count: JSON.parse(q.questions_json || '[]').length,
      created_at: q.created_at,
    })),
  });
});

quizRoutes.get('/join', (c) => {
  const html = renderPageLayout(
    { title: 'লাইভ কুইজে যোগ দিন', user: c.get('user'), activeNav: 'quiz' },
    `<section class="auth-section"><div class="container auth-card">
      <h1>লাইভ কুইজে যোগ দিন</h1>
      <p class="muted">শিক্ষকের দেওয়া ৪-সংখ্যার কুইজ কোড এবং আপনার নাম লিখুন।</p>
      <form onsubmit="joinQuiz(event)" class="stack-form">
        <label>কুইজ কোড <input type="text" id="qCode" required maxlength="6" placeholder="যেমন: 4821"></label>
        <label>আপনার নাম <input type="text" id="qName" required maxlength="100" placeholder="আপনার পূর্ণ নাম"></label>
        <button type="submit" class="btn btn-primary btn-block">যোগ দিন</button>
      </form>
      <p id="joinErr" class="alert error mt-2" style="display:none;"></p>
    </div></section>
    <script>
    async function joinQuiz(e){
      e.preventDefault();
      const code = document.getElementById('qCode').value.trim();
      const name = document.getElementById('qName').value.trim();
      const resp = await fetch('/quiz/' + encodeURIComponent(code) + '/join', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name })
      });
      const data = await resp.json();
      if (!resp.ok) { const err = document.getElementById('joinErr'); err.textContent = data.error; err.style.display='block'; return; }
      location.href = data.redirect || ('/quiz/' + encodeURIComponent(code) + '/waiting');
    }
    </script>`
  );
  return c.html(html);
});

quizRoutes.get('/join/:code', (c) => {
  const code = c.req.param('code');
  const html = renderPageLayout(
    { title: 'কুইজে যোগ দিন', user: c.get('user'), activeNav: 'quiz' },
    `<section class="auth-section"><div class="container auth-card">
      <h1>কুইজ কোড: ${escapeHtml(code)}</h1>
      <form onsubmit="joinQuiz(event)" class="stack-form">
        <label>আপনার নাম <input type="text" id="qName" required maxlength="100" placeholder="আপনার পূর্ণ নাম"></label>
        <button type="submit" class="btn btn-primary btn-block">যোগ দিন</button>
      </form>
      <p id="joinErr" class="alert error mt-2" style="display:none;"></p>
    </div></section>
    <script>
    async function joinQuiz(e){
      e.preventDefault();
      const name = document.getElementById('qName').value.trim();
      const resp = await fetch('/quiz/${escapeHtml(code)}/join', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name })
      });
      const data = await resp.json();
      if (!resp.ok) { const err = document.getElementById('joinErr'); err.textContent = data.error; err.style.display='block'; return; }
      location.href = data.redirect || '/quiz/${escapeHtml(code)}/waiting';
    }
    </script>`
  );
  return c.html(html);
});

quizRoutes.post('/:code/join', rateLimit(30, 60, 'quiz_join'), async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Invalid quiz code. Please check and try again.' }, 404);
  if (quiz.status === 'ended') return c.json({ error: 'This quiz has already ended.' }, 400);

  const body = (await c.req.json().catch(() => ({}))) as { name?: string };
  const name = (body.name || '').trim().slice(0, 100);
  if (!name) return c.json({ error: 'Please enter your name.' }, 400);

  let qs = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE quiz_id = ? AND student_name = ?')
    .bind(quiz.id, name)
    .first<QuizSessionRow>();
  let resumed = true;

  if (!qs) {
    resumed = false;
    const token = randomToken(32);
    await c.env.DB.prepare('INSERT INTO quiz_sessions (quiz_id, student_name, session_token) VALUES (?, ?, ?)')
      .bind(quiz.id, name, token)
      .run();
    qs = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE session_token = ?')
      .bind(token)
      .first<QuizSessionRow>();
  }

  setCookie(c, `quiz_token_${code}`, qs!.session_token, {
    httpOnly: true,
    sameSite: 'Lax',
    path: '/',
    maxAge: 60 * 60 * 6,
  });

  return c.json({
    success: true,
    resumed,
    status: quiz.status,
    redirect: quiz.status === 'active' ? `/quiz/${code}/play` : `/quiz/${code}/waiting`,
  });
});

quizRoutes.get('/:code/lobby', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();

  const user = c.get('user');
  if (!user || user.id !== quiz.teacher_user_id) {
    return c.redirect(`/quiz/join/${code}`);
  }

  const studentsRes = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE quiz_id = ? ORDER BY joined_at ASC')
    .bind(quiz.id)
    .all<QuizSessionRow>();

  const html = renderPageLayout(
    {
      title: `লবি - ${quiz.title}`,
      user,
      extraScripts: `<script>
setInterval(async () => {
  const r = await fetch('/quiz/${escapeHtml(code)}/status');
  const d = await r.json();
  document.getElementById('studentCount').textContent = d.student_count;
  document.getElementById('studentList').innerHTML = d.students.map(s => '<li>' + s.student_name + ' (' + s.status + ')</li>').join('');
}, 3000);
async function startQuiz(){ await fetch('/quiz/${escapeHtml(code)}/start', {method:'POST'}); location.reload(); }
async function endQuiz(){ await fetch('/quiz/${escapeHtml(code)}/end', {method:'POST'}); location.href='/quiz/${escapeHtml(code)}/results'; }
</script>`,
    },
    `<section class="page-section"><div class="container">
      <div class="card">
        <h1>${escapeHtml(quiz.title)}</h1>
        <p>জয়েন কোড: <strong style="font-size:1.8rem;letter-spacing:3px;">${escapeHtml(quiz.join_code)}</strong> | স্ট্যাটাস: <strong>${escapeHtml(quiz.status)}</strong></p>
        <p>শিক্ষার্থী যোগ দিয়েছে: <strong id="studentCount">${studentsRes.results?.length || 0}</strong></p>
        <div class="row-actions mt-2">
          ${quiz.status === 'waiting' ? '<button type="button" class="btn btn-primary" onclick="startQuiz()">কুইজ শুরু করুন</button>' : ''}
          ${quiz.status === 'active' ? '<button type="button" class="btn btn-danger" onclick="endQuiz()">কুইজ শেষ করুন</button>' : ''}
          <a href="/quiz/${escapeHtml(code)}/results" class="btn btn-outline">ফলাফল ও লিডারবোর্ড</a>
        </div>
        <ul id="studentList" class="clean-list mt-3">
          ${(studentsRes.results || []).map((s) => `<li>${escapeHtml(s.student_name)} (${escapeHtml(s.status)})</li>`).join('')}
        </ul>
      </div>
    </div></section>`
  );
  return c.html(html);
});

quizRoutes.post('/:code/start', requireTeacher, async (c) => {
  const code = c.req.param('code');
  const user = c.get('user')!;
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Quiz not found' }, 404);
  if (quiz.teacher_user_id !== user.id) return c.json({ error: 'Not authorized.' }, 403);
  if (quiz.status !== 'waiting') return c.json({ error: `Quiz already ${quiz.status}.` }, 400);

  await c.env.DB.prepare(
    `UPDATE quizzes SET status = 'active', started_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?`
  )
    .bind(quiz.id)
    .run();
  return c.json({ success: true, status: 'active' });
});

quizRoutes.post('/:code/end', requireTeacher, async (c) => {
  const code = c.req.param('code');
  const user = c.get('user')!;
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Quiz not found' }, 404);
  if (quiz.teacher_user_id !== user.id) return c.json({ error: 'Not authorized.' }, 403);

  await c.env.DB.prepare(
    `UPDATE quizzes SET status = 'ended', ended_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?`
  )
    .bind(quiz.id)
    .run();
  return c.json({ success: true, status: 'ended' });
});

quizRoutes.get('/:code/status', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Not found' }, 404);
  const studentsRes = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE quiz_id = ? ORDER BY joined_at ASC')
    .bind(quiz.id)
    .all<QuizSessionRow>();
  const students = studentsRes.results || [];
  return c.json({
    status: quiz.status,
    student_count: students.length,
    students: students.map((s) => ({
      id: s.id,
      student_name: s.student_name,
      score: s.score,
      total_questions: s.total_questions,
      status: s.status,
    })),
  });
});

quizRoutes.get('/:code/waiting', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();
  const token = getCookie(c, `quiz_token_${code}`);
  if (!token) return c.redirect(`/quiz/join/${code}`);
  if (quiz.status === 'active') return c.redirect(`/quiz/${code}/play`);

  return c.html(
    renderPageLayout(
      {
        title: 'অপেক্ষা কক্ষ',
        extraScripts: `<script>setInterval(async()=>{const r=await fetch('/quiz/${escapeHtml(code)}/status');const d=await r.json();if(d.status==='active')location.href='/quiz/${escapeHtml(code)}/play';},2500);</script>`,
      },
      `<section class="auth-section"><div class="container auth-card">
        <h1>${escapeHtml(quiz.title)}</h1>
        <p>শিক্ষক কুইজ শুরু করা পর্যন্ত অপেক্ষা করুন...</p>
      </div></section>`
    )
  );
});

quizRoutes.get('/:code/play', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();

  const token = getCookie(c, `quiz_token_${code}`);
  if (!token) return c.redirect(`/quiz/join/${code}`);

  const qs = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE session_token = ? AND quiz_id = ?')
    .bind(token, quiz.id)
    .first<QuizSessionRow>();
  if (!qs) return c.redirect(`/quiz/join/${code}`);
  if (qs.status === 'submitted' || quiz.status === 'ended') return c.redirect(`/quiz/${code}/score`);
  if (quiz.status === 'waiting') return c.redirect(`/quiz/${code}/waiting`);

  const allQuestions = JSON.parse(quiz.questions_json) as McqQuestionPayload[];
  const shuffled = quiz.shuffle_questions
    ? deterministicShuffle(allQuestions, `${token}q`)
    : { items: allQuestions, order: allQuestions.map((_, i) => i) };

  const safeQuestions = shuffled.items.map((q) => {
    const opts = [...(q.answer_options || [])];
    if (quiz.shuffle_options) {
      const optShuf = deterministicShuffle(opts, `${token}${q.question_text}`);
      opts.splice(0, opts.length, ...optShuf.items);
    }
    return {
      question_text: q.question_text,
      type: q.type || 'simple',
      sub_options: q.sub_options || [],
      final_prompt: q.final_prompt || '',
      answer_options: opts,
    };
  });

  await c.env.DB.prepare("UPDATE quiz_sessions SET status = 'in_progress' WHERE id = ?").bind(qs.id).run();

  const qHtml = safeQuestions
    .map((q, idx) => {
      const opts = q.answer_options
        .map(
          (opt, oi) =>
            `<label class="practice-opt"><input type="radio" name="q_${idx}" value="${escapeHtml(opt)}"> (${['ক', 'খ', 'গ', 'ঘ'][oi] || ''}) ${escapeHtml(opt)}</label>`
        )
        .join('');
      return `<div class="card mt-2">
        <p><strong>${toBengaliNumeral(idx + 1)}. ${escapeHtml(q.question_text)}</strong></p>
        <div class="practice-opts">${opts}</div>
      </div>`;
    })
    .join('');

  return c.html(
    renderPageLayout(
      {
        title: quiz.title,
        extraScripts: `<script>
const startTs = Date.now();
async function submitQuiz(e){
  e.preventDefault();
  const fd = new FormData(e.target);
  const responses = {};
  for (const [k, v] of fd.entries()) responses[k.replace('q_','')] = v;
  const elapsed = Math.floor((Date.now() - startTs) / 1000);
  const resp = await fetch('/quiz/${escapeHtml(code)}/submit', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ responses, time_taken_seconds: elapsed })
  });
  const data = await resp.json();
  if (data.redirect) location.href = data.redirect;
  else alert(data.error || 'Failed');
}
</script>`,
      },
      `<section class="page-section"><div class="container">
        <h1>${escapeHtml(quiz.title)}</h1>
        <p>শিক্ষার্থী: <strong>${escapeHtml(qs.student_name)}</strong> | সময়সীমা: ${toBengaliNumeral(quiz.time_limit_minutes)} মিনিট</p>
        <form onsubmit="submitQuiz(event)">
          ${qHtml}
          <button type="submit" class="btn btn-primary btn-lg mt-3">জমা দিন</button>
        </form>
      </div></section>`
    )
  );
});

quizRoutes.post('/:code/submit', rateLimit(15, 60, 'quiz_submit'), async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Quiz not found' }, 404);

  const token = getCookie(c, `quiz_token_${code}`);
  if (!token) return c.json({ error: 'Session expired. Please rejoin.' }, 401);

  const qs = await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE session_token = ? AND quiz_id = ?')
    .bind(token, quiz.id)
    .first<QuizSessionRow>();
  if (!qs) return c.json({ error: 'Session not found.' }, 404);
  if (qs.status === 'submitted') {
    return c.json({ error: 'Already submitted.', redirect: `/quiz/${code}/score` }, 400);
  }

  const body = (await c.req.json().catch(() => null)) as {
    responses?: Record<string, string>;
    time_taken_seconds?: number;
  } | null;
  if (!body) return c.json({ error: 'No data provided.' }, 400);

  const allQuestions = JSON.parse(quiz.questions_json) as McqQuestionPayload[];
  const shuffleOrder = quiz.shuffle_questions
    ? deterministicShuffle(allQuestions, `${token}q`).order
    : allQuestions.map((_, i) => i);

  const responses = body.responses || {};
  const originalResponses: Record<string, string> = {};
  for (const [shufIdxStr, ans] of Object.entries(responses)) {
    const shufIdx = Number(shufIdxStr);
    if (Number.isInteger(shufIdx) && shufIdx >= 0 && shufIdx < shuffleOrder.length) {
      originalResponses[String(shuffleOrder[shufIdx])] = ans;
    }
  }

  let correct = 0;
  allQuestions.forEach((q, idx) => {
    if (originalResponses[String(idx)] && originalResponses[String(idx)] === q.correct_answer) {
      correct++;
    }
  });

  const total = allQuestions.length;
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  const timeTaken = Math.min(Number(body.time_taken_seconds) || 0, quiz.time_limit_minutes * 60 + 60);

  await c.env.DB.prepare(
    `UPDATE quiz_sessions
     SET score = ?, total_questions = ?, responses_json = ?, time_taken_seconds = ?,
         status = 'submitted', submitted_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
     WHERE id = ?`
  )
    .bind(correct, total, JSON.stringify(originalResponses), timeTaken, qs.id)
    .run();

  return c.json({
    success: true,
    score: correct,
    total,
    percentage: pct,
    redirect: `/quiz/${code}/score`,
  });
});

quizRoutes.get('/:code/score', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();

  const token = getCookie(c, `quiz_token_${code}`);
  const student = token
    ? await c.env.DB.prepare('SELECT * FROM quiz_sessions WHERE session_token = ? AND quiz_id = ?')
        .bind(token, quiz.id)
        .first<QuizSessionRow>()
    : null;

  const lbRes = await c.env.DB.prepare(
    "SELECT * FROM quiz_sessions WHERE quiz_id = ? AND status = 'submitted' ORDER BY score DESC, time_taken_seconds ASC"
  )
    .bind(quiz.id)
    .all<QuizSessionRow>();
  const board = lbRes.results || [];
  const rank = student ? board.findIndex((b) => b.id === student.id) + 1 : null;

  return c.html(
    renderPageLayout(
      { title: `ফলাফল - ${quiz.title}` },
      `<section class="page-section"><div class="container">
        <div class="card">
          <h1>${escapeHtml(quiz.title)}</h1>
          ${student ? `<h2>আপনার স্কোর: ${student.score} / ${student.total_questions} ${rank ? `(র‍্যাংক #${rank})` : ''}</h2>` : ''}
          <h3 class="mt-3">লিডারবোর্ড</h3>
          <table class="data-table">
            <thead><tr><th>র‍্যাংক</th><th>নাম</th><th>স্কোর</th><th>সময়</th></tr></thead>
            <tbody>
              ${board.map((s, i) => `<tr><td>#${i + 1}</td><td>${escapeHtml(s.student_name)}</td><td>${s.score}/${s.total_questions}</td><td>${s.time_taken_seconds || 0}s</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div></section>`
    )
  );
});

quizRoutes.get('/:code/leaderboard', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.json({ error: 'Not found' }, 404);
  const lbRes = await c.env.DB.prepare(
    "SELECT * FROM quiz_sessions WHERE quiz_id = ? AND status = 'submitted' ORDER BY score DESC, time_taken_seconds ASC"
  )
    .bind(quiz.id)
    .all<QuizSessionRow>();

  return c.json({
    quiz_status: quiz.status,
    leaderboard: (lbRes.results || []).map((s, idx) => ({
      rank: idx + 1,
      name: s.student_name,
      score: s.score,
      total: s.total_questions,
      percentage: s.total_questions ? Math.round((s.score / s.total_questions) * 100) : 0,
      time_taken: s.time_taken_seconds,
    })),
  });
});

quizRoutes.get('/:code/results', async (c) => {
  const code = c.req.param('code');
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();
  const user = c.get('user');
  const isTeacher = Boolean(user && user.id === quiz.teacher_user_id);
  if (quiz.status !== 'ended' && !isTeacher) {
    return c.redirect(`/quiz/join/${code}`);
  }

  const lbRes = await c.env.DB.prepare(
    "SELECT * FROM quiz_sessions WHERE quiz_id = ? AND status = 'submitted' ORDER BY score DESC, time_taken_seconds ASC"
  )
    .bind(quiz.id)
    .all<QuizSessionRow>();
  const submitted = lbRes.results || [];

  return c.html(
    renderPageLayout(
      { title: `কুইজ বিশ্লেষণ - ${quiz.title}`, user },
      `<section class="page-section"><div class="container">
        <div class="page-hero">
          <div><h1>${escapeHtml(quiz.title)} — ফলাফল</h1></div>
          ${isTeacher ? `<a href="/quiz/${escapeHtml(code)}/export" class="btn btn-primary">CSV ডাউনলোড</a>` : ''}
        </div>
        <div class="card">
          <table class="data-table">
            <thead><tr><th>র‍্যাংক</th><th>শিক্ষার্থী</th><th>স্কোর</th><th>সময় (সেকেন্ড)</th></tr></thead>
            <tbody>
              ${submitted.map((s, i) => `<tr><td>${i + 1}</td><td>${escapeHtml(s.student_name)}</td><td>${s.score}/${s.total_questions}</td><td>${s.time_taken_seconds || 0}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div></section>`
    )
  );
});

quizRoutes.get('/:code/export', requireTeacher, async (c) => {
  const code = c.req.param('code');
  const user = c.get('user')!;
  const quiz = await c.env.DB.prepare('SELECT * FROM quizzes WHERE join_code = ?').bind(code).first<QuizRow>();
  if (!quiz) return c.notFound();
  if (quiz.teacher_user_id !== user.id) return c.json({ error: 'Forbidden' }, 403);

  const lbRes = await c.env.DB.prepare(
    "SELECT * FROM quiz_sessions WHERE quiz_id = ? AND status = 'submitted' ORDER BY score DESC"
  )
    .bind(quiz.id)
    .all<QuizSessionRow>();

  const rows = ['Rank,Student Name,Score,Total Questions,Percentage,Time Taken (sec),Submitted At'];
  (lbRes.results || []).forEach((s, i) => {
    const pct = s.total_questions ? Math.round((s.score / s.total_questions) * 100) : 0;
    const safeName = `"${(s.student_name || '').replace(/"/g, '""')}"`;
    rows.push(`${i + 1},${safeName},${s.score},${s.total_questions},${pct}%,${s.time_taken_seconds ?? ''},${s.submitted_at ?? ''}`);
  });

  return c.body(rows.join('\n'), 200, {
    'Content-Type': 'text/csv; charset=utf-8',
    'Content-Disposition': `attachment; filename="quiz_${code}_results.csv"`,
  });
});
