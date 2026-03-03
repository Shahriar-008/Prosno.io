def test_get_classes_returns_only_active(client, seed_catalog):
    response = client.get("/api/classes")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["id"] == seed_catalog["class_id"]


def test_get_subjects_returns_only_active_for_class(client, seed_catalog):
    response = client.get(f"/api/subjects/{seed_catalog['class_id']}")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["id"] == seed_catalog["subject_id"]


def test_get_chapters_returns_only_active_for_subject(client, seed_catalog):
    response = client.get(f"/api/chapters/{seed_catalog['subject_id']}")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["id"] == seed_catalog["chapter_id"]


def test_questions_count_counts_only_active_questions(client, seed_catalog):
    response = client.post(
        "/api/questions/count",
        json={"chapter_ids": [seed_catalog["chapter_id"]]},
    )

    assert response.status_code == 200
    assert response.get_json() == {"count": 1}


def test_questions_count_empty_input_returns_zero(client):
    response = client.post("/api/questions/count", json={"chapter_ids": []})

    assert response.status_code == 200
    assert response.get_json() == {"count": 0}
