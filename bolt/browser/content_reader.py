"""
Website Content Reader and Analyzer for BOLT (Phase 3).
Parses accessible webpage text, extracts headings, identifies useful links,
detects login requirements and site unavailability, and generates structured summaries.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.core.logger import get_logger
from bolt.windows.window_manager import WindowManager, get_window_manager

logger = get_logger("ContentReader")


@dataclass
class PageLink:
    text: str
    url: str

    def to_dict(self) -> Dict[str, str]:
        return {"text": self.text, "url": self.url}


@dataclass
class PageContent:
    url: str
    title: str
    is_available: bool = True
    status_code: int = 200
    is_login_page: bool = False
    headings: Dict[str, List[str]] = field(default_factory=dict)
    summary_text: str = ""
    full_text_sample: str = ""
    links: List[PageLink] = field(default_factory=list)
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "is_available": self.is_available,
            "status_code": self.status_code,
            "is_login_page": self.is_login_page,
            "headings": self.headings,
            "summary_text": self.summary_text,
            "links": [it.to_dict() for it in self.links],
            "error_message": self.error_message,
        }


class ContentReader:
    """Reads, extracts, and summarizes content from accessible websites."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Keywords signaling an authentication wall / login screen
    LOGIN_INDICATORS = [
        "sign in", "log in", "login", "password", "enter your password",
        "create account", "two-factor authentication", "mfa", "sso login",
        "forgot password", "authentication required"
    ]

    def __init__(
        self,
        registry: Optional[WebsiteRegistry] = None,
        window_mgr: Optional[WindowManager] = None,
    ):
        self.registry = registry or get_website_registry()
        self.window_mgr = window_mgr or get_window_manager()
        self._last_read_url: str = "https://www.google.com/"

    def read_webpage(self, url: str) -> PageContent:
        """
        Fetch, parse, and analyze content from a target URL.
        Detects login walls, unavailability, headings, and links.
        """
        valid_url = self.registry.validate_url(url)
        if not valid_url:
            return PageContent(
                url=url,
                title="Invalid URL",
                is_available=False,
                status_code=400,
                error_message=f"The URL '{url}' is malformed or invalid.",
            )

        self._last_read_url = valid_url
        logger.info(f"Reading webpage content for: {valid_url}")

        try:
            resp = requests.get(valid_url, headers=self.HEADERS, timeout=12.0)
            status_code = resp.status_code

            if status_code in [401, 403]:
                return PageContent(
                    url=valid_url,
                    title="Access Restricted / Authentication Required",
                    is_available=True,
                    status_code=status_code,
                    is_login_page=True,
                    error_message="This website requires authentication. Please log in manually in your browser.",
                )

            if status_code >= 400:
                return PageContent(
                    url=valid_url,
                    title=f"HTTP Error {status_code}",
                    is_available=False,
                    status_code=status_code,
                    error_message=f"Website returned HTTP error {status_code}.",
                )

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            if not title:
                h1 = soup.find("h1")
                title = h1.get_text(strip=True) if h1 else urlparse(valid_url).netloc

            # Detect login indicators in form / inputs / text
            has_password_field = bool(soup.find("input", {"type": "password"}))
            page_lower = resp.text.lower()
            auth_text_hits = sum(1 for kw in self.LOGIN_INDICATORS if kw in page_lower)
            is_login = has_password_field or (auth_text_hits >= 3 and any(w in valid_url.lower() for w in ["login", "signin", "auth", "accounts"]))

            # Extract headings
            headings: Dict[str, List[str]] = {"h1": [], "h2": [], "h3": []}
            for tag in ["h1", "h2", "h3"]:
                for el in soup.find_all(tag)[:6]:
                    txt = el.get_text(strip=True)
                    if txt and len(txt) > 2 and txt not in headings[tag]:
                        headings[tag].append(txt)

            # Extract clean paragraphs
            # Remove scripts, styles, nav, footer, iframe
            for unwanted in soup(["script", "style", "noscript", "svg", "header", "footer"]):
                unwanted.decompose()

            paragraphs = []
            for p in soup.find_all(["p", "article", "section"]):
                ptxt = p.get_text(strip=True)
                if len(ptxt) >= 40 and ptxt not in paragraphs:
                    paragraphs.append(ptxt)

            # Extract notable links
            links: List[PageLink] = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                atxt = a.get_text(strip=True)
                if href and atxt and not href.startswith(("#", "javascript:", "mailto:")):
                    full_href = urljoin(valid_url, href)
                    if full_href.startswith("http") and not any(l.url == full_href for l in links):
                        links.append(PageLink(text=atxt[:60], url=full_href))
                    if len(links) >= 8:
                        break

            # Create clean summary text
            summary_parts = []
            for p in paragraphs[:3]:
                summary_parts.append(p)
            summary_text = " ".join(summary_parts) if summary_parts else "No extensive text paragraphs found."

            return PageContent(
                url=valid_url,
                title=title,
                is_available=True,
                status_code=status_code,
                is_login_page=is_login,
                headings=headings,
                summary_text=summary_text,
                full_text_sample="\n\n".join(paragraphs[:6]),
                links=links,
            )

        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection failed for {valid_url}")
            return PageContent(
                url=valid_url,
                title="Website Unavailable",
                is_available=False,
                status_code=0,
                error_message=f"Could not connect to `{valid_url}`. The domain may be down or unreachable.",
            )
        except requests.exceptions.Timeout:
            logger.warning(f"Connection timed out for {valid_url}")
            return PageContent(
                url=valid_url,
                title="Connection Timeout",
                is_available=False,
                status_code=0,
                error_message=f"Request to `{valid_url}` timed out.",
            )
        except Exception as e:
            logger.error(f"Error reading webpage {valid_url}: {e}")
            return PageContent(
                url=valid_url,
                title="Error Reading Webpage",
                is_available=False,
                status_code=0,
                error_message=str(e),
            )

    def format_page_summary_markdown(self, content: PageContent) -> str:
        """Format PageContent into a rich executive Markdown report for chat display."""
        if not content.is_available:
            return (
                f"### ⚠️ Website Unavailable\n\n"
                f"- **Target URL:** `{content.url}`\n"
                f"- **Status:** {content.error_message}\n\n"
                f"*Please verify your internet connection or check if the address is correct.*"
            )

        if content.is_login_page:
            return (
                f"### 🔒 Authentication Required\n\n"
                f"- **Webpage:** [{content.title}]({content.url})\n"
                f"- **Status:** Login page detected (`HTTP {content.status_code}`).\n\n"
                f"> **Security Notice:** BOLT does not store, extract, or input user passwords. "
                f"Please sign in manually in your browser to access your account."
            )

        lines = [
            f"### 📄 Webpage Summary: *{content.title}*",
            f"**URL:** `{content.url}`\n",
        ]

        # Headings
        all_headings = []
        if content.headings.get("h1"):
            all_headings.extend([f"**H1:** {h}" for h in content.headings["h1"][:2]])
        if content.headings.get("h2"):
            all_headings.extend([f"**H2:** {h}" for h in content.headings["h2"][:3]])

        if all_headings:
            lines.append("**Key Topics / Sections:**\n- " + "\n- ".join(all_headings) + "\n")

        # Summary text
        if content.summary_text:
            lines.append(f"**Content Overview:**\n{content.summary_text}\n")

        # Key links
        if content.links:
            links_md = [f"- [{link.text}]({link.url})" for link in content.links[:5]]
            lines.append("**Notable Links on Page:**\n" + "\n".join(links_md))

        return "\n".join(lines)

    def find_active_browser_url_or_fallback(self) -> str:
        """
        Identify what website is likely open in the user's active browser window,
        or fall back to the most recently navigated/read URL.
        """
        windows = self.window_mgr.get_visible_windows()
        for w in windows:
            title_lower = w.title.lower()
            for site in self.registry.get_all_registered_websites():
                if site.name in title_lower or site.category.lower() in title_lower:
                    return site.url

        return self._last_read_url


_CONTENT_READER: Optional[ContentReader] = None


def get_content_reader() -> ContentReader:
    global _CONTENT_READER
    if _CONTENT_READER is None:
        _CONTENT_READER = ContentReader()
    return _CONTENT_READER

