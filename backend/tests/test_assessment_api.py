from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.main import app
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentConfigVersion,
    AssessmentQuestionPool,
    AssessmentSection,
    AttemptQuestion,
    Base,
    CandidateSession,
    QuestionVersion,
)
from app.schemas import AttemptResultOut
from app.seed import seed_default_assessments
from app.services import assessment_service


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    with test_session() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_published_assessment(
    db: Session,
    *,
    pool_size: int = 4,
    question_count: int = 2,
    verified: bool = True,
    question_type: str = "single_choice",
) -> Assessment:
    assessment = Assessment(
        id=uuid.uuid4(),
        slug="foundation",
        title="Foundation Aptitude Test",
        description="A verified aptitude assessment.",
        status="published",
        ai_generation_enabled=False,
    )
    config = AssessmentConfigVersion(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        version_number=1,
        status="published",
        duration_seconds=600,
        show_explanations_after_submission=True,
        randomize_questions=True,
        randomize_options=True,
        scoring_policy={"minimum_score_zero": True},
    )
    section = AssessmentSection(
        id=uuid.uuid4(),
        config_version_id=config.id,
        section_key="quantitative",
        title="Quantitative",
        position=0,
        question_count=question_count,
        marks_per_question=2,
        negative_marks=0.5,
    )
    db.add_all([assessment, config, section])
    db.flush()
    now = datetime.now(timezone.utc)
    for index in range(pool_size):
        options = [
            {"id": "correct", "text": str(index + 1)},
            {"id": "incorrect", "text": str(index + 2)},
        ] if question_type != "numeric" else []
        if question_type == "multi_choice":
            options.append({"id": "also-correct", "text": "Also correct"})
            correct_answer = {"option_ids": ["correct", "also-correct"]}
        elif question_type == "numeric":
            correct_answer = {"value": index + 1, "tolerance": 0.1}
        else:
            correct_answer = {"option_id": "correct"}
        question = QuestionVersion(
            logical_id=uuid.uuid4(),
            version_number=1,
            status="published",
            question_type=question_type,
            prompt=f"What is {index} + 1?",
            topic="Arithmetic",
            difficulty="easy",
            options=options,
            correct_answer=correct_answer,
            explanation="Add one to the number.",
            marks=2,
            negative_marks=0.5,
            verified_at=now if verified else None,
        )
        db.add(question)
        db.flush()
        db.add(AssessmentQuestionPool(section_id=section.id, question_version_id=question.id))
    db.commit()
    return assessment


def create_candidate(client: TestClient) -> str:
    response = client.post("/api/v1/candidate-sessions")
    assert response.status_code == 201
    token = response.json()["session_token"]
    assert len(token) >= 40
    return token


def start_attempt(client: TestClient, token: str, idempotency_key: str = "first-attempt-key-001"):
    return client.post(
        "/api/v1/attempts",
        headers={"X-Candidate-Token": token, "Idempotency-Key": idempotency_key},
        json={"assessment_slug": "foundation"},
    )


def test_empty_live_question_bank_never_exposes_unverified_assessments(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session, pool_size=4, question_count=2, verified=False)

    response = client.get("/api/v1/assessments")

    assert response.status_code == 200
    assert response.json() == []
    assert client.post("/api/v1/candidate-sessions").status_code == 201


def test_attempt_lifecycle_is_owned_timed_idempotent_and_hides_answer_keys(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session)
    token = create_candidate(client)
    candidate_headers = {"X-Candidate-Token": token}

    catalog = client.get("/api/v1/assessments")
    assert catalog.status_code == 200
    assert catalog.json()[0]["question_count"] == 2
    assert catalog.json()[0]["duration_seconds"] == 600

    start = start_attempt(client, token)
    assert start.status_code == 201
    attempt = start.json()
    assert attempt["status"] == "in_progress"
    assert attempt["question_count"] == 2
    started_at = datetime.fromisoformat(attempt["started_at"])
    deadline_at = datetime.fromisoformat(attempt["deadline_at"])
    assert (deadline_at - started_at).total_seconds() == 600

    retry = start_attempt(client, token)
    assert retry.status_code == 201
    assert retry.json()["id"] == attempt["id"]

    details = client.get(
        f"/api/v1/attempts/{attempt['id']}",
        headers=candidate_headers,
    )
    assert details.status_code == 200
    assert len(details.json()["questions"]) == 2
    question = details.json()["questions"][0]
    question_json = str(question).lower()
    assert "correct_answer" not in question_json
    assert "explanation" not in question_json
    assert question["answer"] is None
    assert question["visited"] is True
    assert details.json()["current_position"] == 0

    next_question = details.json()["questions"][1]
    moved = client.patch(
        f"/api/v1/attempts/{attempt['id']}/position",
        headers=candidate_headers,
        json={"question_id": next_question["id"], "time_spent_seconds": 6},
    )
    assert moved.status_code == 200
    assert moved.json()["current_position"] == 1
    refreshed = client.get(
        f"/api/v1/attempts/{attempt['id']}",
        headers=candidate_headers,
    )
    assert refreshed.json()["questions"][1]["visited"] is True

    review_flag = client.patch(
        f"/api/v1/attempts/{attempt['id']}/questions/{question['id']}/review",
        headers=candidate_headers,
        json={"marked": True},
    )
    assert review_flag.status_code == 200
    assert review_flag.json() == {"marked": True}

    invalid = client.put(
        f"/api/v1/attempts/{attempt['id']}/responses/{question['id']}",
        headers=candidate_headers,
        json={"answer": {"option_id": "unknown"}, "time_spent_seconds": 4},
    )
    assert invalid.status_code == 422

    saved = client.put(
        f"/api/v1/attempts/{attempt['id']}/responses/{question['id']}",
        headers=candidate_headers,
        json={"answer": {"option_id": "incorrect"}, "time_spent_seconds": 4},
    )
    assert saved.status_code == 200
    assert saved.json()["answer"] == {"option_id": "incorrect"}

    result = client.post(
        f"/api/v1/attempts/{attempt['id']}/submit",
        headers=candidate_headers,
    )
    assert result.status_code == 200
    assert result.json()["status"] == "submitted"
    assert result.json()["correct"] == 0
    assert result.json()["incorrect"] == 1
    assert result.json()["unanswered"] == 1
    assert result.json()["score"] == 0
    assert result.json()["max_score"] == 4
    assert result.json()["assessment_title"] == "Foundation Aptitude Test"
    assert result.json()["review"][0]["correct_answer"] == {"option_id": "correct"}
    assert result.json()["review"][0]["explanation"] == "Add one to the number."

    duplicate_submit = client.post(
        f"/api/v1/attempts/{attempt['id']}/submit",
        headers=candidate_headers,
    )
    assert duplicate_submit.status_code == 200
    assert duplicate_submit.json() == result.json()
    assert client.get(
        f"/api/v1/attempts/{attempt['id']}/results",
        headers=candidate_headers,
    ).json() == result.json()

    closed_response = client.put(
        f"/api/v1/attempts/{attempt['id']}/responses/{question['id']}",
        headers=candidate_headers,
        json={"answer": {"option_id": "correct"}, "time_spent_seconds": 1},
    )
    assert closed_response.status_code == 409

    other_token = create_candidate(client)
    unauthorized = client.get(
        f"/api/v1/attempts/{attempt['id']}",
        headers={"X-Candidate-Token": other_token},
    )
    assert unauthorized.status_code == 404

    stored_session = db_session.scalar(select(CandidateSession))
    assert stored_session is not None
    assert stored_session.token_hash != token
    assert stored_session.token_hash not in token


def test_question_selection_avoids_reuse_until_the_verified_pool_cycles(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session, pool_size=4, question_count=2)
    token = create_candidate(client)
    headers = {"X-Candidate-Token": token}

    attempts: list[set[str]] = []
    for index in range(2):
        start = start_attempt(client, token, f"separate-attempt-key-{index:03d}")
        assert start.status_code == 201
        details = client.get(f"/api/v1/attempts/{start.json()['id']}", headers=headers)
        ids = {question["id"] for question in details.json()["questions"]}
        assert len(ids) == 2
        attempts.append(ids)

    assert attempts[0].isdisjoint(attempts[1])

    assignments = db_session.scalars(select(AttemptQuestion)).all()
    assert len(assignments) == 4


def test_expired_attempt_is_finalized_by_server_and_candidate_token_is_required(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session)
    token = create_candidate(client)
    start = start_attempt(client, token)
    attempt_id = uuid.UUID(start.json()["id"])
    attempt = db_session.get(AssessmentAttempt, attempt_id)
    assert attempt is not None
    past = datetime.now(timezone.utc) - timedelta(minutes=2)
    attempt.started_at = past - timedelta(minutes=10)
    attempt.deadline_at = past
    db_session.commit()

    expired = client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers={"X-Candidate-Token": token},
    )
    assert expired.status_code == 200
    assert expired.json()["status"] == "expired"

    result = client.get(
        f"/api/v1/attempts/{attempt_id}/results",
        headers={"X-Candidate-Token": token},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "expired"
    assert result.json()["unanswered"] == 2

    no_token = client.get(f"/api/v1/attempts/{attempt_id}")
    assert no_token.status_code == 401


def test_alembic_core_migration_matches_registered_model_tables() -> None:
    engine = create_engine("sqlite://")
    migration_config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
        table_names = set(Base.metadata.tables)
        migrated_tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        assert migrated_tables == table_names
        command.check(migration_config)
    engine.dispose()


def test_result_snapshot_has_backward_compatible_time_and_topic_defaults() -> None:
    legacy_snapshot = {
        "attempt_id": str(uuid.uuid4()),
        "assessment_slug": "foundation",
        "assessment_title": "Foundation Aptitude Test",
        "status": "submitted",
        "score": 1,
        "max_score": 2,
        "correct": 1,
        "incorrect": 0,
        "unanswered": 0,
        "accuracy_percent": 100,
        "attempt_rate_percent": 100,
        "elapsed_seconds": 30,
        "sections": [],
        "review": [{
            "question_id": str(uuid.uuid4()),
            "position": 0,
            "section": "Quantitative",
            "topic": "Arithmetic",
            "prompt": "What is 1 + 1?",
            "options": [],
            "answer": None,
            "correct_answer": None,
            "explanation": None,
            "is_correct": None,
        }],
    }

    result = AttemptResultOut.model_validate(legacy_snapshot)

    assert result.review[0].time_spent_seconds == 0
    assert result.topics == []


def test_topic_diagnostics_aggregate_accuracy_and_question_time(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session, pool_size=4, question_count=2)
    token = create_candidate(client)
    start = start_attempt(client, token)
    attempt_id = start.json()["id"]
    details = client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers={"X-Candidate-Token": token},
    ).json()
    first = details["questions"][0]

    saved = client.put(
        f"/api/v1/attempts/{attempt_id}/responses/{first['id']}",
        headers={"X-Candidate-Token": token},
        json={"answer": {"option_id": "correct"}, "time_spent_seconds": 18},
    )
    assert saved.status_code == 200
    result = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        headers={"X-Candidate-Token": token},
    )

    assert result.status_code == 200
    assert result.json()["review"][0]["time_spent_seconds"] == 18
    assert result.json()["topics"] == [{
        "topic": "Arithmetic",
        "correct": 1,
        "incorrect": 0,
        "unanswered": 1,
        "accuracy_percent": 100,
        "avg_time_seconds": 9,
    }]


def test_submission_records_time_on_the_current_question(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session, pool_size=4, question_count=2)
    token = create_candidate(client)
    headers = {"X-Candidate-Token": token}
    attempt_id = start_attempt(client, token).json()["id"]
    question = client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers=headers,
    ).json()["questions"][0]

    result = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        headers=headers,
        json={"question_id": question["id"], "time_spent_seconds": 13},
    )

    assert result.status_code == 200
    review = next(item for item in result.json()["review"] if item["position"] == question["position"])
    assert review["time_spent_seconds"] == 13


def test_weak_topic_practice_uses_candidate_diagnostics_and_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session, pool_size=4, question_count=2)
    token = create_candidate(client)
    headers = {"X-Candidate-Token": token}
    source_id = start_attempt(client, token).json()["id"]
    question = client.get(
        f"/api/v1/attempts/{source_id}",
        headers=headers,
    ).json()["questions"][0]
    client.put(
        f"/api/v1/attempts/{source_id}/responses/{question['id']}",
        headers=headers,
        json={"answer": {"option_id": "incorrect"}, "time_spent_seconds": 25},
    )
    submitted = client.post(f"/api/v1/attempts/{source_id}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["topics"][0]["accuracy_percent"] == 0

    practice = client.post(
        "/api/v1/practice-weak-topics",
        headers={**headers, "Idempotency-Key": "weak-topic-drill-key-001"},
        json={"source_attempt_id": source_id},
    )
    assert practice.status_code == 201
    assert practice.json()["title"] == "Focused practice · Foundation Aptitude Test"
    assert practice.json()["question_count"] == 4
    repeat = client.post(
        "/api/v1/practice-weak-topics",
        headers={**headers, "Idempotency-Key": "weak-topic-drill-key-001"},
        json={"source_attempt_id": source_id},
    )
    assert repeat.status_code == 201
    assert repeat.json()["id"] == practice.json()["id"]


@pytest.mark.parametrize(
    ("question_type", "answer"),
    [
        ("multi_choice", {"option_ids": ["correct", "also-correct"]}),
        ("numeric", {"value": 1.05}),
    ],
)
def test_rich_question_types_accept_responses_and_score_correctly(
    client: TestClient,
    db_session: Session,
    question_type: str,
    answer: dict[str, object],
) -> None:
    add_published_assessment(
        db_session,
        pool_size=2,
        question_count=1,
        question_type=question_type,
    )
    token = create_candidate(client)
    attempt_id = start_attempt(client, token).json()["id"]
    question = client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers={"X-Candidate-Token": token},
    ).json()["questions"][0]
    if question_type == "numeric":
        assigned = db_session.get(AttemptQuestion, uuid.UUID(question["id"]))
        assert assigned is not None
        version = db_session.get(QuestionVersion, assigned.question_version_id)
        assert version is not None
        answer = {"value": version.correct_answer["value"] + 0.05}

    saved = client.put(
        f"/api/v1/attempts/{attempt_id}/responses/{question['id']}",
        headers={"X-Candidate-Token": token},
        json={"answer": answer, "time_spent_seconds": 10},
    )
    assert saved.status_code == 200
    result = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        headers={"X-Candidate-Token": token},
    )

    assert result.status_code == 200
    assert result.json()["correct"] == 1
    assert result.json()["score"] == 2


def test_authoring_published_question_edit_forks_version_and_archive_is_soft(
    client: TestClient,
    db_session: Session,
) -> None:
    add_published_assessment(db_session)
    original = db_session.scalar(select(QuestionVersion))
    assert original is not None
    payload = {
        "question_type": "single_choice",
        "prompt": "Updated arithmetic question?",
        "topic": "Arithmetic",
        "difficulty": "medium",
        "options": [
            {"id": "correct", "text": "2"},
            {"id": "incorrect", "text": "3"},
        ],
        "correct_answer": {"option_id": "correct"},
        "explanation": "The sum is two.",
        "marks": 2,
        "negative_marks": 0.5,
    }

    edited = client.put(f"/api/v1/authoring/questions/{original.id}", json=payload)

    assert edited.status_code == 200
    assert edited.json()["id"] != str(original.id)
    assert edited.json()["logical_id"] == str(original.logical_id)
    assert edited.json()["version_number"] == 2
    assert edited.json()["status"] == "draft"
    assert db_session.get(QuestionVersion, original.id).prompt == "What is 0 + 1?"

    archived = client.post(f"/api/v1/authoring/questions/{original.id}/archive")
    assert archived.status_code == 200
    assert archived.json()["active_pool_usage_count"] == 1
    assert db_session.get(QuestionVersion, original.id).status == "archived"
    assert db_session.scalar(select(AssessmentQuestionPool).where(
        AssessmentQuestionPool.question_version_id == original.id
    )) is not None


def test_bulk_import_dry_run_reports_row_errors_without_writing(
    client: TestClient,
    db_session: Session,
) -> None:
    rows = [
        {
            "question_type": "single_choice",
            "prompt": "What is 1 + 1?",
            "topic": "Arithmetic",
            "difficulty": "easy",
            "options": [{"id": "two", "text": "2"}, {"id": "three", "text": "3"}],
            "correct_answer": {"option_id": "two"},
            "explanation": "Add the numbers.",
        },
        {
            "question_type": "single_choice",
            "prompt": "",
            "topic": "Arithmetic",
            "difficulty": "easy",
            "options": [],
            "correct_answer": {"option_id": "missing"},
            "explanation": "",
        },
    ]

    response = client.post("/api/v1/authoring/questions/bulk-import", json=rows)

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["valid_count"] == 1
    assert response.json()["imported_count"] == 0
    assert any(error["row_index"] == 2 for error in response.json()["errors"])
    assert db_session.scalar(select(func.count()).select_from(QuestionVersion)) == 0


def test_assessment_authoring_requires_ready_pools_before_publish(
    client: TestClient,
    db_session: Session,
) -> None:
    payload = {
        "slug": "new-foundation",
        "title": "New Foundation Assessment",
        "duration_seconds": 600,
        "show_explanations_after_submission": True,
        "randomize_questions": True,
        "randomize_options": True,
        "scoring_policy": {"minimum_score_zero": True},
        "sections": [{
            "section_key": "quant",
            "title": "Quantitative",
            "position": 0,
            "question_count": 1,
            "marks_per_question": 1,
            "negative_marks": 0,
        }],
    }
    created = client.post("/api/v1/authoring/assessments", json=payload)
    assert created.status_code == 201
    assessment_id = created.json()["id"]
    section_id = created.json()["sections"][0]["id"]
    not_ready = client.post(f"/api/v1/authoring/assessments/{assessment_id}/publish")
    assert not_ready.status_code == 409

    question = client.post(
        "/api/v1/authoring/questions",
        json={
            "question_type": "single_choice",
            "prompt": "What is 1 + 1?",
            "topic": "Arithmetic",
            "difficulty": "easy",
            "options": [{"id": "two", "text": "2"}, {"id": "three", "text": "3"}],
            "correct_answer": {"option_id": "two"},
            "explanation": "Add the numbers.",
        },
    )
    question_id = question.json()["id"]
    verified = client.post(f"/api/v1/authoring/questions/{question_id}/verify-publish")
    assert verified.status_code == 200
    pool = client.put(
        f"/api/v1/authoring/sections/{section_id}/pool",
        json={"question_version_ids": [question_id]},
    )
    assert pool.status_code == 200
    assert pool.json()["eligible_verified_count"] == 1

    published = client.post(f"/api/v1/authoring/assessments/{assessment_id}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["config_status"] == "published"


def test_ai_blueprints_generate_parallel_unique_questions_before_timer_starts(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_default_assessments(db_session)
    token = create_candidate(client)
    headers = {"X-Candidate-Token": token}
    original_generate = assessment_service.ai_question_generator.generate_questions
    active = 0
    maximum_active = 0
    completed_at: list[datetime] = []

    async def delayed_generate(request):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep(0.02)
            return await original_generate(request)
        finally:
            active -= 1
            completed_at.append(datetime.now(timezone.utc))

    monkeypatch.setattr(
        assessment_service.ai_question_generator,
        "generate_questions",
        delayed_generate,
    )
    first = client.post(
        "/api/v1/attempts",
        headers={**headers, "Idempotency-Key": "ai-blueprint-first-attempt"},
        json={"assessment_slug": "it-services-cognitive-quant-drive"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    details = client.get(f"/api/v1/attempts/{first_id}", headers=headers)
    assert details.status_code == 200
    first_question_ids = {item["id"] for item in details.json()["questions"]}
    assert len(first_question_ids) == 15
    assert maximum_active > 1
    persisted_started_at = datetime.fromisoformat(first.json()["started_at"]).replace(tzinfo=timezone.utc)
    assert persisted_started_at >= max(completed_at)

    second = client.post(
        "/api/v1/attempts",
        headers={**headers, "Idempotency-Key": "ai-blueprint-second-attempt"},
        json={"assessment_slug": "it-services-cognitive-quant-drive"},
    )
    assert second.status_code == 201
    second_details = client.get(f"/api/v1/attempts/{second.json()['id']}", headers=headers)
    second_question_ids = {item["id"] for item in second_details.json()["questions"]}
    assert len(second_question_ids) == 15
    assert first_question_ids.isdisjoint(second_question_ids)

    idempotent = client.post(
        "/api/v1/attempts",
        headers={**headers, "Idempotency-Key": "ai-blueprint-second-attempt"},
        json={"assessment_slug": "it-services-cognitive-quant-drive"},
    )
    assert idempotent.status_code == 201
    assert idempotent.json()["id"] == second.json()["id"]


def test_candidate_performance_recommendations_and_similar_practice(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_default_assessments(db_session)
    token = create_candidate(client)
    headers = {"X-Candidate-Token": token}
    started = client.post(
        "/api/v1/attempts",
        headers={**headers, "Idempotency-Key": "analytics-source-attempt-key"},
        json={"assessment_slug": "product-sde-analytical-cs-aptitude"},
    )
    assert started.status_code == 201
    attempt_id = started.json()["id"]
    details = client.get(f"/api/v1/attempts/{attempt_id}", headers=headers).json()
    first = details["questions"][0]
    attempt_question = db_session.get(AttemptQuestion, uuid.UUID(first["id"]))
    assert attempt_question is not None
    question_version = db_session.get(QuestionVersion, attempt_question.question_version_id)
    assert question_version is not None
    correct_id = question_version.correct_answer["option_id"]
    wrong_id = next(option["id"] for option in first["options"] if option["id"] != correct_id)
    saved = client.put(
        f"/api/v1/attempts/{attempt_id}/responses/{first['id']}",
        headers=headers,
        json={"answer": {"option_id": wrong_id}, "time_spent_seconds": 90},
    )
    assert saved.status_code == 200
    submitted = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
    assert submitted.status_code == 200

    performance = client.get("/api/v1/candidate/performance", headers=headers)
    assert performance.status_code == 200
    assert performance.json()["completed_attempts"] == 1
    assert performance.json()["trend"][0]["assessment_slug"] == "product-sde-analytical-cs-aptitude"
    assert any(item["incorrect"] == 1 and item["avg_time_seconds"] > 0 for item in performance.json()["topics"])

    recommendations = client.get("/api/v1/candidate/recommendations", headers=headers)
    assert recommendations.status_code == 200
    assert recommendations.json()["count"] == len(recommendations.json()["items"])
    assert any(item["kind"] == "weak_topic" for item in recommendations.json()["items"])
    assert any(item["kind"] == "progression" for item in recommendations.json()["items"])

    similar = client.post(
        "/api/v1/practice/similar",
        headers={**headers, "Idempotency-Key": "similar-practice-drill-key"},
        json={"source_attempt_id": attempt_id, "question_id": first["id"], "question_count": 3},
    )
    assert similar.status_code == 201
    drill_questions = client.get(
        f"/api/v1/attempts/{similar.json()['id']}",
        headers=headers,
    ).json()["questions"]
    assert len(drill_questions) == 3
    assert all(item["topic"] == first["topic"] for item in drill_questions)
