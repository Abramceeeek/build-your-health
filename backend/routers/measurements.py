from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date as date_type

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import BodyMeasurementLog

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


class MeasurementEntry(BaseModel):
    key: str
    value: float
    date: Optional[str] = None  # YYYY-MM-DD; defaults to today


class BulkLogRequest(BaseModel):
    entries: list[MeasurementEntry]


@router.post("/log")
async def log_measurements(
    body: BulkLogRequest,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today = str(date_type.today())
    created = []
    for e in body.entries:
        log = BodyMeasurementLog(
            user_id=user.id,
            key=e.key.strip(),
            value=e.value,
            date=e.date or today,
        )
        db.add(log)
        created.append(log)
    db.commit()
    return {"saved": len(created)}


@router.get("/latest")
async def get_latest(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent value for every measurement key the user has logged."""
    user = get_or_create_user(db, tg_user)
    rows = (
        db.query(BodyMeasurementLog)
        .filter(BodyMeasurementLog.user_id == user.id)
        .order_by(BodyMeasurementLog.date.desc(), BodyMeasurementLog.id.desc())
        .all()
    )
    latest: dict = {}
    for r in rows:
        if r.key not in latest:
            latest[r.key] = {"id": r.id, "value": r.value, "date": r.date}
    return latest


@router.get("/history/{key}")
async def get_history(
    key: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    rows = (
        db.query(BodyMeasurementLog)
        .filter(BodyMeasurementLog.user_id == user.id, BodyMeasurementLog.key == key)
        .order_by(BodyMeasurementLog.date.asc())
        .all()
    )
    return [{"id": r.id, "value": r.value, "date": r.date} for r in rows]


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    row = db.query(BodyMeasurementLog).filter(
        BodyMeasurementLog.id == entry_id,
        BodyMeasurementLog.user_id == user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(row)
    db.commit()
    return {"deleted": entry_id}
