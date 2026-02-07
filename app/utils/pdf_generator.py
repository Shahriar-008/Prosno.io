"""
PDF Generator for Question Papers (v2 - Table-based two-column layout)
Generates PDF files with two-column MCQ layout using ReportLab.
Uses a simple table-based layout approach for reliable two-column rendering.
"""
import io
import os
import subprocess
import tempfile
import shutil
from typing import Optional, Union
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Flowable
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .document_generator import to_bengali_numeral


# --- WeasyPrint HTML renderer helper ---
def _build_html(questions: list, paper_config: dict, show_answer: bool) -> str:
        """Return HTML string for the question paper. Uses local font files via file:// URIs."""
        # locate fonts
        fonts_dir = Path(_FONTS_DIR)
        regular = fonts_dir.joinpath('NotoSansBengali-Regular.ttf').as_uri()
        bold = fonts_dir.joinpath('NotoSansBengali-Bold.ttf').as_uri() if fonts_dir.joinpath('NotoSansBengali-Bold.ttf').exists() else regular

        def esc(s):
                return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        title = esc(paper_config.get('title', 'Home Test'))
        class_name = esc(paper_config.get('class_name', ''))
        subject_name = esc(paper_config.get('subject_name', ''))
        bengali_time = to_bengali_numeral(paper_config.get('time', len(questions)))
        bengali_marks = to_bengali_numeral(paper_config.get('marks', len(questions)))

        # CSS: two columns, simple table for options
        css = f"""
        @font-face {{
            font-family: 'NotoSansBengaliLocal';
            src: url('{regular}');
            font-weight: normal;
        }}
        @font-face {{
            font-family: 'NotoSansBengaliLocal';
            src: url('{bold}');
            font-weight: bold;
        }}
        body {{ font-family: 'NotoSansBengaliLocal', sans-serif; font-size: 12px; }}
        .container {{ width: 100%; max-width: 800px; margin: 0 auto; }}
        .header {{ text-align:center; }}
        .meta {{ display:flex; justify-content:space-between; margin-bottom:8px; }}
        .questions {{ column-count: 2; column-gap: 24px; }}
        .question {{ break-inside: avoid; margin-bottom:6px; }}
        .qtext {{ font-weight:700; margin-bottom:4px; }}
        .opts {{ width:100%; border-collapse:collapse; }}
        .opts td {{ vertical-align:top; padding:2px 6px 2px 0; }}
        .circle {{ display:inline-block; width:12px; height:12px; border-radius:50%; border:1px solid #000; margin-right:6px; vertical-align:middle; }}
        .circle.filled {{ background:#000; }}
        """

        # Build questions HTML
        q_html = []
        for idx, q in enumerate(questions, 1):
                qid = esc(q.get('id', idx))
                qtext = esc(q.get('question_text', ''))
                q_block = [f"<div class='question'><div class='qtext'>{qid}. {qtext}</div>"]
                # complex sub-options
                if q.get('type') == 'complex':
                        for sub in q.get('sub_options', []):
                                q_block.append(f"<div class='sub'>{esc(sub)}</div>")
                        q_block.append(f"<div class='prompt'><strong>{esc(q.get('final_prompt','নিচের কোনটি সঠিক?'))}</strong></div>")

                opts = q.get('answer_options', [])
                correct = str(q.get('correct_answer','')).strip()
                if len(opts) >= 4:
                        # two-row 2x2 table
                        q_block.append("<table class='opts'><tr>")
                        for i in range(4):
                                opt = esc(opts[i])
                                is_correct = show_answer and (str(opts[i]).strip() == correct)
                                circle_cls = 'circle filled' if is_correct else 'circle'
                                # prefix Bengali letters
                                prefix = ['ক)', 'খ)', 'গ)', 'ঘ)'][i]
                                q_block.append(f"<td><span class='{circle_cls}'></span>{prefix} {opt}</td>")
                                if i % 2 == 1 and i != 3:
                                        q_block.append('</tr><tr>')
                        q_block.append('</tr></table>')
                else:
                        for i, opt in enumerate(opts):
                                is_correct = show_answer and (str(opt).strip() == correct)
                                circle_cls = 'circle filled' if is_correct else 'circle'
                                prefix = ['ক)', 'খ)', 'গ)', 'ঘ)'][i] if i < 4 else ''
                                q_block.append(f"<div><span class='{circle_cls}'></span>{prefix} {esc(opt)}</div>")

                q_block.append('</div>')
                q_html.append(''.join(q_block))

        html = f"""
        <html>
        <head>
            <meta charset='utf-8'/>
            <style>{css}</style>
        </head>
        <body>
            <div class='container'>
                <div class='header'>
                    <h1>{title}</h1>
                    <div>{class_name}</div>
                    <div>{subject_name}</div>
                </div>
                <div class='meta'>
                    <div>সময়— {bengali_time} মিনিট</div>
                    <div>পূর্ণমান— {bengali_marks}</div>
                </div>
                <div class='questions'>
                    {''.join(q_html)}
                </div>
            </div>
        </body>
        </html>
        """
        return html


# ---------------------------------------------------------------------------
# Font Registration
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False

_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'static', 'fonts',
)

FONT_REGULAR = 'NotoSansBengali'
FONT_BOLD = 'NotoSansBengali-Bold'


def _register_fonts() -> None:
    """Register Noto Sans Bengali TTF fonts with ReportLab (once)."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    regular_path = os.path.join(_FONTS_DIR, 'NotoSansBengali-Regular.ttf')
    bold_path = os.path.join(_FONTS_DIR, 'NotoSansBengali-Bold.ttf')

    if not os.path.exists(regular_path):
        raise FileNotFoundError(
            f"Bengali font not found: {regular_path}. "
            "Please place NotoSansBengali-Regular.ttf in app/static/fonts/."
        )

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))

    if os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
    else:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, regular_path))

    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily(
        FONT_REGULAR,
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_REGULAR,
        boldItalic=FONT_BOLD,
    )

    _FONTS_REGISTERED = True


# ---------------------------------------------------------------------------
# Layout Constants (matching DOCX)
# ---------------------------------------------------------------------------
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT_MARGIN = 0.75 * inch
_RIGHT_MARGIN = 0.75 * inch
_TOP_MARGIN = 0.5 * inch
_BOTTOM_MARGIN = 0.5 * inch
_COLUMN_GAP = 0.35 * inch  # Gap between columns

_USABLE_WIDTH = _PAGE_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN
_COL_WIDTH = (_USABLE_WIDTH - _COLUMN_GAP) / 2

# Font sizes matching DOCX
_Q_FONT_SIZE = 8
_HEADER_FONT_SIZE = 10
_TITLE_FONT_SIZE = 14
_LEADING = 10


# ---------------------------------------------------------------------------
# Styles (cached globally for performance)
# ---------------------------------------------------------------------------
_CACHED_STYLES = None


def _build_styles() -> dict:
    """Build ParagraphStyle objects. Cached after first call."""
    global _CACHED_STYLES
    if _CACHED_STYLES is not None:
        return _CACHED_STYLES
    
    _CACHED_STYLES = {
        'title': ParagraphStyle(
            'PaperTitle',
            fontName=FONT_BOLD,
            fontSize=_TITLE_FONT_SIZE,
            leading=_TITLE_FONT_SIZE + 2,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        'center': ParagraphStyle(
            'CenterText',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        'header_left': ParagraphStyle(
            'HeaderLeft',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_LEFT,
        ),
        'header_right': ParagraphStyle(
            'HeaderRight',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_RIGHT,
        ),
        'question': ParagraphStyle(
            'QuestionText',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceBefore=3,
            spaceAfter=0,
        ),
        'sub_option': ParagraphStyle(
            'SubOption',
            fontName=FONT_REGULAR,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            leftIndent=6,
            spaceAfter=0,
        ),
        'prompt': ParagraphStyle(
            'Prompt',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceAfter=0,
        ),
        'option_normal': ParagraphStyle(
            'OptionNormal',
            fontName=FONT_REGULAR,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
        ),
        'option_bold': ParagraphStyle(
            'OptionBold',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
        ),
    }
    return _CACHED_STYLES


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
OMR_CIRCLE = '\u25CB'     # ◯
FILLED_CIRCLE = '\u25CF'  # ●
BENGALI_PREFIXES = ['ক)', 'খ)', 'গ)', 'ঘ)']

# Cached TableStyle objects (avoid recreating for every question)
_OPT_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
])

_CELL_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])

_HEADER_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])

_MAIN_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (0, 0), 0),
    ('RIGHTPADDING', (0, 0), (0, 0), _COLUMN_GAP / 2),
    ('LEFTPADDING', (1, 0), (1, 0), _COLUMN_GAP / 2),
    ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])


def _escape(text: str) -> str:
    """Escape XML entities for ReportLab Paragraph markup."""
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


# ---------------------------------------------------------------------------
# Question Builders
# ---------------------------------------------------------------------------
def _build_question_cell(q: dict, show_answer: bool, styles: dict) -> list:
    """Build flowables for one question (for use in a table cell)."""
    flowables = []

    q_text = _escape(q.get('question_text', ''))
    q_id = _escape(str(q.get('id', '')))

    # Question text
    flowables.append(
        Paragraph(f'{q_id}. {q_text}', styles['question'])
    )

    # Complex question sub-options
    if q.get('type') == 'complex':
        for sub_opt in q.get('sub_options', []):
            flowables.append(
                Paragraph(f'. {_escape(sub_opt)}', styles['sub_option'])
            )
        prompt = q.get('final_prompt', 'নিচের কোনটি সঠিক?')
        flowables.append(
            Paragraph(_escape(prompt), styles['prompt'])
        )

    # Answer options (2x2 table)
    options = q.get('answer_options', [])
    correct_ans = str(q.get('correct_answer', '')).strip()

    if len(options) >= 4:
        opt_cell_width = (_COL_WIDTH - 4) / 2
        rows = []
        for row_idx in range(2):
            row = []
            for col_idx in range(2):
                opt_idx = row_idx * 2 + col_idx
                opt_text = str(options[opt_idx]).strip()
                is_correct = show_answer and opt_text == correct_ans
                prefix = BENGALI_PREFIXES[opt_idx]
                style = styles['option_bold'] if is_correct else styles['option_normal']
                # Use a custom flowable that draws the OMR circle and the text
                cell = OptionFlowable(prefix, opt_text, style, filled=is_correct)
                row.append(cell)
            rows.append(row)

        opt_table = Table(rows, colWidths=[opt_cell_width, opt_cell_width])
        opt_table.setStyle(_OPT_TABLE_STYLE)
        flowables.append(opt_table)
    else:
        for j, opt in enumerate(options):
            is_correct = show_answer and str(opt).strip() == correct_ans
            prefix = BENGALI_PREFIXES[j] if j < len(BENGALI_PREFIXES) else ''
            style = styles['option_bold'] if is_correct else styles['option_normal']
            flowables.append(OptionFlowable(prefix, str(opt), style, filled=is_correct))

    return flowables


class OptionFlowable(Flowable):
    """Flowable that draws an OMR-style circle and renders the option text next to it.

    Optimized: defers Paragraph creation until wrap() is called.
    """
    __slots__ = ('prefix', 'text', 'style', 'filled', 'circle_dia', 'paragraph', 'width', 'height')

    def __init__(self, prefix: str, text: str, style: ParagraphStyle, filled: bool = False, circle_dia: int = 8):
        super().__init__()
        self.prefix = prefix
        self.text = text  # Store unescaped, escape once in wrap
        self.style = style
        self.filled = filled
        self.circle_dia = circle_dia
        self.paragraph = None  # Lazy creation

    def wrap(self, availWidth, availHeight):
        # Create paragraph lazily (avoids overhead if not rendered)
        if self.paragraph is None:
            escaped = _escape(self.text)
            self.paragraph = Paragraph(f'{self.prefix} {escaped}', self.style)
        
        gap = 4
        text_avail = max(availWidth - (self.circle_dia + gap), 10)
        _, h = self.paragraph.wrap(text_avail, availHeight)
        self.width = availWidth
        self.height = max(h, self.circle_dia)
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        radius = self.circle_dia / 2.0
        x = radius
        y = self.height / 2.0
        c.saveState()
        c.setLineWidth(0.8)
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.black if self.filled else colors.white)
        c.circle(x, y, radius, stroke=1, fill=1)
        # Draw text paragraph
        self.paragraph.drawOn(c, self.circle_dia + 4, 0)
        c.restoreState()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_question_paper_pdf(
    questions: list,
    output_path: Optional[str],
    paper_config: dict,
    show_answer: bool = False,
) -> Union[io.BytesIO, str]:
    """
    Generate a two-column MCQ question paper as PDF.
    """
    # 1) Prefer LibreOffice/soffice DOCX -> PDF conversion if available.
    #    This preserves DOCX output exactly and ensures correct Bengali shaping.
    soffice_path = shutil.which('soffice') or shutil.which('libreoffice')
    if soffice_path:
        tmpdir = tempfile.mkdtemp(prefix='prosno_docx2pdf_')
        try:
            docx_path = os.path.join(tmpdir, 'paper.docx')
            pdf_path = os.path.join(tmpdir, 'paper.pdf')
            # Create DOCX using the existing document generator
            from . import document_generator as _docgen
            _docgen.create_question_paper(questions, docx_path, paper_config, show_answer=show_answer)

            # Run headless conversion
            cmd = [soffice_path, '--headless', '--convert-to', 'pdf', '--outdir', tmpdir, docx_path]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Read generated PDF
            with open(pdf_path, 'rb') as f:
                data = f.read()

            if output_path is None:
                buf = io.BytesIO(data)
                buf.seek(0)
                return buf
            else:
                out_dir = os.path.dirname(output_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir)
                with open(output_path, 'wb') as out_f:
                    out_f.write(data)
                return output_path
        finally:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    # 2) Prefer WeasyPrint (HTML -> PDF) if available (better complex-script shaping)
    try:
        from weasyprint import HTML, CSS  # type: ignore
        weasy_ok = True
    except Exception:
        weasy_ok = False

    if weasy_ok:
        html = _build_html(questions, paper_config, show_answer)
        # If output_path is None, return BytesIO buffer
        if output_path is None:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf(stylesheets=None)
            buf = io.BytesIO(pdf_bytes)
            buf.seek(0)
            return buf
        else:
            # Ensure output dir exists
            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir)
            HTML(string=html).write_pdf(output_path)
            return output_path

    # 3) Fallback to ReportLab renderer (best-effort)
    _register_fonts()
    styles = _build_styles()

    # Output target
    buffer: Optional[io.BytesIO] = None
    if output_path is None:
        buffer = io.BytesIO()
        target = buffer
    else:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        target = output_path

    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        leftMargin=_LEFT_MARGIN,
        rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
    )

    story = []

    # --- Header section ---
    title = paper_config.get('title', 'Home Test')
    story.append(Paragraph(_escape(title), styles['title']))

    class_name = paper_config.get('class_name', '')
    subject_name = paper_config.get('subject_name', '')
    if class_name:
        story.append(Paragraph(_escape(class_name), styles['center']))
    if subject_name:
        story.append(Paragraph(f'বিষয়: {_escape(subject_name)}', styles['center']))

    # Time & marks row
    num_questions = len(questions)
    time_minutes = paper_config.get('time', num_questions)
    total_marks = paper_config.get('marks', num_questions)
    bengali_time = to_bengali_numeral(time_minutes)
    bengali_marks = to_bengali_numeral(total_marks)

    time_para = Paragraph(f'সময়— {bengali_time} মিনিট', styles['header_left'])
    marks_para = Paragraph(f'পূর্ণমান— {bengali_marks}', styles['header_right'])

    header_table = Table(
        [[time_para, marks_para]],
        colWidths=[_USABLE_WIDTH / 2, _USABLE_WIDTH / 2],
    )
    header_table.setStyle(_HEADER_TABLE_STYLE)
    story.append(header_table)
    story.append(Spacer(1, 8))

    # --- Two-column questions table ---
    # Split questions into left and right columns
    n = len(questions)
    mid = (n + 1) // 2  # Left column gets the extra if odd
    left_questions = questions[:mid]
    right_questions = questions[mid:]

    # Build cell content for each column
    left_cell_content = []
    for q in left_questions:
        left_cell_content.extend(_build_question_cell(q, show_answer, styles))

    right_cell_content = []
    for q in right_questions:
        right_cell_content.extend(_build_question_cell(q, show_answer, styles))

    # Create two-column table
    # Each cell contains a nested table with the questions
    def wrap_in_table(flowables):
        """Wrap flowables in a single-cell table for proper rendering."""
        if not flowables:
            return Paragraph('', styles['option_normal'])
        rows = [[f] for f in flowables]
        t = Table(rows, colWidths=[_COL_WIDTH])
        t.setStyle(_CELL_TABLE_STYLE)
        return t

    left_table = wrap_in_table(left_cell_content)
    right_table = wrap_in_table(right_cell_content)

    # Main two-column table
    main_table = Table(
        [[left_table, right_table]],
        colWidths=[_COL_WIDTH, _COL_WIDTH],
        hAlign='LEFT',
    )
    main_table.setStyle(_MAIN_TABLE_STYLE)

    story.append(main_table)

    # Build PDF
    doc.build(story)

    if output_path is None and buffer is not None:
        buffer.seek(0)
        return buffer
    return output_path or ''


def generate_paper_to_memory_pdf(
    questions: list,
    paper_config: dict,
    student_only: bool = False,
    teacher_only: bool = False,
) -> tuple:
    """Generate PDF copies as BytesIO buffers.
    
    Args:
        questions: List of question objects or dicts
        paper_config: Paper configuration dict
        student_only: If True, only generate student version (teacher_buffer will be None)
        teacher_only: If True, only generate teacher version (student_buffer will be None)
    
    Returns:
        Tuple of (student_buffer, teacher_buffer). One may be None if only generating one version.
    """
    question_list = _prepare_question_list(questions)
    
    student_buffer = None
    teacher_buffer = None
    
    if not teacher_only:
        student_buffer = create_question_paper_pdf(
            question_list, None, paper_config, show_answer=False
        )
    
    if not student_only:
        teacher_buffer = create_question_paper_pdf(
            question_list, None, paper_config, show_answer=True
        )
    
    return student_buffer, teacher_buffer


def generate_paper_from_db_pdf(
    questions: list,
    paper_config: dict,
    output_folder: str,
) -> tuple:
    """Generate both student and teacher PDF copies saved to disk."""
    import uuid as _uuid
    from datetime import datetime as _dt

    question_list = _prepare_question_list(questions)

    timestamp = _dt.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(_uuid.uuid4())[:8]
    base = f"question_paper_{timestamp}_{unique_id}"

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    student_path = os.path.join(output_folder, f"{base}_student.pdf")
    create_question_paper_pdf(
        question_list, student_path, paper_config, show_answer=False
    )

    teacher_path = os.path.join(output_folder, f"{base}_teacher.pdf")
    create_question_paper_pdf(
        question_list, teacher_path, paper_config, show_answer=True
    )

    return student_path, teacher_path


def _prepare_question_list(questions: list) -> list:
    """Convert Question model objects to dicts with sequential IDs."""
    question_list = []
    for idx, q in enumerate(questions, 1):
        if hasattr(q, 'to_dict'):
            q_dict = q.to_dict()
        else:
            q_dict = q.copy() if isinstance(q, dict) else q
        q_dict['id'] = str(idx)
        question_list.append(q_dict)
    return question_list
