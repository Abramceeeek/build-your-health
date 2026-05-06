"""Starting weight calculator — calculates personalized exercise weights.

Uses bodyweight multipliers from the exercise library, adjusted for height and
experience level. Based on Stronger by Science population data and NSCA guidelines.
"""

import math
from sqlalchemy.orm import Session
from backend.models.database import ExerciseLibrary


# Height adjustment factor (taller = longer levers = slight disadvantage on pressing)
# Based on biomechanical lever-arm analysis.
def _height_factor(height_cm: float) -> float:
    """Short (<170cm) +5% advantage, tall (>185cm) -8% disadvantage."""
    if height_cm < 170:
        return 1.05
    elif height_cm > 185:
        return 0.92
    return 1.0


# Experience level multiplier (beginners start lighter for form mastery)
EXPERIENCE_MULT = {
    "beginner": 0.60,       # 60% of calculated weight — prioritize form
    "returning": 0.70,      # 70% — some muscle memory
    "intermediate": 0.85,   # 85% — near full capacity
    "advanced": 1.00,       # 100% — full calculated weight
}


def calculate_starting_weight(
    exercise: ExerciseLibrary,
    bodyweight_kg: float,
    height_cm: float = 175.0,
    sex: str = "male",
    experience_level: str = "beginner",
) -> float:
    """
    Calculate recommended starting weight for an exercise.

    Formula: BW × multiplier × height_factor × experience_factor → round to 2.5kg

    Args:
        exercise: ExerciseLibrary record with starting_weight_mult_male/female
        bodyweight_kg: User's current bodyweight in kg
        height_cm: User's height in cm (default 175)
        sex: 'male' or 'female'
        experience_level: 'beginner', 'returning', 'intermediate', 'advanced'

    Returns:
        Recommended starting weight in kg, rounded to nearest 2.5kg plate increment.
    """
    # Get the sex-appropriate multiplier from the exercise
    if sex == "female":
        bw_mult = exercise.starting_weight_mult_female or 0.20
    else:
        bw_mult = exercise.starting_weight_mult_male or 0.30

    # Base calculation
    raw_weight = bodyweight_kg * bw_mult

    # Apply height adjustment
    raw_weight *= _height_factor(height_cm)

    # Apply experience level
    exp_mult = EXPERIENCE_MULT.get(experience_level, 0.70)
    raw_weight *= exp_mult

    # Round to nearest 2.5kg (standard plate increment)
    rounded = round(raw_weight / 2.5) * 2.5

    # Minimum safety floor: 5kg (empty dumbbell) for isolation, 20kg (empty bar) for barbell
    barbell_exercises = {"Bench Press", "Squat", "Deadlift", "Overhead Press",
                         "Barbell Row", "Front Squat", "Romanian Deadlift",
                         "EZ Bar Curl", "Skull Crusher"}
    if exercise.name in barbell_exercises:
        rounded = max(rounded, 20.0)  # empty Olympic bar
    else:
        rounded = max(rounded, 2.5)   # lightest dumbbell

    return rounded


def format_weight_recommendation(weight_kg: float, exercise: ExerciseLibrary) -> str:
    """Format the weight as a user-friendly string for the task card."""
    if exercise.exercise_type in ("cardio", "stretch", "isometric"):
        return "BW"  # bodyweight exercises

    if weight_kg <= 0:
        return "BW"

    return f"{weight_kg:.1f}kg".replace(".0kg", "kg")


def get_weight_with_history(
    db: Session,
    exercise_name: str,
    user_id: int,
    default_weight: float,
) -> dict:
    """
    Get the recommended weight, considering the user's last recorded session.

    Returns dict with:
      - recommended_weight: what to suggest
      - last_weight: what they lifted last time (or None)
      - progression_note: e.g. "Same as last session" or "+2.5kg from last"
    """
    from backend.models.database import ExerciseWeightLog

    last_log = db.query(ExerciseWeightLog).filter(
        ExerciseWeightLog.user_id == user_id,
        ExerciseWeightLog.exercise_name.ilike(f"%{exercise_name}%"),
    ).order_by(ExerciseWeightLog.recorded_at.desc()).first()

    if not last_log or not last_log.actual_weight:
        return {
            "recommended_weight": default_weight,
            "last_weight": None,
            "progression_note": "First time — start with this weight and focus on form",
        }

    last_weight = float(last_log.actual_weight.replace("kg", "").replace("lb", "").strip())

    # Progressive overload: suggest same weight or +2.5kg if they completed all sets
    sets_str = last_log.sets_completed or ""
    completed_all = "✓" in sets_str or sets_str.count("/") == 0

    if completed_all and last_weight >= default_weight:
        new_weight = round((last_weight + 2.5) / 2.5) * 2.5
        return {
            "recommended_weight": new_weight,
            "last_weight": last_weight,
            "progression_note": f"+2.5kg from last session ({last_weight}kg → {new_weight}kg)",
        }
    else:
        return {
            "recommended_weight": last_weight,
            "last_weight": last_weight,
            "progression_note": f"Same as last session — focus on completing all sets at {last_weight}kg",
        }
