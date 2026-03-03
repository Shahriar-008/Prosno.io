import os

import pytest

os.environ.setdefault("PROSNO_SKIP_GLOBAL_APP", "1")

from app import create_app, db
from app.models import Chapter, Class, Question, Subject
from config import TestingConfig


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"

    class LocalTestingConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.as_posix()}"
        SKIP_STARTUP_TASKS = True

    flask_app = create_app(LocalTestingConfig)

    with flask_app.app_context():
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_catalog(app):
    with app.app_context():
        active_class = Class(
            name="Class 8",
            name_bn="Class 8 BN",
            level="Secondary",
            order=8,
            is_active=True,
        )
        inactive_class = Class(
            name="Class 9",
            name_bn="Class 9 BN",
            level="Secondary",
            order=9,
            is_active=False,
        )
        db.session.add_all([active_class, inactive_class])
        db.session.flush()

        active_subject = Subject(
            name="Mathematics",
            name_bn="Math BN",
            code="MATH",
            class_id=active_class.id,
            order=1,
            is_active=True,
        )
        inactive_subject = Subject(
            name="Science",
            name_bn="Science BN",
            code="SCI",
            class_id=active_class.id,
            order=2,
            is_active=False,
        )
        db.session.add_all([active_subject, inactive_subject])
        db.session.flush()

        active_chapter = Chapter(
            name="Algebra",
            name_bn="Algebra BN",
            chapter_number=1,
            subject_id=active_subject.id,
            order=1,
            is_active=True,
        )
        inactive_chapter = Chapter(
            name="Geometry",
            name_bn="Geometry BN",
            chapter_number=2,
            subject_id=active_subject.id,
            order=2,
            is_active=False,
        )
        db.session.add_all([active_chapter, inactive_chapter])
        db.session.flush()

        active_question = Question(
            question_text="2 + 2 = ?",
            question_type="simple",
            answer_options=["1", "2", "3", "4"],
            correct_answer="4",
            chapter_id=active_chapter.id,
            is_active=True,
        )
        inactive_question = Question(
            question_text="3 + 3 = ?",
            question_type="simple",
            answer_options=["5", "6", "7", "8"],
            correct_answer="6",
            chapter_id=active_chapter.id,
            is_active=False,
        )
        db.session.add_all([active_question, inactive_question])
        db.session.commit()

        return {
            "class_id": active_class.id,
            "subject_id": active_subject.id,
            "chapter_id": active_chapter.id,
            "question_id": active_question.id,
            "inactive_question_id": inactive_question.id,
        }
