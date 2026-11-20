import csv
import io
import json
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from pydantic import ValidationError

from app.api.dependencies import DatabaseSession
from app.schemas import (
    AssessmentCloneIn,
    AssessmentConfigUpdateIn,
    AssessmentCreateIn,
    AuthoringAssessmentOut,
    BulkImportOut,
    ImportRowError,
    QuestionDraftIn,
    QuestionListOut,
    QuestionOut,
    SectionPoolUpdateIn,
    SectionReadinessOut,
)
from app.services import authoring_service
from app.services.assessment_service import DomainError

router = APIRouter(prefix="/authoring")


@router.get("/questions", response_model=QuestionListOut)
def get_questions(
    db: DatabaseSession,
    search: Annotated[str | None, Query(max_length=200)] = None,
    topic: Annotated[str | None, Query(max_length=150)] = None,
    difficulty: Literal["easy", "medium", "hard"] | None = None,
    status_filter: Annotated[
        Literal["draft", "review", "published", "archived"] | None,
        Query(alias="status"),
    ] = None,
    verified: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> QuestionListOut:
    return authoring_service.list_questions(
        db,
        search=search,
        topic=topic,
        difficulty=difficulty,
        status=status_filter,
        verified=verified,
        page=page,
        page_size=page_size,
    )


@router.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionDraftIn, db: DatabaseSession) -> QuestionOut:
    return authoring_service.create_question(db, payload)


@router.put("/questions/{question_id}", response_model=QuestionOut)
def edit_question(
    question_id: UUID,
    payload: QuestionDraftIn,
    db: DatabaseSession,
) -> QuestionOut:
    return authoring_service.update_question(db, question_id, payload)


@router.post("/questions/{question_id}/verify-publish", response_model=QuestionOut)
def verify_publish_question(question_id: UUID, db: DatabaseSession) -> QuestionOut:
    return authoring_service.verify_and_publish_question(db, question_id)


@router.post("/questions/{question_id}/archive", response_model=dict[str, int])
def archive_question(question_id: UUID, db: DatabaseSession) -> dict[str, int]:
    return {"active_pool_usage_count": authoring_service.archive_question(db, question_id)}


def _parse_import_rows(content_type: str, body: bytes) -> list[dict[str, Any]]:
    if "application/json" in content_type:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DomainError(422, "invalid_import", "The JSON import payload is invalid.") from error
        if isinstance(data, dict):
            data = data.get("questions")
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise DomainError(422, "invalid_import", "The JSON import must be a question array or an object with a questions array.")
        return data
    if "text/csv" in content_type or "application/csv" in content_type:
        try:
            text = body.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise DomainError(422, "invalid_import", "The CSV import must include a header row.")
            rows = []
            for row in reader:
                converted: dict[str, Any] = dict(row)
                for field in ("options", "correct_answer", "stimulus"):
                    raw = converted.get(field)
                    if raw:
                        converted[field] = json.loads(raw)
                    elif field == "stimulus":
                        converted[field] = None
                for field in ("marks", "negative_marks"):
                    raw = converted.get(field)
                    if raw not in (None, ""):
                        converted[field] = float(raw)
                rows.append(converted)
            return rows
        except (UnicodeDecodeError, csv.Error, json.JSONDecodeError, ValueError) as error:
            raise DomainError(422, "invalid_import", "The CSV import contains malformed values.") from error
    raise DomainError(415, "unsupported_import_type", "Use application/json or text/csv for question imports.")


@router.post("/questions/bulk-import", response_model=BulkImportOut)
async def bulk_import_questions(
    request: Request,
    db: DatabaseSession,
    dry_run: bool = True,
) -> BulkImportOut:
    rows = _parse_import_rows(request.headers.get("content-type", ""), await request.body())
    valid: list[QuestionDraftIn] = []
    errors: list[ImportRowError] = []
    for row_index, row in enumerate(rows, start=1):
        try:
            valid.append(QuestionDraftIn.model_validate(row))
        except ValidationError as error:
            for issue in error.errors():
                errors.append(ImportRowError(
                    row_index=row_index,
                    field=".".join(str(part) for part in issue["loc"]),
                    message=issue["msg"],
                ))
        except (TypeError, ValueError) as error:
            errors.append(ImportRowError(row_index=row_index, field="question", message=str(error)))

    imported_count = 0
    if not dry_run:
        imported_count = len(authoring_service.create_questions(db, valid))
    return BulkImportOut(
        dry_run=dry_run,
        imported_count=imported_count,
        valid_count=len(valid),
        errors=errors,
    )


@router.get("/assessments", response_model=list[AuthoringAssessmentOut])
def get_assessments(db: DatabaseSession) -> list[AuthoringAssessmentOut]:
    return authoring_service.list_assessments(db)


@router.post("/assessments", response_model=AuthoringAssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreateIn,
    db: DatabaseSession,
) -> AuthoringAssessmentOut:
    return authoring_service.create_assessment(db, payload)


@router.post("/assessments/{assessment_id}/clone", response_model=AuthoringAssessmentOut, status_code=status.HTTP_201_CREATED)
def clone_assessment(
    assessment_id: UUID,
    payload: AssessmentCloneIn,
    db: DatabaseSession,
) -> AuthoringAssessmentOut:
    return authoring_service.clone_assessment(db, assessment_id, payload)


@router.put("/assessments/{assessment_id}/config", response_model=AuthoringAssessmentOut)
def update_assessment_config(
    assessment_id: UUID,
    payload: AssessmentConfigUpdateIn,
    db: DatabaseSession,
) -> AuthoringAssessmentOut:
    return authoring_service.update_assessment_config(db, assessment_id, payload)


@router.put("/sections/{section_id}/pool", response_model=SectionReadinessOut)
def update_section_pool(
    section_id: UUID,
    payload: SectionPoolUpdateIn,
    db: DatabaseSession,
) -> SectionReadinessOut:
    return authoring_service.update_section_pool(
        db,
        section_id,
        payload.question_version_ids,
    )


@router.post("/assessments/{assessment_id}/publish", response_model=AuthoringAssessmentOut)
def publish_assessment(assessment_id: UUID, db: DatabaseSession) -> AuthoringAssessmentOut:
    return authoring_service.publish_assessment(db, assessment_id)
