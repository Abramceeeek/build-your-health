"""Menstrual cycle tracking service.

Phase calculation anchored at ovulation = cycle_length - 14 days before next period.
Gated to users with sex == 'female'.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

PHASE_ADJUSTMENTS = {
    "menstrual": {
        "intensity_mod": -0.20,
        "calorie_mod": 0,
        "note": "Iron-rich foods; gentle movement OK",
    },
    "follicular": {
        "intensity_mod": +0.10,
        "calorie_mod": 0,
        "note": "Peak strength window — push harder",
    },
    "ovulatory": {
        "intensity_mod": +0.15,
        "calorie_mod": 0,
        "note": "Best power output of the cycle",
    },
    "luteal": {
        "intensity_mod": -0.10,
        "calorie_mod": 200,
        "note": "Extra 100–300 kcal; magnesium and rest helpful",
    },
}


def _determine_phase(day: int, cycle_length: int) -> str:
    ovulation_day = cycle_length - 14
    if day <= 5:
        return "menstrual"
    if day <= ovulation_day - 2:
        return "follicular"
    if day <= ovulation_day + 3:
        return "ovulatory"
    return "luteal"


def get_current_phase(user_id: int, db: Session) -> Optional[dict]:
    """Return current cycle phase info for the user. None if no log exists."""
    from backend.models.database import CycleLog
    row = db.query(CycleLog).filter(
        CycleLog.user_id == user_id,
    ).order_by(CycleLog.logged_at.desc()).first()

    if not row:
        return None

    try:
        lps = date.fromisoformat(row.last_period_start)
    except ValueError:
        return None

    cycle_length = row.cycle_length or 28
    today = date.today()
    days_since = (today - lps).days

    # Compute which cycle number we're in
    cycles_elapsed = days_since // cycle_length
    day_of_cycle = days_since % cycle_length + 1

    next_period = lps + timedelta(days=cycle_length * (cycles_elapsed + 1))
    phase = _determine_phase(day_of_cycle, cycle_length)
    adj = PHASE_ADJUSTMENTS[phase]

    return {
        "phase": phase,
        "day_of_cycle": day_of_cycle,
        "cycle_length": cycle_length,
        "next_period": next_period.isoformat(),
        "days_until_next_period": (next_period - today).days,
        "adjustments": adj,
    }


def log_period(user_id: int, last_period_start: str, cycle_length: int, db: Session) -> dict:
    """Save a period start date. Replaces any existing record for the same start date."""
    from backend.models.database import CycleLog
    from datetime import datetime, timezone

    existing = db.query(CycleLog).filter(
        CycleLog.user_id == user_id,
        CycleLog.last_period_start == last_period_start,
    ).first()

    if existing:
        existing.cycle_length = cycle_length
        existing.logged_at = datetime.now(timezone.utc)
    else:
        db.add(CycleLog(
            user_id=user_id,
            last_period_start=last_period_start,
            cycle_length=cycle_length,
        ))
    db.commit()
    return {"status": "logged", "last_period_start": last_period_start, "cycle_length": cycle_length}


def get_adjustments(phase: str) -> dict:
    return PHASE_ADJUSTMENTS.get(phase, PHASE_ADJUSTMENTS["follicular"])
