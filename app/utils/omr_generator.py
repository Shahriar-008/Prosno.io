"""
OMR template normalization and PDF rendering utilities.
"""
from __future__ import annotations

import copy
import html
import io
import logging
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
CLASS_TITLE = "\u09b6\u09cd\u09b0\u09c7\u09a3\u09bf"
CLASS_LABELS = tuple(str(i) for i in range(6, 13))

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

DEFAULT_CORNER_MARKER_SIZE_MM = 10
DEFAULT_CORNER_MARKERS = {
    "top_left": {"x_mm": 2.5, "y_mm": 12, "size_mm": DEFAULT_CORNER_MARKER_SIZE_MM, "orientation": "left"},
    "top_right": {"x_mm": 197.5, "y_mm": 12, "size_mm": DEFAULT_CORNER_MARKER_SIZE_MM, "orientation": "right"},
    "bottom_left": {"x_mm": 2.5, "y_mm": 279, "size_mm": DEFAULT_CORNER_MARKER_SIZE_MM, "orientation": "left"},
    "bottom_right": {"x_mm": 197.5, "y_mm": 279, "size_mm": DEFAULT_CORNER_MARKER_SIZE_MM, "orientation": "right"},
}
DEFAULT_HEADER_BOX = {"x_mm": 13, "y_mm": 10, "width_mm": 184, "height_mm": 30}
DEFAULT_HEADER_OFFSETS = {
    "warning_y_mm": 3.2,
    "pattern_y_mm": 8.9,
    "pattern_center_x_mm": 105,
    "copy_box_x_mm": 24,
    "copy_box_y_mm": 15.2,
    "copy_box_width_mm": 157,
    "copy_box_height_mm": 11.8,
    "manual_label_width_mm": 27,
    "manual_line_start_y_mm": 16.2,
    "manual_line_gap_mm": 4.8,
}
DEFAULT_TOP_PATTERN_STYLE = {
    "square_size_mm": 3.5,
    "circle_diameter_mm": 4.7,
    "gap_mm": 1.05,
}
DEFAULT_ANSWER_TITLE_BOX = {"x_mm": 42, "width_mm": 126, "height_mm": 8}
DEFAULT_ANSWER_GRID_X_MM = 13
DEFAULT_ANSWER_GRID_COLUMN_WIDTH_MM = 43
DEFAULT_ANSWER_GRID_GAP_MM = 4
DEFAULT_ANSWER_GRID_NUMBER_WIDTH_MM = 9.4
DEFAULT_SIDE_MARKER_STACK = {
    "bars": 4,
    "bar_width_mm": 6.6,
    "bar_height_mm": 3.2,
    "gap_mm": 0.9,
    "left_x_mm": 0.8,
    "right_x_mm": 202.6,
}


def _expand_top_marker_pattern(pattern: str) -> list[dict[str, Any]]:
    items = []
    for token in pattern.lower():
        if token in {" ", "-", "|"}:
            continue
        if token == "o":
            items.append({"shape": "circle", "filled": False})
        elif token == "b":
            items.append({"shape": "square", "filled": True})
        else:
            raise ValueError(f"Unsupported top marker token: {token}")
    return items


def _build_side_marker_stacks(y_mm: float) -> list[dict[str, Any]]:
    return [
        {
            "side": "left",
            "x_mm": DEFAULT_SIDE_MARKER_STACK["left_x_mm"],
            "y_mm": y_mm,
            "bars": DEFAULT_SIDE_MARKER_STACK["bars"],
            "bar_width_mm": DEFAULT_SIDE_MARKER_STACK["bar_width_mm"],
            "bar_height_mm": DEFAULT_SIDE_MARKER_STACK["bar_height_mm"],
            "gap_mm": DEFAULT_SIDE_MARKER_STACK["gap_mm"],
        },
        {
            "side": "right",
            "x_mm": DEFAULT_SIDE_MARKER_STACK["right_x_mm"],
            "y_mm": y_mm,
            "bars": DEFAULT_SIDE_MARKER_STACK["bars"],
            "bar_width_mm": DEFAULT_SIDE_MARKER_STACK["bar_width_mm"],
            "bar_height_mm": DEFAULT_SIDE_MARKER_STACK["bar_height_mm"],
            "gap_mm": DEFAULT_SIDE_MARKER_STACK["gap_mm"],
        },
    ]


def _build_identity_section_layout() -> dict[str, Any]:
    return {
        "matrix_blocks": [
            {
                "key": "class_track",
                "title": CLASS_TITLE,
                "x_mm": 13,
                "y_mm": 52,
                "width_mm": 24,
                "height_mm": 82,
                "columns": 1,
                "labels": list(CLASS_LABELS),
            },
            {
                "key": "roll",
                "enabled_field": "roll",
                "title": ROLL_NUMBER_TITLE,
                "x_mm": 40,
                "y_mm": 52,
                "width_mm": 50,
                "height_mm": 82,
                "columns": 6,
                "labels": list(DIGIT_LABELS),
            },
            {
                "key": "subject_code",
                "enabled_field": "subject_code",
                "title": SUBJECT_CODE_TITLE,
                "x_mm": 93,
                "y_mm": 52,
                "width_mm": 26,
                "height_mm": 82,
                "columns": 3,
                "labels": list(DIGIT_LABELS),
            },
            {
                "key": "set_code",
                "enabled_field": "set_code",
                "title": SET_CODE_TITLE,
                "x_mm": 122,
                "y_mm": 52,
                "width_mm": 24,
                "height_mm": 82,
                "columns": 1,
                "labels": list(ANSWER_OPTION_LABELS),
            },
        ],
        "instructions_block": {"x_mm": 149, "y_mm": 52, "width_mm": 48, "height_mm": 33},
        "signature_box": {"x_mm": 149, "y_mm": 93, "width_mm": 48, "height_mm": 22},
    }


def _build_institutional_template(
    *,
    question_count: int,
    pattern: str,
    answer_y_mm: float,
    header_height_mm: float,
    row_height_mm: float,
    questions_per_column: list[int],
    side_marker_y_mm: float,
    title_y_mm: float,
    header_offsets: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not questions_per_column:
        raise ValueError("Institutional templates require at least one answer column.")

    resolved_header_offsets = copy.deepcopy(DEFAULT_HEADER_OFFSETS)
    if header_offsets:
        resolved_header_offsets.update(header_offsets)

    columns = len(questions_per_column)
    rows = max(questions_per_column)

    return {
        "question_count": question_count,
        "print_dimensions": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "left_corner_marker": copy.deepcopy(DEFAULT_CORNER_MARKERS["top_left"]),
        "right_corner_marker": copy.deepcopy(DEFAULT_CORNER_MARKERS["top_right"]),
        "corner_markers": copy.deepcopy(DEFAULT_CORNER_MARKERS),
        "top_marker_pattern": {
            "pattern": pattern,
            "items": _expand_top_marker_pattern(pattern),
            "y_mm": resolved_header_offsets["pattern_y_mm"],
            "center_x_mm": resolved_header_offsets["pattern_center_x_mm"],
            "square_size_mm": DEFAULT_TOP_PATTERN_STYLE["square_size_mm"],
            "circle_diameter_mm": DEFAULT_TOP_PATTERN_STYLE["circle_diameter_mm"],
            "gap_mm": DEFAULT_TOP_PATTERN_STYLE["gap_mm"],
        },
        "side_markers": _build_side_marker_stacks(side_marker_y_mm),
        "header_box": copy.deepcopy(DEFAULT_HEADER_BOX),
        "header_offsets": resolved_header_offsets,
        "identity_section_layout": _build_identity_section_layout(),
        "answer_section_layout": {
            "title_box": {
                "x_mm": DEFAULT_ANSWER_TITLE_BOX["x_mm"],
                "y_mm": title_y_mm,
                "width_mm": DEFAULT_ANSWER_TITLE_BOX["width_mm"],
                "height_mm": DEFAULT_ANSWER_TITLE_BOX["height_mm"],
            },
            "x_mm": DEFAULT_ANSWER_GRID_X_MM,
            "y_mm": answer_y_mm,
            "columns": columns,
            "rows": rows,
            "column_width_mm": DEFAULT_ANSWER_GRID_COLUMN_WIDTH_MM,
            "column_gap_mm": DEFAULT_ANSWER_GRID_GAP_MM,
            "row_height_mm": row_height_mm,
            "header_height_mm": header_height_mm,
            "number_width_mm": DEFAULT_ANSWER_GRID_NUMBER_WIDTH_MM,
            "column_question_counts": list(questions_per_column),
        },
        "row_column_distribution": {
            "columns": columns,
            "questions_per_column": list(questions_per_column),
            "rows": rows,
        },
    }


# Edit these institutional presets to change marker patterns, offsets, and answer flow.
INSTITUTIONAL_TEMPLATE_PRESETS = {
    40: _build_institutional_template(
        question_count=40,
        pattern="obbb oobbb obo oobb",
        answer_y_mm=150,
        header_height_mm=7.0,
        row_height_mm=12.7,
        questions_per_column=[10, 10, 10, 10],
        side_marker_y_mm=160,
        title_y_mm=137,
        header_offsets={"pattern_y_mm": 8.8},
    ),
    60: _build_institutional_template(
        question_count=60,
        pattern="obbb obb obb obobbbb",
        answer_y_mm=150,
        header_height_mm=6.9,
        row_height_mm=8.55,
        questions_per_column=[15, 15, 15, 15],
        side_marker_y_mm=165,
        title_y_mm=137,
        header_offsets={"pattern_y_mm": 8.85},
    ),
    80: _build_institutional_template(
        question_count=80,
        pattern="bbob bobo bboo bbbobb",
        answer_y_mm=149,
        header_height_mm=6.8,
        row_height_mm=6.35,
        questions_per_column=[20, 20, 20, 20],
        side_marker_y_mm=170,
        title_y_mm=136,
        header_offsets={"pattern_y_mm": 8.9},
    ),
    100: _build_institutional_template(
        question_count=100,
        pattern="obbb obbbb obo oobbb",
        answer_y_mm=149,
        header_height_mm=6.6,
        row_height_mm=5.24,
        questions_per_column=[25, 25, 25, 25],
        side_marker_y_mm=175,
        title_y_mm=136,
        header_offsets={"pattern_y_mm": 8.95},
    ),
}


LAYOUT_PRESETS = {
    question_count: {
        "page": copy.deepcopy(template["print_dimensions"]),
        "answer_grid": copy.deepcopy(template["answer_section_layout"]),
    }
    for question_count, template in INSTITUTIONAL_TEMPLATE_PRESETS.items()
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
GENERAL_ANSWER_MARKER_BAND_HEIGHT_MM = 5.2

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


def get_omr_template_presets() -> dict[int, dict[str, Any]]:
    """Return the institutional template definitions used by preview and PDF rendering."""
    return copy.deepcopy(INSTITUTIONAL_TEMPLATE_PRESETS)


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


def _build_general_column_question_counts(question_count: int, answer_columns: int) -> list[int]:
    if answer_columns == GENERAL_AUTO_FLOW_COLUMN:
        counts: list[int] = []
        remaining = question_count
        while remaining > 0:
            take = min(GENERAL_MAX_ROWS_PER_AUTO_COLUMN, remaining)
            counts.append(take)
            remaining -= take
        return counts

    base, remainder = divmod(question_count, answer_columns)
    return [base + (1 if index < remainder else 0) for index in range(answer_columns)]


def _resolve_general_distribution(question_count: int, answer_columns: int) -> tuple[int, int, list[int]]:
    column_question_counts = _build_general_column_question_counts(question_count, answer_columns)
    rows = max(column_question_counts) if column_question_counts else 1
    return len(column_question_counts), rows, column_question_counts


def _build_general_layout(question_count: int, answer_columns: int) -> dict[str, Any]:
    render_columns, rows, column_question_counts = _resolve_general_distribution(question_count, answer_columns)
    spec = GENERAL_COLUMN_LAYOUTS[render_columns]
    available_rows_height = GENERAL_ANSWER_GRID_BOTTOM_MM - GENERAL_ANSWER_GRID_Y_MM - spec["header_height_mm"]
    row_height_mm = min(spec["max_row_height_mm"], available_rows_height / rows)
    return {
        "page": {"width_mm": PAGE_WIDTH_MM, "height_mm": PAGE_HEIGHT_MM},
        "answer_grid": {
            "title_box": {"x_mm": 40, "y_mm": GENERAL_ANSWER_GRID_Y_MM - 13, "width_mm": 130, "height_mm": 8},
            "x_mm": spec["x_mm"],
            "y_mm": GENERAL_ANSWER_GRID_Y_MM,
            "columns": render_columns,
            "rows": rows,
            "column_width_mm": spec["column_width_mm"],
            "column_gap_mm": spec["column_gap_mm"],
            "row_height_mm": round(row_height_mm, 2),
            "header_height_mm": spec["header_height_mm"],
            "number_width_mm": spec["number_width_mm"],
            "column_question_counts": column_question_counts,
        },
    }


def _resolve_institutional_template(question_count: int) -> dict[str, Any]:
    return copy.deepcopy(INSTITUTIONAL_TEMPLATE_PRESETS[question_count])


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
    institutional_template = (
        _resolve_institutional_template(cfg["question_count"])
        if cfg["sheet_variant"] == "institutional"
        else None
    )
    theme = THEME_COLORS[cfg["theme_color"]]
    bubble_preset = BUBBLE_SIZE_PRESETS[cfg["bubble_size"]]

    accent = colors.HexColor(theme["hex"])
    accent_soft = _blend_hex(theme["hex"], "#ffffff", 0.78)

    _draw_page_background(pdf)
    _draw_registration_markers(pdf, institutional_template)
    if cfg["sheet_variant"] == "general":
        _draw_general_header(pdf, cfg)
        _draw_general_identity_section(pdf, accent)
    else:
        _draw_header(pdf, cfg, institutional_template, accent, accent_soft)
        _draw_identity_section(pdf, cfg, institutional_template, accent, accent_soft, bubble_preset)
    _draw_answer_grid(pdf, cfg, layout, institutional_template, accent, accent_soft, bubble_preset)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def _generate_omr_pdf_with_weasyprint(cfg: dict[str, Any]) -> io.BytesIO | None:
    if cfg["sheet_variant"] == "institutional":
        return None

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
        .general-answer-frame {{
            border: 0.55mm solid #1f2937;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.03) 0%, rgba(255, 255, 255, 0) 22%);
        }}
        .general-answer-marker {{
            background: #111827;
            border-radius: 0.35mm;
        }}
        .general-answer-column {{
            background: transparent;
        }}
        .general-answer-row {{
            display: flex;
            border-bottom: 0.25mm solid rgba(15, 23, 42, 0.14);
        }}
        .general-answer-row:last-child {{
            border-bottom: 0;
        }}
        .general-answer-qnum {{
            border-right: 0.35mm solid #1f2937;
            color: #111827;
            font-weight: 700;
        }}
        .general-answer-options {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            flex: 1 1 0;
            place-items: center;
            background: transparent;
        }}
        .general-answer-column .bubble {{
            border-color: #1f2937;
            color: #111827;
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
            position: relative;
            overflow: hidden;
            width: {bubble_preset["diameter_mm"]}mm;
            height: {bubble_preset["diameter_mm"]}mm;
            border: 0.35mm solid {accent};
            border-radius: 50%;
            background: #fff;
            color: #111827;
            font-size: {max(2.5, bubble_preset["font_size"] * 0.62):.2f}mm;
            line-height: 1;
        }}
        .bubble-label {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            transform: translate(0.04em, 0.08em);
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
            cells.append(f'<div class="matrix-cell">{_render_html_bubble(display)}</div>')
    return (
        f'<div class="box panel" style="{_html_box_style_mm(x_mm, y_mm, width_mm, height_mm)}">'
        f'<div class="panel-title">{html.escape(title)}</div>'
        f'<div class="matrix" style="grid-template-columns: repeat({columns}, 1fr); grid-template-rows: repeat({rows}, 1fr);">'
        f"{''.join(cells)}</div></div>"
    )


def _get_general_answer_frame_metrics(grid: dict[str, Any]) -> dict[str, float]:
    width_mm = (grid["columns"] * grid["column_width_mm"]) + ((grid["columns"] - 1) * grid["column_gap_mm"])
    return {
        "x_mm": grid["x_mm"],
        "y_mm": grid["y_mm"],
        "width_mm": width_mm,
        "height_mm": GENERAL_ANSWER_MARKER_BAND_HEIGHT_MM + (grid["rows"] * grid["row_height_mm"]),
    }


def _get_general_answer_marker_specs(frame: dict[str, float]) -> list[dict[str, float]]:
    marker_width_mm = 2.8
    marker_height_mm = 2.8
    offsets = (
        2.1,
        frame["width_mm"] * 0.23,
        frame["width_mm"] * 0.29,
        frame["width_mm"] * 0.49,
        frame["width_mm"] - 10.2,
        frame["width_mm"] - 5.0,
    )
    return [
        {
            "x_mm": frame["x_mm"] + offset,
            "y_mm": frame["y_mm"] + 1.1,
            "width_mm": marker_width_mm,
            "height_mm": marker_height_mm,
        }
        for offset in offsets
    ]


def _render_html_bubble(label: str) -> str:
    return f'<span class="bubble"><span class="bubble-label">{html.escape(label)}</span></span>'


def _render_html_general_answers(layout: dict[str, Any]) -> str:
    grid = layout["answer_grid"]
    column_question_counts = grid.get("column_question_counts") or [grid["rows"]] * grid["columns"]
    frame = _get_general_answer_frame_metrics(grid)
    question_width_pct = (grid["number_width_mm"] / grid["column_width_mm"]) * 100
    html_parts = [
        f'<div class="box answer-title" style="{_html_box_style_mm(40, grid["y_mm"] - 13, 130, 8)}">{GENERAL_ANSWER_TITLE}</div>',
        f'<div class="box general-answer-frame" style="{_html_box_style_mm(frame["x_mm"], frame["y_mm"], frame["width_mm"], frame["height_mm"])}"></div>',
    ]
    html_parts.extend(
        f'<div class="box general-answer-marker" style="{_html_box_style_mm(marker["x_mm"], marker["y_mm"], marker["width_mm"], marker["height_mm"])}"></div>'
        for marker in _get_general_answer_marker_specs(frame)
    )

    next_number = 1
    for column_index in range(grid["columns"]):
        actual_rows = int(column_question_counts[column_index]) if column_index < len(column_question_counts) else grid["rows"]
        if not actual_rows:
            continue
        x_mm = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        y_mm = grid["y_mm"] + GENERAL_ANSWER_MARKER_BAND_HEIGHT_MM
        rows_markup = []
        for row_index in range(actual_rows):
            number = next_number + row_index
            option_markup = "".join(
                f'<span class="answer-option">{_render_html_bubble(label)}</span>'
                for label in ANSWER_OPTION_LABELS
            )
            rows_markup.append(
                '<div class="general-answer-row">'
                f'<span class="general-answer-qnum" style="width:{question_width_pct:.4f}%">{to_bengali_numeral(number)}</span>'
                f'<div class="general-answer-options">{option_markup}</div>'
                "</div>"
            )

        html_parts.append(
            f'<div class="box general-answer-column" style="{_html_box_style_mm(x_mm, y_mm, grid["column_width_mm"], actual_rows * grid["row_height_mm"])}">'
            f'<div class="answer-rows" style="height:{actual_rows * grid["row_height_mm"]}mm; grid-template-rows: repeat({actual_rows}, {grid["row_height_mm"]}mm);">'
            f'{"".join(rows_markup)}</div></div>'
        )
        next_number += actual_rows

    return "".join(html_parts)


def _render_html_answers(cfg: dict[str, Any], layout: dict[str, Any], bubble_preset: dict[str, Any]) -> str:
    del bubble_preset
    if cfg["sheet_variant"] == "general":
        return _render_html_general_answers(layout)

    grid = layout["answer_grid"]
    column_question_counts = grid.get("column_question_counts") or [grid["rows"]] * grid["columns"]
    title = GENERAL_ANSWER_TITLE if cfg["sheet_variant"] == "general" else INSTITUTIONAL_ANSWER_TITLE
    html_parts = [
        f'<div class="box answer-title" style="{_html_box_style_mm(40, grid["y_mm"] - 13, 130, 8)}">{title}</div>'
    ]
    question_width_pct = (grid["number_width_mm"] / grid["column_width_mm"]) * 100
    next_number = 1

    for column_index in range(grid["columns"]):
        actual_rows = int(column_question_counts[column_index]) if column_index < len(column_question_counts) else grid["rows"]
        total_height = grid["header_height_mm"] + (actual_rows * grid["row_height_mm"])
        rows_markup = []
        for row_index in range(actual_rows):
            number = next_number + row_index
            qnum = to_bengali_numeral(number)
            option_markup = "".join(
                f'<span class="answer-option">{_render_html_bubble(label)}</span>'
                for label in ANSWER_OPTION_LABELS
            )
            rows_markup.append(
                '<div class="answer-row">'
                f'<span class="answer-qnum" style="width:{question_width_pct:.4f}%">{qnum}</span>'
                f'<div class="answer-options">{option_markup}</div>'
                "</div>"
            )
        x_mm = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        rows_style = f'height:{actual_rows * grid["row_height_mm"]}mm;'
        if actual_rows:
            rows_style += f' grid-template-rows: repeat({actual_rows}, {grid["row_height_mm"]}mm);'
        html_parts.append(
            f'<div class="box answer-column" style="{_html_box_style_mm(x_mm, grid["y_mm"], grid["column_width_mm"], total_height)}">'
            f'<div class="answer-header" style="height:{grid["header_height_mm"]}mm">'
            f'<span class="question-head" style="width:{question_width_pct:.4f}%">{QUESTION_LABEL}</span>'
            f'<span style="flex:1 1 0">{ANSWER_LABEL}</span>'
            '</div>'
            f'<div class="answer-rows" style="{rows_style}">'
            f"{''.join(rows_markup)}</div></div>"
        )
        next_number += actual_rows
    return "".join(html_parts)


def _html_box_style_mm(x_mm: float, y_mm: float, width_mm: float, height_mm: float) -> str:
    return f"left:{x_mm}mm;top:{y_mm}mm;width:{width_mm}mm;height:{height_mm}mm;"


def _get_corner_marker_specs(template: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not template:
        return [
            {"x_mm": 2.5, "y_mm": 279, "size_mm": 10, "orientation": "left"},
            {"x_mm": 197.5, "y_mm": 279, "size_mm": 10, "orientation": "right"},
            {"x_mm": 2.5, "y_mm": 12, "size_mm": 10, "orientation": "left"},
            {"x_mm": 197.5, "y_mm": 12, "size_mm": 10, "orientation": "right"},
            {"x_mm": 2.5, "y_mm": 148, "size_mm": 10, "orientation": "left"},
            {"x_mm": 197.5, "y_mm": 148, "size_mm": 10, "orientation": "right"},
        ]

    corners = template.get("corner_markers") or DEFAULT_CORNER_MARKERS
    return [
        copy.deepcopy(corners["top_left"]),
        copy.deepcopy(corners["top_right"]),
        copy.deepcopy(corners["bottom_left"]),
        copy.deepcopy(corners["bottom_right"]),
    ]


def _get_side_marker_bars(template: dict[str, Any] | None) -> list[dict[str, float]]:
    if not template:
        return []

    bars: list[dict[str, float]] = []
    for stack in template.get("side_markers", []):
        for index in range(int(stack.get("bars", 0))):
            bars.append(
                {
                    "x_mm": float(stack["x_mm"]),
                    "y_mm": float(stack["y_mm"]) + (index * (float(stack["bar_height_mm"]) + float(stack["gap_mm"]))),
                    "width_mm": float(stack["bar_width_mm"]),
                    "height_mm": float(stack["bar_height_mm"]),
                }
            )
    return bars


def _get_top_marker_item_specs(template: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not template:
        return []

    pattern = template.get("top_marker_pattern") or {}
    items = pattern.get("items") or []
    if not items:
        return []

    square_size_mm = float(pattern.get("square_size_mm", DEFAULT_TOP_PATTERN_STYLE["square_size_mm"]))
    circle_diameter_mm = float(pattern.get("circle_diameter_mm", DEFAULT_TOP_PATTERN_STYLE["circle_diameter_mm"]))
    gap_mm = float(pattern.get("gap_mm", DEFAULT_TOP_PATTERN_STYLE["gap_mm"]))
    row_y_mm = float(template["header_box"]["y_mm"]) + float(pattern.get("y_mm", DEFAULT_HEADER_OFFSETS["pattern_y_mm"]))
    row_center_y_mm = row_y_mm + (max(square_size_mm, circle_diameter_mm) / 2)

    item_widths = [
        circle_diameter_mm if item.get("shape") == "circle" else square_size_mm
        for item in items
    ]
    total_width_mm = sum(item_widths) + (max(0, len(items) - 1) * gap_mm)
    cursor_x_mm = float(pattern.get("center_x_mm", 105)) - (total_width_mm / 2)

    specs = []
    for item, item_width_mm in zip(items, item_widths):
        specs.append(
            {
                "shape": item.get("shape", "square"),
                "filled": bool(item.get("filled", False)),
                "x_mm": cursor_x_mm,
                "y_mm": row_center_y_mm - (item_width_mm / 2),
                "size_mm": item_width_mm,
            }
        )
        cursor_x_mm += item_width_mm + gap_mm
    return specs


def _draw_corner_marker(pdf: canvas.Canvas, marker: dict[str, Any]) -> None:
    x_mm = float(marker["x_mm"])
    y_top_mm = float(marker["y_mm"])
    size_mm = float(marker.get("size_mm", DEFAULT_CORNER_MARKER_SIZE_MM))
    orientation = str(marker.get("orientation", "left")).lower()
    y = _top_to_bottom(y_top_mm, size_mm)

    pdf.setFillColor(colors.black)
    pdf.rect(_mm(x_mm), y, _mm(size_mm), _mm(size_mm), fill=1, stroke=0)
    pdf.setStrokeColor(colors.white)
    pdf.setLineWidth(1.4)

    inset_start = 2.6
    inset_end = size_mm - 2.6
    if orientation == "right":
        pdf.line(_mm(x_mm + inset_start), y + _mm(inset_end), _mm(x_mm + inset_end), y + _mm(inset_end))
        pdf.line(_mm(x_mm + inset_end), y + _mm(inset_start), _mm(x_mm + inset_end), y + _mm(inset_end))
        return

    pdf.line(_mm(x_mm + inset_start), y + _mm(inset_start), _mm(x_mm + inset_end), y + _mm(inset_start))
    pdf.line(_mm(x_mm + inset_start), y + _mm(inset_start), _mm(x_mm + inset_start), y + _mm(inset_end))


def _draw_top_marker_pattern(pdf: canvas.Canvas, template: dict[str, Any] | None) -> None:
    for item in _get_top_marker_item_specs(template):
        x_mm = float(item["x_mm"])
        y_mm = float(item["y_mm"])
        size_mm = float(item["size_mm"])
        shape = str(item["shape"])

        if shape == "circle":
            center_x = _mm(x_mm + (size_mm / 2))
            center_y = _top_to_center(y_mm + (size_mm / 2))
            pdf.setStrokeColor(colors.black)
            pdf.setLineWidth(0.6)
            pdf.circle(center_x, center_y, _mm(size_mm / 2), stroke=1, fill=0)
            continue

        pdf.setFillColor(colors.black)
        pdf.rect(_mm(x_mm), _top_to_bottom(y_mm, size_mm), _mm(size_mm), _mm(size_mm), fill=1, stroke=0)


def _draw_page_background(pdf: canvas.Canvas) -> None:
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#e5e7eb"))
    pdf.setLineWidth(0.8)
    pdf.rect(_mm(4), _mm(4), _mm(202), _mm(289), fill=0, stroke=1)


def _draw_registration_markers(pdf: canvas.Canvas, template: dict[str, Any] | None) -> None:
    for marker in _get_corner_marker_specs(template):
        _draw_corner_marker(pdf, marker)

    if not template:
        return

    pdf.setFillColor(colors.black)
    for bar in _get_side_marker_bars(template):
        pdf.rect(
            _mm(bar["x_mm"]),
            _top_to_bottom(bar["y_mm"], bar["height_mm"]),
            _mm(bar["width_mm"]),
            _mm(bar["height_mm"]),
            fill=1,
            stroke=0,
        )


def _draw_header(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    template: dict[str, Any] | None,
    accent: colors.Color,
    accent_soft: colors.Color,
) -> None:
    if template is None:
        return

    header_box = template["header_box"]
    offsets = template["header_offsets"]
    x_mm = float(header_box["x_mm"])
    y_top_mm = float(header_box["y_mm"])
    width_mm = float(header_box["width_mm"])
    height_mm = float(header_box["height_mm"])
    center_x_mm = x_mm + (width_mm / 2)

    pdf.setFillColor(accent_soft)
    pdf.rect(
        _mm(x_mm),
        _top_to_bottom(y_top_mm, height_mm),
        _mm(width_mm),
        _mm(height_mm),
        fill=1,
        stroke=0,
    )

    pdf.setFillColor(colors.HexColor("#dc2626"))
    pdf.setFont(FONT_BOLD, 9.5)
    pdf.drawCentredString(
        _mm(center_x_mm),
        _top_text_baseline(y_top_mm + float(offsets["warning_y_mm"]), 9.5),
        HEADER_WARNING_TEXT,
    )

    _draw_top_marker_pattern(pdf, template)

    if cfg["header_mode"] == "manual":
        label_x_mm = x_mm + 5.8
        line_start_x_mm = label_x_mm + float(offsets["manual_label_width_mm"])
        line_end_x_mm = x_mm + width_mm - 6.2
        manual_start_y_mm = y_top_mm + float(offsets["manual_line_start_y_mm"])
        manual_gap_mm = float(offsets["manual_line_gap_mm"])

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont(FONT_BOLD, 8.4)
        pdf.setStrokeColor(accent)
        pdf.setLineWidth(0.9)
        for index, label in enumerate(MANUAL_HEADER_LABELS):
            row_y_mm = manual_start_y_mm + (index * manual_gap_mm)
            pdf.drawString(_mm(label_x_mm), _top_text_baseline(row_y_mm, 8.4), label)
            pdf.line(
                _mm(line_start_x_mm),
                _top_to_bottom(row_y_mm - 0.3, 0),
                _mm(line_end_x_mm),
                _top_to_bottom(row_y_mm - 0.3, 0),
            )
        return

    copy_box = {
        "x_mm": x_mm + float(offsets["copy_box_x_mm"]),
        "y_mm": y_top_mm + float(offsets["copy_box_y_mm"]),
        "width_mm": float(offsets["copy_box_width_mm"]),
        "height_mm": float(offsets["copy_box_height_mm"]),
    }
    line_specs = []
    title = (cfg["header"]["title"] or "").strip()
    subtitle = (cfg["header"]["subtitle"] or "").strip()
    institution = (cfg["header"]["institution"] or "").strip()
    if title:
        line_specs.append((title, FONT_BOLD, 11.8))
    if subtitle:
        line_specs.append((subtitle, FONT_BOLD, 7.6))
    if institution:
        line_specs.append((institution, FONT_REGULAR, 7.1))

    if not line_specs:
        return

    gap_mm = 3.8 if len(line_specs) > 1 else 0
    start_y_mm = copy_box["y_mm"] + max(3.0, (copy_box["height_mm"] - (gap_mm * max(0, len(line_specs) - 1))) / 2)
    copy_center_x_mm = copy_box["x_mm"] + (copy_box["width_mm"] / 2)

    pdf.setFillColor(colors.black)
    for index, (text, font_name, font_size) in enumerate(line_specs):
        row_y_mm = start_y_mm + (index * gap_mm)
        pdf.setFont(font_name, font_size)
        pdf.drawCentredString(_mm(copy_center_x_mm), _top_text_baseline(row_y_mm, font_size), text)


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
    template: dict[str, Any] | None,
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    if template is None:
        return

    identity_layout = template["identity_section_layout"]
    for spec in identity_layout["matrix_blocks"]:
        enabled_field = spec.get("enabled_field")
        if enabled_field and not cfg["fields"].get(str(enabled_field)):
            continue
        _draw_bubble_matrix_block(
            pdf,
            x_mm=float(spec["x_mm"]),
            y_top_mm=float(spec["y_mm"]),
            width_mm=float(spec["width_mm"]),
            height_mm=float(spec["height_mm"]),
            title=str(spec["title"]),
            labels=list(spec["labels"]),
            columns=int(spec["columns"]),
            rows=len(spec["labels"]),
            accent=accent,
            accent_soft=accent_soft,
            bubble_preset=bubble_preset,
        )

    instructions_block = identity_layout["instructions_block"]
    _draw_instructions_block(
        pdf,
        x_mm=float(instructions_block["x_mm"]),
        y_top_mm=float(instructions_block["y_mm"]),
        width_mm=float(instructions_block["width_mm"]),
        height_mm=float(instructions_block["height_mm"]),
        cfg=cfg,
        accent=accent,
        accent_soft=accent_soft,
    )
    signature_box = identity_layout["signature_box"]
    _draw_signature_box(
        pdf,
        x_mm=float(signature_box["x_mm"]),
        y_top_mm=float(signature_box["y_mm"]),
        width_mm=float(signature_box["width_mm"]),
        height_mm=float(signature_box["height_mm"]),
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


def _draw_general_answer_grid(
    pdf: canvas.Canvas,
    layout: dict[str, Any],
    bubble_preset: dict[str, Any],
) -> None:
    grid = layout["answer_grid"]
    title_box = grid.get("title_box") or {"x_mm": 40, "y_mm": grid["y_mm"] - 13, "width_mm": 130, "height_mm": 8}
    frame = _get_general_answer_frame_metrics(grid)
    column_question_counts = grid.get("column_question_counts") or [grid["rows"]] * grid["columns"]
    question_font = 7.9 if grid["columns"] <= 3 else 6.8
    stroke = colors.HexColor("#1f2937")

    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 12.5)
    pdf.drawCentredString(
        _mm(title_box["x_mm"] + (title_box["width_mm"] / 2)),
        _top_text_baseline(title_box["y_mm"] + 5.5, 12.5),
        GENERAL_ANSWER_TITLE,
    )

    pdf.setStrokeColor(stroke)
    pdf.setLineWidth(1.35)
    pdf.rect(
        _mm(frame["x_mm"]),
        _top_to_bottom(frame["y_mm"], frame["height_mm"]),
        _mm(frame["width_mm"]),
        _mm(frame["height_mm"]),
        fill=0,
        stroke=1,
    )

    pdf.setFillColor(colors.HexColor("#111827"))
    for marker in _get_general_answer_marker_specs(frame):
        pdf.rect(
            _mm(marker["x_mm"]),
            _top_to_bottom(marker["y_mm"], marker["height_mm"]),
            _mm(marker["width_mm"]),
            _mm(marker["height_mm"]),
            fill=1,
            stroke=0,
        )

    next_number = 1
    for column_index in range(grid["columns"]):
        actual_rows = int(column_question_counts[column_index]) if column_index < len(column_question_counts) else grid["rows"]
        if not actual_rows:
            continue

        column_x = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        answer_width_mm = grid["column_width_mm"] - grid["number_width_mm"]
        for row_index in range(actual_rows):
            current_number = next_number + row_index
            row_top = grid["y_mm"] + GENERAL_ANSWER_MARKER_BAND_HEIGHT_MM + (row_index * grid["row_height_mm"])
            pdf.setStrokeColor(colors.HexColor("#d1d5db"))
            pdf.setLineWidth(0.7)
            pdf.line(
                _mm(column_x),
                _top_to_bottom(row_top + grid["row_height_mm"], 0),
                _mm(column_x + grid["column_width_mm"]),
                _top_to_bottom(row_top + grid["row_height_mm"], 0),
            )
            pdf.setStrokeColor(stroke)
            pdf.line(
                _mm(column_x + grid["number_width_mm"]),
                _top_to_bottom(row_top, grid["row_height_mm"]),
                _mm(column_x + grid["number_width_mm"]),
                _top_to_bottom(row_top, 0),
            )
            pdf.setFillColor(colors.black)
            pdf.setFont(FONT_REGULAR, question_font)
            pdf.drawCentredString(
                _mm(column_x + (grid["number_width_mm"] / 2)),
                _top_text_baseline(row_top + (grid["row_height_mm"] * 0.67), question_font),
                to_bengali_numeral(current_number),
            )

            start_x = column_x + grid["number_width_mm"] + 4.2
            available_width = answer_width_mm - 8.4
            step = available_width / 4
            center_y_top = row_top + (grid["row_height_mm"] / 2)
            for option_index, label in enumerate(ANSWER_OPTION_LABELS):
                center_x = start_x + (step * option_index) + (step / 2)
                _draw_label_bubble(
                    pdf,
                    center_x_mm=center_x,
                    center_y_top_mm=center_y_top,
                    diameter_mm=bubble_preset["diameter_mm"],
                    label=label,
                    accent=stroke,
                    font_size=max(4.6, bubble_preset["font_size"] - 0.3),
                )
        next_number += actual_rows


def _draw_answer_grid(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    layout: dict[str, Any],
    template: dict[str, Any] | None,
    accent: colors.Color,
    accent_soft: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    if cfg["sheet_variant"] == "general":
        _draw_general_answer_grid(pdf, layout, bubble_preset)
        return

    grid = layout["answer_grid"]
    title_box = grid.get("title_box") or {"x_mm": 40, "y_mm": grid["y_mm"] - 13, "width_mm": 130, "height_mm": 8}
    column_question_counts = grid.get("column_question_counts") or [grid["rows"]] * grid["columns"]
    number = 1
    header_label_font = 8.5 if grid["columns"] <= 3 else 7.3
    question_font = 7.9 if grid["columns"] <= 3 else 6.8
    answer_title = GENERAL_ANSWER_TITLE if cfg["sheet_variant"] == "general" else INSTITUTIONAL_ANSWER_TITLE

    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 12.5)
    pdf.drawCentredString(
        _mm(title_box["x_mm"] + (title_box["width_mm"] / 2)),
        _top_text_baseline(title_box["y_mm"] + 5.5, 12.5),
        answer_title,
    )

    for column_index in range(grid["columns"]):
        column_x = grid["x_mm"] + (column_index * (grid["column_width_mm"] + grid["column_gap_mm"]))
        actual_rows = int(column_question_counts[column_index]) if column_index < len(column_question_counts) else grid["rows"]
        _draw_answer_column(
            pdf,
            x_mm=column_x,
            y_top_mm=grid["y_mm"],
            column_width_mm=grid["column_width_mm"],
            header_height_mm=grid["header_height_mm"],
            row_height_mm=grid["row_height_mm"],
            rows=actual_rows,
            number_width_mm=grid["number_width_mm"],
            start_number=number,
            end_number=number + actual_rows - 1,
            accent=accent,
            accent_soft=accent_soft,
            bubble_preset=bubble_preset,
            header_label_font=header_label_font,
            question_font=question_font,
        )
        number += actual_rows


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
