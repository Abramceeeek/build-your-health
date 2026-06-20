"""Stars activation is idempotent and renewals stack remaining time (P3.4)."""
from backend.routers.subscriptions import activate_pro_from_stars
from backend.models.database import User


def _naive(dt):
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def test_activation_idempotent_and_renewal_stacks(db):
    u = User(telegram_id=5, first_name="T")
    db.add(u)
    db.commit()

    s1 = activate_pro_from_stars(db, u.id, charge_id="chg_1")
    db.refresh(s1)
    assert s1.tier == "pro" and s1.status == "active"
    end1 = _naive(s1.current_period_end)

    # Same payment re-delivered -> no change (idempotent).
    s2 = activate_pro_from_stars(db, u.id, charge_id="chg_1")
    db.refresh(s2)
    assert _naive(s2.current_period_end) == end1

    # A new payment (renewal) stacks ~30 more days onto the remaining period.
    s3 = activate_pro_from_stars(db, u.id, charge_id="chg_2")
    db.refresh(s3)
    end3 = _naive(s3.current_period_end)
    assert end3 > end1
    assert 29 <= (end3 - end1).days <= 31
