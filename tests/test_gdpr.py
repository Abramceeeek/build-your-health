"""GDPR export + delete (D3)."""
import asyncio

from backend.routers.users import export_my_data, delete_my_account
from backend.models.database import User, DailyTask


def test_export_then_delete(db):
    u = User(telegram_id=7, first_name="T")
    db.add(u)
    db.commit()
    uid = u.id
    db.add(DailyTask(user_id=uid, date="2026-06-20", section="m", task_key="k",
                     title="t", completed=False))
    db.commit()
    tg = {"id": 7, "first_name": "T", "last_name": "", "username": ""}

    exp = asyncio.run(export_my_data(tg, db))
    assert exp["users"][0]["telegram_id"] == 7
    assert len(exp["daily_tasks"]) == 1

    asyncio.run(delete_my_account(tg, db))
    db.expire_all()
    assert db.query(User).filter_by(telegram_id=7).first() is None
    assert db.query(DailyTask).filter_by(user_id=uid).count() == 0
