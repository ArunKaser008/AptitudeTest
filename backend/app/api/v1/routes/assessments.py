from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status

from app.api.dependencies import Candidate, DatabaseSession
from app.schemas import (
    AssessmentOut,
    AttemptCreateIn,
    AttemptDetailOut,
    AttemptOut,
    AttemptSubmitIn,
    AttemptResultOut,
    CandidateSessionOut,
    PositionUpdateIn,
    PracticeSimilarIn,
    PracticeTopicOut,
    ResponseIn,
    ResponseOut,
    ReviewFlagIn,
    WeakTopicPracticeIn,
)
from app.services import assessment_service
from app.services import practice_service

router = APIRouter()


@router.post(
    "/candidate-sessions",
    response_model=CandidateSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate_session(db: DatabaseSession) -> CandidateSessionOut:
    return assessment_service.create_candidate_session(db)


@router.get("/assessments", response_model=list[AssessmentOut])
def list_assessments(
    db: DatabaseSession,
    category: Literal["aptitude", "company_mock", "practice"] | None = None,
    target_role: str | None = Query(default=None, alias="target_role", max_length=150),
) -> list[AssessmentOut]:
    assessments = assessment_service.list_available_assessments(db)
    if category is not None:
        assessments = [item for item in assessments if item.category == category]
    if target_role is not None:
        assessments = [item for item in assessments if item.target_role == target_role]
    return assessments


@router.get("/practice/topics", response_model=list[PracticeTopicOut])
def list_practice_topics(db: DatabaseSession) -> list[PracticeTopicOut]:
    return practice_service.list_topics(db)


@router.post(
    "/practice/session",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_practice_session(
    payload: PracticeSimilarIn,
    db: DatabaseSession,
    candidate: Candidate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100)],
) -> AttemptOut:
    return await assessment_service.create_similar_practice(
        db,
        candidate,
        payload,
        idempotency_key,
    )


@router.post(
    "/practice/similar",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_similar_practice(
    payload: PracticeSimilarIn,
    db: DatabaseSession,
    candidate: Candidate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100)],
) -> AttemptOut:
    return await assessment_service.create_similar_practice(
        db,
        candidate,
        payload,
        idempotency_key,
    )


@router.post(
    "/practice-weak-topics",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
)
def create_weak_topic_practice(
    payload: WeakTopicPracticeIn,
    db: DatabaseSession,
    candidate: Candidate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100)],
) -> AttemptOut:
    return assessment_service.create_weak_topic_practice(
        db,
        candidate,
        payload.source_attempt_id,
        idempotency_key,
    )


@router.post(
    "/attempts",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_attempt(
    payload: AttemptCreateIn,
    db: DatabaseSession,
    candidate: Candidate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100)],
) -> AttemptOut:
    return await assessment_service.create_attempt(
        db,
        candidate,
        payload.assessment_slug,
        idempotency_key,
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptDetailOut)
def get_attempt(
    attempt_id: UUID,
    db: DatabaseSession,
    candidate: Candidate,
) -> AttemptDetailOut:
    return assessment_service.get_attempt(db, attempt_id, candidate.id)


@router.put(
    "/attempts/{attempt_id}/responses/{question_id}",
    response_model=ResponseOut,
)
def save_response(
    attempt_id: UUID,
    question_id: UUID,
    payload: ResponseIn,
    db: DatabaseSession,
    candidate: Candidate,
) -> ResponseOut:
    return assessment_service.save_response(
        db,
        candidate.id,
        attempt_id,
        question_id,
        payload.answer,
        payload.time_spent_seconds,
    )


@router.delete(
    "/attempts/{attempt_id}/responses/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_response(
    attempt_id: UUID,
    question_id: UUID,
    db: DatabaseSession,
    candidate: Candidate,
) -> Response:
    assessment_service.clear_response(db, candidate.id, attempt_id, question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/attempts/{attempt_id}/questions/{question_id}/review",
)
def set_review_flag(
    attempt_id: UUID,
    question_id: UUID,
    payload: ReviewFlagIn,
    db: DatabaseSession,
    candidate: Candidate,
) -> dict[str, bool]:
    marked = assessment_service.set_review_flag(
        db,
        candidate.id,
        attempt_id,
        question_id,
        payload.marked,
    )
    return {"marked": marked}


@router.patch("/attempts/{attempt_id}/position")
def update_question_position(
    attempt_id: UUID,
    payload: PositionUpdateIn,
    db: DatabaseSession,
    candidate: Candidate,
) -> dict[str, int]:
    position = assessment_service.update_question_position(
        db,
        candidate.id,
        attempt_id,
        payload.question_id,
        payload.time_spent_seconds,
    )
    return {"current_position": position}


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResultOut)
def submit_attempt(
    attempt_id: UUID,
    db: DatabaseSession,
    candidate: Candidate,
    payload: AttemptSubmitIn | None = None,
) -> AttemptResultOut:
    return assessment_service.submit_attempt(
        db,
        candidate.id,
        attempt_id,
        question_id=payload.question_id if payload else None,
        time_spent_seconds=payload.time_spent_seconds if payload else 0,
    )


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResultOut)
def get_attempt_result(
    attempt_id: UUID,
    db: DatabaseSession,
    candidate: Candidate,
) -> AttemptResultOut:
    return assessment_service.get_attempt_result(db, candidate.id, attempt_id)
