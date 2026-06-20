"""Trial-ending nudge query (P4.4)."""
from datetime import datetime, timezone, timedelta

from backend.routers.subscriptions import trial_ending_soon
from backend.models.database import User, Subscription


def _user_sub(db, tg, status, ends_in_days):
    u = User(telegram_id=tg, first_name="x")
    db.add(u)
    db.commit()
    db.add(Subscription(user_id=u.id, status=status,
                        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=ends_in_days)))
    db.commit()


def test_trial_ending_soon_window(db):
    _user_sub(db, 11, "trialing", 1)    # in window
    _user_sub(db, 22, "trialing", 5)    # too far
    _user_sub(db, 33, "trialing", -1)   # already expired
    _user_sub(db, 44, "active", 1)      # paid, not trialing

    tg_ids = [tg for tg, _ in trial_ending_soon(db, within_days=2)]
    assert tg_ids == [11]
