"""Supplement logging router — creatine, whey, BCAAs, omega-3, zinc, magnesium."""
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import SupplementLog

router = APIRouter(prefix="/api/supplements", tags=["supplements"])


# Predefined supplement catalog with science-backed info
SUPPLEMENT_CATALOG = {
    "creatine": {
        "name": "Creatine Monohydrate",
        "emoji": "⚡",
        "default_dose_g": 5.0,
        "when_to_take": "Any time, daily (timing doesn't matter — consistency does)",
        "benefit": "Increases strength, power output, and muscle cell volume. Most researched supplement.",
        "note": "Load for 5-7 days at 20g/day (5g × 4), then 5g/day maintenance. Or just 5g/day from the start.",
        "calories_per_g": 0,
    },
    "whey": {
        "name": "Whey Protein",
        "emoji": "🥛",
        "default_dose_g": 30.0,
        "when_to_take": "Post-workout within 45 min, or between meals to hit protein target",
        "benefit": "Fast-digesting complete protein. Optimal for muscle protein synthesis post-workout.",
        "note": "Mix 1 scoop (~25-30g) in 200-250ml water or milk. Not a replacement for real food.",
        "calories_per_g": 4,
    },
    "bcaa": {
        "name": "BCAAs (Leucine, Isoleucine, Valine)",
        "emoji": "💊",
        "default_dose_g": 10.0,
        "when_to_take": "During fasted training or between meals. Skip if you eat enough protein.",
        "benefit": "Reduces muscle breakdown during training, especially fasted. Leucine triggers MPS.",
        "note": "Mostly redundant if you eat 1.6g protein/kg bodyweight. Use during morning fasted sessions.",
        "calories_per_g": 4,
    },
    "omega3": {
        "name": "Omega-3 Fish Oil",
        "emoji": "🐟",
        "default_dose_g": 3.0,
        "when_to_take": "With a meal, preferably one containing fat for absorption",
        "benefit": "Reduces inflammation, improves joint health, brain function, and cardiovascular health.",
        "note": "Look for 1-2g of EPA+DHA combined per day. Take with food to avoid fish burps.",
        "calories_per_g": 9,
    },
    "zinc": {
        "name": "Zinc",
        "emoji": "⚗️",
        "default_dose_g": 0.025,  # 25mg
        "when_to_take": "Before bed on an empty stomach (enhances absorption)",
        "benefit": "Supports testosterone production, immune function, and wound healing.",
        "note": "Don't exceed 40mg/day. Often stacked with magnesium (ZMA). Don't take with calcium.",
        "calories_per_g": 0,
    },
    "magnesium": {
        "name": "Magnesium Glycinate",
        "emoji": "🌙",
        "default_dose_g": 0.4,  # 400mg
        "when_to_take": "30-60 min before bed",
        "benefit": "Improves sleep quality, reduces muscle cramps, supports 300+ enzymatic reactions.",
        "note": "Glycinate form is most bioavailable and least likely to cause digestive issues.",
        "calories_per_g": 0,
    },
    "vitamin_d": {
        "name": "Vitamin D3",
        "emoji": "☀️",
        "default_dose_g": 0.00125,  # 1250 IU (micrograms)
        "when_to_take": "Morning with fat-containing meal",
        "benefit": "Testosterone support, immune function, bone health, mood. Most people are deficient.",
        "note": "Take with K2 (100-200mcg) for proper calcium direction. 2000-5000 IU/day typical dose.",
        "calories_per_g": 0,
    },
}


class SupplementLogCreate(BaseModel):
    supplement_key: str  # creatine|whey|bcaa|omega3|zinc|magnesium|vitamin_d
    dose_g: Optional[float] = None
    date: Optional[str] = None
    notes: str = ""


@router.get("/catalog")
async def get_catalog():
    """Return the supplement catalog with science info."""
    return SUPPLEMENT_CATALOG


@router.post("/log")
async def log_supplement(
    data: SupplementLogCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    catalog_item = SUPPLEMENT_CATALOG.get(data.supplement_key)
    if not catalog_item:
        raise HTTPException(status_code=400, detail=f"Unknown supplement: {data.supplement_key}")

    date_str = data.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dose = data.dose_g if data.dose_g is not None else catalog_item["default_dose_g"]

    log = SupplementLog(
        user_id=user.id,
        date=date_str,
        supplement_name=data.supplement_key,
        dose_g=dose,
        notes=data.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "id": log.id,
        "supplement": catalog_item["name"],
        "emoji": catalog_item["emoji"],
        "dose_g": dose,
        "date": date_str,
        "benefit": catalog_item["benefit"],
    }


@router.get("/daily/{date}")
async def get_daily_supplements(
    date: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    logs = db.query(SupplementLog).filter(
        SupplementLog.user_id == user.id,
        SupplementLog.date == date,
    ).all()

    taken_keys = {log.supplement_name for log in logs}

    result = []
    for key, info in SUPPLEMENT_CATALOG.items():
        result.append({
            "key": key,
            "name": info["name"],
            "emoji": info["emoji"],
            "default_dose_g": info["default_dose_g"],
            "when_to_take": info["when_to_take"],
            "benefit": info["benefit"],
            "note": info["note"],
            "taken_today": key in taken_keys,
            "log_id": next((log.id for log in logs if log.supplement_name == key), None),
        })
    return result


@router.delete("/log/{log_id}")
async def delete_supplement_log(
    log_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    log = db.query(SupplementLog).filter(
        SupplementLog.id == log_id,
        SupplementLog.user_id == user.id,
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    db.delete(log)
    db.commit()
    return {"status": "deleted"}
