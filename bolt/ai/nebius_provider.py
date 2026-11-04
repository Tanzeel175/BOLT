"""
Nebius Token Factory AI Provider for BOLT.
Integrates Nebius Token Factory (https://tokenfactory.nebius.com/)
using its official OpenAI-compatible inference API.
"""

import json
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.config.constants import DEFAULT_NEBIUS_BASE_URL, DEFAULT_NEBIUS_MODEL, SUPPORTED_NEBIUS_MODELS
from bolt.core.logger import get_logger

logger = get_logger("NebiusProvider")


class NebiusProvider(AIProvider):
    """AI Provider integrating Nebius Token Factory cloud models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_NEBIUS_MODEL,
        base_url: str = DEFAULT_NEBIUS_BASE_URL,
    ):
        import os
        if api_key is None:
            raw_key = os.getenv("Nebius_API_key") or os.getenv("NEBIUS_API_KEY") or ""
        else:
            raw_key = api_key
        self.api_key = raw_key.strip()
        self.model = (model or "").strip() or DEFAULT_NEBIUS_MODEL
        self.base_url = (base_url or "").strip().rstrip("/") or DEFAULT_NEBIUS_BASE_URL

    @property
    def provider_name(self) -> str:
        return "nebius"

    @property
    def display_name(self) -> str:
        return "Nebius Token Factory"

    @property
    def available_models(self) -> List[str]:
        """Return supported Nebius Token Factory models."""
        return list(SUPPORTED_NEBIUS_MODELS)

    @property
    def default_model(self) -> str:
        return DEFAULT_NEBIUS_MODEL

    @property
    def is_configured(self) -> bool:
        """Configured if an API key is present."""
        return bool(self.api_key)

    def mask_key(self) -> str:
        """Safely mask key for UI display without exposing secret."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "••••••••"
        return f"{self.api_key[:4]}••••••••{self.api_key[-4:]}"

    def get_configuration_help(self) -> str:
        return (
            "### 🚀 How to configure Nebius Token Factory:\n\n"
            "1. Visit [tokenfactory.nebius.com](https://tokenfactory.nebius.com) and sign in.\n"
            "2. In the console, navigate to **API Keys** and click **Create API Key**.\n"
            "3. Copy your secret key and enter it in BOLT **Settings (⚙) -> AI Brain** or `.env`:\n"
            "   ```env\n"
            "   NEBIUS_API_KEY=your_nebius_secret_key_here\n"
            "   BOLT_AI_PROVIDER=nebius\n"
            "   NEBIUS_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct\n"
            "   ```\n"
            "4. Base URL is set to `https://api.tokenfactory.nebius.com/v1`."
        )

    def test_connection(self) -> Tuple[bool, str]:
        """
        Verify connection to Nebius Token Factory API by querying /v1/models.
        Never logs or reveals the API key.
        """
        if not self.api_key:
            return False, "Nebius API key is not configured. Please enter your key in Settings or .env."

        endpoint = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "BOLT-Assistant/1.0",
        }

        start_time = time.time()
        try:
            logger.info("Testing connection to Nebius Token Factory...")
            resp = requests.get(endpoint, headers=headers, timeout=12.0)
            latency_ms = round((time.time() - start_time) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                model_count = len(data.get("data", []))
                return True, f"Connected to Nebius Token Factory successfully ({latency_ms} ms, {model_count} models available)."
            elif resp.status_code == 401:
                return False, "Nebius authentication failed (401): Invalid API key."
            elif resp.status_code == 429:
                return False, "Nebius rate limit or quota exceeded (429)."
            else:
                err_detail = ""
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", "")
                except Exception:
                    err_detail = resp.text[:100]
                return False, f"Nebius API error ({resp.status_code}): {err_detail}"
        except requests.exceptions.Timeout:
            return False, "Connection to Nebius Token Factory timed out after 12s."
        except requests.exceptions.ConnectionError:
            return False, "Could not reach Nebius API. Check your internet connection."
        except Exception as e:
            return False, f"Connection error: {e}"

    def fetch_live_models(self) -> List[str]:
        """Fetch real-time list of available models from Nebius Token Factory."""
        if not self.api_key:
            return self.available_models

        endpoint = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = requests.get(endpoint, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                if models:
                    return sorted(models)
        except Exception as e:
            logger.debug(f"Could not fetch live Nebius models: {e}")
        return self.available_models

    def _build_messages(
        self, messages: List[ChatMessage], system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.role if msg.role in ("user", "assistant", "system") else "user"
            out.append({"role": role, "content": msg.content})
        return out

    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Call Nebius Token Factory chat completions API."""
        start_time = time.time()

        if not self.is_configured:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=(
                    "Nebius API key is not configured. "
                    "Please set your key in Settings (⚙) or .env."
                ),
                error_type="KEY_NOT_CONFIGURED",
                duration_seconds=0.0,
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "BOLT-Assistant/1.0",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.info(f"Submitting query to Nebius Token Factory (model: {self.model})...")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=45.0)
            duration = round(time.time() - start_time, 2)

            if response.status_code != 200:
                err_detail = response.text
                err_type = "PROVIDER_ERROR"
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                    if response.status_code == 401:
                        err_type = "INVALID_KEY"
                    elif response.status_code == 429:
                        err_type = "RATE_LIMIT"
                    elif response.status_code == 404:
                        err_type = "MODEL_NOT_FOUND"
                except Exception:
                    pass

                logger.error(f"Nebius API error ({response.status_code}): {err_detail}")
                return AIResponse(
                    content="",
                    model=self.model,
                    provider=self.provider_name,
                    success=False,
                    error=f"Nebius API Error ({response.status_code}): {err_detail}",
                    error_type=err_type,
                    duration_seconds=duration,
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(
                    content="[No response returned by Nebius model]",
                    model=self.model,
                    provider=self.provider_name,
                    success=True,
                    duration_seconds=duration,
                )

            message_obj = choices[0].get("message", {})
            content = message_obj.get("content", "") or message_obj.get("reasoning_content", "") or message_obj.get("reasoning", "") or ""
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            return AIResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                tokens_used=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_response=data,
                success=True,
                duration_seconds=duration,
            )
        except requests.exceptions.Timeout:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="Nebius Token Factory request timed out after 45s.",
                error_type="TIMEOUT",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except requests.exceptions.ConnectionError:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="Network error reaching Nebius Token Factory API. Please check your internet connection.",
                error_type="NETWORK_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except Exception as e:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Unexpected error calling Nebius API: {e}",
                error_type="UNEXPECTED_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )

    def stream_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream chunks from Nebius Token Factory chat completions."""
        if not self.is_configured:
            yield "⚠️ Nebius API key is not configured. Please configure your key in Settings (⚙)."
            return

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "BOLT-Assistant/1.0",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            with requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=45.0) as resp:
                if resp.status_code != 200:
                    yield f"⚠️ Nebius API error ({resp.status_code})"
                    return

                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8").strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    chunk_text = delta.get("content", "")
                                    if chunk_text:
                                        yield chunk_text
                            except Exception:
                                pass
        except Exception as e:
            yield f"⚠️ Nebius stream interrupted: {e}"
