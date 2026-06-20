"""Bio-age safety bounds (H9 VO2max/RHR clamp, H10 activity de-double-counting)."""
from datetime import datetime, timezone

from backend.models.database import User, DailyHealthLog
from backend.services.bio_age_service import compute_bio_age, VO2MAX_MIN, VO2MAX_MAX


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _user(db, **kw):
    u = User(telegram_id=1, first_name="T", sex=kw.get("sex", "male"),
             registration_data_json={"age": kw.get("age", 30)})
    db.add(u)
    db.commit()
    return u


def test_vo2max_estimate_is_clamped_for_implausible_rhr(db):
    # RHR below the accepted floor (40) must be ignored -> no inflated VO2max -> neutral score.
    u = _user(db, age=30)
    db.add(DailyHealthLog(user_id=u.id, date=_today(), resting_hr=31))
    db.commit()
    res = compute_bio_age(u, db)
    # RHR=31 is filtered out, so no VO2max estimate -> cardiovascular falls back to neutral 50.
    assert res["vo2max_used"] is None
    assert res["components"]["cardiovascular"] == 50.0


def test_vo2max_never_exceeds_physiological_max(db):
    u = _user(db, age=30)
    # Valid-but-low RHR=40 -> 15.3*190/40 = 72.7, within bounds.
    db.add(DailyHealthLog(user_id=u.id, date=_today(), resting_hr=40))
    db.commit()
    res = compute_bio_age(u, db)
    assert res["vo2max_used"] is not None
    assert VO2MAX_MIN <= res["vo2max_used"] <= VO2MAX_MAX


def test_activity_score_does_not_double_count(db):
    u = _user(db, age=30)
    # 10k steps (=100 min) AND 600 active cal (=150 min) on the same day.
    # Summing would give 250 min/wk -> 100. max() gives 150 -> still 100 here, so use a
    # smaller sample that distinguishes: 3000 steps (30 min) + 120 cal (30 min).
    db.add(DailyHealthLog(user_id=u.id, date=_today(), steps=3000, active_calories=120))
    db.commit()
    res = compute_bio_age(u, db)
    # max(30, 30) = 30 min/wk -> 30/150*100 = 20, NOT 60/150*100 = 40 (the old double-count).
    assert res["components"]["activity"] == 20.0
