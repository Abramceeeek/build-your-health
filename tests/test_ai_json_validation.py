"""call_ai_json rejects valid-but-wrong-shape responses (M12 / D7)."""
import asyncio

from backend.services import ai_service


def test_required_keys_enforced(monkeypatch):
    async def missing(s, u, m):
        return '{"overall_grade":"A"}'
    monkeypatch.setattr(ai_service, "call_ai", missing)
    assert asyncio.run(ai_service.call_ai_json("s", "u", required_keys=["overall_grade", "headline"])) is None

    async def complete(s, u, m):
        return '{"overall_grade":"A","headline":"hi"}'
    monkeypatch.setattr(ai_service, "call_ai", complete)
    out = asyncio.run(ai_service.call_ai_json("s", "u", required_keys=["overall_grade", "headline"]))
    assert out == {"overall_grade": "A", "headline": "hi"}
    # no required_keys → no shape check
    assert asyncio.run(ai_service.call_ai_json("s", "u")) == {"overall_grade": "A", "headline": "hi"}
