"""
tests/test_bank.py — Tests for the Teacher Question Bank (Phase 1 + 2).

Covers:
  - Unit: normalise_text, compute_text_hash
  - Unit: get_or_create_profile
  - Unit: reputation calculation
  - API: Question CRUD (create, get, update, delete)
  - API: Browse endpoints
  - API: Publish workflow (trusted → public, untrusted → pending)
  - API: Duplicate detection
  - API: Interactions (use, save/unsave, rate, copy)
  - API: Notifications list / mark-read
  - Phase 2: cache invalidation smoke test
  - Phase 2: TeacherNotification model
"""

import pytest

from app import db
from app.models import (
    BankQuestion, TeacherProfile, TeacherNotification, ModerationQueue,
    TeacherLibrary, QuestionInteraction, Class, Subject, Chapter,
)
from app.utils.bank_helpers import (
    normalise_text, compute_text_hash, get_or_create_profile,
    recalculate_reputation, evaluate_and_award_badges, create_notification,
    maybe_grant_auto_trust, find_semantic_duplicates,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

TEACHER_ID = 'teacher-uuid-aaa-111'
TEACHER2_ID = 'teacher-uuid-bbb-222'


@pytest.fixture
def bank_seed(app):
    """Seed a curriculum and two teacher profiles."""
    with app.app_context():
        cls = Class(name='Class 10', name_bn='ক্লাস ১০', level='Secondary', order=10)
        db.session.add(cls)
        db.session.flush()

        subj = Subject(name='Mathematics', name_bn='গণিত', code='MATH',
                       class_id=cls.id, order=1)
        db.session.add(subj)
        db.session.flush()

        chap = Chapter(name='Algebra', name_bn='বীজগণিত', chapter_number=1,
                       subject_id=subj.id, order=1)
        db.session.add(chap)
        db.session.flush()

        profile = TeacherProfile(user_id=TEACHER_ID, display_name='Teacher A')
        profile2 = TeacherProfile(user_id=TEACHER2_ID, display_name='Teacher B',
                                  is_trusted=True)
        db.session.add_all([profile, profile2])
        db.session.commit()

        return {
            'class_id': cls.id,
            'subject_id': subj.id,
            'chapter_id': chap.id,
        }


def _auth_headers(user_id=TEACHER_ID, display_name='Teacher A'):
    return {
        'X-Supabase-User-Id': user_id,
        'X-Supabase-Display-Name': display_name,
        'Content-Type': 'application/json',
    }


# ─── Unit: text helpers ───────────────────────────────────────────────────────

class TestTextHelpers:
    def test_normalise_text_strips_punctuation(self):
        result = normalise_text("What is Newton's 2nd law?")
        assert 'newton' in result
        assert "'" not in result
        assert '?' not in result

    def test_normalise_text_collapses_whitespace(self):
        result = normalise_text('  hello   world  ')
        assert result == 'hello world'

    def test_compute_text_hash_is_64_chars(self):
        h = compute_text_hash('What is 2+2?')
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)

    def test_same_text_same_hash(self):
        a = compute_text_hash('What is 2 + 2?')
        b = compute_text_hash('what is 2 + 2')  # punctuation stripped
        assert a == b

    def test_different_text_different_hash(self):
        a = compute_text_hash('What is 2+2?')
        b = compute_text_hash('What is 3+3?')
        assert a != b


# ─── Unit: profile helpers ────────────────────────────────────────────────────

class TestProfileHelpers:
    def test_get_or_create_creates_new(self, app):
        with app.app_context():
            profile = get_or_create_profile('new-user-xyz', 'New Teacher')
            db.session.commit()
            assert profile.user_id == 'new-user-xyz'
            assert profile.display_name == 'New Teacher'

    def test_get_or_create_idempotent(self, app):
        with app.app_context():
            p1 = get_or_create_profile('idempotent-user', 'Teacher')
            db.session.commit()
            p2 = get_or_create_profile('idempotent-user', 'Teacher')
            db.session.commit()
            assert p1.id == p2.id

    def test_reputation_starts_at_zero(self, app, bank_seed):
        with app.app_context():
            profile = TeacherProfile.query.filter_by(user_id=TEACHER_ID).first()
            score = recalculate_reputation(profile)
            assert score == 0

    def test_auto_trust_not_granted_below_threshold(self, app, bank_seed):
        with app.app_context():
            profile = TeacherProfile.query.filter_by(user_id=TEACHER_ID).first()
            granted = maybe_grant_auto_trust(profile)
            assert not granted
            assert not profile.is_trusted

    def test_create_notification(self, app, bank_seed):
        with app.app_context():
            create_notification(
                teacher_id=TEACHER_ID,
                notif_type='test_type',
                title='Test Notification',
                body='This is a test',
            )
            db.session.commit()
            notif = TeacherNotification.query.filter_by(teacher_id=TEACHER_ID).first()
            assert notif is not None
            assert notif.title == 'Test Notification'
            assert not notif.is_read


# ─── API: Question CRUD ───────────────────────────────────────────────────────

class TestQuestionCRUD:
    def test_create_mcq_question(self, client, bank_seed):
        resp = client.post('/api/v1/bank/questions',
                           headers=_auth_headers(),
                           json={
                               'question_type': 'MCQ',
                               'question_text': 'What is 2+2?',
                               'answer': '4',
                               'answer_options': ['1', '2', '3', '4'],
                               'correct_answer': '4',
                               'class_id': bank_seed['class_id'],
                               'subject_id': bank_seed['subject_id'],
                               'chapter_id': bank_seed['chapter_id'],
                               'difficulty': 'easy',
                               'marks': 1,
                           })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['question_type'] == 'MCQ'
        assert data['visibility'] == 'private'
        assert data['teacher_id'] == TEACHER_ID
        return data['id']

    def test_create_question_requires_auth(self, client, bank_seed):
        resp = client.post('/api/v1/bank/questions',
                           json={'question_type': 'SQ', 'question_text': 'Hello?'})
        assert resp.status_code == 401

    def test_create_question_invalid_type(self, client, bank_seed):
        resp = client.post('/api/v1/bank/questions',
                           headers=_auth_headers(),
                           json={'question_type': 'INVALID', 'question_text': 'x'})
        assert resp.status_code == 400

    def test_get_own_question(self, client, bank_seed):
        # First create
        cid = client.post('/api/v1/bank/questions',
                          headers=_auth_headers(),
                          json={'question_type': 'SQ',
                                'question_text': 'Define gravity.'}).get_json()['id']
        resp = client.get(f'/api/v1/bank/questions/{cid}', headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.get_json()['id'] == cid

    def test_list_own_questions(self, client, bank_seed):
        for i in range(3):
            client.post('/api/v1/bank/questions', headers=_auth_headers(),
                        json={'question_type': 'SQ',
                              'question_text': f'Question number {i}'})
        resp = client.get('/api/v1/bank/questions', headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.get_json()['total'] >= 3

    def test_update_private_question(self, client, bank_seed):
        cid = client.post('/api/v1/bank/questions',
                          headers=_auth_headers(),
                          json={'question_type': 'SQ',
                                'question_text': 'Original text'}).get_json()['id']
        resp = client.put(f'/api/v1/bank/questions/{cid}',
                          headers=_auth_headers(),
                          json={'question_text': 'Updated text'})
        assert resp.status_code == 200
        assert resp.get_json()['question_text'] == 'Updated text'

    def test_delete_private_question(self, client, bank_seed):
        cid = client.post('/api/v1/bank/questions',
                          headers=_auth_headers(),
                          json={'question_type': 'SQ',
                                'question_text': 'To be deleted'}).get_json()['id']
        resp = client.delete(f'/api/v1/bank/questions/{cid}', headers=_auth_headers())
        assert resp.status_code == 200
        # Should be gone
        resp2 = client.get(f'/api/v1/bank/questions/{cid}', headers=_auth_headers())
        assert resp2.status_code == 404


# ─── API: Profile ─────────────────────────────────────────────────────────────

class TestProfile:
    def test_get_own_profile(self, client, bank_seed):
        resp = client.get('/api/v1/bank/profile', headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user_id'] == TEACHER_ID

    def test_update_display_name(self, client, bank_seed):
        resp = client.put('/api/v1/bank/profile', headers=_auth_headers(),
                          json={'display_name': 'Updated Name'})
        assert resp.status_code == 200
        assert resp.get_json()['display_name'] == 'Updated Name'

    def test_get_public_profile(self, client, bank_seed):
        # First ensure profile exists
        client.get('/api/v1/bank/profile', headers=_auth_headers())
        resp = client.get(f'/api/v1/bank/teachers/{TEACHER_ID}/profile')
        assert resp.status_code == 200
        assert resp.get_json()['user_id'] == TEACHER_ID

    def test_leaderboard(self, client, bank_seed):
        resp = client.get('/api/v1/bank/leaderboard')
        assert resp.status_code == 200
        assert 'items' in resp.get_json()


# ─── API: Browse ──────────────────────────────────────────────────────────────

class TestBrowse:
    def _publish_one(self, app, chapter_id, class_id=None, subject_id=None):
        """Helper: directly insert a public bank question with curriculum links."""
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER_ID,
                question_type='SQ',
                question_text='Test public question',
                class_id=class_id,
                subject_id=subject_id,
                chapter_id=chapter_id,
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash('Test public question'),
            )
            db.session.add(bq)
            db.session.commit()
            return bq.id

    def test_browse_classes_empty(self, client, bank_seed):
        resp = client.get('/api/v1/bank/browse/classes')
        assert resp.status_code == 200
        # No public questions yet
        assert resp.get_json() == []

    def test_browse_classes_with_public_question(self, client, app, bank_seed):
        self._publish_one(app, bank_seed['chapter_id'],
                          class_id=bank_seed['class_id'],
                          subject_id=bank_seed['subject_id'])
        resp = client.get('/api/v1/bank/browse/classes')
        assert resp.status_code == 200
        items = resp.get_json()
        assert any(i['id'] == bank_seed['class_id'] for i in items)
        assert items[0]['question_count'] >= 1

    def test_browse_chapter_questions_grouped(self, client, app, bank_seed):
        self._publish_one(app, bank_seed['chapter_id'],
                          class_id=bank_seed['class_id'],
                          subject_id=bank_seed['subject_id'])
        resp = client.get(f'/api/v1/bank/browse/chapters/{bank_seed["chapter_id"]}/questions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'grouped' in data
        assert 'SQ' in data['grouped']


# ─── API: Publish workflow ────────────────────────────────────────────────────

class TestPublishWorkflow:
    def test_trusted_teacher_publishes_directly(self, client, app, bank_seed):
        """A trusted teacher's question goes straight to visibility=public."""
        # Create question as trusted teacher (TEACHER2_ID)
        resp = client.post('/api/v1/bank/questions',
                           headers=_auth_headers(TEACHER2_ID, 'Teacher B'),
                           json={'question_type': 'SQ',
                                 'question_text': 'Trusted direct publish question',
                                 'chapter_id': bank_seed['chapter_id']})
        assert resp.status_code == 201
        qid = resp.get_json()['id']

        with app.app_context():
            from app.models import QuestionSet
            qs = QuestionSet(
                user_id=TEACHER2_ID,
                name='Test Set',
                questions_json=[],
            )
            db.session.add(qs)
            db.session.commit()
            qs_id = qs.id

        # Create prompt
        prompt_resp = client.post(f'/api/v1/bank/question-sets/{qs_id}/publish-prompt',
                                  headers=_auth_headers(TEACHER2_ID, 'Teacher B'),
                                  json={'question_ids': [qid]})
        assert prompt_resp.status_code == 201
        prompt_id = prompt_resp.get_json()['id']

        # Respond: publish
        respond_resp = client.post(f'/api/v1/bank/publish-prompt/{prompt_id}/respond',
                                   headers=_auth_headers(TEACHER2_ID, 'Teacher B'),
                                   json={'decision': 'publish', 'question_ids': [qid]})
        assert respond_resp.status_code == 200
        data = respond_resp.get_json()
        assert qid in data['published_ids']

        with app.app_context():
            bq = db.session.get(BankQuestion, qid)
            assert bq.visibility == 'public'
            assert bq.status == 'approved'

    def test_untrusted_teacher_sends_to_moderation(self, client, app, bank_seed):
        """An untrusted teacher's question enters the moderation queue."""
        resp = client.post('/api/v1/bank/questions',
                           headers=_auth_headers(),
                           json={'question_type': 'SQ',
                                 'question_text': 'Untrusted question for moderation',
                                 'chapter_id': bank_seed['chapter_id']})
        qid = resp.get_json()['id']

        with app.app_context():
            from app.models import QuestionSet
            qs = QuestionSet(
                user_id=TEACHER_ID,
                name='Set 2',
                questions_json=[],
            )
            db.session.add(qs)
            db.session.commit()
            qs_id = qs.id

        prompt_id = client.post(
            f'/api/v1/bank/question-sets/{qs_id}/publish-prompt',
            headers=_auth_headers(),
            json={'question_ids': [qid]}
        ).get_json()['id']

        respond = client.post(
            f'/api/v1/bank/publish-prompt/{prompt_id}/respond',
            headers=_auth_headers(),
            json={'decision': 'publish', 'question_ids': [qid]}
        )
        assert respond.status_code == 200
        with app.app_context():
            bq = db.session.get(BankQuestion, qid)
            assert bq.visibility == 'pending'
            mq = ModerationQueue.query.filter_by(question_id=qid).first()
            assert mq is not None


# ─── API: Duplicate detection ─────────────────────────────────────────────────

class TestDuplicateDetection:
    def test_no_duplicates_initially(self, client, bank_seed):
        q = client.post('/api/v1/bank/questions', headers=_auth_headers(),
                        json={'question_type': 'SQ',
                              'question_text': 'A completely unique question here'}).get_json()
        resp = client.get(f'/api/v1/bank/questions/{q["id"]}/duplicate-check',
                          headers=_auth_headers())
        assert resp.status_code == 200
        assert not resp.get_json()['has_duplicates']

    def test_detects_exact_duplicate(self, client, app, bank_seed):
        """Insert a public question with known hash, then check duplicate."""
        text = 'What is the speed of light?'
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER2_ID,
                question_type='SQ',
                question_text=text,
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash(text),
            )
            db.session.add(bq)
            db.session.commit()
            existing_id = bq.id

        # Create same-text question as TEACHER_ID
        new_q = client.post('/api/v1/bank/questions', headers=_auth_headers(),
                            json={'question_type': 'SQ',
                                  'question_text': text}).get_json()
        resp = client.get(f'/api/v1/bank/questions/{new_q["id"]}/duplicate-check',
                          headers=_auth_headers())
        data = resp.get_json()
        assert data['has_duplicates']
        assert any(d['id'] == existing_id for d in data['similar'])


# ─── API: Interactions ────────────────────────────────────────────────────────

class TestInteractions:
    def _make_public_q(self, app, text='Public interaction test question'):
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER2_ID,
                question_type='SQ',
                question_text=text,
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash(text),
            )
            db.session.add(bq)
            db.session.commit()
            return bq.id

    def test_rate_question(self, client, app, bank_seed):
        qid = self._make_public_q(app)
        resp = client.post(f'/api/v1/bank/questions/{qid}/rate',
                           headers=_auth_headers(),
                           json={'rating': 5})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['rating_count'] == 1
        assert data['average_rating'] == 5.0

    def test_rate_invalid_stars(self, client, app, bank_seed):
        qid = self._make_public_q(app, 'Rate invalid test')
        resp = client.post(f'/api/v1/bank/questions/{qid}/rate',
                           headers=_auth_headers(),
                           json={'rating': 6})
        assert resp.status_code == 400

    def test_save_and_unsave_question(self, client, app, bank_seed):
        qid = self._make_public_q(app, 'Save test question')
        # Save
        r = client.post(f'/api/v1/bank/questions/{qid}/save', headers=_auth_headers())
        assert r.status_code in (200, 201)
        # In library
        lib = client.get('/api/v1/bank/library', headers=_auth_headers())
        ids = [item['id'] for item in lib.get_json()['items']]
        assert qid in ids
        # Unsave
        del_r = client.delete(f'/api/v1/bank/questions/{qid}/save', headers=_auth_headers())
        assert del_r.status_code == 200

    def test_copy_question(self, client, app, bank_seed):
        qid = self._make_public_q(app, 'Copy test question')
        resp = client.post(f'/api/v1/bank/questions/{qid}/copy', headers=_auth_headers())
        assert resp.status_code == 201
        copy = resp.get_json()
        assert copy['visibility'] == 'private'
        assert copy['origin'] == 'copied'
        assert copy['source_question_id'] == qid
        assert copy['teacher_id'] == TEACHER_ID

    def test_use_question(self, client, app, bank_seed):
        qid = self._make_public_q(app, 'Use test question')
        resp = client.post(f'/api/v1/bank/questions/{qid}/use', headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.get_json()['usage_count'] == 1


# ─── API: Notifications ──────────────────────────────────────────────────────

class TestNotifications:
    def test_get_empty_notifications(self, client, bank_seed):
        resp = client.get('/api/v1/bank/notifications', headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['unread_count'] == 0

    def test_notification_created_and_readable(self, client, app, bank_seed):
        with app.app_context():
            create_notification(
                teacher_id=TEACHER_ID,
                notif_type='question_approved',
                title='Your question was approved!',
                body='Congrats',
            )
            db.session.commit()

        resp = client.get('/api/v1/bank/notifications', headers=_auth_headers())
        data = resp.get_json()
        assert data['unread_count'] == 1
        notif_id = data['items'][0]['id']

        # Mark as read
        mark = client.post(f'/api/v1/bank/notifications/{notif_id}/read',
                           headers=_auth_headers())
        assert mark.status_code == 200

        # Unread count should be 0
        resp2 = client.get('/api/v1/bank/notifications', headers=_auth_headers())
        assert resp2.get_json()['unread_count'] == 0

    def test_mark_all_read(self, client, app, bank_seed):
        with app.app_context():
            for i in range(3):
                create_notification(
                    teacher_id=TEACHER_ID,
                    notif_type='badge_awarded',
                    title=f'Badge {i}',
                    body='',
                )
            db.session.commit()

        resp = client.post('/api/v1/bank/notifications/read-all', headers=_auth_headers())
        assert resp.status_code == 200
        check = client.get('/api/v1/bank/notifications', headers=_auth_headers())
        assert check.get_json()['unread_count'] == 0


# ─── API: Search ─────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_returns_results(self, client, app, bank_seed):
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER2_ID,
                question_type='MCQ',
                question_text='What is photosynthesis?',
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash('What is photosynthesis?'),
            )
            db.session.add(bq)
            db.session.commit()

        resp = client.get('/api/v1/bank/search?q=photosynthesis')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] >= 1
        assert data['engine'] == 'sql'   # Meilisearch not configured in tests

    def test_search_empty_query_returns_all_public(self, client, bank_seed):
        resp = client.get('/api/v1/bank/search')
        assert resp.status_code == 200
        assert 'items' in resp.get_json()


# ─── Phase 3: Semantic Deduplication ──────────────────────────────────────────

class TestSemanticDuplication:
    """Tests for find_semantic_duplicates and the duplicate-check endpoint."""

    def test_duplicate_check_returns_similarity_field(
        self, client, app, bank_seed
    ):
        """Exact SHA-256 match returns 'exact' in similar[*].similarity."""
        text = 'What is the capital of Bangladesh?'
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER2_ID,
                question_type='SQ',
                question_text=text,
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash(text),
            )
            db.session.add(bq)
            db.session.commit()

        new_q = client.post(
            '/api/v1/bank/questions',
            headers=_auth_headers(),
            json={'question_type': 'SQ', 'question_text': text},
        ).get_json()

        resp = client.get(
            f'/api/v1/bank/questions/{new_q["id"]}/duplicate-check',
            headers=_auth_headers(),
        )
        data = resp.get_json()
        assert data['has_duplicates']
        assert data['similar'][0]['similarity'] == 'exact'

    def test_duplicate_check_no_match_returns_empty(
        self, client, bank_seed
    ):
        """No match returns has_duplicates: false."""
        new_q = client.post(
            '/api/v1/bank/questions',
            headers=_auth_headers(),
            json={
                'question_type': 'SQ',
                'question_text': 'Absolutely unique xyz 98765',
            },
        ).get_json()

        resp = client.get(
            f'/api/v1/bank/questions/{new_q["id"]}/duplicate-check',
            headers=_auth_headers(),
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert not data['has_duplicates']

    def test_semantic_fallback_when_no_vector(self, app, bank_seed):
        """
        When embedding_vector is NULL (no pgvector), falls back to hash;
        response is still valid tuples.
        """
        text = 'Fallback hash check question'
        with app.app_context():
            bq = BankQuestion(
                teacher_id=TEACHER2_ID,
                question_type='SQ',
                question_text=text,
                visibility='public',
                status='approved',
                is_active=True,
                text_hash=compute_text_hash(text),
            )
            db.session.add(bq)
            db.session.commit()

            results = find_semantic_duplicates(text)
            assert len(results) >= 1
            returned_bq, label = results[0]
            assert label == 'exact'
            assert returned_bq.id == bq.id


# ─── Phase 4: Admin Analytics Dashboard ──────────────────────────────────────

class TestAdminStats:
    """Tests for the extended /api/v1/admin/bank/stats endpoint."""

    def _login_admin(self, client, app):
        """Log in as admin user (creates one if needed)."""
        from app.models import User, ROLE_ADMIN
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@test.com',
                    role=ROLE_ADMIN,
                    is_admin=True,
                )
                admin.set_password('testpass')
                db.session.add(admin)
                db.session.commit()
        client.post('/admin/login', data={
            'username': 'admin',
            'password': 'testpass',
        })

    def test_admin_stats_returns_extended_fields(
        self, client, app, bank_seed
    ):
        """GET /api/v1/admin/bank/stats returns extended analytics keys."""
        self._login_admin(client, app)
        resp = client.get('/api/v1/admin/bank/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'daily_published' in data
        assert 'top_teachers' in data
        assert 'top_subjects' in data
