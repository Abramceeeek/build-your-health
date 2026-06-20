from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Text, Boolean,
    DateTime, ForeignKey, Index, create_engine, JSON,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)  # nullable: email/Apple/Google accounts have no Telegram id
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)  # scrypt; only for email/password accounts
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), default="")
    username = Column(String(100), default="")
    photo_url = Column(Text, default="")
    ovr_rating = Column(Float, default=0.0)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    tier = Column(String(20), default="Bronze")
    streak_days = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    streak_freezes = Column(Integer, default=1)
    last_active_date = Column(String(10), default="")
    joined_at = Column(DateTime, default=utcnow)
    is_registered = Column(Boolean, default=False)
    registration_completed_at = Column(DateTime, default=None)
    last_truth_confirmed_at = Column(DateTime, default=None)
    registration_data_json = Column(JSON, default=None)
    face_transform_subscribed = Column(Boolean, default=False)
    memory_json = Column(JSON, default=None)
    sex = Column(String(10), default=None)          # "male" | "female" — backfilled from registration_data_json
    date_of_birth = Column(String(10), default=None)  # YYYY-MM-DD
    sync_token = Column(String(64), default=None, unique=True)  # SHA-256 hash of the Apple Watch Shortcut token (never plaintext)
    referred_by = Column(Integer, default=None)  # referrer user id (set once on registration)
    timezone_offset = Column(Integer, nullable=False, server_default="0", default=0)  # minutes east of UTC; 0 = UTC
    nudge_log_json = Column(JSON, default=None)  # {scheduler_job_id: "YYYY-MM-DD"} last local day each daily nudge fired

    photos = relationship("UserPhoto", back_populates="user", cascade="all, delete-orphan")
    plans = relationship("UserPlan", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("DailyTask", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="user", cascade="all, delete-orphan")
    habit_trackers = relationship("HabitTracker", back_populates="user", cascade="all, delete-orphan")
    competition_memberships = relationship("CompetitionMember", back_populates="user", cascade="all, delete-orphan")
    metrics = relationship("UserMetrics", back_populates="user", cascade="all, delete-orphan")
    weight_logs = relationship("ExerciseWeightLog", back_populates="user", cascade="all, delete-orphan")
    nutrition_logs = relationship("NutritionLog", back_populates="user", cascade="all, delete-orphan")
    nutrition_targets = relationship("NutritionTarget", back_populates="user", cascade="all, delete-orphan")
    weekly_cycles = relationship("WeeklyPlanCycle", back_populates="user", cascade="all, delete-orphan")
    badges = relationship("UserBadge", back_populates="user", cascade="all, delete-orphan")
    health_logs = relationship("DailyHealthLog", back_populates="user", cascade="all, delete-orphan")
    exercise_sessions = relationship("ExerciseSession", back_populates="user", cascade="all, delete-orphan")
    supplement_logs = relationship("SupplementLog", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("UserReminder", back_populates="user", cascade="all, delete-orphan")
    readiness_scores = relationship("ReadinessScore", back_populates="user", cascade="all, delete-orphan")
    volume_logs = relationship("VolumeLoadLog", back_populates="user", cascade="all, delete-orphan")
    cycle_logs = relationship("CycleLog", back_populates="user", cascade="all, delete-orphan")
    body_measurements = relationship("BodyMeasurementLog", back_populates="user", cascade="all, delete-orphan")


class UserPhoto(Base):
    __tablename__ = "user_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    photo_type = Column(String(20), nullable=False)  # body_front, body_side, body_back, face
    file_path = Column(Text, nullable=False)
    ai_analysis_json = Column(JSON, default=None)
    uploaded_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="photos")


class UserPlan(Base):
    __tablename__ = "user_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(String(10), nullable=False)
    plan_json = Column(JSON, nullable=False)
    analysis_json = Column(JSON, default=None)
    status = Column(String(20), default="active")  # active, completed, replaced
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="plans")

    __table_args__ = (
        Index("ix_user_plans_user_week", "user_id", "week_start"),
    )


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("user_plans.id"), nullable=True)
    date = Column(String(10), nullable=False)
    section = Column(String(30), nullable=False)  # morning, gym, evening, nutrition, sleep, face
    task_key = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    category = Column(String(20), default="health")  # health, fitness, sleep, face
    priority = Column(Boolean, default=False)
    difficulty = Column(String(10), default="normal")  # easy, normal, hard
    duration_minutes = Column(Integer, default=0)
    exercise_sets = Column(String(30), default="")
    exercise_weight = Column(String(30), default="")
    actual_weight_used = Column(String(30), default="")
    exercise_library_id = Column(Integer, ForeignKey("exercise_library.id"), nullable=True)
    xp_reward = Column(Integer, default=10)
    swap_count = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, default=None)
    skipped_reason = Column(String(50), default=None)
    duration_min = Column(Integer, default=None)
    sort_order = Column(Integer, default=0)

    user = relationship("User", back_populates="tasks")

    __table_args__ = (
        Index("ix_daily_tasks_user_date", "user_id", "date"),
        Index("ix_daily_tasks_user_date_section", "user_id", "date", "section"),
    )


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    invite_code = Column(String(20), unique=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    comp_type = Column(String(20), default="weekly")  # weekly, monthly, sprint
    challenge_type = Column(String(20), default="classic")  # classic, consistent, streak, nutrition, strength
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    max_members = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    members = relationship("CompetitionMember", back_populates="competition", cascade="all, delete-orphan")


class CompetitionMember(Base):
    __tablename__ = "competition_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Float, default=0.0)
    tasks_completed = Column(Integer, default=0)
    tasks_total = Column(Integer, default=0)
    streak_bonus = Column(Float, default=0.0)
    joined_at = Column(DateTime, default=utcnow)

    competition = relationship("Competition", back_populates="members")
    user = relationship("User", back_populates="competition_memberships")

    __table_args__ = (
        Index("ix_comp_members_comp_user", "competition_id", "user_id", unique=True),
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    achievement_type = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="")
    unlocked_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="achievements")


class UserMetrics(Base):
    __tablename__ = "user_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    body_fat_pct = Column(Float, nullable=True)
    neck_cm = Column(Float, nullable=True)
    chest_cm = Column(Float, nullable=True)
    waist_cm = Column(Float, nullable=True)
    hips_cm = Column(Float, nullable=True)
    bicep_cm = Column(Float, nullable=True)
    thigh_cm = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=utcnow)
    notes = Column(Text, default="")

    user = relationship("User", back_populates="metrics")

    __table_args__ = (
        Index("ix_user_metrics_user_date", "user_id", "recorded_at"),
    )


class DailyHealthLog(Base):
    __tablename__ = "daily_health_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    water_glasses = Column(Integer, default=0)
    sleep_hours = Column(Float, default=0)
    steps = Column(Integer, default=0)
    mood = Column(Integer, default=0)
    supplements_taken = Column(Boolean, default=False)
    notes = Column(Text, default="")
    # Wearable / smartwatch data
    active_calories = Column(Integer, default=0)    # from Apple Watch / Fitbit etc
    resting_hr = Column(Integer, default=0)         # resting heart rate bpm
    floors_climbed = Column(Integer, default=0)
    wearable_source = Column(String(30), default="")  # apple_watch|fitbit|samsung|manual
    exercise_calories = Column(Integer, default=0)  # auto-calculated from exercise sessions
    # Sleep quality fields (auto-calculated from wearable or manual input)
    sleep_score = Column(Float, default=None)         # 0–100 composite sleep quality
    sleep_deep_pct = Column(Float, default=None)      # fraction deep sleep (0.0–1.0)
    sleep_rem_pct = Column(Float, default=None)       # fraction REM sleep (0.0–1.0)
    sleep_bedtime = Column(String(5), default=None)   # "HH:MM" bedtime
    hrv = Column(Float, default=None)                 # HRV RMSSD ms (from wearable)
    vo2max = Column(Float, default=None)              # ml/kg/min from wearable or HUNT estimate
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="health_logs")

    __table_args__ = (
        Index("ix_daily_health_user_date", "user_id", "date", unique=True),
    )


class HabitTracker(Base):
    __tablename__ = "habit_trackers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    habit_name = Column(String(50), nullable=False)
    quit_date = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="habit_trackers")


class ExerciseLibrary(Base):
    __tablename__ = "exercise_library"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    instructions_json = Column(JSON, default=None)
    muscle_groups = Column(JSON, default=None)
    common_mistakes = Column(JSON, default=None)
    image_url = Column(Text, default="")
    difficulty = Column(String(20), default="intermediate")
    equipment_needed = Column(JSON, default=None)
    # Calorie calculation and AI split matching
    calories_per_min = Column(Float, default=5.0)   # avg kcal/min at moderate intensity
    exercise_type = Column(String(20), default="compound")  # compound|isolation|cardio|stretch|isometric
    split_tags = Column(JSON, default=None)  # ["push", "chest_shoulder"]
    # ── Science-backed enrichment fields ──────────────────────────────────
    emg_rank = Column(Integer, default=0)            # activation efficiency rank within muscle group (1=highest)
    muscle_primary = Column(JSON, default=None)      # ["Pectoralis Major"] — anatomical primary movers
    muscle_secondary = Column(JSON, default=None)    # ["Anterior Deltoid", "Triceps"] — synergists
    reps_min = Column(Integer, default=6)            # hypertrophy default min
    reps_max = Column(Integer, default=12)           # hypertrophy default max
    rest_seconds = Column(Integer, default=120)      # recommended rest between sets
    tempo_eccentric = Column(Integer, default=3)     # lowering phase in seconds
    tempo_concentric = Column(Integer, default=1)    # lifting phase in seconds
    starting_weight_mult_male = Column(Float, default=0.30)    # BW multiplier for 1RM estimate
    starting_weight_mult_female = Column(Float, default=0.20)  # BW multiplier for 1RM estimate
    weight_coefficients_json = Column(JSON, default=None)      # {"beginner": 0.4, "intermediate": 0.8, "advanced": 1.2}
    posture_correction_tags = Column(JSON, default=None)  # ["anterior_pelvic_tilt", "rounded_shoulders"]
    progressions = Column(JSON, default=None)        # ["Paused Bench Press", "Close-Grip Bench"]
    regressions = Column(JSON, default=None)         # ["Push-up", "Machine Chest Press"]


class ExerciseWeightLog(Base):
    __tablename__ = "exercise_weight_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=True)
    exercise_name = Column(String(100), nullable=False)
    date = Column(String(10), nullable=False)
    recommended_weight = Column(String(30), default="")
    actual_weight = Column(String(30), default="")
    sets_completed = Column(String(30), default="")
    notes = Column(Text, default="")
    recorded_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="weight_logs")

    __table_args__ = (
        Index("ix_weight_logs_user_date", "user_id", "date"),
    )


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    meal_type = Column(String(20), default="snack")
    food_name = Column(String(200), nullable=False)
    quantity_grams = Column(Float, nullable=False)
    calories = Column(Float, default=0)
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    fibre_g = Column(Float, default=0)
    source = Column(String(20), default="")
    source_id = Column(String(30), default="")
    logged_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="nutrition_logs")

    __table_args__ = (
        Index("ix_nutrition_logs_user_date", "user_id", "date"),
    )


class NutritionTarget(Base):
    __tablename__ = "nutrition_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(String(10), nullable=False)
    daily_calories = Column(Float, default=0)
    daily_protein_g = Column(Float, default=0)
    daily_carbs_g = Column(Float, default=0)
    daily_fat_g = Column(Float, default=0)
    daily_fibre_g = Column(Float, default=0)
    meal_timing_json = Column(JSON, default=None)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="nutrition_targets")

    __table_args__ = (
        Index("ix_nutrition_targets_user_week", "user_id", "week_start"),
    )


class FoodCache(Base):
    __tablename__ = "food_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False)
    source_id = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    nutrients_per_100g_json = Column(JSON, nullable=False)
    last_fetched = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_food_cache_source", "source", "source_id", unique=True),
    )


class WeeklyPlanCycle(Base):
    __tablename__ = "weekly_plan_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(String(10), nullable=False)
    input_context_json = Column(JSON, default=None)
    output_plan_json = Column(JSON, default=None)
    status = Column(String(20), default="pending")
    generated_at = Column(DateTime, default=None)
    notified = Column(Boolean, default=False)

    user = relationship("User", back_populates="weekly_cycles")

    __table_args__ = (
        Index("ix_weekly_cycles_user_week", "user_id", "week_start"),
    )


class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    badge_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="")
    category = Column(String(30), default="completion")
    rarity = Column(String(20), default="common")
    ovr_bonus = Column(Float, default=0.0)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    unlocked_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="badges")
    badge = relationship("Badge")

    __table_args__ = (
        Index("ix_user_badges_user_badge", "user_id", "badge_id", unique=True),
    )


class ExerciseSession(Base):
    """Records a full exercise session (set-by-set) for a gym task with timer data."""
    __tablename__ = "exercise_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=True)
    date = Column(String(10), nullable=False)
    exercise_name = Column(String(100), nullable=False)
    sets_log_json = Column(JSON, default=None)   # [{set:1, reps:10, weight:"40kg", duration_s:45}, ...]
    rest_seconds_total = Column(Integer, default=0)
    total_duration_s = Column(Integer, default=0)
    calories_burned = Column(Float, default=0)
    user_weight_kg = Column(Float, default=75)   # snapshot at time of session for MET calc
    started_at = Column(DateTime, default=None)
    finished_at = Column(DateTime, default=None)

    user = relationship("User", back_populates="exercise_sessions")

    __table_args__ = (
        Index("ix_exercise_sessions_user_date", "user_id", "date"),
    )


class SupplementLog(Base):
    """Daily supplement intake log (creatine, whey, BCAAs, etc.)."""
    __tablename__ = "supplement_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    supplement_name = Column(String(50), nullable=False)   # creatine|whey|bcaa|omega3|zinc|magnesium
    dose_g = Column(Float, default=0)
    taken_at = Column(DateTime, default=utcnow)
    notes = Column(Text, default="")

    user = relationship("User", back_populates="supplement_logs")

    __table_args__ = (
        Index("ix_supplement_logs_user_date", "user_id", "date"),
    )


class UserReminder(Base):
    """Scheduled Telegram reminder preferences per user."""
    __tablename__ = "user_reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reminder_type = Column(String(30), nullable=False)  # meal_breakfast|meal_lunch|meal_dinner|workout|supplement|sleep|water
    time_hhmm = Column(String(5), nullable=False)        # e.g. "08:30"
    timezone_offset = Column(Integer, default=0)         # offset from UTC in minutes (e.g. +300 = UTC+5)
    is_active = Column(Boolean, default=True)
    days_of_week = Column(JSON, default=[0,1,2,3,4,5,6]) # 0=Mon, 6=Sun
    last_sent_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="reminders")

    __table_args__ = (
        Index("ix_user_reminders_user", "user_id"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(20), default="other")   # bug | idea | praise | other
    rating = Column(Integer, nullable=True)           # 1-5
    message = Column(Text, nullable=False)
    page = Column(String(40), default="")
    submitted_at = Column(DateTime, default=utcnow)


class CoachMessage(Base):
    """Free-form coach chat messages plus templated morning/evening briefs."""
    __tablename__ = "coach_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(12), nullable=False)         # user | assistant | system
    body = Column(Text, nullable=False)
    flagged_injury = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_coach_messages_user_created", "user_id", "created_at"),
    )


class ReadinessScore(Base):
    """Daily composite readiness/recovery score (0–100) computed from health log data."""
    __tablename__ = "readiness_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    score = Column(Float, nullable=False)             # overall 0–100
    sleep_score = Column(Float, default=0)            # component
    rhr_score = Column(Float, default=0)              # component
    hrv_score = Column(Float, default=0)              # component
    mood_score = Column(Float, default=0)             # component
    breakdown_json = Column(JSON, default=None)       # {"sleep": 72, "rhr": 68, ...}
    computed_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="readiness_scores")

    __table_args__ = (
        Index("ix_readiness_user_date", "user_id", "date", unique=True),
    )


class VolumeLoadLog(Base):
    """Weekly volume load per muscle group — used for deload detection."""
    __tablename__ = "volume_load_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(String(10), nullable=False)   # Monday of the week
    muscle_group = Column(String(20), nullable=False) # PUSH | PULL | LEGS | CORE
    total_load = Column(Float, default=0)             # Σ sets×reps×weight_kg
    session_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="volume_logs")

    __table_args__ = (
        Index("ix_volume_user_week_muscle", "user_id", "week_start", "muscle_group", unique=True),
    )


class CycleLog(Base):
    """Menstrual cycle tracking — gated to users with sex == 'female'."""
    __tablename__ = "cycle_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_period_start = Column(String(10), nullable=False)  # YYYY-MM-DD
    cycle_length = Column(Integer, default=28)              # days
    logged_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="cycle_logs")

    __table_args__ = (
        Index("ix_cycle_logs_user", "user_id"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    tier = Column(String(20), default="free")        # free | pro
    status = Column(String(20), default="trialing")  # trialing | active | canceled | free
    trial_ends_at = Column(DateTime, default=None)
    current_period_end = Column(DateTime, default=None)
    provider = Column(String(20), default="")        # stars | stripe | manual
    provider_sub_id = Column(String(100), default="")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class BodyMeasurementLog(Base):
    __tablename__ = "body_measurement_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # composite indexes below cover user_id
    key = Column(String(80), nullable=False)   # e.g. "bicep_flexed_left", "waist_navel"
    value = Column(Float, nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="body_measurements")

    __table_args__ = (
        Index("ix_bml_user_key", "user_id", "key"),
        Index("ix_bml_user_date", "user_id", "date"),
    )


_engine = None
_SessionLocal = None


def get_engine(database_url: str = "sqlite:///./health_transform.db"):
    global _engine
    if _engine is None:
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(database_url, connect_args=connect_args, echo=False)
    return _engine


def get_session_factory(database_url: str = "sqlite:///./health_transform.db"):
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def init_db(database_url: str = "sqlite:///./health_transform.db"):
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine
