from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    duration_seconds: int
    question_count: int
    sections: list[AssessmentSectionOut]


class AttemptCreateIn(StrictSchema):
    assessment_slug: str = Field(min_length=1, max_length=100)


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
    question_type: Literal["single_choice"]
    prompt: str
    stimulus: dict[str, Any] | None = None
    options: list[QuestionOptionOut]
    answer: dict[str, str] | None = None
    marked_for_review: bool
    visited: bool


class AttemptDetailOut(AttemptOut):
    questions: list[AttemptQuestionOut]


class ResponseIn(StrictSchema):
    answer: dict[str, str]
    time_spent_seconds: int = Field(default=0, ge=0, le=3600)


class ResponseOut(StrictSchema):
    question_id: UUID
    answer: dict[str, str]
    saved_at: datetime


class ReviewFlagIn(StrictSchema):
    marked: bool


class PositionUpdateIn(StrictSchema):
    question_id: UUID
    time_spent_seconds: int = Field(default=0, ge=0, le=3600)


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
    options: list[QuestionOptionOut]
    answer: dict[str, str] | None = None
    correct_answer: dict[str, str] | None = None
    explanation: str | None = None
    is_correct: bool | None = None


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
