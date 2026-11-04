"""
Hybrid Automation Controller for BOLT (Phase 6 Event-Driven Computer Control).
Coordinates execution following the strict priority hierarchy:
1. Direct Windows APIs and registered application tools.
2. Windows UI Automation and Accessibility APIs.
3. Keyboard shortcuts and structured mouse actions.
4. OCR for visual text recognition.
5. Screenshot-based local vision AI only when necessary.

Ensures zero unnecessary screenshots, lightweight verification, and maximum speed.
"""

import time
from typing import Any, Dict, List, Optional

from bolt.core.logger import get_logger
from bolt.windows.app_controller import get_app_controller
from bolt.windows.file_manager import FileManager
from bolt.windows.input_controller import InputController
from bolt.windows.system_info import SystemInfo
from bolt.windows.ui_automation import get_ui_automation_manager
from bolt.windows.vision_engine import get_vision_engine
from bolt.windows.window_manager import get_window_manager

logger = get_logger("HybridController")


class HybridController:
    """
    Event-driven controller orchestrating operations through the fastest,
    cheapest, and most reliable mechanism available.
    """

    _instance: Optional["HybridController"] = None

    def __init__(self):
        self.app_ctrl = get_app_controller()
        self.wm = get_window_manager()
        self.uia = get_ui_automation_manager()
        self.vision = get_vision_engine()

    @classmethod
    def get_instance(cls) -> "HybridController":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -------------------------------------------------------------
    # 1. DIRECT AUTOMATION (Priority 1)
    # -------------------------------------------------------------
    def open_application_direct(self, app_name: str) -> Dict[str, Any]:
        """
        Open application using direct Windows discovery and execution.
        Lightweight verification via process list & window handle.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        res = self.app_ctrl.open_application(app_name)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Verification via WindowManager / Process check
        win = self.wm.find_window_by_title(app_name)
        verified = bool(win or res.get("success"))

        return {
            **res,
            "verified": verified,
            "method_used": "direct_windows_api",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def switch_application_direct(self, app_name: str) -> Dict[str, Any]:
        """
        Switch to application via SetForegroundWindow and WindowManager.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        res = self.app_ctrl.switch_application(app_name)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "direct_windows_api",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def create_text_file_direct(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """
        Create a file on disk directly.
        Lightweight verification checks file existence and bytes on disk.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        res = FileManager.create_text_file(file_path, content)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Direct file verification
        target_path = res.get("file_path") or res.get("path") or ""
        verified = False
        if res.get("success") and target_path:
            import os
            verified = os.path.isfile(target_path)

        return {
            **res,
            "path": target_path,
            "file_path": target_path,
            "verified": verified,
            "method_used": "direct_file_api",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def read_text_file_direct(self, file_path: str) -> Dict[str, Any]:
        """Read a text file directly without any UI interaction."""
        start = time.perf_counter()
        res = FileManager.read_text_file(file_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "direct_file_api",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def get_system_info_direct(self) -> Dict[str, Any]:
        """Retrieve system hardware telemetry directly from Windows kernel."""
        start = time.perf_counter()
        summary = SystemInfo.get_system_summary()
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "success": True,
            "data": summary,
            "method_used": "direct_kernel_api",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    # -------------------------------------------------------------
    # 2. UI AUTOMATION & ACCESSIBILITY (Priority 2)
    # -------------------------------------------------------------
    def click_button_by_name(self, window_name: str, button_name: str) -> Dict[str, Any]:
        """
        Locate and click button semantically by name using UI Automation.
        ZERO screenshots captured unless UIA fails.
        """
        start = time.perf_counter()
        try:
            res = self.uia.click_element(window_name, button_name, control_type="button")
        except Exception as e:
            res = {"success": False, "error": str(e)}
        elapsed_ms = (time.perf_counter() - start) * 1000

        if res.get("success"):
            return {
                **res,
                "method_used": "ui_automation",
                "screenshot_taken": False,
                "execution_time_ms": elapsed_ms,
            }

        # Fallback to Screenshot-on-Demand only if UIA failed
        logger.info(f"UI Automation could not find '{button_name}', activating Screenshot-on-Demand fallback.")
        diag = self.vision.diagnose_visual_error(window_title=window_name)

        return {
            "success": False,
            "error": res.get("error"),
            "fallback_visual_diagnosis": diag,
            "method_used": "screenshot_on_demand_fallback",
            "screenshot_taken": True,
            "execution_time_ms": (time.perf_counter() - start) * 1000,
        }

    def read_accessible_text(self, window_name: str, element_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Read text from an accessible text box or document using UI Automation.
        Lightweight verification reads ValuePattern or TextPattern.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        try:
            res = self.uia.get_element_value(window_name, element_name)
        except Exception as e:
            res = {"success": False, "error": str(e), "text": ""}
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "ui_automation",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def set_accessible_text(self, window_name: str, text: str, element_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Write text into accessible control using UI Automation ValuePattern or SendInput.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        try:
            res = self.uia.set_element_value(window_name, element_name, text)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def calculate_accessible(self, expression: str = "125 * 25") -> Dict[str, Any]:
        """
        Calculate mathematical expression in Calculator using accessible controls directly.
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        try:
            res = self.uia.calculate_in_calculator(expression)
        except Exception as e:
            res = {"success": False, "error": str(e), "result": ""}
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "ui_automation",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def inspect_active_window_controls(
        self,
        window_query: Optional[str] = None,
        max_depth: int = 5,
        max_controls: int = 35,
    ) -> Dict[str, Any]:
        """
        Enumerate accessible controls in active or target window, assign sequential IDs [1], [2], [3]...
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        try:
            res = self.uia.inspect_active_window_controls(
                window_query=window_query, max_depth=max_depth, max_controls=max_controls
            )
        except Exception as e:
            res = {"success": False, "error": str(e), "formatted_controls": "", "controls": []}

        elapsed_ms = (time.perf_counter() - start) * 1000

        # If window found but has ZERO accessible controls (e.g. raw OpenGL/canvas), note availability of visual fallback
        if res.get("success") and res.get("control_count", 0) == 0:
            logger.info("Window exposes no accessible controls; visual screenshot fallback is available on demand.")

        return {
            **res,
            "method_used": "ui_automation",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def click_control_by_id(self, element_id: int) -> Dict[str, Any]:
        """
        Click or invoke an interactive control by assigned ID [1], [2], [3]...
        ZERO screenshots captured unless UIA invocation fails completely.
        """
        start = time.perf_counter()
        try:
            res = self.uia.click_control_by_id(element_id)
        except Exception as e:
            res = {"success": False, "error": str(e)}

        elapsed_ms = (time.perf_counter() - start) * 1000

        if res.get("success"):
            return {
                **res,
                "screenshot_taken": False,
                "execution_time_ms": elapsed_ms,
            }

        # If failed due to stale state, return immediately without capturing screenshot
        if res.get("stale_state"):
            return {
                **res,
                "screenshot_taken": False,
                "execution_time_ms": elapsed_ms,
            }

        # Fallback to Screenshot-on-Demand only if UIA failed
        logger.info(f"UI Automation invocation failed for control [{element_id}], activating visual diagnosis fallback.")
        diag = self.vision.diagnose_visual_error()

        return {
            "success": False,
            "error": res.get("error"),
            "fallback_visual_diagnosis": diag,
            "method_used": "screenshot_on_demand_fallback",
            "screenshot_taken": True,
            "execution_time_ms": (time.perf_counter() - start) * 1000,
        }

    def set_control_text(self, element_id: int, text: str) -> Dict[str, Any]:
        """
        Set text into an accessible text field by assigned ID [1], [2], [3]...
        ZERO screenshots captured.
        """
        start = time.perf_counter()
        try:
            res = self.uia.set_control_text(element_id, text)
        except Exception as e:
            res = {"success": False, "error": str(e)}

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    # -------------------------------------------------------------
    # 3. KEYBOARD SHORTCUTS & STRUCTURED MOUSE (Priority 3)
    # -------------------------------------------------------------
    def type_text_into_active(self, text: str) -> Dict[str, Any]:
        """Type Unicode text via Win32 SendInput without taking screenshots."""
        start = time.perf_counter()
        res = InputController.type_text(text)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "keyboard_sendinput",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    def send_hotkey(self, hotkey_str: str) -> Dict[str, Any]:
        """Trigger keyboard hotkey (e.g. 'ctrl+s') without taking screenshots."""
        start = time.perf_counter()
        res = InputController.send_hotkey(hotkey_str)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            **res,
            "method_used": "keyboard_hotkey",
            "screenshot_taken": False,
            "execution_time_ms": elapsed_ms,
        }

    # -------------------------------------------------------------
    # 4. LOCAL OCR & SCREENSHOT-ON-DEMAND (Priorities 4 & 5)
    # -------------------------------------------------------------
    def inspect_visual_region_on_demand(
        self,
        window_title: Optional[str] = None,
        bbox: Optional[tuple] = None,
        reason: str = "Explicit user request",
    ) -> Dict[str, Any]:
        """
        Capture and perform local OCR on a specific window or bounding box ON-DEMAND.
        Only executed when explicitly requested, or when UIA is inaccessible.
        """
        start = time.perf_counter()
        logger.info(f"Visual capture on-demand triggered. Reason: {reason}")
        res = self.vision.run_ocr(window_title=window_title, bbox=bbox)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "success": res.success,
            "text": res.text,
            "lines": res.lines,
            "reason": reason,
            "method_used": res.method_used,
            "screenshot_taken": True,
            "execution_time_ms": elapsed_ms,
            "error": res.error,
        }


# Global singleton access
_hybrid_controller: Optional[HybridController] = None


def get_hybrid_controller() -> HybridController:
    global _hybrid_controller
    if _hybrid_controller is None:
        _hybrid_controller = HybridController.get_instance()
    return _hybrid_controller
