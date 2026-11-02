"""
Natural Language Windows Intent Dispatcher for BOLT.
Translates user instructions into Windows operations (Application Control, Window Management,
File Operations, and System Telemetry).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bolt.core.logger import get_logger
from bolt.windows.app_controller import AppController, get_app_controller
from bolt.windows.file_manager import FileManager, get_file_manager
from bolt.windows.system_info import SystemInfo
from bolt.windows.window_manager import WindowManager, get_window_manager

logger = get_logger("IntentDispatcher")


@dataclass
class IntentResult:
    is_windows_action: bool
    action_type: str = ""
    success: bool = True
    title: str = ""
    content: str = ""
    raw_data: Optional[Dict[str, Any]] = None


class WindowsIntentDispatcher:
    """Classifies natural language instructions and executes corresponding Windows and Browser actions."""

    def __init__(
        self,
        app_controller: Optional[AppController] = None,
        window_mgr: Optional[WindowManager] = None,
        file_mgr: Optional[FileManager] = None,
        navigator: Optional[Any] = None,
        website_registry: Optional[Any] = None,
        browser_detector: Optional[Any] = None,
    ):
        self.app_controller = app_controller or get_app_controller()
        self.window_mgr = window_mgr or get_window_manager()
        self.file_mgr = file_mgr or get_file_manager()

        if navigator is None:
            from bolt.browser.navigator import get_browser_navigator
            self.navigator = get_browser_navigator()
        else:
            self.navigator = navigator

        if website_registry is None:
            from bolt.browser.website_registry import get_website_registry
            self.website_registry = get_website_registry()
        else:
            self.website_registry = website_registry

        if browser_detector is None:
            from bolt.browser.browser_detection import get_browser_detector
            self.browser_detector = get_browser_detector()
        else:
            self.browser_detector = browser_detector

    def dispatch(self, text: str) -> IntentResult:
        """Analyze text and execute matching Windows operation if detected."""
        clean = text.strip()
        lower = clean.lower()

        # Remove polite prefix or assistant name if present (e.g., "BOLT, open notepad" -> "open notepad")
        lower_stripped = re.sub(r"^(bolt|hey bolt|please|can you|could you)\s*[,:]?\s*", "", lower).strip()

        # ---------------- 1. System Telemetry & Specs ----------------
        system_keywords = [
            "system info", "system spec", "hardware info", "computer spec",
            "pc spec", "laptop spec", "system diagnostic", "battery status",
            "battery level", "how much ram", "cpu usage", "ram usage",
            "device specification", "my specs"
        ]
        if any(k in lower_stripped for k in system_keywords) or lower_stripped in ["specs", "battery", "system"]:
            summary_md = SystemInfo.format_markdown_summary()
            return IntentResult(
                is_windows_action=True,
                action_type="system_info",
                success=True,
                title="System Diagnostics",
                content=summary_md,
            )

        # ---------------- 2. List Running Applications ----------------
        is_running_query = (
            any(k in lower_stripped for k in [
                "list running", "show running", "running app", "running process",
                "running program", "running task", "list apps", "active apps",
                "what's running", "whats running"
            ])
            or ("running" in lower_stripped and any(w in lower_stripped for w in ["app", "process", "program", "task", "what", "which"]))
        )
        if is_running_query:
            apps = self.app_controller.list_running_applications()
            if not apps:
                content = "No major user-facing applications detected running."
            else:
                rows = []
                for a in apps[:15]:
                    title_part = f" — *\"{a['window_title']}\"*" if a["window_title"] else ""
                    rows.append(f"- **{a['name']}** (PID: `{a['pid']}`, RAM: {a['memory_mb']} MB){title_part}")
                content = (
                    f"### 📋 Active Running Applications ({len(apps)} detected)\n\n"
                    + "\n".join(rows)
                )

            return IntentResult(
                is_windows_action=True,
                action_type="list_running",
                success=True,
                title="Running Applications",
                content=content,
            )

        # ---------------- 3. List Visible Windows ----------------
        if any(k in lower_stripped for k in [
            "list windows", "show windows", "what windows are open", "open windows"
        ]):
            windows = self.window_mgr.get_visible_windows()
            if not windows:
                content = "No active visible top-level windows detected."
            else:
                rows = [
                    f"- **[HWND {w.hwnd}]** {w.title} *(PID: {w.pid})*"
                    for w in windows[:15]
                ]
                content = (
                    f"### 🪟 Visible Application Windows ({len(windows)} active)\n\n"
                    + "\n".join(rows)
                )

            return IntentResult(
                is_windows_action=True,
                action_type="list_windows",
                success=True,
                title="Visible Windows",
                content=content,
            )

        # ---------------- 4. Open Folder / Directory ----------------
        folder_match = re.match(
            r"^(open|show|explore)\s+(my\s+)?(folder\s+)?([\w\s\\/:\-]+?)(?:\s+folder)?$",
            lower_stripped,
        )
        if folder_match:
            candidate = folder_match.group(4).strip()
            # If candidate matches a known folder alias or path
            resolved_folder = FileManager.resolve_folder_alias(candidate)
            if resolved_folder:
                res = FileManager.open_item(str(resolved_folder))
                if res["success"]:
                    return IntentResult(
                        is_windows_action=True,
                        action_type="open_folder",
                        success=True,
                        title=f"Opened {candidate.title()} Folder",
                        content=f"📁 **Opened Folder:** `{resolved_folder}`",
                    )

        # ---------------- 5. Search / Find Files ----------------
        search_match = re.match(
            r"^(find|search\s+for|search|locate)\s+(?:file\s+)?([^\n]+)$",
            lower_stripped,
        )
        if search_match:
            query = search_match.group(2).strip()
            # Distinguish file searches from general web searches
            has_file_kw = any(w in lower_stripped.split() for w in ["file", "files", "document", "documents"])
            has_file_ext = bool(re.search(r"\.(pdf|txt|docx?|xlsx?|csv|json|png|jpg|exe)\b", query))
            is_web_search = any(w in query for w in ["latest", "ai", "libraries", "tools", "tutorial", "online", "web", "website", "news"])

            if (has_file_kw or has_file_ext) and not is_web_search:
                clean_query = re.sub(r"\b(files?|documents?)\b", "", query).strip()
                files = FileManager.search_files(clean_query, max_results=8)
                if not files:
                    content = f"🔍 No files found matching `*{clean_query}*` in common directories."
                else:
                    rows = [
                        f"- 📄 **{f['name']}** ({f['size_kb']} KB)\n  `{f['path']}`"
                        for f in files
                    ]
                    content = (
                        f"### 🔍 File Search Results for \"{clean_query}\"\n\n"
                        + "\n".join(rows)
                    )

                return IntentResult(
                    is_windows_action=True,
                    action_type="search_files",
                    success=True,
                    title=f"Search: {clean_query}",
                    content=content,
                )

        # ---------------- 6. Switch to Application / Window / Browser Tab / AI Provider ----------------
        switch_match = re.match(
            r"^(switch\s+to|focus|bring\s+to\s+front|activate)\s+([^\n]+)$",
            lower_stripped,
        )
        if switch_match:
            target = switch_match.group(2).strip().rstrip(".")

            # Check if target is an AI provider switch
            norm_target = target.lower()
            if norm_target in ("gemini", "chatgpt", "openai", "mock", "local", "offline") or any(
                norm_target.startswith(p) for p in ["provider to ", "default provider to ", "ai to "]
            ):
                from bolt.ai.provider_manager import get_provider_manager
                clean_p = re.sub(r"^(?:default\s+)?(?:provider|ai)\s+to\s+", "", norm_target).strip()
                pm = get_provider_manager()
                ok, msg = pm.switch_default_provider(clean_p)
                return IntentResult(
                    is_windows_action=True,
                    action_type="switch_ai_provider",
                    success=ok,
                    title="AI Provider Switched" if ok else "Provider Switch Failed",
                    content=msg,
                    raw_data={"provider": clean_p},
                )

            if target.endswith("tab") or " tab" in target:
                clean_tab = re.sub(r"^(the\s+)?", "", target)
                clean_tab = re.sub(r"\s+tab$", "", clean_tab).strip()
                res = self.navigator.switch_to_tab(clean_tab)
                return IntentResult(
                    is_windows_action=True,
                    action_type="switch_tab",
                    success=res.success,
                    title=res.title,
                    content=res.content,
                    raw_data=res.raw_data,
                )

            win = self.window_mgr.find_window_by_title(target)
            if win:
                ok = self.window_mgr.switch_to_window(win.hwnd)
                return IntentResult(
                    is_windows_action=True,
                    action_type="switch_window",
                    success=ok,
                    title=f"Switch to {win.title}",
                    content=f"🪟 Switched to window: **{win.title}**",
                )
            else:
                return IntentResult(
                    is_windows_action=True,
                    action_type="switch_window",
                    success=False,
                    title="Window Not Found",
                    content=f"Could not find an active window matching *\"{target}\"*.",
                )

        # ---------------- 7. Close / Terminate Application ----------------
        close_match = re.match(
            r"^(close|quit|exit|terminate|kill)\s+(?:application\s+|app\s+)?([^\n]+)$",
            lower_stripped,
        )
        if close_match:
            target = close_match.group(2).strip()
            res = self.app_controller.close_application(target)
            if res["success"]:
                content = f"⏹ **{res['message']}**"
            else:
                content = f"⚠️ {res['error']}"

            return IntentResult(
                is_windows_action=True,
                action_type="close_app",
                success=res["success"],
                title=f"Close {target}",
                content=content,
            )

        # =====================================================================
        # BROWSER AND WEBSITE INTELLIGENCE (Phase 3)
        # =====================================================================

        # ---------------- 8. Detect & List Installed Browsers ----------------
        if lower_stripped in [
            "what browsers are installed", "list browsers", "show browsers",
            "installed browsers", "detect browsers", "which browsers are installed"
        ] or (
            "browser" in lower_stripped and any(w in lower_stripped for w in ["what", "list", "show", "installed", "detect"])
        ):
            browsers = self.browser_detector.detect_installed_browsers()
            if not browsers:
                content = "No supported web browsers detected on this system."
            else:
                rows = []
                for b in browsers:
                    def_badge = " *(System Default)*" if b.is_default else ""
                    run_badge = f" — 🟢 Active ({len(b.running_pids)} processes)" if b.is_running else " — ⚪ Inactive"
                    rows.append(f"- **{b.name}**{def_badge}{run_badge}\n  `{b.executable_path}`")
                content = f"### 🌐 Installed Web Browsers ({len(browsers)} detected)\n\n" + "\n".join(rows)

            return IntentResult(
                is_windows_action=True,
                action_type="list_browsers",
                success=True,
                title="Installed Browsers",
                content=content,
            )

        # ---------------- 9. Switch to Specific Browser Tab ----------------
        tab_switch_match = re.match(
            r"^(switch\s+to|focus|go\s+to)\s+(?:the\s+)?([^\n]+?)\s+tab$",
            lower_stripped,
        )
        if tab_switch_match:
            target_tab = tab_switch_match.group(2).strip()
            res = self.navigator.switch_to_tab(target_tab)
            return IntentResult(
                is_windows_action=True,
                action_type="switch_tab",
                success=res.success,
                title=res.title,
                content=res.content,
                raw_data=res.raw_data,
            )

        # ---------------- 10. Read & Summarize Webpage ----------------
        is_read_request = (
            any(phrase in lower_stripped for phrase in [
                "read the current webpage", "read current webpage", "read current page",
                "summarize the current webpage", "summarize current webpage", "summarize current page",
                "summarize this page", "summarize the page", "read the page", "read this webpage",
                "read this page", "summarize webpage", "summarize website"
            ])
            or lower_stripped.startswith("read webpage ")
            or lower_stripped.startswith("summarize ")
        )
        if is_read_request:
            url_match = re.search(r"https?://[^\s]+", clean)
            target_url = url_match.group(0) if url_match else ""
            res = self.navigator.read_and_summarize_page(target_url)
            return IntentResult(
                is_windows_action=True,
                action_type="read_webpage",
                success=res.success,
                title=res.title,
                content=res.content,
                raw_data=res.raw_data,
            )

        # ---------------- 11. Search with Provider (YouTube, Google, Bing) ----------------
        provider_search_match = re.match(
            r"^(?:open\s+|go\s+to\s+)?(youtube|google|bing)\s+(?:and\s+)?search(?:\s+for)?\s+(.+)$",
            lower_stripped,
        )
        if provider_search_match:
            provider = provider_search_match.group(1).strip()
            query = provider_search_match.group(2).strip()
            res = self.navigator.execute_search(query=query, provider=provider, open_in_browser=True)
            return IntentResult(
                is_windows_action=True,
                action_type="search_web",
                success=res.success,
                title=res.title,
                content=res.content,
                raw_data=res.raw_data,
            )

        # ---------------- 12. General Web Search ----------------
        search_web_match = re.match(
            r"^(search\s+for|search\s+the\s+web\s+for|search\s+web\s+for|search\s+online\s+for|find\s+a\s+website\s+for)\s+(.+)$",
            lower_stripped,
        )
        if search_web_match:
            query = search_web_match.group(2).strip()
            if not any(query.endswith(ext) for ext in [".txt", ".pdf", ".py", ".doc", ".docx", ".png"]):
                res = self.navigator.execute_search(query=query, provider="bing", open_in_browser=False)
                return IntentResult(
                    is_windows_action=True,
                    action_type="search_web",
                    success=res.success,
                    title=res.title,
                    content=res.content,
                    raw_data=res.raw_data,
                )

        # ---------------- 13. Multi-Website / Multi-Tab Navigation ----------------
        multi_tab_match = re.match(
            r"^(?:open|visit|launch)\s+([^\n]+?)\s+and\s+([^\n]+?)(?:\s+in\s+separate\s+tabs)?$",
            lower_stripped,
        )
        if multi_tab_match:
            cand1 = multi_tab_match.group(1).strip()
            cand2 = multi_tab_match.group(2).strip()
            is_cand1_site = bool(self.website_registry.find_website(cand1) or self.website_registry.validate_url(cand1))
            is_cand2_site = bool(self.website_registry.find_website(cand2) or self.website_registry.validate_url(cand2))
            if is_cand1_site or is_cand2_site:
                res = self.navigator.navigate_multi_tabs([cand1, cand2])
                return IntentResult(
                    is_windows_action=True,
                    action_type="multi_tab_navigation",
                    success=res.success,
                    title=res.title,
                    content=res.content,
                    raw_data=res.raw_data,
                )

        # ---------------- 14. Single Website or URL Navigation ----------------
        site_nav_match = re.match(
            r"^(open|visit|go\s+to|navigate\s+to)\s+(?:this\s+url:\s*|url:\s*|website\s+)?([^\n]+)$",
            lower_stripped,
        )
        if site_nav_match:
            candidate = site_nav_match.group(2).strip().rstrip(".")
            # Strip trailing browser phrases (e.g. "Open ChatGPT in my browser")
            candidate = re.sub(
                r"\s+in\s+(?:my\s+|the\s+)?(?:browser|edge|chrome|firefox|brave).*$",
                "",
                candidate,
                flags=re.IGNORECASE,
            ).strip()

            # Check if candidate is known website in Website Registry
            known_site = self.website_registry.find_website(candidate)
            if known_site:
                res = self.navigator.navigate_single(known_site.name)
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_website",
                    success=res.success,
                    title=res.title,
                    content=res.content,
                    raw_data=res.raw_data,
                )

            # Check if candidate is a URL
            if candidate.startswith("http://") or candidate.startswith("https://") or (
                "." in candidate and not candidate.endswith((".exe", ".lnk", ".bat", ".py", ".txt"))
            ):
                res = self.navigator.navigate_single(candidate)
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_url",
                    success=res.success,
                    title=res.title,
                    content=res.content,
                    raw_data=res.raw_data,
                )

        # =====================================================================
        # AI APPLICATION INTEGRATION (Phase 4)
        # =====================================================================

        # ---------------- 15. Switch Default AI Provider ----------------
        switch_provider_match = re.match(
            r"^(?:switch\s+(?:to\s+|provider\s+to\s+|default\s+provider\s+to\s+)|use\s+([a-zA-Z0-9_\-\s]+?)\s+as\s+default\s*(?:provider|ai)?$)",
            lower_stripped,
        )
        if switch_provider_match:
            from bolt.ai.provider_manager import get_provider_manager
            target_p = switch_provider_match.group(1) if switch_provider_match.group(1) else lower_stripped.replace("switch to", "").replace("switch provider to", "").replace("switch default provider to", "").strip()
            pm = get_provider_manager()
            ok, msg = pm.switch_default_provider(target_p)
            return IntentResult(
                is_windows_action=True,
                action_type="switch_ai_provider",
                success=ok,
                title="AI Provider Switched" if ok else "Provider Switch Failed",
                content=msg,
                raw_data={"provider": target_p},
            )

        # ---------------- 16. Multi-AI Comparison ----------------
        is_compare_query = (
            lower_stripped.startswith("compare ")
            and any(p in lower_stripped for p in ["gemini", "chatgpt", "openai", "providers", "answers", "responses"])
        )
        if is_compare_query:
            from bolt.ai.multi_ai import get_multi_ai_comparator
            comp = get_multi_ai_comparator()
            prompt_for_ai = re.sub(
                r"^compare\s+(?:how\s+|the\s+(?:answers|responses)\s+from\s+)?(?:gemini\s+and\s+chatgpt|chatgpt\s+and\s+gemini)\s+(?:explain|describe|answer|handle|on|for\s+)?",
                "",
                lower_stripped,
            ).strip()
            if not prompt_for_ai:
                prompt_for_ai = clean
            res = comp.compare_providers(prompt_for_ai, provider_names=["gemini", "openai"])
            return IntentResult(
                is_windows_action=True,
                action_type="compare_ai",
                success=(res.successful_count > 0),
                title="Multi-AI Comparison",
                content=res.formatted_markdown,
                raw_data={"prompt": prompt_for_ai, "successful_count": res.successful_count},
            )

        # ---------------- 17. Explicit Provider Query ----------------
        ask_match = re.match(
            r"^(?:ask|tell|use)\s+(gemini|chatgpt|openai|mock)\s+(?:to\s+|for\s+|this\s+task:\s*|this\s+question:\s*)?(.+)$",
            lower_stripped,
        )
        if ask_match:
            p_target = ask_match.group(1).strip()
            sub_query = ask_match.group(2).strip()
            return IntentResult(
                is_windows_action=False,
                action_type="query_provider",
                title=f"Query {p_target.title()}",
                raw_data={"provider_override": p_target, "prompt": sub_query},
            )

        # ---------------- 15. Open / Launch Application ----------------
        open_match = re.match(
            r"^(open|launch|start|run)\s+(?:application\s+|app\s+)?([^\n]+)$",
            lower_stripped,
        )
        if open_match:
            target = open_match.group(2).strip()

            # Prevent misinterpreting web URLs (handled in Phase 3) or conversational statements
            if target.startswith("http://") or target.startswith("https://") or "website" in target:
                return IntentResult(is_windows_action=False)

            res = self.app_controller.open_application(target)
            if res["success"]:
                action_badge = "ℹ️" if res.get("already_running") else "✅"
                content = f"{action_badge} **{res['message']}**"
            else:
                content = f"⚠️ {res['error']}"

            return IntentResult(
                is_windows_action=True,
                action_type="open_app",
                success=res["success"],
                title=f"Open {target}",
                content=content,
            )

        # ---------------- 9. Minimize / Maximize Active Window ----------------
        if "minimize" in lower_stripped and ("window" in lower_stripped or "all" in lower_stripped):
            windows = self.window_mgr.get_visible_windows()
            if windows:
                # Minimize first non-BOLT window
                for w in windows:
                    if "bolt" not in w.title.lower():
                        self.window_mgr.minimize_window(w.hwnd)
                        return IntentResult(
                            is_windows_action=True,
                            action_type="minimize_window",
                            success=True,
                            title="Minimize Window",
                            content=f"🪟 Minimized window: **{w.title}**",
                        )

        # Not a direct Windows operational command
        return IntentResult(is_windows_action=False)


_DISPATCHER_INSTANCE: Optional[WindowsIntentDispatcher] = None


def get_intent_dispatcher() -> WindowsIntentDispatcher:
    global _DISPATCHER_INSTANCE
    if _DISPATCHER_INSTANCE is None:
        _DISPATCHER_INSTANCE = WindowsIntentDispatcher()
    return _DISPATCHER_INSTANCE
