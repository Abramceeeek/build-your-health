"""Posture correction protocols — deterministic post-processing rules.

When a user's photo analysis detects posture issues, these protocols auto-inject
corrective exercises into their daily plan. This is NOT AI-driven — it's a
deterministic lookup that guarantees corrective exercises are never missed.

Supported conditions:
- anterior_pelvic_tilt (APT)
- rounded_shoulders
- forward_head_posture
- uneven_shoulders
"""

from backend.models.database import DailyTask


# ─── Protocol definitions ──────────────────────────────────────────────────────

POSTURE_PROTOCOLS = {
    "anterior_pelvic_tilt": {
        "morning_exercises": [
            {"key": "pc_apt_1", "title": "Hip Flexor Stretch", "desc": "Kneeling lunge 45s each side. Push hips forward, don't arch lower back.", "cat": "health", "xp": 15, "dur": 3},
            {"key": "pc_apt_2", "title": "Glute Bridge", "desc": "3×15 squeeze hard at top. Activates glutes to counteract tight hip flexors.", "cat": "health", "xp": 10, "dur": 3},
            {"key": "pc_apt_3", "title": "Dead Bug", "desc": "3×10/side. Core anti-extension — trains your abs to hold the pelvis neutral.", "cat": "health", "xp": 10, "dur": 3},
        ],
        "mandatory_gym_exercises": [
            "Hip Thrust",
            "Romanian Deadlift",
            "Bulgarian Split Squat",
        ],
        "avoid_exercises": [],  # No specific avoidances, just don't over-rely on leg press
    },
    "rounded_shoulders": {
        "morning_exercises": [
            {"key": "pc_rs_1", "title": "Doorway Chest Stretch", "desc": "30-45s. Step through doorway with arms on frame at 90°.", "cat": "health", "xp": 10, "dur": 2},
            {"key": "pc_rs_2", "title": "Band Pull-Apart", "desc": "3×15-20. Squeeze shoulder blades together. Light band.", "cat": "health", "xp": 10, "dur": 2},
        ],
        "mandatory_gym_exercises": [
            "Face Pull",
        ],
        "avoid_exercises": [],
    },
    "forward_head_posture": {
        "morning_exercises": [
            {"key": "pc_fhp_1", "title": "Chin Tuck x10", "desc": "Pull chin straight back (double chin). Hold 5s each. Do 3 sets throughout the day.", "cat": "health", "xp": 10, "dur": 2},
        ],
        "mandatory_gym_exercises": [
            "Face Pull",
        ],
        "avoid_exercises": [],
    },
    "uneven_shoulders": {
        "morning_exercises": [],
        "mandatory_gym_exercises": [],
        "notes": "Always train the weak side first on all unilateral exercises.",
    },
}


def get_posture_flags(user) -> list[str]:
    """
    Extract posture condition flags from the user's latest photo analysis.
    Returns a list of strings like ["anterior_pelvic_tilt", "rounded_shoulders"].
    """
    if not user.registration_data_json:
        return []

    # Check registration goals for posture_correction flag
    goals = user.registration_data_json.get("goals", [])
    flags = []

    # If user selected posture_correction as a goal, add common defaults
    if "posture_correction" in goals:
        # Default assumptions for posture correction goal
        flags.extend(["anterior_pelvic_tilt", "rounded_shoulders"])

    # Also check for explicit posture analysis from photo service
    posture_data = user.registration_data_json.get("posture_analysis", {})
    if posture_data:
        if posture_data.get("apt"):
            flags.append("anterior_pelvic_tilt")
        if posture_data.get("rounded_shoulders"):
            flags.append("rounded_shoulders")
        if posture_data.get("forward_head"):
            flags.append("forward_head_posture")
        if posture_data.get("uneven_shoulders"):
            flags.append("uneven_shoulders")

    return list(set(flags))  # deduplicate


def get_corrective_morning_exercises(posture_flags: list[str]) -> list[dict]:
    """Return morning corrective exercises based on detected posture issues."""
    exercises = []
    seen_keys = set()
    for flag in posture_flags:
        protocol = POSTURE_PROTOCOLS.get(flag, {})
        for ex in protocol.get("morning_exercises", []):
            if ex["key"] not in seen_keys:
                exercises.append(ex)
                seen_keys.add(ex["key"])
    return exercises


def get_mandatory_gym_exercises(posture_flags: list[str]) -> list[str]:
    """Return exercise names that MUST be included in every upper body gym session."""
    mandatory = set()
    for flag in posture_flags:
        protocol = POSTURE_PROTOCOLS.get(flag, {})
        mandatory.update(protocol.get("mandatory_gym_exercises", []))
    return list(mandatory)


def inject_posture_tasks(
    tasks: list[DailyTask],
    user,
    user_id: int,
    date_str: str,
    plan_id: int = None,
    start_order: int = 0,
) -> list[DailyTask]:
    """
    Post-process a task list to inject posture corrective exercises.
    Adds morning corrective exercises if they aren't already present.
    Returns the new tasks to add (does not modify existing list).
    """
    posture_flags = get_posture_flags(user)
    if not posture_flags:
        return []

    # Get corrective exercises that should be in the morning
    correctives = get_corrective_morning_exercises(posture_flags)

    # Check which corrective exercises are already in the task list
    existing_titles = {t.title.lower() for t in tasks}
    new_tasks = []
    order = start_order

    for ex in correctives:
        if ex["title"].lower() not in existing_titles:
            new_tasks.append(DailyTask(
                user_id=user_id, plan_id=plan_id, date=date_str,
                section="morning", task_key=ex["key"], title=ex["title"],
                description=ex["desc"], category=ex.get("cat", "health"),
                priority=True, difficulty="normal",
                duration_minutes=ex.get("dur", 2),
                xp_reward=ex.get("xp", 10),
                sort_order=order,
            ))
            order += 1

    return new_tasks
