"""Calorie-burn: single formula, library and fallback on the same scale (H8)."""
from backend.services.exercise_service import estimate_calories_burned


def test_library_and_fallback_consistent_for_same_basis():
    # A curated compound at 6.0 kcal/min and a non-library compound now use one formula.
    lib = estimate_calories_burned("Bench Press", 30, 75, exercise_type="compound",
                                   calories_per_min_override=6.0)
    fallback = estimate_calories_burned("Custom Press", 30, 75, exercise_type="compound")
    assert lib == fallback == 180.0  # was 180 vs 225 (MET) before the fix


def test_weight_scaling_linear_from_75kg():
    at75 = estimate_calories_burned("x", 30, 75, calories_per_min_override=6.0)
    at100 = estimate_calories_burned("x", 30, 100, calories_per_min_override=6.0)
    assert at75 == 180.0
    assert at100 == round(6.0 * (100 / 75) * 30, 1)
    assert at100 > at75


def test_curated_override_takes_priority():
    assert estimate_calories_burned("x", 10, 75, exercise_type="compound",
                                    calories_per_min_override=9.0) == 90.0


def test_nonpositive_inputs_are_safe():
    assert estimate_calories_burned("x", -5, 75, calories_per_min_override=6.0) == 0.0
    assert estimate_calories_burned("x", 10, 0, calories_per_min_override=6.0) == 60.0  # 0 weight -> 75 ref
