"""
Structured Tool Registry for BOLT (Phase 3).
Provides formal schemas and validated callable tool handlers for AI agents and function calling.
Prevents execution of unrestricted browser scripts or terminal commands.
"""

from typing import Any, Callable, Dict, List, Optional

from bolt.browser.browser_detection import get_browser_detector
from bolt.browser.navigator import get_browser_navigator
from bolt.browser.website_registry import get_website_registry
from bolt.core.logger import get_logger

logger = get_logger("ToolRegistry")


class ToolRegistry:
    """Central registry of validated tools exposed to BOLT's AI Engine."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a validated tool with JSON schema."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
        }
        logger.debug(f"Registered tool: {name}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return tool definitions formatted for LLM Function Calling (OpenAI / Gemini compatible)."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in self._tools.values()
        ]

    def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """Safely execute a registered tool with error handling."""
        tool = self._tools.get(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' is not registered in BOLT Tool Registry.",
            }

        try:
            handler = tool["handler"]
            result = handler(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return {"success": False, "error": str(e)}

    def _register_default_tools(self) -> None:
        navigator = get_browser_navigator()
        registry = get_website_registry()
        detector = get_browser_detector()

        # 1. open_website
        self.register_tool(
            name="open_website",
            description="Open a website or web address in the user's web browser.",
            parameters={
                "type": "object",
                "properties": {
                    "website_name_or_url": {
                        "type": "string",
                        "description": "Name of the website (e.g. 'chatgpt', 'gmail') or valid URL (e.g. 'https://example.com').",
                    },
                    "browser": {
                        "type": "string",
                        "description": "Optional preferred browser name ('chrome', 'edge', 'brave', 'firefox').",
                    },
                },
                "required": ["website_name_or_url"],
            },
            handler=lambda website_name_or_url, browser="": navigator.navigate_single(website_name_or_url, preferred_browser=browser).__dict__,
        )

        # 2. open_multiple_tabs
        self.register_tool(
            name="open_multiple_tabs",
            description="Open multiple websites in separate tabs in the web browser.",
            parameters={
                "type": "object",
                "properties": {
                    "websites": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of website names or URLs to open.",
                    },
                    "browser": {
                        "type": "string",
                        "description": "Optional preferred browser name.",
                    },
                },
                "required": ["websites"],
            },
            handler=lambda websites, browser="": navigator.navigate_multi_tabs(websites, preferred_browser=browser).__dict__,
        )

        # 3. search_web
        self.register_tool(
            name="search_web",
            description="Search the web for information and retrieve structured results with titles and summaries.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query keywords.",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Search provider: 'bing', 'google', or 'youtube'.",
                    },
                },
                "required": ["query"],
            },
            handler=lambda query, provider="bing": navigator.execute_search(query, provider=provider).__dict__,
        )

        # 4. read_webpage
        self.register_tool(
            name="read_webpage",
            description="Read, analyze, and summarize accessible webpage content from a URL or current page.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional URL to read. If omitted, reads the active browser page.",
                    },
                },
            },
            handler=lambda url="": navigator.read_and_summarize_page(url).__dict__,
        )

        # 5. switch_browser_tab
        self.register_tool(
            name="switch_browser_tab",
            description="Switch focus to an open browser tab or window matching a website title.",
            parameters={
                "type": "object",
                "properties": {
                    "tab_name": {
                        "type": "string",
                        "description": "Name or title keyword of the tab/window to switch to.",
                    },
                },
                "required": ["tab_name"],
            },
            handler=lambda tab_name: navigator.switch_to_tab(tab_name).__dict__,
        )

        # 6. list_installed_browsers
        self.register_tool(
            name="list_installed_browsers",
            description="List all web browsers installed on the local system with active process state.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: [b.to_dict() for b in detector.detect_installed_browsers()],
        )

        # 7. list_known_websites
        self.register_tool(
            name="list_known_websites",
            description="Fetch all registered websites and URLs in BOLT's persistent memory.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: [w.to_dict() for w in registry.get_all_registered_websites()],
        )


_TOOL_REGISTRY: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = ToolRegistry()
    return _TOOL_REGISTRY

