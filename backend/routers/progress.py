from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone, timedelta

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import (
    User, DailyTask, Achievement, HabitTracker, CompetitionMember,
    Badge, UserBadge,
)
from backend.models.schemas import AchievementResponse, HabitCreate, HabitResponse
from backend.services.badge_service import check_and_award_badges

router = APIRouter(prefix="/api/progress", tags=["progress"])

TIER_THRESHOLDS = [
    (0, "Bronze"),
    (500, "Silver"),
    (1500, "Gold"),
    (3500, "Opal"),
    (7000, "Diamond"),
    (15000, "Champion"),
]

ACHIEVEMENTS = {
    "first_task": {"title": "First Step", "desc": "Complete your first task", "icon": "🌱", "check": lambda s: s["total_completed"] >= 1},
    "ten_tasks": {"title": "Getting Serious", "desc": "Complete 10 tasks", "icon": "💪", "check": lambda s: s["total_completed"] >= 10},
    "fifty_tasks": {"title": "Half Century", "desc": "Complete 50 tasks", "icon": "🔥", "check": lambda s: s["total_completed"] >= 50},
    "hundred_tasks": {"title": "Centurion", "desc": "Complete 100 tasks", "icon": "⚡", "check": lambda s: s["total_completed"] >= 100},
    "five_hundred_tasks": {"title": "Machine", "desc": "Complete 500 tasks", "icon": "🤖", "check": lambda s: s["total_completed"] >= 500},
    "streak_3": {"title": "Warming Up", "desc": "3-day streak", "icon": "🔥", "check": lambda s: s["streak"] >= 3},
    "streak_7": {"title": "One Week Strong", "desc": "7-day streak", "icon": "🗓️", "check": lambda s: s["streak"] >= 7},
    "streak_14": {"title": "Two Weeks In", "desc": "14-day streak", "icon": "⚡", "check": lambda s: s["streak"] >= 14},
    "streak_30": {"title": "Monthly Beast", "desc": "30-day streak", "icon": "🏆", "check": lambda s: s["streak"] >= 30},
    "streak_100": {"title": "Legendary", "desc": "100-day streak", "icon": "👑", "check": lambda s: s["streak"] >= 100},
    "perfect_day": {"title": "Perfect Day", "desc": "Complete all tasks in a day", "icon": "✨", "check": lambda s: s["perfect_days"] >= 1},
    "perfect_week": {"title": "Perfect Week", "desc": "7 perfect days in a row", "icon": "💎", "check": lambda s: s["perfect_days"] >= 7},
    "level_5": {"title": "Rising Star", "desc": "Reach level 5", "icon": "⭐", "check": lambda s: s["level"] >= 5},
    "level_10": {"title": "Dedicated", "desc": "Reach level 10", "icon": "🌟", "check": lambda s: s["level"] >= 10},
    "level_25": {"title": "Elite", "desc": "Reach level 25", "icon": "💫", "check": lambda s: s["level"] >= 25},
    "joined_competition": {"title": "Competitor", "desc": "Join your first competition", "icon": "🏅", "check": lambda s: s["competitions"] >= 1},
}


def calculate_level(xp: int) -> int:
    return max(1, int((xp / 100) ** 0.7) + 1)


def calculate_tier(xp: int) -> str:
    tier = "Bronze"
    for threshold, name in TIER_THRESHOLDS:
        if xp >= threshold:
            tier = name
    return tier


def calculate_ovr(user: User, db: Session) -> float:
    today = datetime.now(timezone.utc)
    thirty_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    tasks_30d = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= thirty_days_ago,
    ).all()

    if not tasks_30d:
        return 0.0

    completed = sum(1 for t in tasks_30d if t.completed)
    total = len(tasks_30d)
    completion_rate = completed / total if total else 0

    streak_factor = min(user.streak_days / 30, 1.0)
    level_factor = min(user.level / 50, 1.0)
    consistency_factor = completion_rate

    ovr = (completion_rate * 50 + streak_factor * 25 + level_factor * 15 + consistency_factor * 10)
    return round(min(99, max(0, ovr)), 1)


@router.post("/update-streak")
async def update_streak(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    today_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == today
    ).all()
    today_done = sum(1 for t in today_tasks if t.completed)
    today_total = len(today_tasks)
    today_pct = (today_done / today_total * 100) if today_total else 0

    if user.last_active_date == today:
        pass
    elif user.last_active_date == yesterday and today_pct >= 50:
        user.streak_days += 1
        user.last_active_date = today
    elif user.last_active_date != yesterday and today_pct >= 50:
        if user.streak_freezes > 0:
            two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
            if user.last_active_date == two_days_ago:
                user.streak_freezes -= 1
                user.streak_days += 1
            else:
                user.streak_days = 1
        else:
            user.streak_days = 1
        user.last_active_date = today
    elif today_pct >= 50 and not user.last_active_date:
        user.streak_days = 1
        user.last_active_date = today

    user.longest_streak = max(user.longest_streak, user.streak_days)
    user.level = calculate_level(user.xp)
    user.tier = calculate_tier(user.xp)
    user.ovr_rating = calculate_ovr(user, db)

    db.commit()

    _check_achievements(db, user)
    new_badges = check_and_award_badges(db, user)

    return {
        "streak_days": user.streak_days,
        "longest_streak": user.longest_streak,
        "xp": user.xp,
        "level": user.level,
        "tier": user.tier,
        "ovr_rating": user.ovr_rating,
        "new_badges": new_badges,
    }


def _perfect_day_streak(db: Session, user: User, lookback_days: int = 120) -> int:
    """Longest run of consecutive calendar days on which every task was completed.

    A "perfect day" = a day with >=1 task where all tasks are done. Returns the max
    consecutive run within the lookback window. Previously this was hardcoded to 0/1 for
    *today only*, which made the 7-in-a-row "Perfect Week" achievement impossible (H7).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    rows = db.query(DailyTask.date, DailyTask.completed).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= cutoff,
    ).all()
    by_day: dict[str, list[int]] = {}
    for d, completed in rows:
        agg = by_day.setdefault(d, [0, 0])  # [done, total]
        agg[1] += 1
        if completed:
            agg[0] += 1
    perfect = sorted(
        date.fromisoformat(d) for d, (done, total) in by_day.items()
        if total > 0 and done == total
    )
    if not perfect:
        return 0
    max_run = run = 1
    for i in range(1, len(perfect)):
        if (perfect[i] - perfect[i - 1]).days == 1:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    return max_run


def _check_achievements(db: Session, user: User):
    existing = {a.achievement_type for a in db.query(Achievement).filter(
        Achievement.user_id == user.id
    ).all()}

    total_completed = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.completed == True
    ).count()

    perfect_days = _perfect_day_streak(db, user)

    comp_count = db.query(CompetitionMember).filter(
        CompetitionMember.user_id == user.id
    ).count()

    stats = {
        "total_completed": total_completed,
        "streak": user.streak_days,
        "perfect_days": perfect_days,
        "level": user.level,
        "competitions": comp_count,
    }

    for ach_type, ach_def in ACHIEVEMENTS.items():
        if ach_type not in existing and ach_def["check"](stats):
            new_ach = Achievement(
                user_id=user.id,
                achievement_type=ach_type,
                title=ach_def["title"],
                description=ach_def["desc"],
                icon=ach_def["icon"],
            )
            db.add(new_ach)

    db.commit()


@router.get("/achievements", response_model=list[AchievementResponse])
async def get_achievements(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user.id
    ).order_by(Achievement.unlocked_at.desc()).all()
    return achievements


@router.post("/habits", response_model=HabitResponse)
async def create_habit(
    req: HabitCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    habit = HabitTracker(
        user_id=user.id,
        habit_name=req.habit_name,
        quit_date=req.quit_date,
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)

    today = datetime.now(timezone.utc).date()
    quit = datetime.strptime(habit.quit_date, "%Y-%m-%d").date()
    days_since = (today - quit).days

    return HabitResponse(
        id=habit.id,
        habit_name=habit.habit_name,
        quit_date=habit.quit_date,
        is_active=habit.is_active,
        days_since=max(0, days_since),
    )


@router.get("/habits", response_model=list[HabitResponse])
async def get_habits(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    habits = db.query(HabitTracker).filter(
        HabitTracker.user_id == user.id,
        HabitTracker.is_active == True,
    ).all()

    today = datetime.now(timezone.utc).date()
    results = []
    for h in habits:
        quit = datetime.strptime(h.quit_date, "%Y-%m-%d").date()
        days_since = (today - quit).days
        results.append(HabitResponse(
            id=h.id,
            habit_name=h.habit_name,
            quit_date=h.quit_date,
            is_active=h.is_active,
            days_since=max(0, days_since),
        ))
    return results


@router.delete("/habits/{habit_id}")
async def delete_habit(
    habit_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    habit = db.query(HabitTracker).filter(
        HabitTracker.id == habit_id,
        HabitTracker.user_id == user.id,
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    habit.is_active = False
    db.commit()
    return {"message": "Habit deactivated"}


@router.get("/dashboard")
async def get_dashboard(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")

    today_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == today_str
    ).all()

    categories = {"health": {"done": 0, "total": 0}, "fitness": {"done": 0, "total": 0},
                   "sleep": {"done": 0, "total": 0}, "face": {"done": 0, "total": 0}}
    for t in today_tasks:
        cat = t.category if t.category in categories else "health"
        categories[cat]["total"] += 1
        if t.completed:
            categories[cat]["done"] += 1

    rings = {}
    for cat, data in categories.items():
        rings[cat] = round(data["done"] / data["total"] * 100) if data["total"] else 0

    week_data = []
    monday = today - timedelta(days=today.weekday())
    for i in range(7):
        day_date = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        tasks = db.query(DailyTask).filter(
            DailyTask.user_id == user.id, DailyTask.date == day_date
        ).all()
        done = sum(1 for t in tasks if t.completed)
        total = len(tasks)
        week_data.append({
            "date": day_date,
            "done": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
        })

    habits = db.query(HabitTracker).filter(
        HabitTracker.user_id == user.id, HabitTracker.is_active == True
    ).all()
    habit_data = []
    for h in habits:
        quit = datetime.strptime(h.quit_date, "%Y-%m-%d").date()
        days = (today.date() - quit).days
        habit_data.append({"name": h.habit_name, "days_since": max(0, days)})

    return {
        "user": {
            "first_name": user.first_name,
            "ovr_rating": user.ovr_rating,
            "xp": user.xp,
            "level": user.level,
            "tier": user.tier,
            "streak_days": user.streak_days,
        },
        "rings": rings,
        "today": {
            "done": sum(1 for t in today_tasks if t.completed),
            "total": len(today_tasks),
            "pct": round(sum(1 for t in today_tasks if t.completed) / len(today_tasks) * 100) if today_tasks else 0,
        },
        "week": week_data,
        "habits": habit_data,
    }


@router.get("/badges")
async def get_badges(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all badges with unlock status for the current user."""
    user = get_or_create_user(db, tg_user)

    all_badges = db.query(Badge).all()
    user_badge_ids = {ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == user.id).all()}

    result = []
    for b in all_badges:
        result.append({
            "id": b.id,
            "badge_key": b.badge_key,
            "name": b.name,
            "description": b.description,
            "requirement_text": b.description,
            "icon": b.icon,
            "category": b.category,
            "rarity": b.rarity,
            "ovr_bonus": b.ovr_bonus,
            "unlocked": b.id in user_badge_ids,
        })

    # Sort: unlocked first, then by category
    result.sort(key=lambda x: (not x["unlocked"], x["category"], x["name"]))
    unlocked_count = sum(1 for b in result if b["unlocked"])

    return {
        "badges": result,
        "unlocked": unlocked_count,
        "total": len(result),
    }
