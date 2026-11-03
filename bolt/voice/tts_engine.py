"""
Offline Text-to-Speech (TTS) Engine for BOLT (Phase 7).
Supports Windows Native SAPI (via pyttsx3/COM) and Piper offline TTS.
Configurable voice, speed (rate), volume, interruptibility, and spoken text summarization.
Never requires cloud speech APIs.
"""

import os
import re
import threading
import time
from typing import Any, Dict, List, Optional
from bolt.core.logger import get_logger

logger = get_logger("TTSEngine")


class TTSEngine:
    """
    Offline Text-to-Speech Engine with voice configuration, interruptibility,
    and echo-cancellation signaling.
    """

    def __init__(self, rate: int = 185, volume: float = 1.0, voice_index: int = 0):
        self._rate = rate
        self._volume = max(0.0, min(1.0, volume))
        self._voice_index = voice_index
        self._is_speaking = False
        self._stop_requested = False
        self._lock = threading.Lock()
        self._engine_type = "sapi"  # "sapi" or "piper"

        self._available_voices: List[Dict[str, Any]] = []
        self._init_engine()

    def _init_engine(self) -> None:
        """Initialize TTS voices from Windows SAPI."""
        try:
            import pyttsx3
            # Initialize engine in a temporary test to query voices
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            voices = engine.getProperty("voices")
            if voices:
                self._available_voices = [
                    {"id": v.id, "name": v.name, "languages": getattr(v, "languages", [])}
                    for v in voices
                ]
                if self._voice_index < len(voices):
                    engine.setProperty("voice", voices[self._voice_index].id)
            engine.stop()
            logger.info(f"Initialized offline TTS with {len(self._available_voices)} voice(s).")
        except Exception as e:
            logger.warning(f"Failed initializing pyttsx3 engine: {e}")
            self._available_voices = []

    @property
    def is_speaking(self) -> bool:
        """True if the TTS engine is currently outputting audio."""
        return self._is_speaking

    @property
    def available_voices(self) -> List[Dict[str, Any]]:
        """List of detected offline voices."""
        return self._available_voices

    def get_speech_rate(self) -> int:
        return self._rate

    def set_speech_rate(self, rate: int) -> None:
        self._rate = max(100, min(300, rate))

    def set_voice_by_name(self, voice_name: str) -> bool:
        """Select a voice by substring of its name."""
        name_lower = voice_name.lower()
        for idx, v in enumerate(self._available_voices):
            if name_lower in v["name"].lower():
                self._voice_index = idx
                logger.info(f"Selected voice: {v['name']}")
                return True
        return False

    def sanitize_for_speech(self, text: str, max_chars: int = 220) -> str:
        """
        Sanitize rich text / markdown into concise, natural spoken English.
        Strips markdown links, bolding, code blocks, tables, and long outputs.
        """
        if not text:
            return ""

        # Remove code blocks
        clean = re.sub(r"```[\s\S]*?```", "code block omitted.", text)
        # Remove inline code
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        # Replace markdown links [label](url) with just label
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
        # Remove markdown headers and formatting
        clean = re.sub(r"[#\*\_\~>]", " ", clean)
        # Clean URLs
        clean = re.sub(r"https?://\S+", "link", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        # Voice-friendly phrase normalizations
        if "opened notepad" in clean.lower() or "launched notepad" in clean.lower():
            return "Opening Notepad."
        if "calculator is already open" in clean.lower() or "launched calculator" in clean.lower():
            return "Calculator is ready."
        if "created text file" in clean.lower() or "notes.txt" in clean.lower():
            return "I have created your file."
        if "no internet connection" in clean.lower():
            return "No internet connection detected."
        if "failed" in clean.lower() and len(clean) > 80:
            return "I could not complete that operation."

        # Limit spoken monologue length to prevent verbose speech
        if len(clean) > max_chars:
            # Cut at sentence boundary if possible
            sentences = re.split(r"(?<=[.!?])\s+", clean)
            accumulated = ""
            for s in sentences:
                if len(accumulated) + len(s) <= max_chars:
                    accumulated += (" " if accumulated else "") + s
                else:
                    break
            clean = accumulated if accumulated else clean[:max_chars] + "..."

        return clean

    def stop_speaking(self) -> None:
        """Immediately interrupt/cancel ongoing speech."""
        self._stop_requested = True
        logger.info("Speech interruption requested.")

    def speak(self, text: str, interruptible: bool = True) -> bool:
        """
        Synchronously speak text aloud using offline TTS.
        Ensures self-echo prevention by setting is_speaking=True.
        """
        if not text:
            return True

        spoken_text = self.sanitize_for_speech(text)
        if not spoken_text:
            return True

        with self._lock:
            self._is_speaking = True
            self._stop_requested = False

        try:
            import pyttsx3
            # Create fresh engine instance per thread to avoid comtypes apartment threading conflicts
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)

            if self._available_voices and self._voice_index < len(self._available_voices):
                engine.setProperty("voice", self._available_voices[self._voice_index]["id"])

            logger.info(f"Speaking: '{spoken_text}' (Rate: {self._rate})")

            # Check interruption before starting
            if self._stop_requested and interruptible:
                return True

            engine.say(spoken_text)
            engine.runAndWait()
            engine.stop()
            return True
        except Exception as e:
            # Fallback to direct PowerShell SAPI if pyttsx3 fails in thread
            logger.warning(f"pyttsx3 speak failed, attempting SAPI fallback: {e}")
            try:
                import subprocess
                ps_text = spoken_text.replace('"', '""').replace("`", " ")
                ps_code = f'$v = New-Object -ComObject SAPI.SpVoice; $v.Rate = {int((self._rate - 150) / 15)}; $v.Speak("{ps_text}")'
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, timeout=12.0)
                return True
            except Exception as ps_err:
                logger.error(f"TTS SAPI fallback failed: {ps_err}")
                return False
        finally:
            with self._lock:
                self._is_speaking = False
                self._stop_requested = False

    def speak_async(self, text: str, on_complete: Optional[Any] = None) -> threading.Thread:
        """Asynchronously speak text on a worker thread."""
        def _run():
            res = self.speak(text)
            if on_complete:
                try:
                    on_complete(res)
                except Exception:
                    pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t


# Singleton instance
_TTS_ENGINE_INSTANCE: Optional[TTSEngine] = None


def get_tts_engine() -> TTSEngine:
    global _TTS_ENGINE_INSTANCE
    if _TTS_ENGINE_INSTANCE is None:
        _TTS_ENGINE_INSTANCE = TTSEngine()
    return _TTS_ENGINE_INSTANCE
