"""Sleep quality scoring — composite from duration, stage percentages, bedtime consistency.

Algorithm (SomnoAI-inspired):
    duration_score   40%  optimal 8h; linear penalty outside 7–9h band
    stage_score      30%  if wearable provides deep/REM pct; else redistributed
    efficiency_score 30%  bedtime consistency vs personal avg; else redistributed
"""
import math
from statistics import mean
from typing import Optional


def calculate_sleep_score(
    hours: float,
    deep_pct: Optional[float] = None,
    rem_pct: Optional[float] = None,
    bedtime: Optional[str] = None,
    recent_bedtimes: Optional[list] = None,
) -> float:
    """Return 0–100 sleep quality score.

    Args:
        hours: sleep duration in hours
        deep_pct: fraction of sleep in deep stage (0.0–1.0), e.g. 0.20
        rem_pct:  fraction of sleep in REM stage (0.0–1.0), e.g. 0.22
        bedtime:  "HH:MM" string for tonight's bedtime
        recent_bedtimes: list of "HH:MM" strings from last 7+ nights
    """
    if not hours or hours <= 0:
        return 0.0

    # ── Duration score (40% base weight) ───────────────────────────────────
    deviation = max(0.0, abs(hours - 8.0) - 1.0)   # 0 penalty inside 7–9h
    duration_score = max(0.0, 100.0 - deviation * 8.0)

    # ── Stage score (30% if available) ─────────────────────────────────────
    if deep_pct is not None and rem_pct is not None and deep_pct >= 0 and rem_pct >= 0:
        deep_score = min(1.0, deep_pct / 0.20) * 50   # target 20% deep
        rem_score  = min(1.0, rem_pct  / 0.22) * 50   # target 22% REM
        stage_score  = min(100.0, deep_score + rem_score)
        stage_weight = 0.30
        dur_weight   = 0.40
    else:
        stage_score  = 0.0
        stage_weight = 0.0
        dur_weight   = 0.70   # redistribute stage weight to duration

    # ── Bedtime consistency score (30% if available) ───────────────────────
    if bedtime and recent_bedtimes and len(recent_bedtimes) >= 3:
        def _to_mins(t: str) -> Optional[int]:
            try:
                h, m = map(int, t.split(":"))
                return (h * 60 + m) % 1440
            except Exception:
                return None

        past_mins = [v for v in (_to_mins(t) for t in recent_bedtimes[-7:]) if v is not None]
        curr_mins = _to_mins(bedtime)
        if past_mins and curr_mins is not None:
            # Bedtimes lie on a 24h circle — use a circular mean/difference so that, e.g.,
            # 23:30 and 00:30 are 60 min apart rather than ~23h. The old linear math added
            # 1440 to pre-6am times and produced a large discontinuity for normal schedules
            # that cross midnight, unfairly tanking consistency scores (M11).
            angles = [m / 1440 * 2 * math.pi for m in past_mins]
            mean_angle = math.atan2(
                mean(math.sin(a) for a in angles),
                mean(math.cos(a) for a in angles),
            )
            curr_angle = curr_mins / 1440 * 2 * math.pi
            d = abs(curr_angle - mean_angle)
            d = min(d, 2 * math.pi - d)          # shortest arc around the clock
            diff = d / (2 * math.pi) * 1440       # back to minutes
            # ≤30 min diff = full score; every extra 30 min = −20 pts
            eff_score  = max(0.0, 100.0 - max(0.0, diff - 30) / 30 * 20)
            eff_weight = 0.30
        else:
            eff_score  = 0.0
            eff_weight = 0.0
            dur_weight += 0.30
    else:
        eff_score  = 0.0
        eff_weight = 0.0
        dur_weight += 0.30   # redistribute efficiency weight to duration

    score = (
        duration_score * dur_weight
        + stage_score  * stage_weight
        + eff_score    * eff_weight
    )
    return round(min(100.0, max(0.0, score)), 1)
