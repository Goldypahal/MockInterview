"""The interviewer's voice: text-to-speech with gTTS (free, Indian English accent)."""

import io
import re

from gtts import gTTS

import config


class VoiceError(Exception):
    pass


def speak(text: str) -> bytes:
    """Return MP3 audio of the text being read aloud."""
    clean = re.sub(r"[*_#`>|]", " ", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        raise VoiceError("Nothing to read aloud.")
    try:
        buf = io.BytesIO()
        gTTS(text=clean, lang=config.TTS_LANG, tld=config.TTS_TLD).write_to_fp(buf)
        return buf.getvalue()
    except Exception as exc:
        raise VoiceError(f"Couldn't create the interviewer's voice (check your internet): {exc}") from exc
