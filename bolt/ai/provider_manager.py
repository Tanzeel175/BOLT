"""AI Provider Manager for BOLT.

Detects, configures, tests, and orchestrates active and alternative AI providers.
Supports runtime switching between Gemini, OpenAI, and local engines without restarts.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from bolt.ai.base import AIProvider
from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.mock_provider import MockProvider
from bolt.ai.openai_provider import OpenAIProvider
from bolt.config.constants import (
    AVAILABLE_PROVIDERS,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    PROVIDER_GEMINI,
    PROVIDER_MOCK,
    PROVIDER_OPENAI,
)
from bolt.config.settings import Settings, get_settings
from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger

logger = get_logger("AIProviderManager")


@dataclass
class ProviderInfo:
    id: str
    display_name: str
    is_configured: bool
    is_default: bool
    selected_model: str
    available_models: List[str]
    status: str
    masked_key: str
    configuration_help: str


def mask_key(key: str) -> str:
    """Safely mask an API key for UI display (e.g. AIza...7x9Q or sk-...4F2b)."""
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}••••••••{key[-4:]}"


class AIProviderManager:
    """Manages AI provider lifecycle, runtime switching, configuration, and diagnostics."""

    def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
        self.settings = settings or get_settings()
        self.db = db or get_database()
        self._providers: Dict[str, AIProvider] = {}
        self._initialize_providers()
        self._sync_with_db()

    def _initialize_providers(self) -> None:
        """Instantiate providers using current settings."""
        self._providers[PROVIDER_GEMINI] = GeminiProvider(
            api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
        )
        self._providers[PROVIDER_OPENAI] = OpenAIProvider(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            base_url=self.settings.openai_base_url,
        )
        self._providers[PROVIDER_MOCK] = MockProvider()

    def _sync_with_db(self) -> None:
        """Sync provider preferences with SQLite database."""
        try:
            for p_id in [PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_MOCK]:
                pref = self.db.get_provider_preference(p_id)
                provider = self._providers.get(p_id)
                if not provider:
                    continue

                is_default = (self.settings.provider == p_id)
                model = (
                    self.settings.gemini_model if p_id == PROVIDER_GEMINI
                    else self.settings.openai_model if p_id == PROVIDER_OPENAI
                    else provider.default_model
                )

                if pref:
                    if pref.get("is_default") and not is_default:
                        # Database recorded this as default
                        pass
                else:
                    self.db.set_provider_preference(
                        provider=p_id,
                        model=model,
                        is_default=is_default,
                        is_available=provider.is_configured,
                        last_status="ready" if provider.is_configured else "not_configured",
                    )
        except Exception as e:
            logger.warning(f"Could not sync provider preferences to DB: {e}")

    def refresh_settings(self, settings: Optional[Settings] = None) -> None:
        """Reload settings and reconfigure providers."""
        self.settings = settings or get_settings(reload=True)
        self._initialize_providers()

    def get_provider(self, name: Optional[str] = None) -> AIProvider:
        """Resolve a specific provider by name or return the active default provider."""
        target_name = (name or self.settings.provider).strip().lower()

        # Map common aliases
        if target_name in ("chatgpt", "gpt", "openai"):
            target_name = PROVIDER_OPENAI
        elif target_name in ("gemini", "google", "bard"):
            target_name = PROVIDER_GEMINI
        elif target_name in ("mock", "local", "offline"):
            target_name = PROVIDER_MOCK

        if target_name in self._providers:
            return self._providers[target_name]

        logger.warning(f"Provider '{target_name}' not found, falling back to default '{self.settings.provider}'")
        return self._providers.get(self.settings.provider, self._providers[PROVIDER_MOCK])

    def get_active_provider(self) -> AIProvider:
        """Get the currently configured default provider."""
        return self.get_provider(self.settings.provider)

    def get_provider_info(self, provider_id: str) -> Optional[ProviderInfo]:
        """Return rich metadata for a given provider."""
        p = self._providers.get(provider_id.lower().strip())
        if not p:
            return None

        is_default = (self.settings.provider.lower() == p.provider_name)
        key = (
            self.settings.gemini_api_key if p.provider_name == PROVIDER_GEMINI
            else self.settings.openai_api_key if p.provider_name == PROVIDER_OPENAI
            else ""
        )
        selected_model = (
            self.settings.gemini_model if p.provider_name == PROVIDER_GEMINI
            else self.settings.openai_model if p.provider_name == PROVIDER_OPENAI
            else p.default_model
        )

        status = "ready" if p.is_configured else "not_configured"
        if p.provider_name == PROVIDER_MOCK:
            status = "offline_mock"

        return ProviderInfo(
            id=p.provider_name,
            display_name=p.display_name,
            is_configured=p.is_configured,
            is_default=is_default,
            selected_model=selected_model,
            available_models=p.available_models,
            status=status,
            masked_key=mask_key(key),
            configuration_help=p.get_configuration_help(),
        )

    def get_all_providers_info(self) -> List[ProviderInfo]:
        """Return rich metadata for all registered providers."""
        infos = []
        for p_id in [PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_MOCK]:
            info = self.get_provider_info(p_id)
            if info:
                infos.append(info)
        return infos

    def switch_default_provider(self, provider_name: str) -> Tuple[bool, str]:
        """Switch the default AI provider at runtime without restarting BOLT."""
        norm = provider_name.strip().lower()
        if norm in ("chatgpt", "gpt"):
            norm = PROVIDER_OPENAI
        elif norm in ("gemini", "google"):
            norm = PROVIDER_GEMINI
        elif norm in ("mock", "local", "offline"):
            norm = PROVIDER_MOCK

        if norm not in self._providers:
            return False, f"Unknown AI provider '{provider_name}'. Available: {AVAILABLE_PROVIDERS}"

        target_provider = self._providers[norm]
        self.settings.provider = norm
        self.settings.save()

        # Update SQLite database
        try:
            self.db.set_default_provider(norm)
        except Exception as e:
            logger.warning(f"Error persisting default provider in DB: {e}")

        logger.info(f"Switched default AI provider to: {target_provider.display_name}")
        return True, f"Successfully switched default AI provider to **{target_provider.display_name}**."

    def set_provider_model(self, provider_name: str, model_name: str) -> Tuple[bool, str]:
        """Update the selected model for a specific provider."""
        norm = provider_name.strip().lower()
        if norm in ("chatgpt", "gpt"):
            norm = PROVIDER_OPENAI
        elif norm in ("gemini", "google"):
            norm = PROVIDER_GEMINI

        clean_model = model_name.strip()
        if not clean_model:
            return False, "Model name cannot be empty."

        if norm == PROVIDER_GEMINI:
            self.settings.gemini_model = clean_model
            self.settings.save()
            self._providers[PROVIDER_GEMINI] = GeminiProvider(
                api_key=self.settings.gemini_api_key,
                model=clean_model,
            )
        elif norm == PROVIDER_OPENAI:
            self.settings.openai_model = clean_model
            self.settings.save()
            self._providers[PROVIDER_OPENAI] = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                model=clean_model,
                base_url=self.settings.openai_base_url,
            )
        else:
            return False, f"Provider '{provider_name}' does not support custom model selection."

        try:
            self.db.set_provider_preference(
                provider=norm,
                model=clean_model,
                is_default=(self.settings.provider == norm),
            )
        except Exception as e:
            logger.warning(f"Error persisting provider model preference: {e}")

        return True, f"Updated model for {norm.title()} to `{clean_model}`."

    def test_provider(self, provider_name: str) -> Tuple[bool, str]:
        """Run connectivity and auth verification test for a provider."""
        p = self.get_provider(provider_name)
        ok, msg = p.test_connection()

        # Record connection test log in database
        try:
            status_str = "SUCCESS" if ok else "FAILED"
            self.db.log_connection_test(
                provider=p.provider_name,
                status=status_str,
                latency_ms=0,
                message=msg,
            )
            self.db.set_provider_preference(
                provider=p.provider_name,
                model=p.default_model,
                is_available=ok,
                last_status=status_str,
            )
        except Exception as e:
            logger.warning(f"Error recording connection test log: {e}")

        return ok, msg

    def test_all_providers(self) -> Dict[str, Tuple[bool, str]]:
        """Run connectivity check across all registered providers."""
        results: Dict[str, Tuple[bool, str]] = {}
        for p_id in [PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_MOCK]:
            results[p_id] = self.test_provider(p_id)
        return results


_PROVIDER_MGR_INSTANCE: Optional[AIProviderManager] = None


def get_provider_manager() -> AIProviderManager:
    """Singleton getter for the AI Provider Manager."""
    global _PROVIDER_MGR_INSTANCE
    if _PROVIDER_MGR_INSTANCE is None:
        _PROVIDER_MGR_INSTANCE = AIProviderManager()
    return _PROVIDER_MGR_INSTANCE

