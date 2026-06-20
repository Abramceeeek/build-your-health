from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.auth import get_current_user
from backend.dependencies.paywall import require_pro
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import FoodCache, NutritionLog, NutritionTarget
from backend.rate_limit import check_rate_limit
from backend.models.schemas import (
    NutritionLogCreate, NutritionLogResponse, NutritionDailySummary, FoodSearchResult,
)
from backend.services.nutrition_service import search_combined, get_nutrients_scaled
from backend.services.food_seed import (
    COOKING_FACTORS, COOKING_LABELS, calculate_cooked_dish,
    is_zero_macro, ZERO_MACRO_ALLOWED,
)
from backend.services.nutrition_targets import compute_targets
from backend.models.database import UserMetrics


def _resolve_targets(db: Session, user) -> dict:
    """Return per-user TDEE-based targets. Reads the most recent NutritionTarget;
    falls back to recomputing on the fly from latest metrics + registration goals.
    Returns an empty dict only when no metrics exist yet — callers must handle that.
    """
    target = db.query(NutritionTarget).filter(
        NutritionTarget.user_id == user.id,
    ).order_by(NutritionTarget.created_at.desc()).first()
    if target:
        return {
            "daily_calories": target.daily_calories,
            "daily_protein_g": target.daily_protein_g,
            "daily_carbs_g": target.daily_carbs_g,
            "daily_fat_g": target.daily_fat_g,
            "daily_fibre_g": target.daily_fibre_g,
        }

    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id,
    ).order_by(UserMetrics.recorded_at.desc()).first()
    reg = user.registration_data_json or {}
    if metrics and metrics.height_cm and metrics.weight_kg:
        return compute_targets(
            sex=reg.get("gender", "male"),
            weight_kg=metrics.weight_kg,
            height_cm=metrics.height_cm,
            goals=reg.get("goals", []),
            gym_days_per_week=reg.get("gym_days_per_week"),
            age=reg.get("age"),
        )
    return {}

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.get("/search", response_model=list[FoodSearchResult])
async def search_food(
    q: str = Query(..., min_length=2, max_length=64),
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Cap query length so a giant string can't be fanned out to the external food APIs (M3).
    # Custom and local seeded foods matching query
    custom_foods = db.query(FoodCache).filter(
        FoodCache.source == "custom",
        FoodCache.name.ilike(f"%{q}%"),
    ).all()

    local_foods = db.query(FoodCache).filter(
        FoodCache.source == "local",
        FoodCache.name.ilike(f"%{q}%"),
    ).limit(20).all()

    local_and_custom = [
        {
            "source": c.source,
            "source_id": c.source_id,
            "name": c.name,
            **c.nutrients_per_100g_json,
        }
        for c in custom_foods + local_foods
    ]

    api_results = await search_combined(q, db)

    seen_names = {r["name"].lower() for r in local_and_custom}
    for item in api_results:
        if item["name"].lower() not in seen_names:
            seen_names.add(item["name"].lower())
            local_and_custom.append(item)

    return local_and_custom


@router.post("/log", response_model=NutritionLogResponse)
async def log_food(
    data: NutritionLogCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    if is_zero_macro(data.calories, data.protein_g, data.carbs_g, data.fat_g) \
            and data.food_name not in ZERO_MACRO_ALLOWED:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{data.food_name}' has zero macros — please pick a real food or "
                f"enter values via Custom food."
            ),
        )

    log_entry = NutritionLog(
        user_id=user.id,
        date=data.date,
        meal_type=data.meal_type,
        food_name=data.food_name,
        quantity_grams=data.quantity_grams,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        fibre_g=data.fibre_g,
        source=data.source,
        source_id=data.source_id,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


@router.delete("/log/{log_id}")
async def delete_log(
    log_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    entry = db.query(NutritionLog).filter(
        NutritionLog.id == log_id,
        NutritionLog.user_id == user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(entry)
    db.commit()
    return {"status": "deleted"}


@router.get("/daily/{date}", response_model=NutritionDailySummary)
async def get_daily_nutrition(
    date: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    logs = db.query(NutritionLog).filter(
        NutritionLog.user_id == user.id,
        NutritionLog.date == date,
    ).order_by(NutritionLog.logged_at).all()

    meals: dict[str, list] = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}
    total_cal = total_pro = total_carb = total_fat = total_fibre = 0.0

    for log in logs:
        entry = {
            "id": log.id,
            "food_name": log.food_name,
            "quantity_grams": log.quantity_grams,
            "calories": log.calories,
            "protein_g": log.protein_g,
            "carbs_g": log.carbs_g,
            "fat_g": log.fat_g,
            "fibre_g": log.fibre_g,
        }
        meal_key = log.meal_type if log.meal_type in meals else "snack"
        meals[meal_key].append(entry)
        total_cal += log.calories
        total_pro += log.protein_g
        total_carb += log.carbs_g
        total_fat += log.fat_g
        total_fibre += log.fibre_g

    t = _resolve_targets(db, user)

    return NutritionDailySummary(
        date=date,
        total_calories=round(total_cal, 1),
        total_protein=round(total_pro, 1),
        total_carbs=round(total_carb, 1),
        total_fat=round(total_fat, 1),
        total_fibre=round(total_fibre, 1),
        target_calories=t.get("daily_calories", 0),
        target_protein=t.get("daily_protein_g", 0),
        target_carbs=t.get("daily_carbs_g", 0),
        target_fat=t.get("daily_fat_g", 0),
        meals=meals,
    )


@router.get("/targets")
async def get_nutrition_targets(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    t = _resolve_targets(db, user)
    if not t:
        # No metrics on file yet — caller should prompt user to enter height/weight.
        return {
            "daily_calories": 0, "daily_protein_g": 0, "daily_carbs_g": 0,
            "daily_fat_g": 0, "daily_fibre_g": 0, "missing_metrics": True,
        }
    return t


class CustomFoodCreate(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float = 0
    carbs_per_100g: float = 0
    fat_per_100g: float = 0
    fibre_per_100g: float = 0


@router.post("/custom-food")
async def add_custom_food(
    data: CustomFoodCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    source_id = f"custom_{user.id}_{data.name.lower().replace(' ', '_')}"
    nutrients = {
        "calories_per_100g": data.calories_per_100g,
        "protein_per_100g": data.protein_per_100g,
        "carbs_per_100g": data.carbs_per_100g,
        "fat_per_100g": data.fat_per_100g,
        "fibre_per_100g": data.fibre_per_100g,
    }
    existing = db.query(FoodCache).filter(FoodCache.source=="custom", FoodCache.source_id==source_id).first()
    if existing:
        existing.name = data.name
        existing.nutrients_per_100g_json = nutrients
    else:
        db.add(FoodCache(source="custom", source_id=source_id, name=data.name, nutrients_per_100g_json=nutrients))
    db.commit()
    return {"source": "custom", "source_id": source_id, "name": data.name, **nutrients}


# ─── COOKING METHODS ─────────────────────────────────────────────────────────

@router.get("/cooking-methods")
async def get_cooking_methods():
    return [{"key": k, "label": v, "factor": COOKING_FACTORS[k]} for k, v in COOKING_LABELS.items()]


class CookedDishIngredient(BaseModel):
    food_name: str
    grams: float
    nutrients_per_100g: dict


class CookedDishCreate(BaseModel):
    dish_name: str
    cooking_method: str
    ingredients: list[CookedDishIngredient]
    meal_type: str = "lunch"
    date: str
    serving_grams: Optional[float] = None


@router.post("/cooked-dish")
async def log_cooked_dish(
    data: CookedDishCreate,
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    if not check_rate_limit(user.id, "cooked_dish", max_calls=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 60 cooked-dish logs per hour.")
    ingredients = [{"food_name": i.food_name, "grams": i.grams, "nutrients_per_100g": i.nutrients_per_100g} for i in data.ingredients]
    dish_totals = calculate_cooked_dish(ingredients, data.cooking_method)
    total_dish_grams = dish_totals["total_grams"]
    serving = data.serving_grams or total_dish_grams
    scale = serving / total_dish_grams if total_dish_grams > 0 else 1.0

    log_entry = NutritionLog(
        user_id=user.id, date=data.date, meal_type=data.meal_type,
        food_name=f"{data.dish_name} ({dish_totals['cooking_label']})",
        quantity_grams=round(serving, 0),
        calories=round(dish_totals["calories"] * scale, 1),
        protein_g=round(dish_totals["protein_g"] * scale, 1),
        carbs_g=round(dish_totals["carbs_g"] * scale, 1),
        fat_g=round(dish_totals["fat_g"] * scale, 1),
        fibre_g=round(dish_totals["fibre_g"] * scale, 1),
        source="cooked", source_id="",
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return {
        "log_id": log_entry.id, "dish_name": data.dish_name,
        "cooking_method": dish_totals["cooking_label"],
        "cooking_factor": dish_totals["cooking_factor"],
        "total_dish_grams": total_dish_grams, "serving_grams": serving,
        "macros_logged": {"calories": log_entry.calories, "protein_g": log_entry.protein_g, "carbs_g": log_entry.carbs_g, "fat_g": log_entry.fat_g},
    }


# ─── BUDGET MEAL SUGGESTIONS ─────────────────────────────────────────────────

class MealSuggestionRequest(BaseModel):
    budget_level: str = "cheap"
    region_hint: str = "Central Asia"


@router.post("/suggest-meals")
async def suggest_meals(
    data: MealSuggestionRequest,
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    if not check_rate_limit(user.id, "suggest_meals", max_calls=20):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 20 meal suggestions per hour.")
    t = _resolve_targets(db, user)
    if not t:
        raise HTTPException(status_code=400, detail="Add your height and weight in Settings to get personalised meal suggestions.")
    cal_target = t["daily_calories"]
    pro_target = t["daily_protein_g"]
    from backend.services.ai_service import suggest_budget_meals
    return await suggest_budget_meals(cal_target, pro_target, data.budget_level, data.region_hint)


# ─── BARCODE LOOKUP ──────────────────────────────────────────────────────────

@router.get("/barcode/{barcode}")
async def lookup_barcode(
    barcode: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Look up a food product by barcode via Open Food Facts. Caches results."""
    import httpx

    cached = db.query(FoodCache).filter(
        FoodCache.source == "off",
        FoodCache.source_id == barcode,
    ).first()
    if cached:
        return {
            "source": cached.source,
            "source_id": cached.source_id,
            "name": cached.name,
            **cached.nutrients_per_100g_json,
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json",
                headers={"User-Agent": "build-your-health/1.0"},
            )
    except Exception:
        raise HTTPException(status_code=503, detail="Open Food Facts unavailable")

    if r.status_code != 200 or r.json().get("status") != 1:
        raise HTTPException(status_code=404, detail="Product not found")

    product = r.json()["product"]
    n = product.get("nutriments", {})
    name = (product.get("product_name") or product.get("product_name_en") or "").strip()
    if not name:
        raise HTTPException(status_code=404, detail="Product has no name")

    nutrients = {
        "calories_per_100g": float(n.get("energy-kcal_100g") or 0),
        "protein_per_100g":  float(n.get("proteins_100g") or 0),
        "carbs_per_100g":    float(n.get("carbohydrates_100g") or 0),
        "fat_per_100g":      float(n.get("fat_100g") or 0),
        "fibre_per_100g":    float(n.get("fiber_100g") or n.get("fibre_100g") or 0),
    }

    try:
        db.add(FoodCache(source="off", source_id=barcode, name=name, nutrients_per_100g_json=nutrients))
        db.commit()
    except Exception:
        db.rollback()

    return {"source": "off", "source_id": barcode, "name": name, **nutrients}


# ─── FOOD PHOTO IDENTIFICATION ───────────────────────────────────────────────

@router.post("/identify-photo")
async def identify_food_photo(
    file: UploadFile = File(...),
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    """Identify foods in a photo using Claude vision and return macros per item.

    Pro-gated (Claude vision is a paid call) and rate limited to 10 requests/hour/user (M2).
    """
    if not check_rate_limit(user.id, "food_photo_identify", max_calls=10):
        raise HTTPException(status_code=429, detail="Rate limit: 10 food photo identifications per hour.")

    # Validate content type
    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image.")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:   # 10 MB guard
        raise HTTPException(status_code=413, detail="Image too large. Max 10 MB.")

    from backend.services.claude_service import identify_food_from_image
    identified = await identify_food_from_image(image_bytes, content_type)

    if not identified:
        return {"foods": []}

    # Enrich with nutrition data from food_cache
    results = []
    for item in identified:
        name  = item.get("name", "")
        grams = float(item.get("estimated_grams") or 100)
        conf  = float(item.get("confidence") or 0.5)

        # Search food cache for macros
        from backend.services.nutrition_service import search_combined
        matches = await search_combined(name, db)
        macros = matches[0] if matches else {}

        scale = grams / 100.0
        results.append({
            "name": name,
            "estimated_grams": round(grams, 0),
            "confidence": round(conf, 2),
            "calories":   round((macros.get("calories_per_100g") or 0) * scale, 1),
            "protein_g":  round((macros.get("protein_per_100g") or 0) * scale, 1),
            "carbs_g":    round((macros.get("carbs_per_100g") or 0) * scale, 1),
            "fat_g":      round((macros.get("fat_per_100g") or 0) * scale, 1),
            "fibre_g":    round((macros.get("fibre_per_100g") or 0) * scale, 1),
            "source":     macros.get("source", ""),
            "source_id":  macros.get("source_id", ""),
            "matched_food_name": macros.get("name", name),
        })

    return {"foods": results}


# ─── WEEKLY AI ANALYSIS ──────────────────────────────────────────────────────

@router.get("/analysis")
async def get_nutrition_analysis(
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    from backend.services.scheduler import collect_user_context
    from backend.services.ai_service import generate_weekly_analysis
    if not check_rate_limit(user.id, "nutrition_analysis", max_calls=10):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 10 analyses per hour.")
    context = collect_user_context(db, user)
    analysis = await generate_weekly_analysis(context)
    return {"analysis": analysis, "context_summary": {
        "completion_rate": context.get("completion_rate"),
        "avg_daily_calories": context.get("avg_daily_calories"),
        "avg_daily_protein": context.get("avg_daily_protein"),
    }}
