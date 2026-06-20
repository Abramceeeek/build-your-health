"""Exercise session router — timer-based set logging and calorie burn tracking."""
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import ExerciseSession, DailyTask, UserMetrics, ExerciseLibrary
from backend.services.exercise_service import estimate_calories_burned, MET_VALUES

router = APIRouter(prefix="/api/exercise-sessions", tags=["exercise-sessions"])


class SessionStart(BaseModel):
    task_id: Optional[int] = None
    exercise_name: str
    date: str


class SetLog(BaseModel):
    set_number: int
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    weight_label: str = ""      # e.g. "40kg", "BW", "BW+10kg"
    duration_s: Optional[int] = None   # for timed exercises (plank, etc.)
    rest_after_s: Optional[int] = None  # rest taken after this set


class SessionFinish(BaseModel):
    sets_log: list[SetLog]
    total_duration_s: int
    rest_seconds_total: int = 0


@router.post("/start")
async def start_session(
    data: SessionStart,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record exercise session start."""
    user = get_or_create_user(db, tg_user)

    # Check if session already started for this task today
    if data.task_id:
        existing = db.query(ExerciseSession).filter(
            ExerciseSession.user_id == user.id,
            ExerciseSession.task_id == data.task_id,
            ExerciseSession.date == data.date,
        ).first()
        if existing and existing.finished_at is None:
            return {"session_id": existing.id, "status": "already_started"}

    session = ExerciseSession(
        user_id=user.id,
        task_id=data.task_id,
        date=data.date,
        exercise_name=data.exercise_name,
        sets_log_json=[],
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "status": "started", "started_at": session.started_at.isoformat()}


@router.post("/{session_id}/finish")
async def finish_session(
    session_id: int,
    data: SessionFinish,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finish exercise session, calculate calories, optionally mark task complete."""
    user = get_or_create_user(db, tg_user)
    session = db.query(ExerciseSession).filter(
        ExerciseSession.id == session_id,
        ExerciseSession.user_id == user.id,
    ).with_for_update().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.finished_at is not None:
        # Idempotent: a second finish (double-submit / network retry) must NOT re-award XP,
        # re-add exercise calories, or re-log volume (H13). The row lock above serializes
        # concurrent finishes of the same session so this check is race-safe.
        return {
            "session_id": session_id,
            "status": "already_completed",
            "exercise_name": session.exercise_name,
            "calories_burned": session.calories_burned,
            "xp_earned": 0,
            "total_xp": user.xp,
        }

    # Get user's weight for calorie calculation
    latest_metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id
    ).order_by(UserMetrics.recorded_at.desc()).first()
    user_weight = latest_metrics.weight_kg if latest_metrics and latest_metrics.weight_kg else 75

    # Look up exercise library for MET data
    ex_library = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{session.exercise_name.split()[0]}%")
    ).first()

    duration_active_min = (data.total_duration_s - data.rest_seconds_total) / 60.0

    if ex_library:
        cal = estimate_calories_burned(
            exercise_name=session.exercise_name,
            duration_minutes=duration_active_min,
            user_weight_kg=user_weight,
            exercise_type=ex_library.exercise_type or "compound",
            calories_per_min_override=ex_library.calories_per_min,
        )
    else:
        cal = estimate_calories_burned(
            exercise_name=session.exercise_name,
            duration_minutes=duration_active_min,
            user_weight_kg=user_weight,
        )

    # Update session
    session.sets_log_json = [s.model_dump() for s in data.sets_log]
    session.total_duration_s = data.total_duration_s
    session.rest_seconds_total = data.rest_seconds_total
    session.calories_burned = cal
    session.user_weight_kg = user_weight
    session.finished_at = datetime.now(timezone.utc)

    # Mark the linked task as complete
    xp_change = 0
    if session.task_id:
        task = db.query(DailyTask).filter(
            DailyTask.id == session.task_id,
            DailyTask.user_id == user.id,
        ).first()
        if task and not task.completed:
            task.completed = True
            task.completed_at = datetime.now(timezone.utc)
            user.xp += task.xp_reward
            xp_change = task.xp_reward

    # Update daily health log with exercise calories
    from backend.models.database import DailyHealthLog
    health_log = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user.id,
        DailyHealthLog.date == session.date,
    ).first()
    if health_log:
        health_log.exercise_calories = (health_log.exercise_calories or 0) + int(cal)
    else:
        health_log = DailyHealthLog(
            user_id=user.id,
            date=session.date,
            exercise_calories=int(cal),
        )
        db.add(health_log)

    db.commit()

    # Track volume load for deload detection (non-fatal if it errors)
    try:
        from backend.services.volume_service import update_volume_log
        update_volume_log(db, user.id, session)
    except Exception:
        pass

    return {
        "session_id": session_id,
        "status": "completed",
        "exercise_name": session.exercise_name,
        "sets_completed": len(data.sets_log),
        "active_time_min": round(duration_active_min, 1),
        "rest_time_min": round(data.rest_seconds_total / 60, 1),
        "calories_burned": cal,
        "xp_earned": xp_change,
        "total_xp": user.xp,
    }


@router.get("/daily/{date}")
async def get_daily_sessions(
    date: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all exercise sessions for a date with calorie summary."""
    user = get_or_create_user(db, tg_user)
    sessions = db.query(ExerciseSession).filter(
        ExerciseSession.user_id == user.id,
        ExerciseSession.date == date,
    ).all()

    total_calories = sum(s.calories_burned or 0 for s in sessions)
    total_active_min = sum(
        ((s.total_duration_s or 0) - (s.rest_seconds_total or 0)) / 60
        for s in sessions
    )

    return {
        "date": date,
        "sessions": [
            {
                "id": s.id,
                "exercise_name": s.exercise_name,
                "sets_completed": len(s.sets_log_json or []),
                "calories_burned": s.calories_burned,
                "active_min": round(((s.total_duration_s or 0) - (s.rest_seconds_total or 0)) / 60, 1),
                "finished": s.finished_at is not None,
            }
            for s in sessions
        ],
        "summary": {
            "total_exercises": len(sessions),
            "total_calories_burned": round(total_calories, 1),
            "total_active_min": round(total_active_min, 1),
        },
    }
