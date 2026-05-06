"""User feedback collection — stores to DB and forwards to Telegram channel."""
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import get_settings
from backend.models.database import Feedback
from backend.rate_limit import check_rate_limit
from backend.routers.users import get_db, get_or_create_user

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    category: str = "other"   # bug | idea | praise | other
    rating: Optional[int] = None
    message: str
    page: str = ""


@router.post("")
async def submit_feedback(
    data: FeedbackCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message required.")

    user = get_or_create_user(db, tg_user)

    if not check_rate_limit(user.id, "feedback", max_calls=5):
        raise HTTPException(status_code=429, detail="Too many submissions. Limit: 5 per hour.")

    if data.category not in ("bug", "idea", "praise", "other"):
        data.category = "other"
    if data.rating is not None and not (1 <= data.rating <= 5):
        data.rating = None

    entry = Feedback(
        user_id=user.id,
        category=data.category,
        rating=data.rating,
        message=data.message.strip(),
        page=data.page[:40],
    )
    db.add(entry)
    db.commit()

    # Forward to Telegram channel if configured
    try:
        from backend.services.notification_service import forward_feedback_to_admin
        import asyncio
        asyncio.create_task(forward_feedback_to_admin(
            user_name=user.first_name,
            username=user.username,
            telegram_id=user.telegram_id,
            category=data.category,
            message=data.message.strip(),
            rating=data.rating,
            page=data.page,
        ))
    except Exception:
        pass  # best-effort

    return {"status": "submitted"}
