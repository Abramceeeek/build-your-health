"""Golden-value tests for BMR/TDEE/macros and the age fix (H1)."""
import pytest

from backend.services.nutrition_targets import (
    DEFAULT_AGE,
    bmr_mifflin_st_jeor,
    compute_targets,
    normalize_age,
)


def test_bmr_mifflin_hand_calc():
    # male: 10*80 + 6.25*180 - 5*25 + 5 = 1805
    assert round(bmr_mifflin_st_jeor("male", 80, 180, 25)) == 1805
    # female: 10*60 + 6.25*165 - 5*30 - 161 = 1320.25
    assert round(bmr_mifflin_st_jeor("female", 60, 165, 30), 2) == 1320.25


@pytest.mark.parametrize("raw,expected", [
    (None, DEFAULT_AGE), ("abc", DEFAULT_AGE), (10, 14), (120, 90), ("25", 25), (45, 45),
])
def test_normalize_age(raw, expected):
    assert normalize_age(raw) == expected


def test_age_changes_targets():
    base = dict(sex="male", weight_kg=80, height_cm=180, goals=["build_muscle"], gym_days_per_week=4)
    young = compute_targets(**base, age=25)["daily_calories"]
    old = compute_targets(**base, age=55)["daily_calories"]
    assert young > old  # older → lower BMR → lower calories


def test_missing_age_falls_back_to_default():
    base = dict(sex="male", weight_kg=80, height_cm=180, goals=["build_muscle"], gym_days_per_week=4)
    assert compute_targets(**base, age=None) == compute_targets(**base, age=DEFAULT_AGE)


def test_macros_consistent_with_calories():
    t = compute_targets(sex="female", weight_kg=60, height_cm=165, goals=["lose_fat"],
                        gym_days_per_week=2, age=30)
    # protein 2.0 g/kg on a cut
    assert t["daily_protein_g"] == 120
    # calories never produce negative carbs
    assert t["daily_carbs_g"] >= 0
    # macro kcal should be within rounding distance of daily_calories
    macro_kcal = t["daily_protein_g"] * 4 + t["daily_carbs_g"] * 4 + t["daily_fat_g"] * 9
    assert abs(macro_kcal - t["daily_calories"]) <= 12
