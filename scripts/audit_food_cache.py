"""Food-cache audit — flag any FoodCache rows with all-zero macros.

Read-only. Run from repo root:

    python scripts/audit_food_cache.py

Trust-bug origin: users were seeing 0p / 0c / 0f for foods like "Chicken Breast".
This script lists every cached food row with all four macros at zero so we can
delete or correct them. Items on the small allowlist (Creatine etc.) are excluded.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from backend.models.database import FoodCache, get_session_factory  # noqa: E402
from backend.services.food_seed import ZERO_MACRO_ALLOWED, is_zero_macro  # noqa: E402


def main() -> int:
    Session = get_session_factory(get_settings().database_url)
    db = Session()
    try:
        rows = db.query(FoodCache).all()
        bad = []
        for r in rows:
            n = r.nutrients_per_100g_json or {}
            cal = n.get("calories_per_100g", 0)
            pro = n.get("protein_per_100g", 0)
            carb = n.get("carbs_per_100g", 0)
            fat = n.get("fat_per_100g", 0)
            if is_zero_macro(cal, pro, carb, fat) and r.name not in ZERO_MACRO_ALLOWED:
                bad.append(r)

        if not bad:
            print(f"OK — scanned {len(rows)} foods, none with all-zero macros.")
            return 0

        print(f"FOUND {len(bad)} suspect rows (all-zero macros, not allowlisted):")
        for r in bad:
            print(f"  id={r.id}  source={r.source}  name={r.name!r}  source_id={r.source_id}")
        print()
        print("Action: either correct the macros in food_seed.py + re-seed, or DELETE these rows.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
