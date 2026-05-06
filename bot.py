"""Telegram Bot for claudeGYM mini app.

Provides:
- /start command with Web App button
- /compete command to create/share competition invite links
- /stats command to show current progress
- Deep linking for competition invites
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    WebAppInfo, MenuButtonWebApp,
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    PreCheckoutQueryHandler, filters, ConversationHandler, CallbackQueryHandler,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Strip whitespace — trailing space in .env breaks the Mini App URL
WEBAPP_URL = (os.getenv("WEBAPP_URL", "") or "").strip()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command — show the mini app button."""
    user = update.effective_user

    deep_link_arg = context.args[0] if context.args else None
    invite_code = None
    if deep_link_arg and deep_link_arg.startswith("join_"):
        invite_code = deep_link_arg[5:]

    webapp_url = WEBAPP_URL
    if invite_code:
        webapp_url += f"?invite={invite_code}"

    # Check if user is registered in the DB
    from backend.config import get_settings
    from backend.models.database import get_session_factory, User
    
    settings = get_settings()
    SessionLocal = get_session_factory(settings.database_url)
    db = SessionLocal()
    is_registered = False
    try:
        db_user = db.query(User).filter(User.telegram_id == user.id).first()
        is_registered = bool(db_user and db_user.is_registered)
    finally:
        db.close()

    keyboard = [
        [InlineKeyboardButton(
            "🚀 Open claudeGYM",
            web_app=WebAppInfo(url=webapp_url),
        )]
    ]
    
    if not is_registered:
        welcome_text = (
            f"👋 *Hey {user.first_name}! Welcome to claudeGYM.*\n\n"
            "I'm your AI-powered personal coach. I don't just track what you do — "
            "I build a complete system to transform your physique and daily habits.\n\n"
            "🔥 *What you get:*\n"
            "• *Gym:* Smart workout plans based on your equipment and goals.\n"
            "• *Face & Posture:* Daily protocols for jawline and posture correction.\n"
            "• *Nutrition:* Easy meal tracking and AI-calculated macros.\n"
            "• *Consistency:* Streaks, XP, badges, and weekly friend competitions.\n\n"
            "Tap the button below to set up your profile and get your first week's plan!"
        )
    else:
        welcome_text = (
            f"Welcome back, *{user.first_name}*! 💪\n\n"
            "Your daily tasks and current week's plan are waiting for you.\n"
            "Need anything else? Try these commands:\n"
            "  /help - See all bot commands\n"
            "  /feedback - Report bugs or send ideas"
        )

    if invite_code:
        welcome_text += f"\n\n🎯 *You've been invited to a competition!* Code: `{invite_code}`"

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command — list available commands."""
    help_text = (
        "🤖 *claudeGYM Bot Commands*\n\n"
        "/start - Open the app or see intro\n"
        "/compete - View and manage competitions\n"
        "/stats - View your streaks and progress\n"
        "/plan - See your weekly AI plan\n"
        "/nutrition - Open the meal tracker\n"
        "/feedback - Submit a bug report or idea\n"
        "/help - Show this message\n\n"
        "Send me a photo to get AI posture and face analysis!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ── Feedback Conversation Handler ──────────────────────────────────────────

FEEDBACK_CATEGORY, FEEDBACK_TEXT = range(2)

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the feedback flow."""
    keyboard = [
        [
            InlineKeyboardButton("🐞 Bug Report", callback_data="feedback_bug"),
            InlineKeyboardButton("💡 Idea/Feature", callback_data="feedback_idea")
        ],
        [
            InlineKeyboardButton("⭐ Praise", callback_data="feedback_praise"),
            InlineKeyboardButton("❓ Other", callback_data="feedback_other")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="feedback_cancel")
        ]
    ]
    await update.message.reply_text(
        "What kind of feedback do you want to share?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return FEEDBACK_CATEGORY

async def feedback_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "feedback_cancel":
        await query.edit_message_text("Feedback cancelled.")
        return ConversationHandler.END
        
    category = query.data.split("_")[1]
    context.user_data["feedback_category"] = category
    
    cat_emoji = {"bug": "🐞", "idea": "💡", "praise": "⭐", "other": "❓"}.get(category, "")
    
    await query.edit_message_text(
        f"{cat_emoji} You selected *{category.title()}*.\n\n"
        "Please type your feedback message below:",
        parse_mode="Markdown"
    )
    return FEEDBACK_TEXT

async def feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the feedback text and save/forward it."""
    message = update.message.text
    category = context.user_data.get("feedback_category", "other")
    user = update.effective_user
    
    # Save and forward
    try:
        from backend.config import get_settings
        from backend.models.database import get_session_factory, User, Feedback
        from backend.services.notification_service import forward_feedback_to_admin
        
        settings = get_settings()
        SessionLocal = get_session_factory(settings.database_url)
        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.telegram_id == user.id).first()
            user_id = db_user.id if db_user else 1  # Fallback if somehow not in DB
            
            # Save to DB
            entry = Feedback(
                user_id=user_id,
                category=category,
                message=message,
                page="bot",
            )
            db.add(entry)
            db.commit()
            
            # Forward to admin
            import asyncio
            asyncio.create_task(forward_feedback_to_admin(
                user_name=user.first_name,
                username=user.username,
                telegram_id=user.id,
                category=category,
                message=message,
                page="bot",
            ))
            
        finally:
            db.close()
            
        await update.message.reply_text(
            "✅ *Feedback submitted!* Thanks for helping improve claudeGYM.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Failed to process bot feedback: %s", e)
        await update.message.reply_text("Sorry, there was an error saving your feedback. Please try again later.")
        
    return ConversationHandler.END

async def feedback_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the feedback conversation."""
    await update.message.reply_text("Feedback cancelled.")
    return ConversationHandler.END


async def compete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /compete — show competition info."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Open Competitions",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?page=compete"),
        )],
    ])

    await update.message.reply_text(
        "*Competitions*\n\n"
        "Challenge your friends! Create a competition and share the invite link.\n\n"
        "Score is based on:\n"
        "  Task completion percentage\n"
        "  Streak bonus (up to +20)\n"
        "  Consistency bonus (up to +10)\n\n"
        "Open the app to create or join a competition.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats — show quick stats."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "View Full Dashboard",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?page=progress"),
        )],
    ])

    await update.message.reply_text(
        "Open the app to see your full stats, streaks, and progress.",
        reply_markup=keyboard,
    )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /plan — show current week plan summary."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "View Weekly Plan",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?page=assistant"),
        )],
    ])

    await update.message.reply_text(
        "*Your Weekly Plan*\n\n"
        "Open the app to view your AI-generated weekly plan, "
        "track progress, and manage your tasks.\n\n"
        "Plans are auto-generated every Sunday evening based on your "
        "metrics, photo analysis, and completion history.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def nutrition_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nutrition — show nutrition page."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Open Nutrition Tracker",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?page=nutrition"),
        )],
    ])

    await update.message.reply_text(
        "*Nutrition Tracker*\n\n"
        "Search foods from USDA & Open Food Facts databases. "
        "Log your meals and track calories, protein, carbs & fat against AI-set targets.\n\n"
        "Open the app to log your meals.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — prompt to upload via the app."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Upload Photos for AI Analysis",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?page=photos"),
        )],
    ])

    await update.message.reply_text(
        "To get your personalized AI plan, upload your photos through the app. "
        "Take a front body shot, side shot, and face photo for the best analysis.",
        reply_markup=keyboard,
    )


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer pre-checkout query — always OK for Stars subscriptions."""
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate Pro after successful Stars payment."""
    tg_user = update.effective_user
    try:
        from backend.config import get_settings
        from backend.models.database import get_session_factory, User
        from backend.routers.subscriptions import activate_pro_from_stars

        settings = get_settings()
        SessionLocal = get_session_factory(settings.database_url)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == tg_user.id).first()
            if user:
                activate_pro_from_stars(db, user.id)
                await update.message.reply_text(
                    "Pro activated! All Pro features are now unlocked. Open the app to get started.",
                )
            else:
                logger.warning("Stars payment from unknown user %s", tg_user.id)
        finally:
            db.close()
    except Exception as e:
        logger.error("Failed to activate Pro for user %s: %s", tg_user.id, e)


async def post_init(application: Application):
    """Set menu button after bot starts."""
    if WEBAPP_URL:
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="claudeGYM",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
        except Exception as e:
            logger.warning("Could not set menu button: %s", e)


def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not WEBAPP_URL:
        print("Warning: WEBAPP_URL not set. Bot will work but mini app links won't function.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("compete", compete_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("nutrition", nutrition_command))
    
    # Feedback flow
    feedback_conv = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_start)],
        states={
            FEEDBACK_CATEGORY: [CallbackQueryHandler(feedback_category, pattern="^feedback_")],
            FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_text)],
        },
        fallbacks=[CommandHandler("cancel", feedback_cancel)],
    )
    app.add_handler(feedback_conv)
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
