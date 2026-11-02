"""
Web Content Reader and Extractor for BOLT.
Parses accessible webpage text, extracts headings, links, detects login walls, and generates summaries.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

from bolt.core.logger import get_logger

logger = get_logger("ContentReader")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class ContentReader:
    """Extracts, cleans, and analyzes webpage content with authentication detection."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_page(self, url: str, timeout: float = 12.0) -> Dict[str, Any]:
        """Fetch webpage HTML using HTTP GET with redirect and error handling."""
        logger.info(f"Fetching webpage content from: {url}")
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 400:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: Website returned error or is unavailable.",
                    "status_code": resp.status_code,
                    "url": url,
                    "final_url": resp.url,
                }

            return {
                "success": True,
                "html": resp.text,
                "url": url,
                "final_url": resp.url,
                "status_code": resp.status_code,
            }
        except requests.exceptions.Timeout:
            logger.warning(f"Connection timed out for: {url}")
            return {
                "success": False,
                "error": f"Connection timed out while loading {url}.",
                "url": url,
            }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return {
                "success": False,
                "error": f"Could not connect to {url}: {str(e)}",
                "url": url,
            }

    def parse_content(self, html: str, base_url: str = "") -> Dict[str, Any]:
        """
        Parse HTML into structured components: title, headings, text content, links,
        and authentication requirement status.
        """
        soup = BeautifulSoup(html, "html.parser")

        # 1. Detect Login / Authentication Wall
        requires_auth = False
        auth_reasons = []

        # Check for password inputs
        if soup.find("input", {"type": "password"}):
            requires_auth = True
            auth_reasons.append("Password input detected on page")

        # Check for login form actions or buttons
        login_btn = soup.find(
            lambda tag: tag.name in ["button", "a", "input"]
            and any(
                term in tag.get_text().lower() or term in str(tag.get("value", "")).lower()
                for term in ["sign in", "log in", "login", "continue with google", "continue with apple"]
            )
        )
        # Check text signals
        page_lower = soup.get_text().lower()
        if any(term in page_lower for term in [
            "sign in to continue", "log in to your account", "enter your password",
            "authentication required", "sign in with your account"
        ]):
            requires_auth = True
            auth_reasons.append("Authentication text detected")

        # Remove script, style, noscript, svg, nav elements for clean content extraction
        for element in soup(["script", "style", "noscript", "svg", "header", "footer"]):
            element.decompose()

        # 2. Page Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # 3. Meta Description
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag["content"].strip()

        # 4. Headings
        headings: List[str] = []
        for h in soup.find_all(["h1", "h2", "h3"]):
            text = h.get_text().strip()
            if text and text not in headings and len(text) < 120:
                headings.append(text)

        # 5. Body paragraphs
        paragraphs: List[str] = []
        for p in soup.find_all("p"):
            text = re.sub(r"\s+", " ", p.get_text()).strip()
            if len(text) > 30 and text not in paragraphs:
                paragraphs.append(text)

        # 6. Outbound links
        links: List[Dict[str, str]] = []
        seen_hrefs = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text().strip()
            full_url = urljoin(base_url, href) if base_url else href
            if (
                full_url.startswith("http")
                and full_url not in seen_hrefs
                and len(text) > 3
                and not full_url.endswith((".png", ".jpg", ".svg", ".css", ".js"))
            ):
                seen_hrefs.add(full_url)
                links.append({"text": text[:60], "url": full_url})
                if len(links) >= 8:
                    break

        return {
            "title": title or "Untitled Webpage",
            "meta_description": meta_desc,
            "headings": headings[:8],
            "paragraphs": paragraphs[:12],
            "links": links,
            "requires_auth": requires_auth,
            "auth_reasons": auth_reasons,
        }

    def summarize_page(self, parsed: Dict[str, Any], url: str = "") -> str:
        """Create a structured Markdown summary of the parsed webpage."""
        title = parsed.get("title", "Webpage")
        meta = parsed.get("meta_description", "")
        headings = parsed.get("headings", [])
        paragraphs = parsed.get("paragraphs", [])
        links = parsed.get("links", [])
        requires_auth = parsed.get("requires_auth", False)

        lines = [f"### 🌐 Webpage Content: **{title}**\n"]
        if url:
            lines.append(f"**URL:** `{url}`\n")

        if requires_auth:
            lines.append(
                "> ⚠️ **Authentication Required:** This website requires a user login or credentials. "
                "For your privacy and security, BOLT does not automate passwords. Please complete authentication in your browser.\n"
            )

        if meta:
            lines.append(f"**Overview:** *{meta}*\n")

        if headings:
            lines.append("**Key Sections / Headings:**")
            for h in headings[:5]:
                lines.append(f"- {h}")
            lines.append("")

        if paragraphs:
            lines.append("**Main Content Highlights:**")
            for p in paragraphs[:4]:
                lines.append(f"> {p}\n")

        if links:
            lines.append("**Important Links on Page:**")
            for lnk in links[:5]:
                lines.append(f"- [{lnk['text']}]({lnk['url']})")
            lines.append("")

        return "\n".join(lines)


_READER_INSTANCE: Optional[ContentReader] = None


def get_content_reader() -> ContentReader:
    """Singleton getter for ContentReader."""
    global _READER_INSTANCE
    if _READER_INSTANCE is None:
        _READER_INSTANCE = ContentReader()
    return _READER_INSTANCE

