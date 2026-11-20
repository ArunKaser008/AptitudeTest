"""Create persistent assessment core.

Revision ID: 20261120_0001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261120_0001"
down_revision = None
branch_labels = None
depends_on = None

uuid_type = sa.Uuid(as_uuid=True)
json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "candidate_sessions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_candidate_session_revocation"),
    )
    op.create_index("ix_candidate_sessions_token_hash", "candidate_sessions", ["token_hash"], unique=True)
    op.create_index("ix_candidate_sessions_expires_at", "candidate_sessions", ["expires_at"])

    op.create_table(
        "assessments",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_assessment_status"),
        sa.UniqueConstraint("slug", name="uq_assessments_slug"),
    )
    op.create_index("ix_assessments_status", "assessments", ["status"])

    op.create_table(
        "assessment_config_versions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("assessment_id", uuid_type, sa.ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("show_explanations_after_submission", sa.Boolean(), nullable=False),
        sa.Column("randomize_questions", sa.Boolean(), nullable=False),
        sa.Column("randomize_options", sa.Boolean(), nullable=False),
        sa.Column("scoring_policy", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_assessment_config_status"),
        sa.CheckConstraint("duration_seconds > 0", name="ck_assessment_duration_positive"),
        sa.UniqueConstraint("assessment_id", "version_number", name="uq_assessment_config_version"),
    )
    op.create_index("ix_assessment_config_versions_assessment_id", "assessment_config_versions", ["assessment_id"])
    op.create_index("ix_assessment_config_versions_status", "assessment_config_versions", ["status"])

    op.create_table(
        "assessment_sections",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("config_version_id", uuid_type, sa.ForeignKey("assessment_config_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("marks_per_question", sa.Float(), nullable=False),
        sa.Column("negative_marks", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("question_count > 0", name="ck_section_question_count_positive"),
        sa.CheckConstraint("position >= 0", name="ck_section_position_nonnegative"),
        sa.UniqueConstraint("config_version_id", "section_key", name="uq_assessment_section_key"),
        sa.UniqueConstraint("config_version_id", "position", name="uq_assessment_section_position"),
    )
    op.create_index("ix_assessment_sections_config_version_id", "assessment_sections", ["config_version_id"])

    op.create_table(
        "question_versions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("logical_id", uuid_type, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("stimulus", json_type, nullable=True),
        sa.Column("topic", sa.String(length=150), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("options", json_type, nullable=False),
        sa.Column("correct_answer", json_type, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("negative_marks", sa.Float(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'review', 'published', 'archived')", name="ck_question_version_status"),
        sa.CheckConstraint("question_type IN ('single_choice')", name="ck_question_type_supported"),
        sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_question_difficulty"),
        sa.CheckConstraint("marks >= 0", name="ck_question_marks_nonnegative"),
        sa.CheckConstraint("negative_marks >= 0", name="ck_question_negative_marks_nonnegative"),
        sa.UniqueConstraint("logical_id", "version_number", name="uq_question_version_number"),
    )
    op.create_index("ix_question_versions_logical_id", "question_versions", ["logical_id"])
    op.create_index("ix_question_versions_status", "question_versions", ["status"])
    op.create_index("ix_question_versions_topic", "question_versions", ["topic"])
    op.create_index("ix_question_versions_difficulty", "question_versions", ["difficulty"])

    op.create_table(
        "assessment_question_pool",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("section_id", uuid_type, sa.ForeignKey("assessment_sections.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_version_id", uuid_type, sa.ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("section_id", "question_version_id", name="uq_section_question_pool"),
    )
    op.create_index("ix_assessment_question_pool_section_id", "assessment_question_pool", ["section_id"])
    op.create_index("ix_assessment_question_pool_question_version_id", "assessment_question_pool", ["question_version_id"])

    op.create_table(
        "assessment_attempts",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("candidate_session_id", uuid_type, sa.ForeignKey("candidate_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assessment_id", uuid_type, sa.ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("config_version_id", uuid_type, sa.ForeignKey("assessment_config_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_position", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("result_snapshot", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('in_progress', 'submitted', 'expired')", name="ck_assessment_attempt_status"),
        sa.CheckConstraint("deadline_at > started_at", name="ck_attempt_deadline_after_start"),
        sa.CheckConstraint("current_position >= 0", name="ck_attempt_current_position_nonnegative"),
        sa.UniqueConstraint("candidate_session_id", "idempotency_key", name="uq_attempt_idempotency"),
    )
    op.create_index("ix_assessment_attempts_candidate_session_id", "assessment_attempts", ["candidate_session_id"])
    op.create_index("ix_assessment_attempts_assessment_id", "assessment_attempts", ["assessment_id"])
    op.create_index("ix_assessment_attempts_config_version_id", "assessment_attempts", ["config_version_id"])
    op.create_index("ix_assessment_attempts_status", "assessment_attempts", ["status"])
    op.create_index("ix_assessment_attempts_deadline_at", "assessment_attempts", ["deadline_at"])

    op.create_table(
        "attempt_questions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("attempt_id", uuid_type, sa.ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("section_id", uuid_type, sa.ForeignKey("assessment_sections.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_version_id", uuid_type, sa.ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("option_order", json_type, nullable=False),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("negative_marks", sa.Float(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("marked_for_review", sa.Boolean(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_attempt_question_position_nonnegative"),
        sa.CheckConstraint("time_spent_seconds >= 0", name="ck_question_time_nonnegative"),
        sa.UniqueConstraint("attempt_id", "position", name="uq_attempt_question_position"),
        sa.UniqueConstraint("attempt_id", "question_version_id", name="uq_attempt_question_unique"),
    )
    op.create_index("ix_attempt_questions_attempt_id", "attempt_questions", ["attempt_id"])

    op.create_table(
        "attempt_responses",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("attempt_question_id", uuid_type, sa.ForeignKey("attempt_questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("attempt_question_id", name="uq_attempt_response_question"),
    )
    op.create_index("ix_attempt_responses_attempt_question_id", "attempt_responses", ["attempt_question_id"])


def downgrade() -> None:
    op.drop_table("attempt_responses")
    op.drop_table("attempt_questions")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_question_pool")
    op.drop_table("question_versions")
    op.drop_table("assessment_sections")
    op.drop_table("assessment_config_versions")
    op.drop_table("assessments")
    op.drop_table("candidate_sessions")
