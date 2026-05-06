"""Exercise catalog audit — counts per muscle and validates GIF URLs.

Read-only. Run from repo root:

    python scripts/audit_exercises.py

Outputs:
  - Per-muscle count table (flags any below 6).
  - List of broken image URLs (HTTP HEAD failure / non-2xx / timeout).
  - Writes BROKEN_EXERCISES.md at repo root with the details.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import urllib.request
import urllib.error
import ssl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.exercise_service import SEED_EXERCISES  # noqa: E402
from backend.services.muscle_workout_builder import (  # noqa: E402
    MUSCLE_GROUPS, MUSCLE_SEARCH_TERMS,
)

REQUEST_TIMEOUT_S = 6
USER_AGENT = "build-your-helth-audit/1.0"
SSL_CTX = ssl.create_default_context()


def head_ok(url: str) -> tuple[bool, str]:
    if not url:
        return False, "no url"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S, context=SSL_CTX) as resp:
            code = resp.getcode()
            if 200 <= code < 400:
                return True, str(code)
            return False, f"http {code}"
    except urllib.error.HTTPError as e:
        # Some CDNs reject HEAD; retry GET with Range
        if e.code in (403, 405):
            try:
                req = urllib.request.Request(
                    url, method="GET",
                    headers={"User-Agent": USER_AGENT, "Range": "bytes=0-1024"},
                )
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S, context=SSL_CTX) as resp:
                    code = resp.getcode()
                    if 200 <= code < 400:
                        return True, f"{code} (GET fallback)"
                    return False, f"http {code}"
            except Exception as ex:
                return False, f"GET fallback: {ex}"
        return False, f"http {e.code}"
    except Exception as e:
        return False, str(e)[:80]


def muscle_bucket_for(exercise: dict) -> list[str]:
    """Best-effort match of an exercise to one or more muscle keys."""
    primary = exercise.get("muscle_primary") or []
    secondary = exercise.get("muscle_secondary") or []
    groups = exercise.get("muscle_groups") or []
    name = exercise.get("name", "")
    blob = " ".join([str(x).lower() for x in primary + secondary + groups + [name]])
    matched = []
    for mkey, terms in MUSCLE_SEARCH_TERMS.items():
        if any(t.lower() in blob for t in terms):
            matched.append(mkey)
    return matched or ["uncategorized"]


def main() -> int:
    counts: dict[str, int] = defaultdict(int)
    broken: list[dict] = []
    print(f"Auditing {len(SEED_EXERCISES)} seeded exercises...\n")

    for i, ex in enumerate(SEED_EXERCISES, 1):
        for mkey in muscle_bucket_for(ex):
            counts[mkey] += 1

        url = ex.get("image_url", "")
        ok, info = head_ok(url)
        marker = "OK " if ok else "BAD"
        print(f"[{i:>3}/{len(SEED_EXERCISES)}] {marker} {ex.get('name','?'):42}  {info}")
        if not ok:
            broken.append({"name": ex.get("name", "?"), "url": url, "reason": info})
        time.sleep(0.05)  # be nice to the CDN

    print("\n── Counts per muscle ─────────────────────────────")
    target_keys = list(MUSCLE_GROUPS.keys()) + ["uncategorized"]
    low = []
    for mkey in target_keys:
        c = counts.get(mkey, 0)
        flag = " <6 LOW" if c < 6 and mkey in MUSCLE_GROUPS else ""
        print(f"  {mkey:14}  {c:>3}{flag}")
        if c < 6 and mkey in MUSCLE_GROUPS:
            low.append((mkey, c))

    print(f"\nBroken image URLs: {len(broken)} / {len(SEED_EXERCISES)}")
    print(f"Muscles below 6 exercises: {len(low)}")

    report = ROOT / "BROKEN_EXERCISES.md"
    lines = ["# Exercise audit report\n"]
    lines.append(f"Total seeded: {len(SEED_EXERCISES)}\n")
    lines.append("\n## Counts per muscle\n")
    for mkey in target_keys:
        c = counts.get(mkey, 0)
        flag = "  **LOW**" if c < 6 and mkey in MUSCLE_GROUPS else ""
        lines.append(f"- `{mkey}` — {c}{flag}\n")
    lines.append("\n## Broken image URLs\n")
    if not broken:
        lines.append("_None._\n")
    else:
        for b in broken:
            lines.append(f"- **{b['name']}** — `{b['reason']}`\n  {b['url']}\n")
    report.write_text("".join(lines), encoding="utf-8")
    print(f"\nWrote: {report.relative_to(ROOT)}")

    # Also dump JSON next to it for tooling
    (ROOT / "broken_exercises.json").write_text(
        json.dumps({"counts": dict(counts), "broken": broken}, indent=2),
        encoding="utf-8",
    )
    return 0 if not broken and not low else 1


if __name__ == "__main__":
    sys.exit(main())
