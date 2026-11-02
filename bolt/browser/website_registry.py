"""
Website Registry and Knowledge subsystem for BOLT.
Maintains persistent website knowledge, aliases, URL normalization, validation, and access history.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger

logger = get_logger("WebsiteRegistry")

# Common aliases and natural phrasing mapped to website names
COMMON_WEBSITE_ALIASES: Dict[str, str] = {
    "chatgpt": "chatgpt",
    "chat gpt": "chatgpt",
    "gpt": "chatgpt",
    "openai": "chatgpt",
    "gemini": "gemini",
    "google gemini": "gemini",
    "bard": "gemini",
    "gmail": "gmail",
    "mail": "gmail",
    "google mail": "gmail",
    "google": "google",
    "google search": "google",
    "search": "google",
    "google drive": "google drive",
    "drive": "google drive",
    "gdrive": "google drive",
    "youtube": "youtube",
    "yt": "youtube",
    "github": "github",
    "gh": "github",
}


class WebsiteRegistry:
    """Manages verified website knowledge, aliases, and SQLite persistence."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Validate URL format and protocol.
        Rejects empty, non-http/https, and dangerous schemes (javascript:, file:, data:).
        """
        if not url or not isinstance(url, str):
            return False

        url_clean = url.strip()
        # Security: block dangerous protocols
        lower = url_clean.lower()
        if any(lower.startswith(bad) for bad in ["javascript:", "file:", "data:", "vbscript:"]):
            return False

        try:
            parsed = urlparse(url_clean)
            # Accept if scheme is http/https and has valid netloc
            if parsed.scheme in ["http", "https"] and bool(parsed.netloc):
                return True
            # Also accept domain format like "example.com" or "www.example.com"
            domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+.*$"
            if re.match(domain_pattern, url_clean):
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def normalize_url(url: str) -> str:
        """Ensure URL has a proper http or https scheme and clean formatting."""
        clean = url.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            clean = f"https://{clean}"
        return clean

    def resolve_website(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Resolve website by natural query using alias lookup, exact name match, or fuzzy search.
        Returns website record dictionary if found, otherwise None.
        """
        clean_query = query.strip().lower()

        # 1. Alias lookup
        target_name = COMMON_WEBSITE_ALIASES.get(clean_query, clean_query)

        # 2. Exact match in SQLite
        site = self.db.get_website_by_name(target_name)
        if site:
            return site

        # 3. Fuzzy search in SQLite
        candidates = self.db.search_websites(target_name)
        if candidates:
            # Prefer match where name or display_name starts with query
            for c in candidates:
                if c["name"].startswith(target_name) or c["display_name"].lower().startswith(target_name):
                    return c
            return candidates[0]

        return None

    def register_website(
        self,
        name: str,
        url: str,
        display_name: Optional[str] = None,
        category: str = "General",
        description: str = "",
        preferred_browser: str = "",
        auth_status: str = "none",
        navigation_procedure: str = "",
    ) -> Dict[str, Any]:
        """
        Validate and register a new website into persistent memory.
        Refuses invalid or unsafe URLs.
        """
        if not self.is_valid_url(url):
            return {
                "success": False,
                "error": f"Invalid or unsafe URL format: '{url}'. Only HTTP/HTTPS URLs are allowed.",
            }

        norm_url = self.normalize_url(url)
        name_clean = name.strip().lower()
        disp_name = display_name or name.title()

        site_id = self.db.upsert_website(
            name=name_clean,
            display_name=disp_name,
            url=norm_url,
            category=category,
            description=description,
            preferred_browser=preferred_browser,
            auth_status=auth_status,
            navigation_procedure=navigation_procedure,
            is_verified=1,
        )

        logger.info(f"Registered website '{disp_name}' ({norm_url}) in category '{category}'")
        return {
            "success": True,
            "id": site_id,
            "name": name_clean,
            "display_name": disp_name,
            "url": norm_url,
            "category": category,
        }

    def list_websites(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List registered websites, optionally filtered by category."""
        all_sites = self.db.get_all_websites()
        if category:
            return [s for s in all_sites if s.get("category", "").lower() == category.lower()]
        return all_sites

    def record_access_success(self, name_or_id: str) -> None:
        """Record successful website navigation."""
        self.db.record_website_access_success(name_or_id)


_REGISTRY_INSTANCE: Optional[WebsiteRegistry] = None


def get_website_registry() -> WebsiteRegistry:
    """Singleton getter for WebsiteRegistry."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = WebsiteRegistry()
    return _REGISTRY_INSTANCE

