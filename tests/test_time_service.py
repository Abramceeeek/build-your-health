"""Per-user local time helper: offset handling, day flips, UTC-default invariance."""
from datetime import datetime, timezone, timedelta

import pytest

from backend.models.database import User
from backend.services.time_service import (
    _offset_minutes, local_from_utc, user_day_start_utc, user_local_now,
    user_today_str, user_tz,
)


def _user(offset):
    return User(telegram_id=1, first_name="T", timezone_offset=offset)


# --- offset normalization -----------------------------------------------------

def test_offset_none_and_missing_default_to_zero():
    assert _offset_minutes(None) == 0
    assert _offset_minutes(User(telegram_id=1, first_name="T", timezone_offset=None)) == 0


def test_offset_accepts_bare_int():
    assert _offset_minutes(120) == 120


@pytest.mark.parametrize("off,expected", [
    (-13 * 60, -12 * 60),   # clamp below UTC-12
    (15 * 60, 14 * 60),     # clamp above UTC+14
    (330, 330),             # India +5:30 unchanged
])
def test_offset_clamped_to_civil_range(off, expected):
    assert _offset_minutes(off) == expected


def test_user_tz_matches_offset():
    assert user_tz(_user(330)).utcoffset(None) == timedelta(minutes=330)


# --- pure conversion / day flips ----------------------------------------------

def test_offset_zero_equals_utc_date():
    instant = datetime(2026, 6, 20, 23, 30, tzinfo=timezone.utc)
    assert local_from_utc(instant, _user(0)).strftime("%Y-%m-%d") == "2026-06-20"


def test_positive_offset_flips_to_next_day():
    # 23:30 UTC + 60 min -> 00:30 next local day
    instant = datetime(2026, 6, 20, 23, 30, tzinfo=timezone.utc)
    local = local_from_utc(instant, _user(60))
    assert local.strftime("%Y-%m-%d") == "2026-06-21"
    assert local.hour == 0 and local.minute == 30


def test_negative_offset_flips_to_previous_day():
    # 00:30 UTC - 60 min -> 23:30 previous local day
    instant = datetime(2026, 6, 20, 0, 30, tzinfo=timezone.utc)
    local = local_from_utc(instant, _user(-60))
    assert local.strftime("%Y-%m-%d") == "2026-06-19"
    assert local.hour == 23 and local.minute == 30


def test_far_east_and_far_west_can_differ_by_a_day():
    instant = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    east = local_from_utc(instant, _user(14 * 60)).date()
    west = local_from_utc(instant, _user(-12 * 60)).date()
    assert (east - west).days in (0, 1)
    assert east >= west


def test_naive_utc_input_is_treated_as_utc():
    naive = datetime(2026, 6, 20, 23, 30)  # no tzinfo
    assert local_from_utc(naive, _user(60)).strftime("%Y-%m-%d") == "2026-06-21"


# --- live helpers agree with UTC at offset 0 ----------------------------------

def test_user_today_str_offset_zero_matches_utc_now():
    assert user_today_str(_user(0)) == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_user_local_now_is_aware_and_supports_weekday():
    now = user_local_now(_user(330))
    assert now.tzinfo is not None
    assert 0 <= now.weekday() <= 6


# --- user_day_start_utc: naive UTC start of the user's local day --------------

def test_day_start_is_naive_utc():
    start = user_day_start_utc(_user(330))
    assert start.tzinfo is None  # comparable against stored naive-UTC timestamps


def test_day_start_offset_zero_is_utc_midnight_today():
    start = user_day_start_utc(_user(0))
    assert start.strftime("%Y-%m-%d") == datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)


@pytest.mark.parametrize("offset", [-12 * 60, -330, 0, 60, 330, 14 * 60])
def test_day_start_maps_back_to_local_midnight(offset):
    user = _user(offset)
    start = user_day_start_utc(user)            # naive UTC instant
    local = local_from_utc(start, user)         # naive treated as UTC, back to local
    assert local.strftime("%Y-%m-%d") == user_today_str(user)
    assert (local.hour, local.minute, local.second) == (0, 0, 0)


def test_day_start_is_at_or_before_now_and_within_a_day():
    # The local day always started in the last 24h, so its UTC instant is in (now-24h, now].
    user = _user(330)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = user_day_start_utc(user)
    assert now - timedelta(days=1) < start <= now
