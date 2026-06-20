"""Referral loop: reward stacks, register attributes + rewards both (P4.3)."""
import asyncio

from fastapi import BackgroundTasks

from backend.routers.users import register_user
from backend.routers.subscriptions import grant_referral_reward
from backend.models.database import User, Subscription
from backend.models.schemas import RegistrationRequest


def test_grant_referral_reward_stacks(db):
    u = User(telegram_id=1, first_name="T")
    db.add(u)
    db.commit()
    grant_referral_reward(db, u.id, days=7)
    sub = db.query(Subscription).filter_by(user_id=u.id).first()
    assert sub.status == "trialing"
    end1 = sub.trial_ends_at
    grant_referral_reward(db, u.id, days=7)
    db.refresh(sub)
    assert sub.trial_ends_at > end1  # stacked, not reset


def test_register_with_referral_rewards_both(db):
    ref = User(telegram_id=100, first_name="Ref", is_registered=True)
    db.add(ref)
    db.commit()

    data = RegistrationRequest(referred_by=ref.id, gender="male")
    tg = {"id": 200, "first_name": "New", "last_name": "", "username": ""}
    asyncio.run(register_user(data, BackgroundTasks(), tg, db))

    referee = db.query(User).filter_by(telegram_id=200).first()
    assert referee.referred_by == ref.id
    assert db.query(Subscription).filter_by(user_id=ref.id).first().status == "trialing"
    assert db.query(Subscription).filter_by(user_id=referee.id).first().status == "trialing"
