"""Persist effective duration and title for focused practice attempts.

Revision ID: 20261120_0003
Revises: 20261120_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20261120_0003"
down_revision = "20261120_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment_attempts", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.add_column("assessment_attempts", sa.Column("title_override", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("assessment_attempts", "title_override")
    op.drop_column("assessment_attempts", "duration_seconds")
