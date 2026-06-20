"""End-to-end: the timezone offset endpoint persists, and request handlers bucket by the
user's local calendar day (regression guard that endpoints use the helper, not utcnow)."""
import os
import pathlib
import tempfile

_DB = pathlib.Path(tempfile.gettempdir()) / "bh_tz_wiring.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ.setdefault("ENVIRONMENT", "development")

from backend.config import get_settings  # noqa: E402
get_settings.cache_clear()

from backend.models.database import Base, get_engine, User  # noqa: E402
from backend.auth import get_current_user  # noqa: E402
from backend.app import app  # noqa: E402
from backend.services.time_service import user_today_str  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

Base.metadata.create_all(get_engine(get_settings().database_url))


def _client_as(telegram_id):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": telegram_id, "first_name": "Tz", "last_name": "", "username": "",
    }
    return TestClient(app, raise_server_exceptions=False)


def test_set_timezone_persists_and_reports_local_date():
    c = _client_as(99001)
    r = c.put("/api/users/me/timezone", json={"offset_minutes": 330})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["timezone_offset"] == 330
    assert body["local_date"] == user_today_str(User(timezone_offset=330))
    app.dependency_overrides.clear()


def test_set_timezone_rejects_out_of_range():
    c = _client_as(99002)
    r = c.put("/api/users/me/timezone", json={"offset_minutes": 999})
    assert r.status_code == 422
    app.dependency_overrides.clear()


def test_today_endpoint_uses_user_local_day():
    c = _client_as(99003)
    assert c.put("/api/users/me/timezone", json={"offset_minutes": 330}).status_code == 200
    r = c.get("/api/tasks/today")
    assert r.status_code == 200, r.text
    assert r.json()["date"] == user_today_str(User(timezone_offset=330))
    app.dependency_overrides.clear()


def test_offset_zero_matches_utc_day():
    from datetime import datetime, timezone
    c = _client_as(99004)  # default offset 0
    r = c.get("/api/tasks/today")
    assert r.status_code == 200, r.text
    assert r.json()["date"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")
    app.dependency_overrides.clear()
