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
REFERRAL_BONUS_DAYS = 7


def grant_referral_reward(db: Session, user_id: int, days: int = REFERRAL_BONUS_DAYS) -> None:
    """Extend (or start) a user's trial by `days`, stacking onto any remaining trial time."""
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    now = datetime.now(timezone.utc)
    base = now
    if sub and sub.trial_ends_at:
        end = sub.trial_ends_at.replace(tzinfo=timezone.utc)
        if end > now:
            base = end
    new_end = base + timedelta(days=days)
    if sub is None:
        db.add(Subscription(user_id=user_id, tier="free", status="trialing", trial_ends_at=new_end))
    else:
        sub.trial_ends_at = new_end
        if sub.status == "free":
            sub.status = "trialing"
    db.commit()


def trial_ending_soon(db: Session, within_days: int = 2) -> list[tuple]:
    """[(telegram_id, days_left)] for trialing users whose trial ends within the window (P4.4)."""
    from backend.models.database import User
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=within_days)
    subs = db.query(Subscription).filter(
        Subscription.status == "trialing",
        Subscription.trial_ends_at.isnot(None),
    ).all()
    out = []
    for s in subs:
        end = s.trial_ends_at if s.trial_ends_at.tzinfo else s.trial_ends_at.replace(tzinfo=timezone.utc)
        if now < end <= horizon:
            u = db.query(User).filter(User.id == s.user_id).first()
            if u and u.telegram_id:
                out.append((u.telegram_id, max(1, (end - now).days)))
    return out


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


def activate_pro_from_stars(db: Session, user_id: int, charge_id: str = ""):
    """Called by bot.py when a Stars payment succeeds.

    Idempotent on charge_id (a re-delivered payment is ignored), and renewals STACK onto any
    remaining paid time instead of resetting the 30-day window so paying users don't lose days.
    """
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    now = datetime.now(timezone.utc)

    # Idempotency: ignore a payment we've already processed (provider_sub_id holds the charge id).
    if charge_id and sub and sub.provider_sub_id == charge_id:
        return sub

    # Renewal: extend from the later of now / current period end.
    base = now
    if sub and sub.current_period_end:
        existing_end = sub.current_period_end.replace(tzinfo=timezone.utc)
        if existing_end > now:
            base = existing_end
    period_end = base + timedelta(days=30)

    if sub is None:
        sub = Subscription(
            user_id=user_id,
            tier="pro",
            status="active",
            provider="stars",
            provider_sub_id=charge_id,
            current_period_end=period_end,
        )
        db.add(sub)
    else:
        sub.tier = "pro"
        sub.status = "active"
        sub.provider = "stars"
        sub.provider_sub_id = charge_id
        sub.current_period_end = period_end
    db.commit()
    return sub
