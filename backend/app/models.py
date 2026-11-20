from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


json_document = JSON().with_variant(JSONB(), "postgresql")


class CandidateSession(TimestampMixin, Base):
    __tablename__ = "candidate_sessions"
    __table_args__ = (
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_candidate_session_revocation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_assessment_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)


class AssessmentConfigVersion(TimestampMixin, Base):
    __tablename__ = "assessment_config_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_config_version"),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_assessment_config_status",
        ),
        CheckConstraint("duration_seconds > 0", name="ck_assessment_duration_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    show_explanations_after_submission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    randomize_questions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    randomize_options: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scoring_policy: Mapped[dict[str, Any]] = mapped_column(json_document, nullable=False, default=dict)


class AssessmentSection(TimestampMixin, Base):
    __tablename__ = "assessment_sections"
    __table_args__ = (
        UniqueConstraint("config_version_id", "section_key", name="uq_assessment_section_key"),
        UniqueConstraint("config_version_id", "position", name="uq_assessment_section_position"),
        CheckConstraint("question_count > 0", name="ck_section_question_count_positive"),
        CheckConstraint("position >= 0", name="ck_section_position_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_config_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    marks_per_question: Mapped[float] = mapped_column(nullable=False, default=1)
    negative_marks: Mapped[float] = mapped_column(nullable=False, default=0)


class QuestionVersion(TimestampMixin, Base):
    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint("logical_id", "version_number", name="uq_question_version_number"),
        CheckConstraint(
            "status IN ('draft', 'review', 'published', 'archived')",
            name="ck_question_version_status",
        ),
        CheckConstraint(
            "question_type IN ('single_choice', 'multi_choice', 'numeric')",
            name="ck_question_type_supported",
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_question_difficulty",
        ),
        CheckConstraint("marks >= 0", name="ck_question_marks_nonnegative"),
        CheckConstraint("negative_marks >= 0", name="ck_question_negative_marks_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logical_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False, default="single_choice")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    stimulus: Mapped[dict[str, Any] | None] = mapped_column(json_document)
    topic: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    options: Mapped[list[dict[str, str]]] = mapped_column(json_document, nullable=False)
    correct_answer: Mapped[dict[str, Any]] = mapped_column(json_document, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[float] = mapped_column(nullable=False, default=1)
    negative_marks: Mapped[float] = mapped_column(nullable=False, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_reference: Mapped[str | None] = mapped_column(Text)


class AssessmentQuestionPool(TimestampMixin, Base):
    __tablename__ = "assessment_question_pool"
    __table_args__ = (
        UniqueConstraint("section_id", "question_version_id", name="uq_section_question_pool"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessment_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class AssessmentAttempt(TimestampMixin, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("candidate_session_id", "idempotency_key", name="uq_attempt_idempotency"),
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="ck_assessment_attempt_status",
        ),
        CheckConstraint("deadline_at > started_at", name="ck_attempt_deadline_after_start"),
        CheckConstraint("current_position >= 0", name="ck_attempt_current_position_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidate_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    config_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_config_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    title_override: Mapped[str | None] = mapped_column(String(200))
    current_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column()
    result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_document)


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "position", name="uq_attempt_question_position"),
        UniqueConstraint("attempt_id", "question_version_id", name="uq_attempt_question_unique"),
        CheckConstraint("position >= 0", name="ck_attempt_question_position_nonnegative"),
        CheckConstraint("time_spent_seconds >= 0", name="ck_question_time_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessment_sections.id", ondelete="RESTRICT"), nullable=False
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    option_order: Mapped[list[str]] = mapped_column(json_document, nullable=False)
    marks: Mapped[float] = mapped_column(nullable=False)
    negative_marks: Mapped[float] = mapped_column(nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttemptResponse(TimestampMixin, Base):
    __tablename__ = "attempt_responses"
    __table_args__ = (
        UniqueConstraint("attempt_question_id", name="uq_attempt_response_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attempt_questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    answer: Mapped[dict[str, Any]] = mapped_column(json_document, nullable=False)
