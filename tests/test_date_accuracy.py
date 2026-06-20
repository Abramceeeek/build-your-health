"""Calendar-math accuracy: week boundaries, weekday mapping, calendar-month walk.

These lock the day/streak/heatmap arithmetic that drives "every day is accurate".
The app computes all dates in UTC (no per-user timezone yet — that's the D4 gap),
so the real correctness risk is the calendar arithmetic itself: Monday-of-week,
weekday index, and stepping months without drift across year boundaries (M13).
"""
from datetime import date, datetime, timedelta

import pytest

from backend.routers.tasks import _day_index_for_date
from backend.routers.heatmap import _recent_months
from backend.services.volume_service import _week_start


# --- _day_index_for_date: Monday=0 .. Sunday=6 -------------------------------

@pytest.mark.parametrize("date_str,expected", [
    ("2026-06-15", 0),  # Monday
    ("2026-06-16", 1),
    ("2026-06-17", 2),
    ("2026-06-18", 3),
    ("2026-06-19", 4),
    ("2026-06-20", 5),
    ("2026-06-21", 6),  # Sunday
])
def test_day_index_known_dates(date_str, expected):
    assert _day_index_for_date(date_str) == expected


# --- _week_start: Monday of the containing week -------------------------------

@pytest.mark.parametrize("date_str,expected", [
    ("2026-06-15", "2026-06-15"),  # Monday -> itself
    ("2026-06-21", "2026-06-15"),  # Sunday -> that Monday
    ("2026-01-01", "2025-12-29"),  # Thu, week starts in the prior year
    ("2025-12-31", "2025-12-29"),  # Wed, across year boundary
    ("2024-03-01", "2024-02-26"),  # leap-year Feb->Mar boundary
])
def test_week_start_value(date_str, expected):
    assert _week_start(date_str) == expected


def test_week_start_lands_on_monday_for_every_day_of_a_year():
    d = date(2025, 1, 1)
    for _ in range(366):
        ws = _week_start(d.strftime("%Y-%m-%d"))
        assert datetime.strptime(ws, "%Y-%m-%d").weekday() == 0
        d += timedelta(days=1)


def test_week_start_is_idempotent():
    for date_str in ("2026-06-18", "2026-01-01", "2025-12-31"):
        once = _week_start(date_str)
        assert _week_start(once) == once


# --- _recent_months: N calendar months, newest first, no drift ----------------

def test_recent_months_within_one_year():
    assert _recent_months(2026, 6, 3) == ["2026-06", "2026-05", "2026-04"]


def test_recent_months_rolls_over_year_boundary():
    assert _recent_months(2026, 2, 4) == ["2026-02", "2026-01", "2025-12", "2025-11"]


def test_recent_months_january_rollover():
    assert _recent_months(2026, 1, 2) == ["2026-01", "2025-12"]


@pytest.mark.parametrize("n", [1, 6, 12, 14, 25])
def test_recent_months_consecutive_no_gaps_no_dupes(n):
    months = _recent_months(2026, 6, n)
    assert len(months) == n
    assert len(set(months)) == n  # no duplicates
    # strictly one calendar month apart, descending
    for newer, older in zip(months, months[1:]):
        ny, nm = map(int, newer.split("-"))
        oy, om = map(int, older.split("-"))
        gap = (ny - oy) * 12 + (nm - om)
        assert gap == 1, f"{newer}->{older} is {gap} months apart"
