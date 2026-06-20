"""Service-layer "today" anchors follow the user's LOCAL calendar day, not UTC.

These complete the per-user timezone guarantee: the request handlers and scheduler
already bucket by local day (see test_timezone_wiring), and these lock the few
service-layer anchors that decide a *day* — cycle day-of-cycle, bio-age birthday,
deload "current week", and the AI-context "today" upper bound.

Each test freezes the clock at a UTC instant near a day/week boundary (via the
``user_local_now``/``user_today_str`` seam, using the real timezone conversion) so a
UTC anchor and a user-local anchor land on different calendar days, then asserts the
service used the local one. N-day lookback WINDOWS deliberately stay UTC and are not
asserted here.
"""
from datetime import datetime, timezone

from backend.models.database import User, CycleLog, VolumeLoadLog
from backend.services import (
    ai_context, bio_age_service, cycle_service, time_service, volume_service,
)


# 23:30 UTC on a Saturday: UTC is still 2026-06-20, but UTC+5:30 is already 2026-06-21.
_FROZEN_SAT = datetime(2026, 6, 20, 23, 30, tzinfo=timezone.utc)
# 23:30 UTC on a Sunday: UTC week is the 06-15 Monday; UTC+5:30 has rolled into 06-22.
_FROZEN_SUN = datetime(2026, 6, 21, 23, 30, tzinfo=timezone.utc)
IST = 330  # India, UTC+5:30 — far enough east to flip the day at this instant.


def _freeze(monkeypatch, module, attr, instant):
    """Pin a module's local-day helper to ``instant`` while keeping the real tz math."""
    monkeypatch.setattr(
        module, attr, lambda u: time_service.local_from_utc(instant, u)
    )


def test_cycle_day_of_cycle_anchors_on_user_local_day(db, monkeypatch):
    _freeze(monkeypatch, cycle_service, "user_local_now", _FROZEN_SAT)

    east = User(telegram_id=101, first_name="E", sex="female", timezone_offset=IST)
    utc = User(telegram_id=102, first_name="U", sex="female", timezone_offset=0)
    db.add_all([east, utc])
    db.commit()
    # Period started on the calendar day it is *locally* for the eastern user.
    for u in (east, utc):
        db.add(CycleLog(user_id=u.id, last_period_start="2026-06-21", cycle_length=28))
    db.commit()

    # East is already on 2026-06-21 -> day 1 (menstrual). A UTC anchor sees 2026-06-20,
    # one day *before* the period start, and wraps to day 28 (luteal) — the bug we fix.
    assert cycle_service.get_current_phase(east, db)["day_of_cycle"] == 1
    assert cycle_service.get_current_phase(utc, db)["day_of_cycle"] == 28


def test_bio_age_birthday_anchors_on_user_local_day(db, monkeypatch):
    _freeze(monkeypatch, bio_age_service, "user_local_now", _FROZEN_SAT)

    east = User(telegram_id=111, first_name="E", sex="male",
                date_of_birth="2000-06-21", timezone_offset=IST)
    utc = User(telegram_id=112, first_name="U", sex="male",
               date_of_birth="2000-06-21", timezone_offset=0)
    db.add_all([east, utc])
    db.commit()

    # East has rolled into their birthday (2026-06-21) -> 26; UTC is still 2026-06-20 -> 25.
    assert bio_age_service.compute_bio_age(east, db)["chronological_age"] == 26
    assert bio_age_service.compute_bio_age(utc, db)["chronological_age"] == 25


def test_deload_current_week_anchors_on_user_local_day(db, monkeypatch):
    _freeze(monkeypatch, volume_service, "user_local_now", _FROZEN_SUN)

    u = User(telegram_id=121, first_name="E", timezone_offset=IST)
    db.add(u)
    db.commit()
    # Three flat baseline weeks, then a spike in the local-Monday week (2026-06-22).
    for week_start, load in [("2026-06-01", 1000), ("2026-06-08", 1000),
                             ("2026-06-15", 1000), ("2026-06-22", 2000)]:
        db.add(VolumeLoadLog(user_id=u.id, week_start=week_start,
                             muscle_group="PUSH", total_load=load, session_count=1))
    db.commit()

    # With the user threaded, "current week" is 2026-06-22 (the spike) -> deload needed.
    assert volume_service.check_deload_needed(db, u.id, user=u) is True
    # Without it the anchor is UTC (week 2026-06-15, a flat 1000) -> no spike detected.
    assert volume_service.check_deload_needed(db, u.id) is False


def test_ai_context_today_anchor_uses_user_local_day(db, monkeypatch):
    # build_ai_context derives its "today" upper bound from user_today_str(user) before any
    # of its DB queries. (A full end-to-end assertion isn't practical here: a later, unrelated
    # task-stats query uses func.cast(..., type_=None), which is a pre-existing SQLite
    # incompatibility — so we tolerate that downstream crash and assert the anchor itself.)
    east = User(telegram_id=131, first_name="E", timezone_offset=IST)
    db.add(east)
    db.commit()

    captured = {}

    def anchor(u):
        captured["user_id"] = u.id
        captured["day"] = time_service.local_from_utc(_FROZEN_SAT, u).strftime("%Y-%m-%d")
        return captured["day"]

    monkeypatch.setattr(ai_context, "user_today_str", anchor)
    try:
        ai_context.build_ai_context(db, east.id)
    except Exception:
        pass  # downstream task-stats cast is SQLite-incompatible; irrelevant to the anchor

    # The anchor was threaded the real User and resolved to their LOCAL day (2026-06-21),
    # not the UTC day (2026-06-20) at this instant.
    assert captured["user_id"] == east.id
    assert captured["day"] == "2026-06-21"
