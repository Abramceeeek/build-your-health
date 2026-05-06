"""add feedback and subscriptions tables

Revision ID: f1a2b3c4d5e6
Revises: ccdfed0298e9
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '61f8d94d37aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('category', sa.String(20), default='other'),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('page', sa.String(40), default=''),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_feedback_user', 'feedback', ['user_id'])

    op.create_table(
        'subscriptions',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('tier', sa.String(20), default='free'),
        sa.Column('status', sa.String(20), default='trialing'),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('provider', sa.String(20), default=''),
        sa.Column('provider_sub_id', sa.String(100), default=''),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('feedback')
    op.drop_table('subscriptions')
