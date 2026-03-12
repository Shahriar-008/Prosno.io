from app import create_app, db
from app.models import GeneratedPaper, GenerationLog, QuestionSet
from config import TestingConfig


def _login(client, user_id="user-1"):
    with client.session_transaction() as session:
        session["user"] = {"id": user_id, "email": "user@example.com"}


def test_generate_paper_success_creates_paper_record(client, seed_catalog, monkeypatch):
    captured = {}

    def fake_generate(questions, paper_config, output_folder, **kwargs):
        captured["questions"] = questions
        captured["paper_config"] = paper_config
        captured["output_folder"] = output_folder
        captured["kwargs"] = kwargs
        return ("student.docx", "teacher.docx")

    monkeypatch.setattr("app.routes.main.generate_paper_from_db", fake_generate)

    payload = {
        "class_id": seed_catalog["class_id"],
        "subject_id": seed_catalog["subject_id"],
        "chapter_ids": [seed_catalog["chapter_id"]],
        "question_count": 1,
        "time_minutes": 40,
        "title": "Unit Test Paper",
    }

    response = client.post("/generate-paper", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["question_count"] == 1
    assert body["student_download"].startswith("/download/")
    assert body["teacher_download"].startswith("/download/")

    with client.application.app_context():
        paper = GeneratedPaper.query.get(body["paper_id"])
        assert paper is not None
        assert paper.title == "Unit Test Paper"
        assert paper.class_id == seed_catalog["class_id"]
        assert paper.subject_id == seed_catalog["subject_id"]
        assert paper.file_path == "student.docx"
        assert paper.file_path_answers == "teacher.docx"
        assert paper.question_ids == [seed_catalog["question_id"]]

    assert captured["paper_config"]["title"] == "Unit Test Paper"
    assert captured["paper_config"]["marks"] == 1
    assert captured["kwargs"]["omr_style"] is True


def test_index_is_not_throttled_by_global_defaults(tmp_path):
    db_path = tmp_path / "ratelimit.db"

    class LocalRateLimitConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.as_posix()}"
        RATELIMIT_ENABLED = True
        SKIP_STARTUP_TASKS = True

    flask_app = create_app(LocalRateLimitConfig)

    with flask_app.app_context():
        db.create_all()

        from app.models import Class

        db.session.add(
            Class(
                name="Class 8",
                name_bn="Class 8 BN",
                level="Secondary",
                order=8,
                is_active=True,
            )
        )
        db.session.commit()

    client = flask_app.test_client()

    for _ in range(55):
        response = client.get("/")
        assert response.status_code == 200


def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_healthz_is_not_throttled(tmp_path):
    db_path = tmp_path / "healthz-ratelimit.db"

    class LocalRateLimitConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.as_posix()}"
        RATELIMIT_ENABLED = True
        SKIP_STARTUP_TASKS = True

    flask_app = create_app(LocalRateLimitConfig)

    with flask_app.app_context():
        db.create_all()

    client = flask_app.test_client()

    for _ in range(100):
        response = client.get("/healthz")
        assert response.status_code == 200


def test_generate_paper_missing_required_fields_returns_400(client):
    response = client.post("/generate-paper", json={"class_id": 1})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing required fields"


def test_generate_paper_rejects_too_many_chapters(client, seed_catalog):
    payload = {
        "class_id": seed_catalog["class_id"],
        "subject_id": seed_catalog["subject_id"],
        "chapter_ids": [1, 2, 3, 4, 5, 6],
    }

    response = client.post("/generate-paper", json=payload)

    assert response.status_code == 400
    assert "Maximum 5 chapters" in response.get_json()["error"]


def test_generate_paper_rejects_invalid_class_or_subject(client, seed_catalog):
    payload = {
        "class_id": 99999,
        "subject_id": seed_catalog["subject_id"],
        "chapter_ids": [seed_catalog["chapter_id"]],
    }

    response = client.post("/generate-paper", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid class or subject"


def test_generate_paper_returns_429_when_credits_exhausted(client, seed_catalog):
    _login(client, user_id="credit-user")

    with client.application.app_context():
        for _ in range(10):
            db.session.add(GenerationLog(user_id="credit-user", generation_type="db"))
        db.session.commit()

    payload = {
        "class_id": seed_catalog["class_id"],
        "subject_id": seed_catalog["subject_id"],
        "chapter_ids": [seed_catalog["chapter_id"]],
    }
    response = client.post("/generate-paper", json=payload)

    assert response.status_code == 429
    data = response.get_json()
    assert data["credits_exhausted"] is True


def test_generate_paper_logged_in_user_creates_generation_log(client, seed_catalog, monkeypatch):
    _login(client, user_id="logging-user")
    monkeypatch.setattr(
        "app.routes.main.generate_paper_from_db",
        lambda *args, **kwargs: ("student.docx", "teacher.docx"),
    )

    payload = {
        "class_id": seed_catalog["class_id"],
        "subject_id": seed_catalog["subject_id"],
        "chapter_ids": [seed_catalog["chapter_id"]],
    }
    response = client.post("/generate-paper", json=payload)

    assert response.status_code == 200

    with client.application.app_context():
        logs = GenerationLog.query.filter_by(user_id="logging-user").all()
        assert len(logs) == 1
        assert logs[0].generation_type == "db"


def test_save_question_set_requires_login(client):
    response = client.post("/save-question-set", json={"questions": [{"id": 1}]})

    assert response.status_code == 401
    data = response.get_json()
    assert data["login_required"] is True


def test_save_question_set_requires_data_payload(client):
    _login(client)
    response = client.post("/save-question-set", json={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No data provided."


def test_save_question_set_requires_questions(client):
    _login(client)
    response = client.post("/save-question-set", json={"questions": []})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No questions to save."


def test_save_question_set_custom_source_success(client):
    _login(client, user_id="custom-user")
    payload = {
        "name": "My custom set",
        "source": "custom",
        "questions": [
            {
                "question_text": "What is 5+5?",
                "answer_options": ["9", "10", "11", "12"],
                "correct_answer": "10",
                "type": "simple",
            }
        ],
        "paper_config": {"title": "Custom", "marks": 1, "time": 30},
    }

    response = client.post("/save-question-set", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    with client.application.app_context():
        saved = QuestionSet.query.get(data["id"])
        assert saved is not None
        assert saved.user_id == "custom-user"
        assert saved.name == "My custom set"
        assert saved.source == "custom"
        assert saved.questions_json[0]["correct_answer"] == "10"


def test_save_question_set_db_source_enriches_full_question_data(client, seed_catalog):
    _login(client, user_id="db-user")
    payload = {
        "source": "db",
        "name": "DB set",
        "questions": [
            {
                "id": seed_catalog["question_id"],
                "question_text": "preview only",
            }
        ],
    }

    response = client.post("/save-question-set", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True

    with client.application.app_context():
        saved = QuestionSet.query.get(body["id"])
        assert saved is not None
        assert saved.source == "db"
        assert saved.questions_json[0]["id"] == str(seed_catalog["question_id"])
        assert saved.questions_json[0]["question_text"] == "2 + 2 = ?"
        assert saved.questions_json[0]["correct_answer"] == "4"
        assert saved.questions_json[0]["answer_options"] == ["1", "2", "3", "4"]
