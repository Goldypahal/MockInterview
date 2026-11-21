"""Settings, read from the .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Google Gemini (free tier). Get a key at https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
# Each free model has its own daily limit. When one runs out, the app tries the next.
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv(
        "GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite,gemini-3.1-flash-lite,gemini-3-flash-preview"
    ).split(",") if m.strip()
]
GEMINI_MODELS = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]

# Voice of the interviewer (gTTS). "co.in" = Indian English accent.
TTS_LANG = os.getenv("TTS_LANG", "en").strip()
TTS_TLD = os.getenv("TTS_TLD", "co.in").strip()


def missing_settings() -> list[str]:
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("<"):
        return ["GEMINI_API_KEY"]
    return []
