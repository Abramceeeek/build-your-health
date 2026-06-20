"""finish_session idempotency — no double XP / calories on repeat submit (H13)."""
import asyncio

from backend.routers.exercise_sessions import finish_session, SessionFinish
from backend.models.database import User, ExerciseSession, DailyTask, DailyHealthLog


def test_finish_session_is_idempotent(db):
    u = User(telegram_id=99, first_name="T", xp=0)
    db.add(u)
    db.commit()
    task = DailyTask(user_id=u.id, date="2026-06-20", section="main", task_key="k",
                     title="Bench", completed=False, xp_reward=10)
    db.add(task)
    db.commit()
    sess = ExerciseSession(user_id=u.id, task_id=task.id, exercise_name="Bench Press",
                           date="2026-06-20")
    db.add(sess)
    db.commit()

    tg = {"id": 99, "first_name": "T", "last_name": "", "username": ""}
    data = SessionFinish(sets_log=[], total_duration_s=600, rest_seconds_total=120)

    r1 = asyncio.run(finish_session(sess.id, data, tg, db))
    r2 = asyncio.run(finish_session(sess.id, data, tg, db))

    db.refresh(u)
    assert r1["status"] == "completed"
    assert r2["status"] == "already_completed"
    assert r2["xp_earned"] == 0
    assert u.xp == 10  # awarded exactly once

    hl = db.query(DailyHealthLog).filter(
        DailyHealthLog.user_id == u.id, DailyHealthLog.date == "2026-06-20"
    ).first()
    assert hl is not None
    assert hl.exercise_calories == int(r1["calories_burned"])  # calories added once, not twice
