"""Base abstraction and data structures for AI providers in BOLT."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class AIResponse:
    content: str
    model: str
    provider: str = ""
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "MISSING_KEY", "INVALID_KEY", "NETWORK_ERROR", "TIMEOUT", "RATE_LIMIT", "PROVIDER_ERROR"
    success: bool = True
    duration_seconds: float = 0.0


class AIProvider(ABC):
    """Abstract base class for all AI service providers in BOLT."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Normalized name of the provider (e.g., 'gemini', 'openai', 'mock')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name of the provider (e.g., 'Google Gemini', 'OpenAI ChatGPT')."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """List of supported model identifiers for this provider."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has the required credentials configured."""
        pass

    @abstractmethod
    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Send chat messages and retrieve completion."""
        pass

    @abstractmethod
    def stream_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream chunks of the completion as they are generated."""
        pass

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Verify API key and network connectivity. Returns (is_healthy, message)."""
        pass

    def get_configuration_help(self) -> str:
        """Return instructions on how to configure this provider."""
        return f"Please set the API credentials for {self.display_name} in Settings (⚙) or .env."
