"""API smoke: every no-path-param GET endpoint must not 500 for an authed, registered user.

This is the cheap, reliable regression net that would have caught the prod `referred_by`
break. (Browser-level "every button" E2E is a heavier follow-up.)

Some endpoints open their own session via get_session_factory(settings.database_url) rather
than the injected get_db, so we point DATABASE_URL at one temp SQLite file (set before
importing the app) and seed it — every session path then shares one real, valid DB. Only
auth is overridden. TestClient is used without `with` so no lifespan/seeding/scheduler runs.
"""
import os
import pathlib
import tempfile
from datetime import datetime, timezone

_DB = pathlib.Path(tempfile.gettempdir()) / "bh_api_smoke.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"

from backend.config import get_settings  # noqa: E402
get_settings.cache_clear()

from backend.models.database import (  # noqa: E402
    Base, get_engine, get_session_factory, User, UserMetrics,
)
from backend.auth import get_current_user  # noqa: E402
from backend.app import app  # noqa: E402  (binds settings -> temp DB)
from fastapi.testclient import TestClient  # noqa: E402


def _setup_db():
    url = get_settings().database_url
    Base.metadata.create_all(get_engine(url))
    db = get_session_factory(url)()
    try:
        if not db.query(User).filter(User.telegram_id == 12345).first():
            u = User(
                telegram_id=12345, first_name="Dev", is_registered=True, sex="male",
                last_truth_confirmed_at=datetime.now(timezone.utc),
                registration_data_json={
                    "gender": "male", "goals": ["build_muscle"], "experience_level": "beginner",
                    "gym_days_per_week": 3, "available_equipment": ["full_gym"], "injuries": "",
                    "gym_schedule_type": "specific_days", "gym_specific_days": [0, 2, 4],
                    "gym_every_n_days": None, "muscle_schedule": {"0": ["chest"]}, "age": 30,
                },
            )
            db.add(u)
            db.commit()
            db.add(UserMetrics(user_id=u.id, height_cm=180, weight_kg=80))
            db.commit()
    finally:
        db.close()


def test_no_param_get_endpoints_never_500():
    _setup_db()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 12345, "first_name": "Dev", "last_name": "", "username": "",
    }
    client = TestClient(app, raise_server_exceptions=False)
    try:
        failures, seen = [], 0
        for route in app.routes:
            methods = getattr(route, "methods", set()) or set()
            path = getattr(route, "path", "")
            if "GET" not in methods or "{" in path:
                continue
            if not (path.startswith("/api") or path in ("/", "/health")):
                continue
            seen += 1
            if client.get(path).status_code >= 500:
                failures.append(path)
        assert seen >= 10, f"expected many endpoints, only saw {seen}"
        assert not failures, f"endpoints returned 5xx: {failures}"
    finally:
        app.dependency_overrides.clear()
