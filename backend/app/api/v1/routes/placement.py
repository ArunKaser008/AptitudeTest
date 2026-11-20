from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession
from app.models import User
from app.placement_schemas import (
    AssignmentCreateIn,
    AssignmentOut,
    AssignmentUpdateIn,
    AttemptAnswerIn,
    AttemptOut,
    AttemptResultOut,
    AttemptStartIn,
    BatchCreateIn,
    BatchOut,
    CollegeCreateIn,
    CollegeOut,
    ExtractQuestionsIn,
    ExtractQuestionsOut,
    GenerateTestIn,
    GenerateTestOut,
    LoginIn,
    QuestionBulkIn,
    QuestionBulkOut,
    QuestionListOut,
    QuestionOut,
    QuestionReplaceIn,
    QuestionWriteIn,
    PracticeQuestionOut,
    PracticeSimilarIn,
    ReviewActionsIn,
    StudentAnalyticsOut,
    TestCreateIn,
    TestOut,
    TestQuestionOrderIn,
    TestQuestionOrderOut,
    TestUpdateIn,
    TokenOut,
    UserCreateIn,
    UserOut,
)
from app.services import placement_service
from app.services.placement_auth import (
    get_placement_user,
    hash_password,
    issue_token,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/placement", tags=["placement-tests"])
PlacementUser = Annotated[User, Depends(get_placement_user)]
PlacementAdmin = Annotated[User, Depends(require_roles("platform_admin", "college_admin"))]
PlatformAdmin = Annotated[User, Depends(require_roles("platform_admin"))]
StudentUser = Annotated[User, Depends(require_roles("student"))]


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: DatabaseSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return issue_token(user)


@router.get("/me", response_model=UserOut)
def current_user(user: PlacementUser) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        college_id=user.college_id,
        batch_id=user.batch_id,
    )


@router.get("/colleges", response_model=list[CollegeOut])
def list_colleges(_: PlatformAdmin, db: DatabaseSession) -> list[CollegeOut]:
    return placement_service.list_colleges(db)


@router.post("/colleges", response_model=CollegeOut, status_code=status.HTTP_201_CREATED)
def create_college(payload: CollegeCreateIn, _: PlatformAdmin, db: DatabaseSession) -> CollegeOut:
    return placement_service.create_college(db, payload)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateIn, creator: PlacementAdmin, db: DatabaseSession) -> UserOut:
    user = placement_service.create_placement_user(
        db,
        creator,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        college_id=payload.college_id,
        batch_id=payload.batch_id,
    )
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        college_id=user.college_id,
        batch_id=user.batch_id,
    )


@router.get("/batches", response_model=list[BatchOut])
def list_batches(admin: PlacementAdmin, db: DatabaseSession) -> list[BatchOut]:
    return placement_service.list_batches(db, admin)


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreateIn, admin: PlacementAdmin, db: DatabaseSession) -> BatchOut:
    return placement_service.create_batch(db, admin, payload)


@router.get("/questions", response_model=QuestionListOut)
def list_questions(
    admin: PlacementAdmin,
    db: DatabaseSession,
    search: str | None = None,
    topic: str | None = None,
    difficulty: Literal["easy", "medium", "hard"] | None = None,
    scope: Literal["global", "college"] | None = None,
    question_status: Annotated[
        Literal["draft", "active", "archived"] | None,
        Query(alias="status"),
    ] = None,
    source_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> QuestionListOut:
    return placement_service.list_questions(
        db,
        admin,
        search=search,
        topic_slug=topic,
        difficulty=difficulty,
        scope=scope,
        status=question_status,
        source_type=source_type,
        page=page,
        page_size=page_size,
    )


@router.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionWriteIn, admin: PlacementAdmin, db: DatabaseSession) -> QuestionOut:
    return placement_service.create_question(db, admin, payload)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: UUID,
    payload: QuestionWriteIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> QuestionOut:
    return placement_service.update_question(db, admin, question_id, payload)


@router.post("/questions/{question_id}/archive", response_model=QuestionOut)
def archive_question(question_id: UUID, admin: PlacementAdmin, db: DatabaseSession) -> QuestionOut:
    return placement_service.archive_question(db, admin, question_id)


@router.post("/questions/{question_id}/clone-to-college", response_model=QuestionOut)
def clone_question(
    question_id: UUID,
    admin: PlacementAdmin,
    db: DatabaseSession,
    college_id: UUID | None = None,
) -> QuestionOut:
    return placement_service.clone_question_to_college(db, admin, question_id, college_id)


@router.post("/questions/bulk", response_model=QuestionBulkOut)
def bulk_questions(payload: QuestionBulkIn, admin: PlacementAdmin, db: DatabaseSession) -> QuestionBulkOut:
    return placement_service.bulk_questions(db, admin, payload)


@router.post("/ai/generate-test", response_model=GenerateTestOut, status_code=status.HTTP_201_CREATED)
async def generate_test(
    payload: GenerateTestIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> GenerateTestOut:
    return await placement_service.generate_test(db, admin, payload)


@router.post("/ai/extract-questions", response_model=ExtractQuestionsOut, status_code=status.HTTP_201_CREATED)
async def extract_questions(admin: PlacementAdmin, db: DatabaseSession, request: Request) -> ExtractQuestionsOut:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "filename") or not hasattr(upload, "read"):
            raise HTTPException(status_code=422, detail="Upload a file using the `file` field.")
        data = await upload.read(10_000_001)
        if len(data) > 10_000_000:
            raise HTTPException(status_code=413, detail="Uploaded files must be 10 MB or smaller.")
        text = placement_service.extract_uploaded_document(upload.filename or "upload.txt", data)
        college_raw = form.get("college_id")
        try:
            college_id = UUID(str(college_raw)) if college_raw else None
        except ValueError as error:
            raise HTTPException(status_code=422, detail="college_id must be a UUID.") from error
        filename = upload.filename or "upload.txt"
        suffix = filename.rsplit(".", 1)[-1].casefold()
        if suffix in {"pdf", "docx"}:
            filename = "extracted.txt"
        payload = ExtractQuestionsIn(filename=filename, content=text, college_id=college_id)
    else:
        payload = ExtractQuestionsIn.model_validate(await request.json())
    return await placement_service.extract_questions(db, admin, payload)


@router.post("/ai/questions/review-action")
async def review_actions(
    payload: ReviewActionsIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> dict[str, int]:
    return await placement_service.review_actions(db, admin, payload)


@router.post("/ai/questions/{question_id}/replace-similar", response_model=QuestionOut)
async def replace_similar(
    question_id: UUID,
    payload: QuestionReplaceIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> QuestionOut:
    return await placement_service.replace_question_similar(
        db,
        admin,
        question_id,
        test_id=payload.test_id,
        topic_slug=payload.topic_slug,
        subtopic=payload.subtopic,
    )


@router.get("/tests", response_model=list[TestOut])
def list_tests(admin: PlacementAdmin, db: DatabaseSession) -> list[TestOut]:
    return placement_service.list_tests(db, admin)


@router.post("/tests", response_model=TestOut, status_code=status.HTTP_201_CREATED)
def create_test(payload: TestCreateIn, admin: PlacementAdmin, db: DatabaseSession) -> TestOut:
    return placement_service.create_test(db, admin, payload)


@router.patch("/tests/{test_id}", response_model=TestOut)
def update_test(test_id: UUID, payload: TestUpdateIn, admin: PlacementAdmin, db: DatabaseSession) -> TestOut:
    return placement_service.update_test(db, admin, test_id, payload)


@router.get("/tests/{test_id}/questions", response_model=TestQuestionOrderOut)
def get_test_questions(test_id: UUID, admin: PlacementAdmin, db: DatabaseSession) -> TestQuestionOrderOut:
    return placement_service.get_test_question_order(db, admin, test_id)


@router.put("/tests/{test_id}/questions", response_model=TestOut)
def order_test_questions(
    test_id: UUID,
    payload: TestQuestionOrderIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> TestOut:
    return placement_service.update_test_question_order(db, admin, test_id, payload)


@router.post("/tests/{test_id}/publish", response_model=TestOut)
def publish_test(test_id: UUID, admin: PlacementAdmin, db: DatabaseSession) -> TestOut:
    return placement_service.set_test_status(db, admin, test_id, "published")


@router.post("/tests/{test_id}/archive", response_model=TestOut)
def archive_test(test_id: UUID, admin: PlacementAdmin, db: DatabaseSession) -> TestOut:
    return placement_service.set_test_status(db, admin, test_id, "archived")


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(admin: PlacementAdmin, db: DatabaseSession) -> list[AssignmentOut]:
    return placement_service.list_assignments(db, admin)


@router.post("/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreateIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> AssignmentOut:
    return placement_service.create_test_assignment(db, admin, payload)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: UUID,
    payload: AssignmentUpdateIn,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> AssignmentOut:
    return placement_service.update_test_assignment(db, admin, assignment_id, payload)


@router.post("/assignments/{assignment_id}/archive", response_model=AssignmentOut)
def archive_assignment(
    assignment_id: UUID,
    admin: PlacementAdmin,
    db: DatabaseSession,
) -> AssignmentOut:
    return placement_service.archive_test_assignment(db, admin, assignment_id)


@router.get("/student/assignments", response_model=list[AssignmentOut])
def student_assignments(student: StudentUser, db: DatabaseSession) -> list[AssignmentOut]:
    return placement_service.list_student_assignments(db, student)


@router.post("/attempts/start", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
def start_attempt(
    payload: AttemptStartIn,
    student: StudentUser,
    db: DatabaseSession,
) -> AttemptOut:
    return placement_service.start_attempt(db, student, payload.assignment_id)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: UUID, student: StudentUser, db: DatabaseSession) -> AttemptOut:
    return placement_service.get_attempt(db, student, attempt_id)


@router.patch("/attempts/{attempt_id}/answer", response_model=AttemptOut)
def save_answer(
    attempt_id: UUID,
    payload: AttemptAnswerIn,
    student: StudentUser,
    db: DatabaseSession,
) -> AttemptOut:
    return placement_service.save_attempt_answer(db, student, attempt_id, payload)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResultOut)
def submit_attempt(attempt_id: UUID, student: StudentUser, db: DatabaseSession) -> AttemptResultOut:
    return placement_service.submit_attempt(db, student, attempt_id)


@router.get("/attempts/{attempt_id}/review", response_model=AttemptResultOut)
def attempt_review(attempt_id: UUID, student: StudentUser, db: DatabaseSession) -> AttemptResultOut:
    return placement_service.get_attempt_review(db, student, attempt_id)


@router.post("/practice/similar", response_model=list[PracticeQuestionOut])
async def similar_practice(
    payload: PracticeSimilarIn,
    student: StudentUser,
    db: DatabaseSession,
) -> list[PracticeQuestionOut]:
    return await placement_service.generate_similar_practice(db, student, payload)


@router.get("/analytics/student", response_model=StudentAnalyticsOut)
def student_analytics(student: StudentUser, db: DatabaseSession) -> StudentAnalyticsOut:
    return placement_service.student_analytics(db, student)


@router.get("/analytics/college")
def college_analytics(
    admin: PlacementAdmin,
    db: DatabaseSession,
    college_id: UUID | None = None,
) -> dict:
    return placement_service.college_analytics(db, admin, college_id)

