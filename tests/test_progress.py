"""Achievements: real consecutive perfect-day streak (H7)."""
from datetime import datetime, timezone, timedelta

from backend.models.database import User, DailyTask
from backend.routers.progress import _perfect_day_streak


def _d(offset):
    return (datetime.now(timezone.utc) - timedelta(days=offset)).strftime("%Y-%m-%d")


def _add_day(db, user, date_str, done, total):
    for i in range(total):
        db.add(DailyTask(user_id=user.id, date=date_str, section="main",
                         task_key=f"k{i}", title=f"t{i}", completed=(i < done)))


def test_perfect_day_streak_finds_longest_run(db):
    u = User(telegram_id=1, first_name="T")
    db.add(u)
    db.commit()
    _add_day(db, u, _d(6), 2, 2)   # perfect
    _add_day(db, u, _d(5), 2, 2)   # perfect (run=2 with day6)
    _add_day(db, u, _d(4), 1, 2)   # NOT perfect -> breaks run
    _add_day(db, u, _d(3), 3, 3)   # perfect
    _add_day(db, u, _d(2), 1, 1)   # perfect
    _add_day(db, u, _d(1), 2, 2)   # perfect
    _add_day(db, u, _d(0), 2, 2)   # perfect -> run of 4 (days 3,2,1,0)
    db.commit()
    assert _perfect_day_streak(db, u) == 4


def test_perfect_week_now_obtainable(db):
    u = User(telegram_id=2, first_name="T")
    db.add(u)
    db.commit()
    for off in range(7):  # 7 perfect days in a row
        _add_day(db, u, _d(off), 2, 2)
    db.commit()
    assert _perfect_day_streak(db, u) >= 7  # was permanently stuck at <=1 before the fix


def test_no_tasks_zero_streak(db):
    u = User(telegram_id=3, first_name="T")
    db.add(u)
    db.commit()
    assert _perfect_day_streak(db, u) == 0
