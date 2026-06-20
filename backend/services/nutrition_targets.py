"""TDEE-based daily nutrition targets.

Mifflin-St Jeor BMR + activity factor + goal modifier produces personalised
calorie / macro targets. Replaces the hardcoded 2200 / 150 / 250 / 70 placeholders
that previously appeared for every user regardless of their onboarding inputs.

Age is captured during onboarding; when missing or invalid we fall back to 30
(adult median). Age is clamped to a sane 14–90 range before use.
"""

from typing import Iterable, Optional

DEFAULT_AGE = 30
MIN_AGE = 14
MAX_AGE = 90


def normalize_age(age) -> int:
    """Coerce a possibly-missing/invalid age to a sane integer in [MIN_AGE, MAX_AGE]."""
    try:
        a = int(age)
    except (TypeError, ValueError):
        return DEFAULT_AGE
    return max(MIN_AGE, min(MAX_AGE, a))


def bmr_mifflin_st_jeor(sex: str, weight_kg: float, height_cm: float, age: int = DEFAULT_AGE) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if (sex or "male").lower().startswith("f"):
        return base - 161
    return base + 5


def activity_factor(gym_days_per_week: Optional[int]) -> float:
    days = gym_days_per_week or 0
    if days <= 1:
        return 1.375  # lightly active
    if days <= 4:
        return 1.55   # moderately active
    return 1.725     # very active


def goal_modifier(goals: Iterable[str]) -> float:
    g = set(goals or [])
    # Cut wins over bulk if user picked both — recomp / fat-loss takes priority.
    if "lose_fat" in g:
        return 0.80
    if "build_muscle" in g:
        return 1.10
    return 1.0


def compute_targets(
    *,
    sex: str,
    weight_kg: float,
    height_cm: float,
    goals: Iterable[str],
    gym_days_per_week: Optional[int],
    age: int = DEFAULT_AGE,
) -> dict:
    age = normalize_age(age)
    bmr = bmr_mifflin_st_jeor(sex, weight_kg, height_cm, age)
    cal = bmr * activity_factor(gym_days_per_week) * goal_modifier(goals)
    cal = round(cal, 0)

    # Macro split: protein 2.0 g/kg (cuts) or 1.8 g/kg (otherwise);
    # fat ~25% of calories; carbs fill remainder.
    is_cut = "lose_fat" in set(goals or [])
    protein_g = round((2.0 if is_cut else 1.8) * weight_kg, 0)
    fat_g = round((cal * 0.25) / 9, 0)
    carb_kcal = max(cal - protein_g * 4 - fat_g * 9, 0)
    carb_g = round(carb_kcal / 4, 0)
    fibre_g = round(min(40, max(20, cal / 1000 * 14)), 0)

    return {
        "daily_calories": cal,
        "daily_protein_g": protein_g,
        "daily_carbs_g": carb_g,
        "daily_fat_g": fat_g,
        "daily_fibre_g": fibre_g,
    }
