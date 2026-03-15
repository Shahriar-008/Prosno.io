import sys
import types

from app.utils.omr_generator import (
    CLASS_TITLE,
    FONT_BOLD,
    FONT_REGULAR,
    HEADER_WARNING_TEXT,
    INSTITUTIONAL_ANSWER_TITLE,
    ROLL_NUMBER_TITLE,
    SIGNATURE_LABEL,
    _build_omr_html,
    _fit_wrapped_pdf_text,
    _generate_omr_pdf_with_weasyprint,
    _measure_pdf_text_width_mm,
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
