"""
Windows Computer Understanding and Application Control package for BOLT (Phase 2).
"""

from .app_discovery import ApplicationDiscovery, DiscoveredApp
from .app_registry import ApplicationRegistry, get_app_registry
from .window_manager import WindowManager, get_window_manager, WindowInfo
from .app_controller import AppController, get_app_controller
from .file_manager import FileManager, get_file_manager
from .system_info import SystemInfo
from .intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher, IntentResult

__all__ = [
    "ApplicationDiscovery",
    "DiscoveredApp",
    "ApplicationRegistry",
    "get_app_registry",
    "WindowManager",
    "get_window_manager",
    "WindowInfo",
    "AppController",
    "get_app_controller",
    "FileManager",
    "get_file_manager",
    "SystemInfo",
    "WindowsIntentDispatcher",
    "get_intent_dispatcher",
    "IntentResult",
]

