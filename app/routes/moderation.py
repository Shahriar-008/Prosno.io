"""
moderation.py — Admin routes for Teacher Question Bank moderation.

Prefix: /api/v1/admin/bank
Auth:   Flask-Login admin session (uses existing @admin_required decorator).

Endpoints:
  GET  /moderation/queue                  pending questions awaiting review
  GET  /moderation/<queue_id>             single queue item detail
  POST /moderation/<queue_id>/decide      approve or reject
  GET  /teachers                          list all teacher profiles
  GET  /teachers/<user_id>               single teacher detail + questions
  PATCH /teachers/<user_id>/trust         grant or revoke trusted status
  GET  /stats                             overall bank statistics
"""

from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import (
    BankQuestion, TeacherProfile, TeacherBadge, ModerationQueue,
    Subject, ROLE_ADMIN,
)
from app.utils.bank_helpers import (
    post_approval_refresh, refresh_profile_counters, create_notification,
)
from app.utils.cache import invalidate_browse_cache, invalidate_leaderboard
from app.utils.search import sync_question_to_index, delete_question_from_index

moderation_bp = Blueprint('moderation', __name__)


# ─── Admin guard ──────────────────────────────────────────────────────────────

def admin_only(f):
    """Require a logged-in admin (Flask-Login) session."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != ROLE_ADMIN:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─── Moderation Queue ─────────────────────────────────────────────────────────

@moderation_bp.route('/moderation/queue', methods=['GET'])
@admin_only
def get_queue():
    """List questions awaiting moderation (decision IS NULL)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    sort = request.args.get('sort', 'oldest')   # oldest | newest | priority

    q = ModerationQueue.query.filter(ModerationQueue.decision.is_(None))

    if sort == 'priority':
        q = q.order_by(ModerationQueue.priority.asc(),
                       ModerationQueue.submitted_at.asc())
    elif sort == 'newest':
        q = q.order_by(ModerationQueue.submitted_at.desc())
    else:
        q = q.order_by(ModerationQueue.submitted_at.asc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for mq in paginated.items:
        entry = mq.to_dict()
        if mq.question:
            entry['question'] = mq.question.to_dict(include_answer=True)
            # Attach teacher display_name
            profile = TeacherProfile.query.filter_by(
                user_id=mq.submitted_by
            ).first()
            entry['teacher_name'] = (profile.display_name if profile else None) or mq.submitted_by[:8] + '…'
            entry['teacher_trusted'] = profile.is_trusted if profile else False
            entry['teacher_approved_count'] = profile.approved_questions_count if profile else 0
        items.append(entry)

    return jsonify({
        'items': items,
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
    })


@moderation_bp.route('/moderation/<int:queue_id>', methods=['GET'])
@admin_only
def get_queue_item(queue_id):
    """Get a single moderation queue item with full question detail."""
    mq = db.session.get(ModerationQueue, queue_id)
    if not mq:
        return jsonify({'error': 'Queue item not found'}), 404

    data = mq.to_dict()
    if mq.question:
        data['question'] = mq.question.to_dict(include_answer=True)
        profile = TeacherProfile.query.filter_by(user_id=mq.submitted_by).first()
        if profile:
            data['teacher'] = profile.to_dict()
            data['teacher']['badges'] = [b.to_dict() for b in profile.badges.all()]
    return jsonify(data)


@moderation_bp.route('/moderation/<int:queue_id>/decide', methods=['POST'])
@admin_only
def decide_queue_item(queue_id):
    """
    Approve or reject a moderation queue item.
    Body: { "decision": "approved"|"rejected", "admin_notes": "..." }
    """
    mq = db.session.get(ModerationQueue, queue_id)
    if not mq:
        return jsonify({'error': 'Queue item not found'}), 404
    if mq.decision:
        return jsonify({'error': 'Already decided'}), 400

    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    if decision not in ('approved', 'rejected'):
        return jsonify({'error': 'decision must be approved or rejected'}), 400

    bq = mq.question
    if not bq:
        return jsonify({'error': 'Associated question not found'}), 404

    # Update moderation record
    mq.decision = decision
    mq.reviewed_by = str(current_user.id)
    mq.reviewed_at = datetime.utcnow()
    mq.admin_notes = data.get('admin_notes', '')

    # Update question state
    if decision == 'approved':
        bq.visibility = 'public'
        bq.status = 'approved'
        bq.published_at = datetime.utcnow()
        bq.rejection_reason = None
        # Sync to Meilisearch and invalidate browse cache
        sync_question_to_index(bq)
        invalidate_browse_cache(
            class_id=bq.class_id,
            subject_id=bq.subject_id,
            chapter_id=bq.chapter_id,
        )
        invalidate_leaderboard()
    else:
        bq.visibility = 'rejected'
        bq.status = 'rejected'
        bq.rejected_at = datetime.utcnow()
        bq.rejection_reason = data.get('admin_notes', '')
        # Remove from search index
        delete_question_from_index(bq.id)

    # Refresh teacher profile stats and award badges
    profile = TeacherProfile.query.filter_by(user_id=bq.teacher_id).first()
    newly_awarded = []
    if profile:
        newly_awarded = post_approval_refresh(profile, question=bq, decision=decision)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    pending_count = ModerationQueue.query.filter(
        ModerationQueue.decision.is_(None)
    ).count()

    return jsonify({
        'message': f'Question {decision}',
        'queue_id': queue_id,
        'question_id': bq.id,
        'decision': decision,
        'newly_awarded_badges': newly_awarded,
        'pending_in_queue': pending_count,
    })


# ─── Teacher Management ───────────────────────────────────────────────────────

@moderation_bp.route('/teachers', methods=['GET'])
@admin_only
def list_teachers():
    """List all teacher profiles with optional filters."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 25, type=int), 100)
    sort = request.args.get('sort', 'reputation')  # reputation | newest | published
    trusted = request.args.get('trusted')

    q = TeacherProfile.query

    if trusted == 'true':
        q = q.filter_by(is_trusted=True)
    elif trusted == 'false':
        q = q.filter_by(is_trusted=False)

    if sort == 'newest':
        q = q.order_by(TeacherProfile.created_at.desc())
    elif sort == 'published':
        q = q.order_by(TeacherProfile.questions_published.desc())
    else:
        q = q.order_by(TeacherProfile.reputation_score.desc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [p.to_dict() for p in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
    })


@moderation_bp.route('/teachers/<string:user_id>', methods=['GET'])
@admin_only
def get_teacher_detail(user_id):
    """Get full detail of a teacher: profile, badges, pending/published questions."""
    profile = TeacherProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Teacher not found'}), 404

    data = profile.to_dict()
    data['badges'] = [b.to_dict() for b in profile.badges.all()]

    # Recent questions summary
    recent = (
        BankQuestion.query
        .filter_by(teacher_id=user_id, is_active=True)
        .order_by(BankQuestion.created_at.desc())
        .limit(20)
        .all()
    )
    data['recent_questions'] = [q.to_dict(include_answer=True) for q in recent]

    # Pending moderation count
    data['pending_moderation'] = ModerationQueue.query.filter(
        ModerationQueue.submitted_by == user_id,
        ModerationQueue.decision.is_(None),
    ).count()

    return jsonify(data)


@moderation_bp.route('/teachers/<string:user_id>/trust', methods=['PATCH'])
@admin_only
def set_teacher_trust(user_id):
    """
    Grant or revoke trusted status for a teacher.
    Body: { "is_trusted": true|false, "reason": "..." }
    """
    profile = TeacherProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Teacher not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'is_trusted' not in data:
        return jsonify({'error': 'is_trusted (bool) is required'}), 400

    profile.is_trusted = bool(data['is_trusted'])
    if profile.is_trusted:
        profile.trust_granted_at = datetime.utcnow()
        profile.trust_granted_by = str(current_user.id)
        # Notify the teacher
        create_notification(
            teacher_id=profile.user_id,
            notif_type='trust_granted',
            title='You are now a Trusted Teacher! 🎉',
            body=(
                'An admin has granted you Trusted status. Your future questions will be '
                'published directly to the Question Bank without needing moderation.'
            ),
        )
    else:
        profile.trust_granted_at = None
        profile.trust_granted_by = None
        invalidate_leaderboard()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'message': f'Trust {"granted" if profile.is_trusted else "revoked"}',
        'user_id': user_id,
        'is_trusted': profile.is_trusted,
    })


# ─── Stats ────────────────────────────────────────────────────────────────────

@moderation_bp.route('/stats', methods=['GET'])
@admin_only
def bank_stats():
    """Overall question bank statistics."""
    total_q = BankQuestion.query.filter_by(is_active=True).count()
    public_q = BankQuestion.query.filter_by(visibility='public', is_active=True).count()
    pending_q = BankQuestion.query.filter_by(visibility='pending', is_active=True).count()
    private_q = BankQuestion.query.filter_by(visibility='private', is_active=True).count()
    rejected_q = BankQuestion.query.filter_by(visibility='rejected', is_active=True).count()
    total_teachers = TeacherProfile.query.count()
    trusted_teachers = TeacherProfile.query.filter_by(is_trusted=True).count()
    pending_moderation = ModerationQueue.query.filter(
        ModerationQueue.decision.is_(None)
    ).count()

    # By question type
    type_counts = dict(
        db.session.query(BankQuestion.question_type, func.count())
        .filter_by(visibility='public', is_active=True)
        .group_by(BankQuestion.question_type)
        .all()
    )

    # Total usage
    total_usage = db.session.query(
        func.sum(BankQuestion.usage_count)
    ).filter_by(visibility='public').scalar() or 0

    # ── Phase 4 extensions ───────────────────────────────────────────────

    # Daily published: last 30 days (questions approved per day)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_rows = (
        db.session.query(
            func.date(BankQuestion.published_at).label('day'),
            func.count().label('cnt'),
        )
        .filter(
            BankQuestion.visibility == 'public',
            BankQuestion.is_active == True,
            BankQuestion.published_at >= thirty_days_ago,
        )
        .group_by(func.date(BankQuestion.published_at))
        .order_by(func.date(BankQuestion.published_at))
        .all()
    )
    daily_published = [
        {'date': str(row.day), 'count': row.cnt} for row in daily_rows
    ]

    # Top 10 teachers by reputation
    top_teachers_rows = (
        TeacherProfile.query
        .order_by(TeacherProfile.reputation_score.desc())
        .limit(10)
        .all()
    )
    top_teachers = [
        {
            'user_id': tp.user_id,
            'display_name': tp.display_name or 'Anonymous',
            'questions_published': tp.questions_published,
            'reputation_score': tp.reputation_score,
        }
        for tp in top_teachers_rows
    ]

    # Top 10 subjects by public question count
    top_subjects_rows = (
        db.session.query(
            Subject.id,
            Subject.name,
            Subject.name_bn,
            func.count(BankQuestion.id).label('question_count'),
        )
        .join(BankQuestion, BankQuestion.subject_id == Subject.id)
        .filter(
            BankQuestion.visibility == 'public',
            BankQuestion.is_active == True,
        )
        .group_by(Subject.id, Subject.name, Subject.name_bn)
        .order_by(func.count(BankQuestion.id).desc())
        .limit(10)
        .all()
    )
    top_subjects = [
        {
            'id': row.id,
            'name': row.name,
            'name_bn': row.name_bn,
            'question_count': row.question_count,
        }
        for row in top_subjects_rows
    ]

    return jsonify({
        'questions': {
            'total': total_q,
            'public': public_q,
            'pending': pending_q,
            'private': private_q,
            'rejected': rejected_q,
            'by_type': type_counts,
        },
        'teachers': {
            'total': total_teachers,
            'trusted': trusted_teachers,
        },
        'moderation': {
            'pending': pending_moderation,
        },
        'engagement': {
            'total_usage': total_usage,
        },
        'daily_published': daily_published,
        'top_teachers': top_teachers,
        'top_subjects': top_subjects,
    })
