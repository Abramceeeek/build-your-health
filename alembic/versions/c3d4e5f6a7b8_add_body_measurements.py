"""add body measurements table

This is the production migration of record for body_measurement_logs (it predates and
supersedes the local a3b4c5d6e7f8 which created the same table — that one was removed and
the chain rebased onto this). Idempotent so it is safe whether or not create_all already
made the table.

Revision ID: c3d4e5f6a7b8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-08
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    if 'body_measurement_logs' in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'body_measurement_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(80), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('date', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bml_user_key', 'body_measurement_logs', ['user_id', 'key'])
    op.create_index('ix_bml_user_date', 'body_measurement_logs', ['user_id', 'date'])


def downgrade():
    op.drop_index('ix_bml_user_date', table_name='body_measurement_logs')
    op.drop_index('ix_bml_user_key', table_name='body_measurement_logs')
    op.drop_table('body_measurement_logs')
