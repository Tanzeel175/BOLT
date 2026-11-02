"""
Website Registry and Knowledge System for BOLT (Phase 3).
Manages persistent knowledge of known websites, URLs, categories,
authentication requirements, and navigation procedures using SQLite.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger

logger = get_logger("WebsiteRegistry")


@dataclass
class WebsiteEntry:
    id: str
    name: str
    url: str
    category: str = "General"
    description: str = ""
    preferred_browser: str = ""
    last_successful_access: Optional[str] = None
    access_count: int = 0
    auth_status: str = "none"  # "none", "login_required", "login_supported"
    navigation_procedure: str = "direct_url"
    is_verified: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "category": self.category,
            "description": self.description,
            "preferred_browser": self.preferred_browser,
            "last_successful_access": self.last_successful_access,
            "access_count": self.access_count,
            "auth_status": self.auth_status,
            "navigation_procedure": self.navigation_procedure,
            "is_verified": self.is_verified,
        }


class WebsiteRegistry:
    """Persistent Website Knowledge Registry for BOLT."""

    # Common aliases mapping user spoken names to canonical website registry keys
    WEBSITE_ALIASES: Dict[str, str] = {
        "gpt": "chatgpt",
        "chat gpt": "chatgpt",
        "openai": "chatgpt",
        "openai chatgpt": "chatgpt",
        "google gemini": "gemini",
        "bard": "gemini",
        "google mail": "gmail",
        "mail": "gmail",
        "email": "gmail",
        "inbox": "gmail",
        "google search": "google",
        "search": "google",
        "drive": "google drive",
        "gdrive": "google drive",
        "yt": "youtube",
        "you tube": "youtube",
    }

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    @staticmethod
    def validate_url(url_candidate: str) -> Optional[str]:
        """
        Validate and normalize a URL.
        Returns normalized https URL if valid, or None if invalid/untrusted.
        """
        raw = url_candidate.strip()
        if not raw:
            return None

        # Add https scheme if omitted
        if not re.match(r"^https?://", raw, re.IGNORECASE):
            raw = "https://" + raw

        try:
            parsed = urlparse(raw)
            if not parsed.scheme or parsed.scheme.lower() not in ["http", "https"]:
                return None
            if not parsed.netloc or "." not in parsed.netloc:
                return None
            # Reject dangerous/invalid schemes or malformed hosts
            if any(char in parsed.netloc for char in [" ", "<", ">", '"', "'", "\\"]):
                return None
            return raw
        except Exception:
            return None

    def find_website(self, query: str) -> Optional[WebsiteEntry]:
        """
        Look up a website by name, alias, URL, or domain.
        Example: "chatgpt" -> ChatGPT, "mail" -> Gmail, "https://youtube.com" -> YouTube.
        """
        clean = query.strip().lower()
        if not clean:
            return None

        # 1. Check exact aliases
        canonical_name = self.WEBSITE_ALIASES.get(clean, clean)

        # 2. Lookup in SQLite by name
        record = self.db.get_website_by_name(canonical_name)
        if record:
            return WebsiteEntry(**record)

        # 3. Check if query is a URL
        if re.match(r"^https?://", clean) or "." in clean:
            valid_url = self.validate_url(clean)
            if valid_url:
                record = self.db.get_website_by_url(valid_url)
                if record:
                    return WebsiteEntry(**record)

                # Try matching by hostname / domain
                parsed = urlparse(valid_url)
                domain = parsed.netloc.lower().replace("www.", "")
                for site_dict in self.db.get_all_websites():
                    site_domain = urlparse(site_dict["url"]).netloc.lower().replace("www.", "")
                    if domain == site_domain or domain in site_domain:
                        return WebsiteEntry(**site_dict)

        return None

    def register_website(
        self,
        name: str,
        url: str,
        category: str = "General",
        description: str = "",
        preferred_browser: str = "",
        auth_status: str = "none",
        is_verified: bool = True,
    ) -> Optional[WebsiteEntry]:
        """
        Register a new website or update an existing one after validation.
        Rejects invalid or malformed URLs.
        """
        valid_url = self.validate_url(url)
        if not valid_url:
            logger.warning(f"Rejected invalid URL for registration: '{url}'")
            return None

        clean_name = name.strip().lower()
        if not clean_name:
            # Derive name from domain if name not specified
            parsed = urlparse(valid_url)
            clean_name = parsed.netloc.lower().replace("www.", "").split(".")[0]

        record = self.db.upsert_website(
            name=clean_name,
            url=valid_url,
            category=category,
            description=description,
            preferred_browser=preferred_browser,
            auth_status=auth_status,
            is_verified=is_verified,
        )
        logger.info(f"Registered website '{clean_name}' -> {valid_url}")
        return WebsiteEntry(**record)

    def record_access_success(self, site_name_or_id: str) -> None:
        """Update last access timestamp and increment counter for a website."""
        self.db.record_website_access_success(site_name_or_id)

    def get_all_registered_websites(self) -> List[WebsiteEntry]:
        """Fetch all registered websites."""
        rows = self.db.get_all_websites()
        return [WebsiteEntry(**row) for row in rows]


_WEBSITE_REGISTRY: Optional[WebsiteRegistry] = None


def get_website_registry() -> WebsiteRegistry:
    global _WEBSITE_REGISTRY
    if _WEBSITE_REGISTRY is None:
        _WEBSITE_REGISTRY = WebsiteRegistry()
    return _WEBSITE_REGISTRY
