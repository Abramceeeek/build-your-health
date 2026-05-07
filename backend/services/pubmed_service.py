"""PubMed E-utilities integration for coach citation support.

Fetches relevant research abstracts and injects them into coach responses
when the user asks health/fitness advice questions.
"""
import re
import httpx

ADVICE_KEYWORDS = {
    "protein", "carbs", "carbohydrate", "fat", "calorie", "caloric",
    "sleep", "recovery", "rest", "hrv", "heart rate",
    "muscle", "strength", "hypertrophy", "volume", "sets", "reps",
    "cardio", "vo2", "endurance", "aerobic",
    "supplement", "creatine", "caffeine", "omega", "vitamin",
    "weight loss", "fat loss", "bulk", "cut", "deficit", "surplus",
    "exercise", "workout", "training", "periodization", "deload",
    "inflammation", "cortisol", "testosterone", "hormone",
}

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def is_advice_query(text: str) -> bool:
    """Return True if the message likely needs research backing."""
    lower = text.lower()
    return any(kw in lower for kw in ADVICE_KEYWORDS)


async def fetch_abstracts(query: str, max_results: int = 3) -> list[dict]:
    """Search PubMed and return top abstracts for the query.

    Returns: [{pmid, title, snippet, url}]
    Falls back to [] on any network / parse error.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Step 1: get PMIDs
            search_resp = await client.get(ESEARCH_URL, params={
                "db": "pubmed",
                "term": query + "[Title/Abstract] AND humans[MeSH]",
                "retmax": max_results + 2,  # fetch a few extra in case some have no abstract
                "retmode": "json",
                "sort": "relevance",
            })
            search_resp.raise_for_status()
            pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            # Step 2: fetch abstracts
            fetch_resp = await client.get(EFETCH_URL, params={
                "db": "pubmed",
                "id": ",".join(pmids[:max_results]),
                "rettype": "abstract",
                "retmode": "text",
            })
            fetch_resp.raise_for_status()
            raw_text = fetch_resp.text

        return _parse_abstracts(raw_text, pmids[:max_results])

    except Exception:
        return []


def _parse_abstracts(text: str, pmids: list[str]) -> list[dict]:
    """Parse PubMed plain-text abstract block into structured dicts."""
    results = []
    # Split on blank lines between records (PubMed text separates records with blank lines + numbers)
    blocks = re.split(r"\n\n+\d+\.\s", "\n\n1. " + text)
    blocks = [b.strip() for b in blocks if b.strip()]

    for i, (pmid, block) in enumerate(zip(pmids, blocks)):
        # Extract title — first non-empty line of block
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        title = lines[0] if lines else f"PMID {pmid}"

        # Extract abstract — lines after "Abstract" marker or after author line
        abstract_start = 0
        for j, line in enumerate(lines):
            if line.lower().startswith("abstract"):
                abstract_start = j + 1
                break
        snippet_lines = lines[abstract_start:abstract_start + 5]
        snippet = " ".join(snippet_lines)[:300].rstrip()
        if len(" ".join(snippet_lines)) > 300:
            snippet += "…"

        results.append({
            "pmid": pmid,
            "title": title[:150],
            "snippet": snippet,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return results


def build_research_context(abstracts: list[dict]) -> str:
    """Format abstracts for injection into Claude system prompt."""
    if not abstracts:
        return ""
    lines = ["Relevant research (cite these when applicable):"]
    for i, a in enumerate(abstracts, 1):
        lines.append(f"[{i}] PMID {a['pmid']} — {a['title']}: {a['snippet']}")
    return "\n".join(lines)
