"""add swap_count to daily_tasks

Revision ID: a1b2c3d4e5f6
Revises: 2c4345c72e77
Create Date: 2026-04-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2c4345c72e77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add swap_count column to daily_tasks."""
    with op.batch_alter_table('daily_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('swap_count', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    """Remove swap_count column from daily_tasks."""
    with op.batch_alter_table('daily_tasks', schema=None) as batch_op:
        batch_op.drop_column('swap_count')
