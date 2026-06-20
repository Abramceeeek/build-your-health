"""encrypt sensitive json fields

Changes users.registration_data_json and users.memory_json from JSON to the app-level
EncryptedJSON type (stored as Text ciphertext). Existing plaintext rows keep working — the
EncryptedJSON read path treats non-ciphertext as legacy plaintext JSON and they re-encrypt on
next write (lazy migration), so no data backfill is needed here.

Revision ID: cc16fbf2c19c
Revises: d5069da04250
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.services.crypto_service import EncryptedJSON

revision: str = 'cc16fbf2c19c'
down_revision: Union[str, Sequence[str], None] = 'd5069da04250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('registration_data_json',
                              existing_type=sa.JSON(), type_=EncryptedJSON(),
                              existing_nullable=True,
                              postgresql_using='registration_data_json::text')
        batch_op.alter_column('memory_json',
                              existing_type=sa.JSON(), type_=EncryptedJSON(),
                              existing_nullable=True,
                              postgresql_using='memory_json::text')


def downgrade() -> None:
    # Refuse to downgrade if encrypted data exists: a Fernet token ('gAAAA...') is not valid JSON,
    # so the ::json cast below would fail or lose data. Decrypting inside a migration is fragile
    # (batch-recreate semantics) so we fail loud instead — re-encrypt to plaintext with a script,
    # or restore a pre-encryption backup, then downgrade. (CI downgrades an empty DB, so this is a
    # no-op there.) Production is forward-only.
    bind = op.get_bind()
    for col in ('registration_data_json', 'memory_json'):
        n = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM users WHERE {col} LIKE 'gAAAA%'")
        ).scalar()
        if n:
            raise RuntimeError(
                f"Cannot downgrade: {n} encrypted {col} row(s) exist. Decrypt them to plaintext "
                "JSON first (re-encrypt script) or restore a pre-encryption backup."
            )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('memory_json',
                              existing_type=EncryptedJSON(), type_=sa.JSON(),
                              existing_nullable=True,
                              postgresql_using='memory_json::json')
        batch_op.alter_column('registration_data_json',
                              existing_type=EncryptedJSON(), type_=sa.JSON(),
                              existing_nullable=True,
                              postgresql_using='registration_data_json::json')
