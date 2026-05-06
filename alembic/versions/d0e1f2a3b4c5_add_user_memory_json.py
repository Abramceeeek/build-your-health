"""add memory_json to users

Revision ID: d0e1f2a3b4c5
Revises: c9d1e2f3a4b5
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("memory_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("users", "memory_json")
