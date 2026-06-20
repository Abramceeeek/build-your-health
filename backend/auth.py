import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, parse_qs

import jwt
from fastapi import Request, HTTPException, Depends
from backend.config import get_settings


# Reject initData older than this. Telegram recommends a small window to
# prevent captured-token replay; 24h is generous enough for normal use.
INIT_DATA_MAX_AGE_S = 24 * 60 * 60

# Account (email/password) JWT settings.
JWT_ALG = "HS256"
ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=30)
_DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me"  # only used when env != production


def _jwt_secret() -> str:
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="Server misconfigured: jwt_secret not set")
    return _DEV_JWT_SECRET


# --- Password hashing (scrypt, stdlib — no native build needed) ---------------

def hash_password(password: str) -> str:
    """scrypt hash as 'scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>'."""
    n, r, p = 2 ** 14, 8, 1
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(hash_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- JWT access / refresh tokens ----------------------------------------------

def _make_token(account_id: int, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(account_id), "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def create_access_token(account_id: int) -> str:
    return _make_token(account_id, "access", ACCESS_TTL)


def create_refresh_token(account_id: int) -> str:
    return _make_token(account_id, "refresh", REFRESH_TTL)


def decode_token(token: str, expected_type: str) -> int:
    """Return the account id from a valid token of expected_type, else raise 401."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Wrong token type")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed token")


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram WebApp initData and return user data.

    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    parsed = parse_qs(init_data)

    if "hash" not in parsed:
        raise ValueError("Missing hash in initData")

    received_hash = parsed.pop("hash")[0]

    data_check_pairs = []
    for key in sorted(parsed.keys()):
        val = parsed[key][0]
        data_check_pairs.append(f"{key}={val}")

    data_check_string = "\n".join(data_check_pairs)

    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()

    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData hash")

    # Replay guard: reject stale initData. `auth_date` is a unix timestamp
    # signed inside the HMAC so we only check it after hash verification.
    auth_date_raw = parsed.get("auth_date", [None])[0]
    if auth_date_raw is None:
        raise ValueError("Missing auth_date in initData")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        raise ValueError("Invalid auth_date in initData")
    age = time.time() - auth_date
    if age < -300:
        raise ValueError("auth_date is in the future")
    if age > INIT_DATA_MAX_AGE_S:
        raise ValueError("initData expired")

    user_data = {}
    if "user" in parsed:
        user_data = json.loads(unquote(parsed["user"][0]))

    return user_data


async def get_current_user(request: Request) -> dict:
    """Extract and validate the Telegram user from the Authorization header."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("tma "):
        init_data = auth_header[4:]
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=503, detail="Server misconfigured: bot token not set")
        try:
            return validate_telegram_init_data(init_data, settings.telegram_bot_token)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    if auth_header.startswith("sync "):
        # Stable token for Apple Watch Shortcut / companion app — does not expire.
        token = auth_header[5:].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing sync token")
        from backend.dependencies.auth_deps import get_db
        from backend.models.database import User
        db = next(get_db())
        try:
            user = db.query(User).filter(User.sync_token == hash_sync_token(token)).first()
        finally:
            db.close()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid sync token")
        return {
            "id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
        }

    if auth_header.startswith("Bearer "):
        # Account (email/password) access token. Resolves to an internal account id;
        # downstream get_or_create_user maps account_id -> the User row.
        account_id = decode_token(auth_header[7:].strip(), "access")
        return {"account_id": account_id}

    if auth_header.startswith("dev "):
        # Dev auth requires explicit opt-in AND a non-production environment.
        # Bot token presence alone no longer disables it so browser testing works
        # alongside a configured token during development.
        if not settings.dev_auth_enabled or settings.environment == "production":
            raise HTTPException(status_code=401, detail="Dev auth is disabled. Use Telegram WebApp auth.")
        try:
            return json.loads(auth_header[4:])
        except json.JSONDecodeError:
            raise HTTPException(status_code=401, detail="Invalid dev auth payload")

    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


def generate_sync_token() -> str:
    """Generate a cryptographically random 32-byte hex sync token (the plaintext)."""
    return secrets.token_hex(32)


def hash_sync_token(token: str) -> str:
    """SHA-256 hex of a sync token. Only the hash is stored, so a DB leak cannot expose
    usable Apple Watch tokens. SHA-256 hex is 64 chars — fits the sync_token column."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
