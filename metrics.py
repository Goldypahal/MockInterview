"""Speaking metrics, calculated locally (no AI needed): filler words, pace and a fluency score."""

import io
import re
import wave
from collections import Counter

# Common filler words and phrases in spoken English (Indian English included).
FILLERS = [
    "um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm",
    "you know", "i mean", "basically", "actually", "literally", "like i said",
    "kind of", "sort of", "okay so", "so yeah",
]
_FILLER_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in sorted(FILLERS, key=len, reverse=True)) + r")\b",
                        re.IGNORECASE)

IDEAL_WPM = (110, 160)   # comfortable speaking pace for interviews


def wav_duration_seconds(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def filler_counts(text: str) -> Counter:
    return Counter(m.group(1).lower() for m in _FILLER_RE.finditer(text or ""))


def speaking_metrics(transcript: str, duration_s: float) -> dict:
    """Metrics for one spoken answer."""
    words = count_words(transcript)
    fillers = filler_counts(transcript)
    n_fill = sum(fillers.values())
    wpm = round(words / (duration_s / 60), 0) if duration_s >= 3 and words else None
    return {
        "words": words,
        "duration_s": round(duration_s, 1),
        "wpm": wpm,
        "fillers": dict(fillers),
        "filler_count": n_fill,
        "fillers_per_100_words": round(100 * n_fill / words, 1) if words else 0.0,
    }


def fluency_score(spoken_turns: list[dict]) -> int | None:
    """0–100 from filler rate and pace, over all spoken answers. None if nothing was spoken."""
    def _m(t):  # works with Turn objects or plain dicts
        return t.get("metrics") if isinstance(t, dict) else getattr(t, "metrics", None)
    spoken = [_m(t) for t in spoken_turns if _m(t) and _m(t)["words"] > 0]
    if not spoken:
        return None
    words = sum(m["words"] for m in spoken)
    fillers = sum(m["filler_count"] for m in spoken)
    rate = 100 * fillers / words if words else 0
    score = 100 - min(60, rate * 10)          # 1 filler per 100 words costs 10 points (max 60)
    wpms = [m["wpm"] for m in spoken if m["wpm"]]
    if wpms:
        avg = sum(wpms) / len(wpms)
        lo, hi = IDEAL_WPM
        off = (lo - avg) if avg < lo else (avg - hi) if avg > hi else 0
        score -= min(30, off * 0.5)           # every 2 wpm outside the ideal range costs 1 point
    return int(max(0, min(100, round(score))))


def pace_label(wpm) -> str:
    if not wpm:
        return "–"
    lo, hi = IDEAL_WPM
    return "Too slow" if wpm < lo else "Too fast" if wpm > hi else "Good"
