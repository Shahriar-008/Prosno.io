"""
bank_helpers.py — Utility functions for the Teacher Question Bank feature.

Handles:
  - Text normalisation & SHA-256 hashing for duplicate detection
  - Semantic duplicate detection (pgvector cosine distance with hash fallback)
  - Trust evaluation (auto-trust based on counters)
  - Reputation score calculation
  - Profile counter refresh
  - Badge evaluation & award (including subject-specific)
  - Contributor rank calculation
  - In-app notification creation
"""

import hashlib
import os
import re
import unicodedata
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import requests as http_requests

from app import db

log = logging.getLogger(__name__)


# ─── Text hashing ─────────────────────────────────────────────────────────────

def normalise_text(text: str) -> str:
    """Lowercase, strip punctuation/diacritics and collapse whitespace."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', text).strip().lower()


def compute_text_hash(question_text: str) -> str:
    """Return a SHA-256 hex digest of the normalised question text."""
    normalised = normalise_text(question_text)
    return hashlib.sha256(normalised.encode('utf-8')).hexdigest()


def find_duplicates(question_text: str, exclude_id: int = None):
    """
    Return a list of public BankQuestion rows whose text_hash matches.
    Optionally exclude a question by id (for edit/update flows).
    """
    from app.models import BankQuestion
    h = compute_text_hash(question_text)
    q = BankQuestion.query.filter_by(text_hash=h, visibility='public')
    if exclude_id:
        q = q.filter(BankQuestion.id != exclude_id)
    return q.all()


def embed_question_text(text: str) -> Optional[List[float]]:
    """
    Call the configured embedding endpoint to obtain a vector for *text*.

    Reads ``EMBEDDING_API_URL`` from the environment.  Returns ``None``
    gracefully when the variable is unset or the request fails.
    """
    url = os.environ.get('EMBEDDING_API_URL')
    if not url:
        return None
    try:
        resp = http_requests.post(
            url,
            json={'text': text},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('embedding') or data.get('vector')
    except Exception as exc:
        log.warning('embed_question_text failed: %s', exc)
        return None


def find_semantic_duplicates(
    question_text: str,
    exclude_id: Optional[int] = None,
) -> List[Tuple]:
    """
    Find duplicate bank questions using semantic similarity when available,
    falling back to SHA-256 hash matching.

    Returns a list of ``(BankQuestion, similarity_label)`` tuples where
    *similarity_label* is ``"exact"``, ``"high"``, or ``"moderate"``.

    Strategy:
      1. Try pgvector cosine-distance query if the extension is available
         **and** the question has an ``embedding_vector``.
      2. Fall back to :func:`find_duplicates` (SHA-256 hash) otherwise.
    """
    from app.models import BankQuestion

    # ── Attempt pgvector path ────────────────────────────────────────────
    try:
        import pgvector  # noqa: F401
        from sqlalchemy import text as sa_text

        vector = embed_question_text(question_text)
        if vector is not None:
            # Cosine distance: 0 = identical, 2 = opposite
            sql = sa_text(
                "SELECT id, embedding_vector <=> CAST(:vec AS vector) AS dist "
                "FROM bank_questions "
                "WHERE visibility = 'public' AND is_active = true "
                "  AND embedding_vector IS NOT NULL "
                "  AND (:excl::int IS NULL OR id != :excl) "
                "ORDER BY dist "
                "LIMIT 10"
            )
            rows = db.session.execute(
                sql,
                {'vec': str(vector), 'excl': exclude_id},
            ).fetchall()

            results: List[Tuple] = []
            for row in rows:
                dist = float(row.dist)
                if dist > 0.4:
                    continue
                bq = db.session.get(BankQuestion, row.id)
                if not bq:
                    continue
                if dist < 0.05:
                    label = 'exact'
                elif dist < 0.2:
                    label = 'high'
                else:
                    label = 'moderate'
                results.append((bq, label))
            return results
    except Exception as exc:
        log.debug('pgvector path unavailable, falling back to hash: %s', exc)

    # ── Fallback: SHA-256 hash ───────────────────────────────────────────
    exact_matches = find_duplicates(question_text, exclude_id=exclude_id)
    return [(bq, 'exact') for bq in exact_matches]


# ─── Trust evaluation ─────────────────────────────────────────────────────────

TRUST_MIN_APPROVED = 50
TRUST_MIN_ACCOUNT_AGE_DAYS = 30
TRUST_MIN_REPUTATION = 100


def evaluate_auto_trust(profile) -> bool:
    """Return True if teacher meets auto-trust criteria. Does NOT mutate profile."""
    if profile.is_trusted:
        return True
    age_days = (datetime.utcnow() - (profile.account_created_at or datetime.utcnow())).days
    return (
        profile.approved_questions_count >= TRUST_MIN_APPROVED
        and age_days >= TRUST_MIN_ACCOUNT_AGE_DAYS
        and profile.reputation_score >= TRUST_MIN_REPUTATION
    )


def maybe_grant_auto_trust(profile) -> bool:
    """
    Check auto-trust and apply it to the profile if criteria are met.
    Returns True if trust was newly granted.
    """
    if profile.is_trusted:
        return False
    if evaluate_auto_trust(profile):
        profile.is_trusted = True
        profile.trust_granted_at = datetime.utcnow()
        profile.trust_granted_by = 'system_auto'
        return True
    return False


# ─── Reputation ───────────────────────────────────────────────────────────────

def recalculate_reputation(profile) -> int:
    """
    Recompute reputation_score from live DB aggregates.
    Formula:
        (questions_published × 2)
      + (questions_used × 1)
      + (avg_rating × rating_count × 5)
      + (total_downloads × 0.1)
    """
    from app.models import BankQuestion
    from sqlalchemy import func

    agg = db.session.query(
        func.sum(BankQuestion.usage_count).label('total_used'),
        func.sum(BankQuestion.download_count).label('total_dl'),
        func.sum(BankQuestion.rating_total).label('r_total'),
        func.sum(BankQuestion.rating_count).label('r_count'),
    ).filter(
        BankQuestion.teacher_id == profile.user_id,
        BankQuestion.visibility == 'public',
    ).one()

    total_used = agg.total_used or 0
    total_dl = agg.total_dl or 0
    r_total = agg.r_total or 0
    r_count = agg.r_count or 0
    avg_rating = (r_total / r_count) if r_count else 0

    score = int(
        (profile.questions_published * 2)
        + (total_used * 1)
        + (avg_rating * r_count * 5)
        + (total_dl * 0.1)
    )

    profile.questions_used = total_used
    profile.total_downloads = total_dl
    profile.average_rating = round(avg_rating, 2) if r_count else 0
    profile.reputation_score = score
    profile.contributor_rank = _rank_for_score(score)
    return score


def _rank_for_score(score: int) -> str:
    if score >= 1000:
        return 'Master'
    if score >= 500:
        return 'Expert'
    if score >= 200:
        return 'Senior Contributor'
    if score >= 50:
        return 'Contributor'
    return 'Newcomer'


# ─── Profile counter refresh ──────────────────────────────────────────────────

def refresh_profile_counters(profile):
    """Recounts questions_created and questions_published from the DB."""
    from app.models import BankQuestion
    profile.questions_created = BankQuestion.query.filter_by(
        teacher_id=profile.user_id, is_active=True
    ).count()
    profile.questions_published = BankQuestion.query.filter_by(
        teacher_id=profile.user_id, visibility='public'
    ).count()
    profile.approved_questions_count = profile.questions_published


# ─── Badge evaluation ─────────────────────────────────────────────────────────

# Static badge definitions (no DB needed to evaluate)
_STATIC_BADGES = [
    {
        'slug': 'first_question',
        'name': 'First Contribution',
        'icon': '🌱',
        'check': lambda p, _: p.questions_published >= 1,
    },
    {
        'slug': 'ten_published',
        'name': '10 Questions Published',
        'icon': '📝',
        'check': lambda p, _: p.questions_published >= 10,
    },
    {
        'slug': 'hundred_published',
        'name': '100 Questions Published',
        'icon': '💯',
        'check': lambda p, _: p.questions_published >= 100,
    },
    {
        'slug': 'thousand_published',
        'name': '1000 Questions Published',
        'icon': '🚀',
        'check': lambda p, _: p.questions_published >= 1000,
    },
    {
        'slug': 'widely_used',
        'name': 'Widely Used',
        'icon': '🌍',
        'check': lambda p, _: (p.questions_used or 0) >= 1000,
    },
    {
        'slug': 'highly_rated',
        'name': 'Highly Rated',
        'icon': '⭐',
        'check': lambda p, _: float(p.average_rating or 0) >= 4.5 and p.questions_published >= 20,
    },
    {
        'slug': 'contributor',
        'name': 'Contributor',
        'icon': '🎖️',
        'check': lambda p, _: p.reputation_score >= 50,
    },
    {
        'slug': 'expert',
        'name': 'Expert Teacher',
        'icon': '🏅',
        'check': lambda p, _: p.reputation_score >= 500,
    },
]

# Dynamic/subject-specific badge definitions (require DB count queries)
_DYNAMIC_BADGES = [
    {
        'slug': 'math_specialist',
        'name': 'Math Specialist',
        'icon': '🔢',
        'subject_keywords': ['math', 'mathematics', 'গণিত'],
        'min_count': 50,
    },
    {
        'slug': 'science_expert',
        'name': 'Science Expert',
        'icon': '🔬',
        'subject_keywords': ['science', 'physics', 'chemistry', 'biology',
                             'বিজ্ঞান', 'পদার্থ', 'রসায়ন', 'জীববিজ্ঞান'],
        'min_count': 50,
    },
    {
        'slug': 'board_question_expert',
        'name': 'Board Question Expert',
        'icon': '📋',
        'subject_keywords': None,   # not subject-filtered
        'min_count': 20,
        'extra_filter': 'board_year',   # requires board + year set
    },
]


def _count_subject_questions(teacher_id: str, keywords: list) -> int:
    """Count approved questions in subjects whose name contains any keyword."""
    from app.models import BankQuestion, Subject
    from sqlalchemy import or_
    total = 0
    for kw in keywords:
        count = (
            db.session.query(BankQuestion)
            .join(Subject, BankQuestion.subject_id == Subject.id)
            .filter(
                BankQuestion.teacher_id == teacher_id,
                BankQuestion.visibility == 'public',
                Subject.name.ilike(f'%{kw}%'),
            )
            .count()
        )
        total += count
    return total


def evaluate_and_award_badges(profile) -> list:
    """
    Check all badge definitions and award newly earned badges.
    Also creates a TeacherNotification for each newly awarded badge.
    Returns a list of newly awarded badge slugs.
    """
    from app.models import TeacherBadge, BankQuestion
    newly_awarded = []

    existing_slugs = {
        b.badge_slug for b in TeacherBadge.query.filter_by(
            teacher_id=profile.user_id
        ).all()
    }

    # Static badges
    for defn in _STATIC_BADGES:
        if defn['slug'] in existing_slugs:
            continue
        try:
            if defn['check'](profile, None):
                _award_badge(profile.user_id, defn)
                newly_awarded.append(defn['slug'])
        except Exception as e:
            log.warning(f'Badge eval error ({defn["slug"]}): {e}')

    # Dynamic subject-specific badges
    for defn in _DYNAMIC_BADGES:
        if defn['slug'] in existing_slugs:
            continue
        try:
            if defn.get('extra_filter') == 'board_year':
                count = BankQuestion.query.filter(
                    BankQuestion.teacher_id == profile.user_id,
                    BankQuestion.visibility == 'public',
                    BankQuestion.board.isnot(None),
                    BankQuestion.year.isnot(None),
                ).count()
            elif defn['subject_keywords']:
                count = _count_subject_questions(profile.user_id, defn['subject_keywords'])
            else:
                count = 0

            if count >= defn['min_count']:
                _award_badge(profile.user_id, defn)
                newly_awarded.append(defn['slug'])
        except Exception as e:
            log.warning(f'Dynamic badge eval error ({defn["slug"]}): {e}')

    return newly_awarded


def _award_badge(teacher_id: str, defn: dict):
    """Insert TeacherBadge row and create a notification for the teacher."""
    from app.models import TeacherBadge
    badge = TeacherBadge(
        teacher_id=teacher_id,
        badge_slug=defn['slug'],
        badge_name=defn['name'],
        badge_icon=defn.get('icon', '🏆'),
    )
    db.session.add(badge)
    create_notification(
        teacher_id=teacher_id,
        notif_type='badge_awarded',
        title=f'{defn.get("icon", "🏆")} Badge Earned: {defn["name"]}',
        body=f'Congratulations! You earned the "{defn["name"]}" badge.',
        badge_slug=defn['slug'],
    )


# ─── Notifications ────────────────────────────────────────────────────────────

def create_notification(teacher_id: str, notif_type: str, title: str,
                        body: str = None, question_id: int = None,
                        badge_slug: str = None):
    """
    Create and add a TeacherNotification to the current session.
    Caller is responsible for committing the session.
    """
    try:
        from app.models import TeacherNotification
        notif = TeacherNotification(
            teacher_id=teacher_id,
            notif_type=notif_type,
            title=title,
            body=body,
            question_id=question_id,
            badge_slug=badge_slug,
        )
        db.session.add(notif)
    except Exception as e:
        log.warning(f'create_notification failed: {e}')


# ─── Post-approval refresh ────────────────────────────────────────────────────

def post_approval_refresh(profile, question=None, decision: str = 'approved') -> list:
    """
    Full refresh after a moderation decision.
    - Refreshes counters
    - Recalculates reputation
    - Evaluates auto-trust
    - Awards new badges
    - Creates a moderation-outcome notification  ← NEW in Phase 2
    Returns newly awarded badge slugs.
    """
    refresh_profile_counters(profile)
    recalculate_reputation(profile)
    maybe_grant_auto_trust(profile)
    newly_awarded = evaluate_and_award_badges(profile)

    # Moderation outcome notification
    if question:
        if decision == 'approved':
            create_notification(
                teacher_id=profile.user_id,
                notif_type='question_approved',
                title='✅ Your question was approved!',
                body=f'"{question.question_text[:80]}…" is now public in the Question Bank.',
                question_id=question.id,
            )
        else:
            create_notification(
                teacher_id=profile.user_id,
                notif_type='question_rejected',
                title='❌ Your question was not approved',
                body=(
                    f'"{question.question_text[:80]}…" was rejected. '
                    f'Reason: {question.rejection_reason or "See admin notes."}'
                ),
                question_id=question.id,
            )

    return newly_awarded


# ─── Get or create profile ────────────────────────────────────────────────────

def get_or_create_profile(user_id: str, display_name: str = None):
    """Return the TeacherProfile for user_id, creating one if it doesn't exist."""
    from app.models import TeacherProfile
    profile = TeacherProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = TeacherProfile(
            user_id=user_id,
            display_name=display_name,
            account_created_at=datetime.utcnow(),
        )
        db.session.add(profile)
        db.session.flush()
    elif display_name and not profile.display_name:
        profile.display_name = display_name
    return profile
