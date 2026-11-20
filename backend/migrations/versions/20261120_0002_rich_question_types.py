"""Support multi-choice and numeric questions.

Revision ID: 20261120_0002
Revises: 20261120_0001
"""

from alembic import op

revision = "20261120_0002"
down_revision = "20261120_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("question_versions") as batch_op:
        batch_op.drop_constraint("ck_question_type_supported", type_="check")
        batch_op.create_check_constraint(
            "ck_question_type_supported",
            "question_type IN ('single_choice', 'multi_choice', 'numeric')",
        )


def downgrade() -> None:
    with op.batch_alter_table("question_versions") as batch_op:
        batch_op.drop_constraint("ck_question_type_supported", type_="check")
        batch_op.create_check_constraint(
            "ck_question_type_supported",
            "question_type IN ('single_choice')",
        )
