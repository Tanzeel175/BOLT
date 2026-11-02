"""OpenAI and OpenAI-Compatible Provider for BOLT (Official API Integration)."""

import json
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("OpenAIProvider")

SUPPORTED_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "o3-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip() or "gpt-4o-mini"
        self.base_url = (base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI ChatGPT"

    @property
    def available_models(self) -> List[str]:
        return list(SUPPORTED_OPENAI_MODELS)

    @property
    def default_model(self) -> str:
        return "gpt-4o-mini"

    @property
    def is_configured(self) -> bool:
        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        return bool(self.api_key) or is_local

    def get_configuration_help(self) -> str:
        return (
            "### 🔑 How to configure OpenAI ChatGPT:\n\n"
            "1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys) and sign in.\n"
            "2. Create a new secret key (starts with `sk-...`).\n"
            "3. In BOLT, open **Settings (⚙)** or edit `.env`:\n"
            "   ```env\n"
            "   OPENAI_API_KEY=sk-your_actual_openai_key_here\n"
            "   BOLT_AI_PROVIDER=openai\n"
            "   ```\n"
            "4. For local/compatible models (Ollama, LM Studio, Groq), set `OPENAI_BASE_URL` accordingly.\n"
            "5. Save settings and test connection."
        )

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
        """Call OpenAI chat/completions API."""
        start_time = time.time()

        if not self.is_configured:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=(
                    "OpenAI API key is not configured. "
                    "Please set your key in Settings (⚙) or .env.\n\n"
                    + self.get_configuration_help()
                ),
                error_type="MISSING_KEY",
                duration_seconds=0.0,
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.debug(f"Calling OpenAI API endpoint: {endpoint} (model: {self.model})...")
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=45.0,
            )
            duration = round(time.time() - start_time, 2)

            if response.status_code != 200:
                err_detail = response.text
                err_type = "PROVIDER_ERROR"
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                    code_val = err_json.get("error", {}).get("code", "")
                    if response.status_code == 401 or "invalid_api_key" in str(code_val):
                        err_type = "INVALID_KEY"
                    elif response.status_code == 429:
                        err_type = "RATE_LIMIT"
                    elif response.status_code == 404:
                        err_type = "MODEL_NOT_FOUND"
                except Exception:
                    pass

                logger.error(f"OpenAI API error ({response.status_code}): {err_detail}")
                return AIResponse(
                    content="",
                    model=self.model,
                    provider=self.provider_name,
                    success=False,
                    error=f"OpenAI API Error ({response.status_code}): {err_detail}",
                    error_type=err_type,
                    duration_seconds=duration,
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(
                    content="[No response choices returned]",
                    model=self.model,
                    provider=self.provider_name,
                    raw_response=data,
                    success=True,
                    duration_seconds=duration,
                )

            message_obj = choices[0].get("message", {})
            reply_text = message_obj.get("content", "")

            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            return AIResponse(
                content=reply_text,
                model=self.model,
                provider=self.provider_name,
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_response=data,
                success=True,
                duration_seconds=duration,
            )

        except requests.exceptions.Timeout:
            logger.error("OpenAI API request timed out.")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="OpenAI API request timed out after 45 seconds.",
                error_type="TIMEOUT",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling OpenAI API: {e}")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Network error communicating with OpenAI API: {e}",
                error_type="NETWORK_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except Exception as e:
            logger.exception("Unexpected error in OpenAIProvider")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Internal error: {e}",
                error_type="INTERNAL_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )

    def stream_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream chunks from OpenAI chat/completions SSE endpoint."""
        if not self.is_configured:
            yield "OpenAI API key is not configured. Please set OPENAI_API_KEY."
            return

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            with requests.post(endpoint, headers=headers, json=payload, timeout=60.0, stream=True) as resp:
                if resp.status_code != 200:
                    yield f"OpenAI streaming error ({resp.status_code})"
                    return

                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data: "):
                            data_str = decoded[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content_chunk = delta.get("content", "")
                                    if content_chunk:
                                        yield content_chunk
                            except Exception:
                                pass
        except Exception as e:
            yield f"[Streaming error: {e}]"

    def test_connection(self) -> Tuple[bool, str]:
        """Verify API key and connectivity with a lightweight request."""
        if not self.is_configured:
            return False, "OpenAI API key is missing. Configure it in Settings (⚙) or .env."

        endpoint = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        t0 = time.time()
        try:
            res = requests.get(endpoint, headers=headers, timeout=10.0)
            latency_ms = int((time.time() - t0) * 1000)

            if res.status_code == 200:
                return True, f"Successfully connected to OpenAI API ({latency_ms} ms)."
            elif res.status_code == 401:
                return False, f"Invalid OpenAI API key (HTTP 401). Check your key at https://platform.openai.com/api-keys."
            elif res.status_code == 429:
                return False, f"OpenAI quota exceeded or rate limit reached (HTTP 429)."
            else:
                return False, f"OpenAI connection test failed (HTTP {res.status_code}): {res.text[:120]}"
        except requests.exceptions.Timeout:
            return False, "Connection to OpenAI timed out (10s limit)."
        except requests.exceptions.RequestException as e:
            return False, f"Network error connecting to OpenAI: {e}"
        except Exception as e:
            return False, f"Error testing OpenAI connection: {e}"
