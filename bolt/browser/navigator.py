"""
Unified Browser and Website Navigator for BOLT (Phase 3).
High-level orchestrator coordinating Browser Detection, Tab Management,
Website Registry, Internet Search, and Web Content Understanding.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bolt.browser.ai_web_interaction import AIWebInteraction, get_ai_web_interaction
from bolt.browser.browser_detection import BrowserDetector, BrowserInfo, get_browser_detector
from bolt.browser.browser_manager import BrowserManager, NavigationResult, get_browser_manager
from bolt.browser.content_reader import ContentReader, PageContent, get_content_reader
from bolt.browser.search_engine import SearchEngine, SearchResponse, get_search_engine
from bolt.browser.website_registry import WebsiteEntry, WebsiteRegistry, get_website_registry
from bolt.core.logger import get_logger

logger = get_logger("Navigator")


@dataclass
class BrowserOperationResult:
    handled: bool
    operation: str  # "navigate", "multi_tab", "search", "switch_tab", "read_page", "register_site"
    success: bool
    title: str
    content: str
    browser_name: str = ""
    url: str = ""
    active_tabs_count: int = 0
    raw_data: Optional[Dict[str, Any]] = None


class BrowserNavigator:
    """High-level browser and website intelligence orchestrator."""

    def __init__(
        self,
        browser_mgr: Optional[BrowserManager] = None,
        registry: Optional[WebsiteRegistry] = None,
        search_engine: Optional[SearchEngine] = None,
        reader: Optional[ContentReader] = None,
        ai_interaction: Optional[AIWebInteraction] = None,
        detector: Optional[BrowserDetector] = None,
    ):
        self.browser_mgr = browser_mgr or get_browser_manager()
        self.registry = registry or get_website_registry()
        self.search_engine = search_engine or get_search_engine()
        self.reader = reader or get_content_reader()
        self.ai_interaction = ai_interaction or get_ai_web_interaction()
        self.detector = detector or get_browser_detector()

    def navigate_single(self, target: str, preferred_browser: str = "") -> BrowserOperationResult:
        """Navigate to a website by name, URL, or alias."""
        clean = target.strip()

        # 1. Check if it's in Website Registry
        known_site = self.registry.find_website(clean)
        if known_site:
            nav_res = self.browser_mgr.open_url(
                known_site.url,
                preferred_browser=preferred_browser or known_site.preferred_browser,
                new_tab=True,
            )
            return BrowserOperationResult(
                handled=True,
                operation="navigate",
                success=nav_res.success,
                title=f"Open {known_site.name.title()}",
                content=nav_res.message,
                browser_name=nav_res.browser_name,
                url=known_site.url,
                raw_data=nav_res.__dict__,
            )

        # 2. Check if it's a direct URL
        valid_url = self.registry.validate_url(clean)
        if valid_url:
            nav_res = self.browser_mgr.open_url(valid_url, preferred_browser=preferred_browser, new_tab=True)
            return BrowserOperationResult(
                handled=True,
                operation="navigate",
                success=nav_res.success,
                title="Open Web Address",
                content=nav_res.message,
                browser_name=nav_res.browser_name,
                url=valid_url,
                raw_data=nav_res.__dict__,
            )

        # 3. Not a recognized site and not a valid URL
        return BrowserOperationResult(
            handled=True,
            operation="navigate",
            success=False,
            title="Invalid Website",
            content=f"Could not identify a valid website or URL for `{clean}`. Please provide a full address (e.g. `https://example.com`) or search for it.",
            url=clean,
        )

    def navigate_multi_tabs(self, targets: List[str], preferred_browser: str = "") -> BrowserOperationResult:
        """Open multiple websites in separate tabs."""
        urls_to_open: List[str] = []
        labels: List[str] = []

        for t in targets:
            site = self.registry.find_website(t)
            if site:
                urls_to_open.append(site.url)
                labels.append(site.name.title())
            else:
                valid = self.registry.validate_url(t)
                if valid:
                    urls_to_open.append(valid)
                    labels.append(urlparse(valid).netloc)

        if not urls_to_open:
            return BrowserOperationResult(
                handled=True,
                operation="multi_tab",
                success=False,
                title="Multi-Tab Navigation",
                content="None of the requested website names or URLs could be identified.",
            )

        results = self.browser_mgr.open_multiple_urls(urls_to_open, preferred_browser=preferred_browser)
        success_count = sum(1 for r in results if r.success)
        browser_name = results[0].browser_name if results else "Browser"

        summary_rows = [f"- **{labels[i]}**: `{urls_to_open[i]}`" for i in range(len(urls_to_open))]
        content = (
            f"### 🌐 Opened {success_count}/{len(urls_to_open)} Websites in Separate Tabs\n\n"
            f"Using **{browser_name}**:\n"
            + "\n".join(summary_rows)
        )

        return BrowserOperationResult(
            handled=True,
            operation="multi_tab",
            success=(success_count > 0),
            title="Multi-Tab Navigation",
            content=content,
            browser_name=browser_name,
            active_tabs_count=len(urls_to_open),
        )

    def execute_search(self, query: str, provider: str = "bing", open_in_browser: bool = False) -> BrowserOperationResult:
        """Execute a search query online and return live results or launch in browser."""
        if open_in_browser or "youtube" in provider.lower() or "google" in provider.lower():
            search_url = self.search_engine.get_search_url_for_provider(provider, query)
            nav_res = self.browser_mgr.open_url(search_url, new_tab=True)
            provider_display = "YouTube" if provider.lower() == "youtube" else provider.title()
            return BrowserOperationResult(
                handled=True,
                operation="search",
                success=nav_res.success,
                title=f"{provider_display} Search",
                content=(
                    f"### 🔍 Searching {provider_display} for: *\"{query}\"*\n\n"
                    f"{nav_res.message}\n\n"
                    f"- **Direct Search Link:** [{search_url}]({search_url})"
                ),
                browser_name=nav_res.browser_name,
                url=search_url,
            )

        # Standard live API / HTML scraping search
        resp: SearchResponse = self.search_engine.search_web(query, max_results=5)
        return BrowserOperationResult(
            handled=True,
            operation="search",
            success=(resp.total_results > 0 or bool(resp.search_url)),
            title="Web Search",
            content=resp.markdown_content,
            url=resp.search_url,
        )

    def switch_to_tab(self, tab_name: str) -> BrowserOperationResult:
        """Switch focus to an open browser tab/window matching a query."""
        window = self.browser_mgr.switch_to_tab(tab_name)
        if window:
            return BrowserOperationResult(
                handled=True,
                operation="switch_tab",
                success=True,
                title="Switched Browser Tab",
                content=f"Switched focus to browser tab: **\"{window.title}\"**.",
                browser_name=window.title,
            )
        else:
            return BrowserOperationResult(
                handled=True,
                operation="switch_tab",
                success=False,
                title="Tab Not Found",
                content=f"No open browser tab or window matching *\"{tab_name}\"* was found. Would you like BOLT to open it?",
            )

    def read_and_summarize_page(self, url: str = "") -> BrowserOperationResult:
        """Read, analyze, and format a webpage summary."""
        target_url = url.strip()
        if not target_url:
            target_url = self.reader.find_active_browser_url_or_fallback()

        content: PageContent = self.reader.read_webpage(target_url)
        summary_md = self.reader.format_page_summary_markdown(content)

        return BrowserOperationResult(
            handled=True,
            operation="read_page",
            success=content.is_available,
            title=f"Summary: {content.title[:40]}",
            content=summary_md,
            url=target_url,
        )


_BROWSER_NAVIGATOR: Optional[BrowserNavigator] = None


def get_browser_navigator() -> BrowserNavigator:
    global _BROWSER_NAVIGATOR
    if _BROWSER_NAVIGATOR is None:
        _BROWSER_NAVIGATOR = BrowserNavigator()
    return _BROWSER_NAVIGATOR
