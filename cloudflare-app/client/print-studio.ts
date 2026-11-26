import katex from 'katex';
import 'katex/dist/katex.min.css';
import {
  AlignmentType,
  Document,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  BorderStyle,
} from 'docx';

interface StudioPayload {
  paperId: number | null;
  questionSetId: number | null;
  paperConfig: {
    title: string;
    class_name?: string;
    subject_name?: string;
    time?: number;
    marks?: number;
  };
  studio: {
    font: 'hind' | 'noto' | 'tiro' | 'kalpurush';
    paperSize: 'a4' | 'legal';
    columns: 1 | 2 | 3;
    fontSizePx: number;
    marginMm: number;
    omrStyle: boolean;
    showBoardTags: boolean;
    headerPreset: 'board' | 'coaching' | 'minimal';
    instituteName: string;
    instituteSubtitle: string;
    logoUrl: string;
    watermarkText: string;
    watermarkOpacity: number;
  };
  questions: Array<{
    question_text: string;
    type?: string;
    sub_options?: string[];
    final_prompt?: string;
    answer_options: string[];
    correct_answer: string;
    explanation?: string;
  }>;
  sqConfig: {
    questions: Array<{ question_text: string; marks?: number }>;
    answer_count: number;
    marks_per_question: number;
  } | null;
  cqConfig: {
    questions: Array<{
      stem: string;
      part_ka?: string;
      part_kha?: string;
      part_ga?: string;
      part_gha?: string;
      marks_ka?: number;
      marks_kha?: number;
      marks_ga?: number;
      marks_gha?: number;
    }>;
    answer_count: number;
  } | null;
  canViewTeacherCopy: boolean;
  canEditConfig: boolean;
  autoprint: boolean;
}

const EN_TO_BN: Record<string, string> = {
  '0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
  '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯',
};

function bn(val: string | number): string {
  return String(val).replace(/[0-9]/g, (d) => EN_TO_BN[d] || d);
}

function renderKatexNodes(): void {
  const nodes = document.querySelectorAll<HTMLElement>('.math-tex');
  nodes.forEach((el) => {
    const tex = el.dataset.tex;
    if (!tex) return;
    const isDisplay = el.classList.contains('math-display');
    try {
      el.innerHTML = katex.renderToString(tex, {
        displayMode: isDisplay,
        throwOnError: false,
        strict: false,
      });
    } catch {
      // keep fallback text
    }
  });
}

function getFontStack(font: string): string {
  switch (font) {
    case 'noto':
      return "'Noto Sans Bengali', 'Hind Siliguri', sans-serif";
    case 'tiro':
      return "'Tiro Bangla', 'Hind Siliguri', serif";
    case 'kalpurush':
      return "'Kalpurush', 'SolaimanLipi', 'Noto Sans Bengali', sans-serif";
    default:
      return "'Hind Siliguri', 'Noto Sans Bengali', sans-serif";
  }
}

function showTab(tab: 'questions' | 'answers' | 'teacher'): void {
  const sections: Array<'questions' | 'answers' | 'teacher'> = ['questions', 'answers', 'teacher'];
  for (const s of sections) {
    const el = document.getElementById(`section-${s}`);
    if (el) el.classList.toggle('hidden', s !== tab);
    const btn = document.querySelector<HTMLButtonElement>(`[data-tab-btn="${s}"]`);
    if (btn) btn.classList.toggle('active', s === tab);
  }
}

async function generateAndDownloadDocx(payload: StudioPayload, showAnswer: boolean): Promise<void> {
  const prefixes = ['ক)', 'খ)', 'গ)', 'ঘ)'];
  const children: Array<Paragraph | Table> = [];
  const font = 'Nirmala UI';

  if (payload.studio.instituteName) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: payload.studio.instituteName, bold: true, size: 28, font })],
      })
    );
  }

  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: payload.paperConfig.title || 'Question Paper', bold: true, size: 26, font })],
    })
  );

  if (payload.paperConfig.subject_name || payload.paperConfig.class_name) {
    const subLine = [
      payload.paperConfig.subject_name ? `বিষয়: ${payload.paperConfig.subject_name}` : '',
      payload.paperConfig.class_name || '',
    ]
      .filter(Boolean)
      .join(' | ');
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: subLine, size: 20, font })],
      })
    );
  }

  const timeStr = `সময়— ${bn(payload.paperConfig.time ?? payload.questions.length)} মিনিট`;
  const marksStr = `পূর্ণমান— ${bn(payload.paperConfig.marks ?? payload.questions.length)}`;
  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 180 },
      children: [new TextRun({ text: `${timeStr}    |    ${marksStr}`, bold: true, size: 20, font })],
    })
  );

  const noBorders = {
    top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  };

  payload.questions.forEach((q, idx) => {
    const num = bn(idx + 1);
    children.push(
      new Paragraph({
        spacing: { before: 80, after: 40 },
        keepNext: true,
        children: [new TextRun({ text: `${num}. ${q.question_text}`, bold: true, size: 19, font })],
      })
    );

    if (q.type === 'complex' && Array.isArray(q.sub_options)) {
      q.sub_options.forEach((sub) => {
        children.push(
          new Paragraph({
            indent: { left: 320 },
            spacing: { after: 20 },
            keepNext: true,
            children: [new TextRun({ text: sub, size: 18, font })],
          })
        );
      });
      children.push(
        new Paragraph({
          spacing: { after: 40 },
          keepNext: true,
          children: [new TextRun({ text: q.final_prompt || 'নিচের কোনটি সঠিক?', bold: true, size: 18, font })],
        })
      );
    }

    const opts = q.answer_options || [];
    const correct = (q.correct_answer || '').trim();
    if (opts.length >= 4) {
      const makeCell = (i: number) => {
        const isCorrect = showAnswer && (opts[i] || '').trim() === correct;
        const circle = payload.studio.omrStyle ? (isCorrect ? '● ' : '◯ ') : '';
        return new TableCell({
          borders: noBorders,
          width: { size: 50, type: WidthType.PERCENTAGE },
          children: [
            new Paragraph({
              children: [
                new TextRun({
                  text: `${circle}${prefixes[i]} ${opts[i]}`,
                  bold: isCorrect,
                  size: 18,
                  font,
                }),
              ],
            }),
          ],
        });
      };
      children.push(
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          borders: noBorders,
          rows: [
            new TableRow({ children: [makeCell(0), makeCell(1)] }),
            new TableRow({ children: [makeCell(2), makeCell(3)] }),
          ],
        })
      );
    }
  });

  if (payload.sqConfig?.questions?.length) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 220, after: 80 },
        children: [new TextRun({ text: 'খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)', bold: true, size: 22, font })],
      })
    );
    payload.sqConfig.questions.forEach((sq, i) => {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [
            new TextRun({
              text: `${bn(i + 1)}। ${sq.question_text} [${bn(sq.marks ?? payload.sqConfig!.marks_per_question ?? 2)}]`,
              size: 19,
              font,
            }),
          ],
        })
      );
    });
  }

  if (payload.cqConfig?.questions?.length) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 220, after: 80 },
        children: [new TextRun({ text: 'গ-বিভাগ (সৃজনশীল প্রশ্ন)', bold: true, size: 22, font })],
      })
    );
    payload.cqConfig.questions.forEach((cq, i) => {
      children.push(
        new Paragraph({
          spacing: { before: 120, after: 40 },
          children: [new TextRun({ text: `${bn(i + 1)}। উদ্দীপক: ${cq.stem}`, bold: true, size: 19, font })],
        })
      );
      const parts: Array<[string | undefined, number | undefined, string]> = [
        [cq.part_ka, cq.marks_ka, 'ক'],
        [cq.part_kha, cq.marks_kha, 'খ'],
        [cq.part_ga, cq.marks_ga, 'গ'],
        [cq.part_gha, cq.marks_gha, 'ঘ'],
      ];
      for (const [text, m, lbl] of parts) {
        if (!text) continue;
        children.push(
          new Paragraph({
            indent: { left: 320 },
            spacing: { after: 30 },
            children: [new TextRun({ text: `${lbl}. ${text} [${bn(m ?? 0)}]`, size: 18, font })],
          })
        );
      }
    });
  }

  const doc = new Document({
    sections: [
      {
        properties: {
          page: {
            margin: { top: 720, bottom: 720, left: 900, right: 900 },
          },
        },
        children,
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const suffix = showAnswer ? 'Teacher' : 'Student';
  a.download = `${(payload.paperConfig.title || 'Prosno_Paper').replace(/\s+/g, '_')}_${suffix}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function initPrintStudio(): void {
  renderKatexNodes();

  const dataEl = document.getElementById('paper-data');
  if (!dataEl) return;

  let payload: StudioPayload;
  try {
    payload = JSON.parse(dataEl.textContent || '{}') as StudioPayload;
  } catch {
    return;
  }

  document.querySelectorAll<HTMLButtonElement>('[data-tab-btn]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tabBtn as 'questions' | 'answers' | 'teacher';
      if (target) showTab(target);
    });
  });

  const btnPrintQ = document.getElementById('btnPrintQuestions');
  btnPrintQ?.addEventListener('click', () => {
    showTab('questions');
    setTimeout(() => window.print(), 180);
  });

  const btnPrintA = document.getElementById('btnPrintAnswers');
  btnPrintA?.addEventListener('click', () => {
    showTab('answers');
    setTimeout(() => window.print(), 180);
  });

  const btnDocx = document.getElementById('btnDownloadDocx');
  btnDocx?.addEventListener('click', async () => {
    const activeTeacher = !document.getElementById('section-teacher')?.classList.contains('hidden');
    await generateAndDownloadDocx(payload, payload.canViewTeacherCopy && activeTeacher);
  });

  const drawer = document.getElementById('studioDrawer');
  const btnCustomize = document.getElementById('btnToggleCustomize');
  btnCustomize?.addEventListener('click', () => drawer?.classList.toggle('hidden'));

  const rootStyle = document.documentElement.style;
  const ctrlFont = document.getElementById('ctrlFont') as HTMLSelectElement | null;
  const ctrlCols = document.getElementById('ctrlCols') as HTMLSelectElement | null;
  const ctrlHeaderPreset = document.getElementById('ctrlHeaderPreset') as HTMLSelectElement | null;
  const ctrlFontSize = document.getElementById('ctrlFontSize') as HTMLInputElement | null;
  const ctrlMargin = document.getElementById('ctrlMargin') as HTMLInputElement | null;
  const ctrlInstName = document.getElementById('ctrlInstName') as HTMLInputElement | null;
  const ctrlInstSub = document.getElementById('ctrlInstSub') as HTMLInputElement | null;
  const ctrlWatermark = document.getElementById('ctrlWatermark') as HTMLInputElement | null;
  const ctrlLogoUrl = document.getElementById('ctrlLogoUrl') as HTMLInputElement | null;
  const ctrlOmr = document.getElementById('ctrlOmr') as HTMLInputElement | null;
  const ctrlBoardTags = document.getElementById('ctrlBoardTags') as HTMLInputElement | null;

  ctrlFont?.addEventListener('change', () => {
    payload.studio.font = ctrlFont.value as StudioPayload['studio']['font'];
    rootStyle.setProperty('--paper-font', getFontStack(payload.studio.font));
  });

  ctrlCols?.addEventListener('change', () => {
    payload.studio.columns = Number(ctrlCols.value) as 1 | 2 | 3;
    rootStyle.setProperty('--paper-cols', String(payload.studio.columns));
  });

  ctrlHeaderPreset?.addEventListener('change', () => {
    payload.studio.headerPreset = ctrlHeaderPreset.value as StudioPayload['studio']['headerPreset'];
    document.querySelectorAll('[data-paper-header]').forEach((h) => {
      h.classList.remove('preset-board', 'preset-coaching', 'preset-minimal');
      h.classList.add(`preset-${payload.studio.headerPreset}`);
    });
  });

  ctrlFontSize?.addEventListener('input', () => {
    payload.studio.fontSizePx = Number(ctrlFontSize.value);
    rootStyle.setProperty('--paper-font-size', `${payload.studio.fontSizePx}px`);
    const lbl = document.getElementById('lblFontSize');
    if (lbl) lbl.textContent = String(payload.studio.fontSizePx);
  });

  ctrlMargin?.addEventListener('input', () => {
    payload.studio.marginMm = Number(ctrlMargin.value);
    rootStyle.setProperty('--paper-margin', `${payload.studio.marginMm}mm`);
    const lbl = document.getElementById('lblMargin');
    if (lbl) lbl.textContent = String(payload.studio.marginMm);
  });

  ctrlInstName?.addEventListener('input', () => {
    payload.studio.instituteName = ctrlInstName.value;
    document.querySelectorAll<HTMLElement>('[data-el="instName"]').forEach((el) => {
      el.textContent = ctrlInstName.value;
      el.classList.toggle('hidden', !ctrlInstName.value.trim());
    });
  });

  ctrlInstSub?.addEventListener('input', () => {
    payload.studio.instituteSubtitle = ctrlInstSub.value;
    document.querySelectorAll<HTMLElement>('[data-el="instSubtitle"]').forEach((el) => {
      el.textContent = ctrlInstSub.value;
      el.classList.toggle('hidden', !ctrlInstSub.value.trim());
    });
  });

  ctrlWatermark?.addEventListener('input', () => {
    payload.studio.watermarkText = ctrlWatermark.value;
    document.querySelectorAll<HTMLElement>('[data-wm]').forEach((el) => {
      el.textContent = ctrlWatermark.value;
    });
  });

  ctrlLogoUrl?.addEventListener('input', () => {
    payload.studio.logoUrl = ctrlLogoUrl.value.trim();
    document.querySelectorAll<HTMLImageElement>('.inst-logo').forEach((img) => {
      img.src = payload.studio.logoUrl;
      img.classList.toggle('hidden', !payload.studio.logoUrl);
    });
  });

  ctrlOmr?.addEventListener('change', () => {
    payload.studio.omrStyle = ctrlOmr.checked;
    document.body.classList.toggle('hide-omr', !ctrlOmr.checked);
  });

  ctrlBoardTags?.addEventListener('change', () => {
    payload.studio.showBoardTags = ctrlBoardTags.checked;
    document.body.classList.toggle('hide-board-tags', !ctrlBoardTags.checked);
  });

  const btnSave = document.getElementById('btnSaveStudio');
  btnSave?.addEventListener('click', async () => {
    if (!payload.paperId) return;
    const statusEl = document.getElementById('saveStudioStatus');
    if (statusEl) statusEl.textContent = 'সেভ হচ্ছে...';
    try {
      const resp = await fetch(`/api/papers/${payload.paperId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ studio: payload.studio }),
      });
      if (statusEl) {
        statusEl.textContent = resp.ok ? 'সেভ হয়েছে!' : 'সেভ ব্যর্থ হয়েছে';
      }
    } catch {
      if (statusEl) statusEl.textContent = 'নেটওয়ার্ক ত্রুটি';
    }
  });

  if (payload.autoprint) {
    setTimeout(() => window.print(), 400);
  }
}

document.addEventListener('DOMContentLoaded', initPrintStudio);
