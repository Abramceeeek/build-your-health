"""Sleep bedtime consistency uses circular stats across midnight (M11)."""
from backend.services.sleep_service import calculate_sleep_score


def test_consistent_late_sleeper_not_penalized():
    s = calculate_sleep_score(8.0, deep_pct=0.20, rem_pct=0.22, bedtime="01:00",
                              recent_bedtimes=["01:00", "01:05", "00:55", "01:00"])
    assert s >= 95  # a regular 1am sleeper is consistent, not "inconsistent"


def test_midnight_crossing_uses_short_arc():
    # mean bedtime ~23:30; tonight 00:30 is 60 min later, not ~23h apart.
    close = calculate_sleep_score(8.0, deep_pct=0.20, rem_pct=0.22, bedtime="00:30",
                                  recent_bedtimes=["23:30", "23:30", "23:30"])
    far = calculate_sleep_score(8.0, deep_pct=0.20, rem_pct=0.22, bedtime="12:00",
                                recent_bedtimes=["23:30", "23:30", "23:30"])
    assert close > far          # crossing midnight is NOT treated as maximally inconsistent
    assert close >= 90          # 60 min off -> only a small penalty


def test_zero_hours_is_zero():
    assert calculate_sleep_score(0) == 0.0
