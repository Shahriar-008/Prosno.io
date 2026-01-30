"""
Main routes for Prosno.io
"""
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, abort
import os

from app import db
from app.models import Class, Subject, Chapter, Question, GeneratedPaper
from app.utils.document_generator import generate_paper_from_db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/index.html', classes=classes)


@main_bp.route('/generate', methods=['GET', 'POST'])
def generate():
    """Question paper generation page"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/generate.html', classes=classes)


@main_bp.route('/get-subjects/<int:class_id>')
def get_subjects(class_id):
    """Get subjects for a class"""
    subjects = Subject.query.filter_by(
        class_id=class_id, 
        is_active=True
    ).order_by(Subject.order).all()
    
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'name_bn': s.name_bn or s.name
    } for s in subjects])


@main_bp.route('/get-chapters/<int:subject_id>')
def get_chapters(subject_id):
    """Get chapters for a subject"""
    chapters = Chapter.query.filter_by(
        subject_id=subject_id,
        is_active=True
    ).order_by(Chapter.order).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'name_bn': c.name_bn or c.name,
        'chapter_number': c.chapter_number
    } for c in chapters])


@main_bp.route('/get-question-count', methods=['POST'])
def get_question_count():
    """Get count of available questions for selected chapters"""
    data = request.get_json()
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify({'count': 0})
    
    count = Question.query.filter(
        Question.chapter_id.in_(chapter_ids),
        Question.is_active == True
    ).count()
    
    return jsonify({'count': count})


@main_bp.route('/get-questions-for-chapters', methods=['POST'])
def get_questions_for_chapters():
    """Get all questions for selected chapters"""
    data = request.get_json()
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify({'questions': []})
    
    questions = Question.query.filter(
        Question.chapter_id.in_(chapter_ids),
        Question.is_active == True
    ).order_by(Question.chapter_id, Question.id).all()
    
    # Group by chapter
    chapters_info = {}
    for q in questions:
        if q.chapter_id not in chapters_info:
            chapter = Chapter.query.get(q.chapter_id)
            chapters_info[q.chapter_id] = {
                'id': chapter.id,
                'name': chapter.name_bn or chapter.name,
                'chapter_number': chapter.chapter_number
            }
    
    return jsonify({
        'questions': [{
            'id': q.id,
            'question_text': q.question_text[:100] + '...' if len(q.question_text) > 100 else q.question_text,
            'full_text': q.question_text,
            'type': q.question_type,
            'chapter_id': q.chapter_id,
            'difficulty': q.difficulty
        } for q in questions],
        'chapters': chapters_info
    })


@main_bp.route('/generate-paper', methods=['POST'])
def generate_paper():
    """Generate question paper"""
    data = request.get_json()
    
    class_id = data.get('class_id')
    subject_id = data.get('subject_id')
    chapter_ids = data.get('chapter_ids', [])
    question_ids = data.get('question_ids', [])  # Specific question IDs if selected
    question_count = data.get('question_count', 30)
    time_minutes = data.get('time_minutes', 30)
    paper_title = data.get('title', 'Home Test')
    randomize = data.get('randomize', False)
    
    # Validate input
    if not all([class_id, subject_id, chapter_ids]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get class and subject info
    class_obj = Class.query.get(class_id)
    subject_obj = Subject.query.get(subject_id)
    
    if not class_obj or not subject_obj:
        return jsonify({'error': 'Invalid class or subject'}), 400
    
    # Fetch questions - either specific IDs or from chapters
    if question_ids:
        # User selected specific questions
        questions = Question.query.filter(
            Question.id.in_(question_ids),
            Question.is_active == True
        ).all()
        # Preserve order if not randomizing
        if not randomize:
            question_order = {qid: idx for idx, qid in enumerate(question_ids)}
            questions = sorted(questions, key=lambda q: question_order.get(q.id, 0))
        else:
            import random
            random.shuffle(questions)
    else:
        # Random selection from chapters (legacy behavior)
        questions = Question.query.filter(
            Question.chapter_id.in_(chapter_ids),
            Question.is_active == True
        ).order_by(db.func.random()).limit(question_count).all()
    
    if not questions:
        return jsonify({'error': 'No questions found for selected criteria'}), 404
    
    # Prepare paper configuration
    paper_config = {
        'title': paper_title,
        'class_name': class_obj.name_bn or class_obj.name,
        'subject_name': subject_obj.name_bn or subject_obj.name,
        'time': time_minutes,
        'marks': len(questions)
    }
    
    # Generate the papers
    output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
    student_path, teacher_path = generate_paper_from_db(
        questions, paper_config, output_folder
    )
    
    # Save to database for tracking
    paper = GeneratedPaper(
        title=paper_title,
        class_id=class_id,
        subject_id=subject_id,
        chapter_ids=chapter_ids,
        question_count=len(questions),
        time_minutes=time_minutes,
        file_path=student_path,
        file_path_answers=teacher_path
    )
    db.session.add(paper)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'paper_id': paper.id,
        'question_count': len(questions),
        'student_download': f'/download/{paper.id}/student',
        'teacher_download': f'/download/{paper.id}/teacher'
    })


@main_bp.route('/download/<int:paper_id>/<paper_type>')
def download_paper(paper_id, paper_type):
    """Download generated paper"""
    paper = GeneratedPaper.query.get_or_404(paper_id)
    
    if paper_type == 'student':
        file_path = paper.file_path
        filename = f"Question_Paper_{paper.id}.docx"
    elif paper_type == 'teacher':
        file_path = paper.file_path_answers
        filename = f"Question_Paper_With_Answers_{paper.id}.docx"
    else:
        abort(400)
    
    if not file_path or not os.path.exists(file_path):
        abort(404)
    
    # Update download count
    paper.download_count += 1
    db.session.commit()
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@main_bp.route('/about')
def about():
    """About page"""
    return render_template('main/about.html')


@main_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('main/contact.html')
