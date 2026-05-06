from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging
import os

from backend.config import get_settings
from backend.models.database import init_db
from backend.routers import users, tasks, plans, competitions, progress, heatmap, nutrition, exercises, health, feedback, subscriptions, coach

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("Sentry initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    if settings.environment == "production" and settings.database_url.startswith("sqlite"):
        raise RuntimeError(
            "SQLite must not be used in production. "
            "Run: fly postgres create && fly postgres attach --app health-transform"
        )
    init_db(settings.database_url)

    # Seed exercise library and local food database
    from backend.models.database import get_session_factory
    from backend.services.exercise_service import seed_exercise_library
    from backend.services.badge_service import seed_badges
    from backend.services.food_seed import seed_food_database
    SessionLocal = get_session_factory(settings.database_url)
    db = SessionLocal()
    try:
        n_ex = seed_exercise_library(db)
        seed_badges(db)
        n_food = seed_food_database(db)
        if n_ex:
            logger.info("Seeded %d exercises into library", n_ex)
        if n_food:
            logger.info("Seeded %d foods into local database", n_food)
    finally:
        db.close()

    # Start background scheduler (weekly plans + daily reminders)
    try:
        from backend.services.scheduler import start_scheduler
        start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.warning("Scheduler failed to start: %s", e)

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    try:
        from backend.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(title="claudeGYM", version="2.0.0", lifespan=lifespan)

_local_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

if settings.environment == "production" and not settings.webapp_url:
    raise RuntimeError(
        "WEBAPP_URL must be set in production. "
        "Set WEBAPP_URL in your .env and restart."
    )

if settings.webapp_url:
    _origin = settings.webapp_url.rstrip("/").strip()
    _allowed_origins = [_origin] + _local_origins
else:
    # Development without a webapp URL — allow localhost only, no wildcard
    _allowed_origins = _local_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(base_dir, "frontend")
uploads_dir = os.path.join(base_dir, "uploads")

app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(plans.router)
app.include_router(competitions.router)
app.include_router(progress.router)
app.include_router(heatmap.router)
app.include_router(nutrition.router)
app.include_router(exercises.router)
app.include_router(health.router)
app.include_router(feedback.router)
app.include_router(subscriptions.router)
app.include_router(coach.router)

# Lazy-import new routers to avoid import errors if dependencies not yet installed
try:
    from backend.routers import supplements, reminders, exercise_sessions
    app.include_router(supplements.router)
    app.include_router(reminders.router)
    app.include_router(exercise_sessions.router)
except ImportError as e:
    logger.warning("Optional routers not loaded: %s", e)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/public/config")
async def public_config():
    """Bootstrap config the frontend needs before authenticating.

    Used by the Telegram-gate screen to build the deep-link button when the page
    is opened in a regular browser instead of the Mini App.
    """
    return {"bot_username": settings.telegram_bot_username}


def _index_response():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"status": "claudeGYM API running", "docs": "/docs"}


@app.get("/")
async def root():
    return _index_response()


@app.get("/index.html")
async def root_index_html():
    """Some clients request /index.html explicitly; avoid 404."""
    return _index_response()


# Static file mounts — API routes use /api/ prefix so no conflicts
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
