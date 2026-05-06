from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from backend.auth import get_current_user
from backend.dependencies.paywall import require_pro
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import UserPlan, UserPhoto, DailyTask
from backend.models.schemas import PlanGenerateRequest, PlanResponse
from backend.services.claude_service import analyze_photos, generate_plan
from backend.services.plan_generator import create_tasks_from_plan
from backend.services.ai_context import build_ai_context

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/current", response_model=PlanResponse)
async def get_current_plan(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    plan = db.query(UserPlan).filter(
        UserPlan.user_id == user.id,
        UserPlan.status == "active",
    ).order_by(UserPlan.created_at.desc()).first()

    if not plan:
        raise HTTPException(status_code=404, detail="No active plan. Upload photos to generate one.")
    return plan


@router.get("/history", response_model=list[PlanResponse])
async def get_plan_history(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    plans = db.query(UserPlan).filter(
        UserPlan.user_id == user.id,
    ).order_by(UserPlan.created_at.desc()).limit(10).all()
    return plans


@router.post("/generate")
async def generate_new_plan(
    request: PlanGenerateRequest,
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    # ── Rate limiting: max 1 plan generation per hour ─────────────────
    last_plan = db.query(UserPlan).filter(
        UserPlan.user_id == user.id,
    ).order_by(UserPlan.created_at.desc()).first()

    if last_plan and last_plan.created_at:
        elapsed = (datetime.now(timezone.utc) - last_plan.created_at).total_seconds()
        if elapsed < 3600:  # 1 hour cooldown
            remaining = int((3600 - elapsed) / 60)
            raise HTTPException(
                status_code=429,
                detail=f"Plan generation is rate-limited. Try again in {remaining} minutes."
            )

    latest_photos = db.query(UserPhoto).filter(
        UserPhoto.user_id == user.id,
    ).order_by(UserPhoto.uploaded_at.desc()).limit(4).all()

    completed_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.completed == True,
    ).count()

    total_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
    ).count()

    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks else 0

    # Use existing AI analysis from photos (photos themselves are not stored)
    analysis = None
    if latest_photos:
        analysis = next(
            (p.ai_analysis_json for p in latest_photos if p.ai_analysis_json),
            None,
        )

    try:
        # Build enriched context from user data
        user_data_context = build_ai_context(db, user.id)

        plan_data = await generate_plan(
            analysis=analysis,
            goals=request.goals,
            experience_level=request.experience_level,
            available_equipment=request.available_equipment,
            injuries=request.injuries,
            sleep_target=request.sleep_target_hours,
            gym_days=request.gym_days_per_week,
            completion_rate=completion_rate,
            streak_days=user.streak_days,
            user_data_context=user_data_context,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")

    old_plans = db.query(UserPlan).filter(
        UserPlan.user_id == user.id,
        UserPlan.status == "active",
    ).all()
    for p in old_plans:
        p.status = "replaced"

    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    week_start = monday.strftime("%Y-%m-%d")

    new_plan = UserPlan(
        user_id=user.id,
        week_start=week_start,
        plan_json=plan_data,
        analysis_json=analysis,
        status="active",
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)

    for i in range(7):
        day_date = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        existing = db.query(DailyTask).filter(
            DailyTask.user_id == user.id,
            DailyTask.date == day_date,
        ).all()
        for t in existing:
            if not t.completed:
                db.delete(t)
        db.commit()

        new_tasks = create_tasks_from_plan(user.id, new_plan.id, day_date, plan_data)
        db.add_all(new_tasks)
    db.commit()

    return {
        "plan_id": new_plan.id,
        "week_start": week_start,
        "analysis": analysis,
        "message": "New plan generated and tasks created for the week",
    }


@router.post("/analyze-photos")
async def analyze_user_photos(
    user=Depends(require_pro),
    db: Session = Depends(get_db),
):
    """Analyze user photos. Uses stored AI analysis if available, or returns mock for re-analysis."""

    photos = db.query(UserPhoto).filter(
        UserPhoto.user_id == user.id,
    ).order_by(UserPhoto.uploaded_at.desc()).limit(4).all()

    if not photos:
        raise HTTPException(status_code=400, detail="No photos uploaded yet")

    # Check if any photos already have analysis results
    existing_analysis = next((p.ai_analysis_json for p in photos if p.ai_analysis_json), None)
    if existing_analysis:
        return {"analysis": existing_analysis}

    # No stored analysis — photos were processed in-memory and bytes are gone.
    # Use mock analysis (real analysis happens at upload time via /api/ai/analyse-photos)
    try:
        analysis = await analyze_photos(photo_data=[], photo_paths=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    for photo in photos:
        photo.ai_analysis_json = analysis
    db.commit()

    return {"analysis": analysis}
