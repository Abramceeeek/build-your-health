"""Volume load tracking per muscle group + deload detection.

weekly_volume_load = Σ (sets × reps × weight_kg) per muscle_group per week
Deload trigger: current week load > mean(prev 3 weeks) × 1.15

Muscle group mapping from exercise split_tags:
    PUSH  ← push, chest, shoulder, triceps
    PULL  ← pull, back, biceps
    LEGS  ← legs, quad, hamstring, glute, calf
    CORE  ← core, abs

Source: Snouzy/workout-cool volume landmark pattern.
"""
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional
from sqlalchemy.orm import Session

from backend.models.database import ExerciseSession, ExerciseLibrary, VolumeLoadLog
from backend.services.time_service import user_local_now

_PUSH_TAGS = {"push", "chest", "shoulder", "triceps"}
_PULL_TAGS = {"pull", "back", "biceps"}
_LEGS_TAGS = {"legs", "quad", "hamstring", "glute", "calf"}
_CORE_TAGS = {"core", "abs"}


def _classify_muscle_group(split_tags: Optional[list]) -> str:
    """Map exercise split_tags list to PUSH/PULL/LEGS/CORE."""
    if not split_tags:
        return "PUSH"  # safe default
    tags = {t.lower() for t in split_tags}
    if tags & _LEGS_TAGS:
        return "LEGS"
    if tags & _PULL_TAGS:
        return "PULL"
    if tags & _CORE_TAGS:
        return "CORE"
    return "PUSH"


def _week_start(date_str: str) -> str:
    """Return Monday of the week containing date_str."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def _session_load(sets_log: Optional[list]) -> float:
    """Sum sets×reps×weight_kg from sets_log_json."""
    if not sets_log:
        return 0.0
    total = 0.0
    for s in sets_log:
        reps   = s.get("reps") or 0
        weight = s.get("weight_kg") or 0
        total += reps * weight
    return total


def update_volume_log(db: Session, user_id: int, session: ExerciseSession) -> None:
    """Called after a session finishes — accumulate load into VolumeLoadLog."""
    load = _session_load(session.sets_log_json)
    if load <= 0:
        return

    week = _week_start(session.date)

    # Look up muscle group from exercise library
    ex = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{session.exercise_name.split()[0]}%")
    ).first()
    muscle_group = _classify_muscle_group(ex.split_tags if ex else None)

    existing = db.query(VolumeLoadLog).filter(
        VolumeLoadLog.user_id == user_id,
        VolumeLoadLog.week_start == week,
        VolumeLoadLog.muscle_group == muscle_group,
    ).first()

    if existing:
        existing.total_load    += load
        existing.session_count += 1
    else:
        db.add(VolumeLoadLog(
            user_id=user_id,
            week_start=week,
            muscle_group=muscle_group,
            total_load=load,
            session_count=1,
        ))
    db.commit()


def check_deload_needed(db: Session, user_id: int, user=None) -> bool:
    """Return True if any muscle group this week exceeds 115% of its 3-week average.

    `user` (optional) anchors "current week" on the user's local day; falls back to UTC.
    """
    today = user_local_now(user)
    current_week = _week_start(today.strftime("%Y-%m-%d"))

    current_rows = db.query(VolumeLoadLog).filter(
        VolumeLoadLog.user_id == user_id,
        VolumeLoadLog.week_start == current_week,
    ).all()
    if not current_rows:
        return False

    for row in current_rows:
        # Fetch previous 3 weeks for same muscle group
        prev = db.query(VolumeLoadLog).filter(
            VolumeLoadLog.user_id == user_id,
            VolumeLoadLog.muscle_group == row.muscle_group,
            VolumeLoadLog.week_start < current_week,
        ).order_by(VolumeLoadLog.week_start.desc()).limit(3).all()

        if len(prev) < 2:
            continue  # not enough history

        avg_load = mean(p.total_load for p in prev)
        if avg_load > 0 and row.total_load > avg_load * 1.15:
            return True

    return False


def get_volume_trend(db: Session, user_id: int, weeks: int = 8) -> list:
    """Return list of {week_start, PUSH, PULL, LEGS, CORE} dicts for charting."""
    today = datetime.utcnow()
    cutoff = (today - timedelta(weeks=weeks)).strftime("%Y-%m-%d")

    rows = db.query(VolumeLoadLog).filter(
        VolumeLoadLog.user_id == user_id,
        VolumeLoadLog.week_start >= cutoff,
    ).order_by(VolumeLoadLog.week_start).all()

    # Group by week
    by_week: dict = {}
    for row in rows:
        w = by_week.setdefault(row.week_start, {"week_start": row.week_start, "PUSH": 0, "PULL": 0, "LEGS": 0, "CORE": 0})
        w[row.muscle_group] = round(row.total_load, 1)

    return list(by_week.values())
