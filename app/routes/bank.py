"""
bank.py — Teacher Question Bank API routes.

Prefix: /api/v1/bank
Auth:   All routes require a valid Supabase JWT (via X-Supabase-Auth header or
        Authorization: Bearer <token>).  The helper `require_teacher` resolves
        the user_id and auto-creates a TeacherProfile if needed.

Phase 2 additions:
  - Browse endpoints cached via Flask-Caching (Redis or SimpleCache fallback)
  - Search upgraded to try Meilisearch first, fall back to SQL ilike
  - Meilisearch sync on trusted-publish path
  - Notification endpoints (GET /notifications, POST /notifications/<id>/read,
    POST /notifications/read-all)
"""

from datetime import datetime

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func
from functools import wraps

from app import db, limiter
from app.models import (
    BankQuestion, TeacherProfile, TeacherBadge, TeacherLibrary,
    QuestionInteraction, PublishPrompt, ModerationQueue,
    TeacherNotification,
    Class, Subject, Chapter, QuestionSet,
)
from app.utils.bank_helpers import (
    compute_text_hash, find_duplicates, find_semantic_duplicates,
    get_or_create_profile,
    post_approval_refresh, recalculate_reputation, refresh_profile_counters,
    evaluate_and_award_badges,
)
from app.utils.cache import cache, invalidate_browse_cache, invalidate_leaderboard
from app.utils.search import search_bank_questions, sync_question_to_index

bank_bp = Blueprint('bank', __name__)

# ─── Auth helper ──────────────────────────────────────────────────────────────

def _get_supabase_user():
    """
    Extract user_id (Supabase UUID) from the incoming request.
    Looks for Authorization header or X-Supabase-User-Id (for testing/internal).
    Returns user_id string or None.
    """
    from flask import current_app
    # Simple header for direct user_id pass-through (set by frontend after Supabase auth)
    user_id = request.headers.get('X-Supabase-User-Id')
    if user_id:
        return user_id

    # Try Supabase JWT via the existing SupabaseAuth client
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        supabase_client = current_app.config.get('SUPABASE_CLIENT')
        if supabase_client:
            try:
                user = supabase_client.get_user(token)
                if user:
                    return user.get('id') or user.get('sub')
            except Exception:
                pass
    return None


def require_teacher(f):
    """Decorator: resolve teacher user_id, create profile if needed, set g.teacher_id / g.profile."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = _get_supabase_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        g.teacher_id = user_id
        display_name = request.headers.get('X-Supabase-Display-Name')
        g.profile = get_or_create_profile(user_id, display_name)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return f(*args, **kwargs)
    return decorated


def _question_or_404(question_id, visibility_filter=None):
    q = db.session.get(BankQuestion, question_id)
    if not q or not q.is_active:
        return None
    if visibility_filter and q.visibility != visibility_filter:
        return None
    return q


# ─── Teacher Profile ──────────────────────────────────────────────────────────

@bank_bp.route('/profile', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def get_own_profile():
    """Return own teacher profile with stats and badges."""
    profile = g.profile
    data = profile.to_dict(public=False)
    data['badges'] = [b.to_dict() for b in profile.badges.all()]
    return jsonify(data)


@bank_bp.route('/profile', methods=['PUT'])
@limiter.limit('30 per minute')
@require_teacher
def update_own_profile():
    """Update own display_name."""
    data = request.get_json(silent=True) or {}
    display_name = data.get('display_name', '').strip()
    if not display_name:
        return jsonify({'error': 'display_name is required'}), 400
    g.profile.display_name = display_name
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify(g.profile.to_dict())


@bank_bp.route('/teachers/<string:user_id>/profile', methods=['GET'])
@limiter.limit('60 per minute')
def get_public_profile(user_id):
    """Return public profile of any teacher."""
    profile = TeacherProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Teacher not found'}), 404
    data = profile.to_dict(public=True)
    data['badges'] = [b.to_dict() for b in profile.badges.all()]
    return jsonify(data)


@bank_bp.route('/leaderboard', methods=['GET'])
@limiter.limit('30 per minute')
@cache.cached(timeout=600, key_prefix='bank:leaderboard')
def get_leaderboard():
    """Return top contributors sorted by reputation score (cached 10 min)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    profiles = (
        TeacherProfile.query
        .filter(TeacherProfile.questions_published > 0)
        .order_by(TeacherProfile.reputation_score.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        'items': [p.to_dict(public=True) for p in profiles.items],
        'total': profiles.total,
        'page': page,
        'per_page': per_page,
        'pages': profiles.pages,
    })


# ─── Question Authoring ───────────────────────────────────────────────────────

@bank_bp.route('/questions', methods=['POST'])
@limiter.limit('30 per minute')
@require_teacher
def create_question():
    """Create a new private bank question."""
    data = request.get_json(silent=True) or {}

    q_type = (data.get('question_type') or '').upper()
    if q_type not in ('MCQ', 'SQ', 'CQ'):
        return jsonify({'error': 'question_type must be MCQ, SQ, or CQ'}), 400

    q_text = (data.get('question_text') or '').strip()
    if not q_text:
        return jsonify({'error': 'question_text is required'}), 400

    bq = BankQuestion(
        teacher_id=g.teacher_id,
        question_type=q_type,
        question_text=q_text,
        answer=data.get('answer'),
        explanation=data.get('explanation'),
        class_id=data.get('class_id'),
        subject_id=data.get('subject_id'),
        chapter_id=data.get('chapter_id'),
        topic=data.get('topic'),
        difficulty=data.get('difficulty', 'medium'),
        marks=data.get('marks', 1),
        board=data.get('board'),
        year=data.get('year'),
        text_hash=compute_text_hash(q_text),
        visibility='private',
        status='draft',
        origin='manual',
    )

    # MCQ extras
    if q_type == 'MCQ':
        bq.answer_options = data.get('answer_options')
        bq.correct_answer = data.get('correct_answer')

    # CQ extras
    if q_type == 'CQ':
        bq.stem = data.get('stem')
        bq.part_ka = data.get('part_ka')
        bq.part_kha = data.get('part_kha')
        bq.part_ga = data.get('part_ga')
        bq.part_gha = data.get('part_gha')
        bq.marks_ka = data.get('marks_ka')
        bq.marks_kha = data.get('marks_kha')
        bq.marks_ga = data.get('marks_ga')
        bq.marks_gha = data.get('marks_gha')

    db.session.add(bq)
    # Update created counter
    g.profile.questions_created = (g.profile.questions_created or 0) + 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify(bq.to_dict(include_answer=True)), 201


@bank_bp.route('/questions', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def list_own_questions():
    """List own bank questions with optional filters."""
    q = BankQuestion.query.filter_by(teacher_id=g.teacher_id, is_active=True)

    for param, col in [
        ('class_id', BankQuestion.class_id),
        ('subject_id', BankQuestion.subject_id),
        ('chapter_id', BankQuestion.chapter_id),
    ]:
        val = request.args.get(param, type=int)
        if val:
            q = q.filter(col == val)

    qt = request.args.get('question_type', '').upper()
    if qt:
        q = q.filter_by(question_type=qt)

    visibility = request.args.get('visibility')
    if visibility:
        q = q.filter_by(visibility=visibility)

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    paginated = q.order_by(BankQuestion.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'items': [bq.to_dict(include_answer=True) for bq in paginated.items],
        'total': paginated.total,
        'page': page,
        'per_page': per_page,
        'pages': paginated.pages,
    })


@bank_bp.route('/questions/<int:question_id>', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def get_question(question_id):
    """Get a single bank question. Owner sees full detail; others see public only."""
    bq = _question_or_404(question_id)
    if not bq:
        return jsonify({'error': 'Question not found'}), 404
    # Own question or public
    is_owner = bq.teacher_id == g.teacher_id
    if not is_owner and bq.visibility != 'public':
        return jsonify({'error': 'Question not found'}), 404
    return jsonify(bq.to_dict(include_answer=is_owner))


@bank_bp.route('/questions/<int:question_id>', methods=['PUT'])
@limiter.limit('30 per minute')
@require_teacher
def update_question(question_id):
    """Edit own question (only allowed if visibility is private or rejected)."""
    bq = BankQuestion.query.filter_by(
        id=question_id, teacher_id=g.teacher_id, is_active=True
    ).first()
    if not bq:
        return jsonify({'error': 'Question not found'}), 404
    if bq.visibility not in ('private', 'rejected'):
        return jsonify({'error': 'Only private or rejected questions can be edited'}), 400

    data = request.get_json(silent=True) or {}

    for field in ('question_text', 'answer', 'explanation', 'topic', 'difficulty',
                  'marks', 'board', 'year', 'answer_options', 'correct_answer',
                  'stem', 'part_ka', 'part_kha', 'part_ga', 'part_gha',
                  'marks_ka', 'marks_kha', 'marks_ga', 'marks_gha',
                  'class_id', 'subject_id', 'chapter_id'):
        if field in data:
            setattr(bq, field, data[field])

    if 'question_text' in data:
        bq.text_hash = compute_text_hash(data['question_text'])
    # Reset rejection if teacher edits
    if bq.visibility == 'rejected':
        bq.visibility = 'private'
        bq.status = 'draft'
        bq.rejection_reason = None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify(bq.to_dict(include_answer=True))


@bank_bp.route('/questions/<int:question_id>', methods=['DELETE'])
@limiter.limit('30 per minute')
@require_teacher
def delete_question(question_id):
    """Soft-delete own private question."""
    bq = BankQuestion.query.filter_by(
        id=question_id, teacher_id=g.teacher_id, is_active=True
    ).first()
    if not bq:
        return jsonify({'error': 'Question not found'}), 404
    if bq.visibility == 'public':
        return jsonify({'error': 'Public questions cannot be deleted'}), 400
    bq.is_active = False
    g.profile.questions_created = max(0, (g.profile.questions_created or 1) - 1)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Question deleted'})


# ─── Browsing ─────────────────────────────────────────────────────────────────

@bank_bp.route('/browse/classes', methods=['GET'])
@limiter.limit('60 per minute')
@cache.cached(timeout=3600, key_prefix='bank:browse:classes')
def browse_classes():
    """Return classes that have at least one public bank question (cached 1 h)."""
    rows = (
        db.session.query(Class, func.count(BankQuestion.id).label('count'))
        .join(BankQuestion, BankQuestion.class_id == Class.id)
        .filter(BankQuestion.visibility == 'public', BankQuestion.is_active == True)
        .group_by(Class.id)
        .order_by(Class.order)
        .all()
    )
    return jsonify([
        {'id': cls.id, 'name': cls.name, 'name_bn': cls.name_bn,
         'level': cls.level, 'question_count': cnt}
        for cls, cnt in rows
    ])


@bank_bp.route('/browse/subjects/<int:class_id>', methods=['GET'])
@limiter.limit('60 per minute')
@cache.cached(timeout=3600, make_cache_key=lambda *a, **kw: f'bank:browse:subjects:{request.view_args["class_id"]}')
def browse_subjects(class_id):
    """Return subjects for a class with public question counts (cached 1 h)."""
    rows = (
        db.session.query(Subject, func.count(BankQuestion.id).label('count'))
        .join(BankQuestion, BankQuestion.subject_id == Subject.id)
        .filter(
            Subject.class_id == class_id,
            BankQuestion.visibility == 'public',
            BankQuestion.is_active == True,
        )
        .group_by(Subject.id)
        .order_by(Subject.order)
        .all()
    )
    return jsonify([
        {'id': s.id, 'name': s.name, 'name_bn': s.name_bn, 'question_count': cnt}
        for s, cnt in rows
    ])


@bank_bp.route('/browse/chapters/<int:subject_id>', methods=['GET'])
@limiter.limit('60 per minute')
@cache.cached(timeout=3600, make_cache_key=lambda *a, **kw: f'bank:browse:chapters:{request.view_args["subject_id"]}')
def browse_chapters(subject_id):
    """Return chapters for a subject with public question counts (cached 1 h)."""
    rows = (
        db.session.query(Chapter, func.count(BankQuestion.id).label('count'))
        .join(BankQuestion, BankQuestion.chapter_id == Chapter.id)
        .filter(
            Chapter.subject_id == subject_id,
            BankQuestion.visibility == 'public',
            BankQuestion.is_active == True,
        )
        .group_by(Chapter.id)
        .order_by(Chapter.order)
        .all()
    )
    return jsonify([
        {'id': ch.id, 'name': ch.name, 'name_bn': ch.name_bn,
         'chapter_number': ch.chapter_number, 'question_count': cnt}
        for ch, cnt in rows
    ])


@bank_bp.route('/browse/chapters/<int:chapter_id>/questions', methods=['GET'])
@limiter.limit('60 per minute')
def browse_chapter_questions(chapter_id):
    """
    Return public questions in a chapter, grouped by type.
    Query params: difficulty, sort (rating|usage|newest), page, per_page
    """
    difficulty = request.args.get('difficulty')
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    q = BankQuestion.query.filter_by(
        chapter_id=chapter_id, visibility='public', is_active=True
    )
    if difficulty:
        q = q.filter_by(difficulty=difficulty)

    if sort == 'rating':
        q = q.order_by(
            (BankQuestion.rating_total / func.nullif(BankQuestion.rating_count, 0)).desc()
        )
    elif sort == 'usage':
        q = q.order_by(BankQuestion.usage_count.desc())
    else:
        q = q.order_by(BankQuestion.created_at.desc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    grouped = {'MCQ': [], 'SQ': [], 'CQ': []}
    counts = {'MCQ': 0, 'SQ': 0, 'CQ': 0}
    for bq in paginated.items:
        qt = bq.question_type
        if qt in grouped:
            grouped[qt].append(bq.to_dict())

    # Count totals (all pages)
    for qt in ('MCQ', 'SQ', 'CQ'):
        counts[qt] = BankQuestion.query.filter_by(
            chapter_id=chapter_id, visibility='public', is_active=True, question_type=qt
        ).count()

    chapter = db.session.get(Chapter, chapter_id)
    return jsonify({
        'chapter': {'id': chapter.id, 'name': chapter.name} if chapter else None,
        'grouped': grouped,
        'counts': counts,
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
    })


@bank_bp.route('/search', methods=['GET'])
@limiter.limit('30 per minute')
def search_questions():
    """
    Full-text search across public bank questions.
    Tries Meilisearch first; falls back to SQL ilike if unavailable.
    ?q=<text>&class_id=&subject_id=&chapter_id=&question_type=&difficulty=&sort=&page=&per_page=
    """
    q_text = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    sort = request.args.get('sort', 'usage')

    filters = {
        'class_id':     request.args.get('class_id', type=int),
        'subject_id':   request.args.get('subject_id', type=int),
        'chapter_id':   request.args.get('chapter_id', type=int),
        'question_type': (request.args.get('question_type', '').upper() or None),
        'difficulty':   request.args.get('difficulty') or None,
        'sort':         sort,
    }

    # ── Try Meilisearch ──────────────────────────────────────────────────────
    meili_result = search_bank_questions(q_text, filters, page, per_page)
    if meili_result is not None:
        return jsonify({
            **meili_result,
            'page': page,
            'pages': max(1, (meili_result['total'] + per_page - 1) // per_page),
            'query': q_text,
            'engine': 'meilisearch',
        })

    # ── SQL ilike fallback ───────────────────────────────────────────────────
    query = BankQuestion.query.filter_by(visibility='public', is_active=True)

    if q_text:
        query = query.filter(BankQuestion.question_text.ilike(f'%{q_text}%'))
    for key, col in [
        ('class_id',   BankQuestion.class_id),
        ('subject_id', BankQuestion.subject_id),
        ('chapter_id', BankQuestion.chapter_id),
    ]:
        if filters.get(key):
            query = query.filter(col == filters[key])
    if filters.get('question_type'):
        query = query.filter_by(question_type=filters['question_type'])
    if filters.get('difficulty'):
        query = query.filter_by(difficulty=filters['difficulty'])

    if sort == 'rating':
        query = query.order_by(
            (BankQuestion.rating_total / func.nullif(BankQuestion.rating_count, 0)).desc()
        )
    elif sort == 'newest':
        query = query.order_by(BankQuestion.created_at.desc())
    else:
        query = query.order_by(BankQuestion.usage_count.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [bq.to_dict() for bq in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
        'query': q_text,
        'engine': 'sql',
    })


# ─── Publish Workflow ─────────────────────────────────────────────────────────

@bank_bp.route('/question-sets/<int:qs_id>/publish-prompt', methods=['POST'])
@limiter.limit('20 per minute')
@require_teacher
def create_publish_prompt(qs_id):
    """
    Create a publish prompt after a teacher generates a paper from a question set.
    Body: { "question_ids": [<bank_question_id>, ...], "paper_id": <optional> }
    Only creates if question_ids are valid BankQuestions owned by this teacher.
    """
    qs = db.session.get(QuestionSet, qs_id)
    if not qs or qs.user_id != g.teacher_id:
        return jsonify({'error': 'Question set not found'}), 404

    data = request.get_json(silent=True) or {}
    raw_ids = data.get('question_ids', [])
    paper_id = data.get('paper_id')

    # Validate ids belong to teacher
    valid = BankQuestion.query.filter(
        BankQuestion.id.in_(raw_ids),
        BankQuestion.teacher_id == g.teacher_id,
        BankQuestion.is_active == True,
    ).all()
    valid_ids = [q.id for q in valid]

    if not valid_ids:
        return jsonify({'error': 'No valid bank questions found for this teacher'}), 400

    prompt = PublishPrompt(
        teacher_id=g.teacher_id,
        paper_id=paper_id,
        question_set_id=qs_id,
        question_ids=valid_ids,
    )
    db.session.add(prompt)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify(prompt.to_dict()), 201


@bank_bp.route('/publish-prompt/<int:prompt_id>', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def get_publish_prompt(prompt_id):
    """Get the state of a publish prompt, including questions to be published."""
    prompt = db.session.get(PublishPrompt, prompt_id)
    if not prompt or prompt.teacher_id != g.teacher_id:
        return jsonify({'error': 'Prompt not found'}), 404

    questions = BankQuestion.query.filter(
        BankQuestion.id.in_(prompt.question_ids or [])
    ).all()

    data = prompt.to_dict()
    data['questions'] = [q.to_dict(include_answer=True) for q in questions]
    return jsonify(data)


@bank_bp.route('/publish-prompt/<int:prompt_id>/respond', methods=['POST'])
@limiter.limit('20 per minute')
@require_teacher
def respond_to_publish_prompt(prompt_id):
    """
    Teacher responds to the post-paper publish prompt.
    Body:
      {
        "decision": "publish" | "keep_private",
        "question_ids": [<subset to publish>]   # relevant only when decision=publish
      }
    For each question to publish:
      - Runs duplicate check (warns but does NOT block)
      - Trusted teacher → visibility='public', status='approved'
      - New teacher    → visibility='pending', status='submitted', enters moderation_queue
    """
    prompt = db.session.get(PublishPrompt, prompt_id)
    if not prompt or prompt.teacher_id != g.teacher_id:
        return jsonify({'error': 'Prompt not found'}), 404
    if prompt.responded:
        return jsonify({'error': 'Prompt already responded to'}), 400

    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    if decision not in ('publish', 'keep_private'):
        return jsonify({'error': 'decision must be publish or keep_private'}), 400

    prompt.decision = decision
    prompt.responded = True
    prompt.responded_at = datetime.utcnow()

    published_ids = []
    duplicate_warnings = []

    if decision == 'publish':
        selected_ids = data.get('question_ids', prompt.question_ids or [])
        trusted = g.profile.is_trusted

        for qid in selected_ids:
            bq = db.session.get(BankQuestion, qid)
            if not bq or bq.teacher_id != g.teacher_id or not bq.is_active:
                continue
            if bq.visibility == 'public':
                continue  # already published

            # Duplicate check (semantic when available, hash fallback)
            dupes = find_semantic_duplicates(
                bq.question_text, exclude_id=bq.id,
            )
            if dupes:
                duplicate_warnings.append({
                    'question_id': bq.id,
                    'existing': [{
                        'id': d.id,
                        'question_text': d.question_text[:120],
                        'usage_count': d.usage_count,
                        'average_rating': d.average_rating,
                        'similarity': label,
                    } for d, label in dupes[:3]],
                })

            if trusted:
                bq.visibility = 'public'
                bq.status = 'approved'
                bq.published_at = datetime.utcnow()
                g.profile.questions_published = (g.profile.questions_published or 0) + 1
                g.profile.approved_questions_count = (g.profile.approved_questions_count or 0) + 1
                # Phase 2: sync to Meilisearch immediately for trusted publishes
                sync_question_to_index(bq)
                # Invalidate browse cache since counts changed
                invalidate_browse_cache(
                    class_id=bq.class_id,
                    subject_id=bq.subject_id,
                    chapter_id=bq.chapter_id,
                )
            else:
                bq.visibility = 'pending'
                bq.status = 'submitted'
                mq = ModerationQueue(question_id=bq.id, submitted_by=g.teacher_id)
                db.session.add(mq)

            published_ids.append(qid)

    prompt.published_ids = published_ids
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'message': 'Response recorded',
        'decision': decision,
        'published_ids': published_ids,
        'pending_moderation': len(published_ids) if not g.profile.is_trusted and decision == 'publish' else 0,
        'duplicate_warnings': duplicate_warnings,
    })


@bank_bp.route('/questions/<int:question_id>/duplicate-check', methods=['GET'])
@limiter.limit('30 per minute')
@require_teacher
def duplicate_check(question_id):
    """Check if a bank question has duplicates in the public bank."""
    bq = BankQuestion.query.filter_by(
        id=question_id, teacher_id=g.teacher_id, is_active=True
    ).first()
    if not bq:
        return jsonify({'error': 'Question not found'}), 404
    dupes = find_semantic_duplicates(bq.question_text, exclude_id=bq.id)
    return jsonify({
        'has_duplicates': bool(dupes),
        'count': len(dupes),
        'similar': [{
            'id': d.id,
            'question_text': d.question_text[:200],
            'usage_count': d.usage_count,
            'average_rating': d.average_rating,
            'similarity': label,
        } for d, label in dupes[:5]],
    })


# ─── Interactions ─────────────────────────────────────────────────────────────

def _record_interaction(question_id, action_type, extra=None):
    """
    Record or update a QuestionInteraction.
    For 'rated' action, extra should be {'rating_value': N}.
    Returns (BankQuestion, error_response | None).
    """
    bq = BankQuestion.query.filter_by(
        id=question_id, visibility='public', is_active=True
    ).first()
    if not bq:
        return None, (jsonify({'error': 'Question not found'}), 404)

    existing = QuestionInteraction.query.filter_by(
        question_id=question_id,
        teacher_id=g.teacher_id,
        action_type=action_type,
    ).first()

    if existing:
        if action_type == 'rated' and extra:
            # Update existing rating
            old_val = existing.rating_value or 0
            existing.rating_value = extra['rating_value']
            bq.rating_total = max(0, (bq.rating_total or 0) - old_val + extra['rating_value'])
        return bq, None

    qi = QuestionInteraction(
        question_id=question_id,
        teacher_id=g.teacher_id,
        action_type=action_type,
        **(extra or {}),
    )
    db.session.add(qi)

    if action_type == 'used':
        bq.usage_count = (bq.usage_count or 0) + 1
    elif action_type == 'rated' and extra:
        bq.rating_total = (bq.rating_total or 0) + extra['rating_value']
        bq.rating_count = (bq.rating_count or 0) + 1

    return bq, None


@bank_bp.route('/questions/<int:question_id>/use', methods=['POST'])
@limiter.limit('30 per minute')
@require_teacher
def use_question(question_id):
    """Record that the teacher used this question in a paper/set."""
    data = request.get_json(silent=True) or {}
    bq, err = _record_interaction(question_id, 'used', {
        'question_set_id': data.get('question_set_id'),
        'paper_id': data.get('paper_id'),
    })
    if err:
        return err
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Usage recorded', 'usage_count': bq.usage_count})


@bank_bp.route('/questions/<int:question_id>/save', methods=['POST'])
@limiter.limit('30 per minute')
@require_teacher
def save_question(question_id):
    """Save a public question to personal library."""
    bq = BankQuestion.query.filter_by(
        id=question_id, visibility='public', is_active=True
    ).first()
    if not bq:
        return jsonify({'error': 'Question not found'}), 404

    existing = TeacherLibrary.query.filter_by(
        teacher_id=g.teacher_id, question_id=question_id
    ).first()
    if existing:
        return jsonify({'message': 'Already saved'}), 200

    data = request.get_json(silent=True) or {}
    lib = TeacherLibrary(
        teacher_id=g.teacher_id,
        question_id=question_id,
        notes=data.get('notes'),
    )
    db.session.add(lib)
    _record_interaction(question_id, 'saved')
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Saved to library'}), 201


@bank_bp.route('/questions/<int:question_id>/save', methods=['DELETE'])
@limiter.limit('30 per minute')
@require_teacher
def unsave_question(question_id):
    """Remove a question from personal library."""
    lib = TeacherLibrary.query.filter_by(
        teacher_id=g.teacher_id, question_id=question_id
    ).first()
    if not lib:
        return jsonify({'error': 'Not in library'}), 404
    db.session.delete(lib)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Removed from library'})


@bank_bp.route('/questions/<int:question_id>/rate', methods=['POST'])
@limiter.limit('20 per minute')
@require_teacher
def rate_question(question_id):
    """Rate a question 1–5 stars."""
    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({'error': 'rating must be an integer 1–5'}), 400

    bq, err = _record_interaction(question_id, 'rated', {'rating_value': rating})
    if err:
        return err
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({
        'message': 'Rating recorded',
        'average_rating': bq.average_rating,
        'rating_count': bq.rating_count,
    })


@bank_bp.route('/questions/<int:question_id>/copy', methods=['POST'])
@limiter.limit('20 per minute')
@require_teacher
def copy_question(question_id):
    """Create an editable private copy of a public question."""
    bq = BankQuestion.query.filter_by(
        id=question_id, visibility='public', is_active=True
    ).first()
    if not bq:
        return jsonify({'error': 'Question not found'}), 404

    copy = BankQuestion(
        teacher_id=g.teacher_id,
        question_type=bq.question_type,
        question_text=bq.question_text,
        answer=bq.answer,
        explanation=bq.explanation,
        class_id=bq.class_id,
        subject_id=bq.subject_id,
        chapter_id=bq.chapter_id,
        topic=bq.topic,
        difficulty=bq.difficulty,
        marks=bq.marks,
        board=bq.board,
        year=bq.year,
        answer_options=bq.answer_options,
        correct_answer=bq.correct_answer,
        stem=bq.stem,
        part_ka=bq.part_ka,
        part_kha=bq.part_kha,
        part_ga=bq.part_ga,
        part_gha=bq.part_gha,
        marks_ka=bq.marks_ka,
        marks_kha=bq.marks_kha,
        marks_ga=bq.marks_ga,
        marks_gha=bq.marks_gha,
        text_hash=bq.text_hash,
        visibility='private',
        status='draft',
        origin='copied',
        source_question_id=bq.id,
    )
    db.session.add(copy)
    g.profile.questions_created = (g.profile.questions_created or 0) + 1
    _record_interaction(question_id, 'copied')
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify(copy.to_dict(include_answer=True)), 201


@bank_bp.route('/library', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def get_library():
    """Return teacher's saved library questions."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    items = (
        TeacherLibrary.query
        .filter_by(teacher_id=g.teacher_id)
        .order_by(TeacherLibrary.saved_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        'items': [{
            **item.question.to_dict(),
            'saved_at': item.saved_at.strftime('%Y-%m-%d') if item.saved_at else None,
            'notes': item.notes,
        } for item in items.items if item.question],
        'total': items.total,
        'page': page,
        'pages': items.pages,
    })


# ─── Notifications ────────────────────────────────────────────────────────────

@bank_bp.route('/notifications', methods=['GET'])
@limiter.limit('60 per minute')
@require_teacher
def get_notifications():
    """
    Return own notifications (unread first, then recent).
    Supports ?unread=true to filter unread only.
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)
    only_unread = request.args.get('unread', 'false').lower() == 'true'

    q = TeacherNotification.query.filter_by(teacher_id=g.teacher_id)
    if only_unread:
        q = q.filter_by(is_read=False)

    paginated = (
        q.order_by(TeacherNotification.is_read.asc(),
                   TeacherNotification.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    unread_count = TeacherNotification.query.filter_by(
        teacher_id=g.teacher_id, is_read=False
    ).count()

    return jsonify({
        'items': [n.to_dict() for n in paginated.items],
        'total': paginated.total,
        'unread_count': unread_count,
        'page': page,
        'pages': paginated.pages,
    })


@bank_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@limiter.limit('60 per minute')
@require_teacher
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    notif = db.session.get(TeacherNotification, notif_id)
    if not notif or notif.teacher_id != g.teacher_id:
        return jsonify({'error': 'Notification not found'}), 404
    notif.is_read = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Marked as read'})


@bank_bp.route('/notifications/read-all', methods=['POST'])
@limiter.limit('20 per minute')
@require_teacher
def mark_all_notifications_read():
    """Mark all own notifications as read."""
    TeacherNotification.query.filter_by(
        teacher_id=g.teacher_id, is_read=False
    ).update({'is_read': True})
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'All notifications marked as read'})
