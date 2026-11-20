from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas import StrictSchema

PlacementRole = Literal["platform_admin", "college_admin", "student"]
QuestionType = Literal["mcq_single", "data_interpretation", "pseudocode", "logical_reasoning", "verbal"]
Difficulty = Literal["easy", "medium", "hard"]


class LoginIn(StrictSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class TokenOut(StrictSchema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: "UserOut"


class UserOut(StrictSchema):
    id: UUID
    email: str
    display_name: str
    role: PlacementRole
    college_id: UUID | None
    batch_id: UUID | None


class UserCreateIn(StrictSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=200)
    role: Literal["college_admin", "student"]
    college_id: UUID
    batch_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class CollegeCreateIn(StrictSchema):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=200)


class CollegeOut(StrictSchema):
    id: UUID
    slug: str
    name: str
    status: Literal["active", "archived"]


class BatchCreateIn(StrictSchema):
    name: str = Field(min_length=1, max_length=100)
    graduation_year: int = Field(ge=2000, le=2200)
    branch: str = Field(min_length=1, max_length=100)
    section: str = Field(default="", max_length=50)
    college_id: UUID | None = None


class BatchOut(BatchCreateIn):
    id: UUID
    college_id: UUID


class QuestionOption(StrictSchema):
    id: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=2_000)

    @field_validator("id", "text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value


class PlacementQuestionPayload(StrictSchema):
    stem: str = Field(min_length=8, max_length=20_000)
    options: list[QuestionOption] = Field(min_length=4, max_length=4)
    correct_option_id: str = Field(min_length=1, max_length=50)
    shortcut_solution: str = Field(min_length=1, max_length=10_000)
    concept_solution: str = Field(min_length=1, max_length=20_000)
    estimated_seconds: int = Field(gt=0, le=3600)
    difficulty: Difficulty
    company_tags: list[str] = Field(default_factory=list, max_length=30)
    stimulus: dict[str, Any] | None = None
    latex: str | None = Field(default=None, max_length=10_000)
    code_language: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_option_set(self) -> "PlacementQuestionPayload":
        ids = [option.id for option in self.options]
        texts = [option.text.casefold() for option in self.options]
        if len(set(ids)) != 4 or len(set(texts)) != 4:
            raise ValueError("Options must have four distinct IDs and texts.")
        if self.correct_option_id not in ids:
            raise ValueError("correct_option_id must reference one of the options.")
        if not self.stem.strip() or not self.shortcut_solution.strip() or not self.concept_solution.strip():
            raise ValueError("Stem and both solution fields must not be blank.")
        return self


class QuestionWriteIn(StrictSchema):
    scope: Literal["global", "college"] = "college"
    college_id: UUID | None = None
    topic_slug: str = Field(min_length=1, max_length=100)
    subtopic: str = Field(default="", max_length=150)
    question_type: QuestionType
    payload: PlacementQuestionPayload
    source_type: Literal["manual", "parametric", "ai_generated", "imported"] = "manual"

    @field_validator("topic_slug")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        normalized = value.strip().casefold().replace(" ", "-")
        if not normalized:
            raise ValueError("topic_slug must not be blank.")
        return normalized


class QuestionOut(StrictSchema):
    id: UUID
    college_id: UUID | None
    scope: Literal["global", "college"]
    status: Literal["draft", "active", "archived"]
    topic_slug: str
    topic_name: str
    subtopic: str
    question_type: QuestionType
    payload: PlacementQuestionPayload
    difficulty: Difficulty
    estimated_seconds: int
    company_tags: list[str]
    source_type: str


class QuestionListOut(StrictSchema):
    items: list[QuestionOut]
    total: int
    page: int
    page_size: int


class QuestionBulkIn(StrictSchema):
    question_ids: list[UUID] = Field(min_length=1, max_length=500)
    action: Literal["activate", "archive", "set_topic", "set_difficulty"]
    topic_slug: str | None = None
    difficulty: Difficulty | None = None

    @model_validator(mode="after")
    def validate_action_value(self) -> "QuestionBulkIn":
        if self.action == "set_topic" and not self.topic_slug:
            raise ValueError("topic_slug is required for set_topic.")
        if self.action == "set_difficulty" and self.difficulty is None:
            raise ValueError("difficulty is required for set_difficulty.")
        return self


class QuestionBulkOut(StrictSchema):
    updated_count: int


class GenerateTestIn(StrictSchema):
    prompt: str = Field(min_length=10, max_length=10_000)
    target_difficulty: Difficulty
    question_count: int = Field(ge=1, le=100)
    duration_minutes: int = Field(ge=1, le=360)
    college_id: UUID | None = None
    topic_slugs: list[str] = Field(default_factory=list, max_length=30)
    company_tags: list[str] = Field(default_factory=list, max_length=30)


class GenerateTestOut(StrictSchema):
    test: "TestOut"
    questions: list[QuestionOut]


class ExtractQuestionsIn(StrictSchema):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=1_000_000)
    college_id: UUID | None = None


class ExtractionRowError(StrictSchema):
    row_number: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=2_000)


class ExtractQuestionsOut(StrictSchema):
    questions: list[QuestionOut]
    errors: list[ExtractionRowError] = Field(default_factory=list)


class ReviewActionItem(StrictSchema):
    question_id: UUID
    action: Literal["approve", "edit_and_approve", "regenerate", "discard"]
    replacement: QuestionWriteIn | None = None

    @model_validator(mode="after")
    def edit_requires_payload(self) -> "ReviewActionItem":
        if self.action == "edit_and_approve" and self.replacement is None:
            raise ValueError("replacement is required for edit_and_approve.")
        return self


class ReviewActionsIn(StrictSchema):
    actions: list[ReviewActionItem] = Field(min_length=1, max_length=100)


class TestQuestionIn(StrictSchema):
    question_id: UUID
    section_name: str = Field(default="General", min_length=1, max_length=150)


class TestCreateIn(StrictSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    scope: Literal["global", "college"] = "college"
    college_id: UUID | None = None
    duration_minutes: int = Field(ge=1, le=360)
    negative_marks: float = Field(default=0, ge=0, le=100)
    passing_cutoff_percent: float = Field(default=0, ge=0, le=100)
    question_ids: list[TestQuestionIn] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_question_ids(self) -> "TestCreateIn":
        ids = [item.question_id for item in self.question_ids]
        if len(set(ids)) != len(ids):
            raise ValueError("Question IDs must be unique.")
        return self


class TestUpdateIn(StrictSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    duration_minutes: int = Field(ge=1, le=360)
    negative_marks: float = Field(default=0, ge=0, le=100)
    passing_cutoff_percent: float = Field(default=0, ge=0, le=100)


class TestOut(StrictSchema):
    id: UUID
    college_id: UUID | None
    title: str
    description: str
    scope: Literal["global", "college"]
    duration_minutes: int
    negative_marks: float
    passing_cutoff_percent: float
    status: Literal["draft", "published", "archived"]
    question_count: int


class TestStatusIn(StrictSchema):
    status: Literal["published", "archived"]


class AssignmentCreateIn(StrictSchema):
    test_id: UUID
    college_id: UUID | None = None
    batch_ids: list[UUID] = Field(default_factory=list, max_length=500)
    branches: list[str] = Field(default_factory=list, max_length=100)
    graduation_year: int | None = Field(default=None, ge=2000, le=2200)
    starts_at: datetime
    ends_at: datetime | None = None
    max_attempts: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_window(self) -> "AssignmentCreateIn":
        start = self.starts_at if self.starts_at.tzinfo else self.starts_at.replace(tzinfo=timezone.utc)
        end = self.ends_at if self.ends_at is None or self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)
        if end is not None and end <= start:
            raise ValueError("ends_at must be later than starts_at.")
        return self


class AssignmentOut(StrictSchema):
    id: UUID
    test_id: UUID
    college_id: UUID
    batch_ids: list[str]
    branches: list[str]
    graduation_year: int | None
    starts_at: datetime
    ends_at: datetime | None
    max_attempts: int
    status: str
    test_title: str


class AssignmentUpdateIn(StrictSchema):
    batch_ids: list[UUID] = Field(default_factory=list, max_length=500)
    branches: list[str] = Field(default_factory=list, max_length=100)
    graduation_year: int | None = Field(default=None, ge=2000, le=2200)
    starts_at: datetime
    ends_at: datetime | None = None
    max_attempts: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_window(self) -> "AssignmentUpdateIn":
        start = self.starts_at if self.starts_at.tzinfo else self.starts_at.replace(tzinfo=timezone.utc)
        end = self.ends_at if self.ends_at is None or self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)
        if end is not None and end <= start:
            raise ValueError("ends_at must be later than starts_at.")
        return self


class QuestionReplaceIn(StrictSchema):
    test_id: UUID
    topic_slug: str | None = None
    subtopic: str | None = Field(default=None, max_length=150)


class TestQuestionOrderIn(StrictSchema):
    questions: list[TestQuestionIn] = Field(min_length=1, max_length=200)


class TestQuestionOrderOut(StrictSchema):
    questions: list[TestQuestionIn]


class AttemptStartIn(StrictSchema):
    assignment_id: UUID


class AttemptQuestionOut(StrictSchema):
    position: int
    section_name: str
    question_id: UUID
    topic_slug: str
    subtopic: str
    question_type: QuestionType
    stem: str
    stimulus: dict[str, Any] | None
    latex: str | None
    code_language: str | None
    options: list[QuestionOption]
    difficulty: Difficulty
    estimated_seconds: int
    selected_option_id: str | None = None
    marked_for_review: bool = False


class AttemptOut(StrictSchema):
    id: UUID
    test_id: UUID
    title: str
    status: Literal["in_progress", "submitted", "expired"]
    started_at: datetime
    deadline_at: datetime
    server_time: datetime
    questions: list[AttemptQuestionOut]


class AttemptAnswerIn(StrictSchema):
    question_position: int = Field(ge=0)
    selected_option_id: str | None = Field(default=None, max_length=50)
    marked_for_review: bool = False
    time_spent_seconds: int = Field(default=0, ge=0, le=3600)


class AttemptResultOut(StrictSchema):
    attempt_id: UUID
    test_id: UUID
    score: float
    score_percent: float = 0
    max_score: float
    accuracy_percent: float
    passed: bool
    correct: int
    incorrect: int
    unanswered: int
    topic_breakdown: list[dict[str, Any]]
    answers: list[dict[str, Any]]


class PracticeSimilarIn(StrictSchema):
    attempt_id: UUID
    topic_slugs: list[str] = Field(default_factory=list, max_length=10)
    question_count: int = Field(default=3, ge=1, le=10)


class PracticeQuestionOut(StrictSchema):
    topic_slug: str
    subtopic: str
    question_type: QuestionType
    stem: str
    options: list[QuestionOption]
    correct_option_id: str
    shortcut_solution: str
    concept_solution: str
    estimated_seconds: int
    difficulty: Difficulty
    stimulus: dict[str, Any] | None = None
    latex: str | None = None
    code_language: str | None = None


class StudentAnalyticsOut(StrictSchema):
    attempts_completed: int
    average_score_percent: float
    topic_breakdown: list[dict[str, Any]]


class CollegeAnalyticsOut(StrictSchema):
    college_id: UUID
    attempts_completed: int
    average_score_percent: float
    topic_breakdown: list[dict[str, Any]]
    cohort_breakdown: list[dict[str, Any]]


TokenOut.model_rebuild()
GenerateTestOut.model_rebuild()
