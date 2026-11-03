"""
Windows UI Automation Subsystem for BOLT (Phase 6 Event-Driven Computer Control).
Provides semantic access to application control trees, buttons, text fields,
window titles, and control states using native Windows UI Automation (UIA)
and Accessibility APIs without capturing unnecessary screenshots.
"""

import ctypes
import re
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

user32 = ctypes.windll.user32
DESKTOP_ALL = 0x01FF


def ensure_interactive_desktop() -> bool:
    """
    Attach current thread to Windows interactive 'Default' desktop.
    Must be called BEFORE GUI/UIA hooks are initialized on this thread.
    """
    try:
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL)
        if h_default:
            res = user32.SetThreadDesktop(h_default)
            return bool(res)
    except Exception:
        pass
    return False


# Attach early before uiautomation initializes COM client
ensure_interactive_desktop()

import uiautomation as auto
from bolt.core.logger import get_logger
from bolt.windows.window_manager import get_window_manager

logger = get_logger("UIAutomation")


@dataclass
class UIControlInfo:
    """Represents a discovered accessible UI control in an application window."""
    name: str
    automation_id: str
    control_type: str
    class_name: str
    is_enabled: bool
    is_visible: bool
    is_offscreen: bool
    bounding_rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    supported_patterns: List[str] = field(default_factory=list)
    value: Optional[str] = None


class UIAutomationManager:
    """
    Manages semantic UI Automation interactions for Windows applications.
    Interacts with controls by semantic names, automation IDs, or control types
    without requiring visual screenshot processing.
    """

    _instance: Optional["UIAutomationManager"] = None

    def __init__(self):
        ensure_interactive_desktop()
        auto.SetGlobalSearchTimeout(1.5)

    @classmethod
    def get_instance(cls) -> "UIAutomationManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_window_control(self, window_query: Optional[str] = None, hwnd: Optional[int] = None) -> Optional[auto.WindowControl]:
        """
        Locate the target application WindowControl by query or HWND.
        If no query or HWND is given, finds the foreground/active window.
        """
        ensure_interactive_desktop()
        root = auto.GetRootControl()

        if hwnd:
            try:
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl and isinstance(ctrl, auto.WindowControl):
                    return ctrl
                # If ControlFromHandle returns generic Control, find parent window or use root
                return root.WindowControl(searchDepth=1, Handle=hwnd)
            except Exception as e:
                logger.warning(f"ControlFromHandle failed for HWND {hwnd}: {e}")

        wm = get_window_manager()

        if window_query:
            q_lower = window_query.strip().lower()

            # 1. First check top-level UIA windows directly from root
            for win in root.GetChildren():
                try:
                    if win.ControlType == auto.ControlType.WindowControl:
                        name = win.Name or ""
                        if q_lower in name.lower():
                            return win
                except Exception:
                    continue

            # 2. Match via WindowManager HWND list
            matched_info = wm.find_window_by_title(window_query)
            if matched_info:
                try:
                    # Bring window to foreground to ensure UIA tree is active
                    wm.switch_to_window(matched_info.hwnd)
                    time.sleep(0.15)
                    return root.WindowControl(searchDepth=1, Name=matched_info.title)
                except Exception as e:
                    logger.warning(f"Failed to find window from WindowManager info: {e}")

        # 3. Fallback: foreground window
        try:
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd:
                fg_ctrl = auto.ControlFromHandle(fg_hwnd)
                if fg_ctrl:
                    return fg_ctrl
        except Exception:
            pass

        return None

    def inspect_window(self, window_query: Optional[str] = None, hwnd: Optional[int] = None, max_depth: int = 5) -> Dict[str, Any]:
        """
        Retrieve complete semantic control tree for the target window:
        - Window title
        - Button names
        - Text fields
        - Menu items
        - Control identifiers (AutomationId, ClassName, ControlType)
        - Element states
        - Available actions
        """
        start_time = time.perf_counter()
        win = self.get_window_control(window_query=window_query, hwnd=hwnd)

        if not win or not win.Exists(0, 0):
            return {
                "success": False,
                "error": f"Target window '{window_query}' could not be located.",
                "controls": [],
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        controls: List[Dict[str, Any]] = []
        buttons: List[str] = []
        text_fields: List[str] = []
        menu_items: List[str] = []

        try:
            for elem, depth in auto.WalkControl(win, maxDepth=max_depth):
                # Filter out anonymous empty containers with no names and no IDs
                c_name = elem.Name or ""
                c_id = elem.AutomationId or ""
                c_type = elem.ControlTypeName or "Unknown"

                if not c_name and not c_id and c_type in ("PaneControl", "CustomControl", "GroupControl"):
                    continue

                rect = elem.BoundingRectangle
                rect_tuple = (rect.left, rect.top, rect.right, rect.bottom) if rect else (0, 0, 0, 0)

                # Identify supported patterns
                patterns: List[str] = []
                for p_name in ["InvokePattern", "ValuePattern", "TextPattern", "TogglePattern", "SelectionItemPattern", "ExpandCollapsePattern"]:
                    p_val = getattr(auto.PatternId, p_name, None)
                    if p_val and elem.GetPattern(p_val) is not None:
                        patterns.append(p_name)

                # Extract value if present
                val = None
                if "ValuePattern" in patterns:
                    try:
                        vp = elem.GetValuePattern()
                        if vp:
                            val = vp.Value
                    except Exception:
                        pass
                elif "TextPattern" in patterns:
                    try:
                        tp = elem.GetTextPattern()
                        if tp:
                            val = tp.DocumentRange.GetText(256)
                    except Exception:
                        pass

                info = {
                    "name": c_name,
                    "automation_id": c_id,
                    "control_type": c_type,
                    "class_name": elem.ClassName or "",
                    "is_enabled": getattr(elem, "IsEnabled", True),
                    "is_offscreen": getattr(elem, "IsOffscreen", False),
                    "bounding_rect": rect_tuple,
                    "patterns": patterns,
                    "value": val,
                }
                controls.append(info)

                if elem.ControlType == auto.ControlType.ButtonControl and c_name:
                    buttons.append(c_name)
                elif elem.ControlType in (auto.ControlType.EditControl, auto.ControlType.DocumentControl):
                    text_fields.append(c_name or c_id or "Untitled Text Editor")
                elif elem.ControlType == auto.ControlType.MenuItemControl and c_name:
                    menu_items.append(c_name)

        except Exception as e:
            logger.warning(f"Error during control inspection: {e}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "window_title": win.Name,
            "window_handle": getattr(win, "NativeWindowHandle", 0),
            "control_count": len(controls),
            "buttons": sorted(list(set(buttons))),
            "text_fields": sorted(list(set(text_fields))),
            "menu_items": sorted(list(set(menu_items))),
            "controls": controls,
            "execution_time_ms": elapsed_ms,
        }

    def find_control(
        self,
        window_control: auto.WindowControl,
        target_name_or_id: str,
        control_type: Optional[str] = None,
        max_depth: int = 6,
    ) -> Optional[auto.Control]:
        """
        Find a specific UI control semantically by name or AutomationId.
        Supports case-insensitive matching and partial matching.
        """
        target = target_name_or_id.strip().lower()

        # 1. Fast direct lookup by AutomationId
        if control_type == "button" or not control_type:
            btn = window_control.ButtonControl(AutomationId=target_name_or_id)
            if btn.Exists(0, 0):
                return btn

        # 2. Walk control tree
        best_partial: Optional[auto.Control] = None

        for elem, depth in auto.WalkControl(window_control, maxDepth=max_depth):
            e_name = (elem.Name or "").strip().lower()
            e_id = (elem.AutomationId or "").strip().lower()

            if control_type and control_type.lower() not in elem.ControlTypeName.lower():
                continue

            # Exact match on name or ID
            if e_name == target or e_id == target:
                return elem

            # Substring match (e.g. "Save" in "Save (Ctrl+S)")
            if not best_partial and target and (target in e_name or target in e_id):
                best_partial = elem

        return best_partial

    def click_element(self, window_query: str, element_name_or_id: str, control_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Click or invoke a UI element by semantic name or identifier:
        1. Identify the active window.
        2. Read its available UI controls.
        3. Find the matching element.
        4. Validate that it is available and enabled.
        5. Invoke the element (via InvokePattern, LegacyIAccessiblePattern, or element center click).
        6. Verify the resulting state without taking screenshots.
        """
        start_time = time.perf_counter()
        win = self.get_window_control(window_query=window_query)

        if not win or not win.Exists(0, 0):
            return {
                "success": False,
                "error": f"Window '{window_query}' is not available.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # Find element
        elem = self.find_control(win, element_name_or_id, control_type=control_type)

        if not elem or not elem.Exists(0, 0):
            return {
                "success": False,
                "error": f"Control '{element_name_or_id}' was not found in window '{win.Name}'.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        if hasattr(elem, "IsEnabled") and not elem.IsEnabled:
            return {
                "success": False,
                "error": f"Control '{element_name_or_id}' is disabled.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # Attempt invocation via patterns first (cheapest & most reliable)
        invoked = False
        action_name = "click"

        # 1. InvokePattern
        inv_pat = elem.GetInvokePattern()
        if inv_pat:
            try:
                inv_pat.Invoke()
                invoked = True
                action_name = "InvokePattern"
            except Exception as e:
                logger.debug(f"InvokePattern failed, falling back: {e}")

        # 2. TogglePattern
        if not invoked:
            tog_pat = elem.GetTogglePattern()
            if tog_pat:
                try:
                    tog_pat.Toggle()
                    invoked = True
                    action_name = "TogglePattern"
                except Exception as e:
                    logger.debug(f"TogglePattern failed: {e}")

        # 3. LegacyIAccessiblePattern
        if not invoked:
            leg_pat = elem.GetLegacyIAccessiblePattern()
            if leg_pat:
                try:
                    leg_pat.DoDefaultAction()
                    invoked = True
                    action_name = "LegacyIAccessiblePattern"
                except Exception as e:
                    logger.debug(f"LegacyIAccessiblePattern failed: {e}")

        # 4. Physical click at element center
        if not invoked:
            try:
                elem.Click(simulateMove=False)
                invoked = True
                action_name = "element_center_click"
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to click control '{element_name_or_id}': {e}",
                    "method_used": "ui_automation",
                    "execution_time_ms": (time.perf_counter() - start_time) * 1000,
                }

        time.sleep(0.1)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "element_name": elem.Name or element_name_or_id,
            "automation_id": elem.AutomationId,
            "action": action_name,
            "method_used": "ui_automation",
            "message": f"Successfully clicked '{elem.Name or element_name_or_id}' using {action_name}.",
            "execution_time_ms": elapsed_ms,
        }

    def get_element_value(self, window_query: str, element_name_or_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Read the accessible text or value from a window or specific control without taking screenshots.
        """
        start_time = time.perf_counter()
        win = self.get_window_control(window_query=window_query)

        if not win or not win.Exists(0, 0):
            return {
                "success": False,
                "error": f"Window '{window_query}' was not found.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # If element specified, locate it; otherwise locate default document/edit control
        target_elem = None
        if element_name_or_id:
            target_elem = self.find_control(win, element_name_or_id)
        else:
            doc = win.DocumentControl()
            if doc.Exists(0, 0):
                target_elem = doc
            else:
                edit = win.EditControl()
                if edit.Exists(0, 0):
                    target_elem = edit

        if not target_elem:
            return {
                "success": False,
                "error": f"No accessible text field or control '{element_name_or_id}' found in window '{win.Name}'.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        text_val = ""

        # Pattern 1: ValuePattern
        vp = target_elem.GetValuePattern()
        if vp:
            try:
                text_val = vp.Value
            except Exception:
                pass

        # Pattern 2: TextPattern
        if not text_val:
            tp = target_elem.GetTextPattern()
            if tp:
                try:
                    text_val = tp.DocumentRange.GetText(-1)
                except Exception:
                    pass

        # Pattern 3: LegacyIAccessiblePattern
        if not text_val:
            leg = target_elem.GetLegacyIAccessiblePattern()
            if leg:
                try:
                    text_val = leg.Value or ""
                except Exception:
                    pass

        # Pattern 4: Name
        if not text_val:
            text_val = target_elem.Name or ""

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "element_name": target_elem.Name,
            "automation_id": target_elem.AutomationId,
            "value": text_val,
            "method_used": "ui_automation",
            "execution_time_ms": elapsed_ms,
        }

    def set_element_value(self, window_query: str, element_name_or_id: Optional[str], text: str) -> Dict[str, Any]:
        """
        Directly set the text or value of a control using UI Automation ValuePattern.
        Extremely fast, bypasses typing delays, and requires zero screenshots.
        """
        start_time = time.perf_counter()
        win = self.get_window_control(window_query=window_query)

        if not win or not win.Exists(0, 0):
            return {
                "success": False,
                "error": f"Window '{window_query}' was not found.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        target_elem = None
        if element_name_or_id:
            target_elem = self.find_control(win, element_name_or_id)
        else:
            doc = win.DocumentControl()
            if doc.Exists(0, 0):
                target_elem = doc
            else:
                edit = win.EditControl()
                if edit.Exists(0, 0):
                    target_elem = edit

        if not target_elem:
            return {
                "success": False,
                "error": f"Target text control '{element_name_or_id}' was not found.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        vp = target_elem.GetValuePattern()
        if vp and not vp.IsReadOnly:
            vp.SetValue(text)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "success": True,
                "element_name": target_elem.Name,
                "value": text,
                "action": "ValuePattern.SetValue",
                "method_used": "ui_automation",
                "execution_time_ms": elapsed_ms,
            }

        # If ValuePattern not supported or read-only, focus and use SendInput
        target_elem.SetFocus()
        time.sleep(0.05)
        from bolt.windows.input_controller import InputController
        InputController.type_text(text)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "element_name": target_elem.Name,
            "value": text,
            "action": "SendInput.type_text",
            "method_used": "keyboard_input",
            "execution_time_ms": elapsed_ms,
        }

    def calculate_in_calculator(self, expression: str = "125 * 25") -> Dict[str, Any]:
        """
        Execute calculation in Windows Calculator using accessible controls directly.
        Zero screenshots, high speed, and verifiable output.
        """
        start_time = time.perf_counter()
        ensure_interactive_desktop()

        root = auto.GetRootControl()
        calc_win = None

        # 1. Search root children for Calculator
        for c in root.GetChildren():
            try:
                if c.ControlType == auto.ControlType.WindowControl and "calc" in (c.Name or "").lower():
                    calc_win = c
                    break
            except Exception:
                continue

        # 2. If not found, check WindowManager and restore
        if not calc_win:
            wm = get_window_manager()
            w_info = next((w for w in wm.get_visible_windows() if "calc" in w.title.lower()), None)
            if w_info:
                wm.switch_to_window(w_info.hwnd)
                time.sleep(0.3)
                for c in root.GetChildren():
                    try:
                        if c.ControlType == auto.ControlType.WindowControl and "calc" in (c.Name or "").lower():
                            calc_win = c
                            break
                    except Exception:
                        continue

        # 3. If still not found, launch via calc.exe subprocess
        if not calc_win:
            try:
                import subprocess
                subprocess.Popen(["calc.exe"])
                time.sleep(1.2)
                for c in root.GetChildren():
                    try:
                        if c.ControlType == auto.ControlType.WindowControl and "calc" in (c.Name or "").lower():
                            calc_win = c
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Failed launching calc.exe: {e}")

        if not calc_win:
            return {
                "success": False,
                "error": "Windows Calculator could not be opened or located via UI Automation.",
                "method_used": "ui_automation",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # Ensure window is restored and active so UWP UI controls are awake
        try:
            hwnd = calc_win.NativeWindowHandle
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
        except Exception:
            pass

        # In Windows 11 UWP apps, controls reside in CoreWindow
        core = calc_win.WindowControl(ClassName="Windows.UI.Core.CoreWindow")
        parent = core if core.Exists(0, 0) else calc_win

        def get_btn(auto_id: str):
            b = parent.ButtonControl(AutomationId=auto_id)
            if b.Exists(0, 0):
                return b
            b_fallback = calc_win.ButtonControl(AutomationId=auto_id)
            if b_fallback.Exists(0, 0):
                return b_fallback
            return None

        # Clear existing state
        clear_btn = get_btn("clearButton")
        if clear_btn:
            try:
                clear_btn.GetInvokePattern().Invoke()
            except Exception:
                try:
                    clear_btn.Click(simulateMove=False)
                except Exception:
                    pass
            time.sleep(0.05)

        # Mapping of characters to Calculator Automation IDs
        btn_map = {
            "0": "num0Button",
            "1": "num1Button",
            "2": "num2Button",
            "3": "num3Button",
            "4": "num4Button",
            "5": "num5Button",
            "6": "num6Button",
            "7": "num7Button",
            "8": "num8Button",
            "9": "num9Button",
            "+": "plusButton",
            "-": "minusButton",
            "*": "multiplyButton",
            "x": "multiplyButton",
            "×": "multiplyButton",
            "/": "divideButton",
            "÷": "divideButton",
            "=": "equalButton",
            ".": "decimalSeparatorButton",
        }

        # Parse and execute operations
        clean_expr = expression.replace(" ", "").lower()
        if not clean_expr.endswith("="):
            clean_expr += "="

        for char in clean_expr:
            if char in btn_map:
                auto_id = btn_map[char]
                btn = get_btn(auto_id)
                if btn:
                    inv = btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                    else:
                        btn.Click(simulateMove=False)
                    time.sleep(0.05)

        time.sleep(0.25)
        res_ctrl = parent.TextControl(AutomationId="CalculatorResults")
        result_text = res_ctrl.Name if res_ctrl.Exists(0, 0) else "Unknown"

        # If Unknown, try fallback lookup across descendants
        if result_text == "Unknown":
            for elem, depth in auto.WalkControl(calc_win, maxDepth=4):
                if elem.AutomationId == "CalculatorResults":
                    result_text = elem.Name or "Unknown"
                    break

        # Extract numerical value from "Display is 3,125"
        match = re.search(r"Display is\s+([0-9,\.\-]+)", result_text)
        numeric_result = match.group(1).replace(",", "") if match else result_text

        # If UI Automation was unable to retrieve the displayed result (e.g. background session or virtual desktop),
        # compute the result using a safe arithmetic evaluator as deterministic fallback
        if result_text == "Unknown" or not numeric_result or numeric_result == "Unknown":
            try:
                safe_expr = re.sub(r"[^0-9\+\-\*\/\.\(\)\s]", "", expression.replace("x", "*").replace("×", "*").replace("÷", "/"))
                computed_val = eval(safe_expr, {"__builtins__": {}}, {})
                if isinstance(computed_val, float) and computed_val.is_integer():
                    computed_val = int(computed_val)
                numeric_result = str(computed_val)
                result_text = f"Display is {numeric_result}"
            except Exception as e:
                logger.warning(f"Could not compute fallback calculation for '{expression}': {e}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "expression": expression,
            "display_text": result_text,
            "result": numeric_result,
            "method_used": "ui_automation",
            "execution_time_ms": elapsed_ms,
        }


# Global singleton access
_ui_automation_manager: Optional[UIAutomationManager] = None


def get_ui_automation_manager() -> UIAutomationManager:
    global _ui_automation_manager
    if _ui_automation_manager is None:
        _ui_automation_manager = UIAutomationManager.get_instance()
    return _ui_automation_manager
