"""
scheduler.py — APScheduler background job setup for Prosno.io Teacher Question Bank.

Jobs:
  job_refresh_reputations  — nightly 02:00 — recalc all teacher reputation scores + ranks + badges
  job_evaluate_auto_trust  — daily  02:30 — grant auto-trust where criteria met
  job_sync_meilisearch     — every 10 min — push newly approved questions to Meilisearch

Usage (called from app/__init__.py):
    from app.utils.scheduler import start_scheduler
    start_scheduler(app)
"""

import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(app):
    """
    Initialise and start BackgroundScheduler with the three bank maintenance jobs.
    Safe to call multiple times — only starts once (guards against werkzeug reloader).
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        log.warning('APScheduler not installed — background jobs disabled')
        return

    _scheduler = BackgroundScheduler(daemon=True)

    # ── Job 1: Nightly reputation refresh (02:00 server time) ────────────────
    _scheduler.add_job(
        func=_job_refresh_reputations,
        trigger=CronTrigger(hour=2, minute=0),
        id='refresh_reputations',
        replace_existing=True,
        args=[app],
        name='Nightly reputation refresh',
    )

    # ── Job 2: Daily auto-trust evaluation (02:30) ────────────────────────────
    _scheduler.add_job(
        func=_job_evaluate_auto_trust,
        trigger=CronTrigger(hour=2, minute=30),
        id='evaluate_auto_trust',
        replace_existing=True,
        args=[app],
        name='Daily auto-trust evaluation',
    )

    # ── Job 3: Meilisearch incremental sync (every 10 minutes) ───────────────
    _scheduler.add_job(
        func=_job_sync_meilisearch,
        trigger=IntervalTrigger(minutes=10),
        id='sync_meilisearch',
        replace_existing=True,
        args=[app],
        name='Meilisearch incremental sync',
    )

    _scheduler.start()
    log.info('APScheduler started with 3 bank maintenance jobs')


def stop_scheduler():
    """Gracefully stop the scheduler (useful for testing teardown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# ── Job implementations ───────────────────────────────────────────────────────

def _job_refresh_reputations(app):
    """
    Recalculate reputation scores and contributor ranks for all teachers.
    Also evaluates and awards new badges.
    """
    with app.app_context():
        try:
            from app import db
            from app.models import TeacherProfile
            from app.utils.bank_helpers import recalculate_reputation, evaluate_and_award_badges

            profiles = TeacherProfile.query.all()
            updated = 0
            for profile in profiles:
                try:
                    recalculate_reputation(profile)
                    evaluate_and_award_badges(profile)
                    updated += 1
                except Exception as e:
                    log.warning(f'Reputation refresh failed for {profile.user_id}: {e}')

            db.session.commit()
            log.info(f'Reputation refresh: updated {updated}/{len(profiles)} teachers')
        except Exception as e:
            log.error(f'Reputation refresh job failed: {e}')


def _job_evaluate_auto_trust(app):
    """
    Check all non-trusted teachers against auto-trust thresholds.
    Grants trusted status and creates a notification where criteria are met.
    """
    with app.app_context():
        try:
            from app import db
            from app.models import TeacherProfile
            from app.utils.bank_helpers import maybe_grant_auto_trust, create_notification

            candidates = TeacherProfile.query.filter_by(is_trusted=False).all()
            granted = 0
            for profile in candidates:
                try:
                    newly_trusted = maybe_grant_auto_trust(profile)
                    if newly_trusted:
                        create_notification(
                            teacher_id=profile.user_id,
                            notif_type='trust_granted',
                            title='You are now a Trusted Teacher! 🎉',
                            body=(
                                'Your contributions have reached the trust threshold. '
                                'Your future questions will be published directly to the '
                                'Question Bank without moderation.'
                            ),
                        )
                        granted += 1
                except Exception as e:
                    log.warning(f'Auto-trust failed for {profile.user_id}: {e}')

            db.session.commit()
            log.info(f'Auto-trust evaluation: {granted} teachers newly trusted')
        except Exception as e:
            log.error(f'Auto-trust job failed: {e}')


def _job_sync_meilisearch(app):
    """
    Push questions updated in the last 15 minutes to Meilisearch.
    Skips entirely if Meilisearch is not configured.
    """
    with app.app_context():
        try:
            from app.utils.search import bulk_sync_approved_questions, _get_client
            if _get_client() is None:
                return  # Meilisearch not configured — skip silently

            since = datetime.utcnow() - timedelta(minutes=15)
            count = bulk_sync_approved_questions(since=since)
            if count:
                log.info(f'Meilisearch incremental sync: {count} questions pushed')
        except Exception as e:
            log.error(f'Meilisearch sync job failed: {e}')
