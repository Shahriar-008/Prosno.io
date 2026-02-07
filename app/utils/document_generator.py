"""
Document Generator for Question Papers
Generates DOCX files with two-column MCQ layout with math expression support
"""
import os
import io
import re
import uuid
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# OMML namespace prefix
OMML_PREFIX = 'm'


def _make_element(tag: str) -> OxmlElement:
    """Create an OxmlElement with the given tag (use prefix like 'm:tag')."""
    return OxmlElement(tag)


def _create_omml_run(text: str) -> OxmlElement:
    """Create an OMML run element with text."""
    r = _make_element('m:r')
    t = _make_element('m:t')
    t.text = text
    r.append(t)
    return r


def _create_omml_fraction(numerator: str, denominator: str) -> OxmlElement:
    """Create an OMML fraction element (stacked fraction)."""
    # Create fraction container
    frac = _make_element('m:f')
    
    # Numerator
    num = _make_element('m:num')
    num.append(_create_omml_run(numerator))
    frac.append(num)
    
    # Denominator
    den = _make_element('m:den')
    den.append(_create_omml_run(denominator))
    frac.append(den)
    
    return frac


def _create_omml_superscript(base: str, exponent: str) -> OxmlElement:
    """Create an OMML superscript element (x²)."""
    # Create superscript container
    sSup = _make_element('m:sSup')
    
    # Base element
    e = _make_element('m:e')
    e.append(_create_omml_run(base))
    sSup.append(e)
    
    # Superscript element
    sup = _make_element('m:sup')
    sup.append(_create_omml_run(exponent))
    sSup.append(sup)
    
    return sSup


def _has_math_expression(text: str) -> bool:
    """Check if text contains math expressions that need special rendering."""
    if not text:
        return False
    # Check for fractions, exponents, or math operators
    math_indicators = ['/', '²', '³', '⁴', '⁵', '^', '√', '∛', '±', '×', '÷']
    # Also check for fraction pattern
    if re.search(r'(\([^)]+\)|[a-zA-Z0-9]+)\s*/\s*(\([^)]+\)|[a-zA-Z0-9]+)', text):
        return True
    return any(ind in text for ind in math_indicators)


def _parse_fraction(text: str) -> tuple:
    """Parse a fraction pattern from text, returns (before, numerator, denominator, after)."""
    # Pattern for fractions: (expr)/term, term/(expr), (expr)/(expr), term/term
    pattern = r'(.*?)(\([^)]+\)|[a-zA-Z0-9]+)\s*/\s*(\([^)]+\)|[a-zA-Z0-9]+)(.*)'
    match = re.match(pattern, text, re.DOTALL)
    if match:
        before, num, den, after = match.groups()
        # Strip outer parentheses if present
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        return before.strip(), num, den, after.strip()
    return None


def _convert_unicode_superscript(char: str) -> str:
    """Convert Unicode superscript characters to their numeric value."""
    superscript_map = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    }
    return superscript_map.get(char, char)


def _add_math_text_to_paragraph(paragraph, text: str, font_size=Pt(8), font_name='Nirmala UI', bold=False):
    """Add text with math expressions to a paragraph, rendering fractions and superscripts.
    
    This function parses text for math expressions and renders them using OMML.
    """
    if not text:
        return
    
    # Check for fraction pattern
    frac_result = _parse_fraction(text)
    if frac_result:
        before, num, den, after = frac_result
        
        # Add text before fraction
        if before:
            run = paragraph.add_run(before + ' ')
            run.font.size = font_size
            run.font.name = font_name
            run.bold = bold
        
        # Create and add OMML math zone with fraction
        oMath = _make_element('m:oMath')
        oMath.append(_create_omml_fraction(num, den))
        paragraph._element.append(oMath)  # Append inline math
        
        # Add text after fraction (recursively handle nested fractions)
        if after:
            _add_math_text_to_paragraph(paragraph, ' ' + after, font_size, font_name, bold)
        return
    
    # Check for superscript patterns (Unicode)
    superscript_pattern = r'([a-zA-Z0-9\(\)\+\-]+)([²³⁴⁵⁶⁷⁸⁹⁰¹]+)'
    match = re.search(superscript_pattern, text)
    if match:
        before_match = text[:match.start()]
        base = match.group(1)
        exponent = ''.join(_convert_unicode_superscript(c) for c in match.group(2))
        after_match = text[match.end():]
        
        # Add text before
        if before_match:
            run = paragraph.add_run(before_match)
            run.font.size = font_size
            run.font.name = font_name
            run.bold = bold
        
        # Create OMML superscript
        oMath = _make_element('m:oMath')
        oMath.append(_create_omml_superscript(base, exponent))
        paragraph._element.append(oMath)
        
        # Add text after (recursively)
        if after_match:
            _add_math_text_to_paragraph(paragraph, after_match, font_size, font_name, bold)
        return
    
    # Check for caret notation: x^2, x^{12}
    caret_pattern = r'([a-zA-Z0-9\(\)\+\-]+)\^(?:\{([^}]+)\}|([0-9a-zA-Z]))'
    match = re.search(caret_pattern, text)
    if match:
        before_match = text[:match.start()]
        base = match.group(1)
        exponent = match.group(2) or match.group(3)
        after_match = text[match.end():]
        
        # Add text before
        if before_match:
            run = paragraph.add_run(before_match)
            run.font.size = font_size
            run.font.name = font_name
            run.bold = bold
        
        # Create OMML superscript
        oMath = _make_element('m:oMath')
        oMath.append(_create_omml_superscript(base, exponent))
        paragraph._element.append(oMath)
        
        # Add text after (recursively)
        if after_match:
            _add_math_text_to_paragraph(paragraph, after_match, font_size, font_name, bold)
        return
    
    # No math expressions found, add as plain text
    run = paragraph.add_run(text)
    run.font.size = font_size
    run.font.name = font_name
    run.bold = bold


def to_bengali_numeral(num_str):
    """Converts an English number string to Bengali numerals."""
    english_to_bengali = {
        '0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
        '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯'
    }
    bengali_str = ""
    for char in str(num_str):
        bengali_str += english_to_bengali.get(char, char)
    return bengali_str


def add_question_to_document(document, q, show_answer=False):
    """Adds a single formatted question to the document object with math expression support."""
    
    OMR_CIRCLE = '◯'
    FILLED_CIRCLE = '●'
    # Bengali prefixes for answer options
    bengali_prefixes = ['ক)', 'খ)', 'গ)', 'ঘ)']

    # A. Add Question Text (with math support)
    p = document.add_paragraph()
    question_text = q.get("question_text", "")
    q_id = str(q.get("id", ""))
    
    if _has_math_expression(question_text):
        # Use OMML for math expressions
        run = p.add_run(f'{q_id}. ')
        run.bold = True
        run.font.size = Pt(8)
        run.font.name = 'Nirmala UI'
        _add_math_text_to_paragraph(p, question_text, font_size=Pt(8), font_name='Nirmala UI', bold=True)
    else:
        run = p.add_run(f'{q_id}. {question_text}')
        run.bold = True
        run.font.size = Pt(8)
        run.font.name = 'Nirmala UI'

    # B. Handle 'complex' questions
    if q.get("type") == "complex":
        for sub_opt in q.get("sub_options", []):
            p_sub = document.add_paragraph()
            p_sub.style = 'List Bullet'
            if _has_math_expression(sub_opt):
                _add_math_text_to_paragraph(p_sub, sub_opt, font_size=Pt(8), font_name='Nirmala UI')
            else:
                run = p_sub.add_run(sub_opt)
                run.font.size = Pt(8)
                run.font.name = 'Nirmala UI'
        
        prompt_p = document.add_paragraph()
        final_prompt = q.get("final_prompt", "নিচের কোনটি সঠিক?")
        if _has_math_expression(final_prompt):
            _add_math_text_to_paragraph(prompt_p, final_prompt, font_size=Pt(8), font_name='Nirmala UI', bold=True)
        else:
            run_prompt = prompt_p.add_run(final_prompt)
            run_prompt.bold = True
            run_prompt.font.size = Pt(8)
            run_prompt.font.name = 'Nirmala UI'

    # C. Add Answer Options (in a 2x2 table) with math support
    options = q.get("answer_options", [])
    correct_ans = str(q.get("correct_answer", "")).strip()

    if len(options) >= 4:
        opt_table = document.add_table(rows=2, cols=2)
        cell_data = [
            (opt_table.cell(0, 0), options[0], bengali_prefixes[0]),
            (opt_table.cell(0, 1), options[1], bengali_prefixes[1]),
            (opt_table.cell(1, 0), options[2], bengali_prefixes[2]),
            (opt_table.cell(1, 1), options[3], bengali_prefixes[3])
        ]
        
        for c, option_text, prefix in cell_data:
            p = c.paragraphs[0]
            p.text = ''
            
            option_str = str(option_text).strip()
            is_correct = (show_answer is True) and (option_str == correct_ans)
            current_circle = FILLED_CIRCLE if is_correct else OMR_CIRCLE

            run_circle = p.add_run(current_circle)
            run_circle.font.size = Pt(8)
            run_circle.font.name = 'Nirmala UI'
            if is_correct:
                run_circle.bold = True
            
            # Add option with math support
            if _has_math_expression(option_str):
                run_prefix = p.add_run(f' {prefix} ')
                run_prefix.font.size = Pt(8)
                run_prefix.font.name = 'Nirmala UI'
                if is_correct:
                    run_prefix.bold = True
                _add_math_text_to_paragraph(p, option_str, font_size=Pt(8), font_name='Nirmala UI', bold=is_correct)
            else:
                run_text = p.add_run(f' {prefix} {option_str}')
                run_text.font.size = Pt(8)
                run_text.font.name = 'Nirmala UI'
                if is_correct:
                    run_text.bold = True
    else:
        for j, opt in enumerate(options):
            opt_str = str(opt).strip()
            is_correct = (show_answer is True) and (opt_str == correct_ans)
            p = document.add_paragraph()
            
            prefix = bengali_prefixes[j] if j < len(bengali_prefixes) else ''
            if _has_math_expression(opt_str):
                run_prefix = p.add_run(f'{prefix} ')
                run_prefix.font.size = Pt(8)
                run_prefix.font.name = 'Nirmala UI'
                if is_correct:
                    run_prefix.bold = True
                _add_math_text_to_paragraph(p, opt_str, font_size=Pt(8), font_name='Nirmala UI', bold=is_correct)
            else:
                run = p.add_run(f'{prefix} {opt_str}')
                run.font.size = Pt(8)
                run.font.name = 'Nirmala UI'
                if is_correct:
                    run.bold = True
            
            if is_correct:
                correct_run = p.add_run(' (সঠিক উত্তর)')
                correct_run.bold = True
                correct_run.font.size = Pt(8)
                correct_run.font.name = 'Nirmala UI'


def create_question_paper(questions, output_path, paper_config, show_answer=False):
    """
    Generates a COMPACT two-column MCQ paper with a FULL-WIDTH header.
    
    Args:
        questions: List of question dictionaries
        output_path: Path to save the document
        paper_config: Dict with title, class_name, subject_name, time, marks
        show_answer: Whether to show correct answers
    """
    num_questions = len(questions)
    time_minutes = paper_config.get('time', num_questions)
    total_marks = paper_config.get('marks', num_questions)
    
    bengali_marks = to_bengali_numeral(total_marks)
    bengali_time = to_bengali_numeral(time_minutes)

    # Initialize Document & Set Margins
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    # Set Global Font & Spacing Style
    style = document.styles['Normal']
    font = style.font
    font.name = 'Nirmala UI'
    font.size = Pt(10)
    
    p_format = style.paragraph_format
    p_format.space_before = Pt(0)
    p_format.space_after = Pt(2)
    p_format.line_spacing = 1.0

    # Add Header
    title = paper_config.get('title', 'Home Test')
    document.add_heading(title, level=1).alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    class_name = paper_config.get('class_name', '')
    subject_name = paper_config.get('subject_name', '')
    
    if class_name:
        class_p = document.add_paragraph(class_name)
        class_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    if subject_name:
        subject_p = document.add_paragraph(f'বিষয়: {subject_name}')
        subject_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Time and Marks header with tab stops
    header_p = document.add_paragraph()
    p_fmt = header_p.paragraph_format
    tab_stops = p_fmt.tab_stops
    tab_stops.clear_all()
    tab_stops.add_tab_stop(
        section.page_width - section.left_margin - section.right_margin,
        WD_ALIGN_PARAGRAPH.RIGHT
    )
    header_p.add_run(f'সময়— {bengali_time} মিনিট')
    header_p.add_run('\t')
    header_p.add_run(f'পূর্ণমান— {bengali_marks}')
    
    # Add NEW Section and set 2-Column Layout
    new_section = document.add_section(WD_SECTION.CONTINUOUS)
    sectPr = new_section._sectPr
    
    cols = sectPr.find(qn('w:cols'))
    if cols is None:
        cols = OxmlElement('w:cols')
        sectPr.insert_element_before(cols, 'w:docGrid')
    
    cols.set(qn('w:num'), '2')
    cols.set(qn('w:space'), '720')

    # Populate Questions (into the new 2-column section)
    for q in questions:
        add_question_to_document(document, q, show_answer=show_answer)
        
    # Save the Document
    if output_path is None:
        # Return as BytesIO buffer for in-memory use
        buffer = io.BytesIO()
        document.save(buffer)
        buffer.seek(0)
        return buffer
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    document.save(output_path)
    return output_path


def generate_paper_to_memory(questions, paper_config):
    """
    Generate both student and teacher copies as in-memory BytesIO buffers.
    
    Args:
        questions: List of Question model objects or dicts
        paper_config: Configuration dict for the paper
        
    Returns:
        Tuple of (student_buffer, teacher_buffer) - BytesIO objects
    """
    # Convert Question models to dicts if needed, with sequential IDs
    question_list = []
    for idx, q in enumerate(questions, 1):
        if hasattr(q, 'to_dict'):
            q_dict = q.to_dict()
        else:
            q_dict = q.copy() if isinstance(q, dict) else q
        q_dict['id'] = str(idx)
        question_list.append(q_dict)
    
    # Generate Student Copy (No Answers) - in memory
    student_buffer = create_question_paper(question_list, None, paper_config, show_answer=False)
    
    # Generate Teacher Copy (With Answers) - in memory
    teacher_buffer = create_question_paper(question_list, None, paper_config, show_answer=True)
    
    return student_buffer, teacher_buffer


def generate_paper_from_db(questions, paper_config, output_folder):
    """
    Generate both student and teacher copies of question paper.
    
    Args:
        questions: List of Question model objects or dicts
        paper_config: Configuration dict for the paper
        output_folder: Folder to save generated files
        
    Returns:
        Tuple of (student_file_path, teacher_file_path)
    """
    # Convert Question models to dicts if needed, with sequential IDs
    question_list = []
    for idx, q in enumerate(questions, 1):
        if hasattr(q, 'to_dict'):
            q_dict = q.to_dict()
        else:
            q_dict = q.copy() if isinstance(q, dict) else q
        # Assign sequential ID for paper generation (matches original script)
        q_dict['id'] = str(idx)
        question_list.append(q_dict)
    
    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    base_filename = f"question_paper_{timestamp}_{unique_id}"
    
    # Ensure output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Generate Student Copy (No Answers)
    student_path = os.path.join(output_folder, f"{base_filename}_student.docx")
    create_question_paper(question_list, student_path, paper_config, show_answer=False)
    
    # Generate Teacher Copy (With Answers)
    teacher_path = os.path.join(output_folder, f"{base_filename}_teacher.docx")
    create_question_paper(question_list, teacher_path, paper_config, show_answer=True)
    
    return student_path, teacher_path
