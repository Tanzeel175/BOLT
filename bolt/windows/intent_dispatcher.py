"""
Natural Language Windows & Browser Intent Dispatcher for BOLT.
Translates user instructions into Windows operations (Application Control, Window Management,
File Operations, Hardware Telemetry) and Browser/Website operations (Multi-tab Navigation,
Web Search, Tab Switching, Webpage Summarization).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bolt.core.logger import get_logger
from bolt.windows.app_controller import AppController, get_app_controller
from bolt.windows.file_manager import FileManager, get_file_manager
from bolt.windows.system_info import SystemInfo
from bolt.windows.window_manager import WindowManager, get_window_manager
from bolt.browser.browser_controller import BrowserController, get_browser_controller
from bolt.browser.search_engine import SearchEngine

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
    """Classifies natural language instructions and executes corresponding operations."""

    def __init__(
        self,
        app_controller: Optional[AppController] = None,
        window_mgr: Optional[WindowManager] = None,
        file_mgr: Optional[FileManager] = None,
        browser_controller: Optional[BrowserController] = None,
    ):
        self.app_controller = app_controller or get_app_controller()
        self.window_mgr = window_mgr or get_window_manager()
        self.file_mgr = file_mgr or get_file_manager()
        self.browser_controller = browser_controller or get_browser_controller()

    def dispatch(self, text: str) -> IntentResult:
        """Analyze text and execute matching Windows or Browser operation if detected."""
        clean = text.strip()
        lower = clean.lower()

        # Remove polite prefix or assistant name if present (e.g., "BOLT, open notepad" -> "open notepad")
        lower_stripped = re.sub(r"^(bolt|hey bolt|please|can you|could you)\s*[,:]?\s*", "", lower).strip()
        # Remove trailing period or question mark for pattern matching
        lower_stripped = lower_stripped.rstrip(".?!").strip()

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

        # ---------------- Phase 3: Webpage Reading & Content Summarization ----------------
        if any(k in lower_stripped for k in [
            "read the current webpage", "read current webpage", "read this webpage",
            "summarize the current webpage", "summarize current webpage", "summarize this page",
            "read the webpage", "read webpage and summarize", "read current page"
        ]):
            res = self.browser_controller.read_current_page()
            if res["success"]:
                return IntentResult(
                    is_windows_action=True,
                    action_type="read_webpage",
                    success=True,
                    title=f"Webpage: {res.get('title', 'Content')}",
                    content=res.get("summary", ""),
                )
            else:
                return IntentResult(
                    is_windows_action=True,
                    action_type="read_webpage",
                    success=False,
                    title="Read Webpage Error",
                    content=f"⚠️ {res.get('error', 'Could not read webpage content.')}",
                )

        # ---------------- Phase 3: Tab Management ----------------
        switch_tab_match = re.match(
            r"^(?:switch\s+to|focus|bring\s+to\s+front)\s+(?:the\s+)?([^\n]+?)\s+tab$",
            lower_stripped,
        )
        if switch_tab_match:
            target_tab = switch_tab_match.group(1).strip()
            res = self.browser_controller.switch_to_tab(target_tab)
            if res["success"]:
                content = f"🪟 **{res['message']}**"
            else:
                content = f"⚠️ {res['error']}"

            return IntentResult(
                is_windows_action=True,
                action_type="switch_tab",
                success=res["success"],
                title=f"Tab: {target_tab}",
                content=content,
            )

        if lower_stripped in ["close tab", "close the tab", "close active tab", "close current tab"]:
            res = self.browser_controller.close_tab()
            if res["success"]:
                content = f"⏹ **{res['message']}**"
            else:
                content = f"⚠️ {res['error']}"

            return IntentResult(
                is_windows_action=True,
                action_type="close_tab",
                success=res["success"],
                title="Close Tab",
                content=content,
            )

        if any(k in lower_stripped for k in ["list open tabs", "list tabs", "show tabs", "open tabs"]):
            tabs = self.browser_controller.get_open_tabs()
            if not tabs:
                content = "No browser tabs currently managed by BOLT."
            else:
                rows = [
                    f"- Tab {t['index'] + 1}: **[{t['title']}]({t['url']})** {'*(active)*' if t['is_active'] else ''}"
                    for t in tabs
                ]
                content = f"### 📑 Open Browser Tabs ({len(tabs)})\n\n" + "\n".join(rows)

            return IntentResult(
                is_windows_action=True,
                action_type="list_tabs",
                success=True,
                title="Open Tabs",
                content=content,
            )

        # ---------------- Phase 3: Multi-Website Navigation in Separate Tabs ----------------
        multi_tab_match = re.match(
            r"^(?:open|visit|launch)\s+([a-zA-Z0-9\s\-]+?)\s+and\s+([a-zA-Z0-9\s\-]+?)(?:\s+in\s+separate\s+tabs|\s+in\s+tabs|\s+together)?$",
            lower_stripped,
        )
        if multi_tab_match and "search" not in lower_stripped:
            site1_raw = multi_tab_match.group(1).strip()
            site2_raw = multi_tab_match.group(2).strip()
            reg = self.browser_controller.registry

            # Check if both candidate names resolve as websites or URLs
            s1_rec = bool(reg.resolve_website(site1_raw) or reg.is_valid_url(site1_raw))
            s2_rec = bool(reg.resolve_website(site2_raw) or reg.is_valid_url(site2_raw))

            if s1_rec and s2_rec:
                results = self.browser_controller.open_multiple_urls([site1_raw, site2_raw])
                lines = ["### 🌐 Opened Websites in Separate Tabs\n"]
                all_ok = True
                for r in results:
                    if r["success"]:
                        badge = "ℹ️" if r.get("action") == "reused_tab" else "✅"
                        lines.append(f"- {badge} **{r.get('display_name', 'Site')}**: `{r.get('url', '')}`")
                    else:
                        all_ok = False
                        lines.append(f"- ⚠️ **Failed**: {r.get('error')}")

                return IntentResult(
                    is_windows_action=True,
                    action_type="multi_browser_nav",
                    success=all_ok,
                    title="Opened Multiple Tabs",
                    content="\n".join(lines),
                )

        # ---------------- Phase 3: Site-Specific Search (YouTube / Google / GitHub) ----------------
        site_search_match = re.match(
            r"^(?:open\s+)?(youtube|google|duckduckgo|bing|github)\s+and\s+search\s+(?:for\s+)?([^\n]+)$",
            lower_stripped,
        ) or re.match(
            r"^search\s+(youtube|google|duckduckgo|bing|github)\s+for\s+([^\n]+)$",
            lower_stripped,
        )
        if site_search_match:
            provider = site_search_match.group(1).strip()
            query = site_search_match.group(2).strip()
            search_url = SearchEngine.build_search_url(query, provider)
            nav_res = self.browser_controller.open_url(search_url)

            content = (
                f"🔍 **Searching {provider.title()} for:** *\"{query}\"*\n\n"
                f"🔗 Direct Search URL: [{search_url}]({search_url})\n\n"
                f"✅ **{nav_res.get('message', 'Opened search in browser.')}**"
            )
            return IntentResult(
                is_windows_action=True,
                action_type="site_search",
                success=nav_res["success"],
                title=f"{provider.title()} Search: {query}",
                content=content,
            )

        # ---------------- Phase 3: General Internet Search ----------------
        is_web_search = (
            lower_stripped.startswith("search for ")
            or lower_stripped.startswith("search the web for ")
            or lower_stripped.startswith("search the internet for ")
            or lower_stripped.startswith("search online for ")
            or lower_stripped.startswith("google ")
            or lower_stripped.startswith("find a website for ")
        )
        # Avoid intercepting local file search queries (e.g. "search for file notes.txt")
        if is_web_search and not any(term in lower_stripped for term in [".txt", ".py", ".pdf", ".doc", "file"]):
            clean_search_query = re.sub(
                r"^(search\s+for|search\s+the\s+web\s+for|search\s+the\s+internet\s+for|search\s+online\s+for|google|find\s+a\s+website\s+for)\s+",
                "",
                lower_stripped,
            ).strip()

            search_res = self.browser_controller.search_web(clean_search_query, provider="google")
            return IntentResult(
                is_windows_action=True,
                action_type="web_search",
                success=True,
                title=f"Search: {clean_search_query}",
                content=search_res.get("summary_md", ""),
            )

        # ---------------- 4. Open Folder / Directory ----------------
        folder_match = re.match(
            r"^(open|show|explore)\s+(my\s+)?(folder\s+)?([\w\s\\/:\-]+?)(?:\s+folder)?$",
            lower_stripped,
        )
        if folder_match:
            candidate = folder_match.group(4).strip()
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
            if any(term in query for term in [".", "file", "document", "pdf", "txt", "py", "doc"]):
                clean_query = query.replace("file", "").strip()
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

        # ---------------- Phase 4: Switch AI Provider ----------------
        if any(k in lower_stripped for k in [
            "switch to gemini", "switch to openai", "switch to chatgpt",
            "switch default provider", "switch provider", "switch to mock", "switch to local"
        ]):
            from bolt.ai.provider_manager import get_provider_manager
            pm = get_provider_manager()
            target_p = (
                "gemini" if "gemini" in lower_stripped
                else "openai" if ("openai" in lower_stripped or "chatgpt" in lower_stripped)
                else "mock"
            )
            ok, msg = pm.switch_default_provider(target_p)
            return IntentResult(
                is_windows_action=True,
                action_type="switch_ai_provider",
                success=ok,
                title=f"Switch AI Provider: {target_p.title()}",
                content=msg,
            )

        # ---------------- Phase 4: Multi-AI Comparison ----------------
        if lower_stripped.startswith("compare ") and any(p in lower_stripped for p in ["gemini", "chatgpt", "openai"]):
            from bolt.ai.multi_ai import get_multi_ai_comparator
            comparator = get_multi_ai_comparator()
            prompt_clean = re.sub(
                r"^compare\s+(?:how\s+)?(?:gemini\s+and\s+chatgpt|chatgpt\s+and\s+gemini|openai\s+and\s+gemini|gemini\s+and\s+openai)\s+(?:explain\s+|answer\s+)?",
                "",
                lower_stripped,
            ).strip()
            if not prompt_clean:
                prompt_clean = lower_stripped
            res = comparator.compare_providers(prompt_clean, ["gemini", "openai"])
            return IntentResult(
                is_windows_action=True,
                action_type="compare_ai",
                success=True,
                title="Multi-AI Comparison",
                content=res.formatted_markdown,
            )

        # ---------------- Phase 4: Explicit Named Provider Query ----------------
        ask_match = re.match(
            r"^ask\s+(gemini|chatgpt|openai|mock)\s+(?:to\s+)?([^\n]+)$",
            lower_stripped,
        )
        if ask_match:
            prov_target = ask_match.group(1).strip()
            prompt_text = ask_match.group(2).strip()
            return IntentResult(
                is_windows_action=False,
                action_type="query_provider",
                success=True,
                title=f"Query {prov_target.title()}",
                content=prompt_text,
                raw_data={"provider_override": prov_target, "prompt": prompt_text},
            )

        # ---------------- 6. Switch to Application / Window ----------------
        switch_match = re.match(
            r"^(switch\s+to|focus|bring\s+to\s+front|activate)\s+([^\n]+)$",
            lower_stripped,
        )
        if switch_match:
            target = switch_match.group(2).strip()
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

        # ---------------- 8. Open Website or Application ----------------
        open_match = re.match(
            r"^(open|visit|go\s+to|navigate\s+to|launch|start|run)\s+(?:website\s+|this\s+url\s*:\s*|url\s+|application\s+|app\s+)?([^\n]+)$",
            lower_stripped,
        )
        if open_match:
            raw_target = open_match.group(2).strip()
            # Clean off trailing browser context phrases like "in my browser" or "in browser"
            target = re.sub(r"\s+in\s+(?:my\s+)?browser$", "", raw_target).strip()

            # A. Check if target is a Known Website or Valid Web URL
            is_explicit_url = target.startswith("http://") or target.startswith("https://")
            is_known_site = bool(self.browser_controller.registry.resolve_website(target))
            is_domain = bool(self.browser_controller.registry.is_valid_url(target)) and ("." in target or is_known_site)

            if is_explicit_url or is_known_site or is_domain:
                res = self.browser_controller.open_url(target)
                if res["success"]:
                    action_badge = "ℹ️" if res.get("action") == "reused_tab" else "🌐"
                    auth_note = ""
                    if res.get("requires_auth"):
                        auth_note = (
                            "\n\n> ⚠️ *Note: This website requires account login or authentication. "
                            "For your security, please complete sign-in manually.*"
                        )
                    content = f"{action_badge} **{res['message']}**{auth_note}"
                else:
                    content = f"⚠️ {res['error']}"

                return IntentResult(
                    is_windows_action=True,
                    action_type="open_website",
                    success=res["success"],
                    title=f"Website: {res.get('display_name', target)}",
                    content=content,
                )

            # B. Check if target is an installed desktop application
            app_res = self.app_controller.open_application(target)
            if app_res["success"]:
                action_badge = "ℹ️" if app_res.get("already_running") else "✅"
                content = f"{action_badge} **{app_res['message']}**"
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_app",
                    success=True,
                    title=f"Open {target}",
                    content=content,
                )

            # If neither website nor app, check if explicit app launch was asked
            if "app" in lower_stripped or "application" in lower_stripped:
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_app",
                    success=False,
                    title=f"Application Not Found",
                    content=f"⚠️ {app_res['error']}",
                )

        # ---------------- 9. Minimize / Maximize Active Window ----------------
        if "minimize" in lower_stripped and ("window" in lower_stripped or "all" in lower_stripped):
            windows = self.window_mgr.get_visible_windows()
            if windows:
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

        # Not a direct operational command -> route to AI LLM
        return IntentResult(is_windows_action=False)


_DISPATCHER_INSTANCE: Optional[WindowsIntentDispatcher] = None


def get_intent_dispatcher() -> WindowsIntentDispatcher:
    global _DISPATCHER_INSTANCE
    if _DISPATCHER_INSTANCE is None:
        _DISPATCHER_INSTANCE = WindowsIntentDispatcher()
    return _DISPATCHER_INSTANCE
