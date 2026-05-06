"""Plan generator — converts AI-generated plan JSON into DailyTask objects.

Supports two plan formats:
1. LEAN format (new): gym exercises reference names from ExerciseLibrary,
   descriptions/weights are resolved automatically from the static library.
2. VERBOSE format (legacy): full task descriptions inline in the AI response.

The lean format reduces AI API costs by ~80% since the AI only selects exercises
rather than generating descriptions.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

from backend.models.database import DailyTask, ExerciseLibrary
from backend.routers.tasks import (
    generate_default_tasks_for_day,
    DEFAULT_MORNING, DEFAULT_EVENING,
    DEFAULT_REST, DEFAULT_NUT_GYM, DEFAULT_NUT_REST,
    DAYS,
)


def _resolve_exercise(db: Session, exercise_name: str) -> Optional[ExerciseLibrary]:
    """Look up an exercise in the library by exact or fuzzy name match."""
    if not db:
        return None
    # Exact match
    ex = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(exercise_name)
    ).first()
    if ex:
        return ex
    # Fuzzy: first word match
    first_word = exercise_name.split()[0] if exercise_name else ""
    if first_word:
        ex = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.name.ilike(f"%{first_word}%")
        ).first()
    return ex


def _format_sets_reps(item: dict) -> str:
    """Convert lean format {sets: 4, reps: '6-10'} to display string '4x6-10'."""
    sets = item.get("sets", "")
    reps = item.get("reps", "")
    # Already formatted as "4x10" string
    if isinstance(sets, str) and ("x" in sets or "X" in sets):
        return sets
    # Lean format: separate sets and reps
    if sets and reps:
        return f"{sets}x{reps}"
    return str(sets) if sets else "3x10"


def create_tasks_from_plan(
    user_id: int,
    plan_id: int,
    date_str: str,
    plan_data: dict,
    db: Session = None,
    user=None,
) -> list[DailyTask]:
    """Convert a Claude-generated plan JSON into DailyTask objects for a specific day.

    Args:
        user_id: The user's database ID
        plan_id: The plan's database ID
        date_str: Date string in YYYY-MM-DD format
        plan_data: The AI-generated plan JSON
        db: Database session (for exercise library lookups)
        user: User object (for posture correction injection)
    """
    day_idx = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    day_key = str(day_idx)

    days_data = plan_data.get("days", {})

    if day_key not in days_data or not days_data[day_key]:
        return generate_default_tasks_for_day(user_id, date_str, plan_id, user=user)

    day_plan = days_data[day_key]
    tasks = []
    order = 0

    # ─── Morning tasks (use defaults if AI didn't specify) ────────────────
    morning_items = day_plan.get("morning", [])
    if morning_items:
        for item in morning_items:
            tasks.append(DailyTask(
                user_id=user_id, plan_id=plan_id, date=date_str,
                section="morning",
                task_key=item.get("key", f"m{order}"),
                title=item.get("title", ""),
                description=item.get("description", ""),
                category=item.get("category", "health"),
                priority=item.get("priority", False),
                difficulty=item.get("difficulty", "normal"),
                duration_minutes=item.get("duration_minutes", 0),
                xp_reward=item.get("xp_reward", 10),
                sort_order=order,
            ))
            order += 1

    # ─── Gym / Recovery tasks ─────────────────────────────────────────────
    section_name = "gym" if day_plan.get("type") == "gym" else "recovery"
    gym_tasks = day_plan.get("gym", []) if day_plan.get("type") == "gym" else day_plan.get("recovery", [])

    for idx, item in enumerate(gym_tasks):
        # Detect format: lean (exercise_name) vs verbose (title)
        exercise_name = item.get("exercise_name") or item.get("title", "")
        description = item.get("description", "")
        sets_str = _format_sets_reps(item)
        weight = item.get("weight", "")
        exercise_lib_id = None

        # Lean format: resolve exercise from library
        if item.get("exercise_name") and db:
            ex_lib = _resolve_exercise(db, item["exercise_name"])
            if ex_lib:
                exercise_name = ex_lib.name  # use canonical name
                exercise_lib_id = ex_lib.id
                if not description:
                    description = ex_lib.description or ""

        tasks.append(DailyTask(
            user_id=user_id, plan_id=plan_id, date=date_str,
            section=section_name,
            task_key=item.get("key", f"g{idx}"),
            title=exercise_name,
            description=description,
            category=item.get("category", "fitness"),
            priority=item.get("priority", False),
            difficulty=item.get("difficulty", "normal"),
            duration_minutes=item.get("duration_minutes", 0),
            exercise_sets=sets_str,
            exercise_weight=weight,
            exercise_library_id=exercise_lib_id,
            xp_reward=item.get("xp_reward", 15),
            sort_order=order,
        ))
        order += 1

    # ─── Nutrition tasks ──────────────────────────────────────────────────
    for item in day_plan.get("nutrition", []):
        tasks.append(DailyTask(
            user_id=user_id, plan_id=plan_id, date=date_str,
            section="nutrition",
            task_key=item.get("key", f"n{order}"),
            title=item.get("title", ""),
            description=item.get("description", ""),
            category=item.get("category", "health"),
            priority=item.get("priority", False),
            difficulty=item.get("difficulty", "normal"),
            duration_minutes=item.get("duration_minutes", 0),
            xp_reward=item.get("xp_reward", 10),
            sort_order=order,
        ))
        order += 1

    # ─── Evening tasks ────────────────────────────────────────────────────
    for item in day_plan.get("evening", []):
        tasks.append(DailyTask(
            user_id=user_id, plan_id=plan_id, date=date_str,
            section="evening",
            task_key=item.get("key", f"e{order}"),
            title=item.get("title", ""),
            description=item.get("description", ""),
            category=item.get("category", "health"),
            priority=item.get("priority", False),
            difficulty=item.get("difficulty", "normal"),
            duration_minutes=item.get("duration_minutes", 0),
            xp_reward=item.get("xp_reward", 10),
            sort_order=order,
        ))
        order += 1

    # ─── Posture correction injection ─────────────────────────────────────
    if user:
        from backend.services.posture_protocols import inject_posture_tasks
        posture_tasks = inject_posture_tasks(
            tasks, user, user_id, date_str, plan_id, start_order=order
        )
        tasks.extend(posture_tasks)

    if not tasks:
        return generate_default_tasks_for_day(user_id, date_str, plan_id, user=user)

    return tasks
