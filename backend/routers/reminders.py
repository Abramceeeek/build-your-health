"""Reminder management router — Telegram alarm/notification preferences."""
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import UserReminder

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


REMINDER_TYPES = {
    "meal_breakfast": {"label": "Breakfast", "emoji": "🌅", "default_time": "08:00"},
    "meal_lunch": {"label": "Lunch", "emoji": "🌤️", "default_time": "13:00"},
    "meal_dinner": {"label": "Dinner", "emoji": "🌙", "default_time": "19:00"},
    "workout": {"label": "Workout", "emoji": "💪", "default_time": "07:00"},
    "supplement": {"label": "Supplements", "emoji": "💊", "default_time": "08:30"},
    "sleep": {"label": "Sleep / Phone down", "emoji": "😴", "default_time": "22:00"},
    "water": {"label": "Drink Water", "emoji": "💧", "default_time": "10:00"},
}


class ReminderCreate(BaseModel):
    reminder_type: str
    time_hhmm: str   # e.g. "08:30"
    timezone_offset: int = 0  # minutes from UTC (e.g. 300 = UTC+5)
    days_of_week: list[int] = [0, 1, 2, 3, 4, 5, 6]


class ReminderUpdate(BaseModel):
    time_hhmm: Optional[str] = None
    is_active: Optional[bool] = None
    days_of_week: Optional[list[int]] = None


@router.get("/types")
async def get_reminder_types():
    """Return all available reminder types."""
    return REMINDER_TYPES


@router.get("/")
async def get_reminders(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    reminders = db.query(UserReminder).filter(
        UserReminder.user_id == user.id
    ).all()

    # Build response with type info
    result = []
    existing_types = {r.reminder_type: r for r in reminders}

    for rtype, info in REMINDER_TYPES.items():
        existing = existing_types.get(rtype)
        result.append({
            "id": existing.id if existing else None,
            "reminder_type": rtype,
            "label": info["label"],
            "emoji": info["emoji"],
            "time_hhmm": existing.time_hhmm if existing else info["default_time"],
            "is_active": existing.is_active if existing else False,
            "days_of_week": existing.days_of_week if existing else [0, 1, 2, 3, 4, 5, 6],
            "timezone_offset": existing.timezone_offset if existing else 0,
        })

    return result


@router.post("/")
async def create_reminder(
    data: ReminderCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    if data.reminder_type not in REMINDER_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown reminder type: {data.reminder_type}")

    # Upsert — one per type per user
    existing = db.query(UserReminder).filter(
        UserReminder.user_id == user.id,
        UserReminder.reminder_type == data.reminder_type,
    ).first()

    if existing:
        existing.time_hhmm = data.time_hhmm
        existing.timezone_offset = data.timezone_offset
        existing.days_of_week = data.days_of_week
        existing.is_active = True
        db.commit()
        return {"id": existing.id, "status": "updated"}

    reminder = UserReminder(
        user_id=user.id,
        reminder_type=data.reminder_type,
        time_hhmm=data.time_hhmm,
        timezone_offset=data.timezone_offset,
        days_of_week=data.days_of_week,
        is_active=True,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return {"id": reminder.id, "status": "created"}


@router.patch("/{reminder_id}")
async def update_reminder(
    reminder_id: int,
    data: ReminderUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    reminder = db.query(UserReminder).filter(
        UserReminder.id == reminder_id,
        UserReminder.user_id == user.id,
    ).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if data.time_hhmm is not None:
        reminder.time_hhmm = data.time_hhmm
    if data.is_active is not None:
        reminder.is_active = data.is_active
    if data.days_of_week is not None:
        reminder.days_of_week = data.days_of_week

    db.commit()
    return {"status": "updated"}


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    reminder = db.query(UserReminder).filter(
        UserReminder.id == reminder_id,
        UserReminder.user_id == user.id,
    ).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"status": "deleted"}
