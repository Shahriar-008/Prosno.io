from app.models import Question, QuizSession


def test_question_to_dict_simple():
    question = Question(
        id=10,
        question_text="What is 2 + 2?",
        question_type="simple",
        answer_options=["1", "2", "3", "4"],
        correct_answer="4",
        chapter_id=1,
    )

    data = question.to_dict()

    assert data["id"] == "10"
    assert data["question_text"] == "What is 2 + 2?"
    assert data["type"] == "simple"
    assert data["answer_options"] == ["1", "2", "3", "4"]
    assert data["correct_answer"] == "4"
    assert "sub_options" not in data
    assert "final_prompt" not in data


def test_question_to_dict_complex():
    question = Question(
        id=11,
        question_text="Read and answer",
        question_type="complex",
        sub_options=["i. A", "ii. B"],
        final_prompt="Which one is correct?",
        answer_options=["i only", "ii only", "both", "none"],
        correct_answer="i only",
        chapter_id=1,
    )

    data = question.to_dict()

    assert data["id"] == "11"
    assert data["type"] == "complex"
    assert data["sub_options"] == ["i. A", "ii. B"]
    assert data["final_prompt"] == "Which one is correct?"


def test_quiz_session_grade_updates_score_and_total():
    session = QuizSession(
        quiz_id=1,
        student_name="Nadia",
        session_token="token-1",
        responses_json={"0": "A", "1": "C", "2": "B"},
    )
    questions = [
        {"correct_answer": "A"},
        {"correct_answer": "B"},
        {"correct_answer": "B"},
    ]

    session.grade(questions)

    assert session.score == 2
    assert session.total_questions == 3
    assert session.score_percentage == 67


def test_quiz_session_grade_no_responses_keeps_existing_values():
    session = QuizSession(
        quiz_id=1,
        student_name="Rafi",
        session_token="token-2",
        responses_json=None,
        score=5,
        total_questions=7,
    )
    questions = [{"correct_answer": "A"}]

    session.grade(questions)

    assert session.score == 5
    assert session.total_questions == 7
