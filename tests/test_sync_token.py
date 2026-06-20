"""sync_token is stored hashed and rotates on generation (P2.2)."""
import asyncio

from backend.auth import hash_sync_token, generate_sync_token
from backend.routers.users import get_shortcut_token
from backend.models.database import User


def test_hash_sync_token_deterministic_and_not_plaintext():
    t = generate_sync_token()
    assert hash_sync_token(t) == hash_sync_token(t)
    assert hash_sync_token(t) != t
    assert len(hash_sync_token(t)) == 64


def test_shortcut_token_stored_hashed_and_rotates(db):
    tg = {"id": 77, "first_name": "T", "last_name": "", "username": ""}

    r1 = asyncio.run(get_shortcut_token(tg, db))
    plaintext1 = r1["sync_token"]
    user = db.query(User).filter(User.telegram_id == 77).first()

    # DB holds the HASH, never the plaintext the client received.
    assert user.sync_token == hash_sync_token(plaintext1)
    assert user.sync_token != plaintext1
    assert len(user.sync_token) == 64

    # Re-generating rotates: new plaintext, old token's hash replaced.
    r2 = asyncio.run(get_shortcut_token(tg, db))
    db.refresh(user)
    assert r2["sync_token"] != plaintext1
    assert user.sync_token == hash_sync_token(r2["sync_token"])
    assert user.sync_token != hash_sync_token(plaintext1)
