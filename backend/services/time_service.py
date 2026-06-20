"""Per-user local time.

The app stores all timestamps in UTC, but a person's "today", streak rollover, heatmap
day, and morning reminder must follow THEIR calendar day. `User.timezone_offset` is minutes
east of UTC (default 0 = UTC, so existing UTC behavior is preserved exactly until a user sets
a zone). These helpers convert UTC "now" into the user's local wall-clock.

Use `user_local_now(user)` anywhere code currently does `datetime.now(timezone.utc)` to decide
a calendar day for that user; keep UTC for audit timestamps, TTLs, and N-day lookback windows.
"""
from datetime import datetime, timedelta, timezone


def _offset_minutes(user) -> int:
    """timezone_offset for a User (or a bare int/None), clamped to a sane range."""
    if user is None:
        return 0
    off = user if isinstance(user, int) else getattr(user, "timezone_offset", 0)
    if off is None:
        return 0
    # UTC-12:00 .. UTC+14:00 — the real-world span of civil offsets.
    return max(-12 * 60, min(14 * 60, int(off)))


def user_tz(user) -> timezone:
    return timezone(timedelta(minutes=_offset_minutes(user)))


def local_from_utc(now_utc: datetime, user) -> datetime:
    """Pure core: convert a UTC instant to the user's local wall-clock (aware)."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(user_tz(user))


def user_local_now(user) -> datetime:
    """Current instant as a timezone-aware datetime in the user's local offset.

    Supports `.weekday()`, `.strftime("%Y-%m-%d")`, and date arithmetic, so it is a drop-in
    for `datetime.now(timezone.utc)` at any per-user day-boundary computation.
    """
    return local_from_utc(datetime.now(timezone.utc), user)


def user_today_str(user) -> str:
    """The user's local calendar day as 'YYYY-MM-DD'."""
    return user_local_now(user).strftime("%Y-%m-%d")


def user_day_start_utc(user) -> datetime:
    """The UTC instant marking the start of the user's local calendar day.

    Returned as a *naive* UTC datetime (tzinfo stripped) so it compares directly against
    stored timestamps, which are persisted as naive UTC wall-clock (see models.database.utcnow).
    Use this to bucket rows by the user's local day, e.g.
    `Row.created_at >= user_day_start_utc(user)`.
    """
    local_midnight = user_local_now(user).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
