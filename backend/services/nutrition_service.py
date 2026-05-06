"""Nutrition search service combining USDA FoodData Central and Open Food Facts."""

import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.database import FoodCache


USDA_BASE = "https://api.nal.usda.gov/fdc/v1"
OFF_BASE = "https://world.openfoodfacts.org"
CACHE_TTL_DAYS = 7


async def search_openfoodfacts(query: str, limit: int = 15) -> list[dict]:
    """Search Open Food Facts for food items."""
    url = f"{OFF_BASE}/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
        "fields": "code,product_name,nutriments",
    }
    headers = {"User-Agent": "HealthTransform/1.0 (health-app)"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for product in data.get("products", []):
        name = product.get("product_name", "").strip()
        if not name:
            continue
        n = product.get("nutriments", {})
        results.append({
            "source": "openfoodfacts",
            "source_id": product.get("code", ""),
            "name": name,
            "calories_per_100g": round(n.get("energy-kcal_100g", 0) or 0, 1),
            "protein_per_100g": round(n.get("proteins_100g", 0) or 0, 1),
            "carbs_per_100g": round(n.get("carbohydrates_100g", 0) or 0, 1),
            "fat_per_100g": round(n.get("fat_100g", 0) or 0, 1),
            "fibre_per_100g": round(n.get("fiber_100g", 0) or 0, 1),
        })
    return results


async def search_usda(query: str, limit: int = 15) -> list[dict]:
    """Search USDA FoodData Central. Requires USDA_API_KEY in settings."""
    settings = get_settings()
    api_key = getattr(settings, "usda_api_key", "") or "DEMO_KEY"
    if not api_key:
        return []

    url = f"{USDA_BASE}/foods/search"
    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": limit,
        "dataType": ["Foundation", "SR Legacy"],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    results = []
    for food in data.get("foods", []):
        nutrients = {n["nutrientName"]: n.get("value", 0) for n in food.get("foodNutrients", [])}
        results.append({
            "source": "usda",
            "source_id": str(food.get("fdcId", "")),
            "name": food.get("description", "").title(),
            "calories_per_100g": round(nutrients.get("Energy", 0), 1),
            "protein_per_100g": round(nutrients.get("Protein", 0), 1),
            "carbs_per_100g": round(nutrients.get("Carbohydrate, by difference", 0), 1),
            "fat_per_100g": round(nutrients.get("Total lipid (fat)", 0), 1),
            "fibre_per_100g": round(nutrients.get("Fiber, total dietary", 0), 1),
        })
    return results


async def search_combined(query: str, db: Optional[Session] = None) -> list[dict]:
    """Search both USDA and Open Food Facts, deduplicate and rank."""
    # Check cache first
    if db:
        cached = _get_cached_results(db, query)
        if cached:
            return cached

    # Search both APIs
    off_results = await search_openfoodfacts(query)
    usda_results = await search_usda(query)

    # Combine: USDA first (more accurate), then OFF
    combined = usda_results + off_results

    # Deduplicate by name similarity
    seen_names = set()
    unique = []
    for item in combined:
        normalised = item["name"].lower().strip()
        if normalised not in seen_names and item["calories_per_100g"] > 0:
            seen_names.add(normalised)
            unique.append(item)

    # Cache results
    if db and unique:
        _cache_results(db, unique)

    return unique[:50]


def get_nutrients_scaled(food: dict, quantity_grams: float) -> dict:
    """Scale nutrients from per-100g to actual quantity."""
    factor = quantity_grams / 100.0
    return {
        "calories": round(food["calories_per_100g"] * factor, 1),
        "protein_g": round(food["protein_per_100g"] * factor, 1),
        "carbs_g": round(food["carbs_per_100g"] * factor, 1),
        "fat_g": round(food["fat_per_100g"] * factor, 1),
        "fibre_g": round(food["fibre_per_100g"] * factor, 1),
    }


def _get_cached_results(db: Session, query: str) -> list[dict]:
    """Return cached food items matching the query — supports multi-word tokenised search."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)

    # Tokenise: each word must match
    tokens = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not tokens:
        tokens = [query]

    q = db.query(FoodCache).filter(FoodCache.last_fetched >= cutoff)
    for token in tokens:
        q = q.filter(FoodCache.name.ilike(f"%{token}%"))
    cached = q.limit(50).all()

    if not cached:
        return []

    return [
        {
            "source": c.source,
            "source_id": c.source_id,
            "name": c.name,
            **c.nutrients_per_100g_json,
        }
        for c in cached
    ]


def _cache_results(db: Session, results: list[dict]):
    """Cache food search results."""
    for item in results:
        existing = db.query(FoodCache).filter(
            FoodCache.source == item["source"],
            FoodCache.source_id == item["source_id"],
        ).first()

        nutrients = {
            "calories_per_100g": item["calories_per_100g"],
            "protein_per_100g": item["protein_per_100g"],
            "carbs_per_100g": item["carbs_per_100g"],
            "fat_per_100g": item["fat_per_100g"],
            "fibre_per_100g": item["fibre_per_100g"],
        }

        if existing:
            existing.nutrients_per_100g_json = nutrients
            existing.last_fetched = datetime.now(timezone.utc)
        else:
            db.add(FoodCache(
                source=item["source"],
                source_id=item["source_id"],
                name=item["name"],
                nutrients_per_100g_json=nutrients,
            ))

    try:
        db.commit()
    except Exception:
        db.rollback()
