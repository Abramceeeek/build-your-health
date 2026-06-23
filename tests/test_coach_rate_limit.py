"""Coach free-form cap is bucketed by the user's LOCAL calendar day.

Regression guard for the timezone work: the per-message cap used to be a rolling 24h
window (window_seconds=86400), which never aligned with a non-UTC user's calendar
midnight. It now counts the user's own `role == "user"` messages since the start of
THEIR local day (mirroring daily-task completion), so the cap resets at local midnight.
"""
import os
import pathlib
import tempfile
from datetime import timedelta

from backend.models.database import CoachMessage, User
from backend.routers.coach import DAILY_FREEFORM_LIMIT, _freeform_used_today
from backend.services.time_service import user_day_start_utc


def _seed_user(db, offset_minutes=0):
    u = User(telegram_id=555000 + offset_minutes, first_name="Cz", timezone_offset=offset_minutes)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _msg(user_id, role, created_at):
    return CoachMessage(user_id=user_id, role=role, body="x", flagged_injury=False, created_at=created_at)


def test_counts_only_user_role_rows_in_window(db):
    user = _seed_user(db, offset_minutes=0)
    start = user_day_start_utc(user)
    db.add_all([
        _msg(user.id, "user", start + timedelta(hours=1)),
        _msg(user.id, "user", start + timedelta(hours=2)),
        _msg(user.id, "assistant", start + timedelta(hours=1)),   # replies don't count
        _msg(user.id, "assistant", start + timedelta(hours=2)),
    ])
    db.commit()
    assert _freeform_used_today(db, user) == 2


def test_excludes_messages_before_local_day_start(db):
    """A message from the user's previous local day must not count toward today's cap."""
    user = _seed_user(db, offset_minutes=330)  # UTC+5:30 — boundary is NOT UTC midnight
    start = user_day_start_utc(user)
    db.add_all([
        _msg(user.id, "user", start - timedelta(minutes=1)),   # just before local midnight: yesterday
        _msg(user.id, "user", start - timedelta(hours=6)),     # earlier yesterday
        _msg(user.id, "user", start),                          # exactly at local midnight: today
        _msg(user.id, "user", start + timedelta(hours=3)),     # today
    ])
    db.commit()
    assert _freeform_used_today(db, user) == 2


def test_isolated_per_user(db):
    a = _seed_user(db, offset_minutes=0)
    b = _seed_user(db, offset_minutes=60)
    start_a = user_day_start_utc(a)
    db.add_all([
        _msg(a.id, "user", start_a + timedelta(hours=1)),
        _msg(a.id, "user", start_a + timedelta(hours=2)),
        _msg(b.id, "user", user_day_start_utc(b) + timedelta(hours=1)),
    ])
    db.commit()
    assert _freeform_used_today(db, a) == 2
    assert _freeform_used_today(db, b) == 1


def test_at_cap_blocks_further_messages(db):
    user = _seed_user(db, offset_minutes=0)
    start = user_day_start_utc(user)
    for i in range(DAILY_FREEFORM_LIMIT):
        db.add(_msg(user.id, "user", start + timedelta(minutes=i)))
    db.commit()
    # The endpoint blocks once the count reaches the limit (the would-be 21st message).
    assert _freeform_used_today(db, user) == DAILY_FREEFORM_LIMIT
    assert _freeform_used_today(db, user) >= DAILY_FREEFORM_LIMIT


# --- endpoint-level: 20 allowed, 21st returns 429 ----------------------------

_DB = pathlib.Path(tempfile.gettempdir()) / "bh_coach_rl.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ.setdefault("ENVIRONMENT", "development")

from backend.config import get_settings  # noqa: E402
get_settings.cache_clear()

from backend.models.database import Base, get_engine  # noqa: E402
from backend.auth import get_current_user  # noqa: E402
from backend import app as app_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

Base.metadata.create_all(get_engine(get_settings().database_url))


def test_post_message_caps_at_daily_limit(monkeypatch):
    # Stub the LLM call so the test is deterministic and never touches the network.
    monkeypatch.setattr(app_module.coach, "_claude_reply", lambda *a, **k: "ok")
    app_module.app.dependency_overrides[get_current_user] = lambda: {
        "id": 778899, "first_name": "Cap", "last_name": "", "username": "",
    }
    client = TestClient(app_module.app, raise_server_exceptions=False)
    try:
        for _ in range(DAILY_FREEFORM_LIMIT):
            r = client.post("/api/coach/message", json={"body": "morning"})
            assert r.status_code == 200, r.text
        r = client.post("/api/coach/message", json={"body": "morning"})
        assert r.status_code == 429
        assert str(DAILY_FREEFORM_LIMIT) in r.json()["detail"]
    finally:
        app_module.app.dependency_overrides.clear()
