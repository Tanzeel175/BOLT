"""
Browser Controller subsystem for BOLT.
Coordinates Playwright browser automation, tab management, multi-tab navigation,
session reuse, webpage inspection, and fallback native execution.
"""

import os
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from bolt.core.logger import get_logger
from bolt.core.network_manager import get_network_manager, OFFLINE_SEARCH_ERROR_MESSAGE
from bolt.browser.browser_detector import BrowserDetector, get_browser_detector
from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.browser.content_reader import ContentReader, get_content_reader
from bolt.browser.search_engine import SearchEngine, get_search_engine

logger = get_logger("BrowserController")


class BrowserController:
    """Manages browser sessions, tabs, URL navigation, and webpage content inspection."""

    def __init__(
        self,
        detector: Optional[BrowserDetector] = None,
        registry: Optional[WebsiteRegistry] = None,
        content_reader: Optional[ContentReader] = None,
        search_engine: Optional[SearchEngine] = None,
    ):
        self.detector = detector or get_browser_detector()
        self.registry = registry or get_website_registry()
        self.content_reader = content_reader or get_content_reader()
        self.search_engine = search_engine or get_search_engine()

        # Playwright instances (lazy initialized)
        self._playwright = None
        self._browser = None
        self._context = None
        self._active_page = None
        self._is_headless: Optional[bool] = None

    def _determine_headless(self) -> bool:
        """Determine if browser should run headless based on environment."""
        if self._is_headless is not None:
            return self._is_headless
        env_val = os.environ.get("BOLT_HEADLESS_BROWSER", "").lower()
        if env_val in ["1", "true", "yes"]:
            return True
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return True
        return False

    def set_headless(self, headless: bool) -> None:
        """Manually override headless mode (useful for unit testing)."""
        if self._playwright and self._is_headless != headless:
            self.close_browser()
        self._is_headless = headless

    def _ensure_browser(self, preferred_browser: Optional[str] = None) -> bool:
        """Initialize Playwright and launch browser instance if not already running."""
        if self._browser and self._context:
            return True

        from playwright.sync_api import sync_playwright

        headless = self._determine_headless()
        browser_info = self.detector.get_preferred_or_default_browser(preferred_browser)
        channel = browser_info.get("channel", "msedge") if browser_info else "msedge"

        logger.info(f"Initializing browser engine (channel='{channel}', headless={headless})...")

        try:
            if not self._playwright:
                self._playwright = sync_playwright().start()

            # Launch using installed Edge or Chrome channel
            try:
                self._browser = self._playwright.chromium.launch(
                    channel=channel,
                    headless=headless,
                )
            except Exception as e:
                logger.warning(f"Failed to launch with channel '{channel}': {e}. Falling back to default chromium.")
                self._browser = self._playwright.chromium.launch(headless=headless)

            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            return False

    def open_url(
        self,
        query_or_url: str,
        new_tab: bool = True,
        preferred_browser: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Open a website by name (e.g. 'ChatGPT', 'Gemini', 'Gmail') or direct URL.
        1. Resolves name via WebsiteRegistry.
        2. Validates and normalizes URL.
        3. Reuses existing tab if the URL is already open.
        4. Navigates, verifies page loading, and detects login requirements.
        """
        logger.info(f"Open URL requested: '{query_or_url}'")
        clean_input = query_or_url.strip()

        # 1. Resolve in Website Registry
        site_record = self.registry.resolve_website(clean_input)
        if site_record:
            target_url = site_record["url"]
            display_name = site_record.get("display_name", site_record["name"])
            site_name = site_record["name"]
        else:
            # Check if it is a valid URL
            if not self.registry.is_valid_url(clean_input):
                return {
                    "success": False,
                    "error": f"'{clean_input}' is neither a known website nor a valid web URL.",
                    "url": clean_input,
                }
            target_url = self.registry.normalize_url(clean_input)
            display_name = urlparse(target_url).netloc
            site_name = display_name

        # Check connectivity for external web addresses
        if not any(target_url.startswith(p) for p in ["http://localhost", "http://127.0.0.1", "file://"]):
            if not get_network_manager().is_internet_available():
                return {
                    "success": False,
                    "error": OFFLINE_SEARCH_ERROR_MESSAGE,
                    "url": target_url,
                    "display_name": display_name,
                    "is_offline": True,
                }

        # 2. Initialize browser
        if not self._ensure_browser(preferred_browser):
            # Fallback to native OS browser open if Playwright fails
            try:
                import webbrowser
                webbrowser.open(target_url)
                return {
                    "success": True,
                    "action": "opened_native",
                    "display_name": display_name,
                    "url": target_url,
                    "title": display_name,
                    "message": f"Opened {display_name} ({target_url}) in system default browser.",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to launch browser: {e}",
                    "url": target_url,
                }

        # 3. Check for Tab Reuse: Is this URL or domain already open in any tab?
        open_pages = self._context.pages
        target_domain = urlparse(target_url).netloc.lower()

        for page in open_pages:
            try:
                page_domain = urlparse(page.url).netloc.lower()
                if (page_domain and page_domain == target_domain) or page.url.rstrip("/") == target_url.rstrip("/"):
                    page.bring_to_front()
                    self._active_page = page
                    logger.info(f"Reused existing browser tab for '{display_name}' ({page.url}).")
                    self.registry.record_access_success(site_name)
                    return {
                        "success": True,
                        "action": "reused_tab",
                        "display_name": display_name,
                        "url": page.url,
                        "title": page.title(),
                        "message": f"Switched to existing tab for {display_name}.",
                    }
            except Exception:
                continue

        # 4. Open in new tab or reuse blank page
        try:
            if not new_tab and self._active_page:
                target_page = self._active_page
            elif open_pages and open_pages[-1].url == "about:blank":
                target_page = open_pages[-1]
            else:
                target_page = self._context.new_page()

            # Navigate with DOM loaded wait
            resp = target_page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            self._active_page = target_page
            target_page.bring_to_front()

            status_code = resp.status if resp else 200
            if status_code >= 400:
                return {
                    "success": False,
                    "error": f"HTTP {status_code} error loading {display_name}.",
                    "url": target_url,
                    "status_code": status_code,
                }

            page_title = target_page.title()

            # 5. Check if page requires authentication
            page_content = target_page.content()
            parsed = self.content_reader.parse_content(page_content, base_url=target_url)
            requires_auth = parsed.get("requires_auth", False)

            # Record success in registry
            self.registry.record_access_success(site_name)

            auth_msg = " (Note: This page requires authentication/sign-in)." if requires_auth else ""
            logger.info(f"Successfully navigated to '{display_name}' ({page_title}){auth_msg}")

            return {
                "success": True,
                "action": "navigated",
                "display_name": display_name,
                "url": target_page.url,
                "title": page_title,
                "requires_auth": requires_auth,
                "tab_count": len(self._context.pages),
                "message": f"Successfully opened {display_name} in browser.{auth_msg}",
            }

        except Exception as e:
            logger.error(f"Failed to navigate to '{target_url}': {e}")
            return {
                "success": False,
                "error": f"Failed to load {display_name}: {str(e)}",
                "url": target_url,
            }

    def open_multiple_urls(self, targets: List[str]) -> List[Dict[str, Any]]:
        """Open multiple websites in separate browser tabs sequentially."""
        logger.info(f"Opening {len(targets)} URLs in separate tabs...")
        results = []
        for target in targets:
            res = self.open_url(target, new_tab=True)
            results.append(res)
            time.sleep(0.3)
        return results

    def get_open_tabs(self) -> List[Dict[str, Any]]:
        """Return metadata for all currently open browser tabs."""
        if not self._context:
            return []

        tabs = []
        for i, page in enumerate(self._context.pages):
            try:
                tabs.append({
                    "index": i,
                    "title": page.title() or "Untitled",
                    "url": page.url,
                    "is_active": (page == self._active_page),
                })
            except Exception:
                continue
        return tabs

    def switch_to_tab(self, target: Union[int, str]) -> Dict[str, Any]:
        """
        Switch to tab by numeric index or title/URL substring.
        Brings target tab to the front.
        """
        if not self._context or not self._context.pages:
            return {"success": False, "error": "No browser tabs are currently open."}

        pages = self._context.pages
        selected_page = None

        if isinstance(target, int):
            if 0 <= target < len(pages):
                selected_page = pages[target]
        else:
            q_lower = str(target).lower().strip()
            # Match title or URL
            for page in pages:
                try:
                    if q_lower in page.title().lower() or q_lower in page.url.lower():
                        selected_page = page
                        break
                except Exception:
                    continue

        if selected_page:
            selected_page.bring_to_front()
            self._active_page = selected_page
            return {
                "success": True,
                "title": selected_page.title(),
                "url": selected_page.url,
                "message": f"Switched to tab: \"{selected_page.title()}\"",
            }
        else:
            return {
                "success": False,
                "error": f"Could not find open tab matching '{target}'.",
            }

    def close_tab(self, target: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """Close specified tab or the active tab."""
        if not self._context or not self._context.pages:
            return {"success": False, "error": "No open tabs to close."}

        pages = self._context.pages
        page_to_close = None

        if target is None:
            page_to_close = self._active_page or pages[-1]
        elif isinstance(target, int):
            if 0 <= target < len(pages):
                page_to_close = pages[target]
        else:
            q_lower = str(target).lower().strip()
            for page in pages:
                try:
                    if q_lower in page.title().lower() or q_lower in page.url.lower():
                        page_to_close = page
                        break
                except Exception:
                    continue

        if page_to_close:
            closed_title = page_to_close.title()
            page_to_close.close()

            # Update active page
            remaining = self._context.pages
            self._active_page = remaining[-1] if remaining else None

            return {
                "success": True,
                "closed_title": closed_title,
                "remaining_tabs": len(remaining),
                "message": f"Closed tab: \"{closed_title}\". ({len(remaining)} remaining)",
            }
        else:
            return {
                "success": False,
                "error": f"Tab matching '{target}' not found.",
            }

    def read_current_page(self, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspect and summarize the current active webpage or a specified URL.
        Returns parsed structure and formatted Markdown summary.
        """
        target_html = None
        target_url = url or ""

        # If a live tab is open and no specific URL was given, read from the live tab
        if not target_url and self._active_page:
            try:
                target_url = self._active_page.url
                target_html = self._active_page.content()
            except Exception as e:
                logger.warning(f"Could not read from active page: {e}")

        if target_html:
            parsed = self.content_reader.parse_content(target_html, base_url=target_url)
            summary_md = self.content_reader.summarize_page(parsed, url=target_url)
            return {
                "success": True,
                "title": parsed.get("title", ""),
                "url": target_url,
                "summary": summary_md,
                "parsed": parsed,
            }

        # Otherwise fetch via HTTP
        if not target_url:
            return {
                "success": False,
                "error": "No active webpage to read and no URL provided.",
            }

        norm_url = self.registry.normalize_url(target_url)
        fetch_res = self.content_reader.fetch_page(norm_url)
        if not fetch_res["success"]:
            return fetch_res

        parsed = self.content_reader.parse_content(fetch_res["html"], base_url=fetch_res["final_url"])
        summary_md = self.content_reader.summarize_page(parsed, url=fetch_res["final_url"])
        return {
            "success": True,
            "title": parsed.get("title", ""),
            "url": fetch_res["final_url"],
            "summary": summary_md,
            "parsed": parsed,
        }

    def search_web(
        self,
        query: str,
        provider: str = "google",
        open_in_browser: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute internet search, retrieve results, and optionally open search page in browser.
        Distinguishes offline state and stops immediately without retrying or inventing results.
        """
        net_mgr = get_network_manager()
        if not net_mgr.is_internet_available():
            logger.warning("Search aborted: Internet connection is unavailable.")
            return {
                "success": False,
                "error": OFFLINE_SEARCH_ERROR_MESSAGE,
                "query": query,
                "provider": provider,
                "is_offline": True,
            }

        try:
            results = self.search_engine.search_online(query)
            summary_md = self.search_engine.format_results_markdown(query, results, provider=provider)
            search_url = self.search_engine.build_search_url(query, provider)

            if open_in_browser:
                self.open_url(search_url, new_tab=True)

            return {
                "success": True,
                "query": query,
                "provider": provider,
                "search_url": search_url,
                "results": results,
                "summary_md": summary_md,
            }
        except ConnectionError:
            return {
                "success": False,
                "error": OFFLINE_SEARCH_ERROR_MESSAGE,
                "query": query,
                "provider": provider,
                "is_offline": True,
            }
        except Exception as e:
            classified = net_mgr.classify_browser_error(e)
            if not net_mgr.is_internet_available():
                return {
                    "success": False,
                    "error": OFFLINE_SEARCH_ERROR_MESSAGE,
                    "query": query,
                    "provider": provider,
                    "is_offline": True,
                }
            return {
                "success": False,
                "error": f"Search failed: {e}",
                "query": query,
                "provider": provider,
            }

    def close_browser(self) -> None:
        """Safely close active browser context and engine."""
        try:
            if self._context:
                self._context.close()
                self._context = None
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            self._active_page = None
            logger.info("Browser engine closed successfully.")
        except Exception as e:
            logger.warning(f"Error during browser teardown: {e}")


_CONTROLLER_INSTANCE: Optional[BrowserController] = None


def get_browser_controller() -> BrowserController:
    """Singleton getter for BrowserController."""
    global _CONTROLLER_INSTANCE
    if _CONTROLLER_INSTANCE is None:
        _CONTROLLER_INSTANCE = BrowserController()
    return _CONTROLLER_INSTANCE

