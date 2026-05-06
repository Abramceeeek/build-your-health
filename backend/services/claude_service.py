import base64
import json
import os
from typing import Optional

import anthropic

from backend.config import get_settings

PHOTO_ANALYSIS_PROMPT = """You are an expert fitness coach, physiotherapist, and facial aesthetics specialist.

Analyze the provided photos and return a structured JSON assessment. Be specific, actionable, and honest.

Return ONLY valid JSON with this exact structure:
{
  "posture": {
    "anterior_pelvic_tilt": {"detected": true/false, "severity": "none|mild|moderate|severe", "notes": "..."},
    "forward_head": {"detected": true/false, "severity": "none|mild|moderate|severe", "notes": "..."},
    "rounded_shoulders": {"detected": true/false, "severity": "none|mild|moderate|severe", "notes": "..."},
    "lateral_imbalance": {"detected": true/false, "severity": "none|mild|moderate|severe", "notes": "..."},
    "overall_score": 1-10
  },
  "body_composition": {
    "estimated_bf_range": "X-Y%",
    "build_type": "ectomorph|mesomorph|endomorph|mixed",
    "muscle_development": {
      "shoulders": "underdeveloped|average|developed|strong",
      "chest": "underdeveloped|average|developed|strong",
      "back": "underdeveloped|average|developed|strong",
      "arms": "underdeveloped|average|developed|strong",
      "core": "underdeveloped|average|developed|strong",
      "legs": "underdeveloped|average|developed|strong"
    },
    "priority_areas": ["area1", "area2", "area3"],
    "strengths": ["strength1", "strength2"]
  },
  "facial_analysis": {
    "jaw_definition": "weak|average|defined|strong",
    "facial_puffiness": "none|mild|moderate|significant",
    "symmetry": "good|slight_asymmetry|notable_asymmetry",
    "skin_condition": "poor|fair|good|excellent",
    "under_eye_area": "clear|mild_circles|moderate_circles|dark_circles",
    "recommendations": ["rec1", "rec2", "rec3"]
  },
  "recommendations": [
    "Top priority recommendation 1",
    "Recommendation 2",
    "Recommendation 3",
    "Recommendation 4",
    "Recommendation 5"
  ],
  "severity_scores": {
    "posture": 1-10,
    "body_composition": 1-10,
    "facial": 1-10,
    "overall": 1-10
  }
}"""

PLAN_GENERATION_SYSTEM = """You are an elite personal trainer. Generate a personalized 7-day training plan based on the user profile and data in the message.

Return ONLY valid JSON:
{
  "overview": "Brief plan description",
  "gym_schedule": [0, 2, 4],
  "days": {
    "0": {
      "type": "gym|rest",
      "focus": "Push day",
      "gym": [
        {"exercise_name": "Bench Press", "sets": 4, "reps": "6-10", "priority": true},
        {"exercise_name": "Incline Dumbbell Press", "sets": 4, "reps": "8-12", "priority": false}
      ],
      "morning_additions": ["extra task title if needed"],
      "evening_additions": ["extra task title if needed"]
    }
  }
}

Rules:
- Scale difficulty: if completion_rate_pct < 60, use fewer exercises and lighter volume
- If muscle_schedule is provided in user profile: STRICTLY follow it. Session 0 muscles → gym day 0 exercises, session 1 muscles → gym day 1 exercises, etc. Do NOT override with generic push/pull/legs.
- If muscle_schedule is null: use science-backed Push/Pull/Legs or Upper/Lower split based on gym_days_per_week
- Include 5-8 gym exercises per session targeting the specified muscles. Big muscles (chest/back/legs): 4-5 exercises. Small (biceps/triceps): 2-3 exercises.
- Always include at least 1 compound exercise per primary muscle group
- Always include Face Pull on upper body days (posture correction)
- Gym section only — morning/evening/nutrition tasks use defaults
- Return ONLY valid JSON"""


async def analyze_photos(
    photo_data: list[dict],
    photo_paths: list[str] | None = None,
) -> Optional[dict]:
    """Send photos to Claude for body/face analysis.

    Args:
        photo_data: list of {"bytes": raw_bytes, "media_type": "image/jpeg"} dicts
                    (preferred — in-memory, nothing touches disk).
        photo_paths: legacy fallback — list of file paths on disk.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _mock_analysis()

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    content = []

    # Preferred: in-memory bytes
    if photo_data:
        for item in photo_data:
            data = base64.standard_b64encode(item["bytes"]).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": item.get("media_type", "image/jpeg"),
                    "data": data,
                },
            })
    # Legacy fallback: read from disk
    elif photo_paths:
        for path in photo_paths:
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                data = base64.standard_b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(path)[1].lower()
            media_type = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
            }.get(ext, "image/jpeg")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })

    content.append({"type": "text", "text": "Please analyze these photos thoroughly."})

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=PHOTO_ANALYSIS_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    response_text = message.content[0].text

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return {"raw_response": response_text, "error": "Failed to parse JSON"}


async def generate_plan(
    analysis: Optional[dict],
    goals: list[str],
    experience_level: str,
    available_equipment: list[str],
    injuries: list[str],
    sleep_target: float,
    gym_days: int,
    completion_rate: float,
    streak_days: int,
    user_data_context: str = "",
    user_memory: str = "",
    muscle_schedule: Optional[dict] = None,
) -> dict:
    """Generate a personalized 7-day plan using Claude."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _mock_plan()

    user_profile = {
        "goals": goals if goals else ["General fitness", "Improve face"],
        "experience_level": experience_level,
        "equipment": available_equipment if available_equipment else ["Full gym access"],
        "injuries": injuries if injuries else [],
        "gym_days_per_week": gym_days,
        "completion_rate_pct": round(completion_rate, 1),
        "streak_days": streak_days,
        "muscle_schedule": muscle_schedule,  # e.g. {"0":["chest","biceps"],"1":["back","triceps"]}
    }

    msg_parts = []

    if user_memory:
        msg_parts.append(user_memory)

    msg_parts.append(f"USER PROFILE:\n{json.dumps(user_profile, indent=2)}")

    if analysis and "raw_response" not in analysis:
        msg_parts.append(f"BODY/FACE ANALYSIS:\n{json.dumps(analysis, indent=2)}")
    else:
        msg_parts.append("BODY/FACE ANALYSIS: Not available — generate a balanced general plan.")

    if user_data_context:
        msg_parts.append(f"HISTORICAL DATA:\n{user_data_context}")

    msg_parts.append("Generate my personalized 7-day plan now.")
    user_message = "\n\n".join(msg_parts)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=PLAN_GENERATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = message.content[0].text

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return _mock_plan()


def _mock_analysis() -> dict:
    """Return mock analysis when no API key is configured."""
    return {
        "posture": {
            "anterior_pelvic_tilt": {"detected": True, "severity": "mild", "notes": "Slight forward hip tilt visible"},
            "forward_head": {"detected": True, "severity": "moderate", "notes": "Head position ~2cm forward of shoulders"},
            "rounded_shoulders": {"detected": True, "severity": "mild", "notes": "Minor rounding, likely from desk work"},
            "lateral_imbalance": {"detected": False, "severity": "none", "notes": "Symmetry appears balanced"},
            "overall_score": 6,
        },
        "body_composition": {
            "estimated_bf_range": "18-22%",
            "build_type": "mesomorph",
            "muscle_development": {
                "shoulders": "average", "chest": "underdeveloped",
                "back": "average", "arms": "average",
                "core": "underdeveloped", "legs": "average",
            },
            "priority_areas": ["chest", "shoulders", "core"],
            "strengths": ["legs", "back"],
        },
        "facial_analysis": {
            "jaw_definition": "average",
            "facial_puffiness": "mild",
            "symmetry": "good",
            "skin_condition": "good",
            "under_eye_area": "mild_circles",
            "recommendations": [
                "Daily face icing to reduce puffiness",
                "Consistent mewing practice for jaw definition",
                "Increase water intake, reduce sodium",
            ],
        },
        "recommendations": [
            "Focus on upper chest and shoulder development for V-taper",
            "Add face pulls and rear delt work to correct forward head posture",
            "Incorporate hip flexor stretches daily for pelvic tilt",
            "Start consistent face protocol: icing + mewing + jaw exercises",
            "Reduce body fat to 15% for sharper facial features",
        ],
        "severity_scores": {"posture": 6, "body_composition": 5, "facial": 6, "overall": 6},
    }


def _mock_plan() -> dict:
    """Return a default plan when no API key is configured."""
    return {
        "overview": "Balanced 3-day gym split with daily face protocol and sleep optimization",
        "gym_schedule": [0, 2, 4],
        "days": {},
    }
