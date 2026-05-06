"""Science-backed workout templates — pre-built training splits.

These templates reference exercises by name (matched to ExerciseLibrary at runtime).
Each template encodes the research-backed set/rep/rest prescriptions from:
- Schoenfeld (2016, 2019) hypertrophy meta-analysis
- NSCA Essentials of Strength Training
- Stronger by Science volume recommendations
"""


WORKOUT_TEMPLATES = {
    "Push day": {
        "label": "Push Day — Chest / Shoulders / Triceps",
        "exercises": [
            {"name": "Warm-up: 5 min cardio + arm circles", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Glute bridge warm-up", "key": "g1", "sets": "3x15", "weight": "BW", "xp": 15, "dur": 5, "priority": True,
             "desc": "Activates glutes to fix anterior pelvic tilt."},
            {"name": "Overhead Press", "key": "g2", "sets": "4x6-8", "xp": 20, "dur": 10, "priority": True,
             "desc": "Shoulder width transforms your V-taper silhouette."},
            {"name": "Incline Dumbbell Press", "key": "g3", "sets": "4x8-12", "xp": 15, "dur": 10, "priority": False,
             "desc": "Upper chest thickness. Set bench to exactly 30°."},
            {"name": "Lateral Raise", "key": "g4", "sets": "4x12-15", "xp": 20, "dur": 8, "priority": True,
             "desc": "Side delts = visible width from front. Slow and controlled."},
            {"name": "Cable Fly", "key": "g5", "sets": "3x12-15", "xp": 15, "dur": 8, "priority": False,
             "desc": "Chest isolation with full stretch for depth."},
            {"name": "Tricep Pushdown", "key": "g6", "sets": "3x12-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Arm thickness. Triceps = 2/3 of arm size."},
            {"name": "Face Pull", "key": "g7", "sets": "3x15-20", "xp": 20, "dur": 6, "priority": True,
             "desc": "Posture fix. Rear delts + rotator cuff. Never skip."},
            {"name": "Hanging Leg Raise", "key": "g8", "sets": "3x10-15", "weight": "BW", "xp": 10, "dur": 5, "priority": False,
             "desc": "Lower abs + fixes pelvic tilt belly protrusion."},
        ],
    },
    "Pull day": {
        "label": "Pull Day — Back / Biceps / Rear Delts",
        "exercises": [
            {"name": "Warm-up: 5 min rowing + band pull-aparts", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Pull-up", "key": "g1", "sets": "5x5-8", "weight": "BW", "xp": 25, "dur": 12, "priority": True,
             "desc": "Your #1 exercise. Wide back is the biggest physique changer."},
            {"name": "Barbell Row", "key": "g2", "sets": "4x6-10", "xp": 15, "dur": 10, "priority": False,
             "desc": "Mid-back thickness with strict form."},
            {"name": "Dumbbell Row", "key": "g3", "sets": "3x8-12", "xp": 15, "dur": 8, "priority": False,
             "desc": "Full lat stretch to contraction. Pull elbow to ceiling."},
            {"name": "Face Pull", "key": "g4", "sets": "4x15-20", "xp": 20, "dur": 8, "priority": True,
             "desc": "Double face pulls this week. Extra rear delt work."},
            {"name": "Straight-Arm Pulldown", "key": "g5", "sets": "3x10-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Arms straight, pull bar to hips. Best lat activation."},
            {"name": "Incline Dumbbell Curl", "key": "g6", "sets": "4x10-15", "xp": 10, "dur": 8, "priority": False,
             "desc": "Bicep peak. Incline forces full stretch."},
            {"name": "Hammer Curl", "key": "g7", "sets": "3x8-12", "xp": 10, "dur": 6, "priority": False,
             "desc": "Brachialis thickness. Bigger arms from all angles."},
            {"name": "Dead Bug", "key": "g8", "sets": "3x10/side", "weight": "BW", "xp": 10, "dur": 5, "priority": False,
             "desc": "Core stability without spine loading. Fixes pelvic tilt."},
        ],
    },
    "Legs + core": {
        "label": "Leg Day — Quads / Hams / Glutes / Core",
        "exercises": [
            {"name": "Warm-up: 5 min bike + leg swings", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Squat", "key": "g1", "sets": "4x5-8", "xp": 25, "dur": 12, "priority": True,
             "desc": "Highest testosterone response. Go below parallel."},
            {"name": "Romanian Deadlift", "key": "g2", "sets": "4x8-12", "xp": 20, "dur": 10, "priority": False,
             "desc": "Hamstring + glute. Hinge at hips, feel the stretch."},
            {"name": "Leg Press", "key": "g3", "sets": "3x10-15", "xp": 15, "dur": 8, "priority": False,
             "desc": "Quad volume without lower back strain."},
            {"name": "Bulgarian Split Squat", "key": "g4", "sets": "3x8-12/leg", "xp": 20, "dur": 10, "priority": True,
             "desc": "Best exercise for fixing anterior pelvic tilt."},
            {"name": "Leg Curl", "key": "g5", "sets": "3x10-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Hamstring isolation. Slow on the negative."},
            {"name": "Plank", "key": "g6", "sets": "3x45s", "weight": "BW", "xp": 10, "dur": 5, "priority": False,
             "desc": "Squeeze glutes hard. Core + glute exercise."},
            {"name": "Hip Flexor Stretch", "key": "g7", "sets": "3x45s/side", "weight": "BW", "xp": 20, "dur": 5, "priority": True,
             "desc": "Root cause fix. Tight hip flexors cause pelvic tilt."},
            {"name": "Calf Raise", "key": "g8", "sets": "3x15-20", "weight": "BW", "xp": 10, "dur": 5, "priority": False,
             "desc": "Proportion. Often skipped but very visible."},
        ],
    },
    "Upper body": {
        "label": "Upper Body — Balanced Push & Pull",
        "exercises": [
            {"name": "Warm-up: 5 min jump rope + shoulder dislocates", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Bench Press", "key": "g1", "sets": "4x6-10", "xp": 20, "dur": 10, "priority": True,
             "desc": "Foundational chest strength."},
            {"name": "Barbell Row", "key": "g2", "sets": "4x6-10", "xp": 20, "dur": 10, "priority": True,
             "desc": "Back thickness. Pull to lower chest."},
            {"name": "Dumbbell Shoulder Press", "key": "g3", "sets": "3x8-12", "xp": 15, "dur": 8, "priority": False,
             "desc": "Overhead strength for balanced shoulders."},
            {"name": "Cable Fly", "key": "g4", "sets": "3x12-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Chest stretch and squeeze."},
            {"name": "Lat Pulldown", "key": "g5", "sets": "3x8-12", "xp": 15, "dur": 8, "priority": False,
             "desc": "Lower lat width. Lean back slightly."},
            {"name": "EZ Bar Curl", "key": "g6", "sets": "3x8-12", "xp": 10, "dur": 6, "priority": False,
             "desc": "Bicep mass. Full stretch at bottom."},
            {"name": "Overhead Tricep Extension", "key": "g7", "sets": "3x10-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Long head of tricep. Deep stretch."},
            {"name": "Face Pull", "key": "g8", "sets": "3x15-20", "xp": 20, "dur": 6, "priority": True,
             "desc": "Posture fix. Never skip this."},
        ],
    },
    "Lower + core": {
        "label": "Lower Body + Core — Quads / Glutes / Abs",
        "exercises": [
            {"name": "Warm-up: 5 min bike + hip circles", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Front Squat", "key": "g1", "sets": "4x5-8", "xp": 25, "dur": 12, "priority": True,
             "desc": "Quad emphasis. Upright torso."},
            {"name": "Hip Thrust", "key": "g2", "sets": "4x8-15", "xp": 20, "dur": 10, "priority": True,
             "desc": "Glute builder. Squeeze at top."},
            {"name": "Walking Lunge", "key": "g3", "sets": "3x10-15/leg", "xp": 15, "dur": 8, "priority": False,
             "desc": "Unilateral leg strength. Control each step."},
            {"name": "Leg Extension", "key": "g4", "sets": "3x10-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Quad isolation. Pause at top."},
            {"name": "Calf Raise", "key": "g5", "sets": "3x15-20", "xp": 10, "dur": 5, "priority": False,
             "desc": "Soleus muscle. Slow and controlled."},
            {"name": "Ab Wheel Rollout", "key": "g6", "sets": "3x6-10", "weight": "BW", "xp": 15, "dur": 5, "priority": False,
             "desc": "Full core engagement. Go as far as you can control."},
            {"name": "Russian Twist", "key": "g7", "sets": "3x15-25", "xp": 10, "dur": 5, "priority": False,
             "desc": "Obliques. Twist with control, not speed."},
            {"name": "Hanging Leg Raise", "key": "g8", "sets": "3x8-15", "weight": "BW", "xp": 15, "dur": 5, "priority": False,
             "desc": "Lower abs. Full range of motion."},
        ],
    },
    "Full body": {
        "label": "Full Body — Compound Focus",
        "exercises": [
            {"name": "Warm-up: 5 min cardio + dynamic stretches", "key": "gw", "sets": "", "weight": "BW", "is_warmup": True, "xp": 5, "dur": 5, "priority": False},
            {"name": "Deadlift", "key": "g1", "sets": "4x4-6", "xp": 25, "dur": 12, "priority": True,
             "desc": "Full body compound. Keep back neutral."},
            {"name": "Incline Dumbbell Press", "key": "g2", "sets": "3x8-12", "xp": 15, "dur": 8, "priority": False,
             "desc": "Upper chest and front delts."},
            {"name": "Pull-up", "key": "g3", "sets": "4x5-8", "weight": "BW", "xp": 20, "dur": 10, "priority": True,
             "desc": "Back + biceps in one movement."},
            {"name": "Leg Press", "key": "g4", "sets": "3x10-15", "xp": 15, "dur": 8, "priority": False,
             "desc": "Heavy leg volume without spinal load."},
            {"name": "Lateral Raise", "key": "g5", "sets": "3x12-15", "xp": 10, "dur": 6, "priority": False,
             "desc": "Cap those delts. Slow controlled reps."},
            {"name": "Seated Cable Row", "key": "g6", "sets": "3x8-12", "xp": 15, "dur": 8, "priority": False,
             "desc": "Mid-back. Squeeze shoulder blades."},
            {"name": "Plank", "key": "g7", "sets": "3x60s", "weight": "BW", "xp": 10, "dur": 5, "priority": False,
             "desc": "Core stability. Squeeze everything."},
            {"name": "Cool-down stretches", "key": "g8", "sets": "5 min", "weight": "", "xp": 5, "dur": 5, "priority": False,
             "desc": "Full body stretch. Hold each position 30s."},
        ],
    },
}


def get_template(focus_name: str) -> dict:
    """Get a workout template by focus name, with fallback to Push day."""
    return WORKOUT_TEMPLATES.get(focus_name, WORKOUT_TEMPLATES["Push day"])


def get_template_exercises(focus_name: str) -> list[dict]:
    """Get the exercise list for a template, formatted for task generation."""
    template = get_template(focus_name)
    return template["exercises"]
