"""Base abstraction and data structures for AI providers in BOLT."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class AIResponse:
    content: str
    model: str
    tokens_used: int = 0
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    success: bool = True


class AIProvider(ABC):
    """Abstract base class for all AI service providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'gemini', 'openai', 'mock')."""
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
    def test_connection(self) -> bool:
        """Verify API key and network connectivity."""
        pass

