"""Cycle-length validation + phase math (H11)."""
from datetime import date

from backend.models.database import User, CycleLog
from backend.services.cycle_service import (
    normalize_cycle_length, get_current_phase, log_period,
)


def test_normalize_cycle_length_clamps():
    assert normalize_cycle_length(None) == 28
    assert normalize_cycle_length("nope") == 28
    assert normalize_cycle_length(10) == 21    # too short -> clamp up
    assert normalize_cycle_length(45) == 35    # too long -> clamp down
    assert normalize_cycle_length("30") == 30


def test_log_period_persists_clamped_value(db):
    u = User(telegram_id=1, first_name="T")
    db.add(u)
    db.commit()
    res = log_period(u.id, date.today().isoformat(), 45, db)
    assert res["cycle_length"] == 35
    row = db.query(CycleLog).filter(CycleLog.user_id == u.id).first()
    assert row.cycle_length == 35  # no nonsense 45-day cycle stored


def test_current_phase_day_one_is_menstrual(db):
    u = User(telegram_id=2, first_name="T")
    db.add(u)
    db.commit()
    log_period(u.id, date.today().isoformat(), 28, db)
    phase = get_current_phase(u, db)
    assert phase["phase"] == "menstrual"
    assert phase["day_of_cycle"] == 1
    assert phase["cycle_length"] == 28


def test_no_log_returns_none(db):
    u = User(telegram_id=3, first_name="T")
    db.add(u)
    db.commit()
    assert get_current_phase(u, db) is None
