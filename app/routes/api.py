"""
API routes for Prosno.io
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models import Class, Subject, Chapter, Question

api_bp = Blueprint('api', __name__)


@api_bp.route('/classes')
def get_classes():
    """Get all active classes"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'name_bn': c.name_bn,
        'level': c.level
    } for c in classes])


@api_bp.route('/subjects/<int:class_id>')
def get_subjects(class_id):
    """Get subjects for a class"""
    subjects = Subject.query.filter_by(
        class_id=class_id,
        is_active=True
    ).order_by(Subject.order).all()
    
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'name_bn': s.name_bn,
        'code': s.code
    } for s in subjects])


@api_bp.route('/chapters/<int:subject_id>')
def get_chapters(subject_id):
    """Get chapters for a subject"""
    chapters = Chapter.query.filter_by(
        subject_id=subject_id,
        is_active=True
    ).order_by(Chapter.order).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'name_bn': c.name_bn,
        'chapter_number': c.chapter_number
    } for c in chapters])


@api_bp.route('/questions/count', methods=['POST'])
def get_question_count():
    """Get question count for selected chapters"""
    data = request.get_json()
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify({'count': 0})
    
    count = Question.query.filter(
        Question.chapter_id.in_(chapter_ids),
        Question.is_active == True
    ).count()
    
    return jsonify({'count': count})


@api_bp.route('/questions/<int:chapter_id>')
def get_questions(chapter_id):
    """Get questions for a chapter"""
    questions = Question.query.filter_by(
        chapter_id=chapter_id,
        is_active=True
    ).all()
    
    return jsonify([q.to_dict() for q in questions])


@api_bp.route('/stats')
def get_stats():
    """Get overall statistics"""
    return jsonify({
        'classes': Class.query.count(),
        'subjects': Subject.query.count(),
        'chapters': Chapter.query.count(),
        'questions': Question.query.count()
    })
