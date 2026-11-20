"""Add multi-tenant placement test domain.

Revision ID: 20261120_0005
Revises: 20261120_0004
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261120_0005"
down_revision = "20261120_0004"
branch_labels = None
depends_on = None

uuid_type = sa.Uuid(as_uuid=True)
json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "colleges",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_college_status"),
    )
    op.create_table(
        "batches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("branch", sa.String(100), nullable=False),
        sa.Column("section", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("college_id", "name", "branch", "section", name="uq_batch_cohort"),
        sa.CheckConstraint("graduation_year >= 2000", name="ck_batch_graduation_year"),
    )
    op.create_index("ix_batches_college_id", "batches", ["college_id"])
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT")),
        sa.Column("batch_id", uuid_type, sa.ForeignKey("batches.id", ondelete="RESTRICT")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('platform_admin', 'college_admin', 'student')", name="ck_user_role"),
        sa.CheckConstraint(
            "(role = 'platform_admin' AND college_id IS NULL) OR "
            "(role != 'platform_admin' AND college_id IS NOT NULL)",
            name="ck_user_tenant_role",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_college_id", "users", ["college_id"])
    op.create_index("ix_users_batch_id", "users", ["batch_id"])
    op.create_table(
        "topics",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("college_id", "slug", name="uq_topic_tenant_slug"),
        sa.CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_topic_scope",
        ),
    )
    op.create_index("ix_topics_slug", "topics", ["slug"])
    op.create_index("ix_topics_college_id", "topics", ["college_id"])
    op.create_table(
        "questions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT")),
        sa.Column("topic_id", uuid_type, sa.ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("question_type", sa.String(40), nullable=False),
        sa.Column("subtopic", sa.String(150), nullable=False, server_default=""),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("estimated_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("company_tags", json_type, nullable=False, server_default="[]"),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_placement_question_status"),
        sa.CheckConstraint(
            "question_type IN ('mcq_single', 'data_interpretation', 'pseudocode', 'logical_reasoning', 'verbal')",
            name="ck_placement_question_type",
        ),
        sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_placement_question_difficulty"),
        sa.CheckConstraint("estimated_seconds > 0", name="ck_placement_question_estimated_time"),
        sa.CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_placement_question_scope",
        ),
    )
    for column in ("college_id", "topic_id", "status"):
        op.create_index(f"ix_questions_{column}", "questions", [column])
    op.create_table(
        "tests",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT")),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("negative_marks", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passing_cutoff_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sections", json_type, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_placement_test_status"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_placement_test_duration"),
        sa.CheckConstraint(
            "(scope = 'global' AND college_id IS NULL) OR "
            "(scope = 'college' AND college_id IS NOT NULL)",
            name="ck_placement_test_scope",
        ),
    )
    op.create_index("ix_tests_college_id", "tests", ["college_id"])
    op.create_index("ix_tests_status", "tests", ["status"])
    op.create_table(
        "test_questions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("test_id", uuid_type, sa.ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_id", uuid_type, sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.String(150), nullable=False, server_default="General"),
        sa.UniqueConstraint("test_id", "position", name="uq_placement_test_question_position"),
        sa.UniqueConstraint("test_id", "question_id", name="uq_placement_test_question"),
        sa.CheckConstraint("position >= 0", name="ck_placement_test_question_position"),
    )
    op.create_index("ix_test_questions_test_id", "test_questions", ["test_id"])
    op.create_index("ix_test_questions_question_id", "test_questions", ["question_id"])
    op.create_table(
        "test_assignments",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("test_id", uuid_type, sa.ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("college_id", uuid_type, sa.ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_ids", json_type, nullable=False, server_default="[]"),
        sa.Column("branches", json_type, nullable=False, server_default="[]"),
        sa.Column("graduation_year", sa.Integer()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_attempts > 0", name="ck_test_assignment_max_attempts"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_test_assignment_window"),
    )
    op.create_index("ix_test_assignments_test_id", "test_assignments", ["test_id"])
    op.create_index("ix_test_assignments_college_id", "test_assignments", ["college_id"])
    op.create_index("ix_test_assignments_status", "test_assignments", ["status"])
    op.create_table(
        "test_attempts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("test_id", uuid_type, sa.ForeignKey("tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_id", uuid_type, sa.ForeignKey("test_assignments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("question_snapshot", json_type, nullable=False),
        sa.Column("result_snapshot", json_type),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="ck_placement_attempt_status",
        ),
        sa.CheckConstraint("deadline_at > started_at", name="ck_placement_attempt_deadline"),
    )
    for column in ("test_id", "assignment_id", "user_id", "status"):
        op.create_index(f"ix_test_attempts_{column}", "test_attempts", [column])
    op.create_table(
        "attempt_answers",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("attempt_id", uuid_type, sa.ForeignKey("test_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_id", uuid_type, sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_position", sa.Integer(), nullable=False),
        sa.Column("selected_option_id", sa.String(50)),
        sa.Column("marked_for_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_correct", sa.Boolean()),
        sa.Column("mistake_tag", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("attempt_id", "question_position", name="uq_attempt_answer_question"),
        sa.CheckConstraint("time_spent_seconds >= 0", name="ck_attempt_answer_time"),
    )
    op.create_index("ix_attempt_answers_attempt_id", "attempt_answers", ["attempt_id"])
    op.create_index("ix_attempt_answers_question_id", "attempt_answers", ["question_id"])


def downgrade() -> None:
    for table in (
        "attempt_answers",
        "test_attempts",
        "test_assignments",
        "test_questions",
        "tests",
        "questions",
        "topics",
        "users",
        "batches",
        "colleges",
    ):
        op.drop_table(table)
