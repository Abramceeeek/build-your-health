"""App-level encryption for sensitive fields (ARCHITECTURE_REVIEW #3).

Fernet (AES-128-CBC + HMAC) keyed by settings.encryption_key. The EncryptedJSON column type
encrypts a JSON value on write and decrypts on read, transparently — existing code keeps using
`user.memory_json` / `user.registration_data_json` as plain dicts.

Lazy migration: a value that is not a valid Fernet token is treated as legacy plaintext JSON, so
rows written before encryption keep working and get encrypted the next time they are saved. No
big-bang data migration required.

Key rotation: this uses a single key. Rotating ENCRYPTION_KEY makes existing ciphertext
undecryptable — the read path raises (fail-loud, never silent data loss) rather than returning
empty. To rotate, decrypt-then-re-encrypt all rows under the new key (or switch to MultiFernet
with both keys during a transition). Do not change the key in place on a populated DB.
"""
import base64
import json
import logging

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Dev/test fallback key (clearly insecure). Production MUST set ENCRYPTION_KEY.
_DEV_KEY = base64.urlsafe_b64encode(b"buildhealth-dev-encryption-key!!".ljust(32, b"0")[:32])

_fernet_cache: dict[str, Fernet] = {}


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key
    if not key or not key.strip():  # reject empty AND whitespace-only keys
        if settings.environment.lower() == "production":
            raise RuntimeError("ENCRYPTION_KEY must be set in production")
        key = _DEV_KEY.decode()
    f = _fernet_cache.get(key)
    if f is None:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        _fernet_cache[key] = f
    return f


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


class EncryptedJSON(TypeDecorator):
    """Stores a JSON value encrypted at rest. Reads transparently decrypt; values that are not
    valid ciphertext are read as legacy plaintext JSON (lazy migration)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(json.dumps(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # Fernet tokens start with 'gAAAA'; legacy plaintext JSON starts with '{' or '[', so the
        # two are unambiguous. For real ciphertext we let an InvalidToken propagate rather than
        # silently returning None — a wrong/rotated key is a data-integrity problem, not "empty".
        if isinstance(value, str) and value.startswith("gAAAA"):
            try:
                return json.loads(decrypt(value))
            except Exception:
                logger.critical("EncryptedJSON decrypt failed — key mismatch or corruption; "
                                "NOT returning empty (failing loud to avoid silent data loss)")
                raise
        try:
            return json.loads(value)  # legacy row stored as plaintext JSON
        except (TypeError, json.JSONDecodeError):
            return None
