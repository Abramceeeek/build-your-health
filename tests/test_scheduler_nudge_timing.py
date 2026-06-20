"""Per-user-local daily nudge gating: fires at the user's local hour, once per local day,
and only marks a send after it actually happens (no silent miss on delivery failure)."""
from backend.models.database import User
from backend.services.scheduler import _due_now, _mark_sent
from backend.services.time_service import user_local_now

_next_tid = [1000]


def _user(db, offset):
    _next_tid[0] += 1
    u = User(telegram_id=_next_tid[0], first_name="T", timezone_offset=offset)
    db.add(u)
    db.commit()
    return u


def _local_hour(offset):
    return user_local_now(User(timezone_offset=offset)).hour


def test_due_at_local_target_hour(db):
    u = _user(db, 0)
    assert _due_now(u, "morning_reminders", _local_hour(0)) is True


def test_not_due_outside_target_hour(db):
    u = _user(db, 0)
    assert _due_now(u, "evening_gym_nudges", (_local_hour(0) + 3) % 24) is False


def test_mark_sent_dedupes_same_day(db):
    u = _user(db, 0)
    h = _local_hour(0)
    assert _due_now(u, "morning_reminders", h) is True
    _mark_sent(db, u, "morning_reminders")
    assert _due_now(u, "morning_reminders", h) is False  # already fired today


def test_due_now_does_not_record_until_marked(db):
    """A delivery failure (no _mark_sent) must NOT burn the day's slot."""
    u = _user(db, 0)
    h = _local_hour(0)
    assert _due_now(u, "morning_reminders", h) is True
    # simulate send failure: we never call _mark_sent
    assert _due_now(u, "morning_reminders", h) is True  # still due — no silent miss


def test_half_hour_offset_is_served(db):
    """Rebuts the 'non-whole-hour offsets never fire' claim: a UTC+5:30 user is due at their
    own local hour (they fire at :30 past the target hour, but they DO fire)."""
    u = _user(db, 330)  # UTC+5:30
    assert _due_now(u, "morning_reminders", _local_hour(330)) is True
    assert _due_now(u, "morning_reminders", (_local_hour(330) + 1) % 24) is False


def test_offset_shifts_which_hour_fires(db):
    u_east = _user(db, 60)   # one hour east
    u_utc = _user(db, 0)
    assert _due_now(u_east, "end_of_day_nudges", _local_hour(60)) is True
    # the east user is NOT due at the UTC user's local hour (one hour earlier)
    assert _due_now(u_east, "end_of_day_nudges", _local_hour(0)) is False


def test_distinct_jobs_independent(db):
    u = _user(db, 0)
    h = _local_hour(0)
    assert _due_now(u, "morning_reminders", h) is True
    _mark_sent(db, u, "morning_reminders")
    assert _due_now(u, "retention_milestones", h) is True  # separate key still due


def test_mark_sent_persists(db):
    u = _user(db, 0)
    _mark_sent(db, u, "morning_reminders")
    fetched = db.query(User).filter(User.id == u.id).first()
    assert "morning_reminders" in (fetched.nudge_log_json or {})
