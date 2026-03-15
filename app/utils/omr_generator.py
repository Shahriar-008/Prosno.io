"""
OMR template normalization and PDF rendering utilities.
"""
from __future__ import annotations

import copy
import io
import os
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .document_generator import to_bengali_numeral

PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297
SUPPORTED_QUESTION_COUNTS = (40, 60, 80, 100)
SUPPORTED_BUBBLE_SIZES = ("small", "large")
SUPPORTED_HEADER_MODES = ("digital", "manual")
OMR_TEMPLATE_TYPE = "exam_sheet_v1"
ANSWER_OPTION_LABELS = ("ক", "খ", "গ", "ঘ")

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

DEFAULT_OMR_CONFIG = {
    "template_type": OMR_TEMPLATE_TYPE,
    "question_count": 100,
    "theme_color": "rose",
    "bubble_size": "large",
    "header_mode": "digital",
    "header": {
        "title": "Prosno Exam OMR Sheet",
        "subtitle": "Fill the bubbles carefully and use a dark pen.",
        "institution": "Prosno.io",
    },
    "fields": {
        "roll": True,
        "set_code": True,
        "subject_code": True,
    },
    "instructions": [
        "একটি মাত্র বৃত্ত পূরণ করুন।",
        "কালো বা নীল কলম ব্যবহার করুন।",
        "ভুল চিহ্ন দিলে তা সম্পূর্ণ মুছে ফেলুন।",
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

    question_count = raw_config.get("question_count", cfg["question_count"])
    try:
        question_count = int(question_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("Question count must be a number.") from exc
    if question_count not in SUPPORTED_QUESTION_COUNTS:
        raise ValueError("Question count must be one of 40, 60, 80, or 100.")
    cfg["question_count"] = question_count

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
    _register_fonts()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    layout = LAYOUT_PRESETS[cfg["question_count"]]
    theme = THEME_COLORS[cfg["theme_color"]]
    bubble_preset = BUBBLE_SIZE_PRESETS[cfg["bubble_size"]]

    accent = colors.HexColor(theme["hex"])
    accent_soft = _blend_hex(theme["hex"], "#ffffff", 0.78)
    accent_lighter = _blend_hex(theme["hex"], "#ffffff", 0.9)

    _draw_page_background(pdf)
    _draw_registration_markers(pdf)
    _draw_header(pdf, cfg, accent, accent_soft)
    _draw_identity_section(pdf, cfg, accent, accent_soft, accent_lighter, bubble_preset)
    _draw_answer_grid(pdf, cfg, layout, accent, accent_soft, bubble_preset)
    _draw_footer(pdf, accent)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


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
        pdf.line(_mm(x_mm + 2.6), y + _mm(2.6), _mm(x_mm + 7.4), y + _mm(2.6))
        pdf.line(_mm(x_mm + 2.6), y + _mm(2.6), _mm(x_mm + 2.6), y + _mm(7.4))


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
    pdf.roundRect(_mm(x_mm), _top_to_bottom(y_top_mm, height_mm), _mm(width_mm), _mm(height_mm), _mm(2.5), fill=1, stroke=1)

    if cfg["header_mode"] == "digital":
        pdf.setFillColor(colors.HexColor("#dc2626"))
        pdf.setFont(FONT_BOLD, 10)
        pdf.drawCentredString(_mm(105), _top_text_baseline(15.8, 10), "এই বক্সে কোনও দাগ দেওয়া যাবে না")

        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_BOLD, 18)
        pdf.drawCentredString(_mm(105), _top_text_baseline(22.8, 18), cfg["header"]["title"] or "OMR Sheet")
        pdf.setFont(FONT_BOLD, 10.5)
        pdf.drawCentredString(_mm(105), _top_text_baseline(28.8, 10.5), cfg["header"]["subtitle"] or "")
        pdf.setFont(FONT_REGULAR, 9)
        pdf.drawCentredString(_mm(105), _top_text_baseline(34.5, 9), cfg["header"]["institution"] or "")
    else:
        labels = (
            ("প্রতিষ্ঠান", 15.5),
            ("পরীক্ষার নাম", 23.3),
            ("উপশিরোনাম", 31.1),
        )
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont(FONT_BOLD, 9.5)
        for label, y_top in labels:
            pdf.drawString(_mm(22), _top_text_baseline(y_top, 9.5), label)
            pdf.setStrokeColor(accent)
            pdf.setLineWidth(1)
            pdf.line(_mm(48), _top_text_baseline(y_top - 0.7, 0), _mm(184), _top_text_baseline(y_top - 0.7, 0))


def _draw_identity_section(
    pdf: canvas.Canvas,
    cfg: dict[str, Any],
    accent: colors.Color,
    accent_soft: colors.Color,
    accent_lighter: colors.Color,
    bubble_preset: dict[str, Any],
) -> None:
    start_y_top = 52
    block_specs = []
    if cfg["fields"].get("roll"):
        block_specs.append({
            "title": "রোল নম্বর",
            "x_mm": 14,
            "width_mm": 42,
            "labels": [str(i) for i in range(10)],
            "columns": 6,
            "rows": 10,
        })
    if cfg["fields"].get("subject_code"):
        block_specs.append({
            "title": "বিষয় কোড",
            "x_mm": 59,
            "width_mm": 38,
            "labels": [str(i) for i in range(10)],
            "columns": 3,
            "rows": 10,
        })
    if cfg["fields"].get("set_code"):
        block_specs.append({
            "title": "সেট কোড",
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
            accent_lighter=accent_lighter,
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
    accent_lighter: colors.Color,
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

    pdf.setFillColor(accent_lighter)
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
        pdf.line(_mm(line_x), _top_to_bottom(y_top_mm + title_h_mm, content_h_mm), _mm(line_x), _top_to_bottom(y_top_mm + title_h_mm, 0))
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
    pdf.drawCentredString(_mm(x_mm + (width_mm / 2)), _top_text_baseline(y_top_mm + 5.8, 8.5), "নির্দেশনা")

    pdf.setFillColor(accent_soft)
    pdf.rect(_mm(x_mm), _top_to_bottom(y_top_mm + title_h_mm, height_mm - title_h_mm), _mm(width_mm), _mm(height_mm - title_h_mm), fill=1, stroke=0)
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
    pdf.drawCentredString(_mm(x_mm + width_mm / 2), _top_text_baseline(y_top_mm + height_mm - 6, 8), "কক্ষ পরিদর্শকের স্বাক্ষর")


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

    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 12.5)
    pdf.drawCentredString(_mm(105), _top_text_baseline(grid["y_mm"] - 8.5, 12.5), "বহুনির্বাচনি অভীক্ষার উত্তরপত্র")

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
    pdf.drawCentredString(_mm(x_mm + (number_width_mm / 2)), _top_text_baseline(y_top_mm + (header_height_mm * 0.66), header_label_font), "প্রশ্ন")
    pdf.drawCentredString(_mm(x_mm + number_width_mm + (answer_width_mm / 2)), _top_text_baseline(y_top_mm + (header_height_mm * 0.66), header_label_font), "উত্তর")

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


def _draw_footer(pdf: canvas.Canvas, accent: colors.Color) -> None:
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1)
    pdf.roundRect(_mm(134), _top_to_bottom(276, 12), _mm(62), _mm(12), _mm(1.5), fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#059669"))
    pdf.setFont(FONT_BOLD, 8.8)
    pdf.drawCentredString(_mm(165), _top_text_baseline(283.3, 8.8), "This OMR is scannable.")


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


def _mm(value_mm: float) -> float:
    return value_mm * mm


def _top_to_bottom(y_top_mm: float, height_mm: float) -> float:
    return A4[1] - _mm(y_top_mm + height_mm)


def _top_to_center(y_top_mm: float) -> float:
    return A4[1] - _mm(y_top_mm)


def _top_text_baseline(y_top_mm: float, font_size: float) -> float:
    return A4[1] - _mm(y_top_mm) - (font_size * 0.25)
