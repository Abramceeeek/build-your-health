from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- User ---

class UserCreate(BaseModel):
    telegram_id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    photo_url: str = ""


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    first_name: str
    last_name: str
    username: str
    photo_url: str
    ovr_rating: float
    xp: int
    level: int
    tier: str
    streak_days: int
    longest_streak: int
    streak_freezes: int
    joined_at: datetime

    model_config = {"from_attributes": True}


class UserStats(BaseModel):
    ovr_rating: float
    xp: int
    level: int
    tier: str
    streak_days: int
    longest_streak: int
    tasks_completed_today: int
    tasks_total_today: int
    completion_pct: float
    weekly_completion_pct: float


# --- Tasks ---

class TaskToggle(BaseModel):
    task_id: int
    skip_reason: str | None = None
    duration_min: int | None = None


class TaskResponse(BaseModel):
    id: int
    section: str
    task_key: str
    title: str
    description: str
    category: str
    priority: bool
    difficulty: str
    duration_minutes: int
    exercise_sets: str
    exercise_weight: str
    actual_weight_used: str = ""
    exercise_library_id: Optional[int] = None
    xp_reward: int
    completed: bool
    completed_at: Optional[datetime] = None
    sort_order: int

    model_config = {"from_attributes": True}


class DayTasksResponse(BaseModel):
    date: str
    day_name: str
    focus: str
    is_gym_day: bool
    sections: list[dict]
    stats: dict


# --- Plans ---

class PlanGenerateRequest(BaseModel):
    goals: list[str] = []
    experience_level: str = "beginner"
    available_equipment: list[str] = []
    injuries: list[str] = []
    sleep_target_hours: float = 8.0
    gym_days_per_week: int = 3


class PlanResponse(BaseModel):
    id: int
    week_start: str
    status: str
    plan_json: dict
    analysis_json: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Competitions ---

class CompetitionCreate(BaseModel):
    name: str
    comp_type: str = "weekly"
    duration_days: int = 7
    challenge_type: str = "classic"  # classic, consistent, streak, nutrition, strength


class CompetitionJoin(BaseModel):
    invite_code: str


class CompetitionResponse(BaseModel):
    id: int
    name: str
    invite_code: str
    comp_type: str
    start_date: str
    end_date: str
    max_members: int
    is_active: bool
    member_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    telegram_id: int
    first_name: str
    username: str
    score: float
    tasks_completed: int
    tasks_total: int
    completion_pct: float
    streak_bonus: float
    is_self: bool


# --- Achievements ---

class AchievementResponse(BaseModel):
    id: int
    achievement_type: str
    title: str
    description: str
    icon: str
    unlocked_at: datetime

    model_config = {"from_attributes": True}


# --- Habits ---

class HabitCreate(BaseModel):
    habit_name: str
    quit_date: str


class HabitResponse(BaseModel):
    id: int
    habit_name: str
    quit_date: str
    is_active: bool
    days_since: int

    model_config = {"from_attributes": True}


# --- Photos ---

class PhotoResponse(BaseModel):
    id: int
    photo_type: str
    file_path: str
    ai_analysis_json: Optional[dict] = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class AnalysisResponse(BaseModel):
    posture: dict
    body_composition: dict
    facial_analysis: dict
    recommendations: list[str]
    severity_scores: dict


# --- Registration ---

class RegistrationRequest(BaseModel):
    gender: str = "male"  # male or female
    goals: list[str] = []
    experience_level: str = "beginner"
    gym_days_per_week: int = 3
    available_equipment: list[str] = []
    injuries: str = ""
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    # ── Custom gym day scheduling ─────────────────────────────────────────
    gym_schedule_type: str = "specific_days"          # specific_days | every_n_days | daily
    gym_specific_days: Optional[list[int]] = None     # [0,2,4] = Mon/Wed/Fri (0=Mon, 6=Sun)
    gym_every_n_days: Optional[int] = None            # e.g. 2 = every other day
    # ── Muscle schedule per day ───────────────────────────────────────────
    muscle_schedule: Optional[dict[str, list[str]]] = None  # {"0":["chest","biceps"], "2":["back","triceps"]}


class RegistrationStatusResponse(BaseModel):
    is_registered: bool
    truth_confirmed_today: bool


# --- Nutrition ---

class NutritionLogCreate(BaseModel):
    date: str
    meal_type: str = "snack"
    food_name: str
    quantity_grams: float
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    source: str = ""
    source_id: str = ""


class NutritionLogResponse(BaseModel):
    id: int
    date: str
    meal_type: str
    food_name: str
    quantity_grams: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    logged_at: datetime

    model_config = {"from_attributes": True}


class NutritionDailySummary(BaseModel):
    date: str
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    total_fibre: float
    target_calories: float
    target_protein: float
    target_carbs: float
    target_fat: float
    meals: dict[str, list]


class FoodSearchResult(BaseModel):
    source: str
    source_id: str
    name: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fibre_per_100g: float


# --- Exercise Library ---

class ExerciseDetailResponse(BaseModel):
    id: int
    name: str
    description: str
    instructions: Optional[list[str]] = Field(None, validation_alias="instructions_json")
    muscle_groups: Optional[list[str]] = None
    common_mistakes: Optional[list[str]] = None
    image_url: str
    difficulty: str
    equipment_needed: Optional[list[str]] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class WeightLogCreate(BaseModel):
    task_id: Optional[int] = None
    exercise_name: str
    date: str
    recommended_weight: str = ""
    actual_weight: str = ""
    sets_completed: str = ""
    notes: str = ""


class WeightLogResponse(BaseModel):
    id: int
    exercise_name: str
    date: str
    recommended_weight: str
    actual_weight: str
    sets_completed: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


# --- Badges ---

class BadgeResponse(BaseModel):
    id: int
    badge_key: str
    name: str
    description: str
    icon: str
    category: str
    rarity: str
    ovr_bonus: float
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
