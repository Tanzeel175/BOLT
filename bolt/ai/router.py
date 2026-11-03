"""AI Router to dispatch requests to the active or requested provider."""

from typing import Iterator, List, Optional
from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.ai.provider_manager import AIProviderManager, get_provider_manager
from bolt.config.settings import Settings, get_settings
from bolt.core.logger import get_logger

logger = get_logger("AIRouter")


class AIRouter:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        provider_mgr: Optional[AIProviderManager] = None,
    ):
        self.settings = settings or get_settings()
        self.provider_mgr = provider_mgr or get_provider_manager()

    def get_provider(self, name_or_override: Optional[str] = None) -> AIProvider:
        """Resolve the target provider, respecting explicit overrides."""
        target = name_or_override or self.settings.provider
        return self.provider_mgr.get_provider(target)

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        provider_override: Optional[str] = None,
    ) -> AIResponse:
        """Route generation request to the active or explicitly requested provider."""
        provider = self.get_provider(provider_override)
        sys_prompt = system_prompt or self.settings.system_prompt
        logger.info(f"Routing request to provider: {provider.display_name} ({provider.provider_name})")

        response = provider.generate_response(
            messages=messages,
            system_prompt=sys_prompt,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )

        return response

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider_override: Optional[str] = None,
    ) -> str:
        """Convenience method to generate text response for a single prompt."""
        resp = self.generate(
            messages=[ChatMessage(role="user", content=prompt)],
            system_prompt=system_prompt,
            provider_override=provider_override,
        )
        return resp.content

    def generate_response(self, prompt: str) -> str:
        """Alias for generate_text."""
        return self.generate_text(prompt)

    def stream(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        provider_override: Optional[str] = None,
    ) -> Iterator[str]:
        """Stream chunks from the active or explicitly requested provider."""
        provider = self.get_provider(provider_override)
        sys_prompt = system_prompt or self.settings.system_prompt
        logger.info(f"Streaming request from provider: {provider.display_name}")

        return provider.stream_response(
            messages=messages,
            system_prompt=sys_prompt,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )


_ROUTER_INSTANCE: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = AIRouter()
    return _ROUTER_INSTANCE
