from app.utils.omr_generator import (
    FONT_BOLD,
    FONT_REGULAR,
    _fit_wrapped_pdf_text,
    _measure_pdf_text_width_mm,
    _register_fonts,
    _wrap_pdf_text,
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
