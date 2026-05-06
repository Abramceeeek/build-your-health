"""XP, OVR rating, and competition scoring calculations."""


TIER_THRESHOLDS = [
    (0, "Bronze"),
    (500, "Silver"),
    (1500, "Gold"),
    (3500, "Opal"),
    (7000, "Diamond"),
    (15000, "Champion"),
]

TIER_COLORS = {
    "Bronze": "#CD7F32",
    "Silver": "#C0C0C0",
    "Gold": "#FFD700",
    "Opal": "#AF52DE",
    "Diamond": "#00C7BE",
    "Champion": "#FF2D55",
}

XP_PER_LEVEL_BASE = 100
LEVEL_EXPONENT = 0.7


def xp_for_level(level: int) -> int:
    """Total XP required to reach a given level."""
    return int(((level - 1) / 1) ** (1 / LEVEL_EXPONENT) * XP_PER_LEVEL_BASE)


def level_from_xp(xp: int) -> int:
    return max(1, int((xp / XP_PER_LEVEL_BASE) ** LEVEL_EXPONENT) + 1)


def tier_from_xp(xp: int) -> str:
    tier = "Bronze"
    for threshold, name in TIER_THRESHOLDS:
        if xp >= threshold:
            tier = name
    return tier


def tier_color(tier: str) -> str:
    return TIER_COLORS.get(tier, "#CD7F32")


def calculate_ovr_rating(
    completion_rate_30d: float,
    streak_days: int,
    level: int,
    consistency_rate: float,
) -> float:
    """Calculate OVR rating (0-99) from multiple factors."""
    completion_score = completion_rate_30d * 50
    streak_score = min(streak_days / 30, 1.0) * 25
    level_score = min(level / 50, 1.0) * 15
    consistency_score = consistency_rate * 10

    ovr = completion_score + streak_score + level_score + consistency_score
    return round(min(99, max(0, ovr)), 1)


def calculate_competition_score(
    tasks_completed: int,
    tasks_total: int,
    streak_days: int,
    active_days: int,
    total_days: int,
) -> dict:
    """Calculate competition score with breakdown."""
    completion_pct = (tasks_completed / tasks_total * 100) if tasks_total else 0
    streak_bonus = min(streak_days * 2.0, 20.0)
    consistency_bonus = (active_days / max(1, total_days)) * 10

    total_score = completion_pct + streak_bonus + consistency_bonus

    return {
        "total_score": round(total_score, 1),
        "completion_pct": round(completion_pct, 1),
        "streak_bonus": round(streak_bonus, 1),
        "consistency_bonus": round(consistency_bonus, 1),
    }


MUSCLE_GROUPS = [
    "chest", "shoulders", "back", "biceps", "triceps",
    "forearms", "core", "quads", "hamstrings", "glutes", "calves",
]

EXERCISE_MUSCLE_MAP = {
    "overhead press": ["shoulders"],
    "incline dumbbell press": ["chest", "shoulders"],
    "lateral raises": ["shoulders"],
    "cable fly": ["chest"],
    "pec dec": ["chest"],
    "tricep rope pushdown": ["triceps"],
    "face pull": ["shoulders", "back"],
    "hanging knee raise": ["core"],
    "pull-ups": ["back", "biceps"],
    "lat pulldown": ["back", "biceps"],
    "chest-supported row": ["back"],
    "dumbbell row": ["back"],
    "straight-arm pulldown": ["back"],
    "incline dumbbell curl": ["biceps"],
    "hammer curl": ["biceps", "forearms"],
    "dead bug": ["core"],
    "barbell squat": ["quads", "glutes", "core"],
    "romanian deadlift": ["hamstrings", "glutes"],
    "leg press": ["quads"],
    "bulgarian split squat": ["quads", "glutes"],
    "leg curl": ["hamstrings"],
    "plank": ["core"],
    "hip flexor stretch": ["quads"],
    "calf raises": ["calves"],
    "glute bridge": ["glutes"],
}


def get_muscle_heatmap(completed_exercises: list[str]) -> dict[str, float]:
    """Calculate muscle group activation percentages from completed exercises.

    Returns dict mapping muscle group -> intensity (0.0 to 1.0).
    """
    muscle_hits = {m: 0 for m in MUSCLE_GROUPS}

    for exercise in completed_exercises:
        exercise_lower = exercise.lower()
        for pattern, muscles in EXERCISE_MUSCLE_MAP.items():
            if pattern in exercise_lower:
                for m in muscles:
                    muscle_hits[m] += 1
                break

    max_hits = max(muscle_hits.values()) if muscle_hits else 1
    if max_hits == 0:
        max_hits = 1

    return {m: round(hits / max_hits, 2) for m, hits in muscle_hits.items()}
