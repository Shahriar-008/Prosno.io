"""
OMR template normalization and PDF rendering utilities.
"""
from __future__ import annotations

import copy
import html
import io
import logging
import math
import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .document_generator import to_bengali_numeral

logger = logging.getLogger(__name__)

PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297
SUPPORTED_QUESTION_COUNTS = (40, 60, 80, 100)
SUPPORTED_BUBBLE_SIZES = ("small", "large")
SUPPORTED_HEADER_MODES = ("digital", "manual")
SUPPORTED_SHEET_VARIANTS = ("institutional", "general")
SUPPORTED_GENERAL_COLUMNS = (1, 2, 3, 4)
GENERAL_QUESTION_COUNT_RANGE = (1, 100)
GENERAL_AUTO_FLOW_COLUMN = 1
GENERAL_MAX_ROWS_PER_AUTO_COLUMN = 25
GENERAL_MAX_QUESTIONS_BY_COLUMN = {1: 100, 2: 50, 3: 75, 4: 100}
OMR_TEMPLATE_TYPE = "exam_sheet_v1"
ANSWER_OPTION_LABELS = ("ক", "খ", "গ", "ঘ")
HEADER_WARNING_TEXT = "এই বক্সে কোনো দাগ দেওয়া যাবে না"
MANUAL_HEADER_LABELS = ("প্রতিষ্ঠান", "পরীক্ষার নাম", "উপশিরোনাম")
GENERAL_FIELD_ROWS = (
    ("নাম",),
    ("শ্রেণি", "সেকশন"),
    ("বিষয়", "রোল"),
)
ROLL_NUMBER_TITLE = "রোল নম্বর"
SUBJECT_CODE_TITLE = "বিষয় কোড"
SET_CODE_TITLE = "সেট কোড"
INSTRUCTIONS_TITLE = "নির্দেশনা"
SIGNATURE_LABEL = "কক্ষ পরিদর্শকের স্বাক্ষর"
QUESTION_LABEL = "প্রশ্ন"
ANSWER_LABEL = "উত্তর"
INSTITUTIONAL_ANSWER_TITLE = "বহুনির্বাচনি অভীক্ষার উত্তরপত্র"
GENERAL_ANSWER_TITLE = "সাধারণ বহুনির্বাচনি উত্তরপত্র"
DIGIT_LABELS = tuple(str(i) for i in range(10))

THEME_COLORS = {
    "rose": {"label": "Rose", "hex": "#f45d74"},
    "slate": {"label": "Slate", "hex": "#8b95a7"},
    "blue": {"label": "Blue", "hex": "#5d8ee6"},
    "green": {"label": "Green", "hex": "#46c56d"},
    "violet": {"label": "Violet", "hex": "#8f68e8"},
    "orange": {"label": "Orange", "hex": "#ff8a3d"},
    "pink": {"label": "Pink", "hex": "#de63a5"},
    "gold": {"label": "Gold", "hex": "#efbd34"},
}

BUBBLE_SIZE_PRESETS = {
    "small": {"label": "Small", "diameter_mm": 3.8, "font_size": 5.2},
    "large": {"label": "Large", "diameter_mm": 4.8, "font_size": 6.0},
}

LAYOUT_PRESETS = {
    40: {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "x_mm": 14,
            "y_mm": 156,
            "columns": 2,
            "rows": 20,
            "column_width_mm": 88,
            "column_gap_mm": 6,
            "row_height_mm": 6.6,
            "header_height_mm": 8,
            "number_width_mm": 13,
        },
    },
    60: {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "x_mm": 10,
            "y_mm": 152,
            "columns": 3,
            "rows": 20,
            "column_width_mm": 59,
            "column_gap_mm": 4,
            "row_height_mm": 6.4,
            "header_height_mm": 7.6,
            "number_width_mm": 11.5,
        },
    },
    80: {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "x_mm": 7,
            "y_mm": 152,
            "columns": 4,
            "rows": 20,
            "column_width_mm": 45.5,
            "column_gap_mm": 3,
            "row_height_mm": 6.2,
            "header_height_mm": 7.2,
            "number_width_mm": 9.8,
        },
    },
    100: {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "x_mm": 7,
            "y_mm": 146,
            "columns": 4,
            "rows": 25,
            "column_width_mm": 45.5,
            "column_gap_mm": 3,
            "row_height_mm": 5.45,
            "header_height_mm": 6.6,
            "number_width_mm": 9.8,
        },
    },
}

GENERAL_COLUMN_LAYOUTS = {
    1: {
        "x_mm": 52,
        "column_width_mm": 106,
        "column_gap_mm": 0,
        "header_height_mm": 8.6,
        "number_width_mm": 16.5,
        "max_row_height_mm": 13.2,
    },
    2: {
        "x_mm": 35,
        "column_width_mm": 67,
        "column_gap_mm": 6,
        "header_height_mm": 8.2,
        "number_width_mm": 13.2,
        "max_row_height_mm": 10.2,
    },
    3: {
        "x_mm": 25,
        "column_width_mm": 50,
        "column_gap_mm": 5,
        "header_height_mm": 7.6,
        "number_width_mm": 11,
        "max_row_height_mm": 8.4,
    },
    4: {
        "x_mm": 13,
        "column_width_mm": 43,
        "column_gap_mm": 4,
        "header_height_mm": 7.1,
        "number_width_mm": 9.4,
        "max_row_height_mm": 6.45,
    },
}

GENERAL_ANSWER_GRID_Y_MM = 102
GENERAL_ANSWER_GRID_BOTTOM_MM = 270

DEFAULT_OMR_CONFIG = {
    "template_type": OMR_TEMPLATE_TYPE,
    "sheet_variant": "institutional",
    "question_count": 100,
    "answer_columns": 4,
    "theme_color": "rose",
    "bubble_size": "large",
    "header_mode": "digital",
    "header": {
        "title": "",
        "subtitle": "",
        "institution": "",
    },
    "fields": {
        "roll": True,
        "set_code": True,
        "subject_code": True,
    },
    "instructions": [
        "একটি মাত্র বৃত্ত পূরণ করুন।",
        "কালো বা নীল কলম ব্যবহার করুন।",
        "ভুল চিহ্ন দিলে তা সম্পূর্ণভাবে মুছে ফেলুন।",
        "ভাঁজ বা দাগ ছাড়া পরিষ্কার কাগজ জমা দিন।",
    ],
}

_FONTS_REGISTERED = False
_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "static",
    "fonts",
)
FONT_REGULAR = "NotoSansBengali"
FONT_BOLD = "NotoSansBengali-Bold"


def _register_fonts() -> None:
    """Register fonts once for OMR PDF rendering."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    regular_path = os.path.join(_FONTS_DIR, "NotoSansBengali-Regular.ttf")
    bold_path = os.path.join(_FONTS_DIR, "NotoSansBengali-Bold.ttf")

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


def get_default_omr_config() -> dict[str, Any]:
    """Return a deep copy of the default OMR template config."""
    return copy.deepcopy(DEFAULT_OMR_CONFIG)


def get_omr_layout_presets() -> dict[int, dict[str, Any]]:
    """Return the fixed layout map used by both preview and PDF rendering."""
    return copy.deepcopy(LAYOUT_PRESETS)


def get_omr_theme_options() -> dict[str, dict[str, str]]:
    """Return the available print-safe theme colors."""
    return copy.deepcopy(THEME_COLORS)


def get_omr_bubble_size_options() -> dict[str, dict[str, Any]]:
    """Return the available bubble size presets."""
    return copy.deepcopy(BUBBLE_SIZE_PRESETS)


def get_omr_general_rules() -> dict[str, Any]:
    """Return UI-safe rules for General Normal OMR controls."""
    return {
        "min_question_count": GENERAL_QUESTION_COUNT_RANGE[0],
        "max_question_count": GENERAL_QUESTION_COUNT_RANGE[1],
        "supported_columns": list(SUPPORTED_GENERAL_COLUMNS),
        "max_question_count_by_column": copy.deepcopy(GENERAL_MAX_QUESTIONS_BY_COLUMN),
    }


def _resolve_general_distribution(question_count: int, answer_columns: int) -> tuple[int, int]:
    if answer_columns == GENERAL_AUTO_FLOW_COLUMN:
        rows = min(question_count, GENERAL_MAX_ROWS_PER_AUTO_COLUMN)
        return max(1, math.ceil(question_count / rows)), rows
    return answer_columns, math.ceil(question_count / answer_columns)


def _build_general_layout(question_count: int, answer_columns: int) -> dict[str, Any]:
    render_columns, rows = _resolve_general_distribution(question_count, answer_columns)
    spec = GENERAL_COLUMN_LAYOUTS[render_columns]
    available_rows_height = GENERAL_ANSWER_GRID_BOTTOM_MM - GENERAL_ANSWER_GRID_Y_MM - spec["header_height_mm"]
    row_height_mm = min(spec["max_row_height_mm"], available_rows_height / rows)
    return {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "x_mm": spec["x_mm"],
            "y_mm": GENERAL_ANSWER_GRID_Y_MM,
            "columns": render_columns,
            "rows": rows,
            "column_width_mm": spec["column_width_mm"],
            "column_gap_mm": spec["column_gap_mm"],
            "row_height_mm": round(row_height_mm, 2),
            "header_height_mm": spec["header_height_mm"],
            "number_width_mm": spec["number_width_mm"],
        },
    }


def _resolve_omr_layout(cfg: dict[str, Any]) -> dict[str, Any]:
    if cfg["sheet_variant"] == "general":
        return _build_general_layout(cfg["question_count"], cfg["answer_columns"])
    return copy.deepcopy(LAYOUT_PRESETS[cfg["question_count"]])


def normalize_omr_template_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize an OMR template config."""
    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise ValueError("OMR config must be a JSON object.")

    cfg = get_default_omr_config()
    raw_type = raw_config.get("template_type", cfg["template_type"])
    if raw_type != OMR_TEMPLATE_TYPE:
        raise ValueError("Unsupported OMR template type.")
    cfg["template_type"] = raw_type

    sheet_variant = str(raw_config.get("sheet_variant", cfg["sheet_variant"])).strip().lower()
    if sheet_variant not in SUPPORTED_SHEET_VARIANTS:
        raise ValueError("OMR sheet variant is not supported.")
    cfg["sheet_variant"] = sheet_variant

    question_count = raw_config.get("question_count", cfg["question_count"])
    try:
        question_count = int(question_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("Question count must be a number.") from exc
    if sheet_variant == "general":
        if not GENERAL_QUESTION_COUNT_RANGE[0] <= question_count <= GENERAL_QUESTION_COUNT_RANGE[1]:
            raise ValueError(
                f"Question count must be between {GENERAL_QUESTION_COUNT_RANGE[0]} and {GENERAL_QUESTION_COUNT_RANGE[1]} for General Normal OMR."
            )
    elif question_count not in SUPPORTED_QUESTION_COUNTS:
        raise ValueError("Question count must be one of 40, 60, 80, or 100.")
    cfg["question_count"] = question_count

    answer_columns = raw_config.get(
        "answer_columns",
        GENERAL_AUTO_FLOW_COLUMN if sheet_variant == "general" else cfg["answer_columns"],
    )
    try:
        answer_columns = int(answer_columns)
    except (TypeError, ValueError) as exc:
        raise ValueError("Column count must be a number.") from exc
    if sheet_variant == "general":
        if answer_columns not in SUPPORTED_GENERAL_COLUMNS:
            raise ValueError("General Normal OMR supports auto flow plus 2, 3, or 4 answer columns.")
        max_questions = GENERAL_MAX_QUESTIONS_BY_COLUMN[answer_columns]
        if question_count > max_questions:
            if answer_columns == GENERAL_AUTO_FLOW_COLUMN:
                raise ValueError(f"Auto flow supports up to {max_questions} questions on General Normal OMR.")
            raise ValueError(
                f"{answer_columns} columns support up to {max_questions} questions on General Normal OMR."
            )
        cfg["answer_columns"] = answer_columns
    else:
        cfg["answer_columns"] = LAYOUT_PRESETS[question_count]["answer_grid"]["columns"]

    theme_color = str(raw_config.get("theme_color", cfg["theme_color"])).strip().lower()
    if theme_color not in THEME_COLORS:
        raise ValueError("Theme color is not supported.")
    cfg["theme_color"] = theme_color

    bubble_size = str(raw_config.get("bubble_size", cfg["bubble_size"])).strip().lower()
    if bubble_size not in SUPPORTED_BUBBLE_SIZES:
        raise ValueError("Bubble size must be 'small' or 'large'.")
    cfg["bubble_size"] = bubble_size

    header_mode = str(raw_config.get("header_mode", cfg["header_mode"])).strip().lower()
    if header_mode not in SUPPORTED_HEADER_MODES:
        raise ValueError("Header mode must be 'digital' or 'manual'.")
    cfg["header_mode"] = header_mode

    raw_header = raw_config.get("header") or {}
    if not isinstance(raw_header, dict):
        raise ValueError("Header must be an object.")
    header_limits = {"title": 80, "subtitle": 120, "institution": 120}
    for key, max_len in header_limits.items():
        value = str(raw_header.get(key, cfg["header"][key])).strip()
        if len(value) > max_len:
            raise ValueError(f"Header {key} is too long (max {max_len} characters).")
        cfg["header"][key] = value

    raw_fields = raw_config.get("fields") or {}
    if not isinstance(raw_fields, dict):
        raise ValueError("Fields must be an object.")
    for key in cfg["fields"]:
        cfg["fields"][key] = bool(raw_fields.get(key, cfg["fields"][key]))
    if not any(cfg["fields"].values()):
        raise ValueError("At least one student info field must stay enabled.")

    raw_instructions = raw_config.get("instructions", cfg["instructions"])
    if isinstance(raw_instructions, str):
        raw_instructions = [line.strip() for line in raw_instructions.splitlines()]
    if not isinstance(raw_instructions, list):
        raise ValueError("Instructions must be a list of strings.")

    cleaned_instructions = []
    for instruction in raw_instructions:
        if instruction is None:
            continue
        text = str(instruction).strip()
        if not text:
            continue
        if len(text) > 140:
            raise ValueError("Each instruction must be 140 characters or less.")
        cleaned_instructions.append(text)
    if not cleaned_instructions:
        cleaned_instructions = copy.deepcopy(DEFAULT_OMR_CONFIG["instructions"])
    cfg["instructions"] = cleaned_instructions[:6]

    return cfg


def generate_omr_pdf_to_memory(config: dict[str, Any]) -> io.BytesIO:
    """Generate a printable OMR sheet PDF from a normalized config."""
    cfg = normalize_omr_template_config(config)
    html_buffer = _generate_omr_pdf_with_weasyprint(cfg)
    if html_buffer is not None:
        return html_buffer

    _register_fonts()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    layout = _resolve_omr_layout(cfg)
    theme = THEME_COLORS[cfg["theme_color"]]
    bubble_preset = BUBBLE_SIZE_PRESETS[cfg["bubble_size"]]

    accent = colors.HexColor(theme["hex"])
    accent_soft = _blend_hex(theme["hex"], "#ffffff", 0.78)

    _draw_page_background(pdf)
    _draw_registration_markers(pdf)
    if cfg["sheet_variant"] == "general":
        _draw_general_header(pdf, cfg)
        _draw_general_identity_section(pdf, accent)
    else:
        _draw_header(pdf, cfg, accent, accent_soft)
        _draw_identity_section(pdf, cfg, accent, accent_soft, bubble_preset)
    _draw_answer_grid(pdf, cfg, layout, accent, accent_soft, bubble_preset)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def _generate_omr_pdf_with_weasyprint(cfg: dict[str, Any]) -> io.BytesIO | None:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:
        logger.debug("WeasyPrint unavailable for OMR PDF rendering: %s", exc)
        return None

    try:
        html_content = _build_omr_html(cfg)
        pdf_bytes = HTML(string=html_content, base_url=str(Path(_FONTS_DIR).resolve())).write_pdf()
    except Exception as exc:
        logger.warning("WeasyPrint OMR render failed, falling back to ReportLab: %s", exc)
        return None

    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)
    return buffer


def _build_omr_html(cfg: dict[str, Any]) -> str:
    layout = _resolve_omr_layout(cfg)
    theme = THEME_COLORS[cfg["theme_color"]]
    bubble_preset = BUBBLE_SIZE_PRESETS[cfg["bubble_size"]]
    fonts_dir = Path(_FONTS_DIR).resolve()
    regular_font = fonts_dir.joinpath("NotoSansBengali-Regular.ttf").as_uri()
    bold_path = fonts_dir.joinpath("NotoSansBengali-Bold.ttf")
    bold_font = bold_path.as_uri() if bold_path.exists() else regular_font
    accent = theme["hex"]
    accent_soft = _hex_to_rgba_css(accent, 0.16)

    blocks = [_render_html_markers()]
    if cfg["sheet_variant"] == "general":
        blocks.append(_render_html_general_header(cfg))
        blocks.append(_render_html_general_identity())
    else:
        blocks.append(_render_html_institutional_header(cfg))
        blocks.append(_render_html_institutional_identity(cfg, bubble_preset))
    blocks.append(_render_html_answers(cfg, layout, bubble_preset))

    return f"""<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="utf-8">
    <style>
        @page {{
            size: A4;
            margin: 0;
        }}
        @font-face {{
            font-family: 'NotoSansBengaliLocal';
            src: url('{regular_font}');
            font-weight: 400;
        }}
        @font-face {{
            font-family: 'NotoSansBengaliLocal';
            src: url('{bold_font}');
            font-weight: 700;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            background: #ffffff;
            font-family: 'NotoSansBengaliLocal', sans-serif;
        }}
        .omr-page {{
            position: relative;
            width: 210mm;
            height: 297mm;
            background: #ffffff;
            box-shadow: inset 0 0 0 0.35mm #e5e7eb;
        }}
        .box {{
            position: absolute;
        }}
        .marker {{
            display: flex;
            align-items: center;
            justify-content: center;
            background: #101010;
        }}
        .marker span {{
            width: 44%;
            height: 44%;
            border-left: 1mm solid #fff;
            border-bottom: 1mm solid #fff;
        }}
        .marker.right span {{
            transform: rotate(180deg);
        }}
        .institutional-header {{
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: center;
            gap: 1.4mm;
            padding: 3.4mm 6mm 4mm;
            border: 0.35mm solid {accent};
            border-radius: 3mm;
            background: {accent_soft};
            text-align: center;
        }}
        .institutional-copy {{
            display: flex;
            flex: 1 1 auto;
            width: 100%;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .institutional-warning {{
            margin: 0;
            color: #dc2626;
            font-size: 3.2mm;
            font-weight: 700;
        }}
        .institutional-header h1 {{
            margin: 0;
            color: #09111d;
            font-size: 5.8mm;
            font-weight: 700;
            line-height: 1.18;
        }}
        .institutional-subtitle,
        .institutional-institution {{
            margin: 1mm 0 0;
            color: #2f3a4a;
            font-size: 3.1mm;
            font-weight: 600;
        }}
        .manual-header {{
            align-items: stretch;
            justify-content: flex-start;
            gap: 2.1mm;
        }}
        .manual-line {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 3mm;
            align-items: center;
            color: #111827;
            font-size: 3.1mm;
            font-weight: 700;
        }}
        .manual-line .rule,
        .general-field .rule {{
            display: block;
            height: 0.3mm;
            background: {accent};
        }}
        .general-header {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: #111827;
        }}
        .general-header h1 {{
            margin: 0;
            font-size: 6.5mm;
            font-weight: 700;
        }}
        .general-header p {{
            margin: 1mm 0 0;
            font-size: 3.2mm;
            font-weight: 600;
        }}
        .general-divider {{
            width: 70%;
            height: 0.3mm;
            margin-top: 3mm;
            background: rgba(15, 23, 42, 0.25);
        }}
        .general-form {{
            display: flex;
            flex-direction: column;
            gap: 3mm;
        }}
        .general-row {{
            display: flex;
            gap: 4mm;
            align-items: center;
        }}
        .general-field {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 2.4mm;
            align-items: center;
            flex: 1 1 0;
            color: #111827;
            font-size: 3.4mm;
            font-weight: 600;
        }}
        .panel,
        .signature,
        .answer-column {{
            border: 0.35mm solid {accent};
            background: #fff;
        }}
        .panel-title {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 9.5mm;
            padding: 1mm 1.5mm;
            background: {accent_soft};
            border-bottom: 0.35mm solid {accent};
            color: #111827;
            font-size: 3.1mm;
            font-weight: 700;
        }}
        .instructions .panel-title {{
            background: {accent};
            color: #ffffff;
        }}
        .matrix {{
            display: grid;
            width: 100%;
            height: calc(100% - 9.5mm);
        }}
        .matrix-cell {{
            display: flex;
            align-items: center;
            justify-content: center;
            border-right: 0.25mm solid rgba(0, 0, 0, 0.08);
            border-bottom: 0.25mm solid rgba(0, 0, 0, 0.08);
            background: #ffffff;
        }}
        .instructions {{
            overflow: hidden;
        }}
        .instructions ol {{
            margin: 0;
            padding: 2mm 3.2mm 3mm 6mm;
            color: #111827;
            font-size: 2.6mm;
            line-height: 1.45;
        }}
        .signature {{
            display: flex;
            align-items: flex-end;
            justify-content: center;
            padding: 0 2mm 3mm;
            color: #111827;
            font-size: 2.9mm;
        }}
        .answer-title {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: #111827;
            font-size: 4.2mm;
            font-weight: 700;
        }}
        .answer-header {{
            display: flex;
            align-items: stretch;
            background: {accent_soft};
            border-bottom: 0.35mm solid {accent};
            color: #111827;
            font-size: 2.9mm;
            font-weight: 700;
        }}
        .answer-header span,
        .answer-qnum,
        .answer-option {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .question-head,
        .answer-qnum {{
            border-right: 0.35mm solid {accent};
        }}
        .answer-rows {{
            display: grid;
        }}
        .answer-row {{
            display: flex;
            border-bottom: 0.25mm solid rgba(0, 0, 0, 0.08);
        }}
        .answer-row:last-child {{
            border-bottom: 0;
        }}
        .answer-options {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            flex: 1 1 0;
            place-items: center;
            background: #ffffff;
        }}
        .bubble {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: {bubble_preset["diameter_mm"]}mm;
            height: {bubble_preset["diameter_mm"]}mm;
            border: 0.35mm solid {accent};
            border-radius: 50%;
            background: #fff;
            color: #111827;
            font-size: {max(2.5, bubble_preset["font_size"] * 0.62):.2f}mm;
            line-height: 1;
        }}
    </style>
</head>
<body>
    <div class="omr-page">
        {''.join(blocks)}
    </div>
</body>
</html>"""


def _render_html_markers() -> str:
    positions = [
        ("", 2.5, 279),
        (" right", 197.5, 279),
        ("", 2.5, 12),
        (" right", 197.5, 12),
        ("", 2.5, 148),
        (" right", 197.5, 148),
    ]
    return "".join(
        f'<div class="box marker{side}" style="{_html_box_style_mm(x_mm, y_mm, 10, 10)}"><span></span></div>'
        for side, x_mm, y_mm in positions
    )


def _render_html_institutional_header(cfg: dict[str, Any]) -> str:
    if cfg["header_mode"] == "manual":
        lines = "".join(
            f'<div class="manual-line"><strong>{label}</strong><span class="rule"></span></div>'
            for label in MANUAL_HEADER_LABELS
        )
        return (
            f'<div class="box institutional-header manual-header" style="{_html_box_style_mm(14, 10, 182, 30)}">'
            f"{lines}</div>"
        )

    title = (cfg["header"]["title"] or "").strip()
    subtitle = (cfg["header"]["subtitle"] or "").strip()
    institution = (cfg["header"]["institution"] or "").strip()
    copy_markup = []
    if title:
        copy_markup.append(f"<h1>{html.escape(title)}</h1>")
    if subtitle:
        copy_markup.append(f'<p class="institutional-subtitle">{html.escape(subtitle)}</p>')
    if institution:
        copy_markup.append(f'<p class="institutional-institution">{html.escape(institution)}</p>')
    return (
        f'<div class="box institutional-header" style="{_html_box_style_mm(14, 10, 182, 30)}">'
        f'<p class="institutional-warning">{HEADER_WARNING_TEXT}</p>'
        f'<div class="institutional-copy">{"".join(copy_markup)}</div>'
        "</div>"
    )


def _render_html_general_header(cfg: dict[str, Any]) -> str:
    title = (cfg["header"]["title"] or "").strip()
    subtitle = (cfg["header"]["subtitle"] or "").strip()
    institution = (cfg["header"]["institution"] or "").strip()
    parts = []
    if title:
        parts.append(f"<h1>{html.escape(title)}</h1>")
    if subtitle:
        parts.append(f"<p>{html.escape(subtitle)}</p>")
    if institution:
        parts.append(f"<p>{html.escape(institution)}</p>")
    return (
        f'<div class="box general-header" style="{_html_box_style_mm(18, 12, 174, 20)}">'
        f'{"".join(parts)}'
        '<div class="general-divider"></div>'
        "</div>"
    )


def _render_html_institutional_identity(cfg: dict[str, Any], bubble_preset: dict[str, Any]) -> str:
    blocks = []
    if cfg["fields"].get("roll"):
        blocks.append(
            _render_html_matrix_panel(
                title=ROLL_NUMBER_TITLE,
                x_mm=14,
                y_mm=52,
                width_mm=42,
                height_mm=82,
                labels=list(DIGIT_LABELS),
                columns=6,
                bubble_preset=bubble_preset,
            )
        )
    if cfg["fields"].get("subject_code"):
        blocks.append(
            _render_html_matrix_panel(
                title=SUBJECT_CODE_TITLE,
                x_mm=59,
                y_mm=52,
                width_mm=38,
                height_mm=82,
                labels=list(DIGIT_LABELS),
                columns=3,
                bubble_preset=bubble_preset,
            )
        )
    if cfg["fields"].get("set_code"):
        blocks.append(
            _render_html_matrix_panel(
                title=SET_CODE_TITLE,
                x_mm=100,
                y_mm=52,
                width_mm=20,
                height_mm=82,
                labels=list(ANSWER_OPTION_LABELS),
                columns=1,
                bubble_preset=bubble_preset,
            )
        )
    blocks.append(
        f'<div class="box panel instructions" style="{_html_box_style_mm(125, 52, 70, 40)}">'
        f'<div class="panel-title">{INSTRUCTIONS_TITLE}</div>'
        "<ol>"
        + "".join(f"<li>{html.escape(item)}</li>" for item in cfg["instructions"][:6])
        + "</ol></div>"
    )
    blocks.append(
        f'<div class="box signature" style="{_html_box_style_mm(125, 97, 46, 23)}">{SIGNATURE_LABEL}</div>'
    )
    return "".join(blocks)


def _render_html_general_identity() -> str:
    rows_markup = []
    for row in GENERAL_FIELD_ROWS:
        fields = "".join(
            f'<div class="general-field"><strong>{label} :</strong><span class="rule"></span></div>'
            for label in row
        )
        rows_markup.append(f'<div class="general-row">{fields}</div>')
    return (
        f'<div class="box general-form" style="{_html_box_style_mm(18, 40, 174, 28)}">'
        f"{''.join(rows_markup)}</div>"
    )


def _render_html_matrix_panel(
    *,
    title: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    labels: list[str],
    columns: int,
    bubble_preset: dict[str, Any],
) -> str:
    del bubble_preset
    rows = len(labels)
    cells = []
    for _ in range(columns):
        for label in labels:
            display = to_bengali_numeral(label) if label.isdigit() else label
            cells.append(f'<div class="matrix-cell"><span class="bubble">{html.escape(display)}</span></div>')
    return (
        f'<div class="box panel" style="{_html_box_style_mm(x_mm, y_mm, width_mm, height_mm)}">'
        f'<div class="panel-title">{html.escape(title)}</div>'
        f'<div class="matrix" style="grid-template-columns: repeat({columns}, 1fr); grid-template-rows: repeat({rows}, 1fr);">'
        f"{''.join(cells)}</div></div>"
    )


def _render_html_answers(cfg: dict[str, Any], layout: dict[str, Any], bubble_preset: dict[str, Any]) -> str:
    del bubble_preset
    grid = layout["answer_grid"]
    total = cfg["question_count"]
    title = GENERAL_ANSWER_TITLE if cfg["sheet_variant"] == "general" else INSTITUTIONAL_ANSWER_TITLE
    html_parts = [
        f'<div class="box answer-title" style="{_html_box_style_mm(40, grid["y_mm"] - 13, 130, 8)}">{title}</div>'
    ]
    total_height = grid["header_height_mm"] + (grid["rows"] * grid["row_height_mm"])
    question_width_pct = (grid["number_width_mm"] / grid["column_width_mm"]) * 100

    for column_index in range(grid["columns"]):
        start_number = (column_index * grid["rows"]) + 1
        end_number = min(total, start_number + grid["rows"] - 1)
        rows_markup = []
        for row_index in range(grid["rows"]):
            number = start_number + row_index
            qnum = to_bengali_numeral(number) if number <= end_number else "&nbsp;"
            option_markup = "".join(
                f'<span class="answer-option"><span class="bubble">{html.escape(label)}</span></span>'
                for label in ANSWER_OPTION_LABELS
            )
            rows_markup.append(
                '<div class="answer-row">'
                f'<span class="answer-qnum" style="width:{question_width_pct:.4f}%">{qnum}</span>'
                f'<div class="answer-options">{option_markup}</div>'
                "</div>"
            )
        x_mm = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        html_parts.append(
            f'<div class="box answer-column" style="{_html_box_style_mm(x_mm, grid["y_mm"], grid["column_width_mm"], total_height)}">'
            f'<div class="answer-header" style="height:{grid["header_height_mm"]}mm">'
            f'<span class="question-head" style="width:{question_width_pct:.4f}%">{QUESTION_LABEL}</span>'
            f'<span style="flex:1 1 0">{ANSWER_LABEL}</span>'
            '</div>'
            f'<div class="answer-rows" style="height:{grid["rows"] * grid["row_height_mm"]}mm; grid-template-rows: repeat({grid["rows"]}, {grid["row_height_mm"]}mm);">'
            f"{''.join(rows_markup)}</div></div>"
        )
    return "".join(html_parts)


def _html_box_style_mm(x_mm: float, y_mm: float, width_mm: float, height_mm: float) -> str:
    return f"left:{x_mm}mm;top:{y_mm}mm;width:{width_mm}mm;height:{height_mm}mm;"


def _draw_page_background(pdf: canvas.Canvas) -> None:
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.setLineWidth(0.8)
    pdf.rect(_mm(4), _mm(4), _mm(202), _mm(289), fill=0, stroke=1)


def _draw_registration_markers(pdf: canvas.Canvas) -> None:
    marker_positions = [
        (2.5, 279),
        (197.5, 279),
        (2.5, 12),
        (197.5, 12),
        (2.5, 148),
        (197.5, 148),
    ]
    for x_mm, y_top_mm in marker_positions:
        y = _top_to_bottom(y_top_mm, 10)
        pdf.setFillColor(colors.black)
        pdf.rect(_mm(x_mm), y, _mm(10), _mm(10), fill=1, stroke=0)
        pdf.setStrokeColor(colors.white)
        pdf.setLineWidth(1.4)
        if x_mm < (PAGE_WIDTH_MM / 2):
            pdf.line(_mm(x_mm + 2.6), y + _mm(2.6), _mm(x_mm + 7.4), y + _mm(2.6))
            pdf.line(_mm(x_mm + 2.6), y + _mm(2.6), _mm(x_mm + 2.6), y + _mm(7.4))
        else:
            pdf.line(_mm(x_mm + 2.6), y + _mm(7.4), _mm(x_mm + 7.4), y + _mm(7.4))
            pdf.line(_mm(x_mm + 7.4), y + _mm(2.6), _mm(x_mm + 7.4), y + _mm(7.4))


def _draw_header(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    accent: colors.Color,
    accent_soft: colors.Color,
) -> None:
    x_mm = 14
    y_top_mm = 10
    width_mm = 182
    height_mm = 30

    pdf.setFillColor(accent_soft)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1.2)
    pdf.roundRect(
        _mm(x_mm),
        _top_to_bottom(y_top_mm, height_mm),
        _mm(width_mm),
        _mm(height_mm),
        _mm(2.5),
        fill=1,
        stroke=1,
    )

    if cfg["header_mode"] == "digital":
        title = (cfg["header"]["title"] or "").strip()
        subtitle = (cfg["header"]["subtitle"] or "").strip()
        institution = (cfg["header"]["institution"] or "").strip()

        pdf.setFillColor(colors.HexColor("#dc2626"))
        pdf.setFont(FONT_BOLD, 10)
        pdf.drawCentredString(_mm(105), _top_text_baseline(15.8, 10), HEADER_WARNING_TEXT)

        pdf.setFillColor(colors.black)
        if title:
            pdf.setFont(FONT_BOLD, 15.5)
            pdf.drawCentredString(_mm(105), _top_text_baseline(23.4, 15.5), title)
        if subtitle:
            pdf.setFont(FONT_BOLD, 9.4)
            pdf.drawCentredString(_mm(105), _top_text_baseline(29.2, 9.4), subtitle)
        if institution:
            pdf.setFont(FONT_REGULAR, 8.5)
            pdf.drawCentredString(_mm(105), _top_text_baseline(34.2, 8.5), institution)
        return

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont(FONT_BOLD, 9.5)
    for label, y_top in zip(MANUAL_HEADER_LABELS, (15.5, 23.3, 31.1)):
        pdf.drawString(_mm(22), _top_text_baseline(y_top, 9.5), label)
        pdf.setStrokeColor(accent)
        pdf.setLineWidth(1)
        pdf.line(_mm(48), _top_text_baseline(y_top - 0.7, 0), _mm(184), _top_text_baseline(y_top - 0.7, 0))


def _draw_general_header(pdf: canvas.Canvas, cfg: dict[str, Any]) -> None:
    title = (cfg["header"]["title"] or "").strip()
    subtitle = (cfg["header"]["subtitle"] or "").strip()
    institution = (cfg["header"]["institution"] or "").strip()

    pdf.setFillColor(colors.black)
    if title:
        pdf.setFont(FONT_BOLD, 15)
        pdf.drawCentredString(_mm(105), _top_text_baseline(17.5, 15), title)
    if subtitle:
        pdf.setFont(FONT_REGULAR, 9)
        pdf.drawCentredString(_mm(105), _top_text_baseline(23.8, 9), subtitle)
    if institution:
        pdf.setFont(FONT_REGULAR, 8.3)
        pdf.drawCentredString(_mm(105), _top_text_baseline(29.2, 8.3), institution)

    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.setLineWidth(0.8)
    pdf.line(_mm(58), _top_to_bottom(34, 0), _mm(152), _top_to_bottom(34, 0))


def _draw_identity_section(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    start_y_top = 52
    block_specs = []
    if cfg["fields"].get("roll"):
        block_specs.append({
            "title": ROLL_NUMBER_TITLE,
            "x_mm": 14,
            "width_mm": 42,
            "labels": list(DIGIT_LABELS),
            "columns": 6,
            "rows": 10,
        })
    if cfg["fields"].get("subject_code"):
        block_specs.append({
            "title": SUBJECT_CODE_TITLE,
            "x_mm": 59,
            "width_mm": 38,
            "labels": list(DIGIT_LABELS),
            "columns": 3,
            "rows": 10,
        })
    if cfg["fields"].get("set_code"):
        block_specs.append({
            "title": SET_CODE_TITLE,
            "x_mm": 100,
            "width_mm": 20,
            "labels": list(ANSWER_OPTION_LABELS),
            "columns": 1,
            "rows": 4,
        })

    for spec in block_specs:
        _draw_bubble_matrix_block(
            pdf,
            x_mm=spec["x_mm"],
            y_top_mm=start_y_top,
            width_mm=spec["width_mm"],
            height_mm=82,
            title=spec["title"],
            labels=spec["labels"],
            columns=spec["columns"],
            rows=spec["rows"],
            accent=accent,
            accent_soft=accent_soft,
            bubble_preset=bubble_preset,
        )

    _draw_instructions_block(
        pdf,
        x_mm=125,
        y_top_mm=start_y_top,
        width_mm=70,
        height_mm=40,
        cfg=cfg,
        accent=accent,
        accent_soft=accent_soft,
    )
    _draw_signature_box(
        pdf,
        x_mm=125,
        y_top_mm=start_y_top + 45,
        width_mm=46,
        height_mm=23,
        accent=accent,
    )


def _draw_bubble_matrix_block(
    pdf: canvas.Canvas,
    *,
    x_mm: float,
    y_top_mm: float,
    width_mm: float,
    height_mm: float,
    title: str,
    labels: list[str],
    columns: int,
    rows: int,
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    title_h_mm = 9.5
    content_h_mm = height_mm - title_h_mm
    col_w_mm = width_mm / max(columns, 1)
    row_h_mm = content_h_mm / max(rows, 1)
    bubble_d_mm = bubble_preset["diameter_mm"]

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, height_mm), _mm(width_mm), _mm(height_mm), fill=0, stroke=1)
    pdf.setFillColor(accent_soft)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, title_h_mm), _mm(width_mm), _mm(title_h_mm), fill=1, stroke=0)
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawCentredString(_mm(x_mm + width_mm / 2), _top_text_baseline(y_top_mm + 6.5, 9), title)

    pdf.setFillColor(colors.white)
    pdf.rect(
        _mm(x_mm),
        _top_to_bottom(y_top_mm + title_h_mm, content_h_mm),
        _mm(width_mm),
        _mm(content_h_mm),
        fill=1,
        stroke=0,
    )

    for col_index in range(1, columns):
        line_x = x_mm + (col_w_mm * col_index)
        pdf.line(
            _mm(line_x),
            _top_to_bottom(y_top_mm + title_h_mm, content_h_mm),
            _mm(line_x),
            _top_to_bottom(y_top_mm + title_h_mm, 0),
        )
    for row_index in range(1, rows):
        line_y_top = y_top_mm + title_h_mm + (row_h_mm * row_index)
        pdf.line(_mm(x_mm), _top_to_bottom(line_y_top, 0), _mm(x_mm + width_mm), _top_to_bottom(line_y_top, 0))

    for col in range(columns):
        for row in range(rows):
            if row >= len(labels):
                continue
            center_x = x_mm + (col * col_w_mm) + (col_w_mm / 2)
            center_y_top = y_top_mm + title_h_mm + (row * row_h_mm) + (row_h_mm / 2)
            _draw_label_bubble(
                pdf,
                center_x_mm=center_x,
                center_y_top_mm=center_y_top,
                diameter_mm=bubble_d_mm,
                label=to_bengali_numeral(labels[row]) if labels[row].isdigit() else labels[row],
                accent=accent,
                font_size=bubble_preset["font_size"],
            )


def _draw_instructions_block(
    pdf: canvas.Canvas,
    *,
    x_mm: float,
    y_top_mm: float,
    width_mm: float,
    height_mm: float,
    cfg: dict[str, Any],
    accent: colors.Color,
    accent_soft: colors.Color,
) -> None:
    title_h_mm = 8.5
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, height_mm), _mm(width_mm), _mm(height_mm), fill=0, stroke=1)
    pdf.setFillColor(accent)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, title_h_mm), _mm(width_mm), _mm(title_h_mm), fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont(FONT_BOLD, 8.5)
    pdf.drawCentredString(_mm(x_mm + (width_mm / 2)), _top_text_baseline(y_top_mm + 5.8, 8.5), INSTRUCTIONS_TITLE)

    pdf.setFillColor(accent_soft)
    pdf.rect(
        _mm(x_mm),
        _top_to_bottom(y_top_mm + title_h_mm, height_mm - title_h_mm),
        _mm(width_mm),
        _mm(height_mm - title_h_mm),
        fill=1,
        stroke=0,
    )
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_REGULAR, 7.2)
    text_y = y_top_mm + 13
    for index, instruction in enumerate(cfg["instructions"], start=1):
        if text_y > y_top_mm + height_mm - 3:
            break
        line = f"{to_bengali_numeral(index)}। {instruction}"
        pdf.drawString(_mm(x_mm + 2.5), _top_text_baseline(text_y, 7.2), line)
        text_y += 6.2


def _draw_signature_box(
    pdf: canvas.Canvas,
    *,
    x_mm: float,
    y_top_mm: float,
    width_mm: float,
    height_mm: float,
    accent: colors.Color,
) -> None:
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, height_mm), _mm(width_mm), _mm(height_mm), fill=0, stroke=1)
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawCentredString(_mm(x_mm + width_mm / 2), _top_text_baseline(y_top_mm + height_mm - 6, 8), SIGNATURE_LABEL)


def _draw_general_identity_section(
    pdf: canvas.Canvas,
    accent: colors.Color,
) -> None:
    _draw_general_line_field(pdf, label="নাম", x_mm=18, y_top_mm=42, width_mm=174, accent=accent)
    _draw_general_line_field(pdf, label="শ্রেণি", x_mm=18, y_top_mm=50, width_mm=82, accent=accent)
    _draw_general_line_field(pdf, label="সেকশন", x_mm=110, y_top_mm=50, width_mm=82, accent=accent)
    _draw_general_line_field(pdf, label="বিষয়", x_mm=18, y_top_mm=58, width_mm=82, accent=accent)
    _draw_general_line_field(pdf, label="রোল", x_mm=110, y_top_mm=58, width_mm=82, accent=accent)


def _draw_general_line_field(
    pdf: canvas.Canvas,
    *,
    label: str,
    x_mm: float,
    y_top_mm: float,
    width_mm: float,
    accent: colors.Color,
) -> None:
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont(FONT_BOLD, 9.2)
    pdf.drawString(_mm(x_mm), _top_text_baseline(y_top_mm, 9.2), f"{label}:")

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(0.8)
    label_width_mm = min(18, max(10, (len(label) * 2.3) + 3.5))
    line_x_mm = x_mm + label_width_mm
    pdf.line(_mm(line_x_mm), _top_to_bottom(y_top_mm + 0.8, 0), _mm(x_mm + width_mm), _top_to_bottom(y_top_mm + 0.8, 0))


def _draw_answer_grid(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    layout: dict[str, Any],
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    grid = layout["answer_grid"]
    total_questions = cfg["question_count"]
    number = 1
    header_label_font = 8.5 if grid["columns"] <= 3 else 7.3
    question_font = 7.9 if grid["columns"] <= 3 else 6.8
    answer_title = GENERAL_ANSWER_TITLE if cfg["sheet_variant"] == "general" else INSTITUTIONAL_ANSWER_TITLE

    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 12.5)
    pdf.drawCentredString(_mm(105), _top_text_baseline(grid["y_mm"] - 8.5, 12.5), answer_title)

    for column_index in range(grid["columns"]):
        column_x = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        _draw_answer_column(
            pdf,
            x_mm=column_x,
            y_top_mm=grid["y_mm"],
            column_width_mm=grid["column_width_mm"],
            header_height_mm=grid["header_height_mm"],
            row_height_mm=grid["row_height_mm"],
            rows=grid["rows"],
            number_width_mm=grid["number_width_mm"],
            start_number=number,
            end_number=min(total_questions, number + grid["rows"] - 1),
            accent=accent,
            accent_soft=accent_soft,
            bubble_preset=bubble_preset,
            header_label_font=header_label_font,
            question_font=question_font,
        )
        number += grid["rows"]


def _draw_answer_column(
    pdf: canvas.Canvas,
    *,
    x_mm: float,
    y_top_mm: float,
    column_width_mm: float,
    header_height_mm: float,
    row_height_mm: float,
    rows: int,
    number_width_mm: float,
    start_number: int,
    end_number: int,
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
    header_label_font: float,
    question_font: float,
) -> None:
    answer_width_mm = column_width_mm - number_width_mm
    total_h_mm = header_height_mm + (rows * row_height_mm)
    bubble_d_mm = bubble_preset["diameter_mm"]

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, total_h_mm), _mm(column_width_mm), _mm(total_h_mm), fill=0, stroke=1)

    pdf.setFillColor(accent_soft)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm, header_height_mm), _mm(column_width_mm), _mm(header_height_mm), fill=1, stroke=0)
    pdf.line(_mm(x_mm + number_width_mm), _top_to_bottom(y_top_mm, total_h_mm), _mm(x_mm + number_width_mm), _top_to_bottom(y_top_mm, 0))
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, header_label_font)
    pdf.drawCentredString(
        _mm(x_mm + (number_width_mm / 2)),
        _top_text_baseline(y_top_mm + (header_height_mm * 0.66), header_label_font),
        QUESTION_LABEL,
    )
    pdf.drawCentredString(
        _mm(x_mm + number_width_mm + (answer_width_mm / 2)),
        _top_text_baseline(y_top_mm + (header_height_mm * 0.66), header_label_font),
        ANSWER_LABEL,
    )

    for row_index in range(rows):
        current_number = start_number + row_index
        row_top = y_top_mm + header_height_mm + (row_index * row_height_mm)
        pdf.line(_mm(x_mm), _top_to_bottom(row_top, 0), _mm(x_mm + column_width_mm), _top_to_bottom(row_top, 0))
        if current_number > end_number:
            continue

        pdf.setFont(FONT_REGULAR, question_font)
        pdf.drawCentredString(
            _mm(x_mm + (number_width_mm / 2)),
            _top_text_baseline(row_top + (row_height_mm * 0.67), question_font),
            to_bengali_numeral(current_number),
        )

        start_x = x_mm + number_width_mm + 4.2
        available_width = answer_width_mm - 8.4
        step = available_width / 4
        center_y_top = row_top + (row_height_mm / 2)
        for option_index, label in enumerate(ANSWER_OPTION_LABELS):
            center_x = start_x + (step * option_index) + (step / 2)
            _draw_label_bubble(
                pdf,
                center_x_mm=center_x,
                center_y_top_mm=center_y_top,
                diameter_mm=bubble_d_mm,
                label=label,
                accent=accent,
                font_size=max(4.6, bubble_preset["font_size"] - 0.3),
            )


def _draw_label_bubble(
    pdf: canvas.Canvas,
    *,
    center_x_mm: float,
    center_y_top_mm: float,
    diameter_mm: float,
    label: str,
    accent: colors.Color,
    font_size: float,
) -> None:
    radius = _mm(diameter_mm / 2)
    center_x = _mm(center_x_mm)
    center_y = _top_to_center(center_y_top_mm)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(0.85)
    pdf.circle(center_x, center_y, radius, stroke=1, fill=0)
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_REGULAR, font_size)
    pdf.drawCentredString(center_x, center_y - (font_size * 0.18), label)


def _blend_hex(hex_a: str, hex_b: str, ratio_b: float) -> colors.Color:
    ratio_b = max(0.0, min(1.0, ratio_b))
    ratio_a = 1.0 - ratio_b
    a = colors.HexColor(hex_a)
    b = colors.HexColor(hex_b)
    return colors.Color(
        (a.red * ratio_a) + (b.red * ratio_b),
        (a.green * ratio_a) + (b.green * ratio_b),
        (a.blue * ratio_a) + (b.blue * ratio_b),
    )


def _hex_to_rgba_css(hex_color: str, alpha: float) -> str:
    clean = hex_color.replace("#", "")
    normalized = clean if len(clean) == 6 else "".join(char * 2 for char in clean)
    value = int(normalized, 16)
    red = (value >> 16) & 255
    green = (value >> 8) & 255
    blue = value & 255
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _mm(value_mm: float) -> float:
    return value_mm * mm


def _top_to_bottom(y_top_mm: float, height_mm: float) -> float:
    return A4[1] - _mm(y_top_mm + height_mm)


def _top_to_center(y_top_mm: float) -> float:
    return A4[1] - _mm(y_top_mm)


def _top_text_baseline(y_top_mm: float, font_size: float) -> float:
    return A4[1] - _mm(y_top_mm) - (font_size * 0.25)
