import sys
import types

from app.utils.omr_generator import (
    CLASS_TITLE,
    FONT_BOLD,
    FONT_REGULAR,
    HEADER_WARNING_TEXT,
    INSTITUTIONAL_BUBBLE_STROKE_HEX,
    INSTITUTIONAL_ANSWER_TITLE,
    INSTITUTIONAL_HEADER_WARNING_HEIGHT_MM,
    INSTITUTIONAL_PANEL_TITLE_HEIGHT_MM,
    INSTITUTIONAL_STRIPE_HEX,
    ROLL_NUMBER_TITLE,
    SIGNATURE_LABEL,
    _build_omr_html,
    _fit_wrapped_pdf_text,
    _generate_omr_pdf_with_weasyprint,
    _measure_pdf_text_width_mm,
    _render_html_matrix_panel,
    _register_fonts,
    _wrap_pdf_text,
    normalize_omr_template_config,
)


def test_wrap_pdf_text_keeps_bengali_instructions_inside_width():
    _register_fonts()

    lines = _wrap_pdf_text(
        "কালো বা নীল বলপেন ব্যবহার করে সম্পূর্ণ বৃত্ত পূরণ করুন",
        FONT_REGULAR,
        7.2,
        28,
    )

    assert len(lines) > 1
    assert all(_measure_pdf_text_width_mm(line, FONT_REGULAR, 7.2) <= 28.1 for line in lines)


def test_fit_wrapped_pdf_text_shrinks_narrow_box_titles_to_one_line():
    _register_fonts()

    lines, font_size, _ = _fit_wrapped_pdf_text(
        "বিষয় কোড",
        FONT_BOLD,
        9,
        6.2,
        17,
        4.8,
        leading_factor=1.05,
        max_lines=1,
    )

    assert lines == ["বিষয় কোড"]
    assert font_size <= 9
    assert _measure_pdf_text_width_mm(lines[0], FONT_BOLD, font_size) <= 17.1


def test_build_omr_html_uses_institutional_template_content():
    cfg = normalize_omr_template_config(
        {
            "question_count": 40,
            "sheet_variant": "institutional",
            "header": {
                "title": "বাংলা বহুনির্বাচনি পরীক্ষা",
                "subtitle": "শুধু একটি বৃত্ত পূরণ করুন",
                "institution": "প্রশ্ন ডট আইও",
            },
        }
    )

    html = _build_omr_html(cfg)

    assert HEADER_WARNING_TEXT in html
    assert cfg["header"]["title"] in html
    assert CLASS_TITLE in html
    assert ROLL_NUMBER_TITLE in html
    assert SIGNATURE_LABEL in html
    assert INSTITUTIONAL_ANSWER_TITLE in html
    assert "top-pattern-item" in html
    assert f"size: 215.900mm 279.400mm;" in html
    assert f"min-height: {INSTITUTIONAL_PANEL_TITLE_HEIGHT_MM}mm;" in html
    assert f"background: {INSTITUTIONAL_STRIPE_HEX};" in html
    assert f"border: 0.4mm solid {INSTITUTIONAL_BUBBLE_STROKE_HEX};" in html
    assert f"height:{INSTITUTIONAL_HEADER_WARNING_HEIGHT_MM}mm;" in html
    assert "min-height: 9.5mm;" not in html


def test_generate_omr_pdf_with_weasyprint_supports_institutional_templates(monkeypatch):
    captured = {}

    class FakeHTML:
        def __init__(self, string, base_url):
            captured["string"] = string
            captured["base_url"] = base_url

        def write_pdf(self):
            return b"%PDF-fake%"

    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasyprint.HTML = FakeHTML
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)

    cfg = normalize_omr_template_config(
        {
            "question_count": 40,
            "sheet_variant": "institutional",
            "header": {"title": "বাংলা বহুনির্বাচনি পরীক্ষা"},
        }
    )

    buffer = _generate_omr_pdf_with_weasyprint(cfg)

    assert buffer is not None
    assert buffer.getvalue() == b"%PDF-fake%"
    assert captured["base_url"]
    assert cfg["header"]["title"] in captured["string"]
    assert CLASS_TITLE in captured["string"]
    assert '<svg viewBox="0 0 100 100"' in captured["string"]
    assert f"background: {INSTITUTIONAL_STRIPE_HEX};" in captured["string"]


def test_build_omr_html_general_answer_numbers_are_centered():
    cfg = normalize_omr_template_config(
        {
            "sheet_variant": "general",
            "question_count": 50,
            "answer_columns": 2,
        }
    )

    html = _build_omr_html(cfg)

    assert ".general-answer-row {" in html
    assert "direction: ltr;" in html
    assert ".general-answer-qnum {" in html
    assert "justify-content: center;" in html
    assert "unicode-bidi: isolate;" in html


def test_render_html_matrix_panel_keeps_serial_label_rows_aligned_across_columns():
    html = _render_html_matrix_panel(
        title="রোল নম্বর",
        x_mm=14,
        y_mm=52,
        width_mm=42,
        height_mm=82,
        labels=["0", "1", "2"],
        columns=3,
        bubble_preset={"diameter_mm": 4.8, "font_size": 6.0},
    )

    assert html.count('<span class="bubble-label">০</span>') == 3
    assert html.count('<span class="bubble-label">১</span>') == 3
    assert html.count('<span class="bubble-label">২</span>') == 3
    zero = html.find('<span class="bubble-label">০</span>')
    one = html.find('<span class="bubble-label">১</span>')
    assert zero != -1
    assert one != -1
    assert zero < one
