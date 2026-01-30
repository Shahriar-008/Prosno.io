"""
Document Generator for Question Papers
Generates DOCX files with two-column MCQ layout
"""
import os
import json
import uuid
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


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
    """Adds a single formatted question to the document object."""
    
    OMR_CIRCLE = '◯'
    FILLED_CIRCLE = '●'
    # Bengali prefixes for answer options
    bengali_prefixes = ['ক)', 'খ)', 'গ)', 'ঘ)']

    # A. Add Question Text
    p = document.add_paragraph()
    run = p.add_run(f'{q["id"]}. {q["question_text"]}')
    run.bold = True
    run.font.size = Pt(8)
    run.font.name = 'Nirmala UI'

    # B. Handle 'complex' questions
    if q.get("type") == "complex":
        for sub_opt in q.get("sub_options", []):
            p_sub = document.add_paragraph(sub_opt, style='List Bullet')
            for run in p_sub.runs:
                run.font.size = Pt(8)
                run.font.name = 'Nirmala UI'
        
        prompt_p = document.add_paragraph()
        run_prompt = prompt_p.add_run(q.get("final_prompt", "নিচের কোনটি সঠিক?"))
        run_prompt.bold = True
        run_prompt.font.size = Pt(8)
        run_prompt.font.name = 'Nirmala UI'

    # C. Add Answer Options (in a 2x2 table)
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
            
            is_correct = (show_answer is True) and (str(option_text).strip() == correct_ans)
            current_circle = FILLED_CIRCLE if is_correct else OMR_CIRCLE

            run_circle = p.add_run(current_circle)
            run_circle.font.size = Pt(8)
            run_circle.font.name = 'Nirmala UI'
            
            run_text = p.add_run(f' {prefix} {option_text}')
            run_text.font.size = Pt(8)
            run_text.font.name = 'Nirmala UI'
            
            if is_correct:
                run_text.bold = True
                run_circle.bold = True
    else:
        for j, opt in enumerate(options):
            is_correct = (show_answer is True) and (str(opt).strip() == correct_ans)
            p = document.add_paragraph()
            run = p.add_run(f'{bengali_prefixes[j]} {opt}')
            run.font.size = Pt(8)
            run.font.name = 'Nirmala UI'
            if is_correct:
                run.bold = True
                p.add_run(' (সঠিক উত্তর)').bold = True


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
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    document.save(output_path)
    return output_path


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
