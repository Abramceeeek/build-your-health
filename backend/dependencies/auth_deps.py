"""Shared database & user dependencies — prevents circular imports."""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.database import User, get_session_factory


def get_db():
    """Yield a SQLAlchemy session scoped to one request."""
    settings = get_settings()
    SessionLocal = get_session_factory(settings.database_url)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user(db: Session, tg_user: dict) -> User:
    """Fetch existing user or create a new record from Telegram data."""
    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="No telegram user id")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.first_name = tg_user.get("first_name", user.first_name)
        user.last_name = tg_user.get("last_name", user.last_name or "")
        user.username = tg_user.get("username", user.username or "")
        user.photo_url = tg_user.get("photo_url", user.photo_url or "")
        db.commit()
        db.refresh(user)
        return user

    user = User(
        telegram_id=telegram_id,
        first_name=tg_user.get("first_name", "User"),
        last_name=tg_user.get("last_name", ""),
        username=tg_user.get("username", ""),
        photo_url=tg_user.get("photo_url", ""),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
