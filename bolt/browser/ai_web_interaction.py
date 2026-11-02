"""
AI Website Interaction Subsystem for BOLT (Phase 3).
Prepares architecture for interacting with ChatGPT, Gemini, and other AI web platforms.
Identifies target AI services, checks API vs. Web Interface availability,
detects authentication state, and guides browser navigation.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from bolt.browser.browser_controller import BrowserController, get_browser_controller
from bolt.browser.content_reader import ContentReader, get_content_reader
from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.config.settings import Settings, get_settings
from bolt.core.logger import get_logger

logger = get_logger("AIWebInteraction")


@dataclass
class AIServiceInfo:
    service_key: str
    display_name: str
    web_url: str
    api_provider_key: str
    api_configured: bool
    requires_auth: bool


class AIWebInteraction:
    """Coordinates interaction between BOLT and web-based AI platforms."""

    KNOWN_AI_SERVICES: Dict[str, Dict[str, str]] = {
        "chatgpt": {
            "name": "ChatGPT",
            "url": "https://chatgpt.com/",
            "api_key_field": "openai_api_key",
            "provider_key": "openai",
        },
        "gemini": {
            "name": "Google Gemini",
            "url": "https://gemini.google.com/",
            "api_key_field": "gemini_api_key",
            "provider_key": "gemini",
        },
        "claude": {
            "name": "Anthropic Claude",
            "url": "https://claude.ai/",
            "api_key_field": "",
            "provider_key": "",
        },
    }

    def __init__(
        self,
        browser_ctrl: Optional[BrowserController] = None,
        registry: Optional[WebsiteRegistry] = None,
        content_reader: Optional[ContentReader] = None,
        settings: Optional[Settings] = None,
    ):
        self.browser_ctrl = browser_ctrl or get_browser_controller()
        self.registry = registry or get_website_registry()
        self.content_reader = content_reader or get_content_reader()
        self.settings = settings or get_settings()

    def identify_ai_service(self, text: str) -> Optional[AIServiceInfo]:
        """Detect if user query targets an AI web service."""
        lower = text.lower()
        for key, info in self.KNOWN_AI_SERVICES.items():
            if key in lower or info["name"].lower() in lower:
                api_field = info["api_key_field"]
                has_api = bool(getattr(self.settings, api_field, None)) if api_field else False
                return AIServiceInfo(
                    service_key=key,
                    display_name=info["name"],
                    web_url=info["url"],
                    api_provider_key=info["provider_key"],
                    api_configured=has_api,
                    requires_auth=True,
                )
        return None

    def open_ai_web_service(self, service_key: str) -> Dict[str, Any]:
        """Open the target AI website in the browser and verify its state."""
        clean_key = service_key.strip().lower()
        info = self.KNOWN_AI_SERVICES.get(clean_key)
        if not info:
            return {
                "success": False,
                "error": f"Unknown AI service '{service_key}'.",
            }

        url = info["url"]
        nav_res = self.browser_ctrl.open_url(url, new_tab=True)
        return nav_res


_AI_WEB_INTERACTION: Optional[AIWebInteraction] = None


def get_ai_web_interaction() -> AIWebInteraction:
    global _AI_WEB_INTERACTION
    if _AI_WEB_INTERACTION is None:
        _AI_WEB_INTERACTION = AIWebInteraction()
    return _AI_WEB_INTERACTION

