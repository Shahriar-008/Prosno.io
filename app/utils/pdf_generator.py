"""
PDF Generator for Question Papers
Generates PDF files with two-column MCQ layout using ReportLab.
Mirrors the DOCX generator's layout: full-width header, 2-column questions,
2x2 option tables with OMR circles, Bengali numeral support.
"""
import io
import os
from typing import Optional, Union

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    NextPageTemplate,
    FrameBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .document_generator import to_bengali_numeral


# ---------------------------------------------------------------------------
# Font Registration
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False

# Resolve font directory relative to this file
_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'static', 'fonts',
)

FONT_REGULAR = 'NotoSansBengali'
FONT_BOLD = 'NotoSansBengali-Bold'


def _register_fonts() -> None:
    """Register Noto Sans Bengali TTF fonts with ReportLab (once)."""
    global _FONTS_REGISTERED  # noqa: PLW0603
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
        # Fallback: alias bold to regular
        pdfmetrics.registerFont(TTFont(FONT_BOLD, regular_path))

    # Register font family so <b> tags in Paragraph work automatically
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
# Style Helpers
# ---------------------------------------------------------------------------
_Q_FONT_SIZE = 8      # Question / option text size (pt)
_HEADER_FONT_SIZE = 10  # Body / header text size (pt)
_TITLE_FONT_SIZE = 14   # Paper title size (pt)
_LEADING = 11           # Line spacing for question text

# Page layout constants matching DOCX generator
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT_MARGIN = 0.75 * inch
_RIGHT_MARGIN = 0.75 * inch
_TOP_MARGIN = 0.5 * inch
_BOTTOM_MARGIN = 0.5 * inch
_COLUMN_GAP = 0.25 * inch

# Usable width inside margins
_USABLE_WIDTH = _PAGE_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN


def _build_styles() -> dict:
    """Build ParagraphStyle objects used throughout the PDF."""
    return {
        'title': ParagraphStyle(
            'PaperTitle',
            fontName=FONT_BOLD,
            fontSize=_TITLE_FONT_SIZE,
            leading=_TITLE_FONT_SIZE + 4,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        'center': ParagraphStyle(
            'CenterText',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 3,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        'header_left': ParagraphStyle(
            'HeaderLeft',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 3,
            alignment=TA_LEFT,
        ),
        'header_right': ParagraphStyle(
            'HeaderRight',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 3,
            alignment=TA_RIGHT,
        ),
        'question': ParagraphStyle(
            'QuestionText',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceBefore=4,
            spaceAfter=1,
        ),
        'sub_option': ParagraphStyle(
            'SubOption',
            fontName=FONT_REGULAR,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            leftIndent=12,
            spaceAfter=0,
        ),
        'prompt': ParagraphStyle(
            'Prompt',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceAfter=1,
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


# ---------------------------------------------------------------------------
# Chararcters
# ---------------------------------------------------------------------------
OMR_CIRCLE = '\u25CB'     # ◯  White circle
FILLED_CIRCLE = '\u25CF'  # ●  Black circle
BENGALI_PREFIXES = ['ক)', 'খ)', 'গ)', 'ঘ)']


# ---------------------------------------------------------------------------
# Question Flowable Builders
# ---------------------------------------------------------------------------
def _build_question_flowables(
    q: dict,
    show_answer: bool,
    styles: dict,
    col_width: float,
) -> list:
    """Return a list of ReportLab flowables for one question."""
    flowables: list = []

    # Escape XML-sensitive characters for Paragraph markup
    q_text = _escape(q.get('question_text', ''))
    q_id = _escape(str(q.get('id', '')))

    # A. Question text (bold)
    flowables.append(
        Paragraph(f'{q_id}. {q_text}', styles['question'])
    )

    # B. Complex question extras
    if q.get('type') == 'complex':
        for sub_opt in q.get('sub_options', []):
            flowables.append(
                Paragraph(f'• {_escape(sub_opt)}', styles['sub_option'])
            )
        prompt = q.get('final_prompt', 'নিচের কোনটি সঠিক?')
        flowables.append(
            Paragraph(_escape(prompt), styles['prompt'])
        )

    # C. Answer options (2x2 table when ≥4 options, else stacked)
    options = q.get('answer_options', [])
    correct_ans = str(q.get('correct_answer', '')).strip()

    if len(options) >= 4:
        flowables.append(
            _build_options_table(
                options[:4], correct_ans, show_answer, styles, col_width
            )
        )
    else:
        for j, opt in enumerate(options):
            is_correct = show_answer and str(opt).strip() == correct_ans
            circle = FILLED_CIRCLE if is_correct else OMR_CIRCLE
            prefix = BENGALI_PREFIXES[j] if j < len(BENGALI_PREFIXES) else ''
            style = styles['option_bold'] if is_correct else styles['option_normal']
            text = f'{circle} {prefix} {_escape(str(opt))}'
            if is_correct:
                text += ' (সঠিক উত্তর)'
            flowables.append(Paragraph(text, style))

    return flowables


def _build_options_table(
    options: list,
    correct_ans: str,
    show_answer: bool,
    styles: dict,
    col_width: float,
) -> Table:
    """Build a 2x2 ReportLab Table for the four MCQ options."""
    half_w = col_width / 2

    rows = []
    for row_idx in range(2):
        row = []
        for col_idx in range(2):
            opt_idx = row_idx * 2 + col_idx
            opt_text = str(options[opt_idx])
            is_correct = show_answer and opt_text.strip() == correct_ans
            circle = FILLED_CIRCLE if is_correct else OMR_CIRCLE
            prefix = BENGALI_PREFIXES[opt_idx]
            style = styles['option_bold'] if is_correct else styles['option_normal']
            cell = Paragraph(
                f'{circle} {prefix} {_escape(opt_text)}', style
            )
            row.append(cell)
        rows.append(row)

    table = Table(rows, colWidths=[half_w, half_w])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return table


def _escape(text: str) -> str:
    """Escape XML entities for ReportLab Paragraph markup."""
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


# ---------------------------------------------------------------------------
# Page Templates with Two-Column Layout
# ---------------------------------------------------------------------------
def _build_doc(buffer_or_path) -> BaseDocTemplate:
    """Create a BaseDocTemplate with header-only and two-column templates."""
    doc = BaseDocTemplate(
        buffer_or_path,
        pagesize=A4,
        leftMargin=_LEFT_MARGIN,
        rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
    )

    frame_full = Frame(
        _LEFT_MARGIN,
        _BOTTOM_MARGIN,
        _USABLE_WIDTH,
        _PAGE_HEIGHT - _TOP_MARGIN - _BOTTOM_MARGIN,
        id='full',
    )

    col_w = (_USABLE_WIDTH - _COLUMN_GAP) / 2
    frame_left = Frame(
        _LEFT_MARGIN,
        _BOTTOM_MARGIN,
        col_w,
        _PAGE_HEIGHT - _TOP_MARGIN - _BOTTOM_MARGIN,
        id='col_left',
    )
    frame_right = Frame(
        _LEFT_MARGIN + col_w + _COLUMN_GAP,
        _BOTTOM_MARGIN,
        col_w,
        _PAGE_HEIGHT - _TOP_MARGIN - _BOTTOM_MARGIN,
        id='col_right',
    )

    header_template = PageTemplate(
        id='header',
        frames=[frame_full],
    )
    twocol_template = PageTemplate(
        id='twocol',
        frames=[frame_left, frame_right],
    )

    doc.addPageTemplates([header_template, twocol_template])
    return doc


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

    Args:
        questions: List of question dicts (same format as DOCX generator).
        output_path: File path to write PDF. If None, returns BytesIO buffer.
        paper_config: Dict with title, class_name, subject_name, time, marks.
        show_answer: Whether to mark correct answers with filled circles.

    Returns:
        BytesIO buffer when output_path is None, else the file path string.
    """
    _register_fonts()
    styles = _build_styles()

    # Decide output target
    buffer: Optional[io.BytesIO] = None
    if output_path is None:
        buffer = io.BytesIO()
        doc = _build_doc(buffer)
    else:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        doc = _build_doc(output_path)

    # ------------------------------------------------------------------
    # Build story (list of flowables)
    # ------------------------------------------------------------------
    story: list = []

    # --- Header section (full-width template) ---
    title = paper_config.get('title', 'Home Test')
    story.append(Paragraph(_escape(title), styles['title']))

    class_name = paper_config.get('class_name', '')
    subject_name = paper_config.get('subject_name', '')
    if class_name:
        story.append(Paragraph(_escape(class_name), styles['center']))
    if subject_name:
        story.append(
            Paragraph(f'বিষয়: {_escape(subject_name)}', styles['center'])
        )

    # Time & marks row (left-aligned time, right-aligned marks)
    num_questions = len(questions)
    time_minutes = paper_config.get('time', num_questions)
    total_marks = paper_config.get('marks', num_questions)
    bengali_time = to_bengali_numeral(time_minutes)
    bengali_marks = to_bengali_numeral(total_marks)

    time_para = Paragraph(
        f'সময়— {bengali_time} মিনিট', styles['header_left']
    )
    marks_para = Paragraph(
        f'পূর্ণমান— {bengali_marks}', styles['header_right']
    )

    header_table = Table(
        [[time_para, marks_para]],
        colWidths=[_USABLE_WIDTH / 2, _USABLE_WIDTH / 2],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # --- Switch to two-column template ---
    story.append(NextPageTemplate('twocol'))
    story.append(FrameBreak())

    # --- Questions ---
    col_w = (_USABLE_WIDTH - _COLUMN_GAP) / 2
    for q in questions:
        q_flowables = _build_question_flowables(
            q, show_answer, styles, col_w
        )
        story.extend(q_flowables)

    # ------------------------------------------------------------------
    # Build PDF
    # ------------------------------------------------------------------
    doc.build(story)

    if output_path is None and buffer is not None:
        buffer.seek(0)
        return buffer
    return output_path or ''


def generate_paper_to_memory_pdf(
    questions: list,
    paper_config: dict,
) -> tuple:
    """
    Generate both student and teacher PDF copies as in-memory BytesIO buffers.

    Args:
        questions: List of Question model objects or dicts.
        paper_config: Configuration dict for the paper.

    Returns:
        Tuple of (student_buffer, teacher_buffer) — BytesIO objects.
    """
    question_list = _prepare_question_list(questions)

    student_buffer = create_question_paper_pdf(
        question_list, None, paper_config, show_answer=False
    )
    teacher_buffer = create_question_paper_pdf(
        question_list, None, paper_config, show_answer=True
    )
    return student_buffer, teacher_buffer


def generate_paper_from_db_pdf(
    questions: list,
    paper_config: dict,
    output_folder: str,
) -> tuple:
    """
    Generate both student and teacher PDF copies saved to disk.

    Args:
        questions: List of Question model objects or dicts.
        paper_config: Configuration dict for the paper.
        output_folder: Directory to save generated files.

    Returns:
        Tuple of (student_file_path, teacher_file_path).
    """
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
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
