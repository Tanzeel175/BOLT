"""Logging subsystem for BOLT."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from bolt.config.constants import LOG_FILE_PATH, LOGS_DIR

_ROOT_LOGGER_INITIALIZED = False


def setup_logger(log_level: str = "INFO") -> logging.Logger:
    """Initialize root application logger with console and rotating file output."""
    global _ROOT_LOGGER_INITIALIZED

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger("BOLT")
    logger.setLevel(numeric_level)

    if not _ROOT_LOGGER_INITIALIZED:
        # Avoid duplicate handlers if called multiple times
        logger.handlers.clear()

        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-7s] [%(name)s:%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (Rotating: 5MB per file, max 5 backups)
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE_PATH),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        _ROOT_LOGGER_INITIALIZED = True

    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """Get a named sub-logger inheriting the BOLT root configuration."""
    if not _ROOT_LOGGER_INITIALIZED:
        setup_logger()

    if module_name:
        return logging.getLogger(f"BOLT.{module_name}")
    return logging.getLogger("BOLT")
