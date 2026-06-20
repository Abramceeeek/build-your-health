"""add referred_by to users (referral loop)

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('referred_by', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('referred_by')
