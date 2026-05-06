"""Telegram bot notification service for plan-ready alerts."""

import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from backend.config import get_settings

logger = logging.getLogger(__name__)


async def _send(telegram_id: int, text: str, button_text: str = None, page: str = None):
    """Low-level send helper — avoids duplicating Bot init everywhere."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("No bot token configured, skipping notification")
        return

    bot = Bot(token=settings.telegram_bot_token)
    webapp_url = settings.webapp_url or ""

    reply_markup = None
    if button_text and webapp_url:
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                button_text,
                web_app=WebAppInfo(url=f"{webapp_url}?page={page or 'today'}"),
            )],
        ])

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Failed to send notification to %s: %s", telegram_id, e)


async def notify_plan_ready(telegram_id: int, week_summary: str):
    """Send a notification to the user that their new weekly plan is ready."""
    text = (
        "📋 *Your new weekly plan is ready!*\n\n"
        f"{week_summary}\n\n"
        "Open the app to review your tasks for this week."
    )
    await _send(telegram_id, text, "View Your Plan", "today")


async def notify_morning_reminder(telegram_id: int, streak: int, tasks_today: int, ai_message: str = None):
    """Send a morning reminder with streak info and optional AI-personalized line."""
    streak_text = f"You're on a *{streak}-day streak!* 🔥 " if streak > 0 else ""
    if ai_message:
        text = (
            f"☀️ {ai_message}\n\n"
            f"{streak_text}"
            f"*{tasks_today} tasks* waiting today."
        )
    else:
        text = (
            f"☀️ Good morning! {streak_text}"
            f"You have *{tasks_today} tasks* today.\n\n"
            "Open the app to get started."
        )
    await _send(telegram_id, text, "Start Today", "today")


async def notify_gym_not_done(telegram_id: int, focus: str):
    """Nudge the user if their gym session hasn't been started yet."""
    text = (
        f"🏋️ *Gym reminder*\n\n"
        f"Today's session ({focus}) hasn't been started yet.\n"
        "Even a short workout counts — don't break the chain."
    )
    await _send(telegram_id, text, "Start Workout", "today")


async def notify_no_activity(telegram_id: int, streak: int):
    """End-of-day nudge when zero tasks have been completed."""
    streak_msg = ""
    if streak > 0:
        streak_msg = f"\n\n⚠️ Your *{streak}-day streak* is at risk!"

    text = (
        "📊 *Daily check-in*\n\n"
        "Day's almost done and your tasks are untouched.\n"
        "Even *1 completed task* keeps your streak alive."
        f"{streak_msg}"
    )
    await _send(telegram_id, text, "Open Tasks", "today")


async def forward_feedback_to_admin(
    user_name: str,
    username: str | None,
    telegram_id: int,
    category: str,
    message: str,
    rating: int | None = None,
    page: str = "",
):
    """Forward user feedback to the admin chat.

    Uses the dedicated FEEDBACK_BOT_TOKEN if set so feedback arrives in your
    separate inbox bot; otherwise falls back to the main bot token.
    """
    settings = get_settings()
    admin_id = settings.feedback_admin_chat_id or settings.feedback_channel_id
    bot_token = settings.feedback_bot_token or settings.telegram_bot_token
    if not admin_id or not bot_token:
        return

    stars = ("★" * rating + "☆" * (5 - rating)) if rating else ""
    text = (
        f"📝 *[{category.upper()}]* {stars}\n"
        f"*From:* {user_name} (@{username or telegram_id})\n"
        f"*Page:* {page or 'bot'}\n\n"
        f"{message}"
    )

    try:
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Failed to forward feedback to admin %s: %s", admin_id, e)
