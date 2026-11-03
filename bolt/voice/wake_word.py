"""
Offline Wake Word Detection for BOLT (Phase 7).
Local activation phrase detection ("Hey Bolt") with zero cloud connectivity.
Supports enable/disable toggling to prevent unnecessary CPU utilization.
Push-to-Talk remains the reliable default.
"""

import re
from typing import Optional, Tuple
from bolt.core.logger import get_logger

logger = get_logger("WakeWordDetector")


class WakeWordDetector:
    """
    Detects local wake word activation phrases ('Hey Bolt' / 'Bolt')
    and extracts subsequent commands.
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self._wake_phrases = ["hey bolt", "bolt", "ok bolt"]
        # Pattern to detect wake word at the beginning of spoken utterance
        self._pattern = re.compile(r"^\s*(?:hey\s+|ok\s+)?bolt\b[\s,:]*", re.IGNORECASE)

    @property
    def is_enabled(self) -> bool:
        """Whether continuous wake-word listening is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Toggle wake-word background listening."""
        self._enabled = enabled
        logger.info(f"Wake word listening {'enabled' if enabled else 'disabled'}.")

    def contains_wake_phrase(self, text: str) -> bool:
        """Return True if the text begins with or contains a wake phrase."""
        if not text:
            return False
        clean = text.strip().lower()
        return bool(self._pattern.search(clean))

    def extract_command(self, text: str) -> Tuple[bool, str]:
        """
        Check if text contains wake word and extract remaining command.
        Returns: (has_wake_word: bool, cleaned_command: str)
        Example: "Hey Bolt, open Calculator" -> (True, "open Calculator")
        Example: "Open Notepad" -> (False, "Open Notepad")
        """
        if not text:
            return False, ""

        clean = text.strip()
        match = self._pattern.search(clean)
        if match:
            remaining = clean[match.end():].strip()
            return True, remaining

        return False, clean


_WAKE_WORD_DETECTOR_INSTANCE: Optional[WakeWordDetector] = None


def get_wake_word_detector() -> WakeWordDetector:
    global _WAKE_WORD_DETECTOR_INSTANCE
    if _WAKE_WORD_DETECTOR_INSTANCE is None:
        _WAKE_WORD_DETECTOR_INSTANCE = WakeWordDetector()
    return _WAKE_WORD_DETECTOR_INSTANCE
