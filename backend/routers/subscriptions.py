"""Subscription management — trial grants, status, and Telegram Stars payments."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import get_settings
from backend.models.database import Subscription
from backend.routers.users import get_db, get_or_create_user

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

TRIAL_DAYS = 14


def _grant_trial(db: Session, user_id: int) -> Subscription:
    """Create or reset subscription to a fresh 14-day trial."""
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    trial_end = datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)
    if sub is None:
        sub = Subscription(
            user_id=user_id,
            tier="free",
            status="trialing",
            trial_ends_at=trial_end,
        )
        db.add(sub)
    elif sub.status == "free":
        sub.status = "trialing"
        sub.trial_ends_at = trial_end
    db.commit()
    return sub


@router.get("/status")
async def get_subscription_status(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    now = datetime.now(timezone.utc)
    if sub is None:
        return {"tier": "free", "status": "free", "days_remaining": 0, "is_pro": False}

    is_trialing = (
        sub.status == "trialing"
        and sub.trial_ends_at
        and sub.trial_ends_at.replace(tzinfo=timezone.utc) > now
    )
    is_active_pro = sub.tier == "pro" and sub.status == "active"
    is_pro = is_trialing or is_active_pro

    days_remaining = 0
    if is_trialing and sub.trial_ends_at:
        days_remaining = max(0, (sub.trial_ends_at.replace(tzinfo=timezone.utc) - now).days)
    elif is_active_pro and sub.current_period_end:
        days_remaining = max(0, (sub.current_period_end.replace(tzinfo=timezone.utc) - now).days)

    return {
        "tier": sub.tier,
        "status": sub.status,
        "is_pro": is_pro,
        "days_remaining": days_remaining,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
    }


@router.post("/start-trial")
async def start_trial(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually start a 14-day trial (called from paywall upgrade sheet)."""
    user = get_or_create_user(db, tg_user)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    # Only grant trial if user has never had one
    if sub and sub.status not in ("free",):
        raise HTTPException(status_code=409, detail="Trial already used or subscription active.")

    _grant_trial(db, user.id)
    return {"status": "trialing", "days": TRIAL_DAYS}


@router.post("/create-stars-invoice")
async def create_stars_invoice(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Telegram Stars invoice for Pro subscription."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Bot not configured.")

    user = get_or_create_user(db, tg_user)
    if not user.telegram_id:
        raise HTTPException(status_code=400, detail="No Telegram ID.")

    # 500 Stars ≈ $4.99 at current Telegram rate
    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendInvoice"
        payload = {
            "chat_id": user.telegram_id,
            "title": "claudeGYM Pro",
            "description": "AI weekly plans, photo analysis, meal suggestions — 30 days.",
            "payload": f"pro_monthly_{user.id}",
            "provider_token": "",   # empty = Telegram Stars
            "currency": "XTR",     # Telegram Stars currency code
            "prices": [{"label": "Pro (30 days)", "amount": 500}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        return {"status": "invoice_sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send invoice: {e}")


def activate_pro_from_stars(db: Session, user_id: int):
    """Called by bot.py when Stars payment succeeds."""
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=30)
    if sub is None:
        sub = Subscription(
            user_id=user_id,
            tier="pro",
            status="active",
            provider="stars",
            current_period_end=period_end,
        )
        db.add(sub)
    else:
        sub.tier = "pro"
        sub.status = "active"
        sub.provider = "stars"
        sub.current_period_end = period_end
    db.commit()
    return sub
