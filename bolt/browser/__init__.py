"""
BOLT Browser and Website Intelligence subsystem.
Provides browser discovery, persistent website registry, tab management,
web search, and content analysis.
"""

from bolt.browser.browser_detector import BrowserDetector, get_browser_detector
from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.browser.search_engine import SearchEngine, get_search_engine
from bolt.browser.content_reader import ContentReader, get_content_reader
from bolt.browser.browser_controller import BrowserController, get_browser_controller

__all__ = [
    "BrowserDetector",
    "get_browser_detector",
    "WebsiteRegistry",
    "get_website_registry",
    "SearchEngine",
    "get_search_engine",
    "ContentReader",
    "get_content_reader",
    "BrowserController",
    "get_browser_controller",
]

