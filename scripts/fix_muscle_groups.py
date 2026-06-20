"""Normalize muscle_groups and populate split_tags for imported exercises.

Run inside Docker:
    docker-compose exec app python scripts/fix_muscle_groups.py

Maps free-exercise-db anatomical muscle names → system muscle keys
(chest, back, legs, shoulders, biceps, triceps, abs, forearms, calves, neck, rear_delts).
Only updates exercises where split_tags is NULL (i.e., imported, not hand-seeded).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./health_transform.db")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.database import ExerciseLibrary

_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
Session = sessionmaker(bind=_engine)

# free-exercise-db muscle name → system muscle key
MUSCLE_NAME_MAP: dict[str, str] = {
    # chest
    "chest": "chest",
    "pectorals": "chest",
    "lower chest": "chest",
    "upper chest": "chest",
    # back
    "lats": "back",
    "latissimus dorsi": "back",
    "middle back": "back",
    "lower back": "back",
    "traps": "back",
    "trapezius": "back",
    "rhomboids": "back",
    "erector spinae": "back",
    # legs
    "quadriceps": "legs",
    "quads": "legs",
    "hamstrings": "legs",
    "glutes": "legs",
    "gluteus maximus": "legs",
    "adductors": "legs",
    "abductors": "legs",
    "hip flexors": "legs",
    "hip abductors": "legs",
    # shoulders
    "shoulders": "shoulders",
    "deltoids": "shoulders",
    "front delts": "shoulders",
    "front deltoids": "shoulders",
    "middle delts": "shoulders",
    "lateral deltoids": "shoulders",
    # biceps
    "biceps": "biceps",
    "brachialis": "biceps",
    # triceps
    "triceps": "triceps",
    # abs
    "abdominals": "abs",
    "abs": "abs",
    "obliques": "abs",
    "core": "abs",
    "serratus anterior": "abs",
    # forearms
    "forearms": "forearms",
    "wrist flexors": "forearms",
    # calves
    "calves": "calves",
    "soleus": "calves",
    "gastrocnemius": "calves",
    # neck
    "neck": "neck",
    # rear delts
    "rear delts": "rear_delts",
    "posterior deltoids": "rear_delts",
}

SPLIT_TAGS_MAP: dict[str, list[str]] = {
    "chest":      ["push", "chest_shoulder", "upper_body"],
    "back":       ["pull", "back_bicep", "upper_body"],
    "legs":       ["legs_core", "lower_body"],
    "shoulders":  ["push", "chest_shoulder", "upper_body"],
    "biceps":     ["pull", "back_bicep", "upper_body"],
    "triceps":    ["push", "chest_shoulder", "upper_body"],
    "abs":        ["legs_core", "core"],
    "forearms":   ["pull", "upper_body"],
    "calves":     ["legs_core", "lower_body"],
    "neck":       ["upper_body"],
    "rear_delts": ["pull", "upper_body"],
}


def muscle_names_to_keys(names: list[str]) -> list[str]:
    keys = []
    for n in names:
        key = MUSCLE_NAME_MAP.get(n.lower().strip())
        if key and key not in keys:
            keys.append(key)
    return keys


def main():
    db = Session()
    try:
        # Only process exercises without split_tags (imported, not seeded)
        exercises = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.split_tags == None  # noqa: E711
        ).all()

        print(f"Found {len(exercises)} exercises without split_tags")
        updated = skipped = unmapped = 0

        for ex in exercises:
            primary = ex.muscle_primary or []
            secondary = ex.muscle_secondary or []

            # Also include any existing muscle_groups values (handle mixed state)
            existing_groups = ex.muscle_groups or []
            all_source = primary + secondary + existing_groups

            system_keys = muscle_names_to_keys(all_source)

            if not system_keys:
                # Try current muscle_groups as-is (might already be system keys)
                system_keys = [
                    g.lower() for g in existing_groups
                    if g.lower() in SPLIT_TAGS_MAP
                ]

            if not system_keys:
                unmapped += 1
                if primary:
                    print(f"  UNMAPPED: {ex.name!r} primary={primary}")
                continue

            ex.muscle_groups = system_keys

            # Derive split_tags from primary system key
            primary_key = system_keys[0]
            ex.split_tags = SPLIT_TAGS_MAP.get(primary_key, ["upper_body"])

            updated += 1
            if updated % 100 == 0:
                db.commit()
                print(f"  ... {updated} updated")

        db.commit()
        print(f"\nDone:")
        print(f"  {updated} exercises updated with normalized muscle_groups + split_tags")
        print(f"  {skipped} already had split_tags (skipped)")
        print(f"  {unmapped} could not be mapped (no recognized muscle names)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
