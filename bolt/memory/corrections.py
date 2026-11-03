"""
Correction Detection and Adaptive Learning Subsystem for BOLT (Phase 8).
Recognizes when the user corrects BOLT (e.g., 'You opened Edge, but I prefer Chrome'),
extracts the mistake, determines the corrected behavior, and records permanent preferences.
"""

import re
from typing import Any, Dict, Optional, Tuple

from bolt.core.logger import get_logger
from bolt.memory.models import CorrectionRecord, MemoryCategory

logger = get_logger("CorrectionHandler")


class CorrectionHandler:
    """Parses user correction statements and maps them to permanent preference updates."""

    # Common correction regex patterns
    PATTERNS = [
        # "You opened Edge, but I prefer Chrome" / "You used X but I wanted Y"
        re.compile(
            r"^(?:you\s+)?(?:opened|used|launched|picked|chose|selected)\s+([a-zA-Z0-9_\-\.\s]+?)(?:,|\s+)+but\s+(?:i\s+)?(?:prefer|want|meant|wanted|like)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:instead|for\s+this|from\s+now\s+on))?[\.\?!]?$",
            re.IGNORECASE,
        ),
        # "Don't open Edge, open Chrome instead" / "Don't use X, use Y"
        re.compile(
            r"^don['’]?t\s+(?:open|use|launch)\s+([a-zA-Z0-9_\-\.\s]+?)(?:,|\s+)+(?:please\s+)?(?:open|use|launch)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+instead)?[\.\?!]?$",
            re.IGNORECASE,
        ),
        # "Not Edge, use Chrome"
        re.compile(
            r"^not\s+([a-zA-Z0-9_\-\.\s]+?)(?:,|\s+)+(?:use|open|launch|prefer)\s+([a-zA-Z0-9_\-\.\s]+?)[\.\?!]?$",
            re.IGNORECASE,
        ),
        # "That was the wrong app, use VS Code instead of Notepad"
        re.compile(
            r"^(?:that\s+was\s+wrong|wrong\s+app|wrong\s+choice)[,\s]+use\s+([a-zA-Z0-9_\-\.\s]+?)\s+instead\s+of\s+([a-zA-Z0-9_\-\.\s]+?)[\.\?!]?$",
            re.IGNORECASE,
        ),
    ]

    # Explicit preference directives: "Always open ChatGPT in Chrome"
    DIRECTIVE_PATTERNS = [
        re.compile(
            r"^always\s+(?:open|launch|run|use)\s+([a-zA-Z0-9_\-\.\s]+?)\s+in\s+([a-zA-Z0-9_\-\.\s]+?)[\.\?!]?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:from\s+now\s+on\s+)?(?:set\s+my\s+)?preferred\s+([a-zA-Z0-9_\-\.\s]+?)\s+(?:is|to|as)\s+([a-zA-Z0-9_\-\.\s]+?)[\.\?!]?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^i\s+prefer\s+([a-zA-Z0-9_\-\.\s]+?)\s+for\s+([a-zA-Z0-9_\-\.\s]+?)[\.\?!]?$",
            re.IGNORECASE,
        ),
    ]

    @staticmethod
    def identify_preference_key(wrong: str, corrected: str, context_hint: str = "") -> str:
        """Derive standard preference key based on corrected entity."""
        w_lower = wrong.lower().strip()
        c_lower = corrected.lower().strip()
        hint_lower = context_hint.lower().strip()

        # Known web browsers
        browsers = ["chrome", "google chrome", "msedge", "edge", "brave", "firefox", "opera"]
        if any(b in w_lower or b in c_lower for b in browsers):
            if "chatgpt" in hint_lower:
                return "preferred_browser_for_chatgpt"
            if "gemini" in hint_lower:
                return "preferred_browser_for_gemini"
            if hint_lower:
                clean_target = re.sub(r"[^a-zA-Z0-9]", "", hint_lower)
                return f"preferred_browser_for_{clean_target}"
            return "preferred_browser"

        # Known IDEs / Code editors
        code_tools = ["vs code", "vscode", "visual studio code", "pycharm", "sublime", "notepad++"]
        if any(tool in w_lower or tool in c_lower for tool in code_tools) or "programming" in hint_lower or "code" in hint_lower:
            return "preferred_programming_app"

        # Known notes / text editors
        notes_tools = ["notepad", "wordpad", "obsidian", "onenote"]
        if any(tool in w_lower or tool in c_lower for tool in notes_tools):
            return "preferred_notes_app"

        # Generic derived key
        clean_hint = re.sub(r"[^a-zA-Z0-9_]", "_", hint_lower or wrong).strip("_")
        return f"preferred_{clean_hint}"

    def parse_correction(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Evaluate text to determine if it is a user correction or explicit preference directive.
        Returns parsed components or None if text is not a correction.
        """
        clean = text.strip()

        # 1. Test correction patterns ("You opened X, but I prefer Y")
        for pattern in self.PATTERNS:
            match = pattern.match(clean)
            if match:
                # Handle group ordering (some patterns have (corrected, wrong))
                if "instead of" in clean.lower():
                    corrected = match.group(1).strip()
                    wrong = match.group(2).strip()
                else:
                    wrong = match.group(1).strip()
                    corrected = match.group(2).strip()

                pref_key = self.identify_preference_key(wrong, corrected)
                if pref_key.startswith("preferred_browser"):
                    corrected = corrected.lower()
                return {
                    "is_correction": True,
                    "is_directive": False,
                    "wrong": wrong,
                    "corrected": corrected,
                    "preference_key": pref_key,
                    "message": (
                        f"I apologize for the mistake. I understand you prefer '{corrected}' rather than '{wrong}'. "
                        f"I have saved this as your permanent preference and will use '{corrected}' in future tasks."
                    ),
                }

        # 2. Test directive patterns ("Always open ChatGPT in Chrome")
        for i, pattern in enumerate(self.DIRECTIVE_PATTERNS):
            match = pattern.match(clean)
            if match:
                if i == 0:  # "always open X in Y"
                    target = match.group(1).strip()
                    choice = match.group(2).strip()
                    pref_key = self.identify_preference_key("", choice, context_hint=target)
                    if pref_key.startswith("preferred_browser"):
                        choice = choice.lower()
                    return {
                        "is_correction": True,
                        "is_directive": True,
                        "wrong": "",
                        "corrected": choice,
                        "target": target,
                        "preference_key": pref_key,
                        "message": f"Understood. I have recorded your preference to always open '{target}' in '{choice}'.",
                    }
                elif i == 1:  # "preferred X is Y"
                    target = match.group(1).strip()
                    choice = match.group(2).strip()
                    pref_key = f"preferred_{re.sub(r'[^a-zA-Z0-9_]', '_', target.lower()).strip('_')}"
                    return {
                        "is_correction": True,
                        "is_directive": True,
                        "wrong": "",
                        "corrected": choice,
                        "target": target,
                        "preference_key": pref_key,
                        "message": f"Understood. Your preferred {target} is now set to '{choice}'.",
                    }
                elif i == 2:  # "i prefer Y for X"
                    choice = match.group(1).strip()
                    target = match.group(2).strip()
                    pref_key = self.identify_preference_key("", choice, context_hint=target)
                    return {
                        "is_correction": True,
                        "is_directive": True,
                        "wrong": "",
                        "corrected": choice,
                        "target": target,
                        "preference_key": pref_key,
                        "message": f"Preference saved: '{choice}' will be used for '{target}'.",
                    }

        return None
