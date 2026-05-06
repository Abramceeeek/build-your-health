"""
Multi-provider AI service — supports Gemini, OpenRouter, and Anthropic.
Priority: Gemini API → OpenRouter → Anthropic (whichever key is configured).
"""
import json
import logging
from typing import Optional
import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


async def call_ai(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
) -> Optional[str]:
    """
    Call AI with automatic provider fallback.
    Returns raw text response or None on failure.
    """
    settings = get_settings()

    # Try OpenRouter first
    if settings.openrouter_api_key:
        result = await _call_openrouter(settings.openrouter_api_key, system_prompt, user_message, max_tokens)
        if result:
            return result

    # Try Gemini second
    if settings.gemini_api_key:
        result = await _call_gemini(settings.gemini_api_key, system_prompt, user_message, max_tokens)
        if result:
            return result

    # Fall back to Anthropic
    if settings.anthropic_api_key:
        result = await _call_anthropic(settings.anthropic_api_key, system_prompt, user_message, max_tokens)
        if result:
            return result

    logger.warning("No AI provider available — all API keys missing or failed")
    return None


async def call_ai_json(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 8192,
) -> Optional[dict]:
    """
    Call AI and parse JSON from the response.
    Strips markdown code fences if present.
    """
    raw = await call_ai(system_prompt, user_message, max_tokens)
    if not raw:
        return None

    text = raw.strip()
    # Strip markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI JSON: %s\nRaw: %s", e, text[:200])
        return None


# ─── GEMINI ──────────────────────────────────────────────────────────────────

async def _call_gemini(api_key: str, system_prompt: str, user_message: str, max_tokens: int) -> Optional[str]:
    """Call Google Gemini API (gemini-1.5-flash — free tier)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning("Gemini call failed: %s", e)
        return None


# ─── OPENROUTER ──────────────────────────────────────────────────────────────

async def _call_openrouter(api_key: str, system_prompt: str, user_message: str, max_tokens: int) -> Optional[str]:
    """Call OpenRouter API (routes to free models like Llama, Mistral, etc.)."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://claudegym.app",
        "X-Title": "claudeGYM",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",  # free model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("OpenRouter call failed: %s", e)
        return None


# ─── ANTHROPIC ───────────────────────────────────────────────────────────────

async def _call_anthropic(api_key: str, system_prompt: str, user_message: str, max_tokens: int) -> Optional[str]:
    """Call Anthropic Claude API."""
    try:
        import anthropic as anthropic_lib  # type: ignore
        client = anthropic_lib.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning("Anthropic call failed: %s", e)
        return None


# ─── EXERCISE SPLIT SUGGESTION ───────────────────────────────────────────────

SPLIT_SUGGESTION_PROMPT = """You are an expert personal trainer. Based on the user's profile, suggest the best workout split.
Return ONLY valid JSON:
{
  "recommended_split": "full_body|ppl|push_pull|upper_lower|bro_split",
  "split_name": "Human readable name",
  "reason": "1-2 sentence explanation",
  "days_per_week": 3,
  "schedule": ["Push day", "Rest", "Pull day", "Rest", "Legs + Core", "Rest", "Rest"],
  "beginner_friendly": true|false
}"""


async def suggest_workout_split(
    experience_level: str,
    inactivity_months: int,
    goals: list[str],
    gym_days: int,
) -> dict:
    """Use AI to suggest the best workout split for the user."""
    user_msg = f"""
User profile:
- Experience: {experience_level}
- Months away from gym: {inactivity_months}
- Goals: {', '.join(goals) if goals else 'general fitness'}
- Available gym days per week: {gym_days}

Suggest the most appropriate workout split.
"""
    result = await call_ai_json(SPLIT_SUGGESTION_PROMPT, user_msg, max_tokens=1024)

    # Fallback if AI fails
    if not result:
        if inactivity_months >= 3 or experience_level == "beginner":
            return {
                "recommended_split": "full_body",
                "split_name": "Full Body (3x/week)",
                "reason": "Best choice after a long break — rebuilds the neuromuscular connection evenly across all muscles.",
                "days_per_week": min(gym_days, 3),
                "schedule": ["Full body", "Rest", "Full body", "Rest", "Full body", "Rest", "Rest"],
                "beginner_friendly": True,
            }
        elif gym_days >= 5:
            return {
                "recommended_split": "ppl",
                "split_name": "Push / Pull / Legs",
                "reason": "High frequency PPL maximizes volume and recovery for intermediate to advanced lifters.",
                "days_per_week": 6,
                "schedule": ["Push", "Pull", "Legs", "Push", "Pull", "Legs", "Rest"],
                "beginner_friendly": False,
            }
        else:
            return {
                "recommended_split": "upper_lower",
                "split_name": "Upper / Lower",
                "reason": "Balanced split hitting each muscle group twice per week — ideal for building muscle efficiently.",
                "days_per_week": 4,
                "schedule": ["Upper", "Lower", "Rest", "Upper", "Lower", "Rest", "Rest"],
                "beginner_friendly": True,
            }

    return result


# ─── MEAL BUDGET SUGGESTIONS ─────────────────────────────────────────────────

MEAL_SUGGEST_PROMPT = """You are a nutritionist and budget meal planner. Create affordable, protein-rich meal plans.
Return ONLY valid JSON:
{
  "budget_level": "cheap|medium|premium",
  "daily_cost_estimate": "~$4-6",
  "meals": [
    {
      "meal_type": "breakfast|lunch|dinner|snack",
      "name": "Meal name",
      "ingredients": [{"item": "...", "amount": "150g", "approx_cost": "$0.50"}],
      "macros": {"calories": 420, "protein_g": 35, "carbs_g": 40, "fat_g": 12},
      "prep_time_min": 10,
      "instructions": "Brief cooking instructions"
    }
  ],
  "total_macros": {"calories": 1900, "protein_g": 145, "carbs_g": 200, "fat_g": 60},
  "shopping_tips": ["Buy chicken in bulk", "Eggs are the cheapest protein"]
}"""


async def suggest_budget_meals(
    daily_calories_target: float,
    protein_target: float,
    budget_level: str = "cheap",  # cheap|medium|premium
    region_hint: str = "Central Asia",
) -> dict:
    """AI-powered budget-aware daily meal plan suggestion."""
    user_msg = f"""
Create a full-day meal plan:
- Calorie target: {round(daily_calories_target)} kcal
- Protein target: {round(protein_target)}g
- Budget level: {budget_level}
- Region/cuisine preference: {region_hint}
- Prioritize affordable, real foods. Include local staples where possible.
- Include 3 meals + 1-2 snacks.
"""
    result = await call_ai_json(MEAL_SUGGEST_PROMPT, user_msg, max_tokens=2048)
    if not result:
        # Hardcoded fallback
        return {
            "budget_level": budget_level,
            "daily_cost_estimate": "~$3-5",
            "meals": [
                {
                    "meal_type": "breakfast",
                    "name": "Oats + Eggs",
                    "ingredients": [
                        {"item": "Rolled oats", "amount": "80g", "approx_cost": "$0.20"},
                        {"item": "Eggs", "amount": "3 whole", "approx_cost": "$0.45"},
                        {"item": "Banana", "amount": "1 medium", "approx_cost": "$0.15"},
                    ],
                    "macros": {"calories": 490, "protein_g": 28, "carbs_g": 58, "fat_g": 14},
                    "prep_time_min": 10,
                    "instructions": "Cook oats with water. Scramble or boil 3 eggs. Eat banana on the side.",
                },
                {
                    "meal_type": "lunch",
                    "name": "Chicken Rice Bowl",
                    "ingredients": [
                        {"item": "Chicken breast", "amount": "180g", "approx_cost": "$0.90"},
                        {"item": "White rice (cooked)", "amount": "200g", "approx_cost": "$0.20"},
                        {"item": "Cucumber + tomato", "amount": "150g", "approx_cost": "$0.25"},
                    ],
                    "macros": {"calories": 520, "protein_g": 48, "carbs_g": 57, "fat_g": 6},
                    "prep_time_min": 20,
                    "instructions": "Grill or boil chicken. Serve over rice with fresh vegetables.",
                },
                {
                    "meal_type": "dinner",
                    "name": "Lentil & Vegetable Soup",
                    "ingredients": [
                        {"item": "Red lentils", "amount": "100g dry", "approx_cost": "$0.25"},
                        {"item": "Onion + carrot", "amount": "150g", "approx_cost": "$0.20"},
                        {"item": "Bread (1 slice)", "amount": "50g", "approx_cost": "$0.10"},
                    ],
                    "macros": {"calories": 380, "protein_g": 22, "carbs_g": 65, "fat_g": 3},
                    "prep_time_min": 25,
                    "instructions": "Boil lentils with veg and spices for 20-25 min.",
                },
                {
                    "meal_type": "snack",
                    "name": "Cottage Cheese + Apple",
                    "ingredients": [
                        {"item": "Cottage cheese", "amount": "150g", "approx_cost": "$0.40"},
                        {"item": "Apple", "amount": "1 medium", "approx_cost": "$0.20"},
                    ],
                    "macros": {"calories": 185, "protein_g": 19, "carbs_g": 21, "fat_g": 2},
                    "prep_time_min": 2,
                    "instructions": "Serve as-is. Add cinnamon for flavour.",
                },
            ],
            "total_macros": {"calories": 1575, "protein_g": 117, "carbs_g": 201, "fat_g": 25},
            "shopping_tips": [
                "Buy chicken breast in bulk (1-2kg) — cheapest protein per gram",
                "Lentils and oats are the cheapest macro sources",
                "Eggs are a complete protein — never skip them",
                "Buy seasonal fruit — it's cheaper and more nutritious",
            ],
        }
    return result


# ─── WEEKLY ANALYSIS REPORT ──────────────────────────────────────────────────

ANALYSIS_PROMPT = """You are an elite fitness coach analyzing a client's weekly data.
Be concise, specific, and motivating. Return ONLY valid JSON:
{
  "overall_grade": "A|B|C|D",
  "headline": "One punchy sentence summarizing their week",
  "muscle_balance": {
    "push_days": 0, "pull_days": 0, "legs_days": 0,
    "imbalance_warning": null
  },
  "nutrition_insight": "One specific nutrition observation",
  "recovery_insight": "Sleep/rest observation",
  "top_win": "Best thing they did this week",
  "top_fix": "Most important thing to improve next week",
  "prediction": "If they keep this up, here's what happens in 30 days",
  "action_items": ["Action 1", "Action 2", "Action 3"]
}"""


async def generate_weekly_analysis(context: dict) -> dict:
    """Generate a weekly performance analysis report using AI."""
    user_msg = f"""
Analyze this week's data:
- Task completion: {context.get('completion_rate', 0)}%
- Tasks done: {context.get('tasks_completed', 0)}/{context.get('tasks_total', 0)}
- Avg daily calories: {context.get('avg_daily_calories', 0)} kcal
- Avg daily protein: {context.get('avg_daily_protein', 0)}g
- Days nutrition logged: {context.get('nutrition_days_logged', 0)}/7
- Current streak: {context.get('streak_days', 0)} days
- Weight: {context.get('latest_metrics', {}).get('weight', 'unknown') if context.get('latest_metrics') else 'unknown'} kg
- Exercises this week: {', '.join([w['exercise'] for w in context.get('weight_logs', [])[:5]])}
Generate the weekly performance analysis.
"""
    result = await call_ai_json(ANALYSIS_PROMPT, user_msg, max_tokens=1024)
    if not result:
        rate = context.get("completion_rate", 0)
        grade = "A" if rate >= 85 else "B" if rate >= 70 else "C" if rate >= 50 else "D"
        return {
            "overall_grade": grade,
            "headline": f"You completed {round(rate)}% of your tasks — keep pushing.",
            "muscle_balance": {"push_days": 0, "pull_days": 0, "legs_days": 0, "imbalance_warning": None},
            "nutrition_insight": "Log your food daily to get personalized nutrition insights.",
            "recovery_insight": "Track your sleep to optimize recovery.",
            "top_win": "You showed up and tracked your progress.",
            "top_fix": "Aim to complete at least 80% of tasks next week.",
            "prediction": "Consistent effort compounds. 4 more weeks of this will produce visible results.",
            "action_items": [
                "Hit your protein target every day",
                "Add one more gym session this week",
                "Log your meals for 7 consecutive days",
            ],
        }
    return result
