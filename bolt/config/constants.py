"""Application constants, file system paths, and defaults for BOLT."""

import os
from pathlib import Path
import sys

from bolt.__version__ import (
    __app_name__,
    __author__,
    __description__,
    __organization__,
    __subtitle__,
    __version__,
)

# Application Identity
APP_NAME = __app_name__
APP_SUBTITLE = __subtitle__
APP_VERSION = __version__
APP_ORGANIZATION = __organization__
APP_AUTHOR = __author__
APP_DESCRIPTION = __description__
APP_USER_MODEL_ID = "BOLTSystems.BOLT.Assistant.1.0"

# Packaging / Frozen Detection
IS_FROZEN = getattr(sys, "frozen", False)

# Base Paths
if IS_FROZEN:
    # Running as a compiled PyInstaller executable
    INSTALL_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(INSTALL_DIR)))
    ROOT_DIR = INSTALL_DIR
else:
    # Running from Python source repository
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    BUNDLE_DIR = ROOT_DIR
    INSTALL_DIR = ROOT_DIR

BOLT_DIR = ROOT_DIR / "bolt"
ASSETS_DIR = ROOT_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- Persistent Windows User Data Directories (Phase 10) ----------------
# Ensures database, logs, workflows, and memory survive application updates and uninstalls.
# SQLite databases must NEVER be written to the temporary _MEIPASS extraction folder.
if IS_FROZEN or os.environ.get("BOLT_USE_APPDATA") == "1":
    local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    USER_DATA_ROOT = Path(local_app_data) / "BOLT"
else:
    USER_DATA_ROOT = ROOT_DIR

DATA_DIR = Path(os.environ.get("BOLT_DATA_DIR", str(USER_DATA_ROOT / "data")))
LOGS_DIR = Path(os.environ.get("BOLT_LOGS_DIR", str(USER_DATA_ROOT / "logs")))
BACKUPS_DIR = Path(os.environ.get("BOLT_BACKUPS_DIR", str(USER_DATA_ROOT / "backups")))
WORKSPACE_DIR = Path(os.environ.get("BOLT_WORKSPACE_DIR", str(USER_DATA_ROOT / "workspace")))
CONFIG_DIR = USER_DATA_ROOT / "config"

# Aliases
BACKUP_DIR = BACKUPS_DIR

# Ensure all runtime and user data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Database, Logs, and Icon Paths
DB_PATH = DATA_DIR / "bolt.db"
DATABASE_PATH = DB_PATH
LOG_FILE_PATH = LOGS_DIR / "bolt.log"
SECURITY_LOG_PATH = LOGS_DIR / "security.log"
APP_ICON_ICO = ASSETS_DIR / "bolt_icon.ico"
APP_ICON_PNG = ASSETS_DIR / "bolt_icon.png"

# Window Default Dimensions
DEFAULT_WINDOW_WIDTH = 1100
DEFAULT_WINDOW_HEIGHT = 750
MIN_WINDOW_WIDTH = 850
MIN_WINDOW_HEIGHT = 550

# Provider Constants
PROVIDER_OLLAMA = "ollama"
PROVIDER_NEBIUS = "nebius"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_CUSTOM = "custom"
PROVIDER_MOCK = "mock"

AVAILABLE_PROVIDERS = [
    PROVIDER_OLLAMA,
    PROVIDER_NEBIUS,
    PROVIDER_CUSTOM,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_MOCK,
]

DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_NEBIUS_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_CUSTOM_MODEL = "llama-3.3-70b-versatile"
DEFAULT_CUSTOM_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_CUSTOM_NAME = "Custom / Any Model"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048

# Official Nebius Token Factory Models (OpenAI-compatible endpoints)
SUPPORTED_NEBIUS_MODELS = [
    "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "meta-llama/Meta-Llama-3.1-405B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-R1",
    "mistralai/Mistral-Nemo-Instruct-2407",
]

# Default System Prompt (Optimized for fast CPU inference & conciseness)
DEFAULT_SYSTEM_PROMPT = (
    "You are BOLT, a personal autonomous AI assistant designed for Windows 11. "
    "You are knowledgeable, efficient, direct, and concise. "
    "Provide clear, succinct, and helpful answers without unnecessary preamble or filler text. "
    "For simple greetings or brief queries, respond warmly in 1 to 2 sentences. "
    "Respond in clean, well-formatted markdown."
)
