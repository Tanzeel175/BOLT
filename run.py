"""
BOLT - Personal Autonomous AI Assistant for Windows
Entry point to launch the BOLT Desktop Application.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in Python sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Windows taskbar grouping & modern AppUserModelID
if sys.platform == "win32":
    try:
        import ctypes
        from bolt.config.constants import APP_USER_MODEL_ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass

# Register Windows DLL directories & plugin paths for PySide6 and shiboken6
if sys.platform == "win32":
    for p in sys.path:
        try:
            p_path = Path(p)
            for sub in ("PySide6", "shiboken6"):
                dll_dir = p_path / sub
                if dll_dir.is_dir() and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(dll_dir))

            pyside_dir = p_path / "PySide6"
            if pyside_dir.is_dir():
                plugins_dir = pyside_dir / "plugins"
                if plugins_dir.is_dir():
                    os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins_dir / "platforms")
        except Exception:
            pass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from bolt.config.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
    APP_ICON_PNG,
    APP_ICON_ICO,
)
from bolt.config.settings import get_settings
from bolt.core.data_manager import get_data_manager
from bolt.core.database import get_database
from bolt.core.logger import setup_logger, get_logger
from bolt.ui.main_window import MainWindow
from bolt.ui.styles.theme import DARK_THEME_QSS


def main():
    # 1. Initialize Settings and Structured Logging
    settings = get_settings()
    logger = setup_logger(log_level=settings.log_level)
    logger.info("=" * 60)
    logger.info(f"Starting {APP_NAME} v{APP_VERSION} (Phase 10: Desktop App & Deployment)")
    logger.info(f"Active Provider: {settings.provider} | Model: {settings.current_model}")
    logger.info("=" * 60)

    # 2. Verify Persistent User Storage Isolation & SQLite Database Initialized
    data_mgr = get_data_manager()
    data_mgr.initialize_storage()
    db = get_database()
    logger.info("Persistent storage verified and SQLite Database ready.")

    # 2b. Pre-warm local Ollama model in background to eliminate cold-load delay
    if settings.provider == "ollama":
        try:
            from bolt.ai.provider_manager import get_ai_provider_manager
            pm = get_ai_provider_manager()
            ollama_p = pm.get_provider("ollama")
            if hasattr(ollama_p, "preload_model"):
                ollama_p.preload_model()
        except Exception:
            pass

    # 3. Configure Windows High-DPI Scaling & Modern Qt Environment
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)

    # Allow app to keep running in system tray when main window is closed/hidden
    app.setQuitOnLastWindowClosed(False)

    # Set Application Icon
    if APP_ICON_PNG.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    elif APP_ICON_ICO.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_ICO)))

    # 4. Apply Dark Theme Stylesheet
    app.setStyleSheet(DARK_THEME_QSS)

    # 5. Create and Show Main Desktop Interface Window
    main_window = MainWindow()
    main_window.show()

    logger.info("BOLT desktop interface window displayed.")

    # 6. Execute Qt Event Loop
    exit_code = app.exec()
    logger.info(f"BOLT terminated gracefully with exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: Unhandled exception starting BOLT: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
