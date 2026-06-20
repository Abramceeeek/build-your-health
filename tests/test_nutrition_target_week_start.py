"""Regression: a NutritionTarget created at registration must be keyed by the
Monday of the user's current week.

The target used to be stored under *today's* date (`user_today_str`). Stats/targets
lookups key by the Monday of the week (via `volume_service._week_start`), so a target
created on any non-Monday landed under the wrong key and was silently invisible —
producing missing/stale nutrition targets mid-week. This locks the Monday keying.
"""
import asyncio
from datetime import datetime

from fastapi import BackgroundTasks

from backend.routers.users import register_user
from backend.models.database import User, NutritionTarget
from backend.models.schemas import RegistrationRequest
from backend.services.time_service import user_today_str
from backend.services.volume_service import _week_start


def test_register_keys_nutrition_target_by_monday(db):
    # height + weight present → the personalised NutritionTarget row is created.
    data = RegistrationRequest(
        gender="male", height_cm=180, weight_kg=80, age=30,
        goals=["build_muscle"], gym_days_per_week=4,
    )
    tg = {"id": 300, "first_name": "Mid", "last_name": "", "username": ""}
    asyncio.run(register_user(data, BackgroundTasks(), tg, db))

    user = db.query(User).filter_by(telegram_id=300).first()
    target = db.query(NutritionTarget).filter_by(user_id=user.id).first()
    assert target is not None, "registration should create a NutritionTarget"

    # The stored key must be the Monday of the user's current local week...
    expected_monday = _week_start(user_today_str(user))
    assert target.week_start == expected_monday
    # ...which, by definition, is always a Monday (weekday() == 0).
    assert datetime.strptime(target.week_start, "%Y-%m-%d").weekday() == 0

    # And the Monday-keyed lookup that stats performs must find the row — the exact
    # path that silently returned nothing when the target was keyed by a mid-week day.
    found = db.query(NutritionTarget).filter(
        NutritionTarget.user_id == user.id,
        NutritionTarget.week_start == _week_start(user_today_str(user)),
    ).first()
    assert found is not None
