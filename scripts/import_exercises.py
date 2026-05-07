"""Import exercises from free-exercise-db (public domain) and longhaul-fitness (MIT).

Run inside the Docker container:
    docker-compose exec backend python scripts/import_exercises.py

Or locally (needs DATABASE_URL env var or .env file):
    python scripts/import_exercises.py
"""
import json
import os
import sys
import urllib.request
from urllib.error import URLError

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

FREE_EXERCISE_DB_URL = (
    "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
)
LONGHAUL_URL = (
    "https://raw.githubusercontent.com/longhaul-fitness/exercises/main/strength.json"
)
GITHUB_IMAGE_BASE = (
    "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"
)

CATEGORY_TO_TYPE = {
    "strength": "compound",
    "cardio": "cardio",
    "stretching": "stretch",
    "powerlifting": "compound",
    "olympic weightlifting": "compound",
    "strongman": "compound",
    "plyometrics": "cardio",
}

LEVEL_TO_DIFFICULTY = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "expert": "advanced",
}


def _fetch_json(url: str) -> list | dict:
    print(f"Fetching {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "build-your-health/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _exercise_type(category: str, mechanic: str | None) -> str:
    if mechanic in ("isolation", "compound"):
        return mechanic
    return CATEGORY_TO_TYPE.get((category or "").lower(), "compound")


def _image_url(images: list) -> str:
    if not images:
        return ""
    return GITHUB_IMAGE_BASE + images[0]


def main():
    db = Session()
    try:
        # ── Load source data ──────────────────────────────────────────────────
        try:
            free_db = _fetch_json(FREE_EXERCISE_DB_URL)
        except URLError as e:
            print(f"ERROR: Could not fetch free-exercise-db: {e}")
            sys.exit(1)

        longhaul_notes: dict[str, str] = {}
        try:
            lh = _fetch_json(LONGHAUL_URL)
            for ex in lh:
                name = (ex.get("name") or "").strip().lower()
                note = (ex.get("notes") or "").strip()
                if name and note:
                    longhaul_notes[name] = note
            print(f"Loaded {len(longhaul_notes)} coaching notes from longhaul-fitness")
        except URLError as e:
            print(f"WARNING: Could not fetch longhaul data ({e}). Continuing without coaching notes.")

        # ── Import exercises ──────────────────────────────────────────────────
        inserted = updated = skipped = 0

        for ex in free_db:
            name = (ex.get("name") or "").strip()
            if not name:
                continue

            coaching_note = longhaul_notes.get(name.lower(), "")
            ex_type = _exercise_type(ex.get("category"), ex.get("mechanic"))
            difficulty = LEVEL_TO_DIFFICULTY.get(ex.get("level", ""), "intermediate")
            equipment_raw = ex.get("equipment")
            equipment = [equipment_raw] if isinstance(equipment_raw, str) and equipment_raw else equipment_raw or []

            existing = db.query(ExerciseLibrary).filter(
                ExerciseLibrary.name == name
            ).first()

            if existing:
                changed = False
                if not existing.instructions_json and ex.get("instructions"):
                    existing.instructions_json = ex["instructions"]
                    changed = True
                if not existing.muscle_primary and ex.get("primaryMuscles"):
                    existing.muscle_primary = ex["primaryMuscles"]
                    changed = True
                if not existing.muscle_secondary and ex.get("secondaryMuscles"):
                    existing.muscle_secondary = ex["secondaryMuscles"]
                    changed = True
                if not existing.image_url and ex.get("images"):
                    existing.image_url = _image_url(ex["images"])
                    changed = True
                if not existing.description and coaching_note:
                    existing.description = coaching_note
                    changed = True
                if not existing.equipment_needed and equipment:
                    existing.equipment_needed = equipment
                    changed = True

                if changed:
                    updated += 1
                else:
                    skipped += 1
            else:
                db.add(ExerciseLibrary(
                    name=name,
                    description=coaching_note,
                    instructions_json=ex.get("instructions") or [],
                    muscle_groups=(ex.get("primaryMuscles") or []) + (ex.get("secondaryMuscles") or []),
                    muscle_primary=ex.get("primaryMuscles") or [],
                    muscle_secondary=ex.get("secondaryMuscles") or [],
                    image_url=_image_url(ex.get("images") or []),
                    difficulty=difficulty,
                    exercise_type=ex_type,
                    equipment_needed=equipment,
                    reps_min=6,
                    reps_max=12,
                    rest_seconds=120,
                    calories_per_min=5.0,
                    emg_rank=0,
                ))
                inserted += 1

            if (inserted + updated + skipped) % 100 == 0:
                db.commit()
                print(f"  ... {inserted + updated + skipped} processed")

        db.commit()
        total = len(free_db)
        print(f"\nDone. {total} exercises processed:")
        print(f"  {inserted} inserted")
        print(f"  {updated} enriched (existing exercises updated)")
        print(f"  {skipped} skipped (already complete)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
