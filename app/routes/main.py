"""
Main routes for Prosno.io
"""
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, abort
import os

from app import db, csrf, limiter
from app.models import Class, Subject, Chapter, Question, GeneratedPaper
from app.utils.document_generator import generate_paper_from_db, generate_paper_to_memory
from app.utils.pdf_generator import generate_paper_to_memory_pdf

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
@csrf.exempt
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
@csrf.exempt
@limiter.limit("30 per minute")
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
@csrf.exempt
@limiter.limit("20 per minute")
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
    
    # Save to database for tracking (including question IDs for regeneration)
    paper = GeneratedPaper(
        title=paper_title,
        class_id=class_id,
        subject_id=subject_id,
        chapter_ids=chapter_ids,
        question_ids=[q.id for q in questions],  # Store exact questions used
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


@main_bp.route('/generate-custom-paper', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def generate_custom_paper():
    """Generate DOCX paper from custom JSON questions (guest users).
    
    Expects JSON body:
    {
        "questions": [
            {"question_text": "...", "answer_options": ["A","B","C","D"], "correct_answer": "A"},
            ...
        ],
        "paper_config": {
            "title": "Home Test",
            "class_name": "...",
            "subject_name": "...",
            "time": 30,
            "marks": 10
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        questions = data.get('questions', [])
        if not questions or not isinstance(questions, list):
            return jsonify({'error': 'Please provide at least one question'}), 400

        if len(questions) > 200:
            return jsonify({'error': 'Maximum 200 questions allowed'}), 400

        # Validate each question has required fields
        for i, q in enumerate(questions):
            if not q.get('question_text'):
                return jsonify({'error': f'Question {i+1} is missing question_text'}), 400
            if not q.get('answer_options') or len(q.get('answer_options', [])) < 2:
                return jsonify({'error': f'Question {i+1} needs at least 2 answer options'}), 400

        paper_config = data.get('paper_config', {})
        paper_config.setdefault('title', 'Home Test')
        paper_config.setdefault('marks', len(questions))
        paper_config.setdefault('time', len(questions))

        # Generate papers to disk
        import uuid
        output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
        student_path, teacher_path = generate_paper_from_db(
            questions, paper_config, output_folder
        )

        # Save to DB for download tracking (no class/subject IDs for custom papers)
        paper = GeneratedPaper(
            title=paper_config.get('title', 'Custom Paper'),
            question_count=len(questions),
            time_minutes=paper_config.get('time', 30),
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

    except Exception as e:
        current_app.logger.error(f"Custom paper generation error: {e}")
        return jsonify({'error': 'Failed to generate paper. Please check your data.'}), 500


@main_bp.route('/download/<int:paper_id>/<paper_type>')
def download_paper(paper_id, paper_type):
    """Download generated paper - supports DOCX (default) and PDF via ?format=pdf"""
    paper = GeneratedPaper.query.get_or_404(paper_id)
    
    if paper_type not in ('student', 'teacher'):
        abort(400, description="Invalid paper type")
    
    # Determine requested format (docx or pdf)
    output_format = request.args.get('format', 'docx').lower()
    if output_format not in ('docx', 'pdf'):
        abort(400, description="Invalid format. Use 'docx' or 'pdf'.")
    
    show_answer = (paper_type == 'teacher')
    
    # PDF is always generated on-demand from stored question IDs
    if output_format == 'pdf':
        return _serve_pdf(paper, paper_type, show_answer)
    
    # --- DOCX path (existing logic) ---
    filename = (
        f"Question_Paper_{paper.id}.docx"
        if paper_type == 'student'
        else f"Question_Paper_With_Answers_{paper.id}.docx"
    )
    
    # Try to use existing file first
    file_path = paper.file_path if paper_type == 'student' else paper.file_path_answers
    if file_path and os.path.exists(file_path):
        paper.download_count += 1
        db.session.commit()
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    
    # File doesn't exist - regenerate from stored question IDs
    question_ids = paper.question_ids or []
    
    if question_ids:
        # Use exact stored question IDs (preserves order)
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        # Preserve original order
        question_order = {qid: idx for idx, qid in enumerate(question_ids)}
        questions = sorted(questions, key=lambda q: question_order.get(q.id, 0))
    else:
        # Fallback: try to get questions from stored chapters
        chapter_ids = paper.chapter_ids or []
        if not chapter_ids:
            return jsonify({
                'error': 'Cannot regenerate paper - no question data stored.'
            }), 404
        
        questions = Question.query.filter(
            Question.chapter_id.in_(chapter_ids),
            Question.is_active == True
        ).limit(paper.question_count).all()
    
    if not questions:
        return jsonify({
            'error': 'No questions found. The data may have been deleted.'
        }), 404
    
    # Prepare config for regeneration
    class_obj = Class.query.get(paper.class_id)
    subject_obj = Subject.query.get(paper.subject_id)
    
    paper_config = {
        'title': paper.title or 'Question Paper',
        'class_name': class_obj.name_bn if class_obj else '',
        'subject_name': subject_obj.name_bn if subject_obj else '',
        'time': paper.time_minutes or len(questions),
        'marks': len(questions)
    }
    
    # Generate to memory and serve directly
    student_buffer, teacher_buffer = generate_paper_to_memory(questions, paper_config)
    buffer = teacher_buffer if show_answer else student_buffer
    
    paper.download_count += 1
    db.session.commit()
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


def _serve_pdf(paper, paper_type, show_answer):
    """Generate PDF on-demand from stored question IDs and serve it."""
    import traceback
    
    filename = (
        f"Question_Paper_{paper.id}.pdf"
        if paper_type == 'student'
        else f"Question_Paper_With_Answers_{paper.id}.pdf"
    )

    try:
        # Fetch questions from DB
        question_ids = paper.question_ids or []
        if question_ids:
            questions = Question.query.filter(Question.id.in_(question_ids)).all()
            question_order = {qid: idx for idx, qid in enumerate(question_ids)}
            questions = sorted(
                questions, key=lambda q: question_order.get(q.id, 0)
            )
        else:
            chapter_ids = paper.chapter_ids or []
            if not chapter_ids:
                return jsonify({
                    'error': 'Cannot generate PDF - no question data stored.'
                }), 404
            questions = Question.query.filter(
                Question.chapter_id.in_(chapter_ids),
                Question.is_active == True
            ).limit(paper.question_count).all()

        if not questions:
            return jsonify({
                'error': 'No questions found. The data may have been deleted.'
            }), 404

        class_obj = Class.query.get(paper.class_id)
        subject_obj = Subject.query.get(paper.subject_id)

        paper_config = {
            'title': paper.title or 'Question Paper',
            'class_name': class_obj.name_bn if class_obj else '',
            'subject_name': subject_obj.name_bn if subject_obj else '',
            'time': paper.time_minutes or len(questions),
            'marks': len(questions),
        }

        # Only generate the version we need (halves processing time)
        student_buf, teacher_buf = generate_paper_to_memory_pdf(
            questions, paper_config,
            student_only=not show_answer,
            teacher_only=show_answer
        )
        buffer = teacher_buf if show_answer else student_buf

        if buffer is None:
            current_app.logger.error(f"PDF generation returned None buffer for paper {paper.id}")
            return jsonify({'error': 'PDF generation failed - buffer is None'}), 500

        paper.download_count += 1
        db.session.commit()

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf',
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error for paper {paper.id}: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500


@main_bp.route('/about')
def about():
    """About page"""
    return render_template('main/about.html')


@main_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('main/contact.html')
