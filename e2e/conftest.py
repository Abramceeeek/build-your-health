"""End-to-end (Playwright) fixtures: a real app server in a subprocess + helpers.

Kept OUT of tests/ so the fast unit suite never needs a browser. CI runs these in a separate
job that installs Chromium. The server uses a throwaway SQLite DB (create_all builds the full
current schema on boot in development).
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_DB = pathlib.Path(tempfile.gettempdir()) / "bh_e2e.db"

# A complete profile so a seeded account skips the registration wizard and lands on the app.
_FULL_PROFILE = {
    "gender": "male", "goals": ["build_muscle"], "experience_level": "beginner",
    "gym_days_per_week": 3, "available_equipment": ["full_gym"], "injuries": "",
    "gym_schedule_type": "specific_days", "gym_specific_days": [0, 2, 4],
    "gym_every_n_days": None, "muscle_schedule": {"0": ["chest"]}, "age": 30,
}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def live_server():
    if _DB.exists():
        _DB.unlink()
    port = _free_port()
    env = {
        **os.environ,
        "ENVIRONMENT": "development",
        "SCHEDULER_ENABLED": "false",
        "DEV_AUTH_ENABLED": "true",
        "DATABASE_URL": f"sqlite:///{_DB.as_posix()}",
        "JWT_SECRET": "e2e-test-secret",
        "ENCRYPTION_KEY": "",  # dev fallback key (same in this process for seeding)
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env, cwd=str(ROOT),
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            if proc.poll() is not None:
                raise RuntimeError(f"server exited early (code {proc.returncode})")
            try:
                with urllib.request.urlopen(base + "/health", timeout=1) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("server did not become healthy in time")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def register_account(base, email, password="e2epass1234"):
    """Create an email/password account via the public API; return (access_token, user_id)."""
    body = json.dumps({"email": email, "password": password, "first_name": "E2E"}).encode()
    req = urllib.request.Request(base + "/api/v1/auth/register", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        res = json.loads(r.read())
    return res["access_token"], res["user"]["id"]


def mark_registered(user_id):
    """Flag a seeded account as fully onboarded (same SQLite file the server uses) so the app
    skips the registration wizard and renders the dashboard."""
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
    from backend.config import get_settings
    get_settings.cache_clear()
    from backend.models.database import get_session_factory, User
    db = get_session_factory(get_settings().database_url)()
    try:
        u = db.get(User, user_id)
        u.is_registered = True
        u.sex = "male"
        u.last_truth_confirmed_at = datetime.now(timezone.utc)
        u.registration_data_json = _FULL_PROFILE
        db.commit()
    finally:
        db.close()
