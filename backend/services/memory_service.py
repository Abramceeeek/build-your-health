"""Per-user fitness memory: accumulates weekly data, compresses older history."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.database import User

logger = logging.getLogger(__name__)

_COMPRESS_SYSTEM = (
    "You are a fitness AI tracking a user's long-term progress. "
    "Compress the provided history into 3-5 bullet points (≤200 words total). "
    "Capture: training consistency, nutrition adherence, strength trends, and recurring blind spots. "
    "Keep every meaningful insight — drop only redundant repetition. "
    "Return plain text bullets only, no headers, no JSON."
)


def _distill_week(week_start: str, ctx: dict) -> dict:
    """Convert raw collect_user_context() output into a compact weekly record."""
    wins = []
    misses = []

    rate = ctx.get("completion_rate", 0)
    if rate >= 80:
        wins.append(f"{rate}% task completion")
    elif rate < 50:
        misses.append(f"Only {rate}% task completion")

    days_logged = ctx.get("nutrition_days_logged", 0)
    if days_logged >= 5:
        wins.append(f"Nutrition logged {days_logged}/7 days")
    elif days_logged <= 2:
        misses.append(f"Nutrition logged only {days_logged}/7 days")

    for wl in (ctx.get("weight_logs") or [])[:3]:
        wins.append(f"{wl['exercise']}: {wl['weight']} x{wl['sets']} sets")

    return {
        "week": week_start,
        "completion_rate": rate,
        "avg_kcal": ctx.get("avg_daily_calories", 0),
        "avg_protein": ctx.get("avg_daily_protein", 0),
        "nutrition_days": days_logged,
        "streak": ctx.get("streak_days", 0),
        "wins": wins[:4],
        "misses": misses[:4],
    }


async def update_user_memory(
    db: Session,
    user: User,
    week_start: str,
    ctx: dict,
) -> None:
    """Append this week to the user's memory; compress if needed."""
    mem = user.memory_json or {
        "week_count": 0,
        "user_summary": "",
        "recent_weeks": [],
        "updated_at": "",
    }

    new_entry = _distill_week(week_start, ctx)
    recent: list = list(mem.get("recent_weeks", []))
    recent.append(new_entry)

    week_count = mem.get("week_count", 0) + 1

    if len(recent) > 4:
        # Compress oldest weeks into summary
        to_compress = recent[:-4]
        keep = recent[-4:]
        old_summary = mem.get("user_summary", "")

        compress_msg = ""
        if old_summary:
            compress_msg += f"EXISTING SUMMARY:\n{old_summary}\n\n"
        compress_msg += "WEEKS TO ABSORB:\n"
        for w in to_compress:
            compress_msg += json.dumps(w) + "\n"

        try:
            from backend.services.ai_service import call_ai
            compressed = await call_ai(_COMPRESS_SYSTEM, compress_msg, max_tokens=400)
            new_summary = compressed.strip() if compressed else old_summary
        except Exception as e:
            logger.warning("Memory compression failed: %s", e)
            new_summary = old_summary

        mem["user_summary"] = new_summary
        mem["recent_weeks"] = keep
    else:
        mem["recent_weeks"] = recent

    mem["week_count"] = week_count
    mem["updated_at"] = datetime.now(timezone.utc).isoformat()

    user.memory_json = mem
    db.commit()
    logger.info("Memory updated for user %s (week %d)", user.id, week_count)


def format_memory_for_prompt(user: User) -> str:
    """Return a concise memory block to inject into AI prompts."""
    mem = user.memory_json
    if not mem:
        return ""

    parts = ["USER LONG-TERM MEMORY:"]

    week_count = mem.get("week_count", 0)
    if week_count:
        parts.append(f"  Active for {week_count} week(s).")

    summary = mem.get("user_summary", "").strip()
    if summary:
        parts.append(f"  Historical patterns:\n{summary}")

    recent = mem.get("recent_weeks", [])
    if recent:
        parts.append("  Recent weeks:")
        for w in recent:
            line = (
                f"    [{w['week']}] {w['completion_rate']}% tasks, "
                f"{w['avg_kcal']} kcal/d, {w['avg_protein']}g protein/d, "
                f"{w['nutrition_days']}/7 days logged, streak {w['streak']}d"
            )
            if w.get("wins"):
                line += f" | wins: {', '.join(w['wins'][:2])}"
            if w.get("misses"):
                line += f" | misses: {', '.join(w['misses'][:2])}"
            parts.append(line)

    return "\n".join(parts)
