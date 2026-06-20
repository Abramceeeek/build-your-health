from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer as SAInteger
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import DailyTask, UserMetrics
from backend.services.scoring import get_muscle_heatmap

router = APIRouter(prefix="/api/heatmap", tags=["heatmap"])


class MetricsCreate(BaseModel):
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    neck_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    bicep_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    notes: str = ""


@router.get("/week")
async def get_weekly_heatmap(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    sunday_str = (monday + timedelta(days=6)).strftime("%Y-%m-%d")

    completed_gym_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= monday_str,
        DailyTask.date <= sunday_str,
        DailyTask.section == "gym",
        DailyTask.completed == True,
    ).all()

    exercise_names = [t.title for t in completed_gym_tasks]
    heatmap = get_muscle_heatmap(exercise_names)

    return {
        "week_start": monday_str,
        "week_end": sunday_str,
        "exercises_completed": len(exercise_names),
        "muscle_data": heatmap,
    }


@router.get("/calendar")
async def get_calendar_data(
    months: int = 6,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return daily task completion data for the GitHub-style contribution calendar.

    Returns a dict mapping date strings to completion percentages for the last N months.
    """
    user = get_or_create_user(db, tg_user)

    today = datetime.now(timezone.utc)
    start_date = today - timedelta(days=months * 31)
    start_str = start_date.strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    tasks = db.query(
        DailyTask.date,
        func.count(DailyTask.id).label("total"),
        func.sum(DailyTask.completed.cast(SAInteger)).label("done"),
    ).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= start_str,
        DailyTask.date <= today_str,
    ).group_by(DailyTask.date).all()

    days = {}
    total_done = 0
    total_tasks = 0
    active_days = 0
    perfect_days = 0

    for row in tasks:
        done = int(row.done or 0)
        total = int(row.total or 0)
        pct = round(done / total * 100) if total else 0
        days[row.date] = {"done": done, "total": total, "pct": pct}
        total_done += done
        total_tasks += total
        if done > 0:
            active_days += 1
        if pct == 100:
            perfect_days += 1

    # Step by real calendar months (not 30-day windows, which drift against variable
    # month lengths and silently drop/duplicate months — M13).
    month_summaries = []
    y, mo = today.year, today.month
    for _ in range(months):
        month_str = f"{y:04d}-{mo:02d}"
        month_days = {k: v for k, v in days.items() if k.startswith(month_str)}
        month_done = sum(d["done"] for d in month_days.values())
        month_total = sum(d["total"] for d in month_days.values())
        month_summaries.append({
            "month": month_str,
            "done": month_done,
            "total": month_total,
            "pct": round(month_done / month_total * 100) if month_total else 0,
            "days_active": len([d for d in month_days.values() if d["done"] > 0]),
        })
        mo -= 1
        if mo == 0:
            mo, y = 12, y - 1

    return {
        "days": days,
        "summary": {
            "total_done": total_done,
            "total_tasks": total_tasks,
            "overall_pct": round(total_done / total_tasks * 100) if total_tasks else 0,
            "active_days": active_days,
            "perfect_days": perfect_days,
        },
        "months": month_summaries,
    }


@router.get("/progress")
async def get_progress_timeline(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return weekly progress summaries for the timeline view."""
    user = get_or_create_user(db, tg_user)

    today = datetime.now(timezone.utc)

    # Anchor timeline to user's actual registration date — no phantom weeks before signup.
    reg_date = user.registration_completed_at or user.joined_at
    reg_str = reg_date.strftime("%Y-%m-%d") if reg_date else None

    weeks = []

    for w in range(8):
        week_end = today - timedelta(days=today.weekday()) - timedelta(weeks=w)
        week_start = week_end - timedelta(days=6)

        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")

        # Skip weeks that ended before the user registered.
        if reg_str and end_str < reg_str:
            break

        tasks = db.query(DailyTask).filter(
            DailyTask.user_id == user.id,
            DailyTask.date >= start_str,
            DailyTask.date <= end_str,
        ).all()

        done = sum(1 for t in tasks if t.completed)
        total = len(tasks)

        categories = {}
        for t in tasks:
            cat = t.category or "health"
            if cat not in categories:
                categories[cat] = {"done": 0, "total": 0}
            categories[cat]["total"] += 1
            if t.completed:
                categories[cat]["done"] += 1

        is_first = reg_str and start_str <= reg_str <= end_str
        weeks.append({
            "week_start": start_str,
            "week_end": end_str,
            "done": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
            "is_first_week": bool(is_first),
            "categories": {
                k: round(v["done"] / v["total"] * 100) if v["total"] else 0
                for k, v in categories.items()
            },
        })

    return {"weeks": weeks}


@router.post("/metrics")
async def save_metrics(
    data: MetricsCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save body metrics (height, weight, measurements)."""
    user = get_or_create_user(db, tg_user)

    metrics = UserMetrics(
        user_id=user.id,
        height_cm=data.height_cm,
        weight_kg=data.weight_kg,
        body_fat_pct=data.body_fat_pct,
        neck_cm=data.neck_cm,
        chest_cm=data.chest_cm,
        waist_cm=data.waist_cm,
        hips_cm=data.hips_cm,
        bicep_cm=data.bicep_cm,
        thigh_cm=data.thigh_cm,
        notes=data.notes,
    )
    db.add(metrics)
    db.commit()
    db.refresh(metrics)

    return {
        "id": metrics.id,
        "recorded_at": metrics.recorded_at.isoformat(),
        "height_cm": metrics.height_cm,
        "weight_kg": metrics.weight_kg,
        "body_fat_pct": metrics.body_fat_pct,
    }


@router.get("/metrics")
async def get_metrics_history(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all body metrics entries ordered by date."""
    user = get_or_create_user(db, tg_user)

    entries = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id,
    ).order_by(UserMetrics.recorded_at.desc()).limit(30).all()

    return [{
        "id": e.id,
        "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
        "height_cm": e.height_cm,
        "weight_kg": e.weight_kg,
        "body_fat_pct": e.body_fat_pct,
        "neck_cm": e.neck_cm,
        "chest_cm": e.chest_cm,
        "waist_cm": e.waist_cm,
        "hips_cm": e.hips_cm,
        "bicep_cm": e.bicep_cm,
        "thigh_cm": e.thigh_cm,
        "notes": e.notes,
    } for e in entries]


@router.get("/metrics/latest")
async def get_latest_metrics(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent body metrics entry."""
    user = get_or_create_user(db, tg_user)

    latest = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id,
    ).order_by(UserMetrics.recorded_at.desc()).first()

    if not latest:
        return {"message": "No metrics recorded yet"}

    return {
        "id": latest.id,
        "recorded_at": latest.recorded_at.isoformat() if latest.recorded_at else None,
        "height_cm": latest.height_cm,
        "weight_kg": latest.weight_kg,
        "body_fat_pct": latest.body_fat_pct,
        "neck_cm": latest.neck_cm,
        "chest_cm": latest.chest_cm,
        "waist_cm": latest.waist_cm,
        "hips_cm": latest.hips_cm,
        "bicep_cm": latest.bicep_cm,
        "thigh_cm": latest.thigh_cm,
        "notes": latest.notes,
    }
