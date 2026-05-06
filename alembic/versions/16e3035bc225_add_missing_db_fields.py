"""Add missing db fields

Revision ID: 16e3035bc225
Revises: d0e1f2a3b4c5
Create Date: 2026-05-02 22:26:55.461724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16e3035bc225'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('exercise_library') as batch_op:
        batch_op.add_column(sa.Column('weight_coefficients_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('exercise_library') as batch_op:
        batch_op.drop_column('weight_coefficients_json')
