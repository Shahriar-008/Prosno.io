import type { OmrBubbleSize, OmrConfig, OmrHeaderMode, OmrSheetVariant, OmrThemeColor } from '../types';
import { toBengaliNumeral } from '../lib/bengali';
import { escapeHtml } from '../lib/math';

export const PAGE_WIDTH_MM = 215.9;
export const PAGE_HEIGHT_MM = 279.4;
export const SUPPORTED_QUESTION_COUNTS = [40, 60, 80, 100] as const;
export const SUPPORTED_GENERAL_COLUMNS = [1, 2, 3, 4] as const;
export const GENERAL_MAX_QUESTIONS_BY_COLUMN: Record<number, number> = {
  1: 100,
  2: 50,
  3: 75,
  4: 100,
};

export const THEME_COLORS: Record<OmrThemeColor, { label: string; hex: string }> = {
  rose: { label: 'Rose', hex: '#f03858' },
  slate: { label: 'Slate', hex: '#8b95a7' },
  blue: { label: 'Blue', hex: '#5d8ee6' },
  green: { label: 'Green', hex: '#46c56d' },
  violet: { label: 'Violet', hex: '#8f68e8' },
  orange: { label: 'Orange', hex: '#ff8a3d' },
  pink: { label: 'Pink', hex: '#de63a5' },
  gold: { label: 'Gold', hex: '#efbd34' },
};

export const BUBBLE_SIZE_PRESETS: Record<OmrBubbleSize, { label: string; diameter_mm: number; font_size: number }> = {
  small: { label: 'Small', diameter_mm: 3.1, font_size: 4.8 },
  large: { label: 'Large', diameter_mm: 3.55, font_size: 5.3 },
};

const ANSWER_OPTION_LABELS = ['ক', 'খ', 'গ', 'ঘ'] as const;
const SET_CODE_LABELS = ['ক', 'খ', 'গ', 'ঘ', 'ঙ'] as const;
const HEADER_WARNING_TEXT = 'এই বক্সে কোনো দাগ দেওয়া যাবে না';
const MANUAL_HEADER_LABELS = ['প্রতিষ্ঠান', 'পরীক্ষার নাম', 'উপশিরোনাম'] as const;
const GENERAL_FIELD_ROWS = [['নাম'], ['শ্রেণি', 'সেকশন'], ['বিষয়', 'রোল']];
const INSTITUTIONAL_SURFACE_HEX = '#f8f8f8';
const INSTITUTIONAL_STRIPE_HEX = '#f8b8c0';
const INSTITUTIONAL_BUBBLE_STROKE_HEX = '#7b7b86';
const INSTITUTIONAL_BUBBLE_TEXT_HEX = '#3f3f46';

export function getDefaultOmrConfig(): OmrConfig {
  return {
    template_type: 'exam_sheet_v1',
    sheet_variant: 'institutional',
    question_count: 100,
    answer_columns: 4,
    theme_color: 'rose',
    bubble_size: 'large',
    header_mode: 'digital',
    header: {
      title: '',
      subtitle: '',
      institution: '',
    },
    fields: {
      roll: true,
      set_code: true,
      subject_code: true,
    },
    instructions: [
      'একটি মাত্র বৃত্ত পূরণ করুন।',
      'কালো বা নীল কলম ব্যবহার করুন।',
      'ভুল চিহ্ন দিলে তা সম্পূর্ণভাবে মুছে ফেলুন।',
      'ভাঁজ বা দাগ ছাড়া পরিষ্কার কাগজ জমা দিন।',
    ],
  };
}

interface InstitutionalPreset {
  question_count: number;
  pattern: string;
  answer_y_mm: number;
  header_height_mm: number;
  row_height_mm: number;
  questions_per_column: number[];
  side_marker_y_mm: number;
  bottom_marker_y_mm: number;
  title_y_mm: number;
}

const INSTITUTIONAL_PRESETS: Record<number, InstitutionalPreset> = {
  40: {
    question_count: 40,
    pattern: 'obbbobbbobbbbbbooobb',
    answer_y_mm: 111.887,
    header_height_mm: 6.223,
    row_height_mm: 5.715,
    questions_per_column: [10, 10, 10, 10],
    side_marker_y_mm: 72.517,
    bottom_marker_y_mm: 165.481,
    title_y_mm: 104.775,
  },
  60: {
    question_count: 60,
    pattern: 'obboobbbobbobobbbbbb',
    answer_y_mm: 111.887,
    header_height_mm: 6.223,
    row_height_mm: 5.715,
    questions_per_column: [15, 15, 15, 15],
    side_marker_y_mm: 86.995,
    bottom_marker_y_mm: 194.183,
    title_y_mm: 104.775,
  },
  80: {
    question_count: 80,
    pattern: 'bbobbbobobboobbbbobb',
    answer_y_mm: 111.887,
    header_height_mm: 6.223,
    row_height_mm: 5.715,
    questions_per_column: [20, 20, 20, 20],
    side_marker_y_mm: 101.219,
    bottom_marker_y_mm: 222.758,
    title_y_mm: 104.775,
  },
  100: {
    question_count: 100,
    pattern: 'obbbobbbbbboboboobbb',
    answer_y_mm: 111.887,
    header_height_mm: 6.223,
    row_height_mm: 5.715,
    questions_per_column: [25, 25, 25, 25],
    side_marker_y_mm: 115.697,
    bottom_marker_y_mm: 251.46,
    title_y_mm: 104.775,
  },
};

const GENERAL_COLUMN_LAYOUTS: Record<
  number,
  {
    x_mm: number;
    column_width_mm: number;
    column_gap_mm: number;
    header_height_mm: number;
    number_width_mm: number;
    max_row_height_mm: number;
  }
> = {
  1: { x_mm: 52, column_width_mm: 106, column_gap_mm: 0, header_height_mm: 8.6, number_width_mm: 16.5, max_row_height_mm: 13.2 },
  2: { x_mm: 35, column_width_mm: 67, column_gap_mm: 6, header_height_mm: 8.2, number_width_mm: 13.2, max_row_height_mm: 10.2 },
  3: { x_mm: 25, column_width_mm: 50, column_gap_mm: 5, header_height_mm: 7.6, number_width_mm: 11, max_row_height_mm: 8.4 },
  4: { x_mm: 13, column_width_mm: 43, column_gap_mm: 4, header_height_mm: 7.1, number_width_mm: 9.4, max_row_height_mm: 6.45 },
};

export function normalizeOmrTemplateConfig(rawInput: unknown): OmrConfig {
  const raw = rawInput === null || rawInput === undefined ? {} : rawInput;
  if (typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('OMR config must be a JSON object.');
  }
  const obj = raw as Record<string, unknown>;
  const cfg = getDefaultOmrConfig();

  const rawType = obj.template_type ?? cfg.template_type;
  if (rawType !== 'exam_sheet_v1') {
    throw new Error('Unsupported OMR template type.');
  }

  const sheetVariant = String(obj.sheet_variant ?? cfg.sheet_variant).trim().toLowerCase();
  if (sheetVariant !== 'institutional' && sheetVariant !== 'general') {
    throw new Error('OMR sheet variant is not supported.');
  }
  cfg.sheet_variant = sheetVariant as OmrSheetVariant;

  const qCount = Number(obj.question_count ?? cfg.question_count);
  if (!Number.isInteger(qCount)) {
    throw new Error('Question count must be a number.');
  }
  if (cfg.sheet_variant === 'general') {
    if (qCount < 1 || qCount > 100) {
      throw new Error('Question count must be between 1 and 100 for General Normal OMR.');
    }
  } else if (![40, 60, 80, 100].includes(qCount)) {
    throw new Error('Question count must be one of 40, 60, 80, or 100.');
  }
  cfg.question_count = qCount;

  const rawCols = obj.answer_columns ?? (cfg.sheet_variant === 'general' ? 1 : cfg.answer_columns);
  const cols = Number(rawCols);
  if (!Number.isInteger(cols)) {
    throw new Error('Column count must be a number.');
  }
  if (cfg.sheet_variant === 'general') {
    if (![1, 2, 3, 4].includes(cols)) {
      throw new Error('General Normal OMR supports auto flow plus 2, 3, or 4 answer columns.');
    }
    const maxQ = GENERAL_MAX_QUESTIONS_BY_COLUMN[cols];
    if (qCount > maxQ) {
      throw new Error(
        cols === 1
          ? `Auto flow supports up to ${maxQ} questions on General Normal OMR.`
          : `${cols} columns support up to ${maxQ} questions on General Normal OMR.`
      );
    }
    cfg.answer_columns = cols;
  } else {
    cfg.answer_columns = 4;
  }

  const themeColor = String(obj.theme_color ?? cfg.theme_color).trim().toLowerCase() as OmrThemeColor;
  if (!(themeColor in THEME_COLORS)) {
    throw new Error('Theme color is not supported.');
  }
  cfg.theme_color = themeColor;

  const bubbleSize = String(obj.bubble_size ?? cfg.bubble_size).trim().toLowerCase();
  if (bubbleSize !== 'small' && bubbleSize !== 'large') {
    throw new Error("Bubble size must be 'small' or 'large'.");
  }
  cfg.bubble_size = bubbleSize as OmrBubbleSize;

  const headerMode = String(obj.header_mode ?? cfg.header_mode).trim().toLowerCase();
  if (headerMode !== 'digital' && headerMode !== 'manual') {
    throw new Error("Header mode must be 'digital' or 'manual'.");
  }
  cfg.header_mode = headerMode as OmrHeaderMode;

  const rawHeader = (obj.header ?? {}) as Record<string, unknown>;
  if (typeof rawHeader !== 'object' || Array.isArray(rawHeader)) {
    throw new Error('Header must be an object.');
  }
  const limits: Record<'title' | 'subtitle' | 'institution', number> = {
    title: 80,
    subtitle: 120,
    institution: 120,
  };
  for (const key of ['title', 'subtitle', 'institution'] as const) {
    const val = String(rawHeader[key] ?? cfg.header[key]).trim();
    if (val.length > limits[key]) {
      throw new Error(`Header ${key} is too long (max ${limits[key]} characters).`);
    }
    cfg.header[key] = val;
  }

  const rawFields = (obj.fields ?? {}) as Record<string, unknown>;
  if (typeof rawFields !== 'object' || Array.isArray(rawFields)) {
    throw new Error('Fields must be an object.');
  }
  for (const key of ['roll', 'set_code', 'subject_code'] as const) {
    cfg.fields[key] = Boolean(rawFields[key] ?? cfg.fields[key]);
  }
  if (!cfg.fields.roll && !cfg.fields.set_code && !cfg.fields.subject_code) {
    throw new Error('At least one student info field must stay enabled.');
  }

  let rawInstructions = obj.instructions ?? cfg.instructions;
  if (typeof rawInstructions === 'string') {
    rawInstructions = rawInstructions.split(/\r?\n/).map((s) => s.trim());
  }
  if (!Array.isArray(rawInstructions)) {
    throw new Error('Instructions must be a list of strings.');
  }
  const cleaned: string[] = [];
  for (const item of rawInstructions) {
    if (item === null || item === undefined) continue;
    const t = String(item).trim();
    if (!t) continue;
    if (t.length > 140) throw new Error('Each instruction must be 140 characters or less.');
    cleaned.push(t);
  }
  cfg.instructions = (cleaned.length > 0 ? cleaned : cfg.instructions).slice(0, 6);

  return cfg;
}

function boxMm(x: number, y: number, w: number, h: number): string {
  return `left:${x}mm;top:${y}mm;width:${w}mm;height:${h}mm;`;
}

function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function renderBubble(label: string): string {
  return `<span class="bubble"><span class="bubble-label">${escapeHtml(label)}</span></span>`;
}

function cornerMarkerSvg(style: string): string {
  const pieces = ['<rect width="100" height="100" fill="#101010"></rect>'];
  if (style === 'top_left') {
    pieces.push('<rect x="30" y="30" width="40" height="40" fill="#ffffff"></rect>');
  } else if (style === 'top_right') {
    pieces.push(
      '<rect x="16" y="18" width="66" height="15" fill="#ffffff"></rect>',
      '<rect x="16" y="18" width="15" height="57" fill="#ffffff"></rect>',
      '<rect x="67" y="18" width="15" height="72" fill="#ffffff"></rect>'
    );
  } else if (style === 'bottom_left') {
    pieces.push(
      '<rect x="16" y="70" width="66" height="15" fill="#ffffff"></rect>',
      '<rect x="16" y="24" width="15" height="61" fill="#ffffff"></rect>',
      '<rect x="67" y="46" width="15" height="39" fill="#ffffff"></rect>'
    );
  } else if (style === 'bottom_right') {
    pieces.push(
      '<rect x="62" y="18" width="15" height="70" fill="#ffffff"></rect>',
      '<rect x="28" y="48" width="49" height="15" fill="#ffffff"></rect>',
      '<rect x="18" y="76" width="18" height="18" fill="#ffffff"></rect>'
    );
  } else {
    pieces.push(
      '<rect x="26" y="26" width="48" height="15" fill="#ffffff"></rect>',
      '<rect x="26" y="26" width="15" height="48" fill="#ffffff"></rect>'
    );
  }
  return `<svg viewBox="0 0 100 100" aria-hidden="true">${pieces.join('')}</svg>`;
}

function buildGeneralColumnCounts(qCount: number, cols: number): number[] {
  if (cols === 1) {
    const counts: number[] = [];
    let rem = qCount;
    while (rem > 0) {
      const take = Math.min(25, rem);
      counts.push(take);
      rem -= take;
    }
    return counts;
  }
  const base = Math.floor(qCount / cols);
  const rem = qCount % cols;
  return Array.from({ length: cols }, (_, i) => base + (i < rem ? 1 : 0));
}

function renderMatrixPanel(params: {
  title: string;
  xMm: number;
  yMm: number;
  wMm: number;
  hMm: number;
  labels: string[];
  columns: number;
  shadeAlt: boolean;
  hasWriteRow: boolean;
}): string {
  const rows = params.labels.length + (params.hasWriteRow ? 1 : 0);
  const cells: string[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < params.columns; c++) {
      if (params.hasWriteRow && r === 0) {
        cells.push('<div class="matrix-cell"></div>');
        continue;
      }
      const lIdx = params.hasWriteRow ? r - 1 : r;
      const rawLabel = params.labels[lIdx] || '';
      const display = /^\d+$/.test(rawLabel) ? toBengaliNumeral(rawLabel) : rawLabel;
      const bg = params.shadeAlt && c % 2 === 0 ? `background:${INSTITUTIONAL_STRIPE_HEX};` : '';
      cells.push(`<div class="matrix-cell" style="${bg}">${renderBubble(display)}</div>`);
    }
  }
  return `<div class="box panel" style="${boxMm(params.xMm, params.yMm, params.wMm, params.hMm)}">
    <div class="panel-title">${escapeHtml(params.title)}</div>
    <div class="matrix" style="grid-template-columns:repeat(${params.columns},1fr);grid-template-rows:repeat(${rows},1fr);">${cells.join('')}</div>
  </div>`;
}

export function buildOmrHtml(rawConfig: OmrConfig, autoprint = false): string {
  const cfg = normalizeOmrTemplateConfig(rawConfig);
  const accent = THEME_COLORS[cfg.theme_color].hex;
  const accentSoft = hexToRgba(accent, 0.16);
  const bubblePreset = BUBBLE_SIZE_PRESETS[cfg.bubble_size];

  const blocks: string[] = [];

  if (cfg.sheet_variant === 'general') {
    // General corner markers
    const genMarkers = [
      { x: 2.5, y: 12, s: 'top_left' },
      { x: 197.5, y: 12, s: 'top_right' },
      { x: 2.5, y: 148, s: 'top_left' },
      { x: 197.5, y: 148, s: 'top_right' },
      { x: 2.5, y: 279, s: 'bottom_left' },
      { x: 197.5, y: 279, s: 'bottom_right' },
    ];
    for (const m of genMarkers) {
      blocks.push(`<div class="box marker" style="${boxMm(m.x, m.y, 10, 10)}">${cornerMarkerSvg(m.s)}</div>`);
    }

    // Header
    blocks.push(`<div class="box general-header" style="${boxMm(18, 12, 174, 20)}">
      ${cfg.header.title ? `<h1>${escapeHtml(cfg.header.title)}</h1>` : ''}
      ${cfg.header.subtitle ? `<p>${escapeHtml(cfg.header.subtitle)}</p>` : ''}
      ${cfg.header.institution ? `<p>${escapeHtml(cfg.header.institution)}</p>` : ''}
      <div class="general-divider"></div>
    </div>`);

    // Identity lines
    const rowsMarkup = GENERAL_FIELD_ROWS.map(
      (row) =>
        `<div class="general-row">${row
          .map((lbl) => `<div class="general-field"><strong>${lbl} :</strong><span class="rule"></span></div>`)
          .join('')}</div>`
    ).join('');
    blocks.push(`<div class="box general-form" style="${boxMm(18, 40, 174, 28)}">${rowsMarkup}</div>`);

    // Answer Grid
    const counts = buildGeneralColumnCounts(cfg.question_count, cfg.answer_columns);
    const renderCols = counts.length;
    const rows = Math.max(...counts);
    const spec = GENERAL_COLUMN_LAYOUTS[renderCols];
    const gridY = 102;
    const availH = 270 - gridY - spec.header_height_mm;
    const rowH = Number(Math.min(spec.max_row_height_mm, availH / rows).toFixed(2));
    const frameW = renderCols * spec.column_width_mm + (renderCols - 1) * spec.column_gap_mm;
    const frameH = 5.2 + rows * rowH;

    blocks.push(`<div class="box answer-title" style="${boxMm(40, gridY - 13, 130, 8)}">সাধারণ বহুনির্বাচনি উত্তরপত্র</div>`);
    blocks.push(`<div class="box general-answer-frame" style="${boxMm(spec.x_mm, gridY, frameW, frameH)}"></div>`);

    const markerOffsets = [2.1, frameW * 0.23, frameW * 0.29, frameW * 0.49, frameW - 10.2, frameW - 5.0];
    for (const off of markerOffsets) {
      blocks.push(`<div class="box general-answer-marker" style="${boxMm(spec.x_mm + off, gridY + 1.1, 2.8, 2.8)}"></div>`);
    }

    const qWidthPct = (spec.number_width_mm / spec.column_width_mm) * 100;
    let nextNum = 1;
    for (let c = 0; c < renderCols; c++) {
      const actualRows = counts[c];
      const colX = spec.x_mm + c * (spec.column_width_mm + spec.column_gap_mm);
      const colY = gridY + 5.2;
      const rowsHtml: string[] = [];
      for (let r = 0; r < actualRows; r++) {
        const num = nextNum + r;
        const optHtml = ANSWER_OPTION_LABELS.map((l) => `<span class="answer-option">${renderBubble(l)}</span>`).join('');
        rowsHtml.push(
          `<div class="general-answer-row"><span class="general-answer-qnum" style="width:${qWidthPct.toFixed(4)}%">${toBengaliNumeral(num)}</span><div class="general-answer-options">${optHtml}</div></div>`
        );
      }
      blocks.push(
        `<div class="box general-answer-column" style="${boxMm(colX, colY, spec.column_width_mm, actualRows * rowH)}">
          <div class="answer-rows" style="height:${actualRows * rowH}mm;grid-template-rows:repeat(${actualRows},${rowH}mm);">${rowsHtml.join('')}</div>
        </div>`
      );
      nextNum += actualRows;
    }
  } else {
    const preset = INSTITUTIONAL_PRESETS[cfg.question_count];
    // Corner markers
    const corners = [
      { x: 14.732, y: 4.953, s: 'top_left' },
      { x: 191.77, y: 4.953, s: 'top_right' },
      { x: 14.732, y: preset.bottom_marker_y_mm, s: 'bottom_left' },
      { x: 191.77, y: preset.bottom_marker_y_mm, s: 'bottom_right' },
    ];
    for (const m of corners) {
      blocks.push(`<div class="box marker" style="${boxMm(m.x, m.y, 10, 10)}">${cornerMarkerSvg(m.s)}</div>`);
    }

    // Side marker bars
    for (const sideX of [14.732, 195.834]) {
      for (let idx = 0; idx < 5; idx++) {
        const barY = preset.side_marker_y_mm + idx * (2.921 + 0.635);
        blocks.push(`<div class="box marker-bar" style="${boxMm(sideX, barY, 5.969, 2.921)}"></div>`);
      }
    }

    // Header box + top pattern
    const hx = 25.908;
    const hy = 4.953;
    const hw = 164.592;
    const hh = 10;
    blocks.push(`<div class="box institutional-header" style="${boxMm(hx, hy, hw, hh)}"></div>`);
    blocks.push(`<div class="box institutional-warning" style="${boxMm(hx + 2.5, hy + 0.72, hw - 5, 3.4)}">${HEADER_WARNING_TEXT}</div>`);

    const items = preset.pattern.split('');
    const sqSize = 2.95;
    const circSize = 3.92;
    const gap = 1.05;
    const widths = items.map((t) => (t === 'o' ? circSize : sqSize));
    const totalPatW = widths.reduce((a, b) => a + b, 0) + Math.max(0, items.length - 1) * gap;
    let curX = 108.204 - totalPatW / 2;
    const centerY = hy + 5.08 + circSize / 2;
    items.forEach((t, idx) => {
      const sz = widths[idx];
      const cls = t === 'o' ? 'circle' : 'square';
      blocks.push(`<div class="box top-pattern-item ${cls}" style="${boxMm(curX, centerY - sz / 2, sz, sz)}"></div>`);
      curX += sz + gap;
    });

    if (cfg.header_mode === 'manual') {
      const lx = hx + 4.2;
      const lw = hw - 8.4;
      MANUAL_HEADER_LABELS.forEach((lbl, i) => {
        const ry = hy + 4.7 + i * 2.2;
        blocks.push(`<div class="box manual-header" style="${boxMm(lx, ry - 1.05, lw, 2.2)}"><strong class="manual-line">${lbl}</strong><span class="rule"></span></div>`);
      });
    } else {
      const lines: Array<[string, string]> = [];
      if (cfg.header.title) lines.push([cfg.header.title, 'title']);
      if (cfg.header.subtitle) lines.push([cfg.header.subtitle, 'subtitle']);
      if (cfg.header.institution) lines.push([cfg.header.institution, 'institution']);
      if (lines.length > 0) {
        const cGap = lines.length > 1 ? 0.65 : 0;
        const lineH = Math.max(1.1, (3.8 - cGap * (lines.length - 1)) / lines.length);
        const copyMarkup = lines
          .map(([t, cls]) => `<div class="institutional-copy-line ${cls}" style="height:${lineH}mm;">${escapeHtml(t)}</div>`)
          .join('');
        blocks.push(`<div class="box institutional-copy" style="${boxMm(hx + 24, hy + 4.8, 116.6, 3.8)}gap:${cGap}mm;">${copyMarkup}</div>`);
      }
    }

    // Identity matrices
    blocks.push(
      renderMatrixPanel({
        title: 'শ্রেণি',
        xMm: 25.527,
        yMm: 35.941,
        wMm: 22.352,
        hMm: 58.547,
        labels: ['6', '7', '8', '9', '10', '11', '12'],
        columns: 1,
        shadeAlt: false,
        hasWriteRow: false,
      })
    );
    if (cfg.fields.roll) {
      blocks.push(
        renderMatrixPanel({
          title: 'রোল নম্বর',
          xMm: 50.419,
          yMm: 35.941,
          wMm: 45.339,
          hMm: 65.024,
          labels: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
          columns: 6,
          shadeAlt: true,
          hasWriteRow: true,
        })
      );
    }
    if (cfg.fields.subject_code) {
      blocks.push(
        renderMatrixPanel({
          title: 'বিষয় কোড',
          xMm: 98.298,
          yMm: 35.941,
          wMm: 22.987,
          hMm: 65.024,
          labels: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
          columns: 3,
          shadeAlt: true,
          hasWriteRow: true,
        })
      );
    }
    if (cfg.fields.set_code) {
      blocks.push(
        renderMatrixPanel({
          title: 'সেট কোড',
          xMm: 123.698,
          yMm: 35.941,
          wMm: 22.479,
          hMm: 52.578,
          labels: [...SET_CODE_LABELS],
          columns: 1,
          shadeAlt: false,
          hasWriteRow: true,
        })
      );
    }

    // Instructions & signature
    blocks.push(`<div class="box panel instructions" style="${boxMm(149.098, 35.941, 41.91, 41.402)}">
      <div class="panel-title">নির্দেশাবলী</div>
      <ol>${cfg.instructions.map((ins) => `<li>${escapeHtml(ins)}</li>`).join('')}</ol>
    </div>`);
    blocks.push(`<div class="box signature" style="${boxMm(149.098, 79.502, 41.91, 21.463)}">কক্ষ পরিদর্শকের স্বাক্ষর তারিখসহ</div>`);

    // Answer section
    blocks.push(`<div class="box answer-title" style="${boxMm(53.7, preset.title_y_mm, 109, 4.6)}">বহুনির্বাচনি অভীক্ষার উত্তরপত্র</div>`);
    const colW = 39.878;
    const colGap = 2.032;
    const numW = 9.4;
    const qWidthPct = (numW / colW) * 100;
    let nextNum = 1;
    preset.questions_per_column.forEach((actualRows, cIdx) => {
      const totalH = preset.header_height_mm + actualRows * preset.row_height_mm;
      const rowsHtml: string[] = [];
      for (let r = 0; r < actualRows; r++) {
        const qnum = toBengaliNumeral(nextNum + r);
        const optHtml = ANSWER_OPTION_LABELS.map((l) => `<span class="answer-option">${renderBubble(l)}</span>`).join('');
        rowsHtml.push(
          `<div class="answer-row"><span class="answer-qnum" style="width:${qWidthPct.toFixed(4)}%">${qnum}</span><div class="answer-options">${optHtml}</div></div>`
        );
      }
      const xMm = 25.527 + cIdx * (colW + colGap);
      blocks.push(
        `<div class="box answer-column" style="${boxMm(xMm, preset.answer_y_mm, colW, totalH)}">
          <div class="answer-header" style="height:${preset.header_height_mm}mm">
            <span class="question-head" style="width:${qWidthPct.toFixed(4)}%">প্রশ্ন</span>
            <span style="flex:1 1 0">উত্তর</span>
          </div>
          <div class="answer-rows" style="height:${actualRows * preset.row_height_mm}mm;grid-template-rows:repeat(${actualRows},${preset.row_height_mm}mm);">${rowsHtml.join('')}</div>
        </div>`
      );
      nextNum += actualRows;
    });
  }

  return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(cfg.header.title || 'Prosno.io OMR Sheet')}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    @page { size: ${PAGE_WIDTH_MM}mm ${PAGE_HEIGHT_MM}mm; margin: 0; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #e2e8f0;
      font-family: 'Noto Sans Bengali', sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .omr-toolbar {
      display: flex; justify-content: center; gap: 10px; padding: 10px;
      background: #0f172a; color: #fff;
    }
    .omr-toolbar button {
      padding: 7px 14px; border-radius: 6px; border: none; background: #10b981;
      color: #fff; font-weight: 700; cursor: pointer; font-family: inherit;
    }
    .omr-page {
      position: relative;
      width: ${PAGE_WIDTH_MM}mm;
      height: ${PAGE_HEIGHT_MM}mm;
      margin: 12px auto;
      background: ${INSTITUTIONAL_SURFACE_HEX};
      box-shadow: 0 8px 28px rgba(0,0,0,0.18);
    }
    .box { position: absolute; }
    .marker { display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .marker svg { display: block; width: 100%; height: 100%; }
    .marker-bar { background: #101010; }
    .institutional-header { background: ${accentSoft}; }
    .institutional-copy { display: flex; flex-direction: column; align-items: center; justify-content: flex-start; width: 100%; text-align: center; }
    .institutional-warning { display: flex; align-items: center; justify-content: center; color: #dc2626; font-size: 2.65mm; font-weight: 700; line-height: 1.02; text-align: center; }
    .top-pattern-item { background: #101010; }
    .top-pattern-item.circle { border: 0.45mm solid #101010; border-radius: 50%; background: transparent; }
    .institutional-copy-line { display: flex; align-items: center; justify-content: center; width: 100%; color: #09111d; line-height: 1.08; overflow: hidden; text-align: center; }
    .institutional-copy-line.title { font-size: 3.2mm; font-weight: 700; }
    .institutional-copy-line.subtitle { font-size: 2.26mm; font-weight: 700; }
    .institutional-copy-line.institution { font-size: 2.05mm; font-weight: 400; }
    .manual-header { display: flex; align-items: center; gap: 2mm; color: #111827; font-size: 2.12mm; font-weight: 700; }
    .manual-header .rule, .general-field .rule { display: block; height: 0.3mm; background: ${accent}; flex: 1; }
    .general-header { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #111827; }
    .general-header h1 { margin: 0; font-size: 6.5mm; font-weight: 700; }
    .general-header p { margin: 1mm 0 0; font-size: 3.2mm; font-weight: 600; }
    .general-divider { width: 70%; height: 0.3mm; margin-top: 3mm; background: rgba(15,23,42,0.25); }
    .general-form { display: flex; flex-direction: column; gap: 3mm; }
    .general-row { display: flex; gap: 4mm; align-items: center; }
    .general-field { display: grid; grid-template-columns: auto 1fr; gap: 2.4mm; align-items: center; flex: 1 1 0; color: #111827; font-size: 3.4mm; font-weight: 600; }
    .panel, .signature, .answer-column { border: 0.45mm solid ${accent}; background: #fff; }
    .panel-title { display: flex; align-items: center; justify-content: center; min-height: 4.45mm; padding: 1mm 1.5mm; border-bottom: 0.3mm solid ${accent}; background: #fff; color: #111827; font-size: 2.55mm; font-weight: 700; line-height: 1.02; }
    .instructions .panel-title { background: ${accent}; color: #fff; }
    .matrix { display: grid; width: 100%; height: calc(100% - 4.45mm); }
    .matrix-cell { display: flex; align-items: center; justify-content: center; border-right: 0.3mm solid ${accent}; border-bottom: 0.3mm solid ${accent}; background: #fff; }
    .instructions { overflow: hidden; background: #fff; }
    .instructions ol { margin: 0; padding: 1.4mm 2.8mm 2.2mm 5.4mm; color: #111827; font-size: 2.05mm; line-height: 1.28; }
    .signature { display: flex; align-items: center; justify-content: center; padding: 2mm; color: #111827; font-size: 2.45mm; text-align: center; line-height: 1.12; }
    .answer-title { display: flex; align-items: center; justify-content: center; color: #111827; font-size: 3.2mm; font-weight: 700; }
    .general-answer-frame { border: 0.55mm solid #1f2937; background: linear-gradient(180deg, rgba(15,23,42,0.03) 0%, rgba(255,255,255,0) 22%); }
    .general-answer-marker { background: #111827; border-radius: 0.35mm; }
    .general-answer-row { display: flex; border-bottom: 0.25mm solid rgba(15,23,42,0.14); }
    .general-answer-row:last-child { border-bottom: 0; }
    .general-answer-qnum { display: flex; align-items: center; justify-content: center; flex: 0 0 auto; color: #111827; font-weight: 700; font-size: 2.7mm; }
    .general-answer-options { display: grid; grid-template-columns: repeat(4, 1fr); flex: 1 1 0; place-items: center; }
    .answer-header { display: flex; align-items: stretch; background: #fff; color: #111827; font-size: 2.55mm; font-weight: 700; }
    .answer-header span, .answer-qnum, .answer-option { display: flex; align-items: center; justify-content: center; }
    .question-head, .answer-qnum { border-right: 0.3mm solid ${accent}; font-size: 2.2mm; }
    .answer-rows { display: grid; }
    .answer-row { display: flex; border-top: 0.3mm solid ${accent}; }
    .answer-options { display: grid; grid-template-columns: repeat(4, 1fr); flex: 1 1 0; place-items: center; background: ${INSTITUTIONAL_STRIPE_HEX}; }
    .bubble {
      display: inline-flex; align-items: center; justify-content: center; position: relative;
      width: ${bubblePreset.diameter_mm}mm; height: ${bubblePreset.diameter_mm}mm;
      border: 0.4mm solid ${INSTITUTIONAL_BUBBLE_STROKE_HEX}; border-radius: 50%; background: #fff;
      color: ${INSTITUTIONAL_BUBBLE_TEXT_HEX}; font-size: ${Math.max(2.5, bubblePreset.font_size * 0.62).toFixed(2)}mm; line-height: 1;
    }
    .bubble-label { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
    @media print {
      body { background: #fff !important; }
      .no-print { display: none !important; }
      .omr-page { margin: 0 !important; box-shadow: none !important; }
    }
  </style>
</head>
<body>
  <div class="no-print omr-toolbar">
    <button type="button" onclick="window.print()">প্রিন্ট / PDF সেভ করুন (1:1 Letter)</button>
  </div>
  <div class="omr-page">${blocks.join('')}</div>
  ${autoprint ? '<script>window.addEventListener("load",()=>setTimeout(()=>window.print(),350));</script>' : ''}
</body>
</html>`;
}
