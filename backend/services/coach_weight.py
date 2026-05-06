"""Coaching weight ladder + RPE-aware progression.

Replaces the old "flat sets + +2.5kg if completed" rule with a four-step pyramid
that ramps the user up to a top working set, plus a feedback signal ("easy /
right / brutal") that drives the next session's top weight.

Design constraints:
  - Output dict-of-sets is JSON-serialisable; the frontend renders it directly.
  - Top set = the weight produced by `starting_weight.calculate_starting_weight`
    (or, if the user has logged this exercise before, the last actual top set
    adjusted by the most recent RPE).
  - Bodyweight / non-loaded exercises (BW, isometric, cardio) skip the ramp and
    return a single "BW" entry.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import ExerciseLibrary, ExerciseWeightLog


# Ramp percentages of the top set, in order.
RAMP_PCT = [0.60, 0.75, 0.88, 1.00]
RAMP_LABELS = ["warm-up", "build", "working", "top set"]
RAMP_REPS = [12, 10, 8, 6]


# RPE chip → next-session adjustment.
# Chosen on the conservative side: only "easy" pushes the weight up meaningfully.
RPE_NEXT_FACTOR = {
    "easy": 1.05,    # +5%
    "right": None,   # +2.5kg (handled separately so it stays plate-aware)
    "brutal": 1.00,  # repeat
}


def _round_to_plate(weight_kg: float, increment: float = 2.5, floor: float = 2.5) -> float:
    rounded = round(weight_kg / increment) * increment
    return max(rounded, floor)


def build_pyramid(
    top_weight_kg: float,
    exercise: Optional[ExerciseLibrary] = None,
) -> list[dict]:
    """Return a 4-set ramp culminating at top_weight_kg.

    For bodyweight / cardio / stretch exercises returns a single BW entry.
    """
    if exercise and exercise.exercise_type in ("cardio", "stretch", "isometric"):
        return [{
            "set": 1, "weight_kg": 0, "weight_label": "BW",
            "reps": exercise.reps_max or 10,
            "label": "working", "is_top": True,
        }]

    if top_weight_kg <= 0:
        return [{
            "set": 1, "weight_kg": 0, "weight_label": "BW",
            "reps": 10, "label": "working", "is_top": True,
        }]

    is_barbell = bool(exercise) and exercise.name in {
        "Bench Press", "Squat", "Deadlift", "Overhead Press",
        "Barbell Row", "Front Squat", "Romanian Deadlift",
        "EZ Bar Curl", "Skull Crusher",
    }
    floor = 20.0 if is_barbell else 2.5

    sets: list[dict] = []
    for idx, (pct, label, reps) in enumerate(zip(RAMP_PCT, RAMP_LABELS, RAMP_REPS), start=1):
        w = _round_to_plate(top_weight_kg * pct, floor=floor)
        sets.append({
            "set": idx,
            "weight_kg": w,
            "weight_label": f"{w:g}kg",
            "reps": reps,
            "label": label,
            "is_top": idx == len(RAMP_PCT),
        })
    return sets


def _adjust_for_rpe(last_top_kg: float, last_rpe: str | None) -> float:
    """Compute next session's top set from the previous top set + RPE chip."""
    if last_rpe == "easy":
        return _round_to_plate(last_top_kg * RPE_NEXT_FACTOR["easy"])
    if last_rpe == "brutal":
        return _round_to_plate(last_top_kg)
    # default ("right" or unknown): +2.5kg
    return _round_to_plate(last_top_kg + 2.5)


def get_next_top_weight(
    db: Session,
    user_id: int,
    exercise_name: str,
    default_top_kg: float,
) -> dict:
    """Look up the user's last logged top set and project the next one.

    Returns:
        {
          "top_kg": float,
          "last_top_kg": float|None,
          "last_rpe": str|None,
          "note": str
        }
    """
    last_log = db.query(ExerciseWeightLog).filter(
        ExerciseWeightLog.user_id == user_id,
        ExerciseWeightLog.exercise_name.ilike(f"%{exercise_name}%"),
    ).order_by(ExerciseWeightLog.recorded_at.desc()).first()

    if not last_log or not last_log.actual_weight:
        return {
            "top_kg": _round_to_plate(default_top_kg),
            "last_top_kg": None,
            "last_rpe": None,
            "note": "First time — start here, focus on form.",
        }

    try:
        last_top = float(
            last_log.actual_weight.replace("kg", "").replace("lb", "").strip()
        )
    except ValueError:
        return {
            "top_kg": _round_to_plate(default_top_kg),
            "last_top_kg": None,
            "last_rpe": None,
            "note": "Couldn't parse last weight — using default.",
        }

    # Notes column doubles as our RPE chip storage ("easy"|"right"|"brutal")
    last_rpe = (last_log.notes or "").strip().lower()
    if last_rpe not in RPE_NEXT_FACTOR:
        last_rpe = "right"

    next_top = _adjust_for_rpe(last_top, last_rpe)

    if last_rpe == "easy":
        note = f"+5% from last top set ({last_top:g}kg → {next_top:g}kg). It felt easy — push it."
    elif last_rpe == "brutal":
        note = f"Repeat {last_top:g}kg — finish all the reps cleanly before going up."
    else:
        note = f"+2.5kg from last top set ({last_top:g}kg → {next_top:g}kg)."

    return {
        "top_kg": next_top,
        "last_top_kg": last_top,
        "last_rpe": last_rpe,
        "note": note,
    }


def build_coaching_payload(
    db: Session,
    user_id: int,
    exercise: ExerciseLibrary,
    default_top_kg: float,
) -> dict:
    """Convenience: progression + ramp in one structure for the API response."""
    progression = get_next_top_weight(
        db, user_id, exercise.name, default_top_kg,
    )
    ramp = build_pyramid(progression["top_kg"], exercise)
    return {
        "exercise": exercise.name,
        "top_kg": progression["top_kg"],
        "last_top_kg": progression["last_top_kg"],
        "last_rpe": progression["last_rpe"],
        "note": progression["note"],
        "sets": ramp,
        "rpe_options": [
            {"key": "easy",   "label": "Easy",    "hint": "Bar moved fast, 3+ reps in reserve"},
            {"key": "right",  "label": "Right",   "hint": "Tough but clean, 1-2 in reserve"},
            {"key": "brutal", "label": "Brutal",  "hint": "Form broke or missed a rep"},
        ],
    }
