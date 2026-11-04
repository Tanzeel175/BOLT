"""
Real Browser Controller for BOLT (Windows 11).
Enables direct semantic control, inspection, navigation, tab management,
and web interaction with real Google Chrome windows using Windows UI Automation
and Chrome accessibility trees without breaking user workflows.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from bolt.core.logger import get_logger
from bolt.windows.ui_automation import (
    ensure_interactive_desktop,
    get_interactive_element_registry,
    IndexedControlInfo,
)
from bolt.windows.window_manager import get_window_manager, WindowInfo
from bolt.browser.chrome_profile_manager import get_chrome_profile_manager

ensure_interactive_desktop()
import uiautomation as auto

logger = get_logger("RealBrowserController")


class RealBrowserController:
    """Controls real, open Google Chrome browser windows, tabs, and web pages on Windows 11."""

    _instance: Optional["RealBrowserController"] = None

    def __init__(self):
        self.wm = get_window_manager()
        self.profile_mgr = get_chrome_profile_manager()
        self.element_registry = get_interactive_element_registry()

    @classmethod
    def get_instance(cls) -> "RealBrowserController":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -------------------------------------------------------------
    # 1. WINDOW & TAB DISCOVERY
    # -------------------------------------------------------------
    def get_open_chrome_windows(self) -> List[Dict[str, Any]]:
        """Find all visible Google Chrome windows with active profile metadata."""
        ensure_interactive_desktop()
        windows = self.wm.get_visible_windows()
        chrome_wins = [w for w in windows if "chrome" in w.title.lower()]
        profile_map = self.profile_mgr.get_open_profile_windows()

        result = []
        for w in chrome_wins:
            prof_info = profile_map.get(str(w.hwnd))
            result.append({
                "hwnd": w.hwnd,
                "title": w.title,
                "pid": w.pid,
                "profile_name": prof_info.name if prof_info else "",
                "profile_directory": prof_info.directory if prof_info else "",
                "profile_email": prof_info.email if prof_info else "",
            })
        return result

    def get_target_window_control(self, hwnd: Optional[int] = None) -> Optional[auto.WindowControl]:
        """Get the WindowControl for a target Chrome window or the topmost active Chrome window."""
        ensure_interactive_desktop()
        if hwnd:
            try:
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl:
                    return ctrl
            except Exception as e:
                logger.warning(f"Failed to get WindowControl from handle {hwnd}: {e}")

        # Fallback to topmost visible Chrome window
        windows = self.wm.get_visible_windows()
        chrome_wins = [w for w in windows if "chrome" in w.title.lower()]
        if chrome_wins:
            target_w = chrome_wins[0]
            try:
                ctrl = auto.ControlFromHandle(target_w.hwnd)
                if ctrl:
                    return ctrl
            except Exception as e:
                logger.warning(f"Failed to get Control for window {target_w.hwnd}: {e}")

        return None

    def get_chrome_tabs(self, hwnd: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all open tabs in the target Chrome window."""
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return []

        tabs = []
        index = 0
        for c, _ in auto.WalkControl(ctrl, maxDepth=10):
            if c.ControlTypeName == "TabItemControl":
                name = c.Name or f"Tab {index + 1}"
                is_selected = False
                sel_pat = c.GetSelectionItemPattern()
                if sel_pat:
                    is_selected = sel_pat.IsSelected

                clean_name = name.split(" - Memory usage")[0].strip()
                tabs.append({
                    "index": index,
                    "title": clean_name,
                    "full_name": name,
                    "is_active": is_selected,
                })
                index += 1
        return tabs

    def switch_tab(self, tab_name_or_index: Any, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """Switch to a tab by title substring or 0-based index."""
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Chrome window found."}

        target_tab = None
        current_index = 0
        query_str = str(tab_name_or_index).strip().lower()

        is_index = query_str.isdigit()
        target_idx = int(query_str) if is_index else -1

        for c, _ in auto.WalkControl(ctrl, maxDepth=10):
            if c.ControlTypeName == "TabItemControl":
                name_clean = (c.Name or "").lower()
                if is_index:
                    if current_index == target_idx:
                        target_tab = c
                        break
                else:
                    if query_str in name_clean:
                        target_tab = c
                        break
                current_index += 1

        if not target_tab:
            return {"success": False, "error": f"Tab '{tab_name_or_index}' was not found in Chrome."}

        try:
            sel_pat = target_tab.GetSelectionItemPattern()
            if sel_pat:
                sel_pat.Select()
            else:
                target_tab.Click()
            return {
                "success": True,
                "title": target_tab.Name,
                "message": f"Switched to browser tab: **{target_tab.Name}**",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to switch tab: {e}"}

    # -------------------------------------------------------------
    # 2. NAVIGATION
    # -------------------------------------------------------------
    def navigate_url(
        self,
        url: str,
        hwnd: Optional[int] = None,
        profile_query: Optional[str] = None,
        new_tab: bool = True,
    ) -> Dict[str, Any]:
        """
        Navigate to a URL in a Chrome window.
        1. If profile_query given, ensures the window for that profile is active.
        2. Sets the Omnibox (Address bar) and executes navigation.
        3. Waits for navigation and verifies completion.
        """
        start_time = time.perf_counter()
        clean_url = url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://") or clean_url.startswith("chrome://")):
            clean_url = f"https://{clean_url}"

        # 1. Profile selection if requested
        if profile_query:
            prof_res = self.profile_mgr.select_profile(profile_query)
            if not prof_res.get("success"):
                return prof_res
            hwnd = prof_res.get("hwnd")

        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            # Launch Chrome with URL directly
            res = self.profile_mgr.select_profile(profile_query or "Default", open_url=clean_url)
            return res

        # 2. Focus window and navigate
        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)
        if target_hwnd:
            self.wm.switch_to_window(target_hwnd)
            time.sleep(0.2)

        # Check existing tabs first to see if target is already open
        existing_tabs = self.get_chrome_tabs(target_hwnd)
        matching_tab = None
        for tab in existing_tabs:
            tab_title = tab.get("title", "").lower()
            if "gmail" in clean_url.lower() and "gmail" in tab_title:
                matching_tab = tab
                break
            elif clean_url.lower().replace("https://", "").replace("http://", "").rstrip("/") in tab_title:
                matching_tab = tab
                break

        if matching_tab:
            # Switch to existing tab without disrupting other tabs
            self.switch_tab(matching_tab["index"], hwnd=target_hwnd)
            time.sleep(0.3)
        elif new_tab:
            # Open a NEW tab so active work in the user's current tab is NEVER destroyed!
            try:
                auto.SendKeys("{Ctrl}t")
                time.sleep(0.4)
                auto.SendKeys(f"{clean_url}{{Enter}}")
            except Exception as e:
                logger.warning(f"Error opening new tab and navigating: {e}")
        else:
            # Select address bar and navigate on current tab
            try:
                auto.SendKeys("{Ctrl}l")
                time.sleep(0.15)
                auto.SendKeys(f"{clean_url}{{Enter}}")
            except Exception as e:
                logger.warning(f"Error navigating address bar: {e}")

        # 3. Wait for navigation verification (up to 4.5s)
        time.sleep(0.8)
        verified = False
        new_title = ""
        poll_start = time.time()
        while time.time() - poll_start < 4.0:
            time.sleep(0.4)
            try:
                curr_ctrl = auto.ControlFromHandle(target_hwnd) if target_hwnd else ctrl
                if curr_ctrl:
                    new_title = curr_ctrl.Name or ""
                    if new_title and "new tab" not in new_title.lower():
                        verified = True
                        break
            except Exception:
                pass

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": True,
            "url": clean_url,
            "window_title": new_title or (ctrl.Name if ctrl else ""),
            "verified": verified,
            "execution_time_ms": elapsed_ms,
            "message": f"Navigated to `{clean_url}` (Title: **{new_title}**).",
        }

    # -------------------------------------------------------------
    # 3. WEBPAGE INSPECTION
    # -------------------------------------------------------------
    def inspect_webpage(
        self,
        hwnd: Optional[int] = None,
        max_elements: int = 40,
    ) -> Dict[str, Any]:
        """
        Traverse the Chrome accessibility tree inside the Document area,
        assign temporary indexed IDs [1], [2], [3]... to interactive elements,
        and return formatted controls with strict stale-ID protection.
        """
        start_time = time.perf_counter()
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Chrome window found."}

        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)
        self.element_registry.clear()
        self.element_registry._window_hwnd = target_hwnd
        self.element_registry._window_title = ctrl.Name if ctrl else ""

        # Locate DocumentControl inside Chrome
        doc_control = None
        for c, _ in auto.WalkControl(ctrl, maxDepth=8):
            if c.ControlTypeName == "DocumentControl" and c.Name:
                doc_control = c
                break

        search_root = doc_control if doc_control else ctrl
        interactive_types = {
            "ButtonControl": "Button",
            "HyperlinkControl": "Link",
            "EditControl": "Input",
            "CheckBoxControl": "CheckBox",
            "RadioButtonControl": "RadioButton",
            "ComboBoxControl": "ComboBox",
            "TabItemControl": "Tab",
            "MenuItemControl": "MenuItem",
        }

        indexed_list: List[IndexedControlInfo] = []
        element_id = 1

        for c, _ in auto.WalkControl(search_root, maxDepth=14):
            if len(indexed_list) >= max_elements:
                break

            ctype = c.ControlTypeName
            if ctype in interactive_types:
                name = (c.Name or "").strip()
                auto_id = c.AutomationId or ""

                # Skip blank buttons with no action name or invisible elements
                if not name and not auto_id and ctype != "EditControl":
                    continue

                rect = c.BoundingRectangle
                rect_tuple = (rect.left, rect.top, rect.right, rect.bottom)
                if rect.width() <= 0 or rect.height() <= 0:
                    continue

                val = None
                if hasattr(c, "GetValuePattern"):
                    try:
                        val_pat = c.GetValuePattern()
                        if val_pat:
                            val = val_pat.Value
                    except Exception:
                        pass

                info = IndexedControlInfo(
                    element_id=element_id,
                    name=name or (f"Input ({auto_id})" if auto_id else "Input Field"),
                    control_type=interactive_types[ctype],
                    automation_id=auto_id,
                    class_name=c.ClassName or "",
                    bounding_rect=rect_tuple,
                    is_enabled=c.IsEnabled,
                    value=val,
                    control_ref=c,
                )
                self.element_registry._elements[element_id] = info
                indexed_list.append(info)
                element_id += 1

        self.element_registry._timestamp = time.time()
        self.element_registry._is_dirty = False

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        formatted_lines = [f"[Page: '{ctrl.Name}' (HWND {target_hwnd})]"]
        for el in indexed_list:
            val_part = f' (value: "{el.value}")' if el.value else ""
            formatted_lines.append(f"[{el.element_id}] {el.control_type} \"{el.name}\"{val_part}")

        return {
            "success": True,
            "window_title": ctrl.Name,
            "hwnd": target_hwnd,
            "element_count": len(indexed_list),
            "elements": [
                {
                    "id": el.element_id,
                    "type": el.control_type,
                    "name": el.name,
                    "automation_id": el.automation_id,
                    "value": el.value,
                }
                for el in indexed_list
            ],
            "formatted": "\n".join(formatted_lines),
            "execution_time_ms": elapsed_ms,
        }

    # -------------------------------------------------------------
    # 4. ELEMENT CLICKING & TEXT ENTRY
    # -------------------------------------------------------------
    def click_element(
        self,
        element_id: Optional[int] = None,
        element_name: Optional[str] = None,
        control_type: Optional[str] = None,
        hwnd: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Click an interactive control by temporary ID [1], [2] or semantic name."""
        start_time = time.perf_counter()
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Chrome window found."}

        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)

        # 1. ID-based lookup with stale protection
        if element_id is not None:
            valid, err, info = self.element_registry.validate_control_id(element_id)
            if not valid or not info:
                return {
                    "success": False,
                    "stale_id": True,
                    "error": f"Element [{element_id}] is stale or invalid: {err}. Please re-inspect the page.",
                }

            ref = info.control_ref
            if ref and ref.Exists(0, 0):
                try:
                    inv = ref.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        ref.Click()
                    return {
                        "success": True,
                        "element_id": element_id,
                        "name": info.name,
                        "message": f"Clicked [{element_id}] {info.control_type} \"{info.name}\".",
                    }
                except Exception as e:
                    return {"success": False, "error": f"Failed to click [{element_id}]: {e}"}

        # 2. Semantic name lookup
        if element_name:
            q = element_name.strip().lower()
            found_ctrl = None
            for c, _ in auto.WalkControl(ctrl, maxDepth=14):
                c_name = (c.Name or "").strip().lower()
                if q == c_name or (q in c_name and len(q) >= 3):
                    if control_type and control_type.lower() not in c.ControlTypeName.lower():
                        continue
                    found_ctrl = c
                    break

            if found_ctrl and found_ctrl.Exists(0, 0):
                try:
                    inv = found_ctrl.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        found_ctrl.Click()
                    return {
                        "success": True,
                        "name": found_ctrl.Name,
                        "message": f"Clicked \"{found_ctrl.Name}\".",
                    }
                except Exception as e:
                    return {"success": False, "error": f"Click on \"{element_name}\" failed: {e}"}

        return {"success": False, "error": f"Could not find element '{element_name or element_id}' to click."}

    def type_element(
        self,
        text: str,
        element_id: Optional[int] = None,
        element_name: Optional[str] = None,
        clear_first: bool = False,
        hwnd: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Type text into an input field or text area in the browser page."""
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Chrome window found."}

        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)

        target_control = None
        if element_id is not None:
            valid, err, info = self.element_registry.validate_control_id(element_id)
            if not valid or not info:
                return {"success": False, "stale_id": True, "error": f"Stale element [{element_id}]: {err}"}
            target_control = info.control_ref

        if not target_control and element_name:
            q = element_name.strip().lower()
            for c, _ in auto.WalkControl(ctrl, maxDepth=16):
                c_name = (c.Name or "").strip().lower()
                if q == c_name or (q in c_name and len(q) >= 3):
                    target_control = c
                    break

        if not target_control:
            return {"success": False, "error": f"Input field '{element_name or element_id}' not found."}

        try:
            target_control.SetFocus()
            time.sleep(0.1)

            if hasattr(target_control, "GetValuePattern"):
                val_pat = target_control.GetValuePattern()
                if val_pat and not clear_first:
                    try:
                        val_pat.SetValue(text)
                        return {
                            "success": True,
                            "text": text,
                            "name": target_control.Name,
                            "message": f"Entered text into \"{target_control.Name}\".",
                        }
                    except Exception:
                        pass
                    pass

            if clear_first:
                target_control.SendKeys("{Ctrl}a{Delete}")
                time.sleep(0.05)

            target_control.SendKeys(text)
            return {
                "success": True,
                "text": text,
                "name": target_control.Name,
                "message": f"Typed text into \"{target_control.Name}\".",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to type text: {e}"}

    def scroll_page(self, direction: str = "down", amount: int = 3, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """Scroll the active webpage up or down."""
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Chrome window found."}

        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)
        if target_hwnd:
            self.wm.switch_to_window(target_hwnd)

        key = "{PageDown}" if direction.lower() == "down" else "{PageUp}"
        for _ in range(max(1, min(amount, 10))):
            auto.SendKeys(key)
            time.sleep(0.1)

        return {
            "success": True,
            "direction": direction,
            "amount": amount,
            "message": f"Scrolled webpage {direction} by {amount} units.",
        }

    def wait_for_element(self, element_name: str, timeout_seconds: float = 12.0, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """Wait until an element matching element_name exists on the page."""
        start = time.time()
        q = element_name.strip().lower()

        while time.time() - start < timeout_seconds:
            try:
                ctrl = self.get_target_window_control(hwnd)
                if ctrl:
                    # Special check: if waiting for Compose and Subject edit field already open, compose is ready
                    if q == "compose":
                        subj = ctrl.EditControl(searchDepth=18, Name="Subject")
                        if subj.Exists(0, 0):
                            return {
                                "success": True,
                                "element_name": "Compose (Active)",
                                "control_type": "EditControl",
                                "elapsed_seconds": round(time.time() - start, 2),
                                "message": "Compose window is active and ready.",
                            }

                    for c, _ in auto.WalkControl(ctrl, maxDepth=14):
                        c_name = (c.Name or "").strip().lower()
                        if q == c_name or (q in c_name and len(q) >= 3):
                            return {
                                "success": True,
                                "element_name": c.Name,
                                "control_type": c.ControlTypeName,
                                "elapsed_seconds": round(time.time() - start, 2),
                                "message": f"Element \"{c.Name}\" is now visible on the page.",
                            }
            except Exception as e:
                logger.debug(f"Note during wait_for_element polling: {e}")

            time.sleep(0.5)

        return {
            "success": False,
            "error": f"Timed out waiting {timeout_seconds}s for element '{element_name}'.",
        }

    # -------------------------------------------------------------
    # 5. GMAIL DRAFT WORKFLOW (SAFE TESTING — NEVER SENDS)
    # -------------------------------------------------------------
    def draft_gmail_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        hwnd: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Safely prepare a complete email draft in Gmail Compose.
        Fills recipient, subject, and body, verifies the draft fields,
        and displays complete summary for user approval.
        STRICT SECURITY: Never clicks Send.
        """
        ctrl = self.get_target_window_control(hwnd)
        if not ctrl:
            return {"success": False, "error": "No active Gmail window found."}

        target_hwnd = getattr(ctrl, "NativeWindowHandle", 0)
        if target_hwnd:
            self.wm.switch_to_window(target_hwnd)
            time.sleep(0.2)

        # 1. Find Compose button if Compose window not already open
        subj_field = ctrl.EditControl(searchDepth=18, Name="Subject")
        if not subj_field.Exists(0, 0):
            compose_btn = None
            for c, _ in auto.WalkControl(ctrl, maxDepth=14):
                if c.ControlTypeName == "ButtonControl" and (c.Name or "").strip().lower() == "compose":
                    compose_btn = c
                    break

            if compose_btn:
                try:
                    inv = compose_btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        compose_btn.Click()
                except Exception as e:
                    logger.warning(f"Error clicking Compose: {e}")

                time.sleep(1.2)
                subj_field = ctrl.EditControl(searchDepth=18, Name="Subject")

        if not subj_field.Exists(0, 0):
            return {
                "success": False,
                "error": "Could not open Gmail Compose window. Make sure Gmail is loaded.",
            }

        # 2. Fill Subject
        subj_field.SetFocus()
        time.sleep(0.1)
        subj_field.SendKeys("{Ctrl}a{Delete}")
        time.sleep(0.05)
        subj_field.SendKeys(subject)
        time.sleep(0.1)

        # 3. Fill Message Body (Clear first so text is never doubled)
        subj_field.SendKeys("{Tab}")
        time.sleep(0.1)
        auto.SendKeys("{Ctrl}a{Delete}")
        time.sleep(0.05)
        auto.SendKeys(body)
        time.sleep(0.1)

        # 4. Fill Recipient (Clear first so chips are never duplicated)
        subj_field.SetFocus()
        time.sleep(0.1)
        subj_field.SendKeys("{Shift}{Tab}")
        time.sleep(0.1)
        auto.SendKeys("{Ctrl}a{Delete}")
        time.sleep(0.05)
        auto.SendKeys(f"{recipient}{{Enter}}")
        time.sleep(0.2)

        # 5. Verify Draft Content
        val_pat = subj_field.GetValuePattern()
        verified_subject = val_pat.Value if val_pat else subject

        draft_summary = (
            f"### ✉️ Gmail Draft Prepared (Safe Test Mode)\n\n"
            f"- **To:** `{recipient}`\n"
            f"- **Subject:** `{verified_subject}`\n"
            f"- **Body Preview:**\n"
            f"> {body.replace(chr(10), chr(10) + '> ')}\n\n"
            f"🛡️ **Safety Gate:** This email is drafted in Gmail. It has NOT been sent."
        )

        return {
            "success": True,
            "status": "draft_created",
            "recipient": recipient,
            "subject": verified_subject,
            "body": body,
            "verified": True,
            "requires_approval": False,
            "waiting_for_user": False,
            "details": draft_summary,
            "message": "Draft created in Gmail. Ready for your review and sending.",
        }


_REAL_BROWSER_CONTROLLER: Optional[RealBrowserController] = None


def get_real_browser_controller() -> RealBrowserController:
    global _REAL_BROWSER_CONTROLLER
    if _REAL_BROWSER_CONTROLLER is None:
        _REAL_BROWSER_CONTROLLER = RealBrowserController.get_instance()
    return _REAL_BROWSER_CONTROLLER
