"""
Local AI Runtime Manager for BOLT (Phase 10).
Manages detection, service lifecycle, model inspection, and start procedures
for the local Ollama runtime on Windows.
"""

import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional
import requests

from bolt.config.constants import DEFAULT_OLLAMA_MODEL
from bolt.core.logger import get_logger

logger = get_logger("RuntimeManager")

COMMON_OLLAMA_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ollama" / "ollama.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Ollama" / "ollama.exe",
]


class LocalAIRuntimeManager:
    """Manages local AI runtime detection, daemon lifecycle, and model discovery."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", custom_binary_path: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.recommended_model = DEFAULT_OLLAMA_MODEL
        self.custom_binary_path = Path(custom_binary_path) if custom_binary_path else None

    def detect_ollama_binary(self) -> Optional[Path]:
        """Find the ollama executable on the Windows host."""
        if self.custom_binary_path:
            return self.custom_binary_path if self.custom_binary_path.exists() else None

        # Check PATH first
        ollama_in_path = shutil_which("ollama")
        if ollama_in_path:
            return Path(ollama_in_path)

        # Check standard installation locations
        for p in COMMON_OLLAMA_PATHS:
            if p.exists() and p.is_file():
                return p

        return None

    def is_installed(self) -> bool:
        """Return True if Ollama binary is found on system."""
        return self.detect_ollama_binary() is not None

    def is_recommended_model_installed(self) -> bool:
        """Return True if recommended local model is downloaded."""
        return self.is_model_installed(self.recommended_model)

    def is_service_running(self, timeout: float = 1.0) -> bool:
        """Check if the local Ollama HTTP server is responsive."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> List[str]:
        """Fetch list of models currently downloaded in the local Ollama library."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if name:
                        models.append(name)
                return models
        except Exception as e:
            logger.debug(f"Could not retrieve local Ollama models: {e}")
        return []

    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        """Check whether a specific model (or default recommended model) is available."""
        target = (model_name or self.recommended_model).strip().lower()
        installed = [m.lower() for m in self.get_installed_models()]
        return any(target in m or m in target for m in installed)

    def start_service(self, wait_seconds: float = 3.0) -> bool:
        """
        Attempt to start the Ollama service as a detached background process if installed.
        """
        if self.is_service_running():
            logger.info("Ollama service is already running.")
            return True

        binary = self.detect_ollama_binary()
        if not binary:
            logger.warning("Cannot start Ollama: Binary not found on system.")
            return False

        try:
            logger.info(f"Launching Ollama daemon from '{binary}'...")
            # Windows detached process creation
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(
                [str(binary), "serve"],
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

            # Wait and probe
            start_time = time.time()
            while time.time() - start_time < wait_seconds:
                time.sleep(0.5)
                if self.is_service_running():
                    logger.info("Ollama service started and responding successfully.")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed starting Ollama service: {e}")
            return False

    def get_runtime_status(self) -> Dict[str, Any]:
        """Return comprehensive status diagnostics for UI and setup wizard."""
        binary = self.detect_ollama_binary()
        is_installed = binary is not None
        is_running = self.is_service_running()
        models = self.get_installed_models() if is_running else []
        model_ready = self.is_model_installed(self.recommended_model) if is_running else False

        return {
            "is_installed": is_installed,
            "ollama_installed": is_installed,
            "binary_path": str(binary) if binary else None,
            "is_running": is_running,
            "service_running": is_running,
            "base_url": self.base_url,
            "installed_models": models,
            "models_found": models,
            "recommended_model": self.recommended_model,
            "recommended_model_ready": model_ready,
            "recommended_present": self.recommended_model if model_ready else "",
            "setup_command": f"ollama run {self.recommended_model}",
        }

    get_status_summary = get_runtime_status


def shutil_which(cmd: str) -> Optional[str]:
    import shutil
    return shutil.which(cmd)


_RUNTIME_MGR_INSTANCE: Optional[LocalAIRuntimeManager] = None


def get_runtime_manager() -> LocalAIRuntimeManager:
    global _RUNTIME_MGR_INSTANCE
    if _RUNTIME_MGR_INSTANCE is None:
        _RUNTIME_MGR_INSTANCE = LocalAIRuntimeManager()
    return _RUNTIME_MGR_INSTANCE
