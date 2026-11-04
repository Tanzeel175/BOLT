"""
Application Registry manager for BOLT.
Maintains persistent SQLite storage of discovered and verified applications,
with alias mapping and auto-synchronization.
"""

import re
from typing import Any, Dict, List, Optional
from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger
from bolt.windows.app_discovery import ApplicationDiscovery, DiscoveredApp

logger = get_logger("AppRegistry")

# Common aliases mapping natural queries to canonical application names
COMMON_ALIASES: Dict[str, str] = {
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "code": "visual studio code",
    "chrome": "google chrome",
    "the chrome": "google chrome",
    "browser": "google chrome",
    "the browser": "google chrome",
    "web browser": "google chrome",
    "my browser": "google chrome",
    "google-chrome": "google chrome",
    "brave": "brave",
    "brave browser": "brave",
    "edge": "microsoft edge",
    "msedge": "microsoft edge",
    "calc": "calculator",
    "word": "microsoft word",
    "excel": "microsoft excel",
    "powerpoint": "microsoft powerpoint",
    "cmd": "command prompt",
    "terminal": "powershell",
    "explorer": "file explorer",
    "files": "file explorer",
    "my computer": "file explorer",
    "this pc": "file explorer",
    "antigravity": "antigravity ide",
    "notes": "notepad",
    "text editor": "notepad",
    "task manager": "task manager",
    "taskmgr": "task manager",
    "control panel": "settings",
    "settings": "settings",
}


class ApplicationRegistry:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self.discovery = ApplicationDiscovery()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Seed registry if empty."""
        apps = self.db.get_all_applications()
        if not apps:
            logger.info("Application registry empty. Running initial system discovery...")
            self.refresh_registry()

    def refresh_registry(self) -> int:
        """Scan system and upsert all discovered applications into SQLite."""
        discovered = self.discovery.discover_all()
        count = 0
        for app in discovered:
            self.db.upsert_application(
                name=app.name,
                display_name=app.display_name,
                launch_identifier=app.launch_identifier,
                launch_method=app.launch_method,
                executable_path=app.executable_path,
                category=app.category,
                discovery_source=app.discovery_source,
                is_verified=1 if app.is_verified else 0,
            )
            count += 1
        logger.info(f"Refreshed registry with {count} applications.")
        return count

    def resolve_application(self, query: str, allow_live_discovery: bool = True) -> Optional[Dict[str, Any]]:
        """
        Find application by query using exact match, alias translation, or substring search.
        If not found in registry and allow_live_discovery is True, performs on-demand discovery.
        """
        clean_query = query.strip().lower()
        clean_stripped = re.sub(r"^(?:the|a|my)\s+", "", clean_query).strip()

        # 1. Check alias table
        target_name = COMMON_ALIASES.get(clean_query, COMMON_ALIASES.get(clean_stripped, clean_stripped))

        # 2. Try exact name match in SQLite
        app = self.db.get_application_by_name(target_name)
        if app:
            return app

        # 3. Try fuzzy/substring search in SQLite
        candidates = self.db.search_applications(target_name)
        if candidates:
            # Pick best match: exact match on display name or shortest matching name
            candidates.sort(key=lambda x: (
                0 if x["name"] == target_name else (
                    1 if target_name in x["name"] else 2
                ),
                len(x["name"])
            ))
            return candidates[0]

        # 4. If still not found and discovery allowed, run quick discovery
        if not allow_live_discovery:
            return None

        logger.info(f"App '{query}' not found in cache. Running live discovery...")
        self.refresh_registry()

        # Try again after refresh
        app = self.db.get_application_by_name(target_name)
        if app:
            return app

        candidates = self.db.search_applications(target_name)
        if candidates:
            return candidates[0]

        logger.warning(f"Application '{query}' could not be discovered on system.")
        return None

    def list_applications(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List registered applications, optionally filtered by category."""
        all_apps = self.db.get_all_applications()
        if category:
            return [a for a in all_apps if a.get("category", "").lower() == category.lower()]
        return all_apps

    def record_launch_success(self, app_id: str) -> None:
        """Mark application as verified and record launch timestamp."""
        self.db.record_app_launch_success(app_id)


_REGISTRY_INSTANCE: Optional[ApplicationRegistry] = None


def get_app_registry() -> ApplicationRegistry:
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = ApplicationRegistry()
    return _REGISTRY_INSTANCE
