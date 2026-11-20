from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.main import app
from app.models import Batch, Base, College, User
from app.services.placement_auth import hash_password, issue_token
from app.services import placement_generator


@pytest.fixture
def placement_db() -> Session:
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
def placement_client(placement_db: Session) -> TestClient:
    def override_get_db():
        yield placement_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_tenant(
    db: Session,
    slug: str,
) -> tuple[College, Batch, User, User]:
    college = College(slug=slug, name=f"{slug.title()} College")
    db.add(college)
    db.flush()
    batch = Batch(
        college_id=college.id,
        name="2027 CSE",
        graduation_year=2027,
        branch="CSE",
        section="A",
    )
    db.add(batch)
    db.flush()
    admin = User(
        email=f"admin-{slug}@example.com",
        password_hash=hash_password("test-password-123"),
        display_name=f"{slug.title()} Admin",
        role="college_admin",
        college_id=college.id,
    )
    student = User(
        email=f"student-{slug}@example.com",
        password_hash=hash_password("test-password-123"),
        display_name=f"{slug.title()} Student",
        role="student",
        college_id=college.id,
        batch_id=batch.id,
    )
    db.add_all([admin, student])
    db.commit()
    db.refresh(college)
    db.refresh(batch)
    db.refresh(admin)
    db.refresh(student)
    return college, batch, admin, student


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user).access_token}"}


def question_payload(college_id: uuid.UUID, stem: str = "A placement question stem?") -> dict:
    return {
        "scope": "college",
        "college_id": str(college_id),
        "topic_slug": "percentages",
        "subtopic": "discounts",
        "question_type": "mcq_single",
        "source_type": "manual",
        "payload": {
            "stem": stem,
            "options": [
                {"id": "a", "text": "10 percent"},
                {"id": "b", "text": "20 percent"},
                {"id": "c", "text": "30 percent"},
                {"id": "d", "text": "40 percent"},
            ],
            "correct_option_id": "b",
            "shortcut_solution": "Use the percentage change formula.",
            "concept_solution": "Compare the change with the original value.",
            "estimated_seconds": 60,
            "difficulty": "medium",
            "company_tags": [],
        },
    }


def test_login_role_guard_and_college_scoped_batch_creation(
    placement_client: TestClient,
    placement_db: Session,
) -> None:
    platform_admin = User(
        email="root@example.com",
        password_hash=hash_password("platform-password-123"),
        display_name="Platform Admin",
        role="platform_admin",
        college_id=None,
    )
    placement_db.add(platform_admin)
    placement_db.commit()
    placement_db.refresh(platform_admin)

    login = placement_client.post(
        "/api/v1/placement/login",
        json={"email": "ROOT@example.com", "password": "platform-password-123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    college = placement_client.post(
        "/api/v1/placement/colleges",
        headers=headers,
        json={"slug": "north-campus", "name": "North Campus"},
    )
    assert college.status_code == 201
    batch = placement_client.post(
        "/api/v1/placement/batches",
        headers=headers,
        json={
            "college_id": college.json()["id"],
            "name": "2027 CSE",
            "graduation_year": 2027,
            "branch": "CSE",
        },
    )
    assert batch.status_code == 201
    assert batch.json()["college_id"] == college.json()["id"]
    assert placement_client.get("/api/v1/placement/colleges", headers=headers).status_code == 200
    assert placement_client.get(
        "/api/v1/placement/questions",
        headers={"Authorization": f"Bearer {issue_token(platform_admin).access_token}"},
    ).status_code == 200


def test_tenant_isolation_and_strict_question_validation(
    placement_client: TestClient,
    placement_db: Session,
) -> None:
    college_a, _, admin_a, _ = create_tenant(placement_db, "college-a")
    _, _, admin_b, _ = create_tenant(placement_db, "college-b")
    headers_a = auth(admin_a)
    headers_b = auth(admin_b)

    invalid = question_payload(college_a.id)
    invalid["payload"]["options"][3]["text"] = "10 percent"
    response = placement_client.post("/api/v1/placement/questions", headers=headers_a, json=invalid)
    assert response.status_code == 422

    created = placement_client.post(
        "/api/v1/placement/questions",
        headers=headers_a,
        json=question_payload(college_a.id),
    )
    assert created.status_code == 201
    question_id = created.json()["id"]
    other_bank = placement_client.get("/api/v1/placement/questions", headers=headers_b)
    assert other_bank.status_code == 200
    assert other_bank.json()["items"] == []
    assert placement_client.post(
        f"/api/v1/placement/questions/{question_id}/archive",
        headers=headers_b,
    ).status_code == 404


def test_college_admins_must_clone_global_questions_before_modifying(
    placement_client: TestClient,
    placement_db: Session,
) -> None:
    college, _, admin, _ = create_tenant(placement_db, "clone-campus")
    platform_admin = User(
        email="global-admin@example.com",
        password_hash=hash_password("platform-password-123"),
        display_name="Platform Admin",
        role="platform_admin",
        college_id=None,
    )
    placement_db.add(platform_admin)
    placement_db.commit()
    placement_db.refresh(platform_admin)
    global_payload = question_payload(college.id)
    global_payload["scope"] = "global"
    global_payload["college_id"] = None
    global_question = placement_client.post(
        "/api/v1/placement/questions",
        headers=auth(platform_admin),
        json=global_payload,
    )
    assert global_question.status_code == 201

    college_headers = auth(admin)
    denied_edit = placement_client.patch(
        f"/api/v1/placement/questions/{global_question.json()['id']}",
        headers=college_headers,
        json=question_payload(college.id, "An unauthorized edit to shared content?"),
    )
    assert denied_edit.status_code == 403
    denied_bulk = placement_client.post(
        "/api/v1/placement/questions/bulk",
        headers=college_headers,
        json={"question_ids": [global_question.json()["id"]], "action": "archive"},
    )
    assert denied_bulk.status_code == 403
    clone = placement_client.post(
        f"/api/v1/placement/questions/{global_question.json()['id']}/clone-to-college?college_id={college.id}",
        headers=college_headers,
    )
    assert clone.status_code == 200
    assert clone.json()["college_id"] == str(college.id)
    assert clone.json()["status"] == "draft"


def test_attempt_payload_hides_answers_and_uses_immutable_question_snapshot(
    placement_client: TestClient,
    placement_db: Session,
) -> None:
    college, _, admin, student = create_tenant(placement_db, "snapshot-campus")
    admin_headers = auth(admin)
    student_headers = auth(student)

    question = placement_client.post(
        "/api/v1/placement/questions",
        headers=admin_headers,
        json=question_payload(college.id),
    )
    assert question.status_code == 201
    question_id = question.json()["id"]
    approved = placement_client.post(
        "/api/v1/placement/ai/questions/review-action",
        headers=admin_headers,
        json={"actions": [{"question_id": question_id, "action": "approve"}]},
    )
    assert approved.status_code == 200

    test = placement_client.post(
        "/api/v1/placement/tests",
        headers=admin_headers,
        json={
            "title": "Placement fundamentals",
            "description": "",
            "scope": "college",
            "college_id": str(college.id),
            "duration_minutes": 10,
            "question_ids": [{"question_id": question_id, "section_name": "Quant"}],
        },
    )
    assert test.status_code == 201
    test_id = test.json()["id"]
    question_order = placement_client.get(
        f"/api/v1/placement/tests/{test_id}/questions",
        headers=admin_headers,
    )
    assert question_order.status_code == 200
    assert question_order.json()["questions"][0]["question_id"] == question_id
    assert placement_client.post(f"/api/v1/placement/tests/{test_id}/publish", headers=admin_headers).status_code == 200
    blocked_archive = placement_client.post(
        f"/api/v1/placement/questions/{question_id}/archive",
        headers=admin_headers,
    )
    assert blocked_archive.status_code == 409
    assignment = placement_client.post(
        "/api/v1/placement/assignments",
        headers=admin_headers,
        json={
            "test_id": test_id,
            "college_id": str(college.id),
            "starts_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "max_attempts": 1,
        },
    )
    assert assignment.status_code == 201
    updated_assignment = placement_client.patch(
        f"/api/v1/placement/assignments/{assignment.json()['id']}",
        headers=admin_headers,
        json={
            "batch_ids": [str(student.batch_id)],
            "branches": ["CSE"],
            "graduation_year": 2027,
            "starts_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            "ends_at": None,
            "max_attempts": 1,
        },
    )
    assert updated_assignment.status_code == 200
    assert updated_assignment.json()["branches"] == ["CSE"]

    started = placement_client.post(
        "/api/v1/placement/attempts/start",
        headers=student_headers,
        json={"assignment_id": assignment.json()["id"]},
    )
    assert started.status_code == 201
    attempt = started.json()
    retry = placement_client.post(
        "/api/v1/placement/attempts/start",
        headers=student_headers,
        json={"assignment_id": assignment.json()["id"]},
    )
    assert retry.status_code == 409
    question_view = attempt["questions"][0]
    assert "correct_option_id" not in question_view
    assert "shortcut_solution" not in question_view
    assert "concept_solution" not in question_view
    assert question_view["stem"] == "A placement question stem?"

    updated_payload = question_payload(college.id, "An edited question stem after the attempt started?")
    updated = placement_client.patch(
        f"/api/v1/placement/questions/{question_id}",
        headers=admin_headers,
        json=updated_payload,
    )
    assert updated.status_code == 200
    resumed = placement_client.get(f"/api/v1/placement/attempts/{attempt['id']}", headers=student_headers)
    assert resumed.status_code == 200
    assert resumed.json()["questions"][0]["stem"] == "A placement question stem?"

    saved = placement_client.patch(
        f"/api/v1/placement/attempts/{attempt['id']}/answer",
        headers=student_headers,
        json={
            "question_position": 0,
            "selected_option_id": "b",
            "marked_for_review": False,
            "time_spent_seconds": 25,
        },
    )
    assert saved.status_code == 200
    result = placement_client.post(
        f"/api/v1/placement/attempts/{attempt['id']}/submit",
        headers=student_headers,
    )
    assert result.status_code == 200
    assert result.json()["correct"] == 1
    assert result.json()["answers"][0]["time_spent_seconds"] == 25
    assert result.json()["answers"][0]["shortcut_solution"] == "Use the percentage change formula."
    assert result.json()["answers"][0]["mistake_tag"] == "fast_accurate"
    practice = placement_client.post(
        "/api/v1/placement/practice/similar",
        headers=student_headers,
        json={"attempt_id": attempt["id"], "topic_slugs": ["percentages"], "question_count": 2},
    )
    assert practice.status_code == 200
    assert len(practice.json()) == 2
    for practice_question in practice.json():
        assert practice_question["topic_slug"] == "percentages"
        assert practice_question["correct_option_id"] in {
            option["id"] for option in practice_question["options"]
        }
    unauthorized_practice = placement_client.post(
        "/api/v1/placement/practice/similar",
        headers=auth(create_tenant(placement_db, "other-campus")[3]),
        json={"attempt_id": attempt["id"], "question_count": 1},
    )
    assert unauthorized_practice.status_code == 404
    analytics = placement_client.get(
        f"/api/v1/placement/analytics/college?college_id={college.id}",
        headers=admin_headers,
    )
    assert analytics.status_code == 200
    assert analytics.json()["topic_breakdown"][0]["avg_time_seconds"] == 25


def test_parametric_numeric_generation_matches_its_answer_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setattr(placement_generator, "get_settings", lambda: Settings(llm_api_key=None))
    generated = asyncio.run(placement_generator.generate_question(
        prompt="Create applied percentage aptitude practice.",
        topic_slug="percentages",
        subtopic="ticket follow-up",
        difficulty="medium",
    ))

    correct = next(option for option in generated.options if option.id == generated.correct_option_id)
    assert generated.source_type == "parametric"
    assert generated.derivation
    assert float(correct.text) == generated.derived_result
    assert len({option.text for option in generated.options}) == 4


def test_llm_response_schema_is_strict_and_requires_every_output_field() -> None:
    schema = placement_generator._placement_question_output_schema("logical-reasoning", "medium")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["topic_slug"]["enum"] == ["logical-reasoning"]
    assert schema["properties"]["difficulty"]["enum"] == ["medium"]
    options = schema["properties"]["options"]["items"]
    assert options["additionalProperties"] is False
    assert options["required"] == ["id", "text"]


def test_csv_extraction_reports_invalid_rows_instead_of_silently_skipping(
    placement_client: TestClient,
    placement_db: Session,
) -> None:
    _, _, admin, _ = create_tenant(placement_db, "import-campus")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["topic_slug", "question_type"])
    writer.writeheader()
    writer.writerow({"topic_slug": "percentages", "question_type": "mcq_single"})

    response = placement_client.post(
        "/api/v1/placement/ai/extract-questions",
        headers=auth(admin),
        json={"filename": "questions.csv", "content": output.getvalue()},
    )

    assert response.status_code == 201
    assert response.json()["questions"] == []
    assert response.json()["errors"][0]["row_number"] == 2
    assert "payload JSON" in response.json()["errors"][0]["message"]
