"""Application constants, file system paths, and defaults for BOLT."""

from pathlib import Path

# Base Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BOLT_DIR = ROOT_DIR / "bolt"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Database and Log Paths
DB_PATH = DATA_DIR / "bolt.db"
LOG_FILE_PATH = LOGS_DIR / "bolt.log"

# Application Identity
APP_NAME = "BOLT"
APP_SUBTITLE = "Autonomous Windows AI Assistant"
APP_VERSION = "0.1.0"
APP_ORGANIZATION = "BOLT Systems"

# Window Default Dimensions
DEFAULT_WINDOW_WIDTH = 1100
DEFAULT_WINDOW_HEIGHT = 750
MIN_WINDOW_WIDTH = 850
MIN_WINDOW_HEIGHT = 550

# Provider Constants
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_MOCK = "mock"

AVAILABLE_PROVIDERS = [
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_MOCK,
]

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048

# Default System Prompt
DEFAULT_SYSTEM_PROMPT = (
    "You are BOLT, a personal autonomous AI assistant designed for Windows 11. "
    "You are knowledgeable, efficient, concise, and focused on helping the user operate their PC, "
    "solve technical problems, manage workflows, browse the web, write code, and organize information. "
    "Respond in clean, well-formatted markdown. Be professional, direct, and helpful."
)

