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
        CheckConstraint(
            "category IN ('aptitude', 'company_mock', 'practice')",
            name="ck_assessment_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="aptitude", index=True)
    target_role: Mapped[str | None] = mapped_column(String(150))
    ai_generation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    blueprint_topics: Mapped[list[str]] = mapped_column(json_document, nullable=False, default=list)


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


class College(TimestampMixin, Base):
    __tablename__ = "colleges"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_college_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("college_id", "name", "branch", "section", name="uq_batch_cohort"),
        CheckConstraint("graduation_year >= 2000", name="ck_batch_graduation_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    college_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False, default="")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('platform_admin', 'college_admin', 'student')",
            name="ck_user_role",
        ),
        CheckConstraint(
            "(role = 'platform_admin' AND college_id IS NULL) OR "
            "(role != 'platform_admin' AND college_id IS NOT NULL)",
            name="ck_user_tenant_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("college_id", "slug", name="uq_topic_tenant_slug"),
        CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_topic_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), index=True
    )


class PlacementQuestion(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_placement_question_status"),
        CheckConstraint(
            "question_type IN ('mcq_single', 'data_interpretation', 'pseudocode', 'logical_reasoning', 'verbal')",
            name="ck_placement_question_type",
        ),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_placement_question_difficulty"),
        CheckConstraint("estimated_seconds > 0", name="ck_placement_question_estimated_time"),
        CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_placement_question_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subtopic: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(json_document, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    company_tags: Mapped[list[str]] = mapped_column(json_document, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")


class PlacementTest(TimestampMixin, Base):
    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_placement_test_status"),
        CheckConstraint("duration_minutes > 0", name="ck_placement_test_duration"),
        CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_placement_test_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_marks: Mapped[float] = mapped_column(nullable=False, default=0)
    passing_cutoff_percent: Mapped[float] = mapped_column(nullable=False, default=0)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(json_document, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)


class PlacementTestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (
        UniqueConstraint("test_id", "position", name="uq_placement_test_question_position"),
        UniqueConstraint("test_id", "question_id", name="uq_placement_test_question"),
        CheckConstraint("position >= 0", name="ck_placement_test_question_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str] = mapped_column(String(150), nullable=False, default="General")


class TestAssignment(TimestampMixin, Base):
    __tablename__ = "test_assignments"
    __table_args__ = (
        CheckConstraint("max_attempts > 0", name="ck_test_assignment_max_attempts"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_test_assignment_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    college_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_ids: Mapped[list[str]] = mapped_column(json_document, nullable=False, default=list)
    branches: Mapped[list[str]] = mapped_column(json_document, nullable=False, default=list)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)


class PlacementTestAttempt(TimestampMixin, Base):
    __tablename__ = "test_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="ck_placement_attempt_status",
        ),
        CheckConstraint("deadline_at > started_at", name="ck_placement_attempt_deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_assignments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", index=True)
    question_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(json_document, nullable=False)
    result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_document)


class PlacementAttemptAnswer(TimestampMixin, Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_position", name="uq_attempt_answer_question"),
        CheckConstraint("time_spent_seconds >= 0", name="ck_attempt_answer_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_position: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_option_id: Mapped[str | None] = mapped_column(String(50))
    marked_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    mistake_tag: Mapped[str | None] = mapped_column(String(30))
