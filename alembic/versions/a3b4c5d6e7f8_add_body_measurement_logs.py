"""Add body_measurement_logs table

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: this table may already exist if an older app build created it via
    # Base.metadata.create_all() before this migration ran. Skip if present so the
    # `alembic upgrade head` step on deploy can't fail on "table already exists".
    if 'body_measurement_logs' in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'body_measurement_logs',
        sa.Column('id',         sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column('user_id',    sa.Integer(),   sa.ForeignKey('users.id'), nullable=False),
        sa.Column('key',        sa.String(80),  nullable=False),
        sa.Column('value',      sa.Float(),     nullable=False),
        sa.Column('date',       sa.String(10),  nullable=False),
        sa.Column('created_at', sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_body_measurement_logs_user_id', 'body_measurement_logs', ['user_id'])
    op.create_index('ix_bml_user_key',  'body_measurement_logs', ['user_id', 'key'])
    op.create_index('ix_bml_user_date', 'body_measurement_logs', ['user_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_bml_user_date', table_name='body_measurement_logs')
    op.drop_index('ix_bml_user_key',  table_name='body_measurement_logs')
    op.drop_index('ix_body_measurement_logs_user_id', table_name='body_measurement_logs')
    op.drop_table('body_measurement_logs')
