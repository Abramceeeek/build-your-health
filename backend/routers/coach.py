"""Coach router — templated morning/evening briefs + free-form Claude chat.

Cost design:
  - GET /api/coach/today  → templated, no LLM call.
  - POST /api/coach/message → Claude Haiku 4.5, max 200 output tokens, capped at
    20 messages/user/day. Injury keywords flag the message so the next plan
    generation prefixes a warning.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import get_settings
from backend.dependencies.auth_deps import get_db, get_or_create_user
from backend.models.database import (
    CoachMessage, DailyTask, ExerciseWeightLog, User,
)
from backend.rate_limit import check_rate_limit
from backend.services.pubmed_service import is_advice_query, fetch_abstracts, build_research_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/coach", tags=["coach"])

INJURY_RE = re.compile(
    r"\b(hurt|pain|sore|tweaked|injur(?:y|ed)|strain(?:ed)?|pulled|ache|aching|stiff|swollen|throb)\b",
    re.IGNORECASE,
)

DAILY_FREEFORM_LIMIT = 20

COACH_SYSTEM_PROMPT = (
    "You are a calm, direct strength coach inside a fitness app. "
    "The user just sent a free-form message. Reply with one practical paragraph "
    "(under 90 words). No headers, no lists, no emojis. "
    "If they describe pain or injury, advise them to rest the affected muscle "
    "and to flag the injury in their settings. Otherwise be encouraging and "
    "specific about what they can do today. Never make medical claims."
)

MORNING_OPENERS = [
    "Today's the day. Let's get the easy wins first.",
    "Show up before you feel like it. Form today, fatigue tomorrow.",
    "Don't look at the whole list — just start the first one.",
    "Discipline is doing it on the days you don't want to.",
    "One rep at a time. The plan does the thinking.",
]

EVENING_REFLECTIONS = [
    "What's one set you wish you'd pushed harder on?",
    "Did anything hurt today? If yes, log it in settings.",
    "Sleep is where the muscle gets built — when are lights out?",
    "One thing you're proud of today?",
    "What would have made today's session 10% better?",
]


class MessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _opener_for(user_id: int, pool: list[str]) -> str:
    return pool[user_id % len(pool)]


@router.get("/today")
async def coach_today(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Templated morning + evening brief for today. No LLM call."""
    user = get_or_create_user(db, tg_user)
    today = _today_str()

    tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == today,
    ).all()

    total = len(tasks)
    done = sum(1 for t in tasks if t.completed)
    gym_tasks = [t for t in tasks if t.section == "gym" and t.task_key != "gw"]
    gym_done = sum(1 for t in gym_tasks if t.completed)

    morning = {
        "headline": _opener_for(user.id, MORNING_OPENERS),
        "tasks_total": total,
        "gym_total": len(gym_tasks),
        "first_priority": next(
            (t.title for t in tasks if t.priority and not t.completed),
            tasks[0].title if tasks else None,
        ),
    }

    evening = {
        "tasks_done": done,
        "tasks_total": total,
        "gym_done": gym_done,
        "gym_total": len(gym_tasks),
        "completion_pct": round(done / total * 100) if total else 0,
        "reflection_question": _opener_for(user.id + done, EVENING_REFLECTIONS),
    }

    return {
        "date": today,
        "streak_days": user.streak_days,
        "morning": morning,
        "evening": evening,
    }


@router.get("/messages")
async def list_messages(
    limit: int = 50,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    limit = max(1, min(200, limit))
    rows = db.query(CoachMessage).filter(
        CoachMessage.user_id == user.id,
    ).order_by(CoachMessage.created_at.desc()).limit(limit).all()
    rows.reverse()  # chronological for the UI
    return [
        {
            "id": r.id,
            "role": r.role,
            "body": r.body,
            "flagged_injury": r.flagged_injury,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _safe_fallback(flagged_injury: bool) -> str:
    if flagged_injury:
        return (
            "Sorry to hear that. Skip anything that loads the sore area today, "
            "ice 15 minutes, and add the injury in Settings so future workouts route around it. "
            "If pain lingers past 48 hours, see a physio."
        )
    return (
        "Logged. Stick with the plan and tell me if anything feels off. "
        "One quality set beats three sloppy ones."
    )


def _build_user_message(user: User, body: str, flagged_injury: bool, research_context: str = "") -> str:
    reg = user.registration_data_json or {}
    context_lines = [
        f"experience: {reg.get('experience_level', 'beginner')}",
        f"goals: {', '.join(reg.get('goals', []) or ['general'])}",
        f"streak: {user.streak_days} days",
    ]
    if flagged_injury:
        context_lines.append("This message mentions pain or injury — be cautious and direct.")
    ctx = " | ".join(context_lines)
    prefix = f"{research_context}\n\n" if research_context else ""
    return f"{prefix}[user context: {ctx}]\n\n{body}"


def _try_anthropic(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=COACH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.warning("coach anthropic failed: %s", e)
        return None


def _try_openrouter(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None
    try:
        import httpx
        # Free models on OpenRouter — try in order. Free tier is rate-limited
        # but plenty for the 20/day per-user cap on this endpoint.
        models = [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
        ]
        last_err = None
        for model in models:
            try:
                r = httpx.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": settings.webapp_url or "https://claudegym.app",
                        "X-Title": "claudeGYM Coach",
                    },
                    json={
                        "model": model,
                        "max_tokens": 200,
                        "temperature": 0.4,
                        "messages": [
                            {"role": "system", "content": COACH_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    },
                    timeout=20,
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                last_err = f"{r.status_code} {r.text[:140]}"
            except Exception as ex:
                last_err = str(ex)[:140]
        logger.warning("coach openrouter all models failed: %s", last_err)
        return None
    except Exception as e:
        logger.warning("coach openrouter exception: %s", e)
        return None


def _try_gemini(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        import httpx
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
        )
        r = httpx.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": COACH_SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 220, "temperature": 0.4},
            },
            timeout=20,
        )
        if r.status_code != 200:
            logger.warning("coach gemini http %s: %s", r.status_code, r.text[:160])
            return None
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning("coach gemini failed: %s", e)
        return None


def _claude_reply(user: User, body: str, flagged_injury: bool, research_context: str = "") -> str:
    """Try Anthropic → OpenRouter → Gemini → templated fallback."""
    prompt = _build_user_message(user, body, flagged_injury, research_context)
    for provider in (_try_openrouter, _try_anthropic, _try_gemini):
        reply = provider(prompt)
        if reply:
            return reply
    return _safe_fallback(flagged_injury)


@router.post("/message")
async def post_message(
    payload: MessageRequest,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)

    if not check_rate_limit(
        user.id, "coach_message", max_calls=DAILY_FREEFORM_LIMIT, window_seconds=86400,
    ):
        raise HTTPException(
            status_code=429,
            detail=f"Let's check in tomorrow — {DAILY_FREEFORM_LIMIT} messages/day.",
        )

    body = payload.body.strip()
    flagged = bool(INJURY_RE.search(body))

    # Fetch PubMed citations for advice queries (non-blocking, falls back to [])
    abstracts = []
    if is_advice_query(body):
        abstracts = await fetch_abstracts(body, max_results=3)
    research_context = build_research_context(abstracts)

    user_msg = CoachMessage(
        user_id=user.id, role="user", body=body, flagged_injury=flagged,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    reply_text = _claude_reply(user, body, flagged, research_context)

    assistant_msg = CoachMessage(
        user_id=user.id, role="assistant", body=reply_text, flagged_injury=False,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    papers = [{"pmid": a["pmid"], "url": a["url"]} for a in abstracts]

    return {
        "user_message": {
            "id": user_msg.id, "role": "user", "body": body,
            "flagged_injury": flagged,
            "created_at": user_msg.created_at.isoformat() if user_msg.created_at else None,
        },
        "assistant_message": {
            "id": assistant_msg.id, "role": "assistant", "body": reply_text,
            "flagged_injury": False,
            "created_at": assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
            "papers": papers if papers else None,
        },
    }


def get_recent_injury_context(db: Session, user_id: int, days: int = 14) -> Optional[str]:
    """Helper for plan_generator: surface the latest flagged injury blurb.

    Returns a short string like 'flagged: shoulder pain — avoid heavy overhead'
    or None if no recent flag.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    rows = db.query(CoachMessage).filter(
        CoachMessage.user_id == user_id,
        CoachMessage.flagged_injury == True,  # noqa: E712
    ).order_by(CoachMessage.created_at.desc()).limit(3).all()
    rows = [
        r for r in rows
        if r.created_at and r.created_at.timestamp() > cutoff
    ]
    if not rows:
        return None
    bits = [r.body[:160].replace("\n", " ") for r in rows]
    return " | ".join(bits)
