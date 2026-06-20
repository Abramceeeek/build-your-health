"""Legal endpoint exposes the medical disclaimer + privacy summary (P3.5)."""
import asyncio

from backend.routers.legal import legal, MEDICAL_DISCLAIMER


def test_legal_payload():
    r = asyncio.run(legal())
    assert "not medical advice" in r["medical_disclaimer"].lower()
    assert r["medical_disclaimer"] == MEDICAL_DISCLAIMER
    assert r["privacy_summary"]
