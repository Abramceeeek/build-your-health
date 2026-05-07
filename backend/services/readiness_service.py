"""Daily readiness / recovery score (0–100) — Whoop-inspired composite.

Weights (redistribute when component missing):
    HRV score    35%  RMSSD vs 30-day personalized baseline (z-score centred at 50)
    Sleep score  30%  from sleep_service; already 0–100
    RHR score    20%  resting HR vs 30-day baseline; lower = better
    Mood score   15%  mood 1–5 normalized to 0–100

Source: anna-pirogova/hrv-sleep-dashboard pattern adapted for this stack.
"""
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Optional
from sqlalchemy.orm import Session

from backend.models.database import DailyHealthLog, ReadinessScore


def _baseline(values: list) -> tuple:
    """Return (mean, std) with a sensible default std when data is sparse."""
    if not values:
        return 0.0, 15.0
    m = mean(values)
    if len(values) < 2:
        return m, 15.0
    return m, max(stdev(values), 1.0)


def _z_to_100(value: float, base_mean: float, base_std: float) -> float:
    """Z-score mapped to 0–100 centred at 50 (±15 pts per SD)."""
    z = (value - base_mean) / base_std
    return min(100.0, max(0.0, z * 15 + 50))


def _compute_score(
    sleep_score: float,
    mood: Optional[int],
    resting_hr: Optional[int],
    hrv: Optional[float],
    hr_baseline: tuple,
    hrv_baseline: tuple,
) -> dict:
    """Return {"score": float, "components": {name: float, ...}}."""
    weighted_sum = 0.0
    total_weight = 0.0
    components: dict = {}

    # Sleep (always contributes if health log exists)
    w_sleep = 0.30
    components["sleep"] = round(float(sleep_score or 0), 1)
    weighted_sum += components["sleep"] * w_sleep
    total_weight += w_sleep

    # Mood
    if mood and mood > 0:
        mood_score = (mood - 1) / 4 * 100   # 1→0, 5→100
        w_mood = 0.15
        components["mood"] = round(mood_score, 1)
        weighted_sum += mood_score * w_mood
        total_weight += w_mood

    # Resting HR (lower = better)
    if resting_hr and resting_hr > 0 and hr_baseline[0] > 0:
        rhr_score = min(100.0, max(0.0, 100.0 - (resting_hr - hr_baseline[0]) * 3))
        w_rhr = 0.20
        components["rhr"] = round(rhr_score, 1)
        weighted_sum += rhr_score * w_rhr
        total_weight += w_rhr

    # HRV (higher = better)
    if hrv and hrv > 0 and hrv_baseline[0] > 0:
        hrv_score = _z_to_100(hrv, hrv_baseline[0], hrv_baseline[1])
        w_hrv = 0.35
        components["hrv"] = round(hrv_score, 1)
        weighted_sum += hrv_score * w_hrv
        total_weight += w_hrv

    if total_weight == 0:
        return {"score": 50.0, "components": {}}

    score = round(min(100.0, max(0.0, weighted_sum / total_weight)), 1)
    return {"score": score, "components": components}


def compute_and_store(db: Session, user_id: int, date_str: str) -> Optional[dict]:
    """Compute readiness for user on date_str, upsert to readiness_scores, return dict."""
    today = datetime.strptime(date_str, "%Y-%m-%d")
    thirty_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    today_log = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user_id,
        DailyHealthLog.date == date_str,
    ).first()
    if not today_log:
        return None

    baseline_logs = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == user_id,
        DailyHealthLog.date >= thirty_days_ago,
        DailyHealthLog.date < date_str,
    ).all()

    hr_values  = [l.resting_hr for l in baseline_logs if getattr(l, "resting_hr", None)]
    hrv_values = [l.hrv for l in baseline_logs if getattr(l, "hrv", None)]

    result = _compute_score(
        sleep_score=getattr(today_log, "sleep_score", None) or 0.0,
        mood=today_log.mood,
        resting_hr=getattr(today_log, "resting_hr", None),
        hrv=getattr(today_log, "hrv", None),
        hr_baseline=_baseline(hr_values),
        hrv_baseline=_baseline(hrv_values),
    )

    # Upsert
    existing = db.query(ReadinessScore).filter(
        ReadinessScore.user_id == user_id,
        ReadinessScore.date == date_str,
    ).first()

    comps = result["components"]
    if existing:
        existing.score       = result["score"]
        existing.sleep_score = comps.get("sleep", 0)
        existing.rhr_score   = comps.get("rhr", 0)
        existing.hrv_score   = comps.get("hrv", 0)
        existing.mood_score  = comps.get("mood", 0)
        existing.breakdown_json = comps
    else:
        db.add(ReadinessScore(
            user_id=user_id,
            date=date_str,
            score=result["score"],
            sleep_score=comps.get("sleep", 0),
            rhr_score=comps.get("rhr", 0),
            hrv_score=comps.get("hrv", 0),
            mood_score=comps.get("mood", 0),
            breakdown_json=comps,
        ))
    db.commit()
    return result
