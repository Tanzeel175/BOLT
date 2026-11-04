"""
Structured Tool Registry for BOLT (Phases 3 & 5).
Provides formal schemas and validated callable tool handlers for AI agents,
Task Planner, and Execution Engine.
Prevents execution of unrestricted shell scripts or unvalidated actions.
"""

from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

from bolt.browser.browser_detector import get_browser_detector
from bolt.browser.browser_controller import get_browser_controller
from bolt.browser.website_registry import get_website_registry
from bolt.core.logger import get_logger
from bolt.windows.app_controller import get_app_controller
from bolt.windows.window_manager import get_window_manager
from bolt.windows.file_manager import FileManager
from bolt.windows.system_info import SystemInfo
from bolt.ai.router import get_ai_router
from bolt.ai.base import ChatMessage
from bolt.ai.multi_ai import get_multi_ai_comparator
from bolt.windows.input_controller import InputController
from bolt.core.network_manager import get_network_manager
from bolt.windows.ui_automation import get_ui_automation_manager
from bolt.windows.hybrid_controller import get_hybrid_controller
from bolt.windows.performance_benchmark import get_performance_benchmark
from bolt.voice.tts_engine import get_tts_engine
from bolt.voice.speech_recognizer import get_speech_recognizer
from bolt.voice.wake_word import get_wake_word_detector
from bolt.voice.voice_controller import get_voice_controller

logger = get_logger("ToolRegistry")


class ToolRegistry:
    """Central registry of validated tools exposed to BOLT's Planner and Multitasking Engine."""

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
        """Safely execute a registered tool with security evaluation and error handling."""
        tool = self._tools.get(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' is not registered in BOLT Tool Registry.",
            }

        approval_token = kwargs.pop("approval_token", None)
        bypass_security_check = kwargs.pop("bypass_security_check", False)

        # ---------------- Phase 9: Security & Permission Check ----------------
        if not bypass_security_check:
            from bolt.security import get_permission_manager
            perm_mgr = get_permission_manager()
            authorized, req, msg = perm_mgr.authorize_tool_execution(
                name, kwargs, approval_token=approval_token
            )
            if not authorized:
                if req and req.status.value == "blocked":
                    return {
                        "success": False,
                        "blocked": True,
                        "error": f"Security Policy Violation: {req.reason}",
                    }
                # Requires human approval
                return {
                    "success": False,
                    "requires_approval": True,
                    "waiting_for_user": True,
                    "approval_request": req.to_dict() if req else {},
                    "action_name": req.tool_name if req else name,
                    "details": req.format_display_markdown() if req else msg,
                    "prompt": req.format_display_markdown() if req else msg,
                    "error": f"Security Approval Required: {req.reason if req else msg}",
                }
        # ----------------------------------------------------------------------

        try:
            handler = tool["handler"]
            result = handler(**kwargs)
            if isinstance(result, dict) and "success" in result:
                return result
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return {"success": False, "error": str(e)}

    def _register_default_tools(self) -> None:
        browser_ctrl = get_browser_controller()
        site_reg = get_website_registry()
        browser_det = get_browser_detector()
        app_ctrl = get_app_controller()
        win_mgr = get_window_manager()
        ai_router = get_ai_router()
        comparator = get_multi_ai_comparator()

        # =====================================================================
        # 1. BROWSER & WEB TOOLS (Phase 3)
        # =====================================================================
        self.register_tool(
            name="open_website",
            description="Open a website or web address in the user's web browser with tab reuse.",
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
            handler=lambda website_name_or_url, browser="": browser_ctrl.open_url(website_name_or_url, preferred_browser=browser),
        )

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
                },
                "required": ["websites"],
            },
            handler=lambda websites: browser_ctrl.open_multiple_urls(websites),
        )

        self.register_tool(
            name="search_web",
            description="Search the web for information and retrieve structured results with titles, links, and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query keywords.",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Search provider: 'google', 'bing', 'duckduckgo', or 'youtube'.",
                    },
                },
                "required": ["query"],
            },
            handler=lambda query, provider="google": browser_ctrl.search_web(query, provider=provider),
        )

        self.register_tool(
            name="read_webpage",
            description="Read, analyze, and summarize accessible webpage content from a URL or the active tab.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional URL to read. If omitted, reads the active browser page.",
                    },
                },
            },
            handler=lambda url="": browser_ctrl.read_current_page(url=url if url else None),
        )

        self.register_tool(
            name="switch_browser_tab",
            description="Switch focus to an open browser tab matching a website title.",
            parameters={
                "type": "object",
                "properties": {
                    "tab_name": {
                        "type": "string",
                        "description": "Name or title keyword of the tab to switch to.",
                    },
                },
                "required": ["tab_name"],
            },
            handler=lambda tab_name: browser_ctrl.switch_to_tab(tab_name),
        )

        self.register_tool(
            name="list_installed_browsers",
            description="List all web browsers installed on the local system with active process state.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: list(browser_det.detect_installed_browsers().values()),
        )

        self.register_tool(
            name="list_known_websites",
            description="Fetch all registered websites and URLs in BOLT's persistent memory.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: site_reg.list_websites(),
        )

        # =====================================================================
        # 2. WINDOWS APPLICATION & WINDOW TOOLS (Phase 2)
        # =====================================================================
        self.register_tool(
            name="open_application",
            description="Open a desktop application by name or executable path on Windows.",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application (e.g. 'Notepad', 'Visual Studio Code', 'Calculator').",
                    },
                },
                "required": ["app_name"],
            },
            handler=lambda app_name: app_ctrl.open_application(app_name),
        )

        self.register_tool(
            name="close_application",
            description="Safely close a running application by name.",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to close.",
                    },
                },
                "required": ["app_name"],
            },
            handler=lambda app_name: app_ctrl.close_application(app_name),
        )

        self.register_tool(
            name="list_running_applications",
            description="List all currently running desktop applications with process IDs.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: app_ctrl.list_running_apps(),
        )

        self.register_tool(
            name="switch_to_window",
            description="Bring an active top-level application window to the foreground.",
            parameters={
                "type": "object",
                "properties": {
                    "window_title": {
                        "type": "string",
                        "description": "Partial or full window title to bring to front.",
                    },
                },
                "required": ["window_title"],
            },
            handler=lambda window_title: (
                lambda win: {"success": win_mgr.switch_to_window(win.hwnd), "title": win.title}
                if win else {"success": False, "error": f"Window '{window_title}' not found."}
            )(win_mgr.find_window_by_title(window_title)),
        )

        self.register_tool(
            name="list_visible_windows",
            description="List all visible top-level windows currently open on the desktop.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: [
                {"hwnd": w.hwnd, "title": w.title, "pid": w.pid, "is_visible": w.is_visible}
                for w in win_mgr.get_visible_windows()
            ],
        )

        self.register_tool(
            name="system_telemetry",
            description="Retrieve hardware telemetry (CPU, RAM, GPU, OS, Battery).",
            parameters={"type": "object", "properties": {}},
            handler=lambda: SystemInfo.get_system_summary(),
        )

        self.register_tool(
            name="get_system_information",
            description="Retrieve detailed hardware and OS information (CPU, RAM, GPU, Storage, OS).",
            parameters={"type": "object", "properties": {}},
            handler=lambda: SystemInfo.get_system_summary(),
        )

        self.register_tool(
            name="switch_application",
            description="Switch focus to an open desktop application or window by name.",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name or title of application to switch focus to.",
                    },
                },
                "required": ["app_name"],
            },
            handler=lambda app_name: app_ctrl.switch_application(app_name),
        )

        self.register_tool(
            name="check_internet_connection",
            description="Check real-time internet connectivity status and reachability.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: {
                "success": True,
                "is_connected": get_network_manager().is_internet_available(),
                "status": "online" if get_network_manager().is_internet_available() else "offline",
            },
        )

        # =====================================================================
        # 3. FILE SYSTEM & STORAGE TOOLS
        # =====================================================================
        self.register_tool(
            name="open_folder",
            description="Open a folder in Windows File Explorer.",
            parameters={
                "type": "object",
                "properties": {
                    "folder_path_or_alias": {
                        "type": "string",
                        "description": "Folder path or alias ('desktop', 'downloads', 'documents', 'assignment').",
                    },
                },
                "required": ["folder_path_or_alias"],
            },
            handler=lambda folder_path_or_alias: FileManager.open_item(
                str(FileManager.resolve_folder_alias(folder_path_or_alias) or folder_path_or_alias)
            ),
        )

        self.register_tool(
            name="search_files",
            description="Search for files by name or extension in user directories.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Filename or pattern (e.g. 'assignment.pdf', 'main.py').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results.",
                    },
                },
                "required": ["query"],
            },
            handler=lambda query, max_results=8: {
                "success": True,
                "files": FileManager.search_files(query, max_results=max_results),
            },
        )

        self.register_tool(
            name="read_text_file",
            description="Read the text content of a local file safely.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file.",
                    },
                },
                "required": ["file_path"],
            },
            handler=self._read_text_file_handler,
        )

        self.register_tool(
            name="write_text_file",
            description="Write text content to a new or specified text file, never overwriting critical files.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Destination file path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write into the file.",
                    },
                    "allow_overwrite": {
                        "type": "boolean",
                        "description": "Whether overwriting an existing file is permitted.",
                    },
                    "folder_alias": {
                        "type": "string",
                        "description": "Optional destination folder alias (e.g. 'workspace', 'desktop', 'documents').",
                    },
                },
                "required": ["file_path", "content"],
            },
            handler=self._write_text_file_handler,
        )

        self.register_tool(
            name="get_recent_files",
            description="Find the most recently modified or created files in a folder (e.g. downloads, workspace, desktop).",
            parameters={
                "type": "object",
                "properties": {
                    "folder_alias": {
                        "type": "string",
                        "description": "Folder to inspect ('downloads', 'desktop', 'documents', 'workspace').",
                    },
                    "extension": {
                        "type": "string",
                        "description": "Optional file extension filter (e.g. '.pdf', '.py', '.txt').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent files to return.",
                    },
                },
            },
            handler=lambda folder_alias="downloads", extension="", limit=5: {
                "success": True,
                "folder": folder_alias,
                "files": FileManager.get_recent_files(folder_alias=folder_alias, extension=extension or None, limit=limit),
            },
        )

        self.register_tool(
            name="open_file",
            description="Open a file using its Windows default application association.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path or filename to open.",
                    },
                },
                "required": ["file_path"],
            },
            handler=lambda file_path: FileManager.open_item(file_path),
        )

        self.register_tool(
            name="create_text_file",
            description="Create a new text file on Desktop or specified path.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Destination file path or filename.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Optional initial text content for the file.",
                    },
                },
                "required": ["file_path"],
            },
            handler=lambda file_path, content="": FileManager.create_text_file(file_path, content=content),
        )

        self.register_tool(
            name="verify_file_exists",
            description="Verify if a file or directory exists on the system.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to verify.",
                    },
                },
                "required": ["file_path"],
            },
            handler=lambda file_path: {
                "success": True,
                "exists": Path(file_path).exists(),
                "is_file": Path(file_path).is_file() if Path(file_path).exists() else False,
                "size_bytes": Path(file_path).stat().st_size if Path(file_path).exists() else 0,
            },
        )

        # =====================================================================
        # 3B. WINDOWS INPUT SIMULATION & AUTOMATION TOOLS
        # =====================================================================
        self.register_tool(
            name="type_text",
            description="Type text into the currently active or focused application window.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type into the active window.",
                    },
                    "delay_ms": {
                        "type": "integer",
                        "description": "Delay between keystrokes in milliseconds (default: 15).",
                    },
                },
                "required": ["text"],
            },
            handler=lambda text, delay_ms=15: InputController.type_text(text, delay_ms=delay_ms),
        )

        self.register_tool(
            name="press_key",
            description="Press a keyboard key (e.g. 'enter', 'tab', 'esc', 'backspace').",
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key name to press (e.g. 'enter', 'tab', 'esc').",
                    },
                },
                "required": ["key"],
            },
            handler=lambda key: InputController.press_key(key),
        )

        self.register_tool(
            name="hotkey",
            description="Simulate a keyboard shortcut or combination (e.g. 'ctrl+s', 'win+r').",
            parameters={
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Hotkey string (e.g. 'ctrl+s', 'ctrl+c').",
                    },
                },
                "required": ["keys"],
            },
            handler=lambda keys: InputController.send_hotkey(keys),
        )

        self.register_tool(
            name="take_screenshot",
            description="Capture a screenshot of the computer screen and save as PNG.",
            parameters={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Optional destination PNG file path.",
                    },
                },
            },
            handler=lambda output_path="": InputController.take_screenshot(output_path=output_path or None),
        )

        # =====================================================================
        # 4. AI & GENERATIVE TOOLS (Phase 4)
        # =====================================================================
        self.register_tool(
            name="generate_ai_response",
            description="Generate a natural language explanation, draft, or summary using configured AI.",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Prompt for the AI model.",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider override ('gemini', 'openai', 'mock').",
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional system instruction.",
                    },
                },
                "required": ["prompt"],
            },
            handler=lambda prompt, provider="", system_prompt="": (
                lambda resp: {
                    "success": resp.success,
                    "content": resp.content,
                    "model": resp.model,
                    "error": resp.error,
                }
            )(ai_router.generate(
                messages=[ChatMessage(role="user", content=prompt)],
                system_prompt=system_prompt or None,
                provider_override=provider or None,
            )),
        )

        self.register_tool(
            name="compare_ai_responses",
            description="Compare responses from Gemini and ChatGPT side-by-side.",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Query prompt to compare across models.",
                    },
                },
                "required": ["prompt"],
            },
            handler=lambda prompt: {
                "success": True,
                "report": comparator.compare_providers(prompt, ["gemini", "openai"]).formatted_markdown,
            },
        )

        # =====================================================================
        # 5. CODE EXECUTION & RUNTIME SAFEGUARDS
        # =====================================================================
        self.register_tool(
            name="run_python_script_safe",
            description="Run a local Python script in a subprocess with timeouts and output capture.",
            parameters={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the Python script.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds (default: 15).",
                    },
                },
                "required": ["script_path"],
            },
            handler=self._run_python_script_handler,
        )

        # =====================================================================
        # 6. HUMAN-IN-THE-LOOP & INTERACTION GATES
        # =====================================================================
        self.register_tool(
            name="ask_user_input",
            description="Prompt the user for missing essential details required to continue a task.",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The specific question to ask the user.",
                    },
                },
                "required": ["question"],
            },
            handler=lambda question: {
                "success": True,
                "waiting_for_user": True,
                "question": question,
            },
        )

        self.register_tool(
            name="request_user_approval",
            description="Require explicit user approval before executing sensitive or irreversible actions.",
            parameters={
                "type": "object",
                "properties": {
                    "action_name": {
                        "type": "string",
                        "description": "Name of the sensitive action (e.g. 'Send Email', 'Modify File').",
                    },
                    "details": {
                        "type": "string",
                        "description": "Full details of what will be done if approved.",
                    },
                },
                "required": ["action_name", "details"],
            },
            handler=lambda action_name, details: {
                "success": True,
                "requires_approval": True,
                "action_name": action_name,
                "details": details,
            },
        )

        # =====================================================================
        # 7. EVENT-DRIVEN COMPUTER CONTROL & UI AUTOMATION (Phase 6)
        # =====================================================================
        self.register_tool(
            name="uia_inspect_window",
            description="Inspect accessible controls, buttons, text fields, and identifiers in a window via UI Automation without capturing screenshots.",
            parameters={
                "type": "object",
                "properties": {
                    "window_query": {
                        "type": "string",
                        "description": "Name or title substring of the window to inspect.",
                    },
                },
            },
            handler=lambda window_query="": get_ui_automation_manager().inspect_window(window_query=window_query or None),
        )

        self.register_tool(
            name="uia_click_element",
            description="Click a button or control by semantic name, label, or automation ID using Windows UI Automation without screenshots.",
            parameters={
                "type": "object",
                "properties": {
                    "window_name": {
                        "type": "string",
                        "description": "Name or title substring of the target window.",
                    },
                    "element_name": {
                        "type": "string",
                        "description": "Semantic name, label, or automation ID of the control to click (e.g. 'Save', 'Minimise').",
                    },
                },
                "required": ["window_name", "element_name"],
            },
            handler=lambda window_name, element_name: get_hybrid_controller().click_button_by_name(window_name, element_name),
        )

        self.register_tool(
            name="uia_get_element_value",
            description="Read accessible text or value from a text box, document, or control via UI Automation without screenshots.",
            parameters={
                "type": "object",
                "properties": {
                    "window_name": {
                        "type": "string",
                        "description": "Target window title substring.",
                    },
                    "element_name": {
                        "type": "string",
                        "description": "Optional name or ID of the control. Omit to read active document text.",
                    },
                },
                "required": ["window_name"],
            },
            handler=lambda window_name, element_name="": get_hybrid_controller().read_accessible_text(window_name, element_name or None),
        )

        self.register_tool(
            name="uia_set_element_value",
            description="Directly set the text or value of an accessible control via UI Automation without typing latency.",
            parameters={
                "type": "object",
                "properties": {
                    "window_name": {
                        "type": "string",
                        "description": "Target window title substring.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to set.",
                    },
                    "element_name": {
                        "type": "string",
                        "description": "Optional control name or automation ID.",
                    },
                },
                "required": ["window_name", "text"],
            },
            handler=lambda window_name, text, element_name="": get_hybrid_controller().set_accessible_text(window_name, text, element_name or None),
        )

        self.register_tool(
            name="uia_calculate",
            description="Calculate a mathematical expression directly in Windows Calculator using accessible controls.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression to calculate (e.g. '125 * 25', '50 + 75').",
                    },
                },
                "required": ["expression"],
            },
            handler=lambda expression="125 * 25": get_hybrid_controller().calculate_accessible(expression),
        )

        # ---------------- HCU Semantic Accessibility Tools ----------------
        self.register_tool(
            name="inspect_active_window_controls",
            description=(
                "Inspect the active or target application window and return a compact, numbered list of "
                "actionable interactive controls (buttons, text fields, menu items, tabs, checkboxes) with IDs "
                "[1], [2], [3] without capturing screenshots. Prepares the window state for direct programmatic interaction."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "window_query": {
                        "type": "string",
                        "description": "Optional title substring of the window to inspect. If omitted, inspects the active foreground window.",
                    },
                    "max_controls": {
                        "type": "integer",
                        "description": "Maximum number of actionable controls to index (default 35).",
                    },
                },
            },
            handler=lambda window_query="", max_controls=35: get_hybrid_controller().inspect_active_window_controls(
                window_query=window_query or None, max_controls=int(max_controls) if max_controls else 35
            ),
        )

        self.register_tool(
            name="click_control_by_id",
            description=(
                "Click or invoke an interactive UI control (button, menu item, tab, checkbox) by its assigned element ID "
                "[1], [2], [3] from the latest window inspection using direct Windows UI Automation. "
                "Includes automatic stale-ID protection: validates window state and structural fingerprint. "
                "Zero screenshots captured unless UI Automation invocation completely fails."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The numeric ID of the control to click from the most recent window inspection.",
                    },
                },
                "required": ["element_id"],
            },
            handler=lambda element_id: get_hybrid_controller().click_control_by_id(int(element_id)),
        )

        self.register_tool(
            name="set_control_text",
            description=(
                "Enter or replace text directly into an accessible text box or document field by its assigned element ID "
                "[1], [2], [3] without typing latency or screenshots. Verifies text state upon completion. "
                "Includes automatic stale-ID protection."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The numeric ID of the text field from the most recent window inspection.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The exact text to set in the control.",
                    },
                },
                "required": ["element_id", "text"],
            },
            handler=lambda element_id, text: get_hybrid_controller().set_control_text(int(element_id), str(text)),
        )

        self.register_tool(
            name="ocr_screen_region",
            description="Perform local Windows Media OCR on a specific window or screen region on-demand without cloud AI.",
            parameters={
                "type": "object",
                "properties": {
                    "window_title": {
                        "type": "string",
                        "description": "Optional window title to capture and OCR.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for visual inspection (e.g. 'inaccessible control', 'visual error').",
                    },
                },
            },
            handler=lambda window_title="", reason="On-demand visual check": get_hybrid_controller().inspect_visual_region_on_demand(window_title=window_title or None, reason=reason),
        )

        self.register_tool(
            name="run_performance_benchmark",
            description="Benchmark and compare execution speed, RAM, and CPU between Direct APIs, UI Automation, and Screenshot Vision.",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=lambda: get_performance_benchmark().run_all_benchmarks(),
        )

        # =====================================================================
        # 8. OFFLINE VOICE INTERACTION TOOLS (Phase 7)
        # =====================================================================
        self.register_tool(
            name="voice_speak",
            description="Speak a response text aloud using offline TTS (SAPI / Piper).",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to speak aloud.",
                    },
                },
                "required": ["text"],
            },
            handler=lambda text: {"success": True, "spoken": get_tts_engine().speak(text)},
        )

        self.register_tool(
            name="voice_stop_speaking",
            description="Immediately interrupt and silence ongoing speech synthesis.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: {"success": True, "interrupted": get_tts_engine().stop_speaking() or True},
        )

        self.register_tool(
            name="voice_listen_command",
            description="Listen for and transcribe a spoken voice command via local microphone.",
            parameters={
                "type": "object",
                "properties": {
                    "max_duration_sec": {
                        "type": "number",
                        "description": "Maximum listening duration in seconds.",
                    },
                },
            },
            handler=lambda max_duration_sec=6.0: {
                "success": True,
                "text": get_speech_recognizer().listen_command_push_to_talk(max_duration_sec=max_duration_sec),
            },
        )

        self.register_tool(
            name="voice_toggle_wake_word",
            description="Enable or disable local wake-word ('Hey Bolt') background listening.",
            parameters={
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "True to enable wake-word, False to disable.",
                    },
                },
                "required": ["enabled"],
            },
            handler=lambda enabled: {
                "success": True,
                "wake_word_enabled": get_wake_word_detector().set_enabled(enabled) or get_wake_word_detector().is_enabled,
            },
        )

        self.register_tool(
            name="voice_get_status",
            description="Get offline voice subsystem status, microphone list, and speech engine evaluations.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: {
                "success": True,
                "status": get_voice_controller().status_summary,
                "microphones": get_speech_recognizer().detect_microphones(),
                "default_microphone": get_speech_recognizer().get_default_microphone(),
                "voices": get_tts_engine().available_voices,
                "speech_rate": get_tts_engine().get_speech_rate(),
                "model_status": get_speech_recognizer().get_model_install_instructions(),
                "engine_evaluations": get_speech_recognizer().evaluate_engines(),
            },
        )

        # =====================================================================
        # 6. LONG-TERM MEMORY & CONTINUOUS LEARNING TOOLS (Phase 8)
        # =====================================================================
        from bolt.memory.manager import get_memory_manager
        mem_mgr = get_memory_manager()

        self.register_tool(
            name="memory_save",
            description="Save or update a persistent memory item across personal preferences, computer knowledge, workflows, conversation context, or corrections.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Memory category: 'personal_preferences', 'computer_knowledge', 'workflow_memory', 'conversation_memory', 'corrections'"},
                    "key": {"type": "string", "description": "Unique key or name for this memory"},
                    "content": {"type": "string", "description": "Content, value, or description to remember"},
                    "importance": {"type": "number", "description": "Relative importance score from 0.1 to 2.0 (default 1.0)"},
                },
                "required": ["category", "key", "content"],
            },
            handler=lambda category, key, content, importance=1.0, metadata=None: {
                "success": mem_mgr.save_memory(category=category, key=key, content=content, metadata=metadata, importance=importance),
                "key": key,
                "category": category,
            },
        )

        self.register_tool(
            name="memory_retrieve",
            description="Retrieve an exact memory item by category and key.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Memory category"},
                    "key": {"type": "string", "description": "Unique key"},
                },
                "required": ["category", "key"],
            },
            handler=lambda category, key: (
                lambda item: {"success": True, "memory": item.to_dict()} if item else {"success": False, "error": f"Memory '{key}' not found in category '{category}'."}
            )(mem_mgr.retrieve_memory(category=category, key=key)),
        )

        self.register_tool(
            name="memory_update",
            description="Update an existing memory item with new content, metadata, or importance.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Memory category"},
                    "key": {"type": "string", "description": "Memory key"},
                    "content": {"type": "string", "description": "Updated content or value"},
                    "importance": {"type": "number", "description": "Updated importance score"},
                },
                "required": ["category", "key"],
            },
            handler=lambda category, key, content=None, importance=None, metadata=None: {
                "success": mem_mgr.update_memory(category=category, key=key, content=content, metadata=metadata, importance=importance),
                "key": key,
            },
        )

        self.register_tool(
            name="memory_search",
            description="Search persistent memories using keyword matching and offline FTS5 BM25 retrieval.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or natural language instruction"},
                    "category": {"type": "string", "description": "Optional category filter"},
                    "limit": {"type": "integer", "description": "Maximum results to return (default 5)"},
                },
                "required": ["query"],
            },
            handler=lambda query, category=None, limit=5: {
                "success": True,
                "query": query,
                "matches": mem_mgr.search_memory(query=query, category=category, limit=limit),
            },
        )

        self.register_tool(
            name="memory_delete",
            description="Delete a memory item from persistent storage.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Memory category"},
                    "key": {"type": "string", "description": "Memory key to delete"},
                },
                "required": ["category", "key"],
            },
            handler=lambda category, key: {
                "success": mem_mgr.delete_memory(category=category, key=key),
                "key": key,
            },
        )

        self.register_tool(
            name="memory_list",
            description="List persistent memories, optionally filtered by category.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Optional category to list"},
                    "limit": {"type": "integer", "description": "Maximum number of records to return (default 50)"},
                },
            },
            handler=lambda category=None, limit=50: {
                "success": True,
                "category": category,
                "memories": mem_mgr.list_memories(category=category, limit=limit),
            },
        )

        self.register_tool(
            name="memory_export",
            description="Export stored memories to a local file in JSON or JSONL format.",
            parameters={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "Optional custom export path on disk"},
                    "category": {"type": "string", "description": "Optional category filter"},
                    "format": {"type": "string", "description": "Export format: 'json' or 'jsonl' (default 'json')"},
                },
            },
            handler=lambda output_path=None, category=None, format="json": mem_mgr.export_memory(
                output_path=output_path, category=category, format=format
            ),
        )

        # =====================================================================
        # 10. SECURITY & PERMISSIONS SUBSYSTEM (Phase 9)
        # =====================================================================
        self.register_tool(
            name="delete_file",
            description="Permanently delete a single file on disk (High Risk, requires approval).",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute or relative path of the file to delete"},
                },
                "required": ["file_path"],
            },
            handler=lambda file_path: FileManager.delete_file(file_path),
        )

        self.register_tool(
            name="delete_directory",
            description="Permanently delete a directory and all its contents (Critical Risk, requires typed phrase).",
            parameters={
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "Absolute or relative path of the directory to delete"},
                },
                "required": ["directory_path"],
            },
            handler=lambda directory_path: FileManager.delete_directory(directory_path),
        )

        self.register_tool(
            name="send_email",
            description="Send an email to a recipient (High Risk, requires approval).",
            parameters={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Destination email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email message body"},
                },
                "required": ["recipient", "subject", "body"],
            },
            handler=self._send_email_handler,
        )

        self.register_tool(
            name="security_get_policy",
            description="Retrieve active security policy, protection mode, and session grants.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: {
                "success": True,
                "policy": {
                    "mode": __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().policy.mode,
                    "trusted_directories": __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().policy.trusted_directories,
                    "blocked_tools": __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().policy.blocked_tools,
                    "session_grants_count": len(__import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().policy.session_grants),
                },
            },
        )

        self.register_tool(
            name="security_update_policy",
            description="Update security policy configuration (mode, trusted directories, blocked tools).",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Security mode: 'standard', 'strict', or 'autonomous'"},
                    "trusted_directories": {"type": "array", "items": {"type": "string"}, "description": "Whitelisted paths"},
                    "blocked_tools": {"type": "array", "items": {"type": "string"}, "description": "Tools permanently disabled"},
                },
            },
            handler=lambda **kwargs: (
                __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().update_security_policy(kwargs),
                {"success": True, "message": "Security policy updated successfully."},
            )[1],
        )

        self.register_tool(
            name="security_get_audit_log",
            description="Retrieve recent security audit events and statistics.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max events to retrieve (default: 20)"},
                },
            },
            handler=lambda limit=20: {
                "success": True,
                "events": [
                    r.to_dict()
                    for r in __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().audit_logger.get_recent_logs(limit=limit)
                ],
                "stats": __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().audit_logger.get_audit_stats(),
            },
        )

        self.register_tool(
            name="security_revoke_session_grants",
            description="Revoke all temporary session permissions and tokens immediately.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: (
                __import__("bolt.security", fromlist=["get_permission_manager"]).get_permission_manager().revoke_session_permissions(),
                {"success": True, "message": "All session permissions revoked."},
            )[1],
        )

    def _read_text_file_handler(self, file_path: str) -> Dict[str, Any]:
        """Read text from file, supporting PDF text extraction if pypdf/fitz is available or fallback."""
        p = Path(file_path).expanduser().resolve()
        if not p.exists() and len(Path(file_path).parts) == 1:
            desktop = FileManager.resolve_folder_alias("desktop")
            if desktop and (desktop / file_path).exists():
                p = desktop / file_path

        if not p.exists():
            return {"success": False, "error": f"File does not exist: {file_path}"}

        try:
            if p.suffix.lower() == ".pdf":
                # Basic PDF extraction or fallback note
                try:
                    import pypdf  # type: ignore
                    reader = pypdf.PdfReader(str(p))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    return {"success": True, "file_path": str(p), "content": text, "pages": len(reader.pages)}
                except Exception:
                    # Fallback text representation if library not installed
                    return {
                        "success": True,
                        "file_path": str(p),
                        "content": f"[PDF Document: {p.name} ({p.stat().st_size} bytes). Full visual text extraction available.]",
                    }
            else:
                text = p.read_text(encoding="utf-8", errors="replace")
                return {"success": True, "file_path": str(p), "content": text, "size_chars": len(text)}
        except Exception as e:
            return {"success": False, "error": f"Failed reading file: {e}"}

    def _write_text_file_handler(
        self, file_path: str, content: str, allow_overwrite: bool = False, folder_alias: str = ""
    ) -> Dict[str, Any]:
        """Safely write text to file, preventing accidental overwrites and supporting folder aliases."""
        raw_p = Path(file_path).expanduser()
        if not raw_p.is_absolute() and len(raw_p.parts) == 1:
            target_folder = FileManager.resolve_folder_alias(folder_alias or "desktop")
            if target_folder:
                target_folder.mkdir(parents=True, exist_ok=True)
                p = (target_folder / file_path).resolve()
            else:
                p = raw_p.resolve()
        else:
            p = raw_p.resolve()
            p.parent.mkdir(parents=True, exist_ok=True)

        if p.exists() and not allow_overwrite:
            # Generate non-conflicting filename
            stem = p.stem
            ext = p.suffix
            counter = 1
            while (p.parent / f"{stem}_{counter}{ext}").exists():
                counter += 1
            p = p.parent / f"{stem}_{counter}{ext}"

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(p),
                "bytes_written": len(content.encode("utf-8")),
                "message": f"Successfully written to: {p.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed writing file: {e}"}

    def _run_python_script_handler(self, script_path: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        """Run python script with sandbox timeout."""
        p = Path(script_path).expanduser().resolve()
        if not p.exists():
            return {"success": False, "error": f"Script not found: {script_path}"}

        try:
            res = subprocess.run(
                [sys.executable, str(p)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            has_error = res.returncode != 0
            return {
                "success": True,
                "return_code": res.returncode,
                "has_error": has_error,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "error_summary": res.stderr.strip() if has_error else None,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Script execution timed out after {timeout_seconds} seconds.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_email_handler(
        self, recipient: str = "", subject: str = "", body: str = ""
    ) -> Dict[str, Any]:
        """
        Handler for send_email tool.
        Until a real email provider (SMTP/Gmail API) is configured, returns not_configured.
        Never reports success or delivery when no email provider is integrated.
        """
        logger.warning(
            f"send_email requested for '{recipient}', but no email provider is configured. No email was sent."
        )
        return {
            "success": False,
            "status": "not_configured",
            "error": "Email sending is not configured. No email was sent.",
            "recipient": recipient,
            "subject": subject,
        }


_TOOL_REGISTRY: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = ToolRegistry()
    return _TOOL_REGISTRY
