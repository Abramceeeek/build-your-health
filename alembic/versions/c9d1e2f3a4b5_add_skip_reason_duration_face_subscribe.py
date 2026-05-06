"""add skip_reason, duration_min, face_transform_subscribed

Revision ID: c9d1e2f3a4b5
Revises: b7e9c1d4a8f2
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'c9d1e2f3a4b5'
down_revision = 'b7e9c1d4a8f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('daily_tasks') as batch_op:
        batch_op.add_column(sa.Column('skipped_reason', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('duration_min', sa.Integer(), nullable=True))

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('face_transform_subscribed', sa.Boolean(), nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('face_transform_subscribed')

    with op.batch_alter_table('daily_tasks') as batch_op:
        batch_op.drop_column('duration_min')
        batch_op.drop_column('skipped_reason')
