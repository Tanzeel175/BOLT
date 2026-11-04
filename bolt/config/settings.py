"""Settings management for BOLT, supporting .env and runtime persistence."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from .constants import (
    ROOT_DIR,
    PROVIDER_OLLAMA,
    PROVIDER_NEBIUS,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_CUSTOM,
    PROVIDER_MOCK,
    AVAILABLE_PROVIDERS,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_NEBIUS_MODEL,
    DEFAULT_NEBIUS_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_CUSTOM_BASE_URL,
    DEFAULT_CUSTOM_NAME,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
)

ENV_FILE = ROOT_DIR / ".env"


@dataclass
class Settings:
    provider: str = PROVIDER_OLLAMA
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_context_size: int = 2048
    ollama_cpu_threads: int = 8
    nebius_api_key: str = ""
    nebius_model: str = DEFAULT_NEBIUS_MODEL
    nebius_base_url: str = DEFAULT_NEBIUS_BASE_URL
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_base_url: str = "https://api.openai.com/v1"
    custom_provider_name: str = DEFAULT_CUSTOM_NAME
    custom_api_key: str = ""
    custom_base_url: str = DEFAULT_CUSTOM_BASE_URL
    custom_model: str = DEFAULT_CUSTOM_MODEL
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

        provider = os.getenv("BOLT_AI_PROVIDER", PROVIDER_OLLAMA).strip().lower()
        if provider not in AVAILABLE_PROVIDERS:
            provider = PROVIDER_OLLAMA

        ollama_model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
        try:
            ollama_context_size = int(os.getenv("OLLAMA_CONTEXT_SIZE", "2048"))
        except ValueError:
            ollama_context_size = 2048
        try:
            ollama_cpu_threads = int(os.getenv("OLLAMA_CPU_THREADS", "8"))
        except ValueError:
            ollama_cpu_threads = 8

        nebius_api_key = os.getenv("NEBIUS_API_KEY", "").strip()
        nebius_model = os.getenv("NEBIUS_MODEL", DEFAULT_NEBIUS_MODEL).strip()
        nebius_base_url = os.getenv("NEBIUS_BASE_URL", DEFAULT_NEBIUS_BASE_URL).strip()

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()

        custom_provider_name = os.getenv("CUSTOM_PROVIDER_NAME", DEFAULT_CUSTOM_NAME).strip()
        custom_api_key = os.getenv("CUSTOM_API_KEY", "").strip()
        custom_base_url = os.getenv("CUSTOM_BASE_URL", DEFAULT_CUSTOM_BASE_URL).strip()
        custom_model = os.getenv("CUSTOM_MODEL", DEFAULT_CUSTOM_MODEL).strip()

        # Offline-first principle: If a cloud/custom provider is selected but has no API key
        # (and is not a local endpoint), automatically prefer the local model (Ollama)
        # so BOLT operates 100% locally without errors or cloud dependencies.
        if provider == PROVIDER_NEBIUS and not nebius_api_key:
            provider = PROVIDER_OLLAMA
        elif provider == PROVIDER_OPENAI and not openai_api_key:
            provider = PROVIDER_OLLAMA
        elif provider == PROVIDER_GEMINI and not gemini_api_key:
            provider = PROVIDER_OLLAMA
        elif provider == PROVIDER_CUSTOM and not custom_api_key and "localhost" not in custom_base_url and "127.0.0.1" not in custom_base_url:
            provider = PROVIDER_OLLAMA

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
            ollama_model=ollama_model,
            ollama_base_url=ollama_base_url,
            ollama_context_size=ollama_context_size,
            ollama_cpu_threads=ollama_cpu_threads,
            nebius_api_key=nebius_api_key,
            nebius_model=nebius_model,
            nebius_base_url=nebius_base_url,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            custom_provider_name=custom_provider_name,
            custom_api_key=custom_api_key,
            custom_base_url=custom_base_url,
            custom_model=custom_model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            log_level=log_level,
        )

    def save(self) -> None:
        """Persist current settings to .env file atomically."""
        new_values = {
            "BOLT_AI_PROVIDER": self.provider,
            "OLLAMA_MODEL": self.ollama_model,
            "OLLAMA_BASE_URL": self.ollama_base_url,
            "OLLAMA_CONTEXT_SIZE": str(self.ollama_context_size),
            "OLLAMA_CPU_THREADS": str(self.ollama_cpu_threads),
            "NEBIUS_API_KEY": self.nebius_api_key,
            "NEBIUS_MODEL": self.nebius_model,
            "NEBIUS_BASE_URL": self.nebius_base_url,
            "GEMINI_API_KEY": self.gemini_api_key,
            "GEMINI_MODEL": self.gemini_model,
            "OPENAI_API_KEY": self.openai_api_key,
            "OPENAI_MODEL": self.openai_model,
            "OPENAI_BASE_URL": self.openai_base_url,
            "CUSTOM_PROVIDER_NAME": self.custom_provider_name,
            "CUSTOM_API_KEY": self.custom_api_key,
            "CUSTOM_BASE_URL": self.custom_base_url,
            "CUSTOM_MODEL": self.custom_model,
            "BOLT_TEMPERATURE": str(self.temperature),
            "BOLT_MAX_TOKENS": str(self.max_tokens),
            "BOLT_LOG_LEVEL": self.log_level,
        }

        try:
            env_content = "\n".join(f"{k}={v}" for k, v in new_values.items()) + "\n"
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(env_content)
        except Exception:
            pass

        # Update current process environment as well
        os.environ["BOLT_AI_PROVIDER"] = self.provider
        os.environ["OLLAMA_MODEL"] = self.ollama_model
        os.environ["OLLAMA_BASE_URL"] = self.ollama_base_url
        os.environ["OLLAMA_CONTEXT_SIZE"] = str(self.ollama_context_size)
        os.environ["OLLAMA_CPU_THREADS"] = str(self.ollama_cpu_threads)
        os.environ["NEBIUS_API_KEY"] = self.nebius_api_key
        os.environ["NEBIUS_MODEL"] = self.nebius_model
        os.environ["NEBIUS_BASE_URL"] = self.nebius_base_url
        os.environ["GEMINI_API_KEY"] = self.gemini_api_key
        os.environ["GEMINI_MODEL"] = self.gemini_model
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["OPENAI_MODEL"] = self.openai_model
        os.environ["OPENAI_BASE_URL"] = self.openai_base_url
        os.environ["CUSTOM_PROVIDER_NAME"] = self.custom_provider_name
        os.environ["CUSTOM_API_KEY"] = self.custom_api_key
        os.environ["CUSTOM_BASE_URL"] = self.custom_base_url
        os.environ["CUSTOM_MODEL"] = self.custom_model
        os.environ["BOLT_TEMPERATURE"] = str(self.temperature)
        os.environ["BOLT_MAX_TOKENS"] = str(self.max_tokens)
        os.environ["BOLT_LOG_LEVEL"] = self.log_level

    @property
    def current_api_key(self) -> str:
        """Return the API key for the currently active provider."""
        if self.provider == PROVIDER_NEBIUS:
            return self.nebius_api_key
        elif self.provider == PROVIDER_GEMINI:
            return self.gemini_api_key
        elif self.provider == PROVIDER_OPENAI:
            return self.openai_api_key
        elif self.provider == PROVIDER_CUSTOM:
            return self.custom_api_key
        return ""

    @property
    def current_model(self) -> str:
        """Return the model name for the currently active provider."""
        if self.provider == PROVIDER_OLLAMA:
            return self.ollama_model
        elif self.provider == PROVIDER_NEBIUS:
            return self.nebius_model
        elif self.provider == PROVIDER_GEMINI:
            return self.gemini_model
        elif self.provider == PROVIDER_OPENAI:
            return self.openai_model
        elif self.provider == PROVIDER_CUSTOM:
            return self.custom_model
        return ""

    def has_active_api_key(self) -> bool:
        """Check if active provider is ready (local models do not require API keys)."""
        if self.provider in (PROVIDER_OLLAMA, PROVIDER_MOCK):
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
