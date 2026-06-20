"""Email/password accounts: register, login, refresh, and Bearer-token identity.

Mirrors test_api_smoke's DB setup — point DATABASE_URL at one temp SQLite (set before
importing the app) so the auth endpoints and get_current_user share one real DB.
"""
import os
import pathlib
import tempfile

_DB = pathlib.Path(tempfile.gettempdir()) / "bh_accounts.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ.setdefault("ENVIRONMENT", "development")

from backend.config import get_settings  # noqa: E402
get_settings.cache_clear()

from backend.models.database import Base, get_engine  # noqa: E402
from backend.app import app  # noqa: E402  (binds settings -> temp DB)
from fastapi.testclient import TestClient  # noqa: E402

Base.metadata.create_all(get_engine(get_settings().database_url))
client = TestClient(app, raise_server_exceptions=False)


def _register(email, password="hunter2pw", first_name="Alice"):
    return client.post("/api/v1/auth/register",
                       json={"email": email, "password": password, "first_name": first_name})


def test_register_returns_tokens_and_creates_account():
    r = _register("alice@example.com")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["id"]


def test_register_rejects_duplicate_email():
    _register("dup@example.com")
    r = _register("dup@example.com")
    assert r.status_code == 409


def test_register_rejects_short_password():
    r = _register("shortpw@example.com", password="abc")
    assert r.status_code == 422


def test_register_rejects_bad_email():
    r = _register("not-an-email", password="longenough1")
    assert r.status_code == 422


def test_login_wrong_password_401():
    _register("bob@example.com", password="correctpw1")
    r = client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "wrongpw99"})
    assert r.status_code == 401


def test_login_success_returns_tokens():
    _register("carol@example.com", password="carolpass1")
    r = client.post("/api/v1/auth/login", json={"email": "carol@example.com", "password": "carolpass1"})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_email_is_case_insensitive():
    _register("Mixed@Example.com", password="mixedpass1")
    r = client.post("/api/v1/auth/login", json={"email": "mixed@example.com", "password": "mixedpass1"})
    assert r.status_code == 200


def test_bearer_token_resolves_identity_on_authed_endpoint():
    reg = _register("dave@example.com", first_name="Dave").json()
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {reg['access_token']}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["first_name"] == "Dave"
    assert me["id"] == reg["user"]["id"]


def test_refresh_issues_new_access_token():
    reg = _register("erin@example.com").json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["refresh_token"]})
    assert r.status_code == 200, r.text
    new_access = r.json()["access_token"]
    # the fresh access token works on an authed endpoint
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


def test_access_token_rejected_as_refresh():
    reg = _register("frank@example.com").json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["access_token"]})
    assert r.status_code == 401  # wrong token type


def test_garbage_bearer_rejected():
    r = client.get("/api/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
