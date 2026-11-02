"""OpenAI and OpenAI-compatible provider (Groq, OpenRouter, Ollama, LM Studio)."""

from typing import Any, Dict, List, Optional
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("OpenAIProvider")


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key.strip()
        self.model = model.strip() or "gpt-4o-mini"
        self.base_url = base_url.strip().rstrip("/")

    @property
    def provider_name(self) -> str:
        return "openai"

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
        if not self.api_key and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error="OpenAI API Key is not set. Please configure it in Settings or .env.",
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

            if response.status_code != 200:
                err_detail = response.text
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                except Exception:
                    pass

                logger.error(f"OpenAI API error ({response.status_code}): {err_detail}")
                return AIResponse(
                    content="",
                    model=self.model,
                    success=False,
                    error=f"OpenAI API Error ({response.status_code}): {err_detail}",
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(
                    content="[No response choices returned]",
                    model=self.model,
                    raw_response=data,
                    success=True,
                )

            message_obj = choices[0].get("message", {})
            reply_text = message_obj.get("content", "")

            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            return AIResponse(
                content=reply_text,
                model=self.model,
                tokens_used=tokens_used,
                raw_response=data,
                success=True,
            )

        except requests.exceptions.Timeout:
            logger.error("OpenAI API request timed out.")
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error="API request timed out after 45 seconds.",
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling OpenAI API: {e}")
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error=f"Network error communicating with API: {e}",
            )
        except Exception as e:
            logger.exception("Unexpected error in OpenAIProvider")
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error=f"Internal error: {e}",
            )

    def test_connection(self) -> bool:
        """Verify API key and connectivity with a lightweight request."""
        endpoint = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            res = requests.get(endpoint, headers=headers, timeout=10.0)
            return res.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI test connection failed: {e}")
            return False

