"""Biological age estimation using HUNT Non-Exercise VO2max model.

Components:
  cardiovascular  28%  — VO2max vs age/sex norms (HUNT study)
  activity        24%  — weekly active minutes vs WHO 150-min target
  body_comp       18%  — BMI-derived (penalises > 22 kg/m²)
  recovery        30%  — 30-day avg readiness score
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

# VO2max norms (ml/kg/min) by sex and decade, from HUNT study
_VO2MAX_NORMS: dict[str, dict[str, float]] = {
    "male":   {"20s": 44, "30s": 42, "40s": 39, "50s": 35, "60s": 30},
    "female": {"20s": 38, "30s": 35, "40s": 32, "50s": 29, "60s": 25},
}


def _age_bracket(age: int) -> str:
    if age < 30:
        return "20s"
    if age < 40:
        return "30s"
    if age < 50:
        return "40s"
    if age < 60:
        return "50s"
    return "60s"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def compute_bio_age(user, db: Session) -> Optional[dict]:
    """Compute biological age for a user.

    Returns None when insufficient data (no age, no metrics).
    """
    from backend.models.database import DailyHealthLog, UserMetrics, ReadinessScore

    # --- Resolve age and sex ---
    age: Optional[int] = None
    if user.date_of_birth:
        try:
            dob = date.fromisoformat(user.date_of_birth)
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except ValueError:
            pass

    # Fall back to registration_data_json["age"] if no DOB stored
    if age is None:
        reg = user.registration_data_json or {}
        age_raw = reg.get("age")
        if age_raw:
            try:
                age = int(age_raw)
            except (TypeError, ValueError):
                pass

    if not age or age < 16 or age > 90:
        return None

    sex = (user.sex or "male").lower()
    if sex not in _VO2MAX_NORMS:
        sex = "male"

    # --- Latest metrics (weight + height for BMI) ---
    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id,
    ).order_by(UserMetrics.recorded_at.desc()).first()

    bmi: Optional[float] = None
    if metrics and metrics.weight_kg and metrics.height_cm and metrics.height_cm > 0:
        bmi = metrics.weight_kg / (metrics.height_cm / 100) ** 2

    # --- Cardiovascular score via HUNT VO2max ---
    # Try stored wearable VO2max first (last 30 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    vo2max_row = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user.id,
        DailyHealthLog.vo2max.isnot(None),
        DailyHealthLog.date >= cutoff,
    ).order_by(DailyHealthLog.date.desc()).first()

    vo2max: Optional[float] = vo2max_row.vo2max if vo2max_row else None

    # HUNT Non-Exercise estimate: 15.3 × (max_hr / resting_hr)
    if vo2max is None:
        rhr_row = db.query(DailyHealthLog).filter(
            DailyHealthLog.user_id == user.id,
            DailyHealthLog.resting_hr > 30,
            DailyHealthLog.date >= cutoff,
        ).order_by(DailyHealthLog.date.desc()).first()
        if rhr_row and rhr_row.resting_hr:
            max_hr = 220 - age
            vo2max = 15.3 * (max_hr / rhr_row.resting_hr)

    norm = _VO2MAX_NORMS[sex][_age_bracket(age)]
    cardiovascular_score = _clamp((vo2max / norm * 100) if vo2max else 50.0)

    # --- Activity score (weekly active minutes, last 7 days) ---
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_logs = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user.id,
        DailyHealthLog.date >= week_ago,
    ).all()

    # Approximate active minutes from steps (2000 steps ≈ 20 min brisk walk)
    total_steps = sum((l.steps or 0) for l in recent_logs)
    weekly_active_min = total_steps / 100  # rough conversion
    # Add time from active calories if available (4 kcal/min moderate intensity)
    total_active_cal = sum((l.active_calories or 0) for l in recent_logs)
    weekly_active_min += total_active_cal / 4
    activity_score = _clamp(weekly_active_min / 150 * 100)

    # --- Body composition score ---
    if bmi is not None:
        body_comp_score = _clamp(100.0 - max(0.0, bmi - 22) * 5)
    else:
        body_comp_score = 50.0  # neutral if no data

    # --- Recovery score (30-day avg readiness) ---
    cutoff_30 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    readiness_rows = db.query(ReadinessScore).filter(
        ReadinessScore.user_id == user.id,
        ReadinessScore.date >= cutoff_30,
    ).all()
    recovery_score = (
        sum(r.score for r in readiness_rows) / len(readiness_rows)
        if readiness_rows else 50.0
    )

    # --- Weighted composite ---
    composite = (
        cardiovascular_score * 0.28
        + activity_score * 0.24
        + body_comp_score * 0.18
        + recovery_score * 0.30
    )

    delta = (50.0 - composite) / 5.0
    bio_age = round(age + delta, 1)

    return {
        "bio_age": bio_age,
        "chronological_age": age,
        "delta": round(delta, 1),
        "composite_score": round(composite, 1),
        "components": {
            "cardiovascular": round(cardiovascular_score, 1),
            "activity": round(activity_score, 1),
            "body_comp": round(body_comp_score, 1),
            "recovery": round(recovery_score, 1),
        },
        "vo2max_used": round(vo2max, 1) if vo2max else None,
        "data_completeness": _completeness(vo2max, bmi, readiness_rows),
    }


def _completeness(vo2max, bmi, readiness_rows) -> str:
    score = sum([vo2max is not None, bmi is not None, len(readiness_rows) >= 7])
    return ["low", "medium", "medium", "high"][score]
