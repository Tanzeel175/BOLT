"""Settings management for BOLT, supporting .env and runtime persistence."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key

from .constants import (
    ROOT_DIR,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_MOCK,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
)

ENV_FILE = ROOT_DIR / ".env"


@dataclass
class Settings:
    provider: str = PROVIDER_GEMINI
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_base_url: str = "https://api.openai.com/v1"
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment and .env file."""
        if ENV_FILE.exists():
            load_dotenv(dotenv_path=ENV_FILE, override=True)
        else:
            load_dotenv(override=True)

        provider = os.getenv("BOLT_AI_PROVIDER", PROVIDER_GEMINI).strip().lower()
        if provider not in (PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_MOCK):
            provider = PROVIDER_GEMINI

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()

        try:
            temperature = float(os.getenv("BOLT_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
        except ValueError:
            temperature = DEFAULT_TEMPERATURE

        try:
            max_tokens = int(os.getenv("BOLT_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        except ValueError:
            max_tokens = DEFAULT_MAX_TOKENS

        system_prompt = os.getenv("BOLT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()
        log_level = os.getenv("BOLT_LOG_LEVEL", "INFO").strip().upper()

        return cls(
            provider=provider,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            log_level=log_level,
        )

    def save(self) -> None:
        """Persist current settings to .env file."""
        if not ENV_FILE.exists():
            ENV_FILE.touch()

        set_key(str(ENV_FILE), "BOLT_AI_PROVIDER", self.provider)
        set_key(str(ENV_FILE), "GEMINI_API_KEY", self.gemini_api_key)
        set_key(str(ENV_FILE), "GEMINI_MODEL", self.gemini_model)
        set_key(str(ENV_FILE), "OPENAI_API_KEY", self.openai_api_key)
        set_key(str(ENV_FILE), "OPENAI_MODEL", self.openai_model)
        set_key(str(ENV_FILE), "OPENAI_BASE_URL", self.openai_base_url)
        set_key(str(ENV_FILE), "BOLT_TEMPERATURE", str(self.temperature))
        set_key(str(ENV_FILE), "BOLT_MAX_TOKENS", str(self.max_tokens))
        set_key(str(ENV_FILE), "BOLT_LOG_LEVEL", self.log_level)

        # Update current process environment as well
        os.environ["BOLT_AI_PROVIDER"] = self.provider
        os.environ["GEMINI_API_KEY"] = self.gemini_api_key
        os.environ["GEMINI_MODEL"] = self.gemini_model
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["OPENAI_MODEL"] = self.openai_model
        os.environ["OPENAI_BASE_URL"] = self.openai_base_url
        os.environ["BOLT_TEMPERATURE"] = str(self.temperature)
        os.environ["BOLT_MAX_TOKENS"] = str(self.max_tokens)
        os.environ["BOLT_LOG_LEVEL"] = self.log_level

    @property
    def current_api_key(self) -> str:
        """Return the API key for the currently active provider."""
        if self.provider == PROVIDER_GEMINI:
            return self.gemini_api_key
        elif self.provider == PROVIDER_OPENAI:
            return self.openai_api_key
        return ""

    @property
    def current_model(self) -> str:
        """Return the model name for the currently active provider."""
        if self.provider == PROVIDER_GEMINI:
            return self.gemini_model
        elif self.provider == PROVIDER_OPENAI:
            return self.openai_model
        return "mock-offline-engine"

    def has_active_api_key(self) -> bool:
        """Check if an API key is present for the active cloud provider."""
        if self.provider == PROVIDER_MOCK:
            return True
        return bool(self.current_api_key.strip())

    @staticmethod
    def mask_key(key: str) -> str:
        """Return a safely masked string for display in UI."""
        if not key:
            return ""
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"


_SETTINGS_INSTANCE: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """Singleton getter for application settings."""
    global _SETTINGS_INSTANCE
    if _SETTINGS_INSTANCE is None or reload:
        _SETTINGS_INSTANCE = Settings.load()
    return _SETTINGS_INSTANCE

