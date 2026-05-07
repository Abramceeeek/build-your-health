"""Add health tracking features: sleep score, readiness scores, volume load logs

Revision ID: e1f2a3b4c5d6
Revises: 16e3035bc225
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = '16e3035bc225'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New columns on daily_health_logs ───────────────────────────────────
    with op.batch_alter_table('daily_health_logs') as batch_op:
        batch_op.add_column(sa.Column('sleep_score',    sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column('sleep_deep_pct', sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column('sleep_rem_pct',  sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column('sleep_bedtime',  sa.String(5), nullable=True))
        batch_op.add_column(sa.Column('hrv',            sa.Float(),   nullable=True))

    # ── readiness_scores table ──────────────────────────────────────────────
    op.create_table(
        'readiness_scores',
        sa.Column('id',           sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('user_id',      sa.Integer(),    sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date',         sa.String(10),   nullable=False),
        sa.Column('score',        sa.Float(),      nullable=False),
        sa.Column('sleep_score',  sa.Float(),      nullable=True),
        sa.Column('rhr_score',    sa.Float(),      nullable=True),
        sa.Column('hrv_score',    sa.Float(),      nullable=True),
        sa.Column('mood_score',   sa.Float(),      nullable=True),
        sa.Column('breakdown_json', sa.JSON(),     nullable=True),
        sa.Column('computed_at',  sa.DateTime(),   nullable=True),
    )
    op.create_index('ix_readiness_user_date', 'readiness_scores', ['user_id', 'date'], unique=True)

    # ── volume_load_logs table ──────────────────────────────────────────────
    op.create_table(
        'volume_load_logs',
        sa.Column('id',            sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('user_id',       sa.Integer(),    sa.ForeignKey('users.id'), nullable=False),
        sa.Column('week_start',    sa.String(10),   nullable=False),
        sa.Column('muscle_group',  sa.String(20),   nullable=False),
        sa.Column('total_load',    sa.Float(),      nullable=True),
        sa.Column('session_count', sa.Integer(),    nullable=True),
        sa.Column('updated_at',    sa.DateTime(),   nullable=True),
    )
    op.create_index(
        'ix_volume_user_week_muscle', 'volume_load_logs',
        ['user_id', 'week_start', 'muscle_group'], unique=True,
    )
    op.create_index('ix_volume_load_logs_user_id', 'volume_load_logs', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_volume_load_logs_user_id', table_name='volume_load_logs')
    op.drop_index('ix_volume_user_week_muscle',  table_name='volume_load_logs')
    op.drop_table('volume_load_logs')

    op.drop_index('ix_readiness_user_date', table_name='readiness_scores')
    op.drop_table('readiness_scores')

    with op.batch_alter_table('daily_health_logs') as batch_op:
        batch_op.drop_column('hrv')
        batch_op.drop_column('sleep_bedtime')
        batch_op.drop_column('sleep_rem_pct')
        batch_op.drop_column('sleep_deep_pct')
        batch_op.drop_column('sleep_score')
