"""Generic / Custom AI Provider for BOLT (Supports Any Model and Any API Key).

Allows users to connect to ANY OpenAI-compatible inference provider, including:
- Groq (https://api.groq.com/openai/v1)
- DeepSeek (https://api.deepseek.com/v1)
- OpenRouter (https://openrouter.ai/api/v1)
- Mistral AI (https://api.mistral.ai/v1)
- Together AI (https://api.together.xyz/v1)
- Perplexity (https://api.perplexity.ai)
- Anthropic Claude (via OpenRouter, LiteLLM, or direct Messages API)
- Local servers (LM Studio, vLLM, text-generation-webui)
- Any custom or enterprise REST endpoint
"""

import json
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("CustomAIProvider")

# Popular presets for quick user configuration
POPULAR_PRESETS: Dict[str, Dict[str, str]] = {
    "groq": {
        "name": "Groq Cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "help_url": "https://console.groq.com/keys",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "help_url": "https://platform.deepseek.com/api_keys",
    },
    "openrouter": {
        "name": "OpenRouter (All Models)",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.5-sonnet",
        "help_url": "https://openrouter.ai/keys",
    },
    "mistral": {
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "help_url": "https://console.mistral.ai/api-keys",
    },
    "together": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "help_url": "https://api.together.ai/settings/api-keys",
    },
    "lmstudio": {
        "name": "LM Studio (Local)",
        "base_url": "http://127.0.0.1:1234/v1",
        "default_model": "local-model",
        "help_url": "http://127.0.0.1:1234",
    },
    "xai": {
        "name": "xAI (Grok)",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2",
        "help_url": "https://console.x.ai",
    },
    "perplexity": {
        "name": "Perplexity AI",
        "base_url": "https://api.perplexity.ai",
        "default_model": "sonar-pro",
        "help_url": "https://www.perplexity.ai/settings/api",
    },
}


class CustomAIProvider(AIProvider):
    """Generic AI provider supporting any OpenAI-compatible API key, model, and base URL."""

    def __init__(
        self,
        name: str = "Custom / Any Model",
        api_key: str = "",
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "llama-3.3-70b-versatile",
    ):
        self.name = (name or "Custom Provider").strip()
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").strip().rstrip("/")
        self.model = (model or "").strip() or "default"

    @property
    def provider_name(self) -> str:
        return "custom"

    @property
    def display_name(self) -> str:
        if self.name and self.name.lower() not in ("custom", "custom provider", "custom / any model"):
            return f"Any Model ({self.name})"
        return "Custom / Any Model"

    @property
    def available_models(self) -> List[str]:
        models = [self.model]
        for preset in POPULAR_PRESETS.values():
            m = preset.get("default_model")
            if m and m not in models:
                models.append(m)
        return models

    @property
    def default_model(self) -> str:
        return self.model or "default"

    @property
    def is_configured(self) -> bool:
        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        return bool(self.api_key) or (is_local and bool(self.base_url))

    def get_configuration_help(self) -> str:
        return (
            "### 🌐 How to connect Any Model or Custom API in BOLT:\n\n"
            "You can use an API key from ANY provider in the world!\n\n"
            "1. **Select or enter your Provider Base URL**:\n"
            "   - **Groq**: `https://api.groq.com/openai/v1`\n"
            "   - **DeepSeek**: `https://api.deepseek.com/v1`\n"
            "   - **OpenRouter**: `https://openrouter.ai/api/v1` (Access Claude, GPT-4, Llama, Gemini with 1 key)\n"
            "   - **Mistral**: `https://api.mistral.ai/v1`\n"
            "   - **Together AI**: `https://api.together.xyz/v1`\n"
            "   - **LM Studio / Local vLLM**: `http://127.0.0.1:1234/v1` (no key required)\n"
            "2. Enter your **API Key**.\n"
            "3. Enter the **Model Name** (e.g. `deepseek-chat`, `llama-3.3-70b-versatile`, `claude-3-5-sonnet`).\n"
            "4. Click **Test Connection** and Save Settings."
        )

    def _get_chat_endpoint(self) -> str:
        url = self.base_url
        if not url:
            url = "https://api.groq.com/openai/v1"
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # OpenRouter specific headers for attribution
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://github.com/BOLT-Assistant"
            headers["X-Title"] = "BOLT Assistant"

        return headers

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
        """Call standard OpenAI-compatible completions API."""
        start_time = time.time()

        if not self.is_configured:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=(
                    f"API key or Base URL for {self.display_name} is not configured.\n\n"
                    + self.get_configuration_help()
                ),
                error_type="MISSING_KEY",
                duration_seconds=0.0,
            )

        endpoint = self._get_chat_endpoint()
        headers = self._build_headers()
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.info(f"Calling Custom API endpoint: {endpoint} (model: {self.model})...")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=45.0)
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

                logger.error(f"Custom API error ({response.status_code}): {err_detail}")
                return AIResponse(
                    content="",
                    model=self.model,
                    provider=self.provider_name,
                    success=False,
                    error=f"{self.display_name} Error ({response.status_code}): {err_detail}",
                    error_type=err_type,
                    duration_seconds=duration,
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(
                    content="[No response choices returned by model]",
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
            logger.error(f"Custom API request to {endpoint} timed out.")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Request to {self.display_name} timed out after 45 seconds.",
                error_type="TIMEOUT",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Custom API: {e}")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Network error communicating with {self.display_name}: {e}",
                error_type="NETWORK_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except Exception as e:
            logger.exception("Unexpected error in CustomAIProvider")
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
        """Stream chunks from completions endpoint."""
        if not self.is_configured:
            yield f"API key or Base URL for {self.display_name} is not configured."
            return

        endpoint = self._get_chat_endpoint()
        headers = self._build_headers()
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
                    yield f"[{self.display_name} error: HTTP {resp.status_code}]"
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
        """Verify API key and connectivity with a lightweight ping/request."""
        if not self.is_configured:
            return False, f"API key or Base URL for {self.display_name} is missing. Configure it in Settings."

        t0 = time.time()
        headers = self._build_headers()

        # Step 1: Try /models endpoint first
        models_endpoint = f"{self.base_url}/models"
        try:
            res = requests.get(models_endpoint, headers=headers, timeout=8.0)
            latency_ms = int((time.time() - t0) * 1000)
            if res.status_code == 200:
                return True, f"Successfully connected to {self.display_name} ({latency_ms} ms)."
            elif res.status_code == 401:
                return False, f"Invalid API key for {self.display_name} (HTTP 401)."
            elif res.status_code == 429:
                return False, f"Rate limit or quota exceeded for {self.display_name} (HTTP 429)."
        except Exception:
            pass

        # Step 2: Fallback to lightweight 1-token test prompt if /models isn't supported
        try:
            endpoint = self._get_chat_endpoint()
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            res = requests.post(endpoint, headers=headers, json=payload, timeout=12.0)
            latency_ms = int((time.time() - t0) * 1000)
            if res.status_code == 200:
                return True, f"Successfully connected to {self.display_name} ({latency_ms} ms)."
            elif res.status_code == 401:
                return False, f"Invalid API key for {self.display_name} (HTTP 401)."
            elif res.status_code == 429:
                return False, f"Rate limit or quota reached (HTTP 429)."
            else:
                return False, f"Connection failed (HTTP {res.status_code}): {res.text[:120]}"
        except requests.exceptions.Timeout:
            return False, f"Connection to {self.display_name} timed out."
        except requests.exceptions.RequestException as e:
            return False, f"Network error connecting to {self.display_name}: {e}"
        except Exception as e:
            return False, f"Error testing {self.display_name} connection: {e}"

