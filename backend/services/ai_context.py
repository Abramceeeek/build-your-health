"""Build enriched context for AI plan generation from user's historical data."""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from backend.models.database import (
    NutritionLog, ExerciseWeightLog, DailyTask, UserMetrics, User,
)


def build_ai_context(db: Session, user_id: int) -> str:
    """Query user's recent data and format as context string for AI prompt."""
    sections = []

    # ─── LONG-TERM MEMORY ────────────────────────────────────
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.memory_json:
        from backend.services.memory_service import format_memory_for_prompt
        memory_block = format_memory_for_prompt(user)
        if memory_block:
            sections.append(memory_block)
    today = datetime.now(timezone.utc)

    # ─── NUTRITION (last 7 days) ─────────────────────
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    nutrition_logs = db.query(
        NutritionLog.date,
        func.sum(NutritionLog.calories).label("cal"),
        func.sum(NutritionLog.protein_g).label("protein"),
        func.sum(NutritionLog.carbs_g).label("carbs"),
        func.sum(NutritionLog.fat_g).label("fat"),
    ).filter(
        NutritionLog.user_id == user_id,
        NutritionLog.date >= week_ago,
        NutritionLog.date <= today_str,
    ).group_by(NutritionLog.date).all()

    if nutrition_logs:
        lines = ["NUTRITION (last 7 days):"]
        for row in nutrition_logs:
            lines.append(
                f"  {row.date}: {row.cal:.0f} kcal, "
                f"{row.protein:.0f}g protein, "
                f"{row.carbs:.0f}g carbs, "
                f"{row.fat:.0f}g fat"
            )
        avg_cal = sum(r.cal for r in nutrition_logs) / len(nutrition_logs)
        avg_pro = sum(r.protein for r in nutrition_logs) / len(nutrition_logs)
        lines.append(f"  Average: {avg_cal:.0f} kcal/day, {avg_pro:.0f}g protein/day")
        sections.append("\n".join(lines))

    # ─── WEIGHT PROGRESSION (last 4 per exercise) ─────
    weight_logs = db.query(ExerciseWeightLog).filter(
        ExerciseWeightLog.user_id == user_id,
    ).order_by(ExerciseWeightLog.recorded_at.desc()).limit(30).all()

    if weight_logs:
        # Group by exercise name, take last 4
        by_exercise = {}
        for wl in weight_logs:
            by_exercise.setdefault(wl.exercise_name, []).append(wl)
        lines = ["WEIGHT PROGRESSION (recent):"]
        for ex_name, logs in by_exercise.items():
            recent = logs[:4]
            entries = ", ".join(
                f"{l.date}: {l.actual_weight} ({l.sets_completed})" for l in recent
            )
            lines.append(f"  {ex_name}: {entries}")
        sections.append("\n".join(lines))

    # ─── TASK COMPLETION PATTERNS (14 days) ──────────
    two_weeks_ago = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    task_stats = db.query(
        DailyTask.section,
        func.count(DailyTask.id).label("total"),
        func.sum(func.cast(DailyTask.completed, type_=None)).label("done"),
    ).filter(
        DailyTask.user_id == user_id,
        DailyTask.date >= two_weeks_ago,
        DailyTask.date <= today_str,
    ).group_by(DailyTask.section).all()

    if task_stats:
        lines = ["TASK COMPLETION PATTERNS (14 days):"]
        for row in task_stats:
            total = row.total or 0
            done = int(row.done or 0)
            pct = (done / total * 100) if total > 0 else 0
            lines.append(f"  {row.section}: {done}/{total} ({pct:.0f}%)")
        sections.append("\n".join(lines))

    # ─── BODY METRIC TRENDS ──────────────────────────
    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user_id,
    ).order_by(UserMetrics.recorded_at.desc()).limit(3).all()

    if metrics:
        lines = ["BODY METRICS (latest entries):"]
        for m in metrics:
            date_str = m.recorded_at.strftime("%Y-%m-%d") if m.recorded_at else "?"
            parts = []
            if m.weight_kg:
                parts.append(f"{m.weight_kg}kg")
            if m.body_fat_pct:
                parts.append(f"{m.body_fat_pct}% BF")
            if m.waist_cm:
                parts.append(f"waist {m.waist_cm}cm")
            if m.chest_cm:
                parts.append(f"chest {m.chest_cm}cm")
            if m.bicep_cm:
                parts.append(f"bicep {m.bicep_cm}cm")
            if parts:
                lines.append(f"  {date_str}: {', '.join(parts)}")
        sections.append("\n".join(lines))

    if not sections:
        return "No historical user data available yet."

    return "\n\n".join(sections)
