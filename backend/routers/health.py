from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import DailyHealthLog

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthUpdate(BaseModel):
    water_glasses: Optional[int] = None
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
    mood: Optional[int] = None
    supplements_taken: Optional[bool] = None


class WearableUpdate(BaseModel):
    """Wearable / manual activity data for today."""
    steps: Optional[int] = None
    active_calories: Optional[int] = None
    resting_hr: Optional[int] = None
    floors_climbed: Optional[int] = None
    wearable_source: Optional[str] = None   # apple_watch|fitbit|samsung|garmin|mi_band|manual


def _log_to_dict(log: DailyHealthLog) -> dict:
    return {
        "id": log.id,
        "date": log.date,
        "water_glasses": log.water_glasses or 0,
        "sleep_hours": log.sleep_hours or 0,
        "steps": log.steps or 0,
        "mood": log.mood or 0,
        "supplements_taken": bool(log.supplements_taken),
        # Wearable / calorie fields (safe getattr for schema migration compat)
        "active_calories": getattr(log, "active_calories", None) or 0,
        "resting_hr": getattr(log, "resting_hr", None) or 0,
        "floors_climbed": getattr(log, "floors_climbed", None) or 0,
        "wearable_source": getattr(log, "wearable_source", None) or "manual",
        "exercise_calories": getattr(log, "exercise_calories", None) or 0,
    }


def _get_or_create_log(db: Session, user_id: int, date_str: str) -> DailyHealthLog:
    log = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user_id,
        DailyHealthLog.date == date_str,
    ).first()
    if not log:
        log = DailyHealthLog(user_id=user_id, date=date_str)
        db.add(log)
        db.commit()
        db.refresh(log)
    return log


@router.get("/today")
async def get_health_today(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = _get_or_create_log(db, user.id, today_str)
    return _log_to_dict(log)


@router.post("/update")
async def update_health(
    data: HealthUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = _get_or_create_log(db, user.id, today_str)

    if data.water_glasses is not None:
        log.water_glasses = max(0, min(data.water_glasses, 20))
    if data.sleep_hours is not None:
        log.sleep_hours = max(0.0, min(data.sleep_hours, 24.0))
    if data.steps is not None:
        log.steps = max(0, data.steps)
    if data.mood is not None:
        log.mood = max(0, min(data.mood, 5))
    if data.supplements_taken is not None:
        log.supplements_taken = data.supplements_taken

    db.commit()
    db.refresh(log)
    return _log_to_dict(log)


@router.patch("/today")
async def patch_wearable_today(
    data: WearableUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save wearable / manual activity data for today."""
    user = get_or_create_user(db, tg_user)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = _get_or_create_log(db, user.id, today_str)

    if data.steps is not None:
        log.steps = max(0, data.steps)
    if data.active_calories is not None and hasattr(log, "active_calories"):
        log.active_calories = max(0, data.active_calories)
    if data.resting_hr is not None and hasattr(log, "resting_hr"):
        log.resting_hr = max(0, min(data.resting_hr, 300))
    if data.floors_climbed is not None and hasattr(log, "floors_climbed"):
        log.floors_climbed = max(0, data.floors_climbed)
    if data.wearable_source is not None and hasattr(log, "wearable_source"):
        log.wearable_source = data.wearable_source

    db.commit()
    db.refresh(log)
    return _log_to_dict(log)


@router.get("/history")
async def get_health_history(
    days: int = 7,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    days = min(days, 90)
    today = datetime.now(timezone.utc)
    start_str = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    logs = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user.id,
        DailyHealthLog.date >= start_str,
        DailyHealthLog.date <= today_str,
    ).order_by(DailyHealthLog.date.desc()).all()

    return [_log_to_dict(log) for log in logs]
