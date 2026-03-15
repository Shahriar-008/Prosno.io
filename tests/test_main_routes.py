from app import create_app, db
from app.models import GeneratedPaper, GenerationLog, OmrTemplate, QuestionSet
from app.utils.omr_generator import get_default_omr_config
from config import TestingConfig


def _login(client, user_id="user-1"):
    with client.session_transaction() as session:
        session["user"] = {"id": user_id, "email": "user@example.com"}


def _valid_omr_payload(question_count=100):
    config = get_default_omr_config()
    config["question_count"] = question_count
    return {
        "name": f"OMR {question_count}",
        "config_json": config,
    }


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


def test_index_includes_seo_metadata(client, seed_catalog):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<meta name="robots" content="index,follow">' in html
    assert '<link rel="canonical" href="http://localhost/">' in html
    assert '<meta property="og:title"' in html
    assert 'application/ld+json' in html


def test_login_page_is_noindex(client):
    response = client.get("/login")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_quiz_join_code_page_is_noindex_with_generic_canonical(client):
    response = client.get("/quiz/join/1234")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert '<link rel="canonical" href="http://localhost/quiz/join">' in html


def test_robots_txt_exposes_sitemap_and_private_paths(client):
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    body = response.get_data(as_text=True)
    assert "Sitemap: http://localhost/sitemap.xml" in body
    assert "Disallow: /admin/" in body
    assert "Disallow: /api/" in body


def test_sitemap_includes_public_pages_and_shared_papers(client):
    with client.application.app_context():
        shared_set = QuestionSet(
            user_id="shared-user",
            name="Shared Algebra Set",
            questions_json=[
                {
                    "question_text": "2 + 2 = ?",
                    "answer_options": ["1", "2", "3", "4"],
                    "correct_answer": "4",
                    "type": "simple",
                }
            ],
            paper_config={"title": "Shared Algebra Practice"},
            share_token="shared-paper-1",
            is_shared=True,
        )
        db.session.add(shared_set)
        db.session.commit()

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    body = response.get_data(as_text=True)
    assert "<loc>http://localhost/</loc>" in body
    assert "<loc>http://localhost/generate</loc>" in body
    assert "<loc>http://localhost/paper/shared-paper-1</loc>" in body
    assert "<lastmod>" in body


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


def test_omr_builder_requires_login(client):
    response = client.get("/omr-builder")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_create_omr_template_requires_login(client):
    response = client.post("/api/omr/templates", json=_valid_omr_payload())

    assert response.status_code == 401
    assert response.get_json()["login_required"] is True


def test_create_and_fetch_omr_template_success(client):
    _login(client, user_id="omr-user")

    response = client.post("/api/omr/templates", json=_valid_omr_payload(question_count=80))

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    template_id = body["template"]["id"]

    list_response = client.get("/api/omr/templates")
    assert list_response.status_code == 200
    assert any(item["id"] == template_id for item in list_response.get_json()["templates"])

    get_response = client.get(f"/api/omr/templates/{template_id}")
    assert get_response.status_code == 200
    template = get_response.get_json()["template"]
    assert template["name"] == "OMR 80"
    assert template["question_count"] == 80
    assert template["config_json"]["template_type"] == "exam_sheet_v1"

    with client.application.app_context():
        saved = OmrTemplate.query.get(template_id)
        assert saved is not None
        assert saved.user_id == "omr-user"


def test_create_omr_template_rejects_invalid_question_count(client):
    _login(client)
    payload = _valid_omr_payload()
    payload["config_json"]["question_count"] = 55

    response = client.post("/api/omr/templates", json=payload)

    assert response.status_code == 400
    assert "Question count" in response.get_json()["error"]


def test_create_general_omr_template_accepts_custom_question_count(client):
    _login(client, user_id="general-omr-user")
    payload = _valid_omr_payload(question_count=37)
    payload["config_json"]["sheet_variant"] = "general"
    payload["config_json"]["answer_columns"] = 2

    response = client.post("/api/omr/templates", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body["template"]["question_count"] == 37
    assert body["template"]["config_json"]["sheet_variant"] == "general"
    assert body["template"]["config_json"]["answer_columns"] == 2


def test_create_general_omr_template_rejects_incompatible_column_count(client):
    _login(client, user_id="general-invalid-user")
    payload = _valid_omr_payload(question_count=80)
    payload["config_json"]["sheet_variant"] = "general"
    payload["config_json"]["answer_columns"] = 3

    response = client.post("/api/omr/templates", json=payload)

    assert response.status_code == 400
    assert "columns support up to" in response.get_json()["error"]


def test_create_omr_template_rejects_invalid_config_shape(client):
    _login(client)

    response = client.post("/api/omr/templates", json={"name": "Broken", "config_json": []})

    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


def test_omr_template_owner_is_enforced(client):
    _login(client, user_id="owner-user")
    create_response = client.post("/api/omr/templates", json=_valid_omr_payload(question_count=60))
    template_id = create_response.get_json()["template"]["id"]

    _login(client, user_id="other-user")

    get_response = client.get(f"/api/omr/templates/{template_id}")
    assert get_response.status_code == 404

    update_response = client.put(
        f"/api/omr/templates/{template_id}",
        json=_valid_omr_payload(question_count=40),
    )
    assert update_response.status_code == 404

    delete_response = client.post(f"/api/omr/templates/{template_id}/delete")
    assert delete_response.status_code == 404


def test_render_omr_pdf_returns_pdf_for_supported_presets(client):
    _login(client, user_id="pdf-user")

    for question_count in (40, 60, 80, 100):
        response = client.post("/api/omr/render", json=_valid_omr_payload(question_count=question_count))

        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert len(response.data) > 1000


def test_render_general_omr_pdf_returns_pdf(client):
    _login(client, user_id="pdf-general-user")
    payload = _valid_omr_payload(question_count=48)
    payload["config_json"]["sheet_variant"] = "general"
    payload["config_json"]["answer_columns"] = 2

    response = client.post("/api/omr/render", json=payload)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert len(response.data) > 1000


def test_render_omr_pdf_accepts_bengali_header(client):
    _login(client, user_id="pdf-bn-user")
    payload = _valid_omr_payload(question_count=40)
    payload["name"] = "বাংলা ওএমআর"
    payload["config_json"]["header"]["title"] = "বহুনির্বাচনি পরীক্ষা"
    payload["config_json"]["header"]["subtitle"] = "শুধু একটি বৃত্ত পূরণ করুন"
    payload["config_json"]["header"]["institution"] = "প্রশ্ন ডট আইও"

    response = client.post("/api/omr/render", json=payload)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert len(response.data) > 1000


def test_dashboard_lists_saved_omr_templates(client):
    _login(client, user_id="dashboard-user")

    with client.application.app_context():
        db.session.add(
            OmrTemplate(
                user_id="dashboard-user",
                name="Board OMR",
                config_json=get_default_omr_config(),
                question_count=100,
                download_count=2,
            )
        )
        db.session.commit()

    response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Saved OMR Templates" in html
    assert "Board OMR" in html
