"""Create 2-frame animated GIFs for imported exercises (free-exercise-db frames).

Run inside Docker:
    docker-compose exec app python scripts/generate_exercise_gifs.py

Downloads /0.jpg + /1.jpg for each GitHub-sourced exercise, creates an
animated GIF in /uploads/exercise_gifs/{id}.gif, and updates image_url in DB.
Skips exercises that already have a local GIF or non-GitHub image.
"""
import asyncio
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.database import ExerciseLibrary

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./health_transform.db")
GIF_DIR = "/app/uploads/exercise_gifs"
MAX_DIM = 400       # max width or height (keeps aspect ratio)
FRAME_DURATION = 700  # ms per frame
MAX_CONCURRENT = 8  # parallel downloads


def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w <= MAX_DIM and h <= MAX_DIM:
        return img
    ratio = min(MAX_DIM / w, MAX_DIM / h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


async def _make_gif(ex_id: int, name: str, url0: str, sem: asyncio.Semaphore,
                    client: httpx.AsyncClient) -> str | None:
    gif_path = os.path.join(GIF_DIR, f"{ex_id}.gif")
    if os.path.exists(gif_path):
        return gif_path

    url1 = url0.replace("/0.jpg", "/1.jpg")
    headers = {"User-Agent": "build-your-health/1.0"}

    async with sem:
        try:
            r0, r1 = await asyncio.gather(
                client.get(url0, headers=headers, timeout=15),
                client.get(url1, headers=headers, timeout=15),
            )
        except Exception as e:
            print(f"  SKIP {name}: {e}")
            return None

    frames = []
    for r in (r0, r1):
        if r.status_code == 200:
            try:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                frames.append(_resize(img))
            except Exception:
                pass

    if not frames:
        return None

    try:
        p = frames[0]
        p.save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            format="GIF",
            duration=FRAME_DURATION,
            loop=0,
            optimize=False,
        )
        return gif_path
    except Exception as e:
        print(f"  SAVE ERROR {name}: {e}")
        return None


async def run():
    os.makedirs(GIF_DIR, exist_ok=True)

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    )
    S = sessionmaker(bind=engine)
    db = S()

    exercises = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.image_url.like("%raw.githubusercontent%")
    ).all()

    print(f"Processing {len(exercises)} exercises with GitHub images …")
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    done = skipped = errors = 0

    async with httpx.AsyncClient() as client:
        tasks = [
            _make_gif(ex.id, ex.name, ex.image_url, sem, client)
            for ex in exercises
        ]
        results = await asyncio.gather(*tasks)

    for ex, gif_path in zip(exercises, results):
        if gif_path is None:
            # Keep existing image_url (static JPG) as fallback
            errors += 1
        elif gif_path and os.path.exists(gif_path):
            local_url = f"/uploads/exercise_gifs/{ex.id}.gif"
            if ex.image_url != local_url:
                ex.image_url = local_url
                done += 1
            else:
                skipped += 1

    db.commit()
    db.close()

    print(f"\nDone:")
    print(f"  {done} GIFs created and DB updated")
    print(f"  {skipped} already existed (skipped)")
    print(f"  {errors} failed (kept static fallback)")


if __name__ == "__main__":
    asyncio.run(run())
