"""App-level field encryption: roundtrip, ciphertext-at-rest, transparent ORM, legacy fallback."""
import json
import os

import pytest
from sqlalchemy import text

from backend.config import get_settings
from backend.models.database import User
from backend.services import crypto_service
from backend.services.crypto_service import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    assert decrypt(encrypt("hello health")) == "hello health"


def test_ciphertext_is_not_plaintext():
    token = encrypt('{"injuries": "left knee"}')
    assert "injuries" not in token
    assert token.startswith("gAAAA")  # Fernet token prefix


def test_orm_read_write_is_transparent(db):
    u = User(telegram_id=1, first_name="T",
             registration_data_json={"goals": ["build_muscle"], "injuries": "none"})
    db.add(u)
    db.commit()
    db.expire(u)
    assert u.registration_data_json == {"goals": ["build_muscle"], "injuries": "none"}


def test_value_stored_encrypted_at_rest(db):
    u = User(telegram_id=2, first_name="T", memory_json={"note": "secret context"})
    db.add(u)
    db.commit()
    raw = db.execute(text("SELECT memory_json FROM users WHERE id = :i"), {"i": u.id}).scalar()
    assert "secret context" not in raw  # not stored in the clear
    assert raw.startswith("gAAAA")
    assert decrypt(raw) == json.dumps({"note": "secret context"})


def test_legacy_plaintext_is_read_transparently(db):
    """A row written before encryption (plaintext JSON) must still read back as a dict."""
    u = User(telegram_id=3, first_name="T")
    db.add(u)
    db.commit()
    db.execute(text("UPDATE users SET registration_data_json = :v WHERE id = :i"),
               {"v": '{"goals": ["legacy"]}', "i": u.id})
    db.commit()
    db.expire(u)
    assert u.registration_data_json == {"goals": ["legacy"]}


def test_none_stays_none(db):
    u = User(telegram_id=4, first_name="T", memory_json=None)
    db.add(u)
    db.commit()
    db.expire(u)
    assert u.memory_json is None


def test_decrypt_failure_raises_not_none():
    """A 'gAAAA' token that won't decrypt must raise (fail loud), never silently become None."""
    from backend.services.crypto_service import EncryptedJSON
    with pytest.raises(Exception):
        EncryptedJSON().process_result_value("gAAAAAcorrupted-not-a-real-token", None)


def test_whitespace_only_key_rejected_in_production():
    old_env, old_key = os.environ.get("ENVIRONMENT"), os.environ.get("ENCRYPTION_KEY")
    try:
        os.environ["ENVIRONMENT"] = "Production"  # also checks case-insensitive guard
        os.environ["ENCRYPTION_KEY"] = "   "
        get_settings.cache_clear()
        crypto_service._fernet_cache.clear()
        with pytest.raises(RuntimeError):
            encrypt("x")
    finally:
        for k, v in (("ENVIRONMENT", old_env), ("ENCRYPTION_KEY", old_key)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()
        crypto_service._fernet_cache.clear()


def test_production_requires_key():
    settings = get_settings()
    old_env, old_key = os.environ.get("ENVIRONMENT"), os.environ.get("ENCRYPTION_KEY")
    try:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["ENCRYPTION_KEY"] = ""
        get_settings.cache_clear()
        crypto_service._fernet_cache.clear()
        with pytest.raises(RuntimeError):
            encrypt("x")
    finally:
        if old_env is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = old_env
        if old_key is None:
            os.environ.pop("ENCRYPTION_KEY", None)
        else:
            os.environ["ENCRYPTION_KEY"] = old_key
        get_settings.cache_clear()
        crypto_service._fernet_cache.clear()
