"""Badge seed data and badge-checking logic."""

from sqlalchemy.orm import Session
from backend.models.database import Badge, UserBadge, User, DailyTask

SEED_BADGES = [
    # Streak badges
    {"badge_key": "streak_3", "name": "3-Day Streak", "description": "Complete tasks 3 days in a row", "icon": "🔥", "category": "streak", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "streak_7", "name": "Week Warrior", "description": "7-day streak", "icon": "🔥", "category": "streak", "rarity": "common", "ovr_bonus": 0.2},
    {"badge_key": "streak_14", "name": "Fortnight Force", "description": "14-day streak", "icon": "🔥", "category": "streak", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "streak_30", "name": "30-Day Beast", "description": "30-day streak", "icon": "🔥", "category": "streak", "rarity": "epic", "ovr_bonus": 0.5},
    {"badge_key": "streak_60", "name": "Iron Discipline", "description": "60-day streak", "icon": "💎", "category": "streak", "rarity": "epic", "ovr_bonus": 0.8},
    {"badge_key": "streak_100", "name": "Centurion", "description": "100-day streak", "icon": "👑", "category": "streak", "rarity": "legendary", "ovr_bonus": 1.0},

    # Completion badges
    {"badge_key": "tasks_1", "name": "First Step", "description": "Complete your first task", "icon": "✅", "category": "completion", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "tasks_10", "name": "Getting Going", "description": "Complete 10 tasks", "icon": "✅", "category": "completion", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "tasks_50", "name": "Half Century", "description": "Complete 50 tasks", "icon": "🎯", "category": "completion", "rarity": "common", "ovr_bonus": 0.2},
    {"badge_key": "tasks_100", "name": "Century Club", "description": "Complete 100 tasks", "icon": "🎯", "category": "completion", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "tasks_500", "name": "Task Machine", "description": "Complete 500 tasks", "icon": "⚡", "category": "completion", "rarity": "epic", "ovr_bonus": 0.5},
    {"badge_key": "tasks_1000", "name": "Unstoppable", "description": "Complete 1000 tasks", "icon": "💫", "category": "completion", "rarity": "legendary", "ovr_bonus": 1.0},

    # Perfect badges
    {"badge_key": "perfect_day", "name": "Perfect Day", "description": "Complete every task in a day", "icon": "⭐", "category": "perfect", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "perfect_week", "name": "Perfect Week", "description": "Complete every task for 7 consecutive days", "icon": "🌟", "category": "perfect", "rarity": "epic", "ovr_bonus": 0.5},

    # Competition badges
    {"badge_key": "comp_first", "name": "Challenger", "description": "Join your first competition", "icon": "⚔️", "category": "competition", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "comp_win", "name": "Victor", "description": "Win a competition", "icon": "🏆", "category": "competition", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "comp_win5", "name": "Champion", "description": "Win 5 competitions", "icon": "👑", "category": "competition", "rarity": "epic", "ovr_bonus": 0.5},

    # Nutrition badges
    {"badge_key": "nutrition_first", "name": "First Bite", "description": "Log your first food", "icon": "🍎", "category": "nutrition", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "nutrition_streak7", "name": "Meal Prepper", "description": "Log food 7 days in a row", "icon": "🥗", "category": "nutrition", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "nutrition_macros", "name": "Macro Master", "description": "Hit all macro targets in a day", "icon": "💪", "category": "nutrition", "rarity": "epic", "ovr_bonus": 0.5},

    # Strength badges
    {"badge_key": "weight_first", "name": "Iron Starter", "description": "Log your first weight", "icon": "🏋️", "category": "strength", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "weight_10pct", "name": "Progressive Overload", "description": "Increase weight by 10% on any exercise", "icon": "📈", "category": "strength", "rarity": "rare", "ovr_bonus": 0.3},
    {"badge_key": "weight_25pct", "name": "Strength Surge", "description": "Increase weight by 25% on any exercise", "icon": "🚀", "category": "strength", "rarity": "epic", "ovr_bonus": 0.5},

    # Level badges
    {"badge_key": "level_5", "name": "Rising Star", "description": "Reach Level 5", "icon": "⬆️", "category": "level", "rarity": "common", "ovr_bonus": 0.1},
    {"badge_key": "level_10", "name": "Dedicated", "description": "Reach Level 10", "icon": "🔶", "category": "level", "rarity": "rare", "ovr_bonus": 0.2},
    {"badge_key": "level_25", "name": "Veteran", "description": "Reach Level 25", "icon": "💎", "category": "level", "rarity": "epic", "ovr_bonus": 0.5},
    {"badge_key": "level_50", "name": "Legend", "description": "Reach Level 50", "icon": "👑", "category": "level", "rarity": "legendary", "ovr_bonus": 1.0},

    # Retention milestone badges (3-week cliff strategy)
    {"badge_key": "milestone_week1", "name": "First Week Done", "description": "Complete 7 days on the platform", "icon": "📅", "category": "milestone", "rarity": "common", "ovr_bonus": 0.2},
    {"badge_key": "milestone_3weeks", "name": "3-Week Warrior", "description": "Survived the 3-week cliff — you're in the top 20%", "icon": "⚔️", "category": "milestone", "rarity": "epic", "ovr_bonus": 0.5},
    {"badge_key": "milestone_2months", "name": "Two Month Titan", "description": "60 days of transformation — this is your lifestyle now", "icon": "🏛️", "category": "milestone", "rarity": "legendary", "ovr_bonus": 1.0},
]


def seed_badges(db: Session):
    """Seed badge definitions if empty."""
    if db.query(Badge).count() > 0:
        return
    for b in SEED_BADGES:
        db.add(Badge(**b))
    db.commit()


def check_and_award_badges(db: Session, user: User) -> list[dict]:
    """Check which badges the user qualifies for and award new ones. Returns newly awarded badges."""
    existing = {ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == user.id).all()}
    all_badges = {b.badge_key: b for b in db.query(Badge).all()}
    newly_awarded = []

    total_completed = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.completed == True,
    ).count()

    def try_award(key):
        badge = all_badges.get(key)
        if badge and badge.id not in existing:
            db.add(UserBadge(user_id=user.id, badge_id=badge.id))
            existing.add(badge.id)
            newly_awarded.append({"name": badge.name, "icon": badge.icon, "rarity": badge.rarity})

    # Streak badges
    if user.streak_days >= 3: try_award("streak_3")
    if user.streak_days >= 7: try_award("streak_7")
    if user.streak_days >= 14: try_award("streak_14")
    if user.streak_days >= 30: try_award("streak_30")
    if user.streak_days >= 60: try_award("streak_60")
    if user.streak_days >= 100: try_award("streak_100")

    # Completion badges
    if total_completed >= 1: try_award("tasks_1")
    if total_completed >= 10: try_award("tasks_10")
    if total_completed >= 50: try_award("tasks_50")
    if total_completed >= 100: try_award("tasks_100")
    if total_completed >= 500: try_award("tasks_500")
    if total_completed >= 1000: try_award("tasks_1000")

    # Level badges
    if user.level >= 5: try_award("level_5")
    if user.level >= 10: try_award("level_10")
    if user.level >= 25: try_award("level_25")
    if user.level >= 50: try_award("level_50")

    # Retention milestone badges (3-week cliff strategy)
    # Calculate days since registration
    if user.created_at:
        from datetime import datetime, timezone
        days_active = (datetime.now(timezone.utc) - user.created_at).days
        if days_active >= 7: try_award("milestone_week1")
        if days_active >= 21: try_award("milestone_3weeks")
        if days_active >= 60: try_award("milestone_2months")

    if newly_awarded:
        db.commit()

    return newly_awarded
