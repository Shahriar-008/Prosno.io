import { Hono } from 'hono';
import type {
  AppContextEnv,
  CqQuestionPayload,
  CqSectionConfig,
  McqQuestionPayload,
  PaperConfig,
  SqQuestionPayload,
  SqSectionConfig,
  StudioConfig,
} from '../types';
import { requireTeacher } from '../lib/auth';
import { rateLimit } from '../lib/rate-limit';
import { randomUrlSafeToken, randomToken } from '../lib/crypto';
import { getUserCredits } from './api';
import { normalizeStudioConfig, renderPaperStudioHtml } from '../services/paper-renderer';
import { renderHtmlToPdfBuffer } from '../services/browser-pdf';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';
import { toBengaliNumeral } from '../lib/bengali';

export const paperRoutes = new Hono<AppContextEnv>();

const MAX_QUESTIONS_PER_PAPER = 50;
const MAX_CHAPTERS_PER_REQUEST = 5;

interface DbQuestionRow {
  id: number;
  question_text: string;
  question_type: string;
  sub_options: string | null;
  final_prompt: string | null;
  answer_options: string;
  correct_answer: string;
  explanation: string | null;
  board: string | null;
  year: number | null;
  chapter_id: number;
  difficulty: string;
}

interface GeneratedPaperRow {
  id: number;
  user_id: string | null;
  title: string | null;
  class_id: number | null;
  subject_id: number | null;
  chapter_ids: string | null;
  question_ids: string | null;
  question_count: number | null;
  time_minutes: number | null;
  custom_questions_json: string | null;
  custom_paper_config: string | null;
  omr_style: number;
  created_at: string;
  download_count: number;
}

function dbQuestionToPayload(row: DbQuestionRow): McqQuestionPayload {
  return {
    id: row.id,
    question_text: row.question_text,
    type: row.question_type === 'complex' ? 'complex' : 'simple',
    sub_options: row.sub_options ? JSON.parse(row.sub_options) : [],
    final_prompt: row.final_prompt || '',
    answer_options: row.answer_options ? JSON.parse(row.answer_options) : [],
    correct_answer: row.correct_answer,
    explanation: row.explanation,
    board: row.board,
    year: row.year,
    chapter_id: row.chapter_id,
    difficulty: row.difficulty,
  };
}

function shuffleInPlace<T>(arr: T[]): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

async function getTeacherBrandingStudio(db: D1Database, userId?: string): Promise<Partial<StudioConfig>> {
  if (!userId) return {};
  const prof = await db
    .prepare(
      'SELECT institute_name, institute_subtitle, logo_url, watermark_text, default_font FROM teacher_profiles WHERE user_id = ?'
    )
    .bind(userId)
    .first<{
      institute_name: string | null;
      institute_subtitle: string | null;
      logo_url: string | null;
      watermark_text: string | null;
      default_font: string | null;
    }>();
  if (!prof) return {};
  return {
    instituteName: prof.institute_name || '',
    instituteSubtitle: prof.institute_subtitle || '',
    logoUrl: prof.logo_url || '',
    watermarkText: prof.watermark_text || '',
    font: (prof.default_font as StudioConfig['font']) || 'hind',
  };
}

async function loadPaperRenderContext(db: D1Database, paper: GeneratedPaperRow) {
  let questions: McqQuestionPayload[] = [];
  const storedCfg: PaperConfig = paper.custom_paper_config
    ? (JSON.parse(paper.custom_paper_config) as PaperConfig)
    : { title: paper.title || 'Question Paper' };

  if (paper.custom_questions_json) {
    questions = JSON.parse(paper.custom_questions_json) as McqQuestionPayload[];
  } else {
    const qIds: number[] = paper.question_ids ? JSON.parse(paper.question_ids) : [];
    if (qIds.length > 0) {
      const placeholders = qIds.map(() => '?').join(',');
      const res = await db
        .prepare(`SELECT * FROM questions WHERE id IN (${placeholders})`)
        .bind(...qIds)
        .all<DbQuestionRow>();
      const byId = new Map<number, DbQuestionRow>();
      for (const r of res.results || []) byId.set(r.id, r);
      questions = qIds
        .map((id) => byId.get(id))
        .filter((r): r is DbQuestionRow => Boolean(r))
        .map(dbQuestionToPayload);
    } else if (paper.chapter_ids) {
      const chIds: number[] = JSON.parse(paper.chapter_ids);
      if (chIds.length > 0) {
        const placeholders = chIds.map(() => '?').join(',');
        const res = await db
          .prepare(
            `SELECT * FROM questions WHERE chapter_id IN (${placeholders}) AND is_active = 1 LIMIT ?`
          )
          .bind(...chIds, paper.question_count || 30)
          .all<DbQuestionRow>();
        questions = (res.results || []).map(dbQuestionToPayload);
      }
    }
  }

  let className = storedCfg.class_name || '';
  let subjectName = storedCfg.subject_name || '';
  if (!className && paper.class_id) {
    const cRow = await db
      .prepare('SELECT name, name_bn FROM classes WHERE id = ?')
      .bind(paper.class_id)
      .first<{ name: string; name_bn: string | null }>();
    if (cRow) className = cRow.name_bn || cRow.name;
  }
  if (!subjectName && paper.subject_id) {
    const sRow = await db
      .prepare('SELECT name, name_bn FROM subjects WHERE id = ?')
      .bind(paper.subject_id)
      .first<{ name: string; name_bn: string | null }>();
    if (sRow) subjectName = sRow.name_bn || sRow.name;
  }

  const paperConfig: PaperConfig = {
    title: storedCfg.title || paper.title || 'Question Paper',
    class_name: className,
    subject_name: subjectName,
    time: paper.time_minutes || storedCfg.time || questions.length,
    marks: storedCfg.marks || questions.length,
    omr_style: paper.omr_style === 1,
    sq_config: storedCfg.sq_config || null,
    cq_config: storedCfg.cq_config || null,
    studio: storedCfg.studio,
  };

  return { questions, paperConfig };
}

// ── Public Pages ──────────────────────────────────────────────────────────

paperRoutes.get('/healthz', (c) => c.json({ status: 'ok', runtime: 'cloudflare-workers' }));

paperRoutes.get('/', async (c) => {
  const user = c.get('user');
  const [classesRes, statsQ, statsP] = await Promise.all([
    c.env.DB.prepare('SELECT id, name, name_bn FROM classes WHERE is_active = 1 ORDER BY "order", id').all<{
      id: number;
      name: string;
      name_bn: string | null;
    }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM questions WHERE is_active = 1').first<{ cnt: number }>(),
    c.env.DB.prepare('SELECT COUNT(*) as cnt FROM generated_papers').first<{ cnt: number }>(),
  ]);

  const html = renderPageLayout(
    {
      title: '১-ক্লিকে প্রিন্ট-রেডি প্রশ্নপত্র, উত্তরমালা ও OMR',
      user,
    },
    `<section class="hero-banner">
      <div class="container hero-grid">
        <div>
          <span class="badge-pill">Cloudflare Edge + Live Print Studio</span>
          <h1>বাংলাদেশের শিক্ষকদের জন্য ১-ক্লিকে প্রিন্ট-রেডি প্রশ্নপত্র ও সমাধান স্টুডিও</h1>
          <p class="hero-lead">NCTB সিলেবাস অনুযায়ী MCQ (বোর্ড প্রশ্ন ও জটিল বহুপদী), সংক্ষিপ্ত প্রশ্ন (খ-বিভাগ), সৃজনশীল (গ-বিভাগ), KaTeX গণিত ফর্মুলা, উত্তরমালা, প্রিন্ট-রেডি OMR শিট ও লাইভ কুইজ — সব এক প্ল্যাটফর্মে।</p>
          <div class="hero-actions">
            <a href="/generate" class="btn btn-primary btn-lg">দ্রুত প্রশ্ন তৈরি করুন</a>
            <a href="/builder" class="btn btn-outline btn-lg">স্মার্ট পেপার বিল্ডার</a>
            <a href="/omr-builder" class="btn btn-ghost btn-lg">OMR ডিজাইনার</a>
          </div>
          <div class="hero-stats">
            <div><strong>${toBengaliNumeral(classesRes.results?.length || 10)}+</strong><span>শ্রেণি (১ম-১০ম)</span></div>
            <div><strong>${toBengaliNumeral(statsQ?.cnt || 0)}+</strong><span>প্রশ্ন ব্যাংক</span></div>
            <div><strong>${toBengaliNumeral(statsP?.cnt || 0)}+</strong><span>তৈরিকৃত প্রশ্নপত্র</span></div>
          </div>
        </div>
        <div class="hero-preview-card">
          <div class="mini-paper">
            <div class="mini-paper-head">
              <strong>বিষয়: বিজ্ঞান | অধ্যায় ৫</strong>
              <span>সময়: ২৫ মিনিট | পূর্ণমান: ৫০</span>
            </div>
            <div class="mini-paper-cols">
              <div>
                <p><strong>১.</strong> চোখের কোন অংশ ক্যামেরার ডায়াফ্রামের মতো কাজ করে? [ঢা. বো. ২০]</p>
                <div class="mini-opts"><span>◯ (ক) রেটিনা</span><span>◯ (খ) আইরিশ</span><span>◯ (গ) কর্নিয়া</span><span>◯ (ঘ) অক্ষিগোলক</span></div>
              </div>
              <div>
                <p><strong>২.</strong> যদি x + 1/x = 3 হয়, তবে x² + 1/x² = কত?</p>
                <div class="mini-opts"><span>◯ (ক) 7</span><span>◯ (খ) 9</span><span>◯ (গ) 11</span><span>◯ (ঘ) 5</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="features-section">
      <div class="container">
        <h2 class="section-title">কেন Prosno.io বাংলাদেশের সেরা প্রশ্ন তৈরির প্ল্যাটফর্ম?</h2>
        <div class="feature-grid">
          <div class="feature-card">
            <h3>লাইভ HTML প্রিন্ট ও PDF স্টুডিও</h3>
            <p>কোনো ঝামেলা ছাড়াই Hind Siliguri, Noto Sans Bengali ও KaTeX গণিত সমীকরণসহ ১/২/৩ কলাম প্রিন্ট-রেডি PDF ও DOCX ডাউনলোড।</p>
          </div>
          <div class="feature-card">
            <h3>উত্তরমালা + ব্যাখ্যাসহ সমাধান ট্যাব</h3>
            <p>এক ক্লিকেই ১০-কলাম কুইক উত্তর সংকেত গ্রিড, প্রতিটি প্রশ্নের সংক্ষিপ্ত ব্যাখ্যা এবং OMR ভরাট শিক্ষক কপি।</p>
          </div>
          <div class="feature-card">
            <h3>কোচিং ব্র্যান্ডিং ও ওয়াটারমার্ক</h3>
            <p>প্রতিষ্ঠানের নাম, লোগো, কাস্টম হেডার প্রিসেট ও জলছাপ (Watermark) সেভ করে রাখুন।</p>
          </div>
          <div class="feature-card">
            <h3>স্ক্যান-রেডি OMR + লাইভ কুইজ</h3>
            <p>৪০/৬০/৮০/১০০ প্রশ্নের বোর্ড-স্টাইল OMR শিট এবং ৪-ডিজিট কোডে রিয়েল-টাইম অনলাইন কুইজ ও CSV রেজাল্ট।</p>
          </div>
        </div>
      </div>
    </section>`
  );
  return c.html(html);
});

paperRoutes.get('/generate', async (c) => {
  const user = c.get('user');
  const classesRes = await c.env.DB.prepare(
    'SELECT id, name, name_bn FROM classes WHERE is_active = 1 ORDER BY "order", id'
  ).all<{ id: number; name: string; name_bn: string | null }>();

  const classOptions = (classesRes.results || [])
    .map((cl) => `<option value="${cl.id}">${escapeHtml(cl.name_bn || cl.name)}</option>`)
    .join('');

  const html = renderPageLayout(
    {
      title: 'দ্রুত প্রশ্নপত্র তৈরি',
      user,
      activeNav: 'generate',
      extraScripts: '<script src="/js/generate.js"></script>',
    },
    `<section class="page-section"><div class="container">
      <div class="page-hero">
        <div>
          <span class="badge-pill">Quick Paper Generator</span>
          <h1>দ্রুত প্রশ্নপত্র ও উত্তরমালা তৈরি করুন</h1>
          <p>ডাটাবেস থেকে অধ্যায় বেছে অথবা নিজের প্রশ্ন দিয়ে মুহূর্তেই প্রিন্ট স্টুডিওতে ওপেন করুন।</p>
        </div>
        <div class="mode-switch">
          <button type="button" class="btn btn-primary" id="modeDbBtn">ডাটাবেস মোড</button>
          <button type="button" class="btn btn-outline" id="modeCustomBtn">কাস্টম (Guest) মোড</button>
        </div>
      </div>

      <div id="dbModePanel" class="card form-grid">
        <div class="grid-3">
          <label>শ্রেণি
            <select id="genClass"><option value="">-- শ্রেণি বাছাই করুন --</option>${classOptions}</select>
          </label>
          <label>বিষয়
            <select id="genSubject" disabled><option value="">-- আগে শ্রেণি বাছাই করুন --</option></select>
          </label>
          <label>শিরোনাম
            <input type="text" id="genTitle" value="মডেল টেস্ট">
          </label>
        </div>

        <div class="mt-2">
          <label>অধ্যায়সমূহ (সর্বোচ্চ ৫টি) <span id="genAvailCount" class="badge-pill">০টি প্রশ্ন</span></label>
          <div id="genChaptersBox" class="chip-grid muted">শ্রেণি ও বিষয় বাছাই করুন</div>
        </div>

        <div class="grid-3 mt-2">
          <label>প্রশ্ন সংখ্যা (সর্বোচ্চ ৫০)
            <input type="number" id="genCount" value="25" min="1" max="50">
          </label>
          <label>সময় (মিনিট)
            <input type="number" id="genTime" value="25" min="1" max="300">
          </label>
          <div class="check-col">
            <label><input type="checkbox" id="genRandomize" checked> প্রশ্ন এলোমেলো (Shuffle)</label>
            <label><input type="checkbox" id="genOmr" checked> OMR বৃত্ত দেখান</label>
          </div>
        </div>

        <div class="row-actions mt-3">
          <button type="button" class="btn btn-outline" id="btnPreviewQuestions">নির্দিষ্ট প্রশ্ন বাছাই করুন</button>
          <button type="button" class="btn btn-primary btn-lg" id="btnGenerateDb">প্রশ্নপত্র ও প্রিন্ট স্টুডিও তৈরি করুন</button>
        </div>

        <div id="questionPickerBox" class="picker-box mt-3" style="display:none;"></div>
      </div>

      <div id="customModePanel" class="card" style="display:none;">
        <h3>কাস্টম প্রশ্ন যোগ করুন (লগইন ছাড়াই ব্যবহারযোগ্য)</h3>
        <div class="grid-3">
          <label>শিরোনাম <input type="text" id="custTitle" value="কাস্টম পরীক্ষা"></label>
          <label>সময় (মিনিট) <input type="number" id="custTime" value="30"></label>
          <label><input type="checkbox" id="custOmr" checked> OMR বৃত্ত</label>
        </div>
        <div id="customQuestionsList" class="mt-2"></div>
        <div class="row-actions mt-2">
          <button type="button" class="btn btn-outline" id="btnAddCustomQ">+ নতুন MCQ যোগ করুন</button>
          <button type="button" class="btn btn-primary" id="btnGenerateCustom">প্রিন্ট স্টুডিওতে দেখুন</button>
        </div>
      </div>

      <div id="genResultCard" class="card success-card mt-3" style="display:none;"></div>
    </div></section>`
  );
  return c.html(html);
});

paperRoutes.get('/builder', async (c) => {
  const user = c.get('user');
  const classesRes = await c.env.DB.prepare(
    'SELECT id, name, name_bn FROM classes WHERE is_active = 1 ORDER BY "order", id'
  ).all<{ id: number; name: string; name_bn: string | null }>();
  const classOptions = (classesRes.results || [])
    .map((cl) => `<option value="${cl.id}">${escapeHtml(cl.name_bn || cl.name)}</option>`)
    .join('');

  const html = renderPageLayout(
    {
      title: 'স্মার্ট পেপার বিল্ডার',
      user,
      activeNav: 'builder',
      extraScripts: '<script src="/js/builder.js"></script>',
    },
    `<section class="page-section"><div class="container">
      <div class="page-hero">
        <div>
          <span class="badge-pill">Multi-Section Builder</span>
          <h1>স্মার্ট পেপার বিল্ডার (MCQ + সংক্ষিপ্ত + সৃজনশীল)</h1>
          <p>ডাটাবেস, কমিউনিটি ব্যাংক এবং কাস্টম প্রশ্ন মিলিয়ে পূর্ণাঙ্গ বোর্ড-স্ট্যান্ডার্ড প্রশ্নপত্র তৈরি করুন।</p>
        </div>
        <div class="hero-actions">
          <button type="button" class="btn btn-primary" id="builderGenerateBtn">প্রিন্ট স্টুডিওতে তৈরি করুন</button>
        </div>
      </div>

      <div class="builder-grid">
        <div>
          <div class="card">
            <h3>প্রশ্নপত্র কনফিগারেশন</h3>
            <div class="grid-3">
              <label>শিরোনাম <input type="text" id="bldTitle" value="বার্ষিক পরীক্ষা ২০২৬"></label>
              <label>সময় (মিনিট) <input type="number" id="bldTime" value="60" min="5" max="300"></label>
              <label>শ্রেণি <select id="bldClass"><option value="">-- শ্রেণি --</option>${classOptions}</select></label>
              <label>বিষয় <select id="bldSubject" disabled><option value="">-- বিষয় --</option></select></label>
              <label><input type="checkbox" id="bldOmr" checked> OMR বৃত্ত</label>
            </div>
          </div>

          <div class="card mt-3">
            <div class="row-between">
              <h3>নির্বাচিত প্রশ্নসমূহ (<span id="bldTotalMarks">০</span> নম্বর)</h3>
              <button type="button" class="btn btn-sm btn-outline" id="bldAddCustomMcq">+ কাস্টম MCQ</button>
            </div>
            <div id="bldSelectedSections" class="mt-2"></div>
          </div>

          <div id="builderResultCard" class="card success-card mt-3" style="display:none;"></div>
        </div>

        <aside class="card">
          <h3>প্রশ্ন ব্যাংক প্যানেল</h3>
          <div class="stack-form">
            <input type="text" id="bldSearch" placeholder="প্রশ্ন খুঁজুন...">
            <div class="row-actions">
              <select id="bldType">
                <option value="mcq">MCQ</option>
                <option value="sq">সংক্ষিপ্ত (SQ)</option>
                <option value="cq">সৃজনশীল (CQ)</option>
              </select>
              <button type="button" class="btn btn-sm btn-primary" id="bldFetchBank">খুঁজুন</button>
            </div>
          </div>
          <div id="bldBankResults" class="bank-results mt-2"></div>
        </aside>
      </div>
    </div></section>`
  );
  return c.html(html);
});

paperRoutes.get('/dashboard', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const [credits, setsRes, omrRes, quizzesRes] = await Promise.all([
    getUserCredits(c.env.DB, user.id),
    c.env.DB.prepare('SELECT id, name, source, share_token, is_shared, paper_id, questions_json, created_at FROM question_sets WHERE user_id = ? ORDER BY updated_at DESC LIMIT 30')
      .bind(user.id)
      .all<{
        id: number;
        name: string;
        source: string;
        share_token: string | null;
        is_shared: number;
        paper_id: number | null;
        questions_json: string;
        created_at: string;
      }>(),
    c.env.DB.prepare('SELECT id, name, question_count, updated_at FROM omr_templates WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20')
      .bind(user.id)
      .all<{ id: number; name: string; question_count: number; updated_at: string }>(),
    c.env.DB.prepare('SELECT id, join_code, title, status, time_limit_minutes, created_at FROM quizzes WHERE teacher_user_id = ? ORDER BY created_at DESC LIMIT 20')
      .bind(user.id)
      .all<{ id: number; join_code: string; title: string; status: string; time_limit_minutes: number; created_at: string }>(),
  ]);

  const setRows = (setsRes.results || [])
    .map((s) => {
      const qCount = (() => {
        try {
          return JSON.parse(s.questions_json).length;
        } catch {
          return 0;
        }
      })();
      return `<tr>
        <td><strong>${escapeHtml(s.name)}</strong><br><small class="muted">${toBengaliNumeral(qCount)}টি প্রশ্ন • ${escapeHtml(s.source)}</small></td>
        <td>
          ${s.paper_id ? `<a class="btn btn-sm btn-primary" href="/papers/${s.paper_id}/studio">Print Studio</a>` : ''}
          <button type="button" class="btn btn-sm btn-outline" onclick="createQuizFromSet(${s.id}, '${escapeHtml(s.name)}')">লাইভ কুইজ</button>
          <button type="button" class="btn btn-sm btn-outline" onclick="toggleShareSet(${s.id})">${s.is_shared ? 'শেয়ার বন্ধ' : 'শেয়ার লিংক'}</button>
          ${s.is_shared && s.share_token ? `<a class="btn btn-sm btn-ghost" href="/paper/${escapeHtml(s.share_token)}" target="_blank">লিঙ্ক</a>` : ''}
        </td>
      </tr>`;
    })
    .join('');

  const omrRows = (omrRes.results || [])
    .map(
      (o) => `<li><strong>${escapeHtml(o.name)}</strong> (${toBengaliNumeral(o.question_count)} প্রশ্ন) — <a href="/omr-builder?template=${o.id}">খুলুন</a></li>`
    )
    .join('');

  const quizRows = (quizzesRes.results || [])
    .map(
      (q) => `<li><strong>${escapeHtml(q.title)}</strong> (কোড: <code>${escapeHtml(q.join_code)}</code> • ${escapeHtml(q.status)}) — <a href="/quiz/${escapeHtml(q.join_code)}/lobby">লবি</a> | <a href="/quiz/${escapeHtml(q.join_code)}/results">ফলাফল</a></li>`
    )
    .join('');

  const html = renderPageLayout(
    {
      title: 'ড্যাশবোর্ড',
      user,
      extraScripts: `<script>
async function createQuizFromSet(setId, title) {
  const resp = await fetch('/quiz/create', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ question_set_id: setId, title }) });
  const data = await resp.json();
  if (data.lobby_url) location.href = data.lobby_url;
  else alert(data.error || 'Failed');
}
async function toggleShareSet(setId) {
  const resp = await fetch('/question-set/' + setId + '/share', { method: 'POST' });
  if (resp.ok) location.reload();
}
</script>`,
    },
    `<section class="page-section"><div class="container">
      <div class="page-hero">
        <div>
          <h1>স্বাগতম, ${escapeHtml(user.display_name)}</h1>
          <p>দৈনিক ক্রেডিট: <strong>${toBengaliNumeral(credits.remaining)}/${toBengaliNumeral(credits.limit)}</strong> বাকি আছে</p>
        </div>
        <div class="hero-actions">
          <a href="/generate" class="btn btn-primary">+ নতুন প্রশ্নপত্র</a>
          <a href="/builder" class="btn btn-outline">স্মার্ট বিল্ডার</a>
          <a href="/bank/profile" class="btn btn-ghost">টিচার প্রোফাইল</a>
        </div>
      </div>

      <div class="card">
        <h3>সেভ করা প্রশ্ন সেটসমূহ</h3>
        ${setRows ? `<table class="data-table"><tbody>${setRows}</tbody></table>` : '<p class="muted">এখনো কোনো প্রশ্ন সেট সেভ করা হয়নি।</p>'}
      </div>

      <div class="grid-2 mt-3">
        <div class="card">
          <h3>সেভ করা OMR টেমপ্লেট</h3>
          ${omrRows ? `<ul class="clean-list">${omrRows}</ul>` : '<p class="muted">কোনো OMR টেমপ্লেট নেই। <a href="/omr-builder">তৈরি করুন</a></p>'}
        </div>
        <div class="card">
          <h3>লাইভ কুইজসমূহ</h3>
          ${quizRows ? `<ul class="clean-list">${quizRows}</ul>` : '<p class="muted">কোনো লাইভ কুইজ নেই।</p>'}
        </div>
      </div>
    </div></section>`
  );
  return c.html(html);
});

// ── Paper Preview/Generation APIs ─────────────────────────────────────────

paperRoutes.post('/get-question-count', rateLimit(60, 60, 'paper_qcount'), async (c) => {
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

paperRoutes.post('/get-questions-for-chapters', rateLimit(30, 60, 'paper_qpreview'), async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as { chapter_ids?: number[] };
  const chapterIds = (body.chapter_ids || []).map(Number).filter(Number.isFinite);
  if (chapterIds.length === 0) return c.json({ questions: [], chapters: {} });
  if (chapterIds.length > MAX_CHAPTERS_PER_REQUEST) {
    return c.json({ error: `Maximum ${MAX_CHAPTERS_PER_REQUEST} chapters can be selected at once.` }, 400);
  }

  const placeholders = chapterIds.map(() => '?').join(',');
  const [qRes, chRes] = await Promise.all([
    c.env.DB.prepare(
      `SELECT id, question_text, question_type, chapter_id, difficulty, board, year
       FROM questions WHERE chapter_id IN (${placeholders}) AND is_active = 1
       ORDER BY chapter_id, id`
    )
      .bind(...chapterIds)
      .all<{
        id: number;
        question_text: string;
        question_type: string;
        chapter_id: number;
        difficulty: string;
        board: string | null;
        year: number | null;
      }>(),
    c.env.DB.prepare(`SELECT id, name, name_bn, chapter_number FROM chapters WHERE id IN (${placeholders})`)
      .bind(...chapterIds)
      .all<{ id: number; name: string; name_bn: string | null; chapter_number: number | null }>(),
  ]);

  const chapters: Record<number, { id: number; name: string; chapter_number: number | null }> = {};
  for (const ch of chRes.results || []) {
    chapters[ch.id] = { id: ch.id, name: ch.name_bn || ch.name, chapter_number: ch.chapter_number };
  }

  // Strip options & answers server-side for anti-scraping
  const questions = (qRes.results || []).map((q) => ({
    id: q.id,
    question_text: q.question_text.length > 100 ? `${q.question_text.slice(0, 100)}...` : q.question_text,
    full_text: q.question_text,
    type: q.question_type,
    chapter_id: q.chapter_id,
    difficulty: q.difficulty,
    board: q.board,
    year: q.year,
  }));

  return c.json({ questions, chapters });
});

paperRoutes.post('/generate-paper', rateLimit(20, 60, 'gen_paper'), async (c) => {
  const user = c.get('user');
  if (user) {
    const credits = await getUserCredits(c.env.DB, user.id);
    if (credits.remaining <= 0) {
      return c.json(
        { error: 'Daily generation limit reached (0 credits left). Please wait until tomorrow.', credits_exhausted: true },
        429
      );
    }
  }

  const data = (await c.req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!data) return c.json({ error: 'Invalid JSON payload' }, 400);

  const classId = Number(data.class_id);
  const subjectId = Number(data.subject_id);
  const chapterIds = Array.isArray(data.chapter_ids) ? data.chapter_ids.map(Number).filter(Number.isFinite) : [];
  const questionIds = Array.isArray(data.question_ids) ? data.question_ids.map(Number).filter(Number.isFinite) : [];
  const requestedCount = Math.min(Number(data.question_count) || 30, MAX_QUESTIONS_PER_PAPER);
  const timeMinutes = Number(data.time_minutes) || 30;
  const title = String(data.title || 'Home Test').slice(0, 200);
  const randomize = Boolean(data.randomize);
  const omrStyle = data.omr_style !== undefined ? Boolean(data.omr_style) : true;

  if (!classId || !subjectId || chapterIds.length === 0) {
    return c.json({ error: 'Missing required fields' }, 400);
  }
  if (chapterIds.length > MAX_CHAPTERS_PER_REQUEST) {
    return c.json({ error: `Maximum ${MAX_CHAPTERS_PER_REQUEST} chapters allowed per paper.` }, 400);
  }
  if (questionIds.length > MAX_QUESTIONS_PER_PAPER) {
    return c.json({ error: `Maximum ${MAX_QUESTIONS_PER_PAPER} questions allowed per paper.` }, 400);
  }

  const [classObj, subjectObj] = await Promise.all([
    c.env.DB.prepare('SELECT id, name, name_bn FROM classes WHERE id = ?').bind(classId).first<{ id: number; name: string; name_bn: string | null }>(),
    c.env.DB.prepare('SELECT id, name, name_bn FROM subjects WHERE id = ?').bind(subjectId).first<{ id: number; name: string; name_bn: string | null }>(),
  ]);
  if (!classObj || !subjectObj) return c.json({ error: 'Invalid class or subject' }, 400);

  let selectedQuestions: DbQuestionRow[] = [];
  if (questionIds.length > 0) {
    const placeholders = questionIds.map(() => '?').join(',');
    const res = await c.env.DB.prepare(
      `SELECT * FROM questions WHERE id IN (${placeholders}) AND is_active = 1`
    )
      .bind(...questionIds)
      .all<DbQuestionRow>();
    const map = new Map<number, DbQuestionRow>();
    for (const q of res.results || []) map.set(q.id, q);
    selectedQuestions = questionIds.map((id) => map.get(id)).filter((q): q is DbQuestionRow => Boolean(q));
    if (randomize) shuffleInPlace(selectedQuestions);
  } else {
    const placeholders = chapterIds.map(() => '?').join(',');
    const res = await c.env.DB.prepare(
      `SELECT * FROM questions WHERE chapter_id IN (${placeholders}) AND is_active = 1 ORDER BY RANDOM() LIMIT ?`
    )
      .bind(...chapterIds, requestedCount)
      .all<DbQuestionRow>();
    selectedQuestions = res.results || [];
  }

  if (selectedQuestions.length === 0) {
    return c.json({ error: 'No questions found for selected criteria' }, 404);
  }

  // Optional SQ/CQ sections
  let sqConfig: SqSectionConfig | null = null;
  if (data.sq_include) {
    const customSqs = Array.isArray(data.sq_custom_questions) ? (data.sq_custom_questions as SqQuestionPayload[]) : [];
    const marksPerQ = Number(data.sq_marks) || 2;
    if (customSqs.length > 0) {
      const m = Math.min(Number(data.sq_include_count) || customSqs.length, customSqs.length);
      const n = Math.min(Number(data.sq_answer_count) || m, m);
      sqConfig = { questions: customSqs.slice(0, m), answer_count: n, marks_per_question: marksPerQ };
    } else {
      const m = Number(data.sq_include_count) || 0;
      const n = Number(data.sq_answer_count) || 0;
      if (m > 0 && n > 0) {
        if (n > m) return c.json({ error: 'সংক্ষিপ্ত প্রশ্ন: উত্তর সংখ্যা (N) মোট প্রশ্ন (M) এর চেয়ে বেশি হতে পারে না।' }, 400);
        const sqRes = await c.env.DB.prepare(
          'SELECT id, question_text, answer, marks, board, year FROM short_questions WHERE subject_id = ? AND is_active = 1 ORDER BY RANDOM() LIMIT ?'
        )
          .bind(Number(data.sq_subject_id) || subjectId, m)
          .all<SqQuestionPayload>();
        if ((sqRes.results || []).length < m) {
          return c.json({ error: `সংক্ষিপ্ত প্রশ্ন: ${m}টি চাওয়া হয়েছে কিন্তু মাত্র ${sqRes.results?.length || 0}টি উপলব্ধ।` }, 400);
        }
        sqConfig = { questions: sqRes.results || [], answer_count: n, marks_per_question: marksPerQ };
      }
    }
  }

  let cqConfig: CqSectionConfig | null = null;
  if (data.cq_include) {
    const customCqs = Array.isArray(data.cq_custom_questions) ? (data.cq_custom_questions as CqQuestionPayload[]) : [];
    if (customCqs.length > 0) {
      const m = Math.min(Number(data.cq_include_count) || customCqs.length, customCqs.length);
      const n = Math.min(Number(data.cq_answer_count) || m, m);
      cqConfig = { questions: customCqs.slice(0, m), answer_count: n };
    } else {
      const m = Number(data.cq_include_count) || 0;
      const n = Number(data.cq_answer_count) || 0;
      if (m > 0 && n > 0) {
        if (n > m) return c.json({ error: 'সৃজনশীল প্রশ্ন: উত্তর সংখ্যা মোট প্রশ্নের চেয়ে বেশি হতে পারে না।' }, 400);
        const cqRes = await c.env.DB.prepare(
          'SELECT id, stem, part_ka, part_kha, part_ga, part_gha, marks_ka, marks_kha, marks_ga, marks_gha, board, year FROM cq_questions WHERE subject_id = ? AND is_active = 1 ORDER BY RANDOM() LIMIT ?'
        )
          .bind(Number(data.cq_subject_id) || subjectId, m)
          .all<CqQuestionPayload>();
        if ((cqRes.results || []).length < m) {
          return c.json({ error: `সৃজনশীল প্রশ্ন: ${m}টি চাওয়া হয়েছে কিন্তু মাত্র ${cqRes.results?.length || 0}টি উপলব্ধ।` }, 400);
        }
        cqConfig = { questions: cqRes.results || [], answer_count: n };
      }
    }
  }

  let totalMarks = selectedQuestions.length;
  if (sqConfig) totalMarks += sqConfig.answer_count * sqConfig.marks_per_question;
  if (cqConfig) totalMarks += cqConfig.answer_count * 10;

  const studioDefaults = await getTeacherBrandingStudio(c.env.DB, user?.id);
  const paperCfg: PaperConfig = {
    title,
    class_name: classObj.name_bn || classObj.name,
    subject_name: subjectObj.name_bn || subjectObj.name,
    time: timeMinutes,
    marks: totalMarks,
    omr_style: omrStyle,
    sq_config: sqConfig,
    cq_config: cqConfig,
    studio: normalizeStudioConfig(studioDefaults, omrStyle),
  };

  const usedIds = selectedQuestions.map((q) => q.id);
  const ins = await c.env.DB.prepare(
    `INSERT INTO generated_papers (user_id, title, class_id, subject_id, chapter_ids, question_ids, question_count, time_minutes, custom_paper_config, omr_style)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      user?.id || null,
      title,
      classId,
      subjectId,
      JSON.stringify(chapterIds),
      JSON.stringify(usedIds),
      usedIds.length,
      timeMinutes,
      JSON.stringify(paperCfg),
      omrStyle ? 1 : 0
    )
    .run();

  const paperId = Number(ins.meta.last_row_id);
  if (user) {
    await c.env.DB.prepare("INSERT INTO generation_logs (user_id, generation_type) VALUES (?, 'db')")
      .bind(user.id)
      .run();
  }

  return c.json({
    success: true,
    paper_id: paperId,
    question_count: usedIds.length,
    total_marks: totalMarks,
    studio_url: `/papers/${paperId}/studio`,
    print_url: `/papers/${paperId}/print`,
    student_download: `/download/${paperId}/student?format=pdf`,
    teacher_download: `/download/${paperId}/teacher?format=pdf`,
  });
});

paperRoutes.post('/generate-custom-paper', rateLimit(20, 60, 'gen_custom'), async (c) => {
  const user = c.get('user');
  const data = (await c.req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!data) return c.json({ error: 'Invalid JSON payload' }, 400);

  const rawQuestions = Array.isArray(data.questions) ? (data.questions as McqQuestionPayload[]) : [];
  if (rawQuestions.length === 0) return c.json({ error: 'At least one question is required.' }, 400);
  if (rawQuestions.length > MAX_QUESTIONS_PER_PAPER) {
    return c.json({ error: `Maximum ${MAX_QUESTIONS_PER_PAPER} questions allowed.` }, 400);
  }

  for (let i = 0; i < rawQuestions.length; i++) {
    const q = rawQuestions[i];
    if (!q.question_text || !Array.isArray(q.answer_options) || q.answer_options.length < 4 || !q.correct_answer) {
      return c.json({ error: `Question ${i + 1} is incomplete.` }, 400);
    }
  }

  const title = String(data.title || 'Custom Question Paper').slice(0, 200);
  const timeMinutes = Number(data.time_minutes) || rawQuestions.length;
  const omrStyle = data.omr_style !== undefined ? Boolean(data.omr_style) : true;
  const studioDefaults = await getTeacherBrandingStudio(c.env.DB, user?.id);

  const paperCfg: PaperConfig = {
    title,
    class_name: String(data.class_name || ''),
    subject_name: String(data.subject_name || ''),
    time: timeMinutes,
    marks: rawQuestions.length,
    omr_style: omrStyle,
    studio: normalizeStudioConfig(studioDefaults, omrStyle),
  };

  const ins = await c.env.DB.prepare(
    `INSERT INTO generated_papers (user_id, title, question_count, time_minutes, custom_questions_json, custom_paper_config, omr_style)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      user?.id || null,
      title,
      rawQuestions.length,
      timeMinutes,
      JSON.stringify(rawQuestions),
      JSON.stringify(paperCfg),
      omrStyle ? 1 : 0
    )
    .run();

  const paperId = Number(ins.meta.last_row_id);
  return c.json({
    success: true,
    paper_id: paperId,
    question_count: rawQuestions.length,
    studio_url: `/papers/${paperId}/studio`,
    print_url: `/papers/${paperId}/print`,
    student_download: `/download/${paperId}/student?format=pdf`,
    teacher_download: `/download/${paperId}/teacher?format=pdf`,
  });
});

paperRoutes.post('/api/builder/questions', async (c) => {
  const user = c.get('user');
  const body = (await c.req.json().catch(() => ({}))) as {
    type?: string;
    subject_id?: number;
    chapter_id?: number;
    search?: string;
    limit?: number;
  };
  const qType = (body.type || 'mcq').toLowerCase();
  const limit = Math.min(Number(body.limit) || 30, 60);
  const search = (body.search || '').trim();
  const subjectId = Number(body.subject_id) || 0;
  const chapterId = Number(body.chapter_id) || 0;

  if (qType === 'sq') {
    let sql = 'SELECT id, question_text, marks, board, year, "db" as db_source FROM short_questions WHERE is_active = 1';
    const binds: unknown[] = [];
    if (subjectId) {
      sql += ' AND subject_id = ?';
      binds.push(subjectId);
    }
    if (chapterId) {
      sql += ' AND chapter_id = ?';
      binds.push(chapterId);
    }
    if (search) {
      sql += ' AND question_text LIKE ?';
      binds.push(`%${search}%`);
    }
    sql += ' ORDER BY id DESC LIMIT ?';
    binds.push(limit);
    const res = await c.env.DB.prepare(sql).bind(...binds).all();
    return c.json({ questions: res.results || [] });
  }

  if (qType === 'cq') {
    let sql = 'SELECT id, stem, part_ka, part_kha, part_ga, part_gha, marks_ka, marks_kha, marks_ga, marks_gha, board, year, "db" as db_source FROM cq_questions WHERE is_active = 1';
    const binds: unknown[] = [];
    if (subjectId) {
      sql += ' AND subject_id = ?';
      binds.push(subjectId);
    }
    if (chapterId) {
      sql += ' AND chapter_id = ?';
      binds.push(chapterId);
    }
    if (search) {
      sql += ' AND stem LIKE ?';
      binds.push(`%${search}%`);
    }
    sql += ' ORDER BY id DESC LIMIT ?';
    binds.push(limit);
    const res = await c.env.DB.prepare(sql).bind(...binds).all();
    return c.json({ questions: res.results || [] });
  }

  // MCQ: merge curriculum questions + public/own bank questions
  let sql = `SELECT q.id, q.question_text, q.question_type, q.board, q.year, q.difficulty, 'db' as db_source
             FROM questions q
             JOIN chapters ch ON ch.id = q.chapter_id
             WHERE q.is_active = 1`;
  const binds: unknown[] = [];
  if (subjectId) {
    sql += ' AND ch.subject_id = ?';
    binds.push(subjectId);
  }
  if (chapterId) {
    sql += ' AND q.chapter_id = ?';
    binds.push(chapterId);
  }
  if (search) {
    sql += ' AND q.question_text LIKE ?';
    binds.push(`%${search}%`);
  }
  sql += ' ORDER BY q.id DESC LIMIT ?';
  binds.push(limit);
  const dbMcqs = await c.env.DB.prepare(sql).bind(...binds).all();

  let bqSql = `SELECT id, question_text, 'simple' as question_type, board, year, difficulty, 'bank' as db_source
               FROM bank_questions WHERE is_active = 1 AND question_type = 'MCQ'
               AND (visibility = 'public'${user ? ' OR teacher_id = ?' : ''})`;
  const bqBinds: unknown[] = user ? [user.id] : [];
  if (subjectId) {
    bqSql += ' AND subject_id = ?';
    bqBinds.push(subjectId);
  }
  if (chapterId) {
    bqSql += ' AND chapter_id = ?';
    bqBinds.push(chapterId);
  }
  if (search) {
    bqSql += ' AND question_text LIKE ?';
    bqBinds.push(`%${search}%`);
  }
  bqSql += ' ORDER BY id DESC LIMIT ?';
  bqBinds.push(limit);
  const bankMcqs = await c.env.DB.prepare(bqSql).bind(...bqBinds).all();

  return c.json({
    questions: [...(dbMcqs.results || []), ...(bankMcqs.results || [])].slice(0, limit),
  });
});

paperRoutes.post('/api/builder/generate', requireTeacher, rateLimit(20, 60, 'builder_gen'), async (c) => {
  const user = c.get('user')!;
  const credits = await getUserCredits(c.env.DB, user.id);
  if (credits.remaining <= 0) {
    return c.json({ error: 'Daily generation limit reached.', credits_exhausted: true }, 429);
  }

  const data = (await c.req.json().catch(() => null)) as {
    paper_config?: Record<string, unknown>;
    sections?: Array<{
      type: string;
      questions?: Array<Record<string, unknown>>;
      answer_count?: number;
      marks_per_question?: number;
    }>;
  } | null;

  if (!data || !Array.isArray(data.sections)) {
    return c.json({ error: 'Missing sections data.' }, 400);
  }

  const cfg = data.paper_config || {};
  const classId = Number(cfg.class_id) || null;
  const subjectId = Number(cfg.subject_id) || null;
  const title = String(cfg.title || 'Question Paper').slice(0, 200);
  const timeMinutes = Number(cfg.time_minutes) || 60;
  const omrStyle = cfg.omr_style !== undefined ? Boolean(cfg.omr_style) : true;

  const mcqList: McqQuestionPayload[] = [];
  let sqConfig: SqSectionConfig | null = null;
  let cqConfig: CqSectionConfig | null = null;

  for (const sec of data.sections) {
    const items = sec.questions || [];
    if (items.length === 0) continue;

    if (sec.type === 'mcq') {
      for (const item of items) {
        if (item.source === 'db' && item.id) {
          if (item.db_source === 'bank') {
            const bq = await c.env.DB.prepare(
              `SELECT * FROM bank_questions WHERE id = ? AND question_type = 'MCQ' AND is_active = 1 AND (visibility = 'public' OR teacher_id = ?)`
            )
              .bind(Number(item.id), user.id)
              .first<{
                id: number;
                question_text: string;
                answer_options: string;
                correct_answer: string;
                explanation: string | null;
                board: string | null;
                year: number | null;
              }>();
            if (bq) {
              mcqList.push({
                id: bq.id,
                question_text: bq.question_text,
                type: 'simple',
                answer_options: JSON.parse(bq.answer_options || '[]'),
                correct_answer: bq.correct_answer || '',
                explanation: bq.explanation,
                board: bq.board,
                year: bq.year,
              });
              continue;
            }
          }
          const qRow = await c.env.DB.prepare('SELECT * FROM questions WHERE id = ? AND is_active = 1')
            .bind(Number(item.id))
            .first<DbQuestionRow>();
          if (qRow) mcqList.push(dbQuestionToPayload(qRow));
        } else if (item.source === 'custom') {
          mcqList.push({
            question_text: String(item.question_text || ''),
            type: item.type === 'complex' ? 'complex' : 'simple',
            sub_options: (item.sub_options as string[]) || [],
            final_prompt: String(item.final_prompt || ''),
            answer_options: (item.answer_options as string[]) || [],
            correct_answer: String(item.correct_answer || ''),
            explanation: item.explanation ? String(item.explanation) : null,
          });
        }
      }
    } else if (sec.type === 'sq') {
      const sqList: SqQuestionPayload[] = [];
      for (const item of items) {
        if (item.source === 'db' && item.id) {
          const sq = await c.env.DB.prepare(
            'SELECT id, question_text, answer, marks, board, year FROM short_questions WHERE id = ? AND is_active = 1'
          )
            .bind(Number(item.id))
            .first<SqQuestionPayload>();
          if (sq) sqList.push(sq);
        } else if (item.source === 'custom') {
          sqList.push({
            question_text: String(item.question_text || ''),
            marks: Number(item.marks) || 2,
          });
        }
      }
      if (sqList.length > 0) {
        sqConfig = {
          questions: sqList,
          answer_count: Number(sec.answer_count) || sqList.length,
          marks_per_question: Number(sec.marks_per_question) || 2,
        };
      }
    } else if (sec.type === 'cq') {
      const cqList: CqQuestionPayload[] = [];
      for (const item of items) {
        if (item.source === 'db' && item.id) {
          const cq = await c.env.DB.prepare('SELECT * FROM cq_questions WHERE id = ? AND is_active = 1')
            .bind(Number(item.id))
            .first<CqQuestionPayload>();
          if (cq) cqList.push(cq);
        } else if (item.source === 'custom') {
          cqList.push(item as unknown as CqQuestionPayload);
        }
      }
      if (cqList.length > 0) {
        cqConfig = {
          questions: cqList,
          answer_count: Number(sec.answer_count) || cqList.length,
        };
      }
    }
  }

  if (mcqList.length === 0 && !sqConfig && !cqConfig) {
    return c.json({ error: 'No questions in any section.' }, 400);
  }

  let totalMarks = mcqList.length;
  if (sqConfig) totalMarks += sqConfig.answer_count * sqConfig.marks_per_question;
  if (cqConfig) totalMarks += cqConfig.answer_count * 10;

  let className = String(cfg.class_name || '');
  let subjectName = String(cfg.subject_name || '');
  if (classId && !className) {
    const cRow = await c.env.DB.prepare('SELECT name, name_bn FROM classes WHERE id = ?')
      .bind(classId)
      .first<{ name: string; name_bn: string | null }>();
    if (cRow) className = cRow.name_bn || cRow.name;
  }
  if (subjectId && !subjectName) {
    const sRow = await c.env.DB.prepare('SELECT name, name_bn FROM subjects WHERE id = ?')
      .bind(subjectId)
      .first<{ name: string; name_bn: string | null }>();
    if (sRow) subjectName = sRow.name_bn || sRow.name;
  }

  const studioDefaults = await getTeacherBrandingStudio(c.env.DB, user.id);
  const paperCfg: PaperConfig = {
    title,
    class_name: className,
    subject_name: subjectName,
    time: timeMinutes,
    marks: totalMarks,
    omr_style: omrStyle,
    sq_config: sqConfig,
    cq_config: cqConfig,
    studio: normalizeStudioConfig(studioDefaults, omrStyle),
  };

  const ins = await c.env.DB.prepare(
    `INSERT INTO generated_papers (user_id, title, class_id, subject_id, question_count, time_minutes, custom_questions_json, custom_paper_config, omr_style)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      user.id,
      title,
      classId,
      subjectId,
      mcqList.length + (sqConfig?.questions.length || 0) + (cqConfig?.questions.length || 0),
      timeMinutes,
      JSON.stringify(mcqList),
      JSON.stringify(paperCfg),
      omrStyle ? 1 : 0
    )
    .run();

  const paperId = Number(ins.meta.last_row_id);
  await c.env.DB.prepare("INSERT INTO generation_logs (user_id, generation_type) VALUES (?, 'builder')")
    .bind(user.id)
    .run();

  return c.json({
    success: true,
    paper_id: paperId,
    question_count: mcqList.length,
    total_marks: totalMarks,
    studio_url: `/papers/${paperId}/studio`,
    student_download: `/download/${paperId}/student?format=pdf`,
    teacher_download: `/download/${paperId}/teacher?format=pdf`,
  });
});

// ── Live Print Studio & PDF Routes ────────────────────────────────────────

paperRoutes.get('/papers/:id/studio', async (c) => {
  const id = Number(c.req.param('id'));
  const paper = await c.env.DB.prepare('SELECT * FROM generated_papers WHERE id = ?')
    .bind(id)
    .first<GeneratedPaperRow>();
  if (!paper) return c.notFound();

  const user = c.get('user');
  const isCustomGuest = Boolean(paper.custom_questions_json && !paper.user_id);
  const canViewTeacherCopy = Boolean(user || isCustomGuest);
  const canEditConfig = Boolean(user && (!paper.user_id || paper.user_id === user.id || user.is_admin));

  const { questions, paperConfig } = await loadPaperRenderContext(c.env.DB, paper);
  const tabParam = c.req.query('tab');
  const defaultTab = tabParam === 'answers' || tabParam === 'teacher' ? tabParam : 'questions';

  const html = renderPaperStudioHtml({
    paperId: paper.id,
    questions,
    paperConfig,
    canViewTeacherCopy,
    canEditConfig,
    defaultTab,
    printOnly: false,
    autoprint: c.req.query('autoprint') === '1',
    hasBrowserPdf: Boolean(c.env.BROWSER),
  });
  return c.html(html);
});

paperRoutes.get('/papers/:id/print', async (c) => {
  const id = Number(c.req.param('id'));
  const paper = await c.env.DB.prepare('SELECT * FROM generated_papers WHERE id = ?')
    .bind(id)
    .first<GeneratedPaperRow>();
  if (!paper) return c.notFound();

  const user = c.get('user');
  const isCustomGuest = Boolean(paper.custom_questions_json && !paper.user_id);
  const copy = c.req.query('copy') || 'questions';
  if ((copy === 'answers' || copy === 'teacher') && !user && !isCustomGuest) {
    return c.json({ error: 'Authentication required for answer keys' }, 403);
  }

  const { questions, paperConfig } = await loadPaperRenderContext(c.env.DB, paper);
  const defaultTab = copy === 'answers' || copy === 'teacher' ? copy : 'questions';

  const html = renderPaperStudioHtml({
    paperId: paper.id,
    questions,
    paperConfig,
    canViewTeacherCopy: Boolean(user || isCustomGuest),
    defaultTab,
    printOnly: true,
    autoprint: c.req.query('autoprint') === '1',
  });
  return c.html(html);
});

paperRoutes.get('/api/papers/:id/pdf', rateLimit(30, 60, 'paper_pdf'), async (c) => {
  const id = Number(c.req.param('id'));
  const paper = await c.env.DB.prepare('SELECT * FROM generated_papers WHERE id = ?')
    .bind(id)
    .first<GeneratedPaperRow>();
  if (!paper) return c.notFound();

  const user = c.get('user');
  const isCustomGuest = Boolean(paper.custom_questions_json && !paper.user_id);
  const copy = c.req.query('copy') || 'student';
  if ((copy === 'teacher' || copy === 'answers') && !user && !isCustomGuest) {
    return c.json({ error: 'Authentication required for answer keys' }, 403);
  }

  const { questions, paperConfig } = await loadPaperRenderContext(c.env.DB, paper);
  const defaultTab = copy === 'teacher' ? 'teacher' : copy === 'answers' ? 'answers' : 'questions';
  const html = renderPaperStudioHtml({
    paperId: paper.id,
    questions,
    paperConfig,
    canViewTeacherCopy: Boolean(user || isCustomGuest),
    defaultTab,
    printOnly: true,
    autoprint: false,
  });

  await c.env.DB.prepare('UPDATE generated_papers SET download_count = download_count + 1 WHERE id = ?')
    .bind(id)
    .run();

  const pdfBuf = await renderHtmlToPdfBuffer(c.env, html, `papers/${id}/${defaultTab}.pdf`);
  if (pdfBuf) {
    return new Response(pdfBuf, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="Question_Paper_${id}_${copy}.pdf"`,
      },
    });
  }

  // Fallback when Browser Rendering is not bound (Free tier): redirect to print studio autoprint
  return c.redirect(`/papers/${id}/studio?tab=${defaultTab}&autoprint=1`);
});

paperRoutes.get('/download/:id/:paperType', async (c) => {
  const id = Number(c.req.param('id'));
  const paperType = c.req.param('paperType');
  if (paperType !== 'student' && paperType !== 'teacher') {
    return c.json({ error: 'Invalid paper type' }, 400);
  }
  const format = (c.req.query('format') || 'pdf').toLowerCase();
  if (format === 'pdf' && c.env.BROWSER) {
    return c.redirect(`/api/papers/${id}/pdf?copy=${paperType}`);
  }
  return c.redirect(`/papers/${id}/studio?tab=${paperType === 'teacher' ? 'answers' : 'questions'}`);
});

paperRoutes.put('/api/papers/:id/config', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const paper = await c.env.DB.prepare('SELECT * FROM generated_papers WHERE id = ?')
    .bind(id)
    .first<GeneratedPaperRow>();
  if (!paper) return c.json({ error: 'Paper not found' }, 404);
  if (paper.user_id && paper.user_id !== user.id && !user.is_admin) {
    return c.json({ error: 'Forbidden' }, 403);
  }

  const body = (await c.req.json().catch(() => ({}))) as { studio?: Partial<StudioConfig> };
  const existingCfg: PaperConfig = paper.custom_paper_config
    ? JSON.parse(paper.custom_paper_config)
    : { title: paper.title || 'Question Paper' };

  const normalized = normalizeStudioConfig(body.studio, paper.omr_style === 1);
  existingCfg.studio = normalized;

  await c.env.DB.prepare('UPDATE generated_papers SET custom_paper_config = ?, omr_style = ? WHERE id = ?')
    .bind(JSON.stringify(existingCfg), normalized.omrStyle ? 1 : 0, id)
    .run();

  return c.json({ success: true, studio: normalized });
});

// ── Saved Question Sets & Sharing ─────────────────────────────────────────

paperRoutes.post('/save-question-set', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as {
    name?: string;
    questions?: McqQuestionPayload[];
    paper_config?: PaperConfig;
    source?: string;
    paper_id?: number;
  };
  const name = (body.name || 'Saved Question Set').trim().slice(0, 200);
  let questions = body.questions || [];
  let paperCfg = body.paper_config || { title: name };

  if (body.paper_id && questions.length === 0) {
    const paper = await c.env.DB.prepare('SELECT * FROM generated_papers WHERE id = ?')
      .bind(body.paper_id)
      .first<GeneratedPaperRow>();
    if (paper) {
      const ctx = await loadPaperRenderContext(c.env.DB, paper);
      questions = ctx.questions;
      paperCfg = ctx.paperConfig;
    }
  }

  if (questions.length === 0) return c.json({ error: 'No questions to save.' }, 400);

  const ins = await c.env.DB.prepare(
    `INSERT INTO question_sets (user_id, name, questions_json, paper_config, source, paper_id)
     VALUES (?, ?, ?, ?, ?, ?)`
  )
    .bind(
      user.id,
      name,
      JSON.stringify(questions),
      JSON.stringify(paperCfg),
      body.source || 'custom',
      body.paper_id || null
    )
    .run();

  return c.json({ success: true, id: Number(ins.meta.last_row_id) }, 201);
});

paperRoutes.get('/question-set/:id', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const qs = await c.env.DB.prepare('SELECT * FROM question_sets WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first<{
      id: number;
      name: string;
      questions_json: string;
      paper_config: string | null;
      source: string;
      share_token: string | null;
      is_shared: number;
      created_at: string;
    }>();
  if (!qs) return c.json({ error: 'Question set not found' }, 404);
  return c.json({
    id: qs.id,
    name: qs.name,
    questions: JSON.parse(qs.questions_json),
    paper_config: qs.paper_config ? JSON.parse(qs.paper_config) : null,
    source: qs.source,
    share_token: qs.share_token,
    is_shared: Boolean(qs.is_shared),
    created_at: qs.created_at,
  });
});

paperRoutes.put('/question-set/:id', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const body = (await c.req.json().catch(() => ({}))) as {
    name?: string;
    questions?: McqQuestionPayload[];
    paper_config?: PaperConfig;
  };
  const existing = await c.env.DB.prepare('SELECT * FROM question_sets WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first();
  if (!existing) return c.json({ error: 'Not found' }, 404);

  await c.env.DB.prepare(
    `UPDATE question_sets SET name = COALESCE(?, name), questions_json = COALESCE(?, questions_json),
     paper_config = COALESCE(?, paper_config), updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
     WHERE id = ? AND user_id = ?`
  )
    .bind(
      body.name ?? null,
      body.questions ? JSON.stringify(body.questions) : null,
      body.paper_config ? JSON.stringify(body.paper_config) : null,
      id,
      user.id
    )
    .run();
  return c.json({ success: true });
});

paperRoutes.post('/question-set/:id/delete', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  await c.env.DB.prepare('DELETE FROM question_sets WHERE id = ? AND user_id = ?').bind(id, user.id).run();
  return c.json({ success: true });
});

paperRoutes.post('/question-set/:id/share', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const qs = await c.env.DB.prepare('SELECT id, share_token, is_shared FROM question_sets WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first<{ id: number; share_token: string | null; is_shared: number }>();
  if (!qs) return c.json({ error: 'Question set not found' }, 404);

  const token = qs.share_token || randomUrlSafeToken(10);
  const newShared = qs.is_shared ? 0 : 1;
  await c.env.DB.prepare('UPDATE question_sets SET share_token = ?, is_shared = ? WHERE id = ?')
    .bind(token, newShared, id)
    .run();
  return c.json({ success: true, is_shared: Boolean(newShared), share_token: token, share_url: `/paper/${token}` });
});

paperRoutes.post('/regenerate-from-set/:id', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const qs = await c.env.DB.prepare('SELECT * FROM question_sets WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first<{ id: number; name: string; questions_json: string; paper_config: string | null }>();
  if (!qs) return c.json({ error: 'Question set not found' }, 404);

  const questions = JSON.parse(qs.questions_json) as McqQuestionPayload[];
  const cfg = qs.paper_config ? (JSON.parse(qs.paper_config) as PaperConfig) : { title: qs.name };
  const ins = await c.env.DB.prepare(
    `INSERT INTO generated_papers (user_id, title, question_count, time_minutes, custom_questions_json, custom_paper_config, omr_style)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(user.id, cfg.title || qs.name, questions.length, cfg.time || questions.length, qs.questions_json, JSON.stringify(cfg), 1)
    .run();
  const paperId = Number(ins.meta.last_row_id);
  return c.json({ success: true, paper_id: paperId, studio_url: `/papers/${paperId}/studio` });
});

paperRoutes.get('/paper/:shareToken', async (c) => {
  const token = c.req.param('shareToken');
  const qs = await c.env.DB.prepare('SELECT * FROM question_sets WHERE share_token = ? AND is_shared = 1')
    .bind(token)
    .first<{ id: number; name: string; questions_json: string }>();
  if (!qs) {
    return c.html(
      renderPageLayout({ title: 'পাওয়া যায়নি', user: c.get('user') }, '<div class="container"><div class="card"><h2>এই প্রশ্নপত্রটি আর শেয়ার করা নেই।</h2></div></div>'),
      404
    );
  }

  const questions = JSON.parse(qs.questions_json) as McqQuestionPayload[];
  const itemsHtml = questions
    .map((q, idx) => {
      const opts = (q.answer_options || [])
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
        title: qs.name,
        user: c.get('user'),
        extraScripts: `<script>
async function submitPractice(e){
  e.preventDefault();
  const fd = new FormData(e.target);
  const responses = {};
  for (const [k, v] of fd.entries()) responses[k.replace('q_','')] = v;
  const resp = await fetch('/paper/${escapeHtml(token)}/submit', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({responses}) });
  const data = await resp.json();
  document.getElementById('practiceResult').innerHTML = '<h3>আপনার স্কোর: ' + data.score + ' / ' + data.total + ' (' + data.percentage + '%)</h3>';
  document.getElementById('practiceResult').style.display = 'block';
}
</script>`,
      },
      `<section class="page-section"><div class="container">
        <h1>${escapeHtml(qs.name)}</h1>
        <form onsubmit="submitPractice(event)">
          ${itemsHtml}
          <button type="submit" class="btn btn-primary btn-lg mt-3">উত্তর জমা দিন</button>
        </form>
        <div id="practiceResult" class="card success-card mt-3" style="display:none;"></div>
      </div></section>`
    )
  );
});

paperRoutes.post('/paper/:shareToken/submit', async (c) => {
  const token = c.req.param('shareToken');
  const qs = await c.env.DB.prepare('SELECT questions_json FROM question_sets WHERE share_token = ? AND is_shared = 1')
    .bind(token)
    .first<{ questions_json: string }>();
  if (!qs) return c.json({ error: 'Shared paper not found' }, 404);

  const questions = JSON.parse(qs.questions_json) as McqQuestionPayload[];
  const body = (await c.req.json().catch(() => ({}))) as { responses?: Record<string, string> };
  const responses = body.responses || {};
  let score = 0;
  questions.forEach((q, idx) => {
    if (responses[String(idx)] && responses[String(idx)] === q.correct_answer) score++;
  });
  const total = questions.length;
  const percentage = total > 0 ? Math.round((score / total) * 100) : 0;
  return c.json({ score, total, percentage });
});

paperRoutes.get('/paper/:shareToken/api', async (c) => {
  const token = c.req.param('shareToken');
  const qs = await c.env.DB.prepare('SELECT id, name, questions_json, paper_config FROM question_sets WHERE share_token = ? AND is_shared = 1')
    .bind(token)
    .first<{ id: number; name: string; questions_json: string; paper_config: string | null }>();
  if (!qs) return c.json({ error: 'Not found' }, 404);

  const questions = (JSON.parse(qs.questions_json) as McqQuestionPayload[]).map((q) => ({
    question_text: q.question_text,
    type: q.type || 'simple',
    sub_options: q.sub_options || [],
    final_prompt: q.final_prompt || '',
    answer_options: q.answer_options || [],
  }));
  return c.json({ id: qs.id, name: qs.name, questions, paper_config: qs.paper_config ? JSON.parse(qs.paper_config) : null });
});

// ── Static / Info / SEO Routes ────────────────────────────────────────────

paperRoutes.get('/about', (c) =>
  c.html(
    renderPageLayout(
      { title: 'আমাদের সম্পর্কে', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>Prosno.io সম্পর্কে</h1>
        <p>Prosno.io বাংলাদেশের স্কুল, কলেজ, কোচিং সেন্টার ও শিক্ষকদের জন্য নির্মিত একটি আধুনিক প্রশ্নপত্র, সমাধান, OMR এবং লাইভ কুইজ প্ল্যাটফর্ম। সম্পূর্ণ Cloudflare Edge অবকাঠামোতে পরিচালিত হওয়ায় এটি ঢাকা ও সারাদেশে অত্যন্ত দ্রুতগতিতে কাজ করে।</p>
      </div></section>`
    )
  )
);

paperRoutes.get('/contact', (c) =>
  c.html(
    renderPageLayout(
      { title: 'যোগাযোগ', user: c.get('user') },
      `<section class="page-section"><div class="container card">
        <h1>যোগাযোগ করুন</h1>
        <p>যেকোনো প্রশ্ন বা প্রতিষ্ঠানিক প্যাকেজের জন্য ইমেইল করুন: <strong>${escapeHtml(c.env.SUPPORT_EMAIL || 'support@prosno.io')}</strong></p>
      </div></section>`
    )
  )
);

paperRoutes.get('/robots.txt', (c) => {
  const origin = new URL(c.req.url).origin;
  return c.text(`User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: ${origin}/sitemap.xml\n`);
});

paperRoutes.get('/sitemap.xml', (c) => {
  const origin = new URL(c.req.url).origin;
  const urls = ['/', '/generate', '/builder', '/omr-builder', '/bank', '/bank/leaderboard', '/quiz/join', '/about', '/contact'];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${origin}${u}</loc></url>`).join('\n')}
</urlset>`;
  return c.body(xml, 200, { 'Content-Type': 'application/xml; charset=utf-8' });
});
