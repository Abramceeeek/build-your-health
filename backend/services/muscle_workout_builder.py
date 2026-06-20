"""Muscle-group–based workout builder.

Users pick which muscles to train on each gym day.  The builder queries
ExerciseLibrary, picks the right number of exercises per muscle, avoids
recent repeats, and auto-suggests a small "bonus" muscle.

Muscle tiers
────────────
  Big   → chest, back, legs        → 4 exercises per session, weekly mandatory
  Mid   → shoulders, biceps, triceps → 4 exercises per session, weekly mandatory
  Small → abs, neck, forearms, rear_delts, calves → 1-2 exercises, bonus add-on
"""

from __future__ import annotations

import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import DailyTask, ExerciseLibrary, User

logger = logging.getLogger(__name__)

# ── Muscle group definitions ────────────────────────────────────────────────

MUSCLE_GROUPS = {
    # Big muscles: 4 exercises per session (prevents overtraining if hit 2x a week)
    "chest":      {"tier": "big",   "count": 4, "label": "Chest",      "icon": "🫁"},
    "back":       {"tier": "big",   "count": 4, "label": "Back",       "icon": "🔙"},
    "legs":       {"tier": "big",   "count": 4, "label": "Legs",       "icon": "🦵"},
    # Mid muscles: 2-3 exercises per session
    "shoulders":  {"tier": "mid",   "count": 3, "label": "Shoulders",  "icon": "🏋️"},
    "biceps":     {"tier": "mid",   "count": 2, "label": "Biceps",     "icon": "💪"},
    "triceps":    {"tier": "mid",   "count": 2, "label": "Triceps",    "icon": "💪"},
    # Small muscles: 2 exercises per session
    "abs":        {"tier": "small", "count": 2, "label": "Abs",        "icon": "🧱"},
    "neck":       {"tier": "small", "count": 2, "label": "Neck",       "icon": "🦒"},
    "forearms":   {"tier": "small", "count": 2, "label": "Forearms",   "icon": "🤝"},
    "rear_delts": {"tier": "small", "count": 2, "label": "Rear Delts", "icon": "🎯"},
    "calves":     {"tier": "small", "count": 2, "label": "Calves",     "icon": "🦶"},
}

SMALL_MUSCLES = [k for k, v in MUSCLE_GROUPS.items() if v["tier"] == "small"]

# Mapping from our muscle key → possible ExerciseLibrary.muscle_primary values
# (case-insensitive partial match)
MUSCLE_SEARCH_TERMS = {
    "chest":      ["chest", "pectoral", "pec"],
    "back":       ["back", "lat", "latissimus", "rhomboid", "trapezius", "trap"],
    "legs":       ["quad", "hamstring", "glute", "adductor", "abductor", "hip flexor"],
    "shoulders":  ["shoulder", "deltoid", "delt"],
    "biceps":     ["bicep", "brachialis"],
    "triceps":    ["tricep"],
    "abs":        ["abdominal", "oblique", "core", "serratus"],
    "neck":       ["neck"],
    "forearms":   ["forearm", "wrist", "grip"],
    "rear_delts": ["rear delt", "posterior delt"],
    "calves":     ["calf", "calves", "soleus", "gastrocnemius"],
}

# ── Fallback exercises when library is empty for a muscle ────────────────────

FALLBACK_EXERCISES: dict[str, list[dict]] = {
    "chest": [
        {"name": "Bench Press",           "sets": "4x6-10",  "desc": "Foundational chest strength. Full range of motion.", "xp": 20, "dur": 10},
        {"name": "Incline Dumbbell Press", "sets": "4x8-12", "desc": "Upper chest thickness. Set bench to 30°.", "xp": 15, "dur": 10},
        {"name": "Cable Fly",             "sets": "3x12-15",  "desc": "Chest isolation — full stretch and squeeze.", "xp": 15, "dur": 8},
        {"name": "Dips (chest)",          "sets": "3x8-12",  "desc": "Lean forward for chest emphasis. Deep stretch.", "xp": 15, "dur": 8},
    ],
    "back": [
        {"name": "Pull-up",              "sets": "5x5-8",   "desc": "Your #1 exercise. Wide back is the biggest physique changer.", "xp": 25, "dur": 12},
        {"name": "Barbell Row",           "sets": "4x6-10",  "desc": "Mid-back thickness. Strict form.", "xp": 20, "dur": 10},
        {"name": "Lat Pulldown",          "sets": "3x8-12",  "desc": "Lower lat width. Lean back slightly.", "xp": 15, "dur": 8},
        {"name": "Seated Cable Row",      "sets": "3x10-12", "desc": "Mid-back. Squeeze shoulder blades together.", "xp": 15, "dur": 8},
    ],
    "legs": [
        {"name": "Squat",                 "sets": "4x5-8",   "desc": "Highest testosterone response. Go below parallel.", "xp": 25, "dur": 12},
        {"name": "Romanian Deadlift",     "sets": "4x8-12",  "desc": "Hamstring + glute. Hinge at hips, feel the stretch.", "xp": 20, "dur": 10},
        {"name": "Leg Press",             "sets": "3x10-15", "desc": "Quad volume without lower back strain.", "xp": 15, "dur": 8},
        {"name": "Bulgarian Split Squat", "sets": "3x8-12/leg", "desc": "Best unilateral exercise. Fixes imbalances.", "xp": 20, "dur": 10},
    ],
    "shoulders": [
        {"name": "Overhead Press",        "sets": "4x6-8",   "desc": "Shoulder width transforms your V-taper.", "xp": 20, "dur": 10},
        {"name": "Lateral Raise",         "sets": "4x12-15", "desc": "Side delts = visible width. Slow and controlled.", "xp": 20, "dur": 8},
        {"name": "Face Pull",             "sets": "3x15-20", "desc": "Rear delts + rotator cuff. Never skip.", "xp": 20, "dur": 6},
        {"name": "Dumbbell Shoulder Press","sets": "3x8-12",  "desc": "Overhead strength for balanced shoulders.", "xp": 15, "dur": 8},
    ],
    "biceps": [
        {"name": "Incline Dumbbell Curl", "sets": "4x10-15", "desc": "Bicep peak. Incline forces full stretch.", "xp": 15, "dur": 8},
        {"name": "Hammer Curl",           "sets": "3x8-12",  "desc": "Brachialis thickness. Bigger arms from all angles.", "xp": 10, "dur": 6},
        {"name": "EZ Bar Curl",           "sets": "3x8-12",  "desc": "Bicep mass. Full stretch at bottom.", "xp": 10, "dur": 6},
        {"name": "Concentration Curl",    "sets": "3x10-12", "desc": "Peak contraction isolation.", "xp": 10, "dur": 6},
    ],
    "triceps": [
        {"name": "Tricep Pushdown",       "sets": "3x12-15", "desc": "Triceps = 2/3 of arm size. Full lockout.", "xp": 10, "dur": 6},
        {"name": "Overhead Tricep Extension","sets":"3x10-15","desc": "Long head of tricep. Deep stretch.", "xp": 10, "dur": 6},
        {"name": "Close-Grip Bench Press","sets": "3x8-10",  "desc": "Compound tricep builder.", "xp": 15, "dur": 8},
        {"name": "Skull Crusher",         "sets": "3x10-12", "desc": "Classic tricep isolation. Control the negative.", "xp": 10, "dur": 6},
    ],
    "abs": [
        {"name": "Hanging Leg Raise",     "sets": "3x10-15", "desc": "Lower abs. Full range of motion.", "xp": 15, "dur": 5},
        {"name": "Plank",                 "sets": "3x45-60s","desc": "Core stability. Squeeze everything.", "xp": 10, "dur": 5},
    ],
    "neck": [
        {"name": "Neck Curl",             "sets": "3x15-20", "desc": "Neck flexion with plate. Light weight, high reps.", "xp": 10, "dur": 5},
    ],
    "forearms": [
        {"name": "Wrist Curl",            "sets": "3x15-20", "desc": "Forearm flexors. Slow and controlled.", "xp": 10, "dur": 5},
    ],
    "rear_delts": [
        {"name": "Face Pull",             "sets": "3x15-20", "desc": "Rear delts + rotator cuff. Posture fix.", "xp": 15, "dur": 6},
    ],
    "calves": [
        {"name": "Calf Raise",            "sets": "3x15-20", "desc": "Standing calf raise. Full stretch at bottom.", "xp": 10, "dur": 5},
        {"name": "Seated Calf Raise",     "sets": "3x15-20", "desc": "Soleus muscle. Slow and controlled.", "xp": 10, "dur": 5},
    ],
}


def _find_exercises_for_muscle(
    db: Session,
    muscle_key: str,
    user: User,
    count: int,
    exclude_names: set[str],
) -> list[dict]:
    """Query ExerciseLibrary for exercises targeting the given muscle.

    Falls back to FALLBACK_EXERCISES if the library doesn't have enough matches.
    """
    search_terms = MUSCLE_SEARCH_TERMS.get(muscle_key, [muscle_key])
    reg = user.registration_data_json or {}
    available_equipment = reg.get("available_equipment", [])

    # Query exercises whose muscle_primary or muscle_groups contain any search term
    all_exercises = db.query(ExerciseLibrary).all()
    matched = []
    for ex in all_exercises:
        if ex.name.lower() in {n.lower() for n in exclude_names}:
            continue

        primary = ex.muscle_primary or []
        secondary = ex.muscle_secondary or []
        groups = ex.muscle_groups or []

        # Exact key match first (normalized muscle_groups from fix_muscle_groups.py)
        all_keys = [g.lower() for g in groups]
        if muscle_key in all_keys:
            matched.append(ex)
            continue

        # Substring search on muscle data only — do NOT include exercise name
        # (including name caused "Leg Curl"→biceps, "Leg Extension"→triceps false positives)
        text_blob = " ".join(t.lower() for t in primary + secondary + groups)
        if any(term.lower() in text_blob for term in search_terms):
            matched.append(ex)

    # Sort by EMG rank (lower = better activation), with 0/None last
    matched.sort(key=lambda e: e.emg_rank if e.emg_rank and e.emg_rank > 0 else 999)

    # Filter by equipment if user has preferences
    if available_equipment:
        equip_filtered = [
            e for e in matched
            if not e.equipment_needed
            or any(eq.lower() in [x.lower() for x in (e.equipment_needed or [])]
                   for eq in available_equipment)
        ]
        if len(equip_filtered) >= count:
            matched = equip_filtered

    # Split into compound (always include ≥1) and isolation
    compounds = [e for e in matched if e.exercise_type == "compound"]
    isolation = [e for e in matched if e.exercise_type != "compound"]

    # Always lead with the top compound; randomise the rest for variety
    selected: list = []
    if compounds:
        selected.append(compounds[0])                   # best compound by emg_rank
        non_lead = compounds[1:]
        random.shuffle(non_lead)                        # in-place on own list (not a slice)
        random.shuffle(isolation)
        pool = non_lead + isolation
    else:
        pool = list(matched)
        random.shuffle(pool)

    for ex in pool:
        if len(selected) >= count:
            break
        if ex not in selected:
            selected.append(ex)

    matched = selected

    results = []
    for ex in matched[:count]:
        sets_base = ex.default_sets if hasattr(ex, "default_sets") and ex.default_sets else f"{ex.reps_min or 3}x{ex.reps_max or 12}"
        rest = ex.rest_seconds or 90
        sets_display = f"{sets_base} ({rest}s rest)"
        results.append({
            "name": ex.name,
            "key": f"g{len(results)+1}",
            "sets": sets_display,
            "desc": ex.description or "",
            "xp": 15 if MUSCLE_GROUPS.get(muscle_key, {}).get("tier") != "small" else 10,
            "dur": 8,
            "priority": len(results) < 2,  # first 2 are priority
            "exercise_library_id": ex.id,
        })

    # Fill remaining with fallbacks
    fallbacks = FALLBACK_EXERCISES.get(muscle_key, [])
    for fb in fallbacks:
        if len(results) >= count:
            break
        if fb["name"].lower() in {r["name"].lower() for r in results}:
            continue
        if fb["name"].lower() in {n.lower() for n in exclude_names}:
            continue
        results.append({
            **fb,
            "key": f"g{len(results)+1}",
            "priority": len(results) < 2,
        })

    return results[:count]


def _pick_bonus_small_muscle(
    user_muscles: list[str],
    recent_smalls: set[str] | None = None,
) -> str | None:
    """Auto-suggest a small muscle that the user hasn't explicitly picked."""
    available = [m for m in SMALL_MUSCLES if m not in user_muscles]
    if not available:
        return None

    # Prefer muscles not trained recently
    if recent_smalls:
        not_recent = [m for m in available if m not in recent_smalls]
        if not_recent:
            return random.choice(not_recent)

    return random.choice(available)


def build_workout_for_day(
    db: Session,
    user: User,
    date_str: str,
    muscles: list[str],
    plan_id: int | None = None,
) -> list[DailyTask]:
    """Build a full gym workout for the given muscles.

    Args:
        db: Database session
        user: The user object
        date_str: Date string "YYYY-MM-DD"
        muscles: List of muscle keys e.g. ["chest", "biceps"]
        plan_id: Optional plan ID

    Returns:
        List of DailyTask objects (not yet added to DB)
    """
    tasks: list[DailyTask] = []
    used_names: set[str] = set()
    order = 0

    # Warm-up
    tasks.append(DailyTask(
        user_id=user.id, plan_id=plan_id, date=date_str,
        section="gym", task_key="gw",
        title="Warm-up: 5 min cardio + dynamic stretches",
        description="Get blood flowing before lifting. Light jog, arm circles, leg swings.",
        category="fitness", priority=False, difficulty="normal",
        duration_minutes=5, xp_reward=5, sort_order=order,
    ))
    order += 1

    # Main muscles
    for muscle_key in muscles:
        info = MUSCLE_GROUPS.get(muscle_key)
        if not info:
            continue

        count = info["count"]
        exercises = _find_exercises_for_muscle(db, muscle_key, user, count, used_names)

        for ex in exercises:
            used_names.add(ex["name"])
            tasks.append(DailyTask(
                user_id=user.id, plan_id=plan_id, date=date_str,
                section="gym", task_key=ex.get("key", f"g{order}"),
                title=ex["name"],
                description=ex.get("desc", ""),
                category="fitness",
                priority=ex.get("priority", False),
                difficulty="normal",
                duration_minutes=ex.get("dur", 8),
                exercise_sets=ex.get("sets", "3x10"),
                exercise_weight="",
                exercise_library_id=ex.get("exercise_library_id"),
                xp_reward=ex.get("xp", 15),
                sort_order=order,
            ))
            order += 1

    # Auto-suggest bonus small muscle
    bonus = _pick_bonus_small_muscle(muscles)
    if bonus:
        bonus_info = MUSCLE_GROUPS[bonus]
        bonus_exercises = _find_exercises_for_muscle(
            db, bonus, user, bonus_info["count"], used_names,
        )
        if bonus_exercises:
            # Add a label comment as a separator-ish approach in the task title
            for ex in bonus_exercises:
                used_names.add(ex["name"])
                tasks.append(DailyTask(
                    user_id=user.id, plan_id=plan_id, date=date_str,
                    section="gym", task_key=ex.get("key", f"g{order}"),
                    title=ex["name"],
                    description=f"Bonus: {bonus_info['label']} — {ex.get('desc', '')}",
                    category="fitness",
                    priority=False, difficulty="normal",
                    duration_minutes=ex.get("dur", 5),
                    exercise_sets=ex.get("sets", "3x15"),
                    exercise_weight="",
                    exercise_library_id=ex.get("exercise_library_id"),
                    xp_reward=ex.get("xp", 10),
                    sort_order=order,
                ))
                order += 1

    # Re-key all gym tasks sequentially
    gym_idx = 0
    for t in tasks:
        if t.section == "gym":
            t.task_key = "gw" if gym_idx == 0 else f"g{gym_idx}"
            t.sort_order = gym_idx
            gym_idx += 1

    return tasks


def get_muscle_groups_info() -> dict:
    """Return the full muscle group catalog for frontend display."""
    return MUSCLE_GROUPS


def validate_muscle_schedule(schedule: dict[str, list[str]], gym_days: list[int]) -> list[str]:
    """Validate that a muscle schedule covers all big + mid muscles at least once/week.

    Returns list of error messages (empty = valid).
    """
    errors = []

    all_chosen = set()
    for day_idx_str, muscles in schedule.items():
        day_idx = int(day_idx_str)
        if day_idx not in gym_days:
            errors.append(f"Day {day_idx} is not a gym day")
        for m in muscles:
            if m not in MUSCLE_GROUPS:
                errors.append(f"Unknown muscle group: {m}")
            all_chosen.add(m)

    # Check mandatory muscles (big + mid)
    mandatory = {k for k, v in MUSCLE_GROUPS.items() if v["tier"] in ("big", "mid")}
    missing = mandatory - all_chosen
    if missing:
        labels = [MUSCLE_GROUPS[m]["label"] for m in missing]
        errors.append(f"Missing required muscles in weekly schedule: {', '.join(labels)}")

    return errors
