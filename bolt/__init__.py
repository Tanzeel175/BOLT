"""
BOLT - Personal Autonomous AI Assistant for Windows
Phase 1: Foundation and Desktop Interface
"""

import os
import sys
from pathlib import Path

# Ensure Windows environment correctly resolves PySide6 libraries and plugins
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

__version__ = "0.1.0"
__app_name__ = "BOLT"
