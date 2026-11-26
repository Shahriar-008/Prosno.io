import type {
  CqQuestionPayload,
  CqSectionConfig,
  McqQuestionPayload,
  PaperConfig,
  SqQuestionPayload,
  SqSectionConfig,
  StudioConfig,
} from '../types';
import { BENGALI_OPTION_PREFIXES, toBengaliNumeral } from '../lib/bengali';
import { escapeHtml, formatMathHtml } from '../lib/math';

export const DEFAULT_STUDIO_CONFIG: StudioConfig = {
  font: 'hind',
  paperSize: 'a4',
  columns: 2,
  fontSizePx: 11.5,
  marginMm: 12,
  omrStyle: true,
  showBoardTags: true,
  headerPreset: 'board',
  instituteName: '',
  instituteSubtitle: '',
  logoUrl: '',
  watermarkText: '',
  watermarkOpacity: 0.08,
};

export function normalizeStudioConfig(raw?: Partial<StudioConfig> | null, fallbackOmr = true): StudioConfig {
  const s = raw || {};
  const validFonts = ['hind', 'noto', 'tiro', 'kalpurush'] as const;
  const font = validFonts.includes(s.font as StudioConfig['font'])
    ? (s.font as StudioConfig['font'])
    : 'hind';
  const paperSize = s.paperSize === 'legal' ? 'legal' : 'a4';
  const colsNum = Number(s.columns);
  const columns: 1 | 2 | 3 = colsNum === 1 ? 1 : colsNum === 3 ? 3 : 2;
  const fontSizePx = Math.min(15, Math.max(9, Number(s.fontSizePx) || 11.5));
  const marginMm = Math.min(25, Math.max(6, Number(s.marginMm) || 12));
  const headerPreset =
    s.headerPreset === 'coaching' || s.headerPreset === 'minimal' ? s.headerPreset : 'board';
  const watermarkOpacity = Math.min(0.25, Math.max(0.02, Number(s.watermarkOpacity) || 0.08));

  return {
    font,
    paperSize,
    columns,
    fontSizePx,
    marginMm,
    omrStyle: typeof s.omrStyle === 'boolean' ? s.omrStyle : fallbackOmr,
    showBoardTags: typeof s.showBoardTags === 'boolean' ? s.showBoardTags : true,
    headerPreset,
    instituteName: String(s.instituteName || '').slice(0, 140),
    instituteSubtitle: String(s.instituteSubtitle || '').slice(0, 180),
    logoUrl: String(s.logoUrl || '').slice(0, 100000),
    watermarkText: String(s.watermarkText || '').slice(0, 100),
    watermarkOpacity,
  };
}

function getFontStack(font: StudioConfig['font']): string {
  switch (font) {
    case 'noto':
      return "'Noto Sans Bengali', 'Hind Siliguri', sans-serif";
    case 'tiro':
      return "'Tiro Bangla', 'Hind Siliguri', serif";
    case 'kalpurush':
      return "'Kalpurush', 'SolaimanLipi', 'Noto Sans Bengali', sans-serif";
    case 'hind':
    default:
      return "'Hind Siliguri', 'Noto Sans Bengali', sans-serif";
  }
}

function resolveCorrectIndex(q: McqQuestionPayload): number {
  const opts = q.answer_options || [];
  const target = String(q.correct_answer || '').trim();
  const idx = opts.findIndex((o) => String(o).trim() === target);
  return idx;
}

function renderMcqItem(
  q: McqQuestionPayload,
  index: number,
  options: { showAnswer: boolean; omrStyle: boolean; showBoardTags: boolean }
): string {
  const bnIdx = toBengaliNumeral(index);
  const qHtml = formatMathHtml(q.question_text || '');
  const boardTag =
    options.showBoardTags && q.board
      ? `<span class="board-tag">[${escapeHtml(q.board)}${q.year ? ' ' + toBengaliNumeral(String(q.year).slice(-2)) : ''}]</span>`
      : '';

  let complexHtml = '';
  if (q.type === 'complex' && Array.isArray(q.sub_options) && q.sub_options.length > 0) {
    const subs = q.sub_options
      .map((s) => `<div class="sub-opt">${formatMathHtml(s)}</div>`)
      .join('');
    const prompt = escapeHtml(q.final_prompt || 'নিচের কোনটি সঠিক?');
    complexHtml = `<div class="complex-subs">${subs}</div><div class="final-prompt">${prompt}</div>`;
  }

  const correctIdx = resolveCorrectIndex(q);
  const ansOpts = q.answer_options || [];
  const optsHtml = ansOpts
    .slice(0, 4)
    .map((opt, i) => {
      const prefix = BENGALI_OPTION_PREFIXES[i] || '';
      const isCorrect = options.showAnswer && i === correctIdx;
      const bubbleHtml = options.omrStyle
        ? `<span class="omr-bubble${isCorrect ? ' filled' : ''}"></span>`
        : '';
      return `<div class="opt-item${isCorrect ? ' opt-correct' : ''}">${bubbleHtml}<span class="opt-prefix">(${prefix})</span> <span class="opt-text">${formatMathHtml(opt)}</span></div>`;
    })
    .join('');

  return `<article class="question-item">
  <p class="q-stem"><span class="q-num">${bnIdx}.</span> ${qHtml} ${boardTag}</p>
  ${complexHtml}
  <div class="options-grid">${optsHtml}</div>
</article>`;
}

function renderShortQuestionsSection(sqConfig: SqSectionConfig | null | undefined): string {
  if (!sqConfig || !Array.isArray(sqConfig.questions) || sqConfig.questions.length === 0) return '';
  const answerCount = toBengaliNumeral(sqConfig.answer_count || sqConfig.questions.length);
  const marksPerQ = toBengaliNumeral(sqConfig.marks_per_question || 2);

  const items = sqConfig.questions
    .map((sq: SqQuestionPayload, i: number) => {
      const bnIdx = toBengaliNumeral(i + 1);
      const qMarks = toBengaliNumeral(sq.marks ?? sqConfig.marks_per_question ?? 2);
      const boardTag = sq.board
        ? `<span class="board-tag">[${escapeHtml(sq.board)}${sq.year ? ' ' + toBengaliNumeral(String(sq.year).slice(-2)) : ''}]</span>`
        : '';
      return `<div class="sq-item">
        <div class="sq-text">${bnIdx}। ${formatMathHtml(sq.question_text)} ${boardTag}</div>
        <div class="sq-mark">${qMarks}</div>
      </div>`;
    })
    .join('');

  return `<section class="section-block sq-section">
    <div class="section-heading">
      <h3>খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)</h3>
      <p>নিচের যেকোনো ${answerCount}টি প্রশ্নের উত্তর দাও। প্রতিটি প্রশ্নের মান ${marksPerQ}।</p>
    </div>
    <div class="sq-list">${items}</div>
  </section>`;
}

function renderCreativeQuestionsSection(cqConfig: CqSectionConfig | null | undefined): string {
  if (!cqConfig || !Array.isArray(cqConfig.questions) || cqConfig.questions.length === 0) return '';
  const answerCount = toBengaliNumeral(cqConfig.answer_count || cqConfig.questions.length);

  const items = cqConfig.questions
    .map((cq: CqQuestionPayload, i: number) => {
      const bnIdx = toBengaliNumeral(i + 1);
      const boardTag = cq.board
        ? `<span class="board-tag">[${escapeHtml(cq.board)}${cq.year ? ' ' + toBengaliNumeral(String(cq.year).slice(-2)) : ''}]</span>`
        : '';
      const parts: Array<[string | null | undefined, number | undefined, string]> = [
        [cq.part_ka, cq.marks_ka ?? 1, 'ক'],
        [cq.part_kha, cq.marks_kha ?? 2, 'খ'],
        [cq.part_ga, cq.marks_ga ?? 3, 'গ'],
        [cq.part_gha, cq.marks_gha ?? 4, 'ঘ'],
      ];
      const partsHtml = parts
        .filter(([text]) => Boolean(text))
        .map(
          ([text, marks, label]) => `<div class="cq-part">
            <span class="cq-part-text"><strong>${label}.</strong> ${formatMathHtml(text)}</span>
            <span class="cq-part-mark">${toBengaliNumeral(marks ?? 0)}</span>
          </div>`
        )
        .join('');

      return `<article class="cq-item">
        <div class="cq-stem"><strong>${bnIdx}। উদ্দীপক:</strong> ${formatMathHtml(cq.stem)} ${boardTag}</div>
        <div class="cq-parts">${partsHtml}</div>
      </article>`;
    })
    .join('');

  return `<section class="section-block cq-section">
    <div class="section-heading">
      <h3>গ-বিভাগ (সৃজনশীল প্রশ্ন)</h3>
      <p>নিচের যেকোনো ${answerCount}টি প্রশ্নের উত্তর দাও।</p>
    </div>
    <div class="cq-list">${items}</div>
  </section>`;
}

function renderAnswersTabContent(
  questions: McqQuestionPayload[],
  sqConfig: SqSectionConfig | null | undefined,
  paperConfig: PaperConfig,
  studio: StudioConfig
): string {
  const bnTime = toBengaliNumeral(paperConfig.time ?? questions.length);
  const bnMarks = toBengaliNumeral(paperConfig.marks ?? questions.length);

  const quickGrid = questions
    .map((q, i) => {
      const idx = i + 1;
      const correctIdx = resolveCorrectIndex(q);
      const letter = correctIdx >= 0 ? BENGALI_OPTION_PREFIXES[correctIdx] : '—';
      return `<div class="quick-key-cell">${toBengaliNumeral(idx)}. ${letter}</div>`;
    })
    .join('');

  const solutions = questions
    .map((q, i) => {
      const idx = i + 1;
      const correctIdx = resolveCorrectIndex(q);
      const letter = correctIdx >= 0 ? `(${BENGALI_OPTION_PREFIXES[correctIdx]})` : '';
      const ansText = formatMathHtml(q.correct_answer || '');
      const explText = q.explanation
        ? formatMathHtml(q.explanation)
        : '<span class="muted-note">ব্যাখ্যা সংযুক্ত নেই।</span>';
      return `<div class="answer-item">
        <span class="ans-badge">${toBengaliNumeral(idx)}. ${letter} ${ansText} :</span>
        <span class="ans-expl">${explText}</span>
      </div>`;
    })
    .join('');

  let sqAnswersHtml = '';
  if (sqConfig && Array.isArray(sqConfig.questions) && sqConfig.questions.some((s) => s.answer)) {
    const sqRows = sqConfig.questions
      .map((s, i) =>
        s.answer
          ? `<div class="answer-item"><span class="ans-badge">সংক্ষিপ্ত ${toBengaliNumeral(i + 1)}।</span> ${formatMathHtml(s.answer)}</div>`
          : ''
      )
      .join('');
    sqAnswersHtml = `<h4 class="ans-section-title" style="margin-top:16px;">খ-বিভাগ (সংক্ষিপ্ত প্রশ্নের উত্তর)</h4><div class="answer-grid">${sqRows}</div>`;
  }

  return `<div class="paper-header preset-${studio.headerPreset}">
    <div class="header-top-row">
      ${studio.logoUrl ? `<img class="inst-logo" src="${escapeHtml(studio.logoUrl)}" alt="Logo">` : ''}
      <div class="header-titles">
        ${studio.instituteName ? `<div class="inst-name">${escapeHtml(studio.instituteName)}</div>` : ''}
        <h2 class="paper-title">${escapeHtml(paperConfig.title || 'প্রশ্নপত্র')}</h2>
        ${paperConfig.subject_name ? `<h3 class="paper-subtitle">বিষয়: ${escapeHtml(paperConfig.subject_name)}${paperConfig.class_name ? ` (${escapeHtml(paperConfig.class_name)})` : ''}</h3>` : ''}
      </div>
    </div>
    <div class="meta-bar">
      <span>পূর্ণমান: ${bnMarks}</span>
      <span class="ans-title-pill">নৈর্ব্যক্তিক উত্তরমালা ও ব্যাখ্যাসহ সমাধান</span>
      <span>সময়: ${bnTime} মিনিট</span>
    </div>
  </div>
  <div class="quick-key-box">
    <h4>দ্রুত উত্তর সংকেত (Quick Answer Key)</h4>
    <div class="quick-key-grid">${quickGrid}</div>
  </div>
  <h4 class="ans-section-title">প্রশ্নভিত্তিক সঠিক উত্তর ও সংক্ষিপ্ত ব্যাখ্যা:</h4>
  <div class="answer-grid">${solutions}</div>
  ${sqAnswersHtml}`;
}

export interface RenderPaperStudioOptions {
  paperId?: number;
  questionSetId?: number;
  questions: McqQuestionPayload[];
  paperConfig: PaperConfig;
  studio?: Partial<StudioConfig> | null;
  canViewTeacherCopy: boolean;
  canEditConfig?: boolean;
  defaultTab?: 'questions' | 'answers' | 'teacher';
  printOnly?: boolean;
  autoprint?: boolean;
  hasBrowserPdf?: boolean;
}

export function renderPaperStudioHtml(opts: RenderPaperStudioOptions): string {
  const studio = normalizeStudioConfig(
    { ...(opts.paperConfig.studio || {}), ...(opts.studio || {}) },
    opts.paperConfig.omr_style ?? true
  );
  const questions = opts.questions || [];
  const sqConfig = opts.paperConfig.sq_config;
  const cqConfig = opts.paperConfig.cq_config;

  const totalMcq = questions.length;
  const totalMarks = opts.paperConfig.marks ?? totalMcq;
  const timeMin = opts.paperConfig.time ?? totalMcq;
  const bnTime = toBengaliNumeral(timeMin);
  const bnMarks = toBengaliNumeral(totalMarks);

  const activeTab =
    !opts.canViewTeacherCopy && opts.defaultTab !== 'questions'
      ? 'questions'
      : opts.defaultTab || 'questions';

  const studentQuestionsHtml = questions
    .map((q, i) =>
      renderMcqItem(q, i + 1, {
        showAnswer: false,
        omrStyle: studio.omrStyle,
        showBoardTags: studio.showBoardTags,
      })
    )
    .join('');

  const teacherQuestionsHtml = opts.canViewTeacherCopy
    ? questions
        .map((q, i) =>
          renderMcqItem(q, i + 1, {
            showAnswer: true,
            omrStyle: true,
            showBoardTags: studio.showBoardTags,
          })
        )
        .join('')
    : '';

  const sqHtml = renderShortQuestionsSection(sqConfig);
  const cqHtml = renderCreativeQuestionsSection(cqConfig);
  const answersHtml = opts.canViewTeacherCopy
    ? renderAnswersTabContent(questions, sqConfig, opts.paperConfig, studio)
    : '';

  const headerHtml = (copyBadge?: string) => `<div class="paper-header preset-${studio.headerPreset}" data-paper-header>
    <div class="header-top-row">
      ${studio.logoUrl ? `<img class="inst-logo" src="${escapeHtml(studio.logoUrl)}" alt="Logo">` : '<img class="inst-logo hidden" src="" alt="Logo">'}
      <div class="header-titles">
        <div class="inst-name${studio.instituteName ? '' : ' hidden'}" data-el="instName">${escapeHtml(studio.instituteName)}</div>
        <div class="inst-sub${studio.instituteSubtitle ? '' : ' hidden'}" data-el="instSubtitle">${escapeHtml(studio.instituteSubtitle)}</div>
        <h2 class="paper-title">${escapeHtml(opts.paperConfig.title || 'প্রশ্নপত্র')}</h2>
        ${opts.paperConfig.subject_name || opts.paperConfig.class_name ? `<h3 class="paper-subtitle">${opts.paperConfig.subject_name ? `বিষয়: ${escapeHtml(opts.paperConfig.subject_name)}` : ''}${opts.paperConfig.class_name ? ` | ${escapeHtml(opts.paperConfig.class_name)}` : ''}</h3>` : ''}
      </div>
    </div>
    <div class="meta-bar">
      <span>সময়: ${bnTime} মিনিট</span>
      <span>${copyBadge ? escapeHtml(copyBadge) : 'বহুনির্বাচনি অভীক্ষা'}</span>
      <span>পূর্ণমান: ${bnMarks}</span>
    </div>
    <p class="header-note">[বিশেষ দ্রষ্টব্য: সরবরাহকৃত উত্তরপত্রে সঠিক উত্তরের বৃত্তটি বলপয়েন্ট কলম দিয়ে সম্পূর্ণ ভরাট করো।]</p>
  </div>`;

  const serializedData = JSON.stringify({
    paperId: opts.paperId ?? null,
    questionSetId: opts.questionSetId ?? null,
    paperConfig: opts.paperConfig,
    studio,
    questions,
    sqConfig: sqConfig || null,
    cqConfig: cqConfig || null,
    canViewTeacherCopy: opts.canViewTeacherCopy,
    canEditConfig: Boolean(opts.canEditConfig),
    autoprint: Boolean(opts.autoprint),
  }).replace(/</g, '\\u003c');

  const pageSizeCss = studio.paperSize === 'legal' ? '8.5in 14in' : 'A4';
  const fontStack = getFontStack(studio.font);

  return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(opts.paperConfig.title || 'Prosno.io Print Studio')}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;500;600;700&family=Tiro+Bangla:ital@0;1&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/dist/print-studio.css">
  <style>
    :root {
      --paper-font: ${fontStack};
      --paper-cols: ${studio.columns};
      --paper-font-size: ${studio.fontSizePx}px;
      --paper-margin: ${studio.marginMm}mm;
      --wm-opacity: ${studio.watermarkOpacity};
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      padding: ${opts.printOnly ? '0' : '16px'};
      font-family: var(--paper-font);
      background: ${opts.printOnly ? '#ffffff' : '#eef2f7'};
      color: #111827;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }

    .hidden { display: none !important; }

    /* Studio Toolbar */
    .studio-toolbar {
      position: sticky;
      top: 10px;
      z-index: 30;
      max-width: 1120px;
      margin: 0 auto 18px auto;
      background: rgba(255, 255, 255, 0.96);
      backdrop-filter: blur(10px);
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 12px 18px;
      box-shadow: 0 8px 24px rgba(15, 36, 33, 0.08);
    }

    .toolbar-top {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .toolbar-brand h1 {
      margin: 0;
      font-size: 17px;
      font-weight: 700;
      color: #0f172a;
    }

    .toolbar-brand p {
      margin: 2px 0 0 0;
      font-size: 12.5px;
      color: #64748b;
    }

    .toolbar-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      align-items: center;
    }

    .st-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      color: #1e293b;
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .st-btn:hover { background: #e2e8f0; }
    .st-btn:active { transform: scale(0.98); }
    .st-btn.active { background: #0f766e; border-color: #0f766e; color: #ffffff; }
    .st-btn.emerald { background: #0f766e; border-color: #0f766e; color: #ffffff; }
    .st-btn.emerald:hover { background: #115e59; }
    .st-btn.indigo { background: #0f172a; border-color: #0f172a; color: #ffffff; }
    .st-btn.indigo:hover { background: #1e293b; }
    .st-btn.amber { background: #ffffff; border-color: #0f766e; color: #0f766e; }
    .st-btn.amber:hover { background: #f0fdfa; }

    /* Customization Drawer */
    .studio-drawer {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid #e2e8f0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px 14px;
    }
    .ctrl-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .ctrl-group label {
      font-size: 11.5px;
      font-weight: 600;
      color: #475569;
    }
    .ctrl-group input[type="text"],
    .ctrl-group select {
      padding: 6px 9px;
      border-radius: 7px;
      border: 1px solid #cbd5e1;
      font-family: inherit;
      font-size: 12.5px;
      background: #fff;
    }
    .ctrl-row {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
    }

    /* Paper Sheet Canvas */
    .print-page {
      position: relative;
      max-width: ${studio.paperSize === 'legal' ? '216mm' : '210mm'};
      min-height: ${studio.paperSize === 'legal' ? '355mm' : '297mm'};
      margin: 0 auto 24px auto;
      background: #ffffff;
      padding: var(--paper-margin);
      border-radius: ${opts.printOnly ? '0' : '12px'};
      box-shadow: ${opts.printOnly ? 'none' : '0 10px 30px rgba(15, 23, 42, 0.1)'};
      font-family: var(--paper-font);
      font-size: var(--paper-font-size);
      line-height: 1.45;
      overflow: hidden;
    }

    .watermark-layer {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      z-index: 0;
    }
    .watermark-text {
      transform: rotate(-32deg);
      font-size: 46px;
      font-weight: 700;
      color: rgba(15, 23, 42, var(--wm-opacity));
      white-space: nowrap;
      user-select: none;
    }

    .sheet-inner { position: relative; z-index: 1; }

    /* Header Presets */
    .paper-header {
      text-align: center;
      padding-bottom: 8px;
      margin-bottom: 12px;
      border-bottom: 2px solid #111827;
    }
    .paper-header.preset-coaching {
      border-bottom: 3px double #1e293b;
      background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
      padding: 8px 10px;
      border-radius: 6px;
    }
    .paper-header.preset-minimal {
      border-bottom: 1px solid #94a3b8;
    }
    .header-top-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
    }
    .inst-logo {
      max-height: 52px;
      max-width: 72px;
      object-fit: contain;
    }
    .inst-name {
      font-size: 1.35em;
      font-weight: 700;
      color: #0f172a;
    }
    .inst-sub {
      font-size: 0.92em;
      color: #475569;
    }
    .paper-title {
      margin: 2px 0 0 0;
      font-size: 1.4em;
      font-weight: 700;
      color: #111827;
    }
    .paper-subtitle {
      margin: 2px 0 0 0;
      font-size: 1.08em;
      font-weight: 600;
      color: #334155;
    }
    .meta-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 6px;
      font-weight: 600;
      font-size: 0.95em;
    }
    .header-note {
      margin: 4px 0 0 0;
      font-size: 0.8em;
      color: #4b5563;
      font-style: italic;
    }

    /* Multi-column MCQ Grid */
    .question-grid {
      column-count: var(--paper-cols);
      column-gap: 18px;
      column-rule: 1px solid #e5e7eb;
    }
    .question-item {
      break-inside: avoid;
      page-break-inside: avoid;
      margin-bottom: 9px;
      padding-bottom: 6px;
      border-bottom: 1px dashed #e5e7eb;
    }
    .q-stem {
      margin: 0 0 4px 0;
      font-weight: 600;
      color: #111827;
    }
    .board-tag {
      font-size: 0.82em;
      font-weight: 500;
      color: #475569;
      margin-left: 3px;
    }
    body.hide-board-tags .board-tag { display: none; }
    body.hide-omr .omr-bubble { display: none; }

    .complex-subs {
      padding-left: 14px;
      margin: 2px 0 3px 0;
      font-size: 0.95em;
    }
    .final-prompt {
      font-weight: 600;
      margin-bottom: 4px;
      font-size: 0.95em;
    }
    .options-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 2px 8px;
    }
    .opt-item {
      display: flex;
      align-items: flex-start;
      gap: 4px;
      font-size: 0.95em;
    }
    .opt-correct {
      font-weight: 700;
      color: #065f46;
    }
    .omr-bubble {
      display: inline-block;
      flex: 0 0 auto;
      width: 12px;
      height: 12px;
      border: 1.4px solid #1f2937;
      border-radius: 50%;
      margin-top: 3px;
    }
    .omr-bubble.filled {
      background: #059669;
      border-color: #059669;
    }

    /* Legacy Math Fractions */
    .frac {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      vertical-align: middle;
      margin: 0 2px;
      font-size: 0.85em;
      line-height: 1.05;
    }
    .frac-num {
      border-bottom: 1px solid currentColor;
      padding: 0 3px 1px 3px;
    }
    .frac-den { padding: 1px 3px 0 3px; }

    /* SQ & CQ Sections */
    .section-block {
      margin-top: 16px;
      padding-top: 10px;
      border-top: 1.5px solid #111827;
    }
    .section-heading {
      text-align: center;
      margin-bottom: 10px;
    }
    .section-heading h3 {
      margin: 0;
      font-size: 1.15em;
      font-weight: 700;
    }
    .section-heading p {
      margin: 2px 0 0 0;
      font-size: 0.9em;
      color: #475569;
    }
    .sq-item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
      break-inside: avoid;
    }
    .sq-mark, .cq-part-mark { font-weight: 700; flex: 0 0 auto; }
    .cq-item {
      margin-bottom: 12px;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .cq-stem {
      background: #f8fafc;
      border-left: 3px solid #334155;
      padding: 6px 9px;
      margin-bottom: 5px;
    }
    .cq-part {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding-left: 16px;
      margin-bottom: 3px;
    }

    /* Answer Key & Solutions Tab */
    .ans-title-pill {
      color: #1d4ed8;
      text-decoration: underline;
      font-weight: 700;
    }
    .quick-key-box {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 14px;
    }
    .quick-key-box h4 {
      margin: 0 0 8px 0;
      text-align: center;
      font-size: 0.95em;
    }
    .quick-key-grid {
      display: grid;
      grid-template-columns: repeat(10, minmax(0, 1fr));
      gap: 5px;
      text-align: center;
      font-size: 0.85em;
      font-weight: 600;
    }
    .quick-key-cell {
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      padding: 3px 4px;
    }
    .ans-section-title {
      margin: 0 0 8px 0;
      font-size: 1em;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 4px;
    }
    .answer-grid {
      column-count: 2;
      column-gap: 16px;
    }
    .answer-item {
      break-inside: avoid;
      page-break-inside: avoid;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 6px 8px;
      margin-bottom: 7px;
      font-size: 0.92em;
    }
    .ans-badge {
      font-weight: 700;
      color: #1e40af;
    }
    .muted-note { color: #64748b; font-style: italic; }

    @media (max-width: 768px) {
      .question-grid, .answer-grid { column-count: 1; }
      .quick-key-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    }

    @media print {
      @page {
        size: ${pageSizeCss};
        margin: ${studio.marginMm}mm;
      }
      body {
        background: #ffffff !important;
        padding: 0 !important;
      }
      .no-print { display: none !important; }
      .print-page {
        box-shadow: none !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        min-height: auto !important;
        width: 100% !important;
      }
      .question-grid {
        column-count: var(--paper-cols) !important;
      }
      .answer-grid {
        column-count: 2 !important;
      }
      .quick-key-grid {
        grid-template-columns: repeat(10, minmax(0, 1fr)) !important;
      }
    }
  </style>
</head>
<body class="${!studio.omrStyle ? 'hide-omr ' : ''}${!studio.showBoardTags ? 'hide-board-tags' : ''}">

${opts.printOnly ? '' : `
  <header class="no-print studio-toolbar">
    <div class="toolbar-top">
      <div class="toolbar-brand">
        <h1>${escapeHtml(opts.paperConfig.title || 'প্রশ্নপত্র স্টুডিও')}</h1>
        <p>${toBengaliNumeral(totalMcq)}টি নৈর্ব্যক্তিক প্রশ্ন | পূর্ণমান: ${bnMarks} | সময়: ${bnTime} মিনিট</p>
      </div>
      <div class="toolbar-actions">
        <a href="/dashboard" class="st-btn">ড্যাশবোর্ড</a>
        <button type="button" class="st-btn${activeTab === 'questions' ? ' active' : ''}" data-tab-btn="questions">প্রশ্নপত্র</button>
        ${opts.canViewTeacherCopy ? `
        <button type="button" class="st-btn${activeTab === 'answers' ? ' active' : ''}" data-tab-btn="answers">উত্তরমালা ও সমাধান</button>
        <button type="button" class="st-btn${activeTab === 'teacher' ? ' active' : ''}" data-tab-btn="teacher">শিক্ষক কপি (OMR)</button>
        ` : ''}
        <button type="button" class="st-btn emerald" id="btnPrintQuestions">প্রশ্নপত্র PDF</button>
        ${opts.canViewTeacherCopy ? `<button type="button" class="st-btn indigo" id="btnPrintAnswers">উত্তরমালা PDF</button>` : ''}
        <button type="button" class="st-btn amber" id="btnDownloadDocx">DOCX ডাউনলোড</button>
        ${opts.paperId && opts.hasBrowserPdf ? `<a class="st-btn" id="btnServerPdf" href="/api/papers/${opts.paperId}/pdf?copy=student">সার্ভার PDF</a>` : ''}
        <button type="button" class="st-btn" id="btnToggleCustomize">কাস্টমাইজ</button>
      </div>
    </div>

    <div class="studio-drawer hidden" id="studioDrawer">
      <div class="ctrl-group">
        <label>বাংলা ফন্ট</label>
        <select id="ctrlFont">
          <option value="hind"${studio.font === 'hind' ? ' selected' : ''}>Hind Siliguri (আধুনিক)</option>
          <option value="noto"${studio.font === 'noto' ? ' selected' : ''}>Noto Sans Bengali</option>
          <option value="tiro"${studio.font === 'tiro' ? ' selected' : ''}>Tiro Bangla (বই স্টাইল)</option>
          <option value="kalpurush"${studio.font === 'kalpurush' ? ' selected' : ''}>Kalpurush / SolaimanLipi</option>
        </select>
      </div>
      <div class="ctrl-group">
        <label>কলাম সংখ্যা (MCQ)</label>
        <select id="ctrlCols">
          <option value="1"${studio.columns === 1 ? ' selected' : ''}>১ কলাম</option>
          <option value="2"${studio.columns === 2 ? ' selected' : ''}>২ কলাম (বোর্ড স্ট্যান্ডার্ড)</option>
          <option value="3"${studio.columns === 3 ? ' selected' : ''}>৩ কলাম (পেপার সেভার)</option>
        </select>
      </div>
      <div class="ctrl-group">
        <label>হেডার স্টাইল</label>
        <select id="ctrlHeaderPreset">
          <option value="board"${studio.headerPreset === 'board' ? ' selected' : ''}>বোর্ড স্ট্যান্ডার্ড</option>
          <option value="coaching"${studio.headerPreset === 'coaching' ? ' selected' : ''}>কোচিং মডেল টেস্ট</option>
          <option value="minimal"${studio.headerPreset === 'minimal' ? ' selected' : ''}>মিনিমাল</option>
        </select>
      </div>
      <div class="ctrl-group">
        <label>ফন্ট সাইজ (<span id="lblFontSize">${studio.fontSizePx}</span>px)</label>
        <input type="range" id="ctrlFontSize" min="9.5" max="14" step="0.5" value="${studio.fontSizePx}">
      </div>
      <div class="ctrl-group">
        <label>মার্জিন (<span id="lblMargin">${studio.marginMm}</span>mm)</label>
        <input type="range" id="ctrlMargin" min="8" max="20" step="1" value="${studio.marginMm}">
      </div>
      <div class="ctrl-group">
        <label>প্রতিষ্ঠানের নাম</label>
        <input type="text" id="ctrlInstName" value="${escapeHtml(studio.instituteName)}" placeholder="যেমন: উদয়ন কোচিং সেন্টার">
      </div>
      <div class="ctrl-group">
        <label>উপশিরোনাম / ঠিকানা</label>
        <input type="text" id="ctrlInstSub" value="${escapeHtml(studio.instituteSubtitle)}" placeholder="মিরপুর, ঢাকা">
      </div>
      <div class="ctrl-group">
        <label>ওয়াটারমার্ক টেক্সট</label>
        <input type="text" id="ctrlWatermark" value="${escapeHtml(studio.watermarkText)}" placeholder="Prosno.io / Coaching">
      </div>
      <div class="ctrl-group">
        <label>লোগো URL</label>
        <input type="text" id="ctrlLogoUrl" value="${escapeHtml(studio.logoUrl)}" placeholder="https://.../logo.png">
      </div>
      <div class="ctrl-group" style="justify-content:flex-end;">
        <label class="ctrl-row"><input type="checkbox" id="ctrlOmr"${studio.omrStyle ? ' checked' : ''}> OMR বৃত্ত দেখান</label>
        <label class="ctrl-row"><input type="checkbox" id="ctrlBoardTags"${studio.showBoardTags ? ' checked' : ''}> বোর্ড ও সাল ট্যাগ</label>
      </div>
      ${opts.canEditConfig && opts.paperId ? `
      <div class="ctrl-group" style="justify-content:flex-end;">
        <button type="button" class="st-btn emerald" id="btnSaveStudio">সেটিংস সেভ করুন</button>
        <span id="saveStudioStatus" style="font-size:11px;color:#059669;"></span>
      </div>` : ''}
    </div>
  </header>
`}

  <!-- TAB 1: STUDENT QUESTION PAPER -->
  <main id="section-questions" class="print-page${activeTab === 'questions' ? '' : ' hidden'}">
    <div class="watermark-layer"><div class="watermark-text" data-wm>${escapeHtml(studio.watermarkText)}</div></div>
    <div class="sheet-inner">
      ${headerHtml('বহুনির্বাচনি / প্রশ্নপত্র')}
      <div class="question-grid">${studentQuestionsHtml}</div>
      ${sqHtml}
      ${cqHtml}
    </div>
  </main>

  ${opts.canViewTeacherCopy ? `
  <!-- TAB 2: ANSWER KEY & SOLUTIONS -->
  <main id="section-answers" class="print-page${activeTab === 'answers' ? '' : ' hidden'}">
    <div class="watermark-layer"><div class="watermark-text" data-wm>${escapeHtml(studio.watermarkText)}</div></div>
    <div class="sheet-inner">
      ${answersHtml}
    </div>
  </main>

  <!-- TAB 3: TEACHER MARKED COPY -->
  <main id="section-teacher" class="print-page${activeTab === 'teacher' ? '' : ' hidden'}">
    <div class="watermark-layer"><div class="watermark-text" data-wm>${escapeHtml(studio.watermarkText)}</div></div>
    <div class="sheet-inner">
      ${headerHtml('শিক্ষক কপি (উত্তরসহ)')}
      <div class="question-grid">${teacherQuestionsHtml}</div>
      ${sqHtml}
      ${cqHtml}
    </div>
  </main>
  ` : ''}

  <script id="paper-data" type="application/json">${serializedData}</script>
  <script type="module" src="/dist/print-studio.js"></script>
</body>
</html>`;
}
