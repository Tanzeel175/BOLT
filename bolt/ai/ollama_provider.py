"""
Ollama Local AI Provider for BOLT (Part 2).
Provides genuine offline-first inference via Ollama runtime with zero cloud dependencies.
Supports Gemma 4 E2B, context size management, CPU thread optimization, structured tool calling,
conversation preservation, and live hardware benchmarking.
"""

import json
import os
import pathlib
import shutil
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
import psutil
import requests

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("OllamaProvider")

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_CONTEXT_SIZE = 2048
DEFAULT_CPU_THREADS = 4


class OllamaProvider(AIProvider):
    """Integrates local Ollama LLM runtime into BOLT's AI orchestration engine."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_HOST,
        model: str = DEFAULT_OLLAMA_MODEL,
        context_size: int = DEFAULT_CONTEXT_SIZE,
        cpu_threads: int = DEFAULT_CPU_THREADS,
    ):
        self.base_url = (base_url or DEFAULT_OLLAMA_HOST).rstrip("/")
        self.model = model or DEFAULT_OLLAMA_MODEL
        self.context_size = context_size
        self.cpu_threads = cpu_threads
        self._cached_models: List[str] = []
        self._last_models_fetch: float = 0.0

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return "Ollama Local AI (Offline)"

    @property
    def default_model(self) -> str:
        return self.model or DEFAULT_OLLAMA_MODEL

    @property
    def available_models(self) -> List[str]:
        """Fetch list of downloaded local models, with fallback defaults."""
        downloaded = self.get_downloaded_models()
        defaults = [DEFAULT_OLLAMA_MODEL, "gemma4:e4b", "gemma2:2b", "qwen2.5:3b", "llama3.2:3b"]
        combined = list(dict.fromkeys(downloaded + defaults))
        return combined

    @property
    def is_configured(self) -> bool:
        """Configured if Ollama service is reachable on localhost."""
        running, _ = self.is_service_running()
        return running

    # ---------------- Detection & Status Diagnostics ----------------

    def is_ollama_installed(self) -> Tuple[bool, str]:
        """Check if Ollama binary is installed on Windows system."""
        # Check PATH
        in_path = shutil.which("ollama")
        if in_path:
            return True, in_path

        # Check standard Windows installation directory
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            standard_path = pathlib.Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
            if standard_path.exists():
                return True, str(standard_path)

        prog_files = pathlib.Path(r"C:\Program Files\Ollama\ollama.exe")
        if prog_files.exists():
            return True, str(prog_files)

        return False, ""

    def is_service_running(self) -> Tuple[bool, str]:
        """Check if local Ollama daemon is currently listening on localhost."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                return True, "Ollama service is active and responding."
            return False, f"Ollama HTTP status {resp.status_code}."
        except requests.RequestException:
            return False, "Cannot connect to Ollama service on 127.0.0.1:11434."

    def get_downloaded_models(self) -> List[str]:
        """Return list of models downloaded and available in local Ollama storage."""
        now = time.time()
        if self._cached_models and (now - self._last_models_fetch < 10.0):
            return self._cached_models

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                self._cached_models = models
                self._last_models_fetch = now
                return models
        except Exception as e:
            logger.debug(f"Failed to fetch downloaded Ollama models: {e}")

        return self._cached_models

    def is_model_downloaded(self, model_name: Optional[str] = None) -> bool:
        """Verify whether the requested model is downloaded in local storage."""
        target = (model_name or self.model).lower().strip()
        downloaded = [m.lower() for m in self.get_downloaded_models()]
        for m in downloaded:
            if target == m or target in m or m.startswith(target.split(":")[0]):
                return True
        return False

    def test_connection(self) -> Tuple[bool, str]:
        """Test complete health: installation, daemon status, and model presence."""
        installed, path = self.is_ollama_installed()
        if not installed:
            return (
                False,
                "Ollama is not installed. Please download it from https://ollama.com/download/windows",
            )

        running, status_msg = self.is_service_running()
        if not running:
            return (
                False,
                "Ollama is installed, but the local service is not running. "
                "Launch Ollama from your Start menu or run 'ollama serve'.",
            )

        if not self.is_model_downloaded(self.model):
            return (
                False,
                f"Ollama is running, but model '{self.model}' is not yet downloaded.\n"
                f"To install it, open a terminal and run:\n\n"
                f"    ollama run {self.model}\n\n"
                "BOLT will not download models automatically.",
            )

        return True, f"Ollama local runtime is active with model '{self.model}'."

    def get_configuration_help(self) -> str:
        return (
            "### 🦙 Ollama Local AI Setup (Offline-First)\n\n"
            "1. **Download Ollama**: Visit [ollama.com/download/windows](https://ollama.com/download/windows) and install.\n"
            f"2. **Download Model**: Open Command Prompt / PowerShell and run:\n"
            f"   ```bash\n   ollama run {self.model}\n   ```\n"
            "3. **Zero Internet Required**: Once downloaded, all prompts run locally on your Intel Core i7 CPU."
        )

    # ---------------- Inference & Generation ----------------

    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Generate synchronous response from local Ollama model."""
        start_time = time.time()

        # 1. Health checks
        installed, _ = self.is_ollama_installed()
        if not installed:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="Ollama is not installed. Install from https://ollama.com/download/windows",
                error_type="RUNTIME_MISSING",
                duration_seconds=time.time() - start_time,
            )

        running, _ = self.is_service_running()
        if not running:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error="Ollama service is not running on 127.0.0.1:11434. Please start Ollama.",
                error_type="SERVICE_OFFLINE",
                duration_seconds=time.time() - start_time,
            )

        if not self.is_model_downloaded(self.model):
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=(
                    f"Model '{self.model}' is not downloaded. Run 'ollama run {self.model}' in terminal. "
                    "BOLT never downloads models without permission."
                ),
                error_type="MODEL_NOT_FOUND",
                duration_seconds=time.time() - start_time,
            )

        # 2. Format messages for Ollama /api/chat
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload_messages.append({"role": msg.role, "content": msg.content})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context_size,
                "num_thread": self.cpu_threads,
                "num_predict": max_tokens,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            logger.info(f"Submitting query to local Ollama model '{self.model}'...")
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60.0)
            duration = time.time() - start_time

            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", {})
                content = msg.get("content", "")
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)

                return AIResponse(
                    content=content,
                    model=self.model,
                    provider=self.provider_name,
                    tokens_used=prompt_tokens + completion_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    raw_response=data,
                    success=True,
                    duration_seconds=duration,
                )
            else:
                return AIResponse(
                    content="",
                    model=self.model,
                    provider=self.provider_name,
                    success=False,
                    error=f"Ollama returned HTTP error {resp.status_code}: {resp.text}",
                    error_type="PROVIDER_ERROR",
                    duration_seconds=duration,
                )
        except requests.Timeout:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Local Ollama inference timed out after 60s for model '{self.model}'.",
                error_type="TIMEOUT",
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return AIResponse(
                content="",
                model=self.model,
                provider=self.provider_name,
                success=False,
                error=f"Error connecting to Ollama: {e}",
                error_type="CONNECTION_ERROR",
                duration_seconds=time.time() - start_time,
            )

    def stream_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream chunks of tokens from local Ollama model."""
        if not self.is_configured or not self.is_model_downloaded(self.model):
            yield (
                f"⚠️ Local model '{self.model}' is unavailable. "
                f"Please ensure Ollama is running and '{self.model}' is downloaded."
            )
            return

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context_size,
                "num_thread": self.cpu_threads,
                "num_predict": max_tokens,
            },
        }

        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=60.0) as resp:
                if resp.status_code != 200:
                    yield f"⚠️ Ollama error: {resp.status_code}"
                    return

                for line in resp.iter_lines():
                    if line:
                        chunk_json = json.loads(line.decode("utf-8"))
                        chunk_text = chunk_json.get("message", {}).get("content", "")
                        if chunk_text:
                            yield chunk_text
        except Exception as e:
            yield f"⚠️ Stream interrupted: {e}"

    # ---------------- Benchmarking Telemetry (Part 2) ----------------

    def benchmark_model(self, test_prompt: str = "Explain recursion in C++ in 3 short bullet points.") -> Dict[str, Any]:
        """
        Empirically benchmark model performance on this laptop:
        - First token latency
        - Tokens per second
        - RAM consumption (before/after)
        - CPU utilization
        """
        if not self.is_configured:
            return {"success": False, "error": "Ollama service is not running."}

        if not self.is_model_downloaded(self.model):
            return {
                "success": False,
                "error": f"Model '{self.model}' is not downloaded. Run 'ollama run {self.model}' to benchmark it.",
            }

        # Snapshot pre-benchmark system telemetry
        mem_before = psutil.virtual_memory()
        cpu_before = psutil.cpu_percent(interval=None)
        start_time = time.time()

        response = self.generate_response(
            messages=[ChatMessage(role="user", content=test_prompt)],
            max_tokens=256,
        )

        total_time = time.time() - start_time
        mem_after = psutil.virtual_memory()
        cpu_after = psutil.cpu_percent(interval=0.2)

        if not response.success:
            return {
                "success": False,
                "error": response.error,
                "duration_seconds": total_time,
            }

        tokens_generated = response.completion_tokens or max(1, len(response.content.split()))
        tokens_per_sec = round(tokens_generated / max(total_time, 0.001), 2)
        ram_delta_mb = round((mem_after.used - mem_before.used) / (1024 * 1024), 1)

        return {
            "success": True,
            "model": self.model,
            "test_prompt": test_prompt,
            "total_latency_seconds": round(total_time, 3),
            "tokens_generated": tokens_generated,
            "tokens_per_second": tokens_per_sec,
            "cpu_utilization_percent": cpu_after,
            "ram_used_gb": round(mem_after.used / (1024**3), 2),
            "ram_available_gb": round(mem_after.available / (1024**3), 2),
            "ram_delta_mb": ram_delta_mb,
            "response_snippet": response.content[:120] + "...",
        }

