"""Connection to the Google Gemini API, with automatic model fallback.

The free tier gives each model its own small daily limit (for example 20 requests
per day). When one model's limit is used up, generate() moves on to the next model
in the list, so the app keeps working.
"""

import re
from functools import lru_cache

from google import genai
from google.genai import types

import config


class AllModelsBusy(Exception):
    """Every model in the list is out of free quota (or unavailable)."""


# Models that ran out of quota during this run of the app (skipped until restart).
_exhausted: set[str] = set()


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    # v1beta is needed for JSON-mode responses and function calling.
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta"),
    )


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _is_missing_model(exc: Exception) -> bool:
    msg = str(exc)
    return "404" in msg or "NOT_FOUND" in msg or "is not found" in msg


def _retry_hint(exc: Exception) -> str:
    m = re.search(r"retry in ([0-9hms.]+?)(?:\d*\.\d+)?s", str(exc))
    if not m:
        return ""
    hours = re.search(r"(\d+)h", m.group(1))
    mins = re.search(r"(\d+)m", m.group(1))
    parts = []
    if hours:
        parts.append(f"{hours.group(1)} h")
    if mins:
        parts.append(f"{mins.group(1)} min")
    return " in about " + " ".join(parts) if parts else ""


def model_order(prefer_light: bool = False) -> list[str]:
    models = list(config.GEMINI_MODELS)
    if prefer_light:  # simple jobs (like extracting dates) go to the lighter models first
        models.sort(key=lambda m: 0 if "lite" in m else 1)
    return models


def generate(contents, gen_config: types.GenerateContentConfig, prefer_light: bool = False,
             on_retry=None):
    """Call Gemini, trying each model in turn if one is out of quota.

    on_retry: optional function called before trying the next model (used by the agent
              to clear its record of tool calls from the failed attempt).
    Returns (response, model_name_used).
    """
    last_exc = None
    tried_any = False
    for model in model_order(prefer_light):
        if model in _exhausted:
            continue
        if tried_any and on_retry:
            on_retry()
        tried_any = True
        try:
            return get_client().models.generate_content(model=model, contents=contents, config=gen_config), model
        except Exception as exc:
            if _is_quota_error(exc) or _is_missing_model(exc):
                _exhausted.add(model)
                last_exc = exc
                continue
            raise
    hint = _retry_hint(last_exc) if last_exc else ""
    raise AllModelsBusy(
        "The free Gemini limit is used up for all models in your list"
        f"{', try again' + hint if hint else ''}. Free limits reset daily at midnight US Pacific time (around 1:30 PM in India). "
        "You can add more models to GEMINI_FALLBACK_MODELS in .env."
    )


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, AllModelsBusy):
        return str(exc)
    if _is_quota_error(exc):
        return "The free Gemini limit was reached. Wait a minute and try again."
    msg = str(exc)
    if "API key not valid" in msg or "API_KEY_INVALID" in msg:
        return "Your Gemini API key isn't valid. Check GEMINI_API_KEY in .env."
    return msg if len(msg) < 300 else msg[:300] + "..."
