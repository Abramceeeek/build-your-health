"""add coach_messages table

Revision ID: b7e9c1d4a8f2
Revises: f1a2b3c4d5e6
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e9c1d4a8f2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("flagged_injury", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("coach_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_coach_messages_user_id"), ["user_id"], unique=False,
        )
        batch_op.create_index(
            "ix_coach_messages_user_created", ["user_id", "created_at"], unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("coach_messages", schema=None) as batch_op:
        batch_op.drop_index("ix_coach_messages_user_created")
        batch_op.drop_index(batch_op.f("ix_coach_messages_user_id"))
    op.drop_table("coach_messages")
