from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import ExerciseLibrary, ExerciseWeightLog
from backend.models.schemas import ExerciseDetailResponse, WeightLogCreate, WeightLogResponse

from fastapi.responses import StreamingResponse
import httpx
import re

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

_PROXY_HOST_ALLOWLIST = {
    "fitnessprogramer.com", "www.fitnessprogramer.com",
    "wger.de", "www.wger.de",
    "media1.tenor.com", "media.tenor.com",
}


def _proxy_url_is_safe(url: str) -> bool:
    """Whitelist-based SSRF guard. Only allow http(s) to known image hosts.

    Blocks attempts to pivot to internal services (loopback, link-local, RFC1918)
    even if those happen to resolve from a known host name.
    """
    from urllib.parse import urlparse
    import ipaddress
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    if not host or host not in _PROXY_HOST_ALLOWLIST:
        return False
    # If host happens to be a literal IP (shouldn't with these names, but
    # defence in depth), reject any private / loopback / link-local.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


@router.get("/proxy-image")
async def proxy_exercise_image(url: str):
    """Proxy image requests to bypass hotlinking restrictions (403).

    Host-allowlisted to prevent SSRF (browsers can't send auth headers on
    <img src> so this stays unauthenticated; the allowlist + no-redirect
    + 10 s timeout neutralise the abuse paths).
    """
    if not _proxy_url_is_safe(url):
        raise HTTPException(status_code=400, detail="URL not allowed")

    async def stream_image():
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://fitnessprogramer.com/",
            }
            try:
                async with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
                    if response.status_code == 200:
                        async for chunk in response.aiter_bytes():
                            yield chunk
                    else:
                        yield b""
            except Exception:
                yield b""

    return StreamingResponse(stream_image(), media_type="image/gif")

@router.get("/{exercise_id}", response_model=ExerciseDetailResponse)
async def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
):
    exercise = db.query(ExerciseLibrary).filter(ExerciseLibrary.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.get("/search/", response_model=list[ExerciseDetailResponse])
async def search_exercises(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    results = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{q}%")
    ).limit(20).all()
    return results


@router.get("/by-name/{name}")
async def get_exercise_by_name(
    name: str,
    db: Session = Depends(get_db),
):
    import re
    # Clean the search name: strip sets/reps info, special chars
    clean = re.sub(r'[\u2013\u2014\u2212–—/]', ' ', name)  # replace dashes/slashes with space
    clean = re.sub(r'\d+\s*(x|sets?|reps?|min|kg|lb)', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\(.*?\)', '', clean)  # remove parenthetical text
    clean = clean.strip()

    # 1. Try exact match (case-insensitive)
    exercise = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(clean)
    ).first()
    if exercise:
        return ExerciseDetailResponse.model_validate(exercise)

    # 2. Score all exercises by word overlap with search query
    search_words = set(w.lower() for w in clean.split() if len(w) > 2)
    if not search_words:
        search_words = set(w.lower() for w in clean.split() if len(w) > 1)

    all_exercises = db.query(ExerciseLibrary).all()
    best_match = None
    best_score = 0

    for ex in all_exercises:
        ex_words = set(w.lower() for w in ex.name.split())
        # Count how many search words appear in the exercise name
        overlap = len(search_words & ex_words)
        # Also check partial word matches (e.g., "pushdown" in "Tricep Pushdown")
        if overlap == 0:
            for sw in search_words:
                for ew in ex_words:
                    if sw in ew or ew in sw:
                        overlap += 0.5

        if overlap > best_score:
            best_score = overlap
            best_match = ex

    if best_match and best_score > 0:
        return ExerciseDetailResponse.model_validate(best_match)

    return None


@router.post("/log-weight", response_model=WeightLogResponse)
async def log_weight(
    data: WeightLogCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    log_entry = ExerciseWeightLog(
        user_id=user.id,
        task_id=data.task_id,
        exercise_name=data.exercise_name,
        date=data.date,
        recommended_weight=data.recommended_weight,
        actual_weight=data.actual_weight,
        sets_completed=data.sets_completed,
        notes=data.notes,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


@router.get("/weight-history/{exercise_name}", response_model=list[WeightLogResponse])
async def get_weight_history(
    exercise_name: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    logs = db.query(ExerciseWeightLog).filter(
        ExerciseWeightLog.user_id == user.id,
        ExerciseWeightLog.exercise_name.ilike(f"%{exercise_name}%"),
    ).order_by(ExerciseWeightLog.date.desc()).limit(20).all()
    return logs


# ── Admin: patch a single exercise's image_url without redeploy ───────────
# Restricted to the admin user_id stored in FEEDBACK_ADMIN_CHAT_ID env var.
from pydantic import BaseModel
from backend.config import get_settings


class ImagePatchRequest(BaseModel):
    name: str
    image_url: str


@router.post("/admin/image-url")
async def admin_patch_image(
    payload: ImagePatchRequest,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: replace an exercise's GIF URL on the fly. Use this to
    fix any broken `image_url` without rebuilding the container."""
    settings = get_settings()
    admin_id = (settings.feedback_admin_chat_id or "").strip()
    if not admin_id or str(tg_user.get("id")) != admin_id:
        raise HTTPException(status_code=403, detail="Admin only")

    ex = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(payload.name)
    ).first()
    if not ex:
        raise HTTPException(status_code=404, detail=f"Exercise not found: {payload.name}")
    ex.image_url = payload.image_url.strip()
    db.commit()
    return {"name": ex.name, "image_url": ex.image_url}


@router.get("/admin/all")
async def admin_all_exercises(
    muscle: str | None = None,
    page: int = 1,
    per_page: int = 50,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated exercise list for visual review. No user-data exposed. Admin only."""
    settings = get_settings()
    admin_id = (settings.feedback_admin_chat_id or "").strip()
    if not admin_id or str(tg_user.get("id")) != admin_id:
        raise HTTPException(status_code=403, detail="Admin only")

    q = db.query(ExerciseLibrary)
    if muscle:
        # Filter by system muscle key in muscle_groups JSON array
        q = q.filter(ExerciseLibrary.muscle_groups.contains([muscle]))
    total = q.count()
    exercises = q.order_by(ExerciseLibrary.name).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": ex.id,
                "name": ex.name,
                "muscle_groups": ex.muscle_groups or [],
                "exercise_type": ex.exercise_type or "",
                "difficulty": ex.difficulty or "",
                "image_url": ex.image_url or "",
                "split_tags": ex.split_tags or [],
            }
            for ex in exercises
        ],
    }


@router.get("/admin/missing-images")
async def admin_list_missing_images(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: list exercises whose `image_url` is empty."""
    settings = get_settings()
    admin_id = (settings.feedback_admin_chat_id or "").strip()
    if not admin_id or str(tg_user.get("id")) != admin_id:
        raise HTTPException(status_code=403, detail="Admin only")
    rows = db.query(ExerciseLibrary).filter(
        (ExerciseLibrary.image_url == "") | (ExerciseLibrary.image_url.is_(None))
    ).order_by(ExerciseLibrary.name).all()
    return [{"id": r.id, "name": r.name, "muscle_groups": r.muscle_groups or []} for r in rows]
