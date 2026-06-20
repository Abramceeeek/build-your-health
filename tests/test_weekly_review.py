"""Weekly review wraps analysis + attaches PubMed citations (P4.2)."""
import asyncio

from backend.services import ai_service


def test_weekly_review_attaches_citations(monkeypatch):
    async def fake_analysis(ctx):
        return {"overall_grade": "B", "headline": "Solid week."}

    async def fake_abstracts(query, max_results=2):
        return [{"pmid": "1", "title": "T", "snippet": "s", "url": "u"}]

    monkeypatch.setattr(ai_service, "generate_weekly_analysis", fake_analysis)
    monkeypatch.setattr("backend.services.pubmed_service.fetch_abstracts", fake_abstracts)

    out = asyncio.run(ai_service.generate_weekly_review({"avg_daily_protein": 80}))
    assert out["overall_grade"] == "B"
    assert out["citations"] == [{"pmid": "1", "title": "T", "snippet": "s", "url": "u"}]
