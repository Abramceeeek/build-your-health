"""Pro subscription gate — use Depends(require_pro) on paid endpoints."""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.models.database import Subscription
from backend.dependencies.auth_deps import get_db, get_or_create_user


def _is_pro(sub: Subscription | None) -> bool:
    if sub is None:
        return False
    if sub.status == "trialing" and sub.trial_ends_at:
        return sub.trial_ends_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    return sub.tier == "pro" and sub.status == "active"


def require_pro(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dependency that blocks non-Pro users with HTTP 402."""
    user = get_or_create_user(db, tg_user)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not _is_pro(sub):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "pro_required",
                "message": "This feature requires Pro. Your 14-day trial awaits.",
            },
        )
    return user
