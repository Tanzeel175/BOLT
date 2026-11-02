"""AI Router to dispatch requests to the active provider."""

from typing import List, Optional
from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.openai_provider import OpenAIProvider
from bolt.ai.mock_provider import MockProvider
from bolt.config.constants import PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_MOCK
from bolt.config.settings import Settings, get_settings
from bolt.core.logger import get_logger

logger = get_logger("AIRouter")


class AIRouter:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def get_provider(self) -> AIProvider:
        """Resolve and instantiate the active AI provider based on settings."""
        provider_name = self.settings.provider.lower()

        if provider_name == PROVIDER_GEMINI:
            if not self.settings.gemini_api_key.strip():
                logger.info("No Gemini API key found; falling back to Mock/Local provider.")
                return MockProvider()
            return GeminiProvider(
                api_key=self.settings.gemini_api_key,
                model=self.settings.gemini_model,
            )

        elif provider_name == PROVIDER_OPENAI:
            if not self.settings.openai_api_key.strip():
                logger.info("No OpenAI API key found; falling back to Mock/Local provider.")
                return MockProvider()
            return OpenAIProvider(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                base_url=self.settings.openai_base_url,
            )

        else:
            return MockProvider()

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Route generation request to the active provider."""
        provider = self.get_provider()
        sys_prompt = system_prompt or self.settings.system_prompt
        logger.info(f"Routing request to provider: {provider.provider_name}")

        response = provider.generate_response(
            messages=messages,
            system_prompt=sys_prompt,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )

        return response


_ROUTER_INSTANCE: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = AIRouter()
    return _ROUTER_INSTANCE

