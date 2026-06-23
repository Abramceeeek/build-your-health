from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import Optional

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import DailyHealthLog, ReadinessScore, User
from backend.services.time_service import user_local_now, user_today_str

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthUpdate(BaseModel):
    water_glasses: Optional[int] = None
    sleep_hours: Optional[float] = None
    sleep_deep_pct: Optional[float] = None    # 0.0–1.0
    sleep_rem_pct: Optional[float] = None     # 0.0–1.0
    sleep_bedtime: Optional[str] = None       # "HH:MM"
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
    hrv: Optional[float] = None             # HRV RMSSD ms


class WearableSync(BaseModel):
    """Full wearable sync payload — used by Apple Watch Shortcut and companion apps."""
    date: Optional[str] = None              # YYYY-MM-DD, defaults to today
    steps: Optional[int] = None
    active_calories: Optional[float] = None
    resting_hr: Optional[int] = None
    hrv_rmssd: Optional[float] = None      # alias for hrv
    floors_climbed: Optional[int] = None
    sleep_hours: Optional[float] = None
    sleep_deep_pct: Optional[float] = None  # 0.0–1.0
    sleep_rem_pct: Optional[float] = None   # 0.0–1.0
    sleep_bedtime: Optional[str] = None     # HH:MM
    vo2max: Optional[float] = None          # ml/kg/min
    wearable_source: Optional[str] = None


class CycleLogRequest(BaseModel):
    last_period_start: str   # YYYY-MM-DD
    cycle_length: int = Field(default=28, ge=15, le=60)  # service further clamps to 21–35


def _log_to_dict(log: DailyHealthLog) -> dict:
    return {
        "id": log.id,
        "date": log.date,
        "water_glasses": log.water_glasses or 0,
        "sleep_hours": log.sleep_hours or 0,
        "sleep_score": getattr(log, "sleep_score", None),
        "sleep_deep_pct": getattr(log, "sleep_deep_pct", None),
        "sleep_rem_pct": getattr(log, "sleep_rem_pct", None),
        "sleep_bedtime": getattr(log, "sleep_bedtime", None),
        "steps": log.steps or 0,
        "mood": log.mood or 0,
        "supplements_taken": bool(log.supplements_taken),
        "active_calories": getattr(log, "active_calories", None) or 0,
        "resting_hr": getattr(log, "resting_hr", None) or 0,
        "hrv": getattr(log, "hrv", None),
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


def _recalc_sleep_score(db: Session, log: DailyHealthLog, user_id: int) -> None:
    """Recompute sleep_score on the health log and persist it."""
    hours     = log.sleep_hours or 0
    deep_pct  = getattr(log, "sleep_deep_pct", None)
    rem_pct   = getattr(log, "sleep_rem_pct", None)
    bedtime   = getattr(log, "sleep_bedtime", None)

    if not hours:
        return

    # Gather recent bedtimes for consistency scoring
    week_ago = (datetime.strptime(log.date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_logs = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user_id,
        DailyHealthLog.date >= week_ago,
        DailyHealthLog.date < log.date,
        DailyHealthLog.sleep_bedtime.isnot(None),
    ).all()
    recent_bedtimes = [l.sleep_bedtime for l in recent_logs if l.sleep_bedtime]

    from backend.services.sleep_service import calculate_sleep_score
    log.sleep_score = calculate_sleep_score(hours, deep_pct, rem_pct, bedtime, recent_bedtimes)


@router.get("/today")
async def get_health_today(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today_str = user_today_str(user)
    log = _get_or_create_log(db, user.id, today_str)
    return _log_to_dict(log)


@router.post("/update")
async def update_health(
    data: HealthUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today_str = user_today_str(user)
    log = _get_or_create_log(db, user.id, today_str)

    if data.water_glasses is not None:
        log.water_glasses = max(0, min(data.water_glasses, 20))
    if data.sleep_hours is not None:
        log.sleep_hours = max(0.0, min(data.sleep_hours, 24.0))
    if data.sleep_deep_pct is not None:
        log.sleep_deep_pct = max(0.0, min(data.sleep_deep_pct, 1.0))
    if data.sleep_rem_pct is not None:
        log.sleep_rem_pct = max(0.0, min(data.sleep_rem_pct, 1.0))
    if data.sleep_bedtime is not None:
        log.sleep_bedtime = data.sleep_bedtime
    if data.steps is not None:
        log.steps = max(0, data.steps)
    if data.mood is not None:
        log.mood = max(0, min(data.mood, 5))
    if data.supplements_taken is not None:
        log.supplements_taken = data.supplements_taken

    # Auto-calculate sleep score whenever sleep data changes
    sleep_fields_updated = any(
        v is not None for v in [
            data.sleep_hours, data.sleep_deep_pct,
            data.sleep_rem_pct, data.sleep_bedtime,
        ]
    )
    if sleep_fields_updated:
        _recalc_sleep_score(db, log, user.id)

    db.commit()
    db.refresh(log)

    # Recompute readiness score after health data changes
    if any(v is not None for v in [data.sleep_hours, data.mood]):
        from backend.services.readiness_service import compute_and_store
        compute_and_store(db, user.id, today_str)

    return _log_to_dict(log)


@router.patch("/today")
async def patch_wearable_today(
    data: WearableUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save wearable / manual activity data for today."""
    user = get_or_create_user(db, tg_user)
    today_str = user_today_str(user)
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
    if data.hrv is not None and hasattr(log, "hrv"):
        log.hrv = max(0.0, data.hrv)

    db.commit()
    db.refresh(log)

    # Readiness recomputes when HR or HRV change
    if any(v is not None for v in [data.resting_hr, data.hrv]):
        from backend.services.readiness_service import compute_and_store
        compute_and_store(db, user.id, today_str)

    return _log_to_dict(log)


@router.get("/history")
async def get_health_history(
    days: int = 7,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    days = min(days, 90)
    today = user_local_now(user)
    start_str = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    logs = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user.id,
        DailyHealthLog.date >= start_str,
        DailyHealthLog.date <= today_str,
    ).order_by(DailyHealthLog.date.desc()).all()

    return [_log_to_dict(log) for log in logs]


@router.get("/readiness/{date}")
async def get_readiness(
    date: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return readiness score for a given date (YYYY-MM-DD). Computes if missing."""
    user = get_or_create_user(db, tg_user)

    existing = db.query(ReadinessScore).filter(
        ReadinessScore.user_id == user.id,
        ReadinessScore.date == date,
    ).first()

    if existing:
        return {
            "date": existing.date,
            "score": existing.score,
            "sleep_score": existing.sleep_score or 0,
            "rhr_score": existing.rhr_score or 0,
            "hrv_score": existing.hrv_score or 0,
            "mood_score": existing.mood_score or 0,
            "breakdown": existing.breakdown_json or {},
        }

    # Compute on-demand
    from backend.services.readiness_service import compute_and_store
    result = compute_and_store(db, user.id, date)
    if not result:
        return {"date": date, "score": None, "breakdown": {}}

    return {
        "date": date,
        "score": result["score"],
        "breakdown": result["components"],
        "sleep_score": result["components"].get("sleep", 0),
        "rhr_score": result["components"].get("rhr", 0),
        "hrv_score": result["components"].get("hrv", 0),
        "mood_score": result["components"].get("mood", 0),
    }


@router.get("/readiness-history")
async def get_readiness_history(
    days: int = 7,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return last N days of readiness scores for charting."""
    user = get_or_create_user(db, tg_user)
    days = min(days, 30)
    today = user_local_now(user)
    start_str = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = db.query(ReadinessScore).filter(
        ReadinessScore.user_id == user.id,
        ReadinessScore.date >= start_str,
    ).order_by(ReadinessScore.date).all()

    return [
        {
            "date": r.date,
            "score": r.score,
            "sleep_score": r.sleep_score or 0,
            "rhr_score": r.rhr_score or 0,
            "hrv_score": r.hrv_score or 0,
            "mood_score": r.mood_score or 0,
        }
        for r in rows
    ]


# ─── WEARABLE SYNC ────────────────────────────────────────────────────────────

@router.post("/wearable-sync")
async def wearable_sync(
    data: WearableSync,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified wearable sync endpoint for Apple Watch Shortcut and companion apps.

    Accepts a full daily metrics payload, writes to daily_health_logs, and
    auto-triggers sleep score + readiness recompute.
    Returns confirmation with updated scores.
    """
    user = get_or_create_user(db, tg_user)
    date_str = data.date or user_today_str(user)
    log = _get_or_create_log(db, user.id, date_str)

    if data.steps is not None:
        log.steps = max(0, data.steps)
    if data.active_calories is not None:
        log.active_calories = max(0, int(data.active_calories))
    if data.resting_hr is not None:
        log.resting_hr = max(0, min(data.resting_hr, 300))
    if data.hrv_rmssd is not None:
        log.hrv = max(0.0, data.hrv_rmssd)
    if data.floors_climbed is not None:
        log.floors_climbed = max(0, data.floors_climbed)
    if data.sleep_hours is not None:
        log.sleep_hours = max(0.0, min(data.sleep_hours, 24.0))
    if data.sleep_deep_pct is not None:
        log.sleep_deep_pct = max(0.0, min(data.sleep_deep_pct, 1.0))
    if data.sleep_rem_pct is not None:
        log.sleep_rem_pct = max(0.0, min(data.sleep_rem_pct, 1.0))
    if data.sleep_bedtime is not None:
        log.sleep_bedtime = data.sleep_bedtime
    if data.vo2max is not None:
        log.vo2max = max(0.0, data.vo2max)
    if data.wearable_source is not None:
        log.wearable_source = data.wearable_source

    # Auto-calc sleep score if sleep data present
    if any(v is not None for v in [data.sleep_hours, data.sleep_deep_pct, data.sleep_rem_pct]):
        _recalc_sleep_score(db, log, user.id)

    db.commit()
    db.refresh(log)

    # Recompute readiness
    readiness = None
    if any(v is not None for v in [data.sleep_hours, data.resting_hr, data.hrv_rmssd]):
        from backend.services.readiness_service import compute_and_store
        readiness = compute_and_store(db, user.id, date_str)

    return {
        "date": date_str,
        "synced": True,
        "sleep_score": log.sleep_score,
        "readiness_score": readiness["score"] if readiness else None,
    }


# ─── CYCLE TRACKING ───────────────────────────────────────────────────────────

@router.post("/cycle/log-period")
async def log_period(
    data: CycleLogRequest,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log the start of a menstrual period. Gated to female users."""
    user = get_or_create_user(db, tg_user)
    if getattr(user, "sex", None) and user.sex.lower() not in ("female", "f"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cycle tracking is available for female users.")
    from backend.services.cycle_service import log_period as _log
    return _log(user.id, data.last_period_start, data.cycle_length, db)


@router.get("/cycle/phase")
async def get_cycle_phase(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current cycle phase and training adjustments."""
    user = get_or_create_user(db, tg_user)
    from backend.services.cycle_service import get_current_phase
    phase_info = get_current_phase(user, db)
    if phase_info is None:
        return {"phase": None, "message": "No cycle log found. Log your last period start to enable this feature."}
    return phase_info
