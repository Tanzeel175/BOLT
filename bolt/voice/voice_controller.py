"""
Offline Voice Controller for BOLT (Part 7).
Provides local speech synthesis (TTS) using Windows SAPI.SpVoice and local speech recognition (STT) interface.
Never requires cloud speech APIs.
Allows typed input gracefully when microphone is not attached or speech engine is idle.
"""

import subprocess
import threading
from typing import Any, Dict, Optional
from bolt.core.logger import get_logger

logger = get_logger("VoiceController")


class VoiceController:
    """Manages offline speech synthesis and microphone command intake."""

    def __init__(self):
        self._tts_enabled = True
        self._is_speaking = False
        self._check_engine_availability()

    def _check_engine_availability(self) -> None:
        """Verify Windows offline speech synthesis availability."""
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "$v = New-Object -ComObject SAPI.SpVoice; [int]$v.GetVoices().Count",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
            count = int(res.stdout.strip() or "0")
            self._tts_available = count > 0
            logger.info(f"Windows offline TTS available with {count} installed voice(s).")
        except Exception as e:
            logger.debug(f"Offline TTS check: {e}")
            self._tts_available = False

    @property
    def is_tts_available(self) -> bool:
        return getattr(self, "_tts_available", False)

    @property
    def status_summary(self) -> str:
        if self.is_tts_available:
            return "TTS Ready (Offline)"
        return "Text Only"

    def speak_async(self, text: str) -> None:
        """Speak response text asynchronously on a background thread without freezing UI."""
        if not self._tts_enabled or not self.is_tts_available or not text:
            return

        threading.Thread(target=self.speak, args=(text,), daemon=True).start()

    def speak(self, text: str) -> bool:
        """Speak text aloud using Windows native offline SAPI speech synthesizer."""
        if not text:
            return True

        clean_text = text.replace('"', '""').replace("`", " ").strip()
        # Remove markdown tags
        import re
        clean_text = re.sub(r"[\*#_`>]", "", clean_text)
        if len(clean_text) > 300:
            clean_text = clean_text[:300] + "..."

        try:
            self._is_speaking = True
            ps_code = f'$v = New-Object -ComObject SAPI.SpVoice; $v.Speak("{clean_text}")'
            cmd = ["powershell", "-NoProfile", "-Command", ps_code]
            subprocess.run(cmd, capture_output=True, timeout=10.0)
            return True
        except Exception as e:
            logger.warning(f"Voice synthesis error: {e}")
            return False
        finally:
            self._is_speaking = False

    def listen_command(self) -> Optional[str]:
        """
        Attempt to capture spoken command from local microphone.
        If microphone is unavailable or offline STT not installed, returns None to allow typed commands.
        """
        logger.info("Listening for spoken voice command (fallback to typed input if mic unavailable)...")
        # Placeholder for optional Vosk/Whisper offline STT
        return None


_VOICE_CONTROLLER_INSTANCE: Optional[VoiceController] = None


def get_voice_controller() -> VoiceController:
    global _VOICE_CONTROLLER_INSTANCE
    if _VOICE_CONTROLLER_INSTANCE is None:
        _VOICE_CONTROLLER_INSTANCE = VoiceController()
    return _VOICE_CONTROLLER_INSTANCE

