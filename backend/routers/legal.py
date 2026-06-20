"""Legal / trust endpoints — medical disclaimer and privacy summary.

An AI app that gives fitness, nutrition, and health guidance must clearly state that it is
not medical advice, and (for a paid product) expose a privacy summary. Served as data so the
frontend can render it in onboarding and settings.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/legal", tags=["legal"])

MEDICAL_DISCLAIMER = (
    "claudeGYM provides general fitness, nutrition, and wellness information for educational "
    "purposes only. It is not medical advice and is not a substitute for professional medical "
    "care. Consult a qualified healthcare provider before starting any exercise, nutrition, or "
    "supplement program — especially if you have a medical condition, are pregnant, or take "
    "medication. Stop exercising and seek medical attention if you feel unwell."
)

PRIVACY_SUMMARY = (
    "We store the profile, activity, nutrition, photo-analysis, and wearable data you provide "
    "to generate your plans and track progress. We do not sell your data. AI features send the "
    "minimum necessary context to our AI providers to generate responses. You can export or "
    "delete your data at any time from Settings."
)


@router.get("")
async def legal():
    return {
        "medical_disclaimer": MEDICAL_DISCLAIMER,
        "privacy_summary": PRIVACY_SUMMARY,
    }
