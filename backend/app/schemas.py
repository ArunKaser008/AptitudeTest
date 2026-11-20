from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PassageStimulus(StrictSchema):
    kind: Literal["passage"]
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class TableStimulus(StrictSchema):
    kind: Literal["table"]
    title: str | None = Field(default=None, max_length=200)
    headers: list[str] = Field(min_length=1, max_length=50)
    rows: list[list[Any]] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_row_widths(self) -> "TableStimulus":
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Every table row must have the same number of cells as headers.")
        return self


class CodeStimulus(StrictSchema):
    kind: Literal["code"]
    title: str | None = Field(default=None, max_length=200)
    language: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=20_000)


Stimulus = Annotated[
    PassageStimulus | TableStimulus | CodeStimulus,
    Field(discriminator="kind"),
]


class CandidateSessionOut(StrictSchema):
    session_token: str
    expires_at: datetime


class AssessmentSectionOut(StrictSchema):
    title: str
    question_count: int


class AssessmentOut(StrictSchema):
    slug: str
    title: str
    description: str
    category: Literal["aptitude", "company_mock", "practice"] = "aptitude"
    target_role: str | None = None
    ai_generation_enabled: bool = True
    duration_seconds: int
    question_count: int
    sections: list[AssessmentSectionOut]
    difficulties: list[Literal["easy", "medium", "hard"]] = Field(default_factory=list)


class AttemptCreateIn(StrictSchema):
    assessment_slug: str = Field(min_length=1, max_length=100)


class WeakTopicPracticeIn(StrictSchema):
    source_attempt_id: UUID


class PracticeSimilarIn(StrictSchema):
    source_attempt_id: UUID | None = None
    question_id: UUID | None = None
    topics: list[str] = Field(default_factory=list, max_length=20)
    question_count: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_target(self) -> "PracticeSimilarIn":
        if self.question_id is not None and self.source_attempt_id is None:
            raise ValueError("A source_attempt_id is required when question_id is provided.")
        self.topics = [topic.strip() for topic in self.topics]
        if any(not topic for topic in self.topics) or len(set(self.topics)) != len(self.topics):
            raise ValueError("Topics must be non-blank and unique.")
        return self


class PracticeTopicOut(StrictSchema):
    topic: str
    easy_count: int = Field(ge=0)
    medium_count: int = Field(ge=0)
    hard_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class AttemptOut(StrictSchema):
    id: UUID
    assessment_slug: str
    title: str
    status: Literal["in_progress", "submitted", "expired"]
    started_at: datetime
    deadline_at: datetime
    server_time: datetime
    question_count: int
    current_position: int


class QuestionOptionOut(StrictSchema):
    id: str
    text: str


class AttemptQuestionOut(StrictSchema):
    id: UUID
    position: int
    section: str
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    question_type: Literal["single_choice", "multi_choice", "numeric"]
    prompt: str
    stimulus: Stimulus | None = None
    options: list[QuestionOptionOut] = Field(default_factory=list)
    answer: dict[str, Any] | None = None
    marked_for_review: bool
    visited: bool


class AttemptDetailOut(AttemptOut):
    questions: list[AttemptQuestionOut]


class ResponseIn(StrictSchema):
    answer: dict[str, Any]
    time_spent_seconds: int = Field(default=0, ge=0, le=3600)


class ResponseOut(StrictSchema):
    question_id: UUID
    answer: dict[str, Any]
    saved_at: datetime


class ReviewFlagIn(StrictSchema):
    marked: bool


class PositionUpdateIn(StrictSchema):
    question_id: UUID
    time_spent_seconds: int = Field(default=0, ge=0, le=3600)


class AttemptSubmitIn(StrictSchema):
    question_id: UUID | None = None
    time_spent_seconds: int = Field(default=0, ge=0, le=86_400)

    @model_validator(mode="after")
    def validate_active_question_time(self) -> "AttemptSubmitIn":
        if self.question_id is None and self.time_spent_seconds:
            raise ValueError("A question_id is required when reporting time spent.")
        return self


class SectionResultOut(StrictSchema):
    section: str
    score: float
    max_score: float
    correct: int
    incorrect: int
    unanswered: int
    accuracy_percent: float


class QuestionReviewOut(StrictSchema):
    question_id: UUID
    position: int
    section: str
    topic: str
    prompt: str
    stimulus: Stimulus | None = None
    options: list[QuestionOptionOut]
    answer: dict[str, Any] | None = None
    correct_answer: dict[str, Any] | None = None
    explanation: str | None = None
    is_correct: bool | None = None
    time_spent_seconds: int = Field(default=0, ge=0)


class TopicResultOut(StrictSchema):
    topic: str
    correct: int
    incorrect: int
    unanswered: int
    accuracy_percent: float
    avg_time_seconds: float


class AttemptResultOut(StrictSchema):
    attempt_id: UUID
    assessment_slug: str
    assessment_title: str
    status: Literal["submitted", "expired"]
    score: float
    max_score: float
    correct: int
    incorrect: int
    unanswered: int
    accuracy_percent: float
    attempt_rate_percent: float
    elapsed_seconds: int
    sections: list[SectionResultOut]
    review: list[QuestionReviewOut]
    topics: list[TopicResultOut] = Field(default_factory=list)


class PerformanceTopicOut(StrictSchema):
    topic: str
    total_questions: int = Field(ge=0)
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    unanswered: int = Field(ge=0)
    accuracy_percent: float = Field(ge=0, le=100)
    avg_time_seconds: float = Field(ge=0)


class PerformanceTrendOut(StrictSchema):
    attempt_id: UUID
    assessment_slug: str
    assessment_title: str
    category: Literal["aptitude", "company_mock", "practice"]
    submitted_at: datetime
    score_percent: float = Field(ge=0, le=100)
    accuracy_percent: float = Field(ge=0, le=100)


class CandidatePerformanceOut(StrictSchema):
    completed_attempts: int = Field(ge=0)
    readiness_score: float = Field(ge=0, le=100)
    average_accuracy_percent: float = Field(ge=0, le=100)
    average_time_seconds: float = Field(ge=0)
    practice_time_seconds: int = Field(ge=0)
    trend: list[PerformanceTrendOut] = Field(default_factory=list)
    topics: list[PerformanceTopicOut] = Field(default_factory=list)


class RecommendationOut(StrictSchema):
    id: str
    kind: Literal["weak_topic", "time_management", "progression", "baseline"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1_000)
    topic: str | None = None
    assessment_slug: str | None = None
    action_label: str = Field(min_length=1, max_length=80)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1_440)


class RecommendationListOut(StrictSchema):
    count: int = Field(ge=0)
    items: list[RecommendationOut] = Field(default_factory=list)


class QuestionOptionIn(StrictSchema):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2_000)


class QuestionDraftIn(StrictSchema):
    question_type: Literal["single_choice", "multi_choice", "numeric"] = "single_choice"
    prompt: str = Field(min_length=1, max_length=20_000)
    stimulus: Stimulus | None = None
    topic: str = Field(min_length=1, max_length=150)
    difficulty: Literal["easy", "medium", "hard"]
    options: list[QuestionOptionIn] = Field(default_factory=list, max_length=100)
    correct_answer: dict[str, Any]
    explanation: str = Field(min_length=1, max_length=20_000)
    marks: float = Field(default=1, ge=0)
    negative_marks: float = Field(default=0, ge=0)
    source_reference: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_answer_shape(self) -> "QuestionDraftIn":
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("Option IDs must be unique.")
        if self.question_type == "single_choice":
            if len(option_ids) < 2 or set(self.correct_answer) != {"option_id"}:
                raise ValueError("Single-choice questions require at least two options and one option_id answer.")
            if self.correct_answer["option_id"] not in option_ids:
                raise ValueError("The correct option_id must match one of the provided options.")
        elif self.question_type == "multi_choice":
            correct_ids = self.correct_answer.get("option_ids")
            if (
                len(option_ids) < 2
                or set(self.correct_answer) != {"option_ids"}
                or not isinstance(correct_ids, list)
                or not correct_ids
                or any(not isinstance(option_id, str) for option_id in correct_ids)
                or len(set(correct_ids)) != len(correct_ids)
                or not set(correct_ids).issubset(option_ids)
            ):
                raise ValueError("Multiple-choice questions require valid, unique option_ids.")
        else:
            value = self.correct_answer.get("value")
            tolerance = self.correct_answer.get("tolerance", 0)
            if (
                self.options
                or set(self.correct_answer) - {"value", "tolerance"}
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or isinstance(tolerance, bool)
                or not isinstance(tolerance, (int, float))
                or not math.isfinite(tolerance)
                or tolerance < 0
            ):
                raise ValueError("Numeric questions require a numeric value, optional non-negative tolerance, and no options.")
        return self


class QuestionOut(QuestionDraftIn):
    id: UUID
    logical_id: UUID
    version_number: int
    status: Literal["draft", "review", "published", "archived"]
    verified_at: datetime | None
    usage_count: int = 0


class QuestionListOut(StrictSchema):
    items: list[QuestionOut]
    total: int
    page: int
    page_size: int


class ImportRowError(StrictSchema):
    row_index: int
    field: str
    message: str


class BulkImportOut(StrictSchema):
    dry_run: bool
    imported_count: int
    valid_count: int
    errors: list[ImportRowError]


class AuthoringSectionIn(StrictSchema):
    section_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0)
    question_count: int = Field(gt=0)
    marks_per_question: float = Field(ge=0)
    negative_marks: float = Field(ge=0)
    question_version_ids: list[UUID] = Field(default_factory=list)


class AssessmentCreateIn(StrictSchema):
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    category: Literal["aptitude", "company_mock", "practice"] = "aptitude"
    target_role: str | None = Field(default=None, max_length=150)
    ai_generation_enabled: bool = True
    blueprint_topics: list[str] = Field(default_factory=list, max_length=100)
    duration_seconds: int = Field(gt=0, le=86_400)
    show_explanations_after_submission: bool = True
    randomize_questions: bool = True
    randomize_options: bool = True
    scoring_policy: dict[str, Any] = Field(default_factory=dict)
    sections: list[AuthoringSectionIn] = Field(min_length=1, max_length=50)


class AssessmentCloneIn(StrictSchema):
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)


class AssessmentConfigUpdateIn(StrictSchema):
    duration_seconds: int = Field(gt=0, le=86_400)
    show_explanations_after_submission: bool
    randomize_questions: bool
    randomize_options: bool
    scoring_policy: dict[str, Any]
    sections: list[AuthoringSectionIn] = Field(min_length=1, max_length=50)


class SectionPoolUpdateIn(StrictSchema):
    question_version_ids: list[UUID]


class SectionReadinessOut(StrictSchema):
    id: UUID
    section_key: str
    title: str
    position: int
    question_count: int
    marks_per_question: float
    negative_marks: float
    eligible_verified_count: int
    ready: bool
    question_version_ids: list[UUID] = Field(default_factory=list)


class AuthoringAssessmentOut(StrictSchema):
    id: UUID
    slug: str
    title: str
    description: str
    status: Literal["draft", "published", "archived"]
    category: Literal["aptitude", "company_mock", "practice"] = "aptitude"
    target_role: str | None = None
    config_version_id: UUID | None
    config_version_number: int | None
    config_status: Literal["draft", "published", "archived"] | None
    duration_seconds: int | None
    show_explanations_after_submission: bool = True
    randomize_questions: bool = True
    randomize_options: bool = True
    scoring_policy: dict[str, Any] = Field(default_factory=dict)
    eligible_verified_count: int
    required_question_count: int
    ready: bool
    sections: list[SectionReadinessOut]
