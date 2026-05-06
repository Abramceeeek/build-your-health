import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from backend.auth import get_current_user
from backend.routers.users import get_db, get_or_create_user
from backend.models.database import DailyTask, ExerciseLibrary, User, UserPlan
from backend.models.schemas import TaskResponse, DayTasksResponse, TaskToggle
from backend.services.workout_templates import WORKOUT_TEMPLATES, get_template_exercises

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Gym day schedules keyed by number of gym days per week
GYM_SCHEDULES = {
    2: [0, 3],                  # Mon, Thu
    3: [0, 2, 4],               # Mon, Wed, Fri
    4: [0, 1, 3, 4],            # Mon, Tue, Thu, Fri
    5: [0, 1, 2, 3, 4],         # Mon-Fri
    6: [0, 1, 2, 3, 4, 5],      # Mon-Sat
}

# Workout focus cycles — rotates through these based on which gym day of the week it is
FOCUS_CYCLE = ["Push day", "Pull day", "Legs + core", "Upper body", "Lower + core", "Full body"]


def _get_user_schedule(user: User, target_date: str | None = None) -> tuple[list[str], list[str]]:
    """Return (day_type_list, day_focus_list) based on user's registration data.

    Supports three schedule types:
      - specific_days: user picked exact weekdays  [0,2,4] = Mon/Wed/Fri
      - every_n_days:  every N-th day from registration date
      - daily:         every day is a gym day
    Falls back to GYM_SCHEDULES if new fields aren't set.
    """
    reg = user.registration_data_json or {}
    schedule_type = reg.get("gym_schedule_type", "specific_days")
    gym_days = reg.get("gym_days_per_week", 3)

    # ── Determine which day-indices are gym days ─────────────────────────
    if schedule_type == "daily":
        gym_indices = list(range(7))

    elif schedule_type == "every_n_days":
        n = reg.get("gym_every_n_days", 2) or 2
        # Calculate based on user's registration date and the target date
        ref_date = user.registration_completed_at or user.joined_at
        if ref_date and target_date:
            try:
                target = datetime.strptime(target_date, "%Y-%m-%d")
                ref = ref_date.replace(tzinfo=None) if ref_date.tzinfo else ref_date
                delta = (target - ref).days
                # Build a full week starting from target's Monday
                today_weekday = target.weekday()
                monday = target - timedelta(days=today_weekday)
                gym_indices = []
                for i in range(7):
                    day = monday + timedelta(days=i)
                    day_delta = (day - ref).days
                    if day_delta >= 0 and day_delta % n == 0:
                        gym_indices.append(i)
            except Exception:
                gym_indices = GYM_SCHEDULES.get(gym_days, GYM_SCHEDULES[3])
        else:
            gym_indices = GYM_SCHEDULES.get(gym_days, GYM_SCHEDULES[3])

    elif schedule_type == "specific_days":
        specific = reg.get("gym_specific_days")
        if specific and isinstance(specific, list):
            gym_indices = [int(d) for d in specific if 0 <= int(d) <= 6]
        else:
            gym_indices = GYM_SCHEDULES.get(gym_days, GYM_SCHEDULES[3])

    else:
        gym_indices = GYM_SCHEDULES.get(gym_days, GYM_SCHEDULES[3])

    # ── Build day-type and focus arrays ──────────────────────────────────
    day_types = []
    day_focuses = []
    gym_count = 0

    # Check if user has a muscle schedule
    muscle_schedule = reg.get("muscle_schedule")

    for i in range(7):
        if i in gym_indices:
            day_types.append("gym")
            # Key the muscle schedule by the Nth gym session of the week (0, 1, 2...)
            if muscle_schedule and str(gym_count) in muscle_schedule:
                muscles = muscle_schedule[str(gym_count)]
                from backend.services.muscle_workout_builder import MUSCLE_GROUPS
                labels = [MUSCLE_GROUPS.get(m, {}).get("label", m.title()) for m in muscles]
                day_focuses.append(" + ".join(labels))
            else:
                day_focuses.append(FOCUS_CYCLE[gym_count % len(FOCUS_CYCLE)])
            gym_count += 1
        else:
            day_types.append("rest")
            day_focuses.append("Recovery" if gym_count > 0 else "Active rest")

    return day_types, day_focuses

SECTIONS_ORDER = ["morning", "gym", "nutrition", "recovery", "evening", "sleep", "face"]

DEFAULT_MORNING = [
    {"key": "m1", "title": "Cold water 500ml on waking", "desc": "Before phone, before anything. Kickstarts metabolism and reduces puffiness.", "cat": "health", "priority": True, "xp": 15, "dur": 1},
    {"key": "m2", "title": "Ice compress — cheeks + jaw + eyes", "desc": "Wrap 3 ice cubes in thin cloth. Press each cheek 20s, jawline 20s, under-eyes 15s each side. Reduces puffiness and tightens skin.", "cat": "face", "priority": False, "xp": 10, "dur": 2},
    {"key": "m3", "title": "Frozen spoon under-eyes", "desc": "Spoons from freezer, curved side under each eye 15s. Reduces dark circles.", "cat": "face", "priority": False, "xp": 10, "dur": 1},
    {"key": "m4", "title": "Mewing — tongue on palate", "desc": "Press ENTIRE tongue flat against roof of mouth, not just tip. Breathe through nose only. Over months this defines the jawline. Maintain all day.", "cat": "face", "priority": True, "xp": 15, "dur": 0},
    {"key": "m5", "title": "Face oil massage — 3 min", "desc": "2-3 drops of oil. Upward strokes jaw→temples. Knuckle under cheekbone sliding outward. Pinch jawline chin→ears. 3 minutes total.", "cat": "face", "priority": False, "xp": 10, "dur": 3},
    {"key": "m6", "title": "Chin tuck x10", "desc": "Pull chin straight back, hold 5s each. Corrects forward head posture.", "cat": "health", "priority": False, "xp": 10, "dur": 2},
    {"key": "m7", "title": "Skincare — cleanser + moisturiser", "desc": "Cool water wash, pat dry, moisturise. Hydrated skin = sharper features.", "cat": "face", "priority": False, "xp": 10, "dur": 2},
]

DEFAULT_EVENING = [
    {"key": "e1", "title": "Jaw training session — 15 min", "desc": "Dedicated chewing block: hard gum or jaw-trainer device, alternate sides. Builds masseter.", "cat": "face", "priority": False, "xp": 10, "dur": 15},
    {"key": "e2", "title": "Check: nasal breathing all day?", "desc": "Mouth breathing causes facial changes over months. Fix it now.", "cat": "face", "priority": False, "xp": 5, "dur": 0},
    {"key": "e3", "title": "Wall stand — 2 minutes", "desc": "Heels, glutes, shoulders, head touching wall. Resets spine alignment.", "cat": "health", "priority": False, "xp": 10, "dur": 2},
    {"key": "e4", "title": "Water total — hit 2.5-3L?", "desc": "Review intake. If short, drink now. Dehydration = puffy face.", "cat": "health", "priority": True, "xp": 15, "dur": 0},
    {"key": "e5", "title": "No alcohol today", "desc": "Alcohol causes 48hr facial bloating and disrupts sleep quality.", "cat": "health", "priority": True, "xp": 15, "dur": 0},
    {"key": "e6", "title": "Night skincare — oil cleanse + moisturise", "desc": "Massage oil in circles, rinse cool water, moisturise.", "cat": "face", "priority": False, "xp": 10, "dur": 3},
    {"key": "e7", "title": "Phone down 45 min before bed", "desc": "Blue light spikes cortisol. Poor sleep = inflammation + slower fat loss.", "cat": "sleep", "priority": True, "xp": 20, "dur": 0},
    {"key": "e8", "title": "Sleep on your back", "desc": "Side sleeping causes facial asymmetry. Elevated pillow reduces fluid.", "cat": "sleep", "priority": False, "xp": 10, "dur": 0},
    {"key": "e9", "title": "Log tonight's sleep", "desc": "Tap to record hours slept. Aim for 7-9 hours.", "cat": "sleep", "priority": True, "xp": 15, "dur": 0},
]

DEFAULT_GYM_BY_FOCUS = {
    "Push day": [
        {"key": "gw", "title": "Warm-up: 5 min cardio + arm circles", "sets": "", "weight": "", "desc": "Get blood flowing before lifting. Light jog or rowing.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Glute bridge warm-up", "sets": "3x15", "weight": "BW", "desc": "Activates glutes to fix anterior pelvic tilt.", "priority": True, "xp": 15, "dur": 5},
        {"key": "g2", "title": "Overhead press", "sets": "4x8-10", "weight": "30-35kg", "desc": "Shoulder width transforms your V-taper silhouette.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g3", "title": "Incline dumbbell press", "sets": "4x10-12", "weight": "12-16kg", "desc": "Upper chest thickness. Skip flat bench.", "priority": False, "xp": 15, "dur": 10},
        {"key": "g4", "title": "Lateral raises", "sets": "4x12-15", "weight": "6-8kg", "desc": "Side delts = visible width from front. Slow and controlled.", "priority": True, "xp": 20, "dur": 8},
        {"key": "g5", "title": "Cable fly / pec dec", "sets": "3x12", "weight": "15-20kg", "desc": "Chest isolation with full stretch for depth.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g6", "title": "Tricep rope pushdown", "sets": "3x12", "weight": "15-20kg", "desc": "Arm thickness. Triceps = 2/3 of arm size.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g7", "title": "Face pull", "sets": "3x15", "weight": "10-12kg", "desc": "Posture fix. Rear delts + rotator cuff. Never skip.", "priority": True, "xp": 20, "dur": 6},
        {"key": "g8", "title": "Hanging knee raise", "sets": "3x12", "weight": "BW", "desc": "Lower abs + fixes pelvic tilt belly protrusion.", "priority": False, "xp": 10, "dur": 5},
    ],
    "Pull day": [
        {"key": "gw", "title": "Warm-up: 5 min rowing + band pull-aparts", "sets": "", "weight": "", "desc": "Warm up upper back and shoulders before pulling.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Pull-ups or lat pulldown", "sets": "5x6-8", "weight": "BW/50-60kg", "desc": "Your #1 exercise. Wide back is the biggest physique changer.", "priority": True, "xp": 25, "dur": 12},
        {"key": "g2", "title": "Chest-supported row", "sets": "4x10", "weight": "40-50kg", "desc": "Mid-back thickness with no lower back cheating.", "priority": False, "xp": 15, "dur": 10},
        {"key": "g3", "title": "Single-arm dumbbell row", "sets": "3x10/side", "weight": "16-20kg", "desc": "Full lat stretch to contraction. Pull elbow to ceiling.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g4", "title": "Face pull — wide grip", "sets": "4x15", "weight": "10-12kg", "desc": "Double face pulls this week. Extra rear delt work.", "priority": True, "xp": 20, "dur": 8},
        {"key": "g5", "title": "Straight-arm pulldown", "sets": "3x12", "weight": "15-20kg", "desc": "Arms straight, pull bar to hips. Best lat activation.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g6", "title": "Incline dumbbell curl", "sets": "4x10", "weight": "8-12kg", "desc": "Bicep peak. Incline forces full stretch.", "priority": False, "xp": 10, "dur": 8},
        {"key": "g7", "title": "Hammer curl", "sets": "3x12", "weight": "10-14kg", "desc": "Brachialis thickness. Bigger arms from all angles.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g8", "title": "Dead bug", "sets": "3x10/side", "weight": "BW", "desc": "Core stability without spine loading. Fixes pelvic tilt.", "priority": False, "xp": 10, "dur": 5},
    ],
    "Legs + core": [
        {"key": "gw", "title": "Warm-up: 5 min bike + leg swings", "sets": "", "weight": "", "desc": "Warm up hips and knees. Dynamic stretches.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Barbell squat", "sets": "4x8", "weight": "50-60kg", "desc": "Highest testosterone response. Go below parallel.", "priority": True, "xp": 25, "dur": 12},
        {"key": "g2", "title": "Romanian deadlift", "sets": "4x10", "weight": "40-55kg", "desc": "Hamstring + glute. Hinge at hips, feel the stretch.", "priority": False, "xp": 20, "dur": 10},
        {"key": "g3", "title": "Leg press", "sets": "3x12", "weight": "80-100kg", "desc": "Quad volume without lower back strain.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g4", "title": "Bulgarian split squat", "sets": "3x10/leg", "weight": "8-12kg", "desc": "Best exercise for fixing anterior pelvic tilt.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g5", "title": "Leg curl machine", "sets": "3x12", "weight": "25-35kg", "desc": "Hamstring isolation. Slow on the negative.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g6", "title": "Plank — strict", "sets": "3x45s", "weight": "BW", "desc": "Squeeze glutes hard. Core + glute exercise.", "priority": False, "xp": 10, "dur": 5},
        {"key": "g7", "title": "Kneeling hip flexor stretch", "sets": "3x45s/side", "weight": "BW", "desc": "Root cause fix. Tight hip flexors cause pelvic tilt.", "priority": True, "xp": 20, "dur": 5},
        {"key": "g8", "title": "Calf raises", "sets": "3x20", "weight": "BW/30kg", "desc": "Proportion. Often skipped but very visible.", "priority": False, "xp": 10, "dur": 5},
    ],
    "Upper body": [
        {"key": "gw", "title": "Warm-up: 5 min jump rope + shoulder dislocates", "sets": "", "weight": "", "desc": "Full upper body warm-up. Get shoulders mobile.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Bench press", "sets": "4x8", "weight": "50-60kg", "desc": "Foundational chest strength.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g2", "title": "Barbell row", "sets": "4x10", "weight": "40-50kg", "desc": "Back thickness. Pull to lower chest.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g3", "title": "Dumbbell shoulder press", "sets": "3x10", "weight": "12-16kg", "desc": "Overhead strength for balanced shoulders.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g4", "title": "Cable crossover", "sets": "3x12", "weight": "10-15kg", "desc": "Chest stretch and squeeze.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g5", "title": "Lat pulldown — close grip", "sets": "3x12", "weight": "45-55kg", "desc": "Lower lat width. Lean back slightly.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g6", "title": "EZ bar curl", "sets": "3x12", "weight": "15-25kg", "desc": "Bicep mass. Full stretch at bottom.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g7", "title": "Overhead tricep extension", "sets": "3x12", "weight": "12-18kg", "desc": "Long head of tricep. Deep stretch.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g8", "title": "Face pull", "sets": "3x15", "weight": "10-12kg", "desc": "Posture fix. Never skip this.", "priority": True, "xp": 20, "dur": 6},
    ],
    "Lower + core": [
        {"key": "gw", "title": "Warm-up: 5 min bike + hip circles", "sets": "", "weight": "", "desc": "Warm up hip joints and quads before heavy lifts.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Front squat", "sets": "4x8", "weight": "40-50kg", "desc": "Quad emphasis. Upright torso.", "priority": True, "xp": 25, "dur": 12},
        {"key": "g2", "title": "Hip thrust", "sets": "4x10", "weight": "50-70kg", "desc": "Glute builder. Squeeze at top.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g3", "title": "Walking lunges", "sets": "3x12/leg", "weight": "10-16kg", "desc": "Unilateral leg strength. Control each step.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g4", "title": "Leg extension", "sets": "3x12", "weight": "30-40kg", "desc": "Quad isolation. Pause at top.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g5", "title": "Seated calf raise", "sets": "3x15", "weight": "20-30kg", "desc": "Soleus muscle. Slow and controlled.", "priority": False, "xp": 10, "dur": 5},
        {"key": "g6", "title": "Ab wheel rollout", "sets": "3x10", "weight": "BW", "desc": "Full core engagement. Go as far as you can control.", "priority": False, "xp": 15, "dur": 5},
        {"key": "g7", "title": "Russian twist", "sets": "3x20", "weight": "5-10kg", "desc": "Obliques. Twist with control, not speed.", "priority": False, "xp": 10, "dur": 5},
        {"key": "g8", "title": "Hanging leg raise", "sets": "3x10", "weight": "BW", "desc": "Lower abs. Full range of motion.", "priority": False, "xp": 15, "dur": 5},
    ],
    "Full body": [
        {"key": "gw", "title": "Warm-up: 5 min cardio + dynamic stretches", "sets": "", "weight": "", "desc": "Full body warm-up. Jumping jacks, arm circles, leg swings.", "priority": False, "xp": 5, "dur": 5, "is_warmup": True},
        {"key": "g1", "title": "Deadlift", "sets": "4x6", "weight": "60-80kg", "desc": "Full body compound. Keep back neutral.", "priority": True, "xp": 25, "dur": 12},
        {"key": "g2", "title": "Incline bench press", "sets": "3x10", "weight": "40-50kg", "desc": "Upper chest and front delts.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g3", "title": "Chin-ups", "sets": "4x6-8", "weight": "BW", "desc": "Back + biceps in one movement.", "priority": True, "xp": 20, "dur": 10},
        {"key": "g4", "title": "Leg press", "sets": "3x12", "weight": "80-100kg", "desc": "Heavy leg volume without spinal load.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g5", "title": "Dumbbell lateral raise", "sets": "3x15", "weight": "6-8kg", "desc": "Cap those delts. Slow controlled reps.", "priority": False, "xp": 10, "dur": 6},
        {"key": "g6", "title": "Cable row", "sets": "3x12", "weight": "35-45kg", "desc": "Mid-back. Squeeze shoulder blades.", "priority": False, "xp": 15, "dur": 8},
        {"key": "g7", "title": "Plank", "sets": "3x60s", "weight": "BW", "desc": "Core stability. Squeeze everything.", "priority": False, "xp": 10, "dur": 5},
        {"key": "g8", "title": "Cool-down stretches", "sets": "5 min", "weight": "", "desc": "Full body stretch. Hold each position 30s.", "priority": False, "xp": 5, "dur": 5},
    ],
}

# Legacy mapping for backward compatibility
DEFAULT_GYM = {
    0: DEFAULT_GYM_BY_FOCUS["Push day"],
    2: DEFAULT_GYM_BY_FOCUS["Pull day"],
    4: DEFAULT_GYM_BY_FOCUS["Legs + core"],
}

DEFAULT_REST = [
    {"key": "r1", "title": "Walk 20-30 min — no phone", "desc": "Fat-burning zone without disrupting muscle recovery.", "cat": "health", "priority": False, "xp": 15, "dur": 25},
    {"key": "r2", "title": "Protein hit — 140g+ today", "desc": "Muscle builds 24/7. Eggs, chicken, Greek yoghurt, cottage cheese.", "cat": "nutrition", "priority": True, "xp": 20, "dur": 0},
    {"key": "r3", "title": "Hip flexor stretch + chest opener", "desc": "Kneeling lunge 45s each side. Doorway chest stretch 30s.", "cat": "health", "priority": False, "xp": 10, "dur": 5},
    {"key": "r4", "title": "Eat lunch with hard / raw food", "desc": "Carrots, apples, raw veg with lunch. Passive jaw training while you eat.", "cat": "face", "priority": False, "xp": 10, "dur": 15},
    {"key": "r5", "title": "Low sodium meals today", "desc": "Salty food causes visible facial puffiness within hours.", "cat": "face", "priority": True, "xp": 15, "dur": 0},
]

DEFAULT_NUT_GYM = [
    {"key": "n1", "title": "Pre-workout meal (1.5 hrs before)", "desc": "Oats + banana + peanut butter OR rice + eggs. 40g carbs + 25g protein.", "cat": "health", "priority": True, "xp": 15, "dur": 0},
    {"key": "n2", "title": "Creatine 5g", "desc": "5g in water or juice daily. Proven, cheap, effective.", "cat": "health", "priority": True, "xp": 10, "dur": 0},
    {"key": "n3", "title": "Post-workout protein (within 45 min)", "desc": "30-40g protein. Whey + banana or chicken + white rice.", "cat": "health", "priority": True, "xp": 15, "dur": 0},
]

DEFAULT_NUT_REST = [
    {"key": "n2", "title": "Creatine 5g", "desc": "Take every day regardless of gym. Works through muscle saturation.", "cat": "health", "priority": True, "xp": 10, "dur": 0},
]


def _day_index_for_date(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.weekday()


def generate_default_tasks_for_day(user_id: int, date_str: str, plan_id: int = None, user: User = None) -> list[DailyTask]:
    """Generate the default set of tasks for a given day, respecting user's gym schedule."""
    day_idx = _day_index_for_date(date_str)

    # Use user-specific schedule or fallback to 3-day default
    if user:
        day_types, day_focuses = _get_user_schedule(user, date_str)
    else:
        day_types = ["gym", "rest", "gym", "rest", "gym", "rest", "rest"]
        day_focuses = ["Push day", "Recovery", "Pull day", "Recovery", "Legs + core", "Active rest", "Full rest"]

    is_gym = day_types[day_idx] == "gym"
    focus = day_focuses[day_idx]

    # Check goals for conditional task inclusion
    reg = (user.registration_data_json or {}) if user else {}
    goals = reg.get("goals", [])
    include_face = "face_improvement" in goals
    include_sleep = "better_sleep" in goals
    include_health = "general_health" in goals or "posture_correction" in goals

    # Keys that require specific goals
    HEALTH_KEYS = {"m1", "m6", "e3", "e4", "e5"}
    ALWAYS_INCLUDE_REST = {"r1", "r2"}  # walking + protein always included

    tasks = []
    order = 0

    # Morning tasks — filter based on goals
    for item in DEFAULT_MORNING:
        if item["cat"] == "face" and not include_face:
            continue
        if item["cat"] == "sleep" and not include_sleep:
            continue
        if item["key"] in HEALTH_KEYS and not include_health:
            continue
        tasks.append(DailyTask(
            user_id=user_id, plan_id=plan_id, date=date_str,
            section="morning", task_key=item["key"], title=item["title"],
            description=item["desc"], category=item["cat"],
            priority=item.get("priority", False), difficulty="normal",
            duration_minutes=item.get("dur", 0), xp_reward=item.get("xp", 10),
            sort_order=order,
        ))
        order += 1

    if is_gym:
        # ── Find which Nth gym day this is ────────────────────────────────
        gym_session_idx = 0
        for i in range(day_idx):
            if day_types[i] == "gym":
                gym_session_idx += 1

        # ── Check for user-defined muscle schedule ──────────────────────
        muscle_schedule = reg.get("muscle_schedule")
        day_muscles = muscle_schedule.get(str(gym_session_idx)) if muscle_schedule else None

        if day_muscles and user:
            # Use muscle-based workout builder
            from backend.dependencies.auth_deps import get_db as _get_db_gen
            from backend.services.muscle_workout_builder import build_workout_for_day
            # We need a db session — the caller should pass one, but for
            # the default-generation path we open a fresh one.
            from backend.config import get_settings
            from backend.models.database import get_session_factory
            _settings = get_settings()
            _Session = get_session_factory(_settings.database_url)
            _db = _Session()
            try:
                gym_tasks = build_workout_for_day(_db, user, date_str, day_muscles, plan_id)
                for gt in gym_tasks:
                    gt.sort_order = order
                    order += 1
                tasks.extend(gym_tasks)
            finally:
                _db.close()
        else:
            # Legacy: use science-backed templates or hardcoded defaults
            if focus in WORKOUT_TEMPLATES:
                gym_exercises = get_template_exercises(focus)
            else:
                gym_exercises = DEFAULT_GYM_BY_FOCUS.get(focus, DEFAULT_GYM_BY_FOCUS["Push day"])
            for item in gym_exercises:
                title = item.get("name") or item.get("title", "")
                desc = item.get("desc", item.get("description", ""))
                tasks.append(DailyTask(
                    user_id=user_id, plan_id=plan_id, date=date_str,
                    section="gym", task_key=item["key"], title=title,
                    description=desc, category="fitness",
                    priority=item.get("priority", False), difficulty="normal",
                    duration_minutes=item.get("dur", 0),
                    exercise_sets=item.get("sets", ""),
                    exercise_weight=item.get("weight", ""),
                    xp_reward=item.get("xp", 10), sort_order=order,
                ))
                order += 1
        for item in DEFAULT_NUT_GYM:
            tasks.append(DailyTask(
                user_id=user_id, plan_id=plan_id, date=date_str,
                section="nutrition", task_key=item["key"], title=item["title"],
                description=item["desc"], category=item["cat"],
                priority=item.get("priority", False), difficulty="normal",
                duration_minutes=item.get("dur", 0), xp_reward=item.get("xp", 10),
                sort_order=order,
            ))
            order += 1
    else:
        for item in DEFAULT_REST:
            if item["cat"] == "face" and not include_face:
                continue
            if item["key"] not in ALWAYS_INCLUDE_REST:
                if item["cat"] == "health" and not include_health:
                    continue
            tasks.append(DailyTask(
                user_id=user_id, plan_id=plan_id, date=date_str,
                section="recovery", task_key=item["key"], title=item["title"],
                description=item["desc"], category=item["cat"],
                priority=item.get("priority", False), difficulty="normal",
                duration_minutes=item.get("dur", 0), xp_reward=item.get("xp", 10),
                sort_order=order,
            ))
            order += 1
        for item in DEFAULT_NUT_REST:
            tasks.append(DailyTask(
                user_id=user_id, plan_id=plan_id, date=date_str,
                section="nutrition", task_key=item["key"], title=item["title"],
                description=item["desc"], category=item["cat"],
                priority=item.get("priority", False), difficulty="normal",
                duration_minutes=item.get("dur", 0), xp_reward=item.get("xp", 10),
                sort_order=order,
            ))
            order += 1

    # Evening tasks — filter based on goals
    for item in DEFAULT_EVENING:
        if item["cat"] == "face" and not include_face:
            continue
        if item["cat"] == "sleep" and not include_sleep:
            continue
        if item["key"] in HEALTH_KEYS and not include_health:
            continue
        tasks.append(DailyTask(
            user_id=user_id, plan_id=plan_id, date=date_str,
            section="evening", task_key=item["key"], title=item["title"],
            description=item["desc"], category=item["cat"],
            priority=item.get("priority", False), difficulty="normal",
            duration_minutes=item.get("dur", 0), xp_reward=item.get("xp", 10),
            sort_order=order,
        ))
        order += 1

    # ─── Posture correction injection ─────────────────────────────────────
    if user:
        from backend.services.posture_protocols import inject_posture_tasks
        posture_tasks = inject_posture_tasks(
            tasks, user, user_id, date_str, plan_id, start_order=order
        )
        tasks.extend(posture_tasks)

    return tasks


@router.get("/today", response_model=DayTasksResponse)
async def get_today_tasks(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _get_day_tasks(db, user, today)


@router.get("/day/{date}", response_model=DayTasksResponse)
async def get_day_tasks(
    date: str,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    return _get_day_tasks(db, user, date)


@router.get("/week")
async def get_week_tasks(
    days_before: int = 0,
    days_after: int = 0,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a window of days for the day-scroller / weekly bars.

    Default (0,0) keeps the legacy behaviour: Monday→Sunday of the current
    UTC week. Pass `days_before` and/or `days_after` to get a window centred
    on today (e.g. 5,5 returns 11 days centred on today).

    Both params are clamped to [0, 14] to keep DB load bounded.
    """
    user = get_or_create_user(db, tg_user)
    today = datetime.now(timezone.utc)

    days_before = max(0, min(int(days_before or 0), 14))
    days_after  = max(0, min(int(days_after  or 0), 14))

    if days_before or days_after:
        start_date = today - timedelta(days=days_before)
        total_days = days_before + days_after + 1
    else:
        start_date = today - timedelta(days=today.weekday())  # this Monday
        total_days = 7

    day_types, day_focuses = _get_user_schedule(user, start_date.strftime("%Y-%m-%d"))

    week_data = []
    for i in range(total_days):
        day = start_date + timedelta(days=i)
        day_date = day.strftime("%Y-%m-%d")
        weekday_idx = day.weekday()  # 0=Mon..6=Sun

        # Schedule arrays are weekday-keyed so reuse them across the window.
        tasks = db.query(DailyTask).filter(
            DailyTask.user_id == user.id, DailyTask.date == day_date
        ).all()

        if not tasks:
            # Always recompute schedule arrays for the window day to handle
            # 'every_n_days' which depends on the date itself.
            day_types_d, day_focuses_d = _get_user_schedule(user, day_date)
            new_tasks = generate_default_tasks_for_day(user.id, day_date, user=user)
            db.add_all(new_tasks)
            db.commit()
            tasks = db.query(DailyTask).filter(
                DailyTask.user_id == user.id, DailyTask.date == day_date
            ).all()
            d_type = day_types_d[weekday_idx]
            d_focus = day_focuses_d[weekday_idx]
        else:
            d_type = day_types[weekday_idx]
            d_focus = day_focuses[weekday_idx]

        done = sum(1 for t in tasks if t.completed)
        total = len(tasks)

        week_data.append({
            "date": day_date,
            "day_name": DAYS[weekday_idx],
            "day_type": d_type,
            "focus": d_focus,
            "done": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
        })

    return {"week": week_data}


def _get_exercise_intelligence(db: Session, user: User, task: DailyTask) -> dict:
    from backend.models.database import UserMetrics
    from backend.services.starting_weight import calculate_starting_weight, get_weight_with_history, format_weight_recommendation

    ex_lib = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{task.title.split()[0]}%")
    ).first()

    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id
    ).order_by(UserMetrics.recorded_at.desc()).first()

    bw = metrics.weight_kg if metrics and metrics.weight_kg else 75.0
    height = 175.0

    reg = user.registration_data_json or {}
    sex = reg.get("gender", "male")
    exp = reg.get("experience_level", "beginner")

    default_weight = 20.0
    rest_seconds = 90
    emg_rank = None

    if ex_lib:
        default_weight = calculate_starting_weight(ex_lib, bw, height, sex, exp)
        rest_seconds = ex_lib.rest_seconds or 90
        emg_rank = ex_lib.emg_rank

    hist = get_weight_with_history(db, task.title, user.id, default_weight)

    coaching = None
    if ex_lib:
        from backend.services.coach_weight import build_coaching_payload
        coaching = build_coaching_payload(db, user.id, ex_lib, default_weight)

    return {
        "last_weight": hist.get("last_weight"),
        "recommended_weight": hist.get("recommended_weight"),
        "progression_note": hist.get("progression_note"),
        "formatted_weight": format_weight_recommendation(hist.get("recommended_weight", default_weight), ex_lib) if ex_lib else f"{hist.get('recommended_weight', default_weight)}kg",
        "rest_seconds": rest_seconds,
        "emg_rank": emg_rank,
        "coaching": coaching,
    }


def _get_day_tasks(db: Session, user: User, date: str) -> DayTasksResponse:
    tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == date
    ).order_by(DailyTask.sort_order).all()

    if not tasks:
        new_tasks = generate_default_tasks_for_day(user.id, date, user=user)
        db.add_all(new_tasks)
        db.commit()
        tasks = db.query(DailyTask).filter(
            DailyTask.user_id == user.id, DailyTask.date == date
        ).order_by(DailyTask.sort_order).all()

    day_idx = _day_index_for_date(date)
    day_types, day_focuses = _get_user_schedule(user, date)
    is_gym = day_types[day_idx] == "gym"

    sections_map = {}
    for t in tasks:
        if t.section not in sections_map:
            sections_map[t.section] = []

        task_data = {
            "id": t.id,
            "task_key": t.task_key,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "priority": t.priority,
            "difficulty": t.difficulty,
            "duration_minutes": t.duration_minutes,
            "exercise_sets": t.exercise_sets,
            "exercise_weight": t.exercise_weight,
            "xp_reward": t.xp_reward,
            "completed": t.completed,
            "sort_order": t.sort_order,
        }

        # ── Enrich gym exercises with intelligence data ──────────────
        if t.section == "gym" and t.task_key != "gw" and (t.exercise_sets or t.exercise_weight):
            task_data.update(_get_exercise_intelligence(db, user, t))

        sections_map[t.section].append(task_data)

    section_labels = {
        "morning": "Morning routine",
        "gym": f"Gym — {day_focuses[day_idx]}",
        "nutrition": "Nutrition",
        "recovery": "Recovery tasks",
        "evening": "Evening routine",
        "sleep": "Sleep",
        "face": "Face protocol",
    }

    sections = []
    for sec_id in SECTIONS_ORDER:
        if sec_id in sections_map:
            sections.append({
                "id": sec_id,
                "label": section_labels.get(sec_id, sec_id.title()),
                "tasks": sections_map[sec_id],
            })

    done = sum(1 for t in tasks if t.completed)
    total = len(tasks)

    return DayTasksResponse(
        date=date,
        day_name=DAYS[day_idx],
        focus=day_focuses[day_idx],
        is_gym_day=is_gym,
        sections=sections,
        stats={
            "done": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
            "xp_earned": sum(t.xp_reward for t in tasks if t.completed),
            "xp_available": sum(t.xp_reward for t in tasks),
        },
    )


@router.post("/toggle/{task_id}")
async def toggle_task(
    task_id: int,
    payload: TaskToggle | None = None,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(db, tg_user)
    task = db.query(DailyTask).filter(
        DailyTask.id == task_id, DailyTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    was_completed = task.completed
    task.completed = not task.completed
    task.completed_at = datetime.now(timezone.utc) if task.completed else None

    # M4 — skipped tasks don't count toward XP loss, streak breaking
    if payload and payload.skip_reason:
        task.skipped_reason = payload.skip_reason
        # treat as not-completed for XP purposes — no XP award, no XP loss
    else:
        task.skipped_reason = None
        if task.completed and not was_completed:
            user.xp += task.xp_reward
        elif was_completed and not task.completed:
            user.xp = max(0, user.xp - task.xp_reward)

    # M14 — walk duration
    if payload and payload.duration_min:
        task.duration_min = payload.duration_min

    db.commit()

    all_tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user.id, DailyTask.date == task.date
    ).all()
    done = sum(1 for t in all_tasks if t.completed)
    total = len(all_tasks)
    all_done = done == total

    return {
        "task_id": task_id,
        "completed": task.completed,
        "xp_change": task.xp_reward if task.completed else -task.xp_reward,
        "total_xp": user.xp,
        "day_done": done,
        "day_total": total,
        "day_pct": round(done / total * 100) if total else 0,
        "day_complete": all_done,
    }


@router.post("/swap/{task_id}")
async def swap_exercise(
    task_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Swap an uncompleted gym exercise for an alternative targeting the same muscles."""
    user = get_or_create_user(db, tg_user)
    task = db.query(DailyTask).filter(
        DailyTask.id == task_id, DailyTask.user_id == user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.section != "gym" or task.completed:
        raise HTTPException(
            status_code=400, detail="Can only swap uncompleted gym exercises"
        )
    if task.swap_count >= 3:
        raise HTTPException(
            status_code=400, detail="Maximum 3 swaps reached for this exercise"
        )

    # Try to find the current exercise in the library for muscle-group matching
    current_name = task.title.lower()
    # Try exact name match first
    current_ex = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(current_name)
    ).first()
    # Fallback: first-word match
    if not current_ex:
        current_ex = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.name.ilike(f"%{current_name.split()[0]}%")
        ).first()

    target_muscles = None
    if current_ex and current_ex.muscle_groups:
        target_muscles = current_ex.muscle_groups

    # Get alternative exercises sharing at least one muscle group
    if target_muscles:
        all_exercises = db.query(ExerciseLibrary).all()
        candidates = [
            ex
            for ex in all_exercises
            if ex.muscle_groups
            and any(m in ex.muscle_groups for m in target_muscles)
            and ex.name.lower() != task.title.lower()
        ]
    else:
        candidates = (
            db.query(ExerciseLibrary)
            .filter(ExerciseLibrary.name != task.title)
            .all()
        )

    if not candidates:
        # Fallback: pick from DEFAULT_GYM_BY_FOCUS exercises for the same focus
        day_idx = _day_index_for_date(task.date)
        _, day_focuses = _get_user_schedule(user, task.date)
        focus = day_focuses[day_idx]
        pool = DEFAULT_GYM_BY_FOCUS.get(focus, [])
        pool = [
            ex
            for ex in pool
            if ex["title"].lower() != task.title.lower()
            and not ex.get("is_warmup")
        ]
        if not pool:
            raise HTTPException(
                status_code=400, detail="No alternative exercises available"
            )
        chosen = random.choice(pool)
        task.title = chosen["title"]
        task.description = chosen["desc"]
        task.exercise_sets = chosen.get("sets", "")
        task.exercise_weight = chosen.get("weight", "")
        task.exercise_library_id = None
    else:
        new_ex = random.choice(candidates)
        task.title = new_ex.name
        task.description = new_ex.description
        task.exercise_library_id = new_ex.id

    task.swap_count += 1
    db.commit()

    return {
        "task_id": task.id,
        "new_title": task.title,
        "new_description": task.description,
        "swap_count": task.swap_count,
        "swaps_remaining": 3 - task.swap_count,
    }


@router.post("/regenerate-week")
async def regenerate_week(
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete uncompleted tasks from today onwards so they regenerate with updated preferences."""
    user = get_or_create_user(db, tg_user)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Delete uncompleted tasks from today onwards
    tasks_to_delete = db.query(DailyTask).filter(
        DailyTask.user_id == user.id,
        DailyTask.date >= today,
        DailyTask.completed == False,
    ).all()

    deleted_count = len(tasks_to_delete)
    for t in tasks_to_delete:
        db.delete(t)
    db.commit()

    return {"status": "regenerated", "deleted_tasks": deleted_count}


@router.get("/{task_id}/alternatives")
async def get_task_alternatives(
    task_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview 3 alternative exercises for a gym task (no swap applied yet)."""
    user = get_or_create_user(db, tg_user)
    task = db.query(DailyTask).filter(
        DailyTask.id == task_id, DailyTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.section != "gym":
        raise HTTPException(status_code=400, detail="Alternatives only available for gym tasks")

    # Match by muscle group using exercise library
    current_ex = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{task.title.split()[0]}%")
    ).first()

    if current_ex and current_ex.muscle_groups:
        target_muscles = current_ex.muscle_groups
        all_exs = db.query(ExerciseLibrary).all()
        candidates = [
            ex for ex in all_exs
            if ex.muscle_groups
            and any(m in ex.muscle_groups for m in target_muscles)
            and ex.name.lower() != task.title.lower()
        ]
    else:
        candidates = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.name != task.title
        ).all()

    # Pick up to 3 random alternatives
    chosen = random.sample(candidates, min(3, len(candidates)))

    # Also pull some from default gym templates for the same day
    if len(chosen) < 3:
        day_idx = _day_index_for_date(task.date)
        _, day_focuses = _get_user_schedule(user, task.date)
        focus = day_focuses[day_idx]
        pool = [
            ex for ex in DEFAULT_GYM_BY_FOCUS.get(focus, [])
            if ex["title"].lower() != task.title.lower() and not ex.get("is_warmup")
        ]
        for ex in random.sample(pool, min(3 - len(chosen), len(pool))):
            chosen.append({
                "name": ex["title"],
                "description": ex["desc"],
                "sets": ex.get("sets", ""),
                "weight": ex.get("weight", ""),
                "muscle_groups": [],
                "source": "default",
            })

    return {
        "task_id": task_id,
        "current_exercise": task.title,
        "swaps_remaining": max(0, 3 - task.swap_count),
        "alternatives": [
            {
                "name": getattr(c, "name", c.get("name", "")),
                "description": getattr(c, "description", c.get("description", "")),
                "sets": getattr(c, "default_sets", c.get("sets", "")),
                "muscle_groups": getattr(c, "muscle_groups", c.get("muscle_groups", [])),
                "gif_url": getattr(c, "gif_url", None),
                "source": getattr(c, "source", "library") if hasattr(c, "name") else c.get("source", "default"),
            }
            for c in chosen
        ],
    }


@router.get("/{task_id}/timer-meta")
async def get_task_timer_metadata(
    task_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return timer configuration for a gym task (sets, rest, exercise type)."""
    user = get_or_create_user(db, tg_user)
    task = db.query(DailyTask).filter(
        DailyTask.id == task_id, DailyTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Parse sets string like "4x10", "3x45s", "3x60s"
    sets_str = task.exercise_sets or "3x10"
    total_sets = 3
    target_reps = "10"
    exercise_type = "compound"
    rest_seconds = 90

    try:
        parts = sets_str.lower().split("x")
        if len(parts) == 2:
            total_sets = int(parts[0])
            target_reps = parts[1]
    except Exception:
        pass

    # Detect isometric/hold exercises
    is_isometric = any(kw in task.title.lower() for kw in ["plank", "hold", "wall sit", "dead hang", "static"])
    if is_isometric:
        exercise_type = "isometric"
        # Extract hold seconds from reps string like "45s", "60s"
        try:
            hold_s = int(target_reps.replace("s", "").replace("/side", "").strip())
            rest_seconds = hold_s  # reuse rest_seconds field for hold duration
        except Exception:
            rest_seconds = 45

    # Look up exercise library for proper type + rest
    ex_lib = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{task.title.split()[0]}%")
    ).first()
    if ex_lib:
        exercise_type = ex_lib.exercise_type or exercise_type
        if not is_isometric:
            # Use enriched rest_seconds from library, default to 90
            rest_seconds = ex_lib.rest_seconds or 90

    return {
        "task_id": task_id,
        "exercise_name": task.title,
        "exercise_type": exercise_type,
        "total_sets": total_sets,
        "target_reps": target_reps,
        "rest_seconds": rest_seconds,
        "is_isometric": is_isometric,
        "is_warmup": task.task_key == "gw",
    }


@router.get("/{task_id}/previous-session")
async def get_previous_session(
    task_id: int,
    tg_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's last recorded set/rep/weight for the same exercise.
    Shows what they lifted last time + progressive overload suggestion.
    """
    from backend.models.database import ExerciseWeightLog, UserMetrics
    from backend.services.starting_weight import (
        calculate_starting_weight, format_weight_recommendation, get_weight_with_history,
    )

    user = get_or_create_user(db, tg_user)
    task = db.query(DailyTask).filter(
        DailyTask.id == task_id, DailyTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Try to find the exercise in the library for starting weight calc
    ex_lib = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(f"%{task.title.split()[0]}%")
    ).first()

    # Get user's body metrics for weight calc
    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user.id
    ).order_by(UserMetrics.recorded_at.desc()).first()

    bw = metrics.weight_kg if metrics and metrics.weight_kg else 75.0
    height = 175.0  # TODO: add height field to UserMetrics

    reg = user.registration_data_json or {}
    sex = reg.get("gender", "male")
    exp = reg.get("experience_level", "beginner")

    # Calculate starting weight
    default_weight = 20.0
    if ex_lib:
        default_weight = calculate_starting_weight(ex_lib, bw, height, sex, exp)

    # Get historical data
    result = get_weight_with_history(db, task.title, user.id, default_weight)
    result["task_id"] = task_id
    result["exercise_name"] = task.title
    result["formatted_weight"] = format_weight_recommendation(
        result["recommended_weight"], ex_lib
    ) if ex_lib else f"{result['recommended_weight']}kg"

    return result
