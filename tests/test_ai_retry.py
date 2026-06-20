"""AI provider HTTP calls retry transient failures with backoff (H6)."""
import asyncio

import httpx
import pytest

from backend.services import ai_service


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "http://x")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=self.request, response=self)  # type: ignore[arg-type]

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return self._responses.pop(0)


async def _noop(*a, **k):
    return None


def _patch(monkeypatch, responses):
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: _FakeClient(responses))
    monkeypatch.setattr(ai_service.asyncio, "sleep", _noop)  # no real backoff delay in tests


def test_retries_then_succeeds(monkeypatch):
    calls = [_FakeResp(503, {}), _FakeResp(200, {"ok": 1})]
    _patch(monkeypatch, calls)
    result = asyncio.run(ai_service._post_json_with_retry("http://x", json={}))
    assert result == {"ok": 1}
    assert calls == []  # both attempts consumed -> it retried once


def test_does_not_retry_on_400(monkeypatch):
    calls = [_FakeResp(400, {}), _FakeResp(200, {"ok": 1})]
    _patch(monkeypatch, calls)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai_service._post_json_with_retry("http://x", json={}))
    assert len(calls) == 1  # second attempt never happened
