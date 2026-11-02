"""Google Gemini AI Provider for BOLT (Official API Integration)."""

import json
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("GeminiProvider")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SUPPORTED_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str = "", model: str = "gemini-2.5-flash"):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip() or "gemini-2.5-flash"

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    @property
    def available_models(self) -> List[str]:
        return list(SUPPORTED_GEMINI_MODELS)

    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_configuration_help(self) -> str:
        return (
            "### 🔑 How to configure Google Gemini:\n\n"
            "1. Visit [Google AI Studio](https://aistudio.google.com/) and sign in with your Google account.\n"
            "2. Click **Get API key** and create a new key.\n"
            "3. In BOLT, open **Settings (⚙)** or edit `.env`:\n"
            "   ```env\n"
            "   GEMINI_API_KEY=your_actual_gemini_key_here\n"
            "   BOLT_AI_PROVIDER=gemini\n"
            "   ```\n"
            "4. Save settings and test connection."
        )

    def _build_contents(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert chat messages into Gemini API contents structure, ensuring valid turns."""
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                # System messages are passed separately via systemInstruction
                continue
            gemini_role = "user" if msg.role == "user" else "model"
            if contents and contents[-1]["role"] == gemini_role:
                contents[-1]["parts"].append({"text": msg.content})
            else:
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg.content}]
                })

        # Gemini requires the first turn to be 'user'
        if contents and contents[0]["role"] != "user":
            contents.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

        return contents

    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Call Gemini generateContent API endpoint."""
        start_time = time.time()

        if not self.is_configured:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=(
                    "Gemini API key is not configured. "
                    "Please set your key in Settings (⚙) or .env.\n\n"
                    + self.get_configuration_help()
                ),
                error_type="MISSING_KEY",
                duration_seconds=0.0,
            )

        endpoint = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        payload: Dict[str, Any] = {
            "contents": self._build_contents(messages),
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        try:
            logger.debug(f"Calling Gemini API (model: {self.model})...")
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
                    status_str = err_json.get("error", {}).get("status", "")
                    if "API_KEY_INVALID" in err_detail or status_str == "INVALID_ARGUMENT":
                        err_type = "INVALID_KEY"
                    elif response.status_code == 429:
                        err_type = "RATE_LIMIT"
                    elif response.status_code == 404:
                        err_type = "MODEL_NOT_FOUND"
                except Exception:
                    pass

                logger.error(f"Gemini API returned status {response.status_code}: {err_detail}")
                return AIResponse(
                    content="",
                    model=self.model,
                    provider=self.provider_name,
                    success=False,
                    error=f"Gemini API Error ({response.status_code}): {err_detail}",
                    error_type=err_type,
                    duration_seconds=duration,
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return AIResponse(
                    content="[No response generated by model]",
                    model=self.model,
                    provider=self.provider_name,
                    raw_response=data,
                    success=True,
                    duration_seconds=duration,
                )

            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            reply_text = "".join(part.get("text", "") for part in parts)

            tokens_used = 0
            prompt_tokens = 0
            completion_tokens = 0
            if "usageMetadata" in data:
                usage = data["usageMetadata"]
                tokens_used = usage.get("totalTokenCount", 0)
                prompt_tokens = usage.get("promptTokenCount", 0)
                completion_tokens = usage.get("candidatesTokenCount", 0)

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
            logger.error("Gemini API request timed out.")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="Gemini API request timed out after 45 seconds.",
                error_type="TIMEOUT",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Gemini API: {e}")
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Network error communicating with Gemini API: {e}",
                error_type="NETWORK_ERROR",
                duration_seconds=round(time.time() - start_time, 2),
            )
        except Exception as e:
            logger.exception("Unexpected error in GeminiProvider")
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
        """Stream chunks from Gemini streamGenerateContent SSE endpoint."""
        if not self.is_configured:
            yield "Gemini API key is not configured. Please set GEMINI_API_KEY."
            return

        endpoint = f"{GEMINI_API_BASE}/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "contents": self._build_contents(messages),
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            with requests.post(endpoint, headers=headers, json=payload, timeout=60.0, stream=True) as resp:
                if resp.status_code != 200:
                    yield f"Gemini streaming error ({resp.status_code})"
                    return

                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data: "):
                            data_str = decoded[6:].strip()
                            try:
                                chunk_json = json.loads(data_str)
                                candidates = chunk_json.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        txt = part.get("text", "")
                                        if txt:
                                            yield txt
                            except Exception:
                                pass
        except Exception as e:
            yield f"[Streaming error: {e}]"

    def test_connection(self) -> Tuple[bool, str]:
        """Verify API key and connectivity. Returns (is_healthy, message)."""
        if not self.is_configured:
            return False, "Gemini API key is missing. Configure it in Settings (⚙) or .env."

        t0 = time.time()
        try:
            url = f"{GEMINI_API_BASE}?key={self.api_key}"
            res = requests.get(url, timeout=10.0)
            latency_ms = int((time.time() - t0) * 1000)

            if res.status_code == 200:
                return True, f"Successfully connected to Google Gemini API ({latency_ms} ms)."
            elif res.status_code in (400, 403):
                return False, f"Invalid Gemini API key (HTTP {res.status_code}). Please verify your key at Google AI Studio."
            elif res.status_code == 429:
                return False, f"Gemini API rate limit reached (HTTP 429). Please wait before retrying."
            else:
                return False, f"Gemini connection test failed (HTTP {res.status_code}): {res.text[:120]}"
        except requests.exceptions.Timeout:
            return False, "Connection to Google Gemini timed out (10s limit)."
        except requests.exceptions.RequestException as e:
            return False, f"Network error connecting to Gemini: {e}"
        except Exception as e:
            return False, f"Error testing Gemini connection: {e}"
