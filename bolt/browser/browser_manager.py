"""
Browser Manager for BOLT (Phase 3).
Orchestrates browser detection, launching, session reuse, tab management,
URL navigation, window switching, and verification.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bolt.browser.browser_detection import BrowserDetector, BrowserInfo, get_browser_detector
from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.core.logger import get_logger
from bolt.windows.window_manager import WindowInfo, WindowManager, get_window_manager

logger = get_logger("BrowserManager")


@dataclass
class NavigationResult:
    success: bool
    url: str
    browser_name: str
    message: str
    window_title: str = ""
    reused_session: bool = False
    raw_data: Optional[Dict[str, object]] = None


class BrowserManager:
    """Controls browser processes, launches URLs, reuses sessions, and manages tabs."""

    def __init__(
        self,
        detector: Optional[BrowserDetector] = None,
        registry: Optional[WebsiteRegistry] = None,
        window_mgr: Optional[WindowManager] = None,
    ):
        self.detector = detector or get_browser_detector()
        self.registry = registry or get_website_registry()
        self.window_mgr = window_mgr or get_window_manager()

    def get_installed_browsers(self) -> List[BrowserInfo]:
        """Detect and return all installed browsers."""
        return self.detector.detect_installed_browsers()

    def get_default_browser(self) -> Optional[BrowserInfo]:
        """Get the system default browser."""
        return self.detector.get_preferred_or_default_browser()

    def find_open_browser_windows(self) -> List[WindowInfo]:
        """Find all visible top-level windows belonging to known browsers."""
        browsers = self.get_installed_browsers()
        browser_exes = set()
        for b in browsers:
            browser_exes.add(os.path.basename(b.executable_path).lower())

        windows = self.window_mgr.get_visible_windows()
        browser_windows = []
        for w in windows:
            title_lower = w.title.lower()
            if any(name in title_lower for name in ["chrome", "edge", "brave", "firefox", "opera"]):
                browser_windows.append(w)

        return browser_windows

    def open_url(
        self,
        url: str,
        preferred_browser: str = "",
        new_tab: bool = True,
        verify: bool = True,
    ) -> NavigationResult:
        """
        Open a URL in the user's preferred or default browser.
        Reuses existing running browser sessions to avoid duplicate instances.
        """
        valid_url = self.registry.validate_url(url)
        if not valid_url:
            return NavigationResult(
                success=False,
                url=url,
                browser_name="",
                message=f"Invalid or untrusted URL: '{url}'. Please provide a valid web address.",
            )

        browser = self.detector.get_preferred_or_default_browser(preferred_browser)
        if not browser or not browser.executable_path:
            return NavigationResult(
                success=False,
                url=valid_url,
                browser_name="None",
                message="No supported web browser was detected on this system.",
            )

        was_running = browser.is_running
        logger.info(
            f"Navigating to '{valid_url}' via {browser.name} "
            f"(Already running: {was_running}, exe: {browser.executable_path})"
        )

        try:
            # Build launch command
            # When already running, launching with the URL tells the existing instance to open a new tab!
            args = [browser.executable_path]
            if was_running and new_tab and browser.browser_type in ["chrome", "edge", "brave"]:
                args.extend(["--new-tab", valid_url])
            else:
                args.append(valid_url)

            # Spawn process without blocking
            subprocess.Popen(
                args,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Record in website registry if this was a known website
            parsed = urlparse(valid_url)
            domain = parsed.netloc.lower().replace("www.", "")
            known_site = self.registry.find_website(domain)
            if known_site:
                self.registry.record_access_success(known_site.name)

            window_title = ""
            if verify:
                # Poll briefly to confirm browser window appeared or gained focus
                time.sleep(1.2)
                windows = self.find_open_browser_windows()
                if windows:
                    # Look for window containing page/domain keyword or browser name
                    for w in windows:
                        if domain.split(".")[0] in w.title.lower() or browser.browser_type in w.title.lower():
                            window_title = w.title
                            self.window_mgr.switch_to_window(w.hwnd)
                            break
                    if not window_title and windows:
                        window_title = windows[0].title
                        self.window_mgr.switch_to_window(windows[0].hwnd)

            session_text = "Reused active browser session" if was_running else "Launched new browser instance"
            return NavigationResult(
                success=True,
                url=valid_url,
                browser_name=browser.name,
                message=f"Successfully navigated to `{valid_url}` in **{browser.name}** ({session_text}).",
                window_title=window_title,
                reused_session=was_running,
            )

        except Exception as e:
            logger.error(f"Failed to navigate to {valid_url} with {browser.name}: {e}")
            return NavigationResult(
                success=False,
                url=valid_url,
                browser_name=browser.name,
                message=f"Failed to launch browser: {e}",
            )

    def open_multiple_urls(
        self,
        urls: List[str],
        preferred_browser: str = "",
    ) -> List[NavigationResult]:
        """Open multiple URLs in separate tabs efficiently."""
        results = []
        for i, url in enumerate(urls):
            # First URL opens or focuses browser, subsequent open as new tabs
            res = self.open_url(url, preferred_browser=preferred_browser, new_tab=True, verify=(i == len(urls) - 1))
            results.append(res)
            time.sleep(0.3)
        return results

    def switch_to_tab(self, query: str) -> Optional[WindowInfo]:
        """
        Switch to an open browser tab/window matching a website name or title keyword.
        Example: "chatgpt" -> finds and activates ChatGPT tab/window.
        """
        clean = query.strip().lower()
        windows = self.find_open_browser_windows()

        # 1. Exact or partial title match in browser windows
        for w in windows:
            if clean in w.title.lower():
                self.window_mgr.switch_to_window(w.hwnd)
                logger.info(f"Switched to browser window: '{w.title}'")
                return w

        # 2. Check alias in website registry
        site = self.registry.find_website(clean)
        if site:
            parsed = urlparse(site.url)
            domain_key = parsed.netloc.lower().replace("www.", "").split(".")[0]
            for w in windows:
                if domain_key in w.title.lower() or site.name in w.title.lower():
                    self.window_mgr.switch_to_window(w.hwnd)
                    logger.info(f"Switched to browser window via registry key: '{w.title}'")
                    return w

        return None

    def close_matching_browser(self, query: str) -> bool:
        """Close browser window matching a query or tab title."""
        target_window = self.switch_to_tab(query)
        if target_window:
            return self.window_mgr.close_window(target_window.hwnd)
        return False


_BROWSER_MANAGER: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    global _BROWSER_MANAGER
    if _BROWSER_MANAGER is None:
        _BROWSER_MANAGER = BrowserManager()
    return _BROWSER_MANAGER

