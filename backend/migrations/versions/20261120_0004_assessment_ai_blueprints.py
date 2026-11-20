"""Add assessment metadata and AI generation blueprints.

Revision ID: 20261120_0004
Revises: 20261120_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "20261120_0004"
down_revision = "20261120_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assessments") as batch:
        batch.add_column(sa.Column("category", sa.String(length=40), server_default="aptitude", nullable=False))
        batch.add_column(sa.Column("target_role", sa.String(length=150), nullable=True))
        batch.add_column(
            sa.Column("ai_generation_enabled", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(sa.Column("blueprint_topics", sa.JSON(), server_default="[]", nullable=False))
        batch.create_index("ix_assessments_category", ["category"])
        batch.create_check_constraint(
            "ck_assessment_category",
            "category IN ('aptitude', 'company_mock', 'practice')",
        )


def downgrade() -> None:
    with op.batch_alter_table("assessments") as batch:
        batch.drop_constraint("ck_assessment_category", type_="check")
        batch.drop_index("ix_assessments_category")
        batch.drop_column("blueprint_topics")
        batch.drop_column("ai_generation_enabled")
        batch.drop_column("target_role")
        batch.drop_column("category")
