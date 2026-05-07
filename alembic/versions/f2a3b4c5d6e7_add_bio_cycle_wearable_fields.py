"""add bio cycle wearable fields

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-07

Adds:
- users.sex, users.date_of_birth, users.sync_token
- daily_health_logs.vo2max
- cycle_logs table
Backfills users.sex from registration_data_json.gender
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("sex", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("date_of_birth", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("sync_token", sa.String(64), nullable=True))

    with op.batch_alter_table("daily_health_logs") as batch_op:
        batch_op.add_column(sa.Column("vo2max", sa.Float(), nullable=True))

    op.create_table(
        "cycle_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_period_start", sa.String(10), nullable=False),
        sa.Column("cycle_length", sa.Integer(), nullable=False, server_default="28"),
        sa.Column("logged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_cycle_logs_user", "cycle_logs", ["user_id"])

    # Backfill sex from registration_data_json
    conn = op.get_bind()
    try:
        import json
        rows = conn.execute(text(
            "SELECT id, registration_data_json FROM users WHERE registration_data_json IS NOT NULL"
        )).fetchall()
        for row in rows:
            raw = row[1]
            if isinstance(raw, str):
                data = json.loads(raw)
            elif isinstance(raw, dict):
                data = raw
            else:
                continue
            gender = data.get("gender")
            if gender:
                conn.execute(
                    text("UPDATE users SET sex = :sex WHERE id = :uid"),
                    {"sex": gender, "uid": row[0]},
                )
    except Exception:
        pass


def downgrade():
    op.drop_index("ix_cycle_logs_user", table_name="cycle_logs")
    op.drop_table("cycle_logs")

    with op.batch_alter_table("daily_health_logs") as batch_op:
        batch_op.drop_column("vo2max")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("sync_token")
        batch_op.drop_column("date_of_birth")
        batch_op.drop_column("sex")
