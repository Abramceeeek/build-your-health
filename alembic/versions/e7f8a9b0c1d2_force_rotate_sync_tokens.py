"""force_rotate_sync_tokens

Null out existing plaintext sync_token values so the column only ever holds SHA-256
hashes going forward (P2.2). Existing Apple Watch shortcuts must regenerate their token.

Revision ID: e7f8a9b0c1d2
Revises: 1abf6b17232e
Create Date: 2026-06-20 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = '1abf6b17232e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing values are plaintext tokens — invalidate them. New tokens are stored hashed.
    op.execute("UPDATE users SET sync_token = NULL")


def downgrade() -> None:
    # The original plaintext tokens cannot be recovered; nothing to do.
    pass
