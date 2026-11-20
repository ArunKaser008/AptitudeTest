from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
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
) -> Assessment:
    assessment = Assessment(
        id=uuid.uuid4(),
        slug="foundation",
        title="Foundation Aptitude Test",
        description="A verified aptitude assessment.",
        status="published",
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
        question = QuestionVersion(
            logical_id=uuid.uuid4(),
            version_number=1,
            status="published",
            question_type="single_choice",
            prompt=f"What is {index} + 1?",
            topic="Arithmetic",
            difficulty="easy",
            options=[
                {"id": "correct", "text": str(index + 1)},
                {"id": "incorrect", "text": str(index + 2)},
            ],
            correct_answer={"option_id": "correct"},
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
