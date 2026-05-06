from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import secrets
import string

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import (
    Competition, CompetitionMember, User, DailyTask,
    NutritionLog, NutritionTarget, ExerciseWeightLog,
)
from backend.models.schemas import (
    CompetitionCreate, CompetitionJoin, CompetitionResponse, LeaderboardEntry,
)

router = APIRouter(prefix="/api/competitions", tags=["competitions"])


def _generate_invite_code(db: Session) -> str:
    """Generate a unique invite code with retry loop."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "".join(secrets.choice(chars) for _ in range(8))
        existing = db.query(Competition).filter(Competition.invite_code == code).first()
        if not existing:
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique invite code")


def _calc_member_score(db: Session, user_id: int, start_date: str, end_date: str, challenge_type: str = "classic") -> dict:
    tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user_id,
        DailyTask.date >= start_date,
        DailyTask.date <= end_date,
    ).all()

    completed = sum(1 for t in tasks if t.completed)
    total = len(tasks)
    pct = (completed / total * 100) if total else 0

    user = db.query(User).filter(User.id == user_id).first()
    streak_bonus = min(user.streak_days * 2.0, 20.0) if user else 0

    consistency_dates = set()
    for t in tasks:
        if t.completed:
            consistency_dates.add(t.date)
    total_days = max(1, (datetime.strptime(end_date, "%Y-%m-%d") -
                         datetime.strptime(start_date, "%Y-%m-%d")).days + 1)
    consistency_bonus = (len(consistency_dates) / total_days) * 10

    # Score based on challenge type
    if challenge_type == "consistent":
        # Most Consistent: daily completion rate is king
        score = (len(consistency_dates) / total_days) * 100
    elif challenge_type == "streak":
        # Streak Wars: streak days * 10, capped at 100
        score = min((user.streak_days if user else 0) * 10, 100)
    elif challenge_type == "nutrition":
        # Nutrition Champion: days with nutrition logs / total days * 100
        nutrition_days = db.query(NutritionLog.date).filter(
            NutritionLog.user_id == user_id,
            NutritionLog.date >= start_date,
            NutritionLog.date <= end_date,
        ).distinct().count()
        score = (nutrition_days / total_days) * 100
    elif challenge_type == "strength":
        # Iron Will: number of weight logs * 5
        weight_count = db.query(ExerciseWeightLog).filter(
            ExerciseWeightLog.user_id == user_id,
            ExerciseWeightLog.date >= start_date,
            ExerciseWeightLog.date <= end_date,
        ).count()
        score = min(weight_count * 5, 100)
    else:  # classic
        score = pct + streak_bonus + consistency_bonus

    return {
        "score": round(score, 1),
        "tasks_completed": completed,
        "tasks_total": total,
        "completion_pct": round(pct, 1),
        "streak_bonus": round(streak_bonus, 1),
    }


@router.post("/create", response_model=CompetitionResponse)
async def create_competition(
    req: CompetitionCreate,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    # Validate competition name
    if not req.name or len(req.name.strip()) < 2 or len(req.name.strip()) > 50:
        raise HTTPException(status_code=400, detail="Competition name must be 2-50 characters")
    req.name = req.name.strip()

    today = datetime.now(timezone.utc)
    if req.comp_type == "weekly":
        duration = 7
    elif req.comp_type == "monthly":
        duration = 30
    elif req.comp_type == "sprint":
        duration = req.duration_days
    else:
        duration = 7

    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=duration - 1)).strftime("%Y-%m-%d")

    comp = Competition(
        name=req.name,
        invite_code=_generate_invite_code(db),
        created_by=user.id,
        comp_type=req.comp_type,
        challenge_type=req.challenge_type,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    member = CompetitionMember(
        competition_id=comp.id,
        user_id=user.id,
    )
    db.add(member)
    db.commit()

    return CompetitionResponse(
        id=comp.id,
        name=comp.name,
        invite_code=comp.invite_code,
        comp_type=comp.comp_type,
        start_date=comp.start_date,
        end_date=comp.end_date,
        max_members=comp.max_members,
        is_active=comp.is_active,
        member_count=1,
        created_at=comp.created_at,
    )


@router.post("/join")
async def join_competition(
    req: CompetitionJoin,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    code = req.invite_code.strip().upper()
    comp = db.query(Competition).filter(
        Competition.invite_code == code,
        Competition.is_active == True,
    ).first()

    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found or inactive")

    existing = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp.id,
        CompetitionMember.user_id == user.id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already a member")

    member_count = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp.id,
    ).count()

    if member_count >= comp.max_members:
        raise HTTPException(status_code=400, detail="Competition is full")

    member = CompetitionMember(
        competition_id=comp.id,
        user_id=user.id,
    )
    db.add(member)
    db.commit()

    return {"message": "Joined competition", "competition_id": comp.id, "name": comp.name}


@router.get("/my", response_model=list[CompetitionResponse])
async def get_my_competitions(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    memberships = db.query(CompetitionMember).filter(
        CompetitionMember.user_id == user.id,
    ).all()

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    for m in memberships:
        comp = db.query(Competition).filter(Competition.id == m.competition_id).first()
        if comp and comp.is_active and comp.end_date >= today_str:
            member_count = db.query(CompetitionMember).filter(
                CompetitionMember.competition_id == comp.id
            ).count()
            results.append(CompetitionResponse(
                id=comp.id,
                name=comp.name,
                invite_code=comp.invite_code,
                comp_type=comp.comp_type,
                start_date=comp.start_date,
                end_date=comp.end_date,
                max_members=comp.max_members,
                is_active=comp.is_active,
                member_count=member_count,
                created_at=comp.created_at,
            ))

    return results


@router.get("/{comp_id}/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    comp_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_or_create_user(db, tg_user)

    comp = db.query(Competition).filter(Competition.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Verify user is a member of this competition
    is_member = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp_id,
        CompetitionMember.user_id == current_user.id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this competition")

    members = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp_id,
    ).all()

    entries = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if not user:
            continue

        scores = _calc_member_score(db, user.id, comp.start_date, comp.end_date, comp.challenge_type or "classic")

        m.score = scores["score"]
        m.tasks_completed = scores["tasks_completed"]
        m.tasks_total = scores["tasks_total"]
        m.streak_bonus = scores["streak_bonus"]

        entries.append({
            "user": user,
            "member": m,
            "scores": scores,
            "is_self": user.id == current_user.id,
        })

    db.commit()
    entries.sort(key=lambda e: e["scores"]["score"], reverse=True)

    return [
        LeaderboardEntry(
            rank=i + 1,
            user_id=e["user"].id,
            telegram_id=e["user"].telegram_id,
            first_name=e["user"].first_name,
            username=e["user"].username,
            score=e["scores"]["score"],
            tasks_completed=e["scores"]["tasks_completed"],
            tasks_total=e["scores"]["tasks_total"],
            completion_pct=e["scores"]["completion_pct"],
            streak_bonus=e["scores"]["streak_bonus"],
            is_self=e["is_self"],
        )
        for i, e in enumerate(entries)
    ]


@router.get("/{comp_id}/highlights")
async def get_highlights(
    comp_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get competition highlights — biggest streak, most improved, most tasks."""
    current_user = get_or_create_user(db, tg_user)

    comp = db.query(Competition).filter(Competition.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Verify user is a member of this competition
    is_member = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp_id,
        CompetitionMember.user_id == current_user.id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this competition")

    members = db.query(CompetitionMember).filter(
        CompetitionMember.competition_id == comp_id,
    ).all()

    highlights = []
    best_streak = {"name": "", "value": 0}
    most_tasks = {"name": "", "value": 0}
    best_score = {"name": "", "value": 0}

    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if not user:
            continue

        scores = _calc_member_score(db, user.id, comp.start_date, comp.end_date, comp.challenge_type or "classic")

        if user.streak_days > best_streak["value"]:
            best_streak = {"name": user.first_name, "value": user.streak_days}
        if scores["tasks_completed"] > most_tasks["value"]:
            most_tasks = {"name": user.first_name, "value": scores["tasks_completed"]}
        if scores["score"] > best_score["value"]:
            best_score = {"name": user.first_name, "value": scores["score"]}

    if best_streak["value"] > 0:
        highlights.append({"icon": "🔥", "label": "Longest Streak", "name": best_streak["name"], "value": f"{best_streak['value']} days"})
    if most_tasks["value"] > 0:
        highlights.append({"icon": "✅", "label": "Most Tasks Done", "name": most_tasks["name"], "value": str(most_tasks["value"])})
    if best_score["value"] > 0:
        highlights.append({"icon": "🏆", "label": "Top Score", "name": best_score["name"], "value": str(best_score["value"])})

    return {
        "competition_id": comp_id,
        "challenge_type": comp.challenge_type or "classic",
        "highlights": highlights,
    }
