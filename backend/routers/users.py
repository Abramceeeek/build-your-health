from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from io import BytesIO
import os

from backend.services.time_service import local_from_utc, user_local_now, user_today_str

from PIL import Image, UnidentifiedImageError

from backend.auth import get_current_user
from backend.models.database import UserPhoto, UserMetrics, NutritionTarget
from backend.services.nutrition_targets import compute_targets
from backend.models.schemas import (
    UserResponse, UserStats, PhotoResponse,
    RegistrationRequest, RegistrationStatusResponse, BioAgeOut,
)
from backend.rate_limit import check_rate_limit

# ── Canonical source for get_db / get_or_create_user ─────────────────────────
# Imported here so every other router that does
#   `from backend.routers.users import get_db, get_or_create_user`
# keeps working without changes.
from backend.dependencies.auth_deps import get_db, get_or_create_user  # noqa: F401
from backend.dependencies.paywall import require_pro

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(tg_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_or_create_user(db, tg_user)
    return user


@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(tg_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.models.database import DailyTask
    user = get_or_create_user(db, tg_user)

    today = user_today_str(user)
    today_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == today
    ).all()

    done_today = sum(1 for t in today_tasks if t.completed)
    total_today = len(today_tasks)

    from datetime import timedelta
    user_now = user_local_now(user)
    week_start = user_now - timedelta(days=user_now.weekday())
    week_start_str = week_start.strftime("%Y-%m-%d")
    week_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date >= week_start_str
    ).all()
    week_done = sum(1 for t in week_tasks if t.completed)
    week_total = len(week_tasks)

    return UserStats(
        ovr_rating=user.ovr_rating,
        xp=user.xp,
        level=user.level,
        tier=user.tier,
        streak_days=user.streak_days,
        longest_streak=user.longest_streak,
        tasks_completed_today=done_today,
        tasks_total_today=total_today,
        completion_pct=round(done_today / total_today * 100, 1) if total_today else 0,
        weekly_completion_pct=round(week_done / week_total * 100, 1) if week_total else 0,
    )


@router.post("/me/photos", response_model=PhotoResponse)
async def upload_photo(
    photo_type: str,
    file: UploadFile = File(...),
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a photo for AI analysis. Photo is processed in-memory and never stored on disk."""
    if photo_type not in ("body_front", "body_side", "body_back", "face"):
        raise HTTPException(status_code=400, detail="Invalid photo_type")

    user = get_or_create_user(db, tg_user)

    # ── Rate limit: 8 uploads per hour ───────────────────────────────────
    if not check_rate_limit(user.id, "photo_upload", max_calls=8):
        raise HTTPException(status_code=429, detail="Too many uploads. Limit: 8 per hour.")

    # ── Validate file extension ───────────────────────────────────────────
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    ext = os.path.splitext(file.filename or "photo.jpg")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Use: {', '.join(sorted(allowed_extensions))}"
        )

    # ── Validate file size (max 10 MB) ────────────────────────────────────
    MAX_PHOTO_SIZE = 10 * 1024 * 1024
    photo_bytes = await file.read()
    if len(photo_bytes) > MAX_PHOTO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(photo_bytes) // 1024 // 1024}MB). Maximum is 10MB."
        )

    # ── MIME verify + EXIF strip via Pillow ──────────────────────────────
    try:
        Image.open(BytesIO(photo_bytes)).verify()
    except (UnidentifiedImageError, Exception):
        raise HTTPException(status_code=400, detail="File is not a valid image.")

    img = Image.open(BytesIO(photo_bytes))  # re-open after verify()
    fmt_map = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    save_fmt = fmt_map.get(ext, "JPEG")
    if img.mode in ("RGBA", "P", "LA") and save_fmt == "JPEG":
        img = img.convert("RGB")
    clean_buf = BytesIO()
    img.save(clean_buf, format=save_fmt)
    photo_bytes = clean_buf.getvalue()

    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    # Store metadata only — photo processed in-memory, bytes never persisted
    photo = UserPhoto(
        user_id=user.id,
        photo_type=photo_type,
        file_path=f"in_memory://{photo_type}",
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    photo._in_memory_bytes = photo_bytes
    photo._media_type = media_type

    return photo


@router.get("/me/photos", response_model=list[PhotoResponse])
async def get_my_photos(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    photos = db.query(UserPhoto).filter(
        UserPhoto.user_id == user.id
    ).order_by(UserPhoto.uploaded_at.desc()).all()
    return photos


@router.get("/me/shortcut-token")
async def get_shortcut_token(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a fresh sync token for the Apple Watch Shortcut.

    Only the SHA-256 hash is stored server-side; the plaintext is returned once here and
    cannot be retrieved again. Each call ROTATES the token — any previously issued token
    stops working (P2.2, force-rotate).
    """
    from backend.auth import generate_sync_token, hash_sync_token
    user = get_or_create_user(db, tg_user)
    token = generate_sync_token()
    user.sync_token = hash_sync_token(token)
    db.commit()
    return {"sync_token": token}


@router.get("/me/export")
async def export_my_data(tg_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """GDPR: return all of this user's stored data as JSON."""
    from backend.models.database import Base
    user = get_or_create_user(db, tg_user)
    uid = user.id
    out: dict = {}
    for table in Base.metadata.sorted_tables:
        if table.name == "users":
            rows = db.execute(table.select().where(table.c.id == uid)).mappings().all()
        elif "user_id" in table.c:
            rows = db.execute(table.select().where(table.c.user_id == uid)).mappings().all()
        else:
            continue
        if rows:
            out[table.name] = [dict(r) for r in rows]
    return out


@router.delete("/me")
async def delete_my_account(tg_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """GDPR: permanently delete this user and every row referencing them."""
    from backend.models.database import Base
    user = get_or_create_user(db, tg_user)
    uid = user.id
    # Children first (reverse FK order), then the user row.
    for table in reversed(Base.metadata.sorted_tables):
        if "user_id" in table.c:
            db.execute(table.delete().where(table.c.user_id == uid))
    db.execute(Base.metadata.tables["users"].delete().where(Base.metadata.tables["users"].c.id == uid))
    db.commit()
    return {"status": "deleted"}


@router.get("/me/bio-age", response_model=BioAgeOut)
async def get_bio_age(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compute biological age from VO2max, activity, body composition, and recovery."""
    from backend.services.bio_age_service import compute_bio_age
    user = get_or_create_user(db, tg_user)
    result = compute_bio_age(user, db)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Add your date of birth and weight/height to get your biological age.",
        )
    return result


@router.get("/me/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today = user_today_str(user)
    truth_confirmed = False
    if user.last_truth_confirmed_at:
        truth_confirmed = local_from_utc(user.last_truth_confirmed_at, user).strftime("%Y-%m-%d") == today
    return RegistrationStatusResponse(
        is_registered=user.is_registered,
        truth_confirmed_today=truth_confirmed,
    )


class TimezoneUpdate(BaseModel):
    offset_minutes: int  # minutes east of UTC (e.g. -300 = UTC-5, 330 = UTC+5:30)


@router.put("/me/timezone")
async def set_timezone(
    data: TimezoneUpdate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store the user's UTC offset so 'today', streaks, heatmap and reminders follow their
    local calendar day. Clients send their device offset (e.g. -new Date().getTimezoneOffset())."""
    if not (-12 * 60 <= data.offset_minutes <= 14 * 60):
        raise HTTPException(status_code=422, detail="offset_minutes out of range")
    user = get_or_create_user(db, tg_user)
    user.timezone_offset = data.offset_minutes
    db.commit()
    return {"timezone_offset": user.timezone_offset, "local_date": user_today_str(user)}


@router.post("/register")
async def register_user(
    data: RegistrationRequest,
    background_tasks: BackgroundTasks,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    user.is_registered = True
    user.registration_completed_at = datetime.now(timezone.utc)
    user.sex = data.gender  # populate the column (used by bio-age norms + cycle gating)
    user.registration_data_json = {
        "gender": data.gender,
        "goals": data.goals,
        "experience_level": data.experience_level,
        "gym_days_per_week": data.gym_days_per_week,
        "available_equipment": data.available_equipment,
        "injuries": data.injuries,
        "gym_schedule_type": data.gym_schedule_type,
        "gym_specific_days": data.gym_specific_days,
        "gym_every_n_days": data.gym_every_n_days,
        "muscle_schedule": data.muscle_schedule,
        "age": data.age,
    }
    if data.height_cm or data.weight_kg:
        metrics = UserMetrics(
            user_id=user.id,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
        )
        db.add(metrics)

    # Compute personalised nutrition targets (replaces hardcoded 2200/150/250/70).
    if data.height_cm and data.weight_kg:
        t = compute_targets(
            sex=data.gender,
            weight_kg=data.weight_kg,
            height_cm=data.height_cm,
            goals=data.goals,
            gym_days_per_week=data.gym_days_per_week,
            age=data.age,
        )
        # week_start must be the Monday of the user's current local week — that is the
        # key stats/targets lookups use. Storing *today* hid the target on any non-Monday.
        from datetime import timedelta
        now_local = user_local_now(user)
        week_start = (now_local - timedelta(days=now_local.weekday())).strftime("%Y-%m-%d")
        db.add(NutritionTarget(user_id=user.id, week_start=week_start, **t))

    db.commit()

    # Grant 14-day Pro trial on first registration
    from backend.routers.subscriptions import _grant_trial, grant_referral_reward
    _grant_trial(db, user.id)

    # Referral: first-time referee → reward both referee and referrer (once).
    if data.referred_by and not user.referred_by and data.referred_by != user.id:
        from backend.models.database import User
        referrer = db.query(User).filter(User.id == data.referred_by).first()
        if referrer:
            user.referred_by = referrer.id
            db.commit()
            grant_referral_reward(db, user.id)
            grant_referral_reward(db, referrer.id)

    # Generate a plan for the current week immediately (mid-week registration fix)
    user_id = user.id
    background_tasks.add_task(_generate_plan_for_new_user, user_id)

    return {"status": "registered"}


async def _generate_plan_for_new_user(user_id: int) -> None:
    """Generate a weekly plan for a newly registered user (runs in background)."""
    from datetime import timedelta
    from backend.config import get_settings
    from backend.models.database import get_session_factory
    from backend.services.scheduler import generate_user_weekly_plan

    settings = get_settings()
    SessionLocal = get_session_factory(settings.database_url)
    db = SessionLocal()
    try:
        from backend.models.database import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        # Current ISO week Monday
        today = user_local_now(user)
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        await generate_user_weekly_plan(db, user, week_start)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Background plan generation failed for user %s: %s", user_id, e)
    finally:
        db.close()


@router.post("/confirm-truth")
async def confirm_truth(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    user.last_truth_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "confirmed"}


# M10 — face transform early-access subscription
@router.post("/me/face-transform-subscribe")
async def face_transform_subscribe(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    user.face_transform_subscribed = True
    db.commit()
    return {"status": "subscribed"}


@router.get("/registration")
async def get_registration(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current registration data for settings page."""
    user = get_or_create_user(db, tg_user)
    return user.registration_data_json or {}


@router.put("/registration")
async def update_registration(
    data: RegistrationRequest,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update registration preferences (settings page).

    Saves the new prefs and immediately wipes any *uncompleted* tasks from today
    onwards. The next call to /api/tasks/today (or /day/...) will rebuild them
    from the updated muscle_schedule via generate_default_tasks_for_day.
    """
    user = get_or_create_user(db, tg_user)
    user.sex = data.gender
    user.registration_data_json = {
        "gender": data.gender,
        "goals": data.goals,
        "experience_level": data.experience_level,
        "gym_days_per_week": data.gym_days_per_week,
        "available_equipment": data.available_equipment,
        "injuries": data.injuries,
        "gym_schedule_type": data.gym_schedule_type,
        "gym_specific_days": data.gym_specific_days,
        "gym_every_n_days": data.gym_every_n_days,
        "muscle_schedule": data.muscle_schedule,
        "age": data.age,
    }

    from backend.models.database import DailyTask
    today = user_today_str(user)
    deleted = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= today,
        DailyTask.completed == False,  # noqa: E712 — SQLAlchemy expression
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "updated", "tasks_invalidated": deleted}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user profile — only accessible to the user themselves."""
    current_user = get_or_create_user(db, tg_user)
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


# ─── WORKOUT SPLIT SUGGESTION ────────────────────────────────────────────────

class SplitSuggestionRequest(BaseModel):
    inactivity_months: int = 0
    goals: list[str] = []
    experience_level: str = "beginner"
    gym_days: int = 3


@router.post("/suggest-split")
async def suggest_split(
    data: SplitSuggestionRequest,
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    """AI-powered workout split suggestion based on profile and inactivity."""
    if not check_rate_limit(user.id, "suggest_split", max_calls=10):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 10 split suggestions per hour.")
    from backend.services.ai_service import suggest_workout_split
    result = await suggest_workout_split(
        experience_level=data.experience_level,
        inactivity_months=data.inactivity_months,
        goals=data.goals,
        gym_days=data.gym_days,
    )
    return result


@router.post("/reset-account")
async def reset_account(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear registration so the user goes through onboarding again."""
    user = get_or_create_user(db, tg_user)
    user.is_registered = False
    user.registration_data_json = None
    user.registration_completed_at = None
    db.commit()
    return {"reset": True}

