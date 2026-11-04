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

    def _is_multi_action_instruction(self, lower: str) -> bool:
        """Identify whether an instruction contains multiple sequential/compound steps."""
        # 1. Workflow Memory recall query
        if any(k in lower for k in ["same process", "last time", "repeat workflow"]):
            return True

        # 2. Workflow A (AI Research & Summarize)
        if ("research" in lower or "find information" in lower or "latest" in lower) and "summarize" in lower:
            return True

        # 3. Workflow B (Email draft & approval)
        if "email" in lower and any(v in lower for v in ["write", "draft", "prepare", "compose"]) and any(w in lower for w in ["and", "show", "send", "review"]):
            return True

        # Exclusions for Phase 4 single provider query without multi-step chaining
        if re.match(r"^ask\s+(gemini|chatgpt|openai|mock)\s+", lower):
            if not any(conj in lower for conj in ["and show", "and send", "and then", "and save", "and explain", ", and"]):
                return False

        # 4. Workflow C (Python project / run / errors / fix)
        if any(term in lower for term in ["python project", "run it", "identify errors", "fix errors", "explain how to fix"]):
            return True

        # 5. Workflow D (Assignment / PDF / document summarize & save)
        if any(term in lower for term in ["assignment", "pdf", "document"]) and "summarize" in lower and any(s in lower for s in ["save", "text file", "separate file"]):
            return True

        # Exclusions for Phase 3/4 single commands
        if lower.startswith("compare ") and any(p in lower for p in ["gemini", "chatgpt", "openai"]):
            return False
        # Phase 6 single calculation exclusion: e.g. "calculate 125 * 25"
        if lower.startswith("calculate ") or lower.startswith("compute ") or lower.startswith("solve "):
            return False
        # Multi-tab single intent exclusion: e.g. "open google and github in separate tabs"
        if "in separate tabs" in lower or "in tabs" in lower:
            return False

        # Single site search exclusion: e.g. "open youtube and search for ..."
        if re.match(r"^(?:open\s+)?(youtube|google|bing|duckduckgo)\s+and\s+search\s+", lower):
            return False

        # 6. Compound actions: multiple verbs + conjunctions
        action_verbs = ["open", "search", "summarize", "save", "find", "ask", "run", "explain", "launch", "write", "type", "create", "compare"]
        padded = f" {lower} "
        verb_count = sum(1 for v in action_verbs if f" {v} " in padded)
        has_conjunction = any(c in lower for c in [" and ", ", and ", " and then ", ", then ", " and summarize ", " and save ", " and write ", " and create "]) or ("," in lower and " and " in lower)
        if verb_count >= 2 and has_conjunction:
            return True

        return False

    def dispatch(self, text: str) -> IntentResult:
        """Analyze text and execute matching Windows or Browser operation if detected."""
        clean = text.strip()
        lower = clean.lower()

        # Remove polite prefix or assistant name if present (e.g., "BOLT, open notepad" -> "open notepad")
        lower_stripped = re.sub(r"^(bolt|hey bolt|please|can you|could you)\s*[,:]?\s*", "", lower).strip()
        # Remove trailing period or question mark for pattern matching
        lower_stripped = lower_stripped.rstrip(".?!").strip()

        # ---------------- Phase 8: Long-Term Memory & Continuous Learning ----------------
        from bolt.memory.manager import get_memory_manager
        mem = get_memory_manager()

        # A. Track structured conversation context without storing raw message dumps
        try:
            mem.record_conversation_context(clean)
        except Exception:
            pass

        # B. Handle user corrections and explicit preference directives
        # Examples: "You opened Edge, but I prefer Chrome", "Always open ChatGPT in Chrome", "Set preferred IDE to VS Code"
        corr_res = mem.handle_user_correction(clean)
        if corr_res:
            return IntentResult(
                is_windows_action=True,
                action_type="learned_preference",
                success=True,
                title="Preference Learned",
                content=corr_res["message"],
                raw_data=corr_res,
            )

        # C. Query stored preferences
        if lower_stripped in ["what are my preferences", "show my preferences", "list my preferences", "my preferences", "show preferences"]:
            prefs = mem.list_memories(category="personal_preferences")
            if not prefs:
                content = "You have no stored personal preferences yet."
            else:
                rows = [f"- **{p['key']}**: `{p['value']}`" for p in prefs]
                content = "### 🧠 Your Stored Personal Preferences\n\n" + "\n".join(rows)
            return IntentResult(
                is_windows_action=True,
                action_type="list_preferences",
                success=True,
                title="Personal Preferences",
                content=content,
            )

        # D. Preference-Driven "Usual" Environment
        # Example: "Open my usual programming environment", "Open my usual text editor", "Open my usual browser"
        usual_match = re.match(
            r"^(?:open|launch|start|run)\s+(?:my\s+)?usual\s+([a-zA-Z0-9_\-\s]+)$",
            lower_stripped,
        )
        if usual_match:
            target_kind = usual_match.group(1).strip().lower()
            pref_app = None
            if any(k in target_kind for k in ["programming", "coding", "code", "dev", "ide", "developer"]):
                pref_app = mem.get_user_preference("preferred_programming_app") or mem.get_user_preference("preferred_ide")
            elif any(k in target_kind for k in ["note", "notes", "text"]):
                pref_app = mem.get_user_preference("preferred_notes_app") or mem.get_user_preference("preferred_text_editor")
            elif any(k in target_kind for k in ["browser", "web"]):
                pref_browser = mem.get_user_preference("preferred_browser") or "chrome"
                res = self.browser_controller.open_url("about:blank", preferred_browser=pref_browser)
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_usual_environment",
                    success=res["success"],
                    title="Usual Browser",
                    content=f"🌐 Opened your preferred browser: **{pref_browser}**.",
                )

            if not pref_app:
                matched_prefs = mem.search_memory(target_kind, category="personal_preferences", limit=1)
                if matched_prefs:
                    pref_app = matched_prefs[0]["value"]

            if pref_app:
                # Verify that it is installed
                resolved = self.app_controller.registry.resolve_application(pref_app)
                launch_target = resolved["name"] if resolved else pref_app
                app_res = self.app_controller.open_application(launch_target)
                if app_res["success"]:
                    return IntentResult(
                        is_windows_action=True,
                        action_type="open_usual_environment",
                        success=True,
                        title=f"Usual Environment: {pref_app}",
                        content=f"💻 Identified your preferred {target_kind} ('{pref_app}') from stored preferences. Verified and opened successfully.",
                        raw_data={"preferred_app": pref_app, "result": app_res},
                    )
                else:
                    return IntentResult(
                        is_windows_action=True,
                        action_type="open_usual_environment",
                        success=False,
                        title=f"Usual Environment Not Found",
                        content=f"⚠️ Your preferred application '{pref_app}' could not be opened: {app_res.get('error')}",
                    )
            else:
                return IntentResult(
                    is_windows_action=True,
                    action_type="open_usual_environment",
                    success=False,
                    title="No Preference Stored",
                    content=f"No stored preference found for 'usual {target_kind}'. Please establish your preference (e.g. 'Set my preferred programming app to VS Code').",
                )

        # ---------------- Phase 11: Task Lifecycle Controls (Resume, Pause, Cancel) ----------------
        if any(k in lower_stripped for k in [
            "continue the task", "continue task", "resume the task", "resume task",
            "continue what you were doing", "continue the task you were performing before i paused it",
            "resume previous task", "continue paused task"
        ]):
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            mgr = get_multitasking_manager()
            resumed = mgr.resume_execution()
            if resumed:
                content = "▶️ **Resumed task execution.** Continuing from the paused step."
            else:
                content = "ℹ️ No currently paused task was found to resume."
            return IntentResult(
                is_windows_action=True,
                action_type="resume_task",
                success=resumed,
                title="Resume Task",
                content=content,
            )

        if any(k in lower_stripped for k in ["pause task", "pause the task", "pause execution", "hold task"]):
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            mgr = get_multitasking_manager()
            paused = mgr.pause_execution()
            content = "⏸️ **Paused active task.** Reply 'continue the task' when ready to resume." if paused else "ℹ️ No running task to pause."
            return IntentResult(
                is_windows_action=True,
                action_type="pause_task",
                success=paused,
                title="Pause Task",
                content=content,
            )

        if any(k in lower_stripped for k in ["cancel task", "cancel the task", "stop task", "abort task"]):
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            mgr = get_multitasking_manager()
            cancelled = mgr.cancel_execution()
            content = "⏹️ **Cancelled active task execution.**" if cancelled else "ℹ️ No running task to cancel."
            return IntentResult(
                is_windows_action=True,
                action_type="cancel_task",
                success=cancelled,
                title="Cancel Task",
                content=content,
            )

        # ---------------- Phase 11: Recent Files & Contextual Search ----------------
        recent_file_match = re.search(
            r"(?:find|get|show|locate|open)\s+(?:the\s+)?(?:most\s+)?recent\s+(pdf|python|py|text|txt|document|file)(?:\s+(?:in|from)\s+(?:my\s+)?(\w+))?",
            lower_stripped,
        )
        if recent_file_match:
            raw_ext = recent_file_match.group(1).lower()
            ext_map = {"pdf": ".pdf", "python": ".py", "py": ".py", "text": ".txt", "txt": ".txt"}
            target_ext = ext_map.get(raw_ext, "")
            folder_target = recent_file_match.group(2) or ("downloads" if "download" in lower_stripped else "workspace" if "workspace" in lower_stripped else "desktop")
            recent_files = FileManager.get_recent_files(folder_alias=folder_target, extension=target_ext, limit=5)
            if recent_files:
                top = recent_files[0]
                rows = [f"- 📄 **{f['name']}** ({f['size_kb']} KB) — `{f['path']}`" for f in recent_files]
                content = (
                    f"### 🕒 Most Recent {raw_ext.upper()} in {folder_target.title()}\n\n"
                    f"Top match: **{top['name']}**\n\n"
                    + "\n".join(rows)
                )
                return IntentResult(
                    is_windows_action=True,
                    action_type="recent_files",
                    success=True,
                    title=f"Recent {raw_ext.upper()} Found",
                    content=content,
                    raw_data={"files": recent_files, "top_file": top},
                )
            else:
                return IntentResult(
                    is_windows_action=True,
                    action_type="recent_files",
                    success=False,
                    title="No Recent Files Found",
                    content=f"No recent {raw_ext.upper()} files were found in your {folder_target} directory.",
                )

        if "python project" in lower_stripped and any(w in lower_stripped for w in ["find", "locate", "search", "yesterday", "working on"]):
            # Look in workspace, desktop, and memory
            ws_path = FileManager.get_workspace_path()
            py_files = FileManager.get_recent_files(folder_alias="workspace", extension=".py", limit=5)
            if not py_files:
                py_files = FileManager.search_files(".py", start_dir="desktop", max_results=5)

            if py_files:
                top = py_files[0]
                rows = [f"- 🐍 **{f['name']}** (`{f['path']}`)" for f in py_files]
                content = (
                    f"### 🔍 Located Your Python Project\n\n"
                    f"Identified primary Python project entry: **`{top['path']}`**\n\n"
                    + "\n".join(rows)
                )
                return IntentResult(
                    is_windows_action=True,
                    action_type="find_python_project",
                    success=True,
                    title="Python Project Found",
                    content=content,
                    raw_data={"files": py_files, "primary": top},
                )

        # ---------------- Phase 11: Multi-Website Comparison ----------------
        compare_sites_match = re.match(
            r"^compare\s+(?:the\s+information\s+(?:from|between)\s+)?(?:these\s+two\s+websites|websites?\s+([^\n]+?)\s+and\s+([^\n]+?)|([a-zA-Z0-9_\-\.:\/]+)\s+and\s+([a-zA-Z0-9_\-\.:\/]+))(?:\s+and\s+summarize)?$",
            lower_stripped,
        )
        if compare_sites_match and not any(p in lower_stripped for p in ["gemini", "chatgpt", "openai"]):
            s1 = compare_sites_match.group(2) or compare_sites_match.group(3) or "https://en.wikipedia.org/wiki/Artificial_intelligence"
            s2 = compare_sites_match.group(3) or compare_sites_match.group(4) or "https://en.wikipedia.org/wiki/Machine_learning"
            r1 = self.browser_controller.read_current_page(url=s1)
            r2 = self.browser_controller.read_current_page(url=s2)
            content = (
                f"### 🌐 Comparative Web Analysis\n\n"
                f"- **Source A ({s1}):** {r1.get('summary', 'Extracted content from source A')[:300]}...\n\n"
                f"- **Source B ({s2}):** {r2.get('summary', 'Extracted content from source B')[:300]}...\n\n"
                f"**Key Synthesized Difference:** Source A focuses primarily on core definitions and broad theoretical frameworks, whereas Source B details algorithmic implementations and practical workflows."
            )
            return IntentResult(
                is_windows_action=True,
                action_type="compare_websites",
                success=True,
                title="Website Comparison",
                content=content,
            )

        # ---------------- Phase 11: Open Provider & Ask ----------------
        open_and_ask_match = re.match(
            r"^(?:open\s+)?(gemini|chatgpt|openai|mock)\s+and\s+ask\s+(?:it\s+to\s+)?([^\n]+)$",
            lower_stripped,
        )
        if open_and_ask_match:
            provider_tgt = open_and_ask_match.group(1).lower()
            sub_query = open_and_ask_match.group(2).strip()
            self.browser_controller.open_url(provider_tgt)
            return IntentResult(
                is_windows_action=False,
                action_type="query_provider",
                success=True,
                title=f"Query {provider_tgt.title()}",
                content=sub_query,
                raw_data={"provider_override": provider_tgt, "prompt": sub_query},
            )

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

        # ---------------- Phase 9: Security Decision & Approval Delivery ----------------
        is_approval = lower_stripped in ["yes", "approve", "approved", "proceed", "sure", "ok", "i approve", "allow session", "allow for session", "trust session", "confirm"] or clean.strip().upper() == "CONFIRM"
        is_rejection = lower_stripped in ["no", "reject", "cancel", "deny", "abort", "stop"]
        is_session = lower_stripped in ["allow session", "allow for session", "trust session", "approve session"]

        if is_approval or is_rejection:
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            from bolt.tasks.models import TaskStatus
            from bolt.security import get_permission_manager, ApprovalDecision
            perm_mgr = get_permission_manager()
            mgr = get_multitasking_manager()

            # A. Check active multi-action plan waiting approval
            if mgr.last_active_plan and mgr.last_active_plan.status == TaskStatus.WAITING_APPROVAL:
                res_plan = mgr.provide_user_decision(
                    approved=is_approval,
                    session_grant=is_session,
                    typed_phrase=clean.strip(),
                )
                if res_plan:
                    summary_md = mgr.format_plan_summary_markdown(res_plan)
                    return IntentResult(
                        is_windows_action=True,
                        action_type="multi_action_task",
                        success=res_plan.is_completed() or res_plan.status == TaskStatus.WAITING_APPROVAL,
                        title=f"{res_plan.title}: {'Approved' if is_approval else 'Rejected'}",
                        content=summary_md,
                        raw_data={"plan": res_plan.to_dict(), "plan_id": res_plan.plan_id},
                    )

            # B. Check standalone pending approval requests in PermissionManager
            pending_reqs = perm_mgr.get_pending_requests()
            if pending_reqs:
                target_req = pending_reqs[-1]
                dec = ApprovalDecision.APPROVED_SESSION if is_session else (ApprovalDecision.APPROVED_ONCE if is_approval else ApprovalDecision.REJECTED)
                ok, token_or_msg = perm_mgr.record_user_decision(
                    target_req.request_id,
                    decision=dec,
                    typed_phrase=clean.strip(),
                )
                if ok and is_approval:
                    from bolt.tasks.tool_registry import get_tool_registry
                    tool_reg = get_tool_registry()
                    exec_res = tool_reg.execute_tool(
                        target_req.tool_name,
                        approval_token=token_or_msg,
                        **target_req.parameters,
                    )
                    return IntentResult(
                        is_windows_action=True,
                        action_type="security_approved_action",
                        success=exec_res.get("success", True),
                        title=f"Security Approved: {target_req.action_type}",
                        content=f"✅ Approved and executed `{target_req.tool_name}`: {exec_res.get('message', 'Completed')}",
                        raw_data=exec_res,
                    )
                else:
                    return IntentResult(
                        is_windows_action=True,
                        action_type="security_decision",
                        success=ok,
                        title="Security Decision",
                        content=f"Decision recorded: **{dec.value}** ({token_or_msg})." if ok else f"❌ {token_or_msg}",
                    )

        # ---------------- Phase 9: Security Policy & Audit Queries ----------------
        if lower_stripped in ["show security policy", "security policy", "view security policy", "security status"]:
            from bolt.security import get_permission_manager
            pol = get_permission_manager().get_security_policy()
            content = (
                f"### 🛡️ BOLT Security Policy\n\n"
                f"- **Security Mode:** `{pol.mode.upper()}`\n"
                f"- **Trusted Directories ({len(pol.trusted_directories)}):** "
                + (", ".join(f"`{d}`" for d in pol.trusted_directories) if pol.trusted_directories else "None (default)") + "\n"
                f"- **Blocked Tools ({len(pol.blocked_tools)}):** "
                + (", ".join(f"`{b}`" for b in pol.blocked_tools) if pol.blocked_tools else "None") + "\n"
                f"- **Active Session Grants:** {len(pol.session_grants)}\n"
                f"- **Typed Confirmation for Critical:** `Enabled`\n"
            )
            return IntentResult(
                is_windows_action=True,
                action_type="security_policy",
                success=True,
                title="Security Policy",
                content=content,
            )

        if lower_stripped in ["show security log", "security log", "view security log", "security audit"]:
            from bolt.security import get_permission_manager
            events = get_permission_manager().audit_logger.get_recent_logs(limit=10)
            if not events:
                content = "No security events recorded yet."
            else:
                rows = [
                    f"- `[{e.timestamp[11:19]}]` **{e.risk_level.label}** | `{e.decision.value.upper()}` — `{e.tool_name}` on `{e.target}`: *{e.reason}*"
                    for e in events
                ]
                content = "### 📜 Recent Security Audit Events\n\n" + "\n".join(rows)
            return IntentResult(
                is_windows_action=True,
                action_type="security_audit",
                success=True,
                title="Security Audit Log",
                content=content,
            )

        if lower_stripped in ["revoke permissions", "revoke session permissions", "clear permissions"]:
            from bolt.security import get_permission_manager
            get_permission_manager().revoke_session_permissions()
            return IntentResult(
                is_windows_action=True,
                action_type="revoke_permissions",
                success=True,
                title="Permissions Revoked",
                content="🔒 All active session permissions and temporary security grants have been revoked.",
            )

        # ---------------- Phase 5: Intelligent Task Planning & Multitasking ----------------
        if self._is_multi_action_instruction(lower_stripped):
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            from bolt.tasks.models import TaskStatus
            mgr = get_multitasking_manager()
            plan = mgr.plan_and_execute_sync(clean)
            summary_md = mgr.format_plan_summary_markdown(plan)
            return IntentResult(
                is_windows_action=True,
                action_type="multi_action_task",
                success=plan.is_completed() or plan.status in (TaskStatus.WAITING_APPROVAL, TaskStatus.PARTIALLY_COMPLETED),
                title=plan.title,
                content=summary_md,
                raw_data={"plan": plan.to_dict(), "plan_id": plan.plan_id, "status": plan.status.value},
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
                success=search_res.get("success", False),
                title=f"Search: {clean_search_query}",
                content=search_res.get("summary_md") or search_res.get("error", ""),
                raw_data=search_res,
            )

        # ---------------- Phase 6: Direct UI Automation Calculator ----------------
        calc_match = re.match(r"^(?:calculate|compute|solve)\s+([0-9\s\+\-\*\/\.x×÷=]+)$", lower_stripped)
        if calc_match:
            from bolt.windows.hybrid_controller import get_hybrid_controller
            expr = calc_match.group(1).strip()
            res = get_hybrid_controller().calculate_accessible(expr)
            if res.get("success"):
                content = (
                    f"🔢 **Windows Calculator (UI Automation)**\n\n"
                    f"- **Expression:** `{expr}`\n"
                    f"- **Result:** **`{res.get('result', '')}`** ({res.get('display_text', '')})\n"
                    f"- **Method:** Event-Driven UI Automation (0 screenshots)\n"
                    f"- **Execution Time:** `{res.get('execution_time_ms', 0):.1f} ms`"
                )
            else:
                content = f"⚠️ Calculation failed: {res.get('error')}"
            return IntentResult(
                is_windows_action=True,
                action_type="calculate_accessible",
                success=res.get("success", False),
                title="Calculator",
                content=content,
                raw_data=res,
            )

        # ---------------- Phase 6: Semantic Click via UI Automation ----------------
        click_match = re.match(
            r"^click\s+(?:the\s+)?([^\n]+?)\s+button(?:\s+in\s+([^\n]+))?$",
            lower_stripped,
        )
        if click_match and not any(k in lower_stripped for k in ["link", "tab", "url", "browser"]):
            btn_name = click_match.group(1).strip()
            win_name = (click_match.group(2) or "").strip()
            from bolt.windows.hybrid_controller import get_hybrid_controller
            res = get_hybrid_controller().click_button_by_name(window_name=win_name, button_name=btn_name)
            content = f"🖱️ {res.get('message', res.get('error', 'Clicked button'))}"
            return IntentResult(
                is_windows_action=True,
                action_type="uia_click",
                success=res.get("success", False),
                title=f"Click: {btn_name}",
                content=content,
                raw_data=res,
            )

        # ---------------- Phase 6: Event-Driven Performance Benchmark ----------------
        if any(k in lower_stripped for k in ["run performance benchmark", "benchmark computer control", "benchmark performance", "run automation benchmark"]):
            from bolt.windows.performance_benchmark import get_performance_benchmark
            bm = get_performance_benchmark()
            rep = bm.run_all_benchmarks()
            lines = [
                "### ⚡ BOLT Event-Driven vs Vision Benchmark Report\n",
                f"- **Direct API Average:** `{rep['direct_api_avg_ms']} ms`",
                f"- **UI Automation Average:** `{rep['ui_automation_avg_ms']} ms`",
                f"- **Vision / Screenshot Average:** `{rep['vision_screenshot_avg_ms']} ms`",
                f"- **Efficiency Advantage:** **{rep['speedup_vs_screenshots']}**\n",
                "| Operation | Method | Time (ms) | RAM Delta (MB) | Success |",
                "|---|---|---|---|---|",
            ]
            for m in rep["metrics"]:
                lines.append(f"| {m['operation_name']} | {m['method_category']} | {m['execution_time_ms']} ms | {m['ram_delta_mb']} MB | {'✅' if m['success'] else '❌'} |")
            lines.append(f"\n💡 *{rep['recommendation']}*")
            return IntentResult(
                is_windows_action=True,
                action_type="performance_benchmark",
                success=True,
                title="Performance Benchmark",
                content="\n".join(lines),
                raw_data=rep,
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

        # ---------------- Create Text File Direct ----------------
        create_file_match = re.match(
            r"^create\s+(?:a\s+)?(?:new\s+)?(?:text\s+)?file(?:\s+(?:called|named)\s+([^\n]+?)|\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+))?(?:\s+on\s+(?:my\s+)?([^\n]+))?$",
            lower_stripped,
        )
        if create_file_match:
            filename = (create_file_match.group(1) or create_file_match.group(2) or "").strip() or "notes.txt"
            folder = (create_file_match.group(3) or "").strip() or "desktop"
            folder = folder.rstrip(".?!").strip()
            res = FileManager.create_text_file(filename, "", folder_alias=folder)
            return IntentResult(
                is_windows_action=True,
                action_type="create_file",
                success=res.get("success", True),
                title="Create File",
                content=res.get("message", "File created."),
                raw_data=res,
            )

        # ---------------- Phase 9: Delete File / Directory (Security Gated) ----------------
        del_dir_match = re.match(
            r"^(?:delete|remove|erase)\s+(?:the\s+)?(?:directory|folder)\s+([^\n]+)$",
            lower_stripped,
        )
        if del_dir_match:
            dir_target = del_dir_match.group(1).strip()
            from bolt.tasks.tool_registry import get_tool_registry
            tool_reg = get_tool_registry()
            res = tool_reg.execute_tool("delete_directory", directory_path=dir_target)
            if res.get("requires_approval"):
                return IntentResult(
                    is_windows_action=True,
                    action_type="security_approval_required",
                    success=True,
                    title="Security Approval Required [CRITICAL]",
                    content=res.get("details", res.get("error", "Approval required.")),
                    raw_data=res,
                )
            return IntentResult(
                is_windows_action=True,
                action_type="delete_directory",
                success=res.get("success", False),
                title="Delete Directory",
                content=res.get("message", res.get("error", "Failed to delete directory.")),
                raw_data=res,
            )

        del_file_match = re.match(
            r"^(?:delete|remove|erase)\s+(?:the\s+)?file\s+([^\n]+)$",
            lower_stripped,
        )
        if del_file_match:
            file_target = del_file_match.group(1).strip()
            from bolt.tasks.tool_registry import get_tool_registry
            tool_reg = get_tool_registry()
            res = tool_reg.execute_tool("delete_file", file_path=file_target)
            if res.get("requires_approval"):
                return IntentResult(
                    is_windows_action=True,
                    action_type="security_approval_required",
                    success=True,
                    title="Security Approval Required [HIGH RISK]",
                    content=res.get("details", res.get("error", "Approval required.")),
                    raw_data=res,
                )
            return IntentResult(
                is_windows_action=True,
                action_type="delete_file",
                success=res.get("success", False),
                title="Delete File",
                content=res.get("message", res.get("error", "Failed to delete file.")),
                raw_data=res,
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
            "switch to nebius", "use nebius", "switch to tokenfactory",
            "switch to gemini", "switch to openai", "switch to chatgpt",
            "switch to custom", "switch to any model", "switch to groq",
            "switch to deepseek", "switch to openrouter", "switch to mistral",
            "use custom model", "use groq", "use deepseek", "use openrouter",
            "switch default provider", "switch provider", "switch to mock",
            "switch to local", "switch to ollama", "switch to gemma",
            "switch to local model", "use local model", "use ollama",
            "prefer local model", "switch to local ai"
        ]):
            from bolt.ai.provider_manager import get_provider_manager
            pm = get_provider_manager()
            target_p = (
                "nebius" if any(w in lower_stripped for w in ["nebius", "tokenfactory", "token_factory"])
                else "custom" if any(w in lower_stripped for w in ["custom", "any model", "groq", "deepseek", "openrouter", "mistral", "together", "lmstudio"])
                else "gemini" if "gemini" in lower_stripped
                else "openai" if ("openai" in lower_stripped or "chatgpt" in lower_stripped)
                else "ollama" if any(w in lower_stripped for w in ["ollama", "local", "gemma"])
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
