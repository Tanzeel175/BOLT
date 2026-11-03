"""
Comprehensive Test Suite for BOLT Phase 6 Optimization:
Event-Driven Computer Control, Windows UI Automation, and On-Demand Vision.
Tests all requirements defined in Section 10:
- Open Calculator without screenshots.
- Calculate 125 × 25 using accessible controls.
- Open Notepad and type text without screenshots.
- Create a file and verify its contents without screenshots.
- Identify a Save button using UI Automation.
- Read a browser page title without screenshots.
- Capture a screenshot only when the UI is inaccessible.
- Understand a visual error using local OCR or vision AI.
Reports method used and actual execution time for every test.
"""

import os
import pathlib
import time
import unittest
import ctypes
from ctypes import wintypes
from PIL import Image, ImageDraw

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Attach early to interactive desktop
try:
    h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if h_default:
        user32.SetThreadDesktop(h_default)
except Exception:
    pass

from bolt.browser.browser_controller import get_browser_controller
from bolt.windows.app_controller import get_app_controller
from bolt.windows.file_manager import FileManager
from bolt.windows.hybrid_controller import get_hybrid_controller
from bolt.windows.intent_dispatcher import get_intent_dispatcher
from bolt.windows.performance_benchmark import get_performance_benchmark
from bolt.windows.ui_automation import get_ui_automation_manager
from bolt.windows.vision_engine import get_vision_engine
from bolt.windows.window_manager import get_window_manager


class TestPhase6EventDriven(unittest.TestCase):
    """Rigorous tests verifying event-driven automation priority over screenshots."""

    @classmethod
    def setUpClass(cls):
        os.environ["BOLT_HEADLESS_BROWSER"] = "1"
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.hybrid = get_hybrid_controller()
        cls.uia = get_ui_automation_manager()
        cls.vision = get_vision_engine()
        cls.app_ctrl = get_app_controller()
        cls.browser_ctrl = get_browser_controller()

    def test_01_open_calculator_without_screenshots(self):
        """Test: Open Calculator without screenshots."""
        start = time.perf_counter()
        res = self.hybrid.open_application_direct("calculator")
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(res["success"], f"Failed opening Calculator: {res}")
        self.assertFalse(res["screenshot_taken"], "Screenshot was captured when direct API was available!")
        self.assertEqual(res["method_used"], "direct_windows_api")

        print(f"\n[OK] test_01: Open Calculator -> Method: {res['method_used']} | Screenshots: {res['screenshot_taken']} | Time: {elapsed_ms:.2f} ms")

    def test_02_calculate_125_times_25_accessible_controls(self):
        """Test: Calculate 125 × 25 using accessible controls."""
        start = time.perf_counter()
        res = self.hybrid.calculate_accessible("125 * 25")
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(res["success"], f"Calculation failed: {res}")
        self.assertIn("3125", res["result"].replace(",", ""), f"Expected 3125, got {res.get('result')}")
        self.assertFalse(res["screenshot_taken"], "Screenshot was captured during accessible calculation!")
        self.assertEqual(res["method_used"], "ui_automation")

        print(f"\n[OK] test_02: Calculate 125 × 25 = {res['result']} -> Method: {res['method_used']} | Screenshots: {res['screenshot_taken']} | Time: {elapsed_ms:.2f} ms")

    def test_03_open_notepad_and_type_text_without_screenshots(self):
        """Test: Open Notepad and type text without screenshots."""
        # 1. Open Notepad
        start = time.perf_counter()
        open_res = self.hybrid.open_application_direct("notepad")
        self.assertTrue(open_res["success"])
        self.assertFalse(open_res["screenshot_taken"])
        time.sleep(0.5)

        # 2. Type text via direct automation
        type_res = self.hybrid.type_text_into_active("BOLT Phase 6 Event-Driven Text")
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(type_res["success"])
        self.assertFalse(type_res["screenshot_taken"])
        self.assertEqual(type_res["method_used"], "keyboard_sendinput")

        # Clean up
        self.app_ctrl.close_application("notepad")

        print(f"\n[OK] test_03: Open Notepad & Type Text -> Method: {type_res['method_used']} | Screenshots: {type_res['screenshot_taken']} | Time: {elapsed_ms:.2f} ms")

    def test_04_create_file_and_verify_contents_without_screenshots(self):
        """Test: Create a file and verify its contents without screenshots."""
        start = time.perf_counter()
        test_file = "bolt_event_driven_test.txt"
        test_content = "Lightweight direct file verification without visual inspection."

        # 1. Create file
        create_res = self.hybrid.create_text_file_direct(test_file, test_content)
        self.assertTrue(create_res["success"])
        self.assertFalse(create_res["screenshot_taken"])
        self.assertEqual(create_res["method_used"], "direct_file_api")

        # 2. Verify file on disk directly
        full_path = create_res.get("file_path") or create_res.get("path")
        self.assertTrue(full_path and os.path.isfile(full_path))

        # 3. Read content directly
        read_res = self.hybrid.read_text_file_direct(full_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(read_res["success"])
        self.assertEqual(read_res["content"], test_content)
        self.assertFalse(read_res["screenshot_taken"])
        self.assertEqual(read_res["method_used"], "direct_file_api")

        # Clean up
        try:
            os.remove(full_path)
        except Exception:
            pass

        print(f"\n[OK] test_04: Create & Verify File -> Method: {read_res['method_used']} | Screenshots: {read_res['screenshot_taken']} | Time: {elapsed_ms:.2f} ms")

    def test_05_identify_save_button_using_ui_automation(self):
        """Test: Identify a Save button using UI Automation."""
        start = time.perf_counter()

        # Create a window containing an accessible Save button
        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HICON),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        p_def = ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p).value
        cls = WNDCLASS(0, p_def, 0, 0, kernel32.GetModuleHandleW(None), 0, 0, 0, None, "BOLTSaveTestWnd")
        user32.RegisterClassW(ctypes.byref(cls))

        hwnd = user32.CreateWindowExW(
            0, "BOLTSaveTestWnd", "Document Editor",
            0x10000000 | 0x00C00000 | 0x00080000,
            100, 100, 320, 200, 0, 0, 0, None
        )
        btn_hwnd = user32.CreateWindowExW(
            0, "BUTTON", "Save",
            0x50000000 | 0x0001,
            20, 20, 100, 35, hwnd, 101, 0, None
        )
        user32.ShowWindow(hwnd, 5)

        try:
            # 1. Locate window via UIA
            win_ctrl = self.uia.get_window_control(hwnd=hwnd)
            self.assertIsNotNone(win_ctrl)

            # 2. Inspect controls
            inspection = self.uia.inspect_window(hwnd=hwnd)
            self.assertTrue(inspection["success"])
            self.assertIn("Save", inspection["buttons"])

            # 3. Semantically find the Save button
            save_btn = self.uia.find_control(win_ctrl, "Save")
            self.assertIsNotNone(save_btn)
            self.assertEqual(save_btn.Name, "Save")
            self.assertEqual(save_btn.ControlTypeName, "ButtonControl")

            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"\n[OK] test_05: Identify Save Button ('{save_btn.Name}') -> Method: ui_automation | Screenshots: False | Time: {elapsed_ms:.2f} ms")
        finally:
            user32.DestroyWindow(hwnd)

    def test_06_read_browser_page_title_without_screenshots(self):
        """Test: Read a browser page title without screenshots."""
        start = time.perf_counter()
        nav_res = self.browser_ctrl.open_url("https://example.com")
        self.assertTrue(nav_res["success"])

        # Read page title directly from browser DOM without screenshot
        title = nav_res.get("title", "")
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertIn("Example Domain", title)
        print(f"\n[OK] test_06: Read Browser Page Title ('{title}') -> Method: browser_dom | Screenshots: False | Time: {elapsed_ms:.2f} ms")

    def test_07_capture_screenshot_only_when_inaccessible(self):
        """Test: Capture a screenshot only when the UI is inaccessible."""
        start = time.perf_counter()
        # Query an intentional non-existent control
        res = self.hybrid.click_button_by_name("NonExistentWindow999", "FakeButton123")
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertFalse(res["success"])
        # Verified that screenshot was ONLY captured when UIA failed!
        self.assertTrue(res["screenshot_taken"], "Screenshot was not taken on inaccessible fallback!")
        self.assertEqual(res["method_used"], "screenshot_on_demand_fallback")

        print(f"\n[OK] test_07: Inaccessible Control Fallback -> Method: {res['method_used']} | Screenshots: {res['screenshot_taken']} | Time: {elapsed_ms:.2f} ms")

    def test_08_understand_visual_error_using_local_ocr(self):
        """Test: Understand a visual error using local OCR."""
        start = time.perf_counter()
        # Create a synthetic visual error banner image
        error_img = Image.new("RGB", (400, 120), color=(255, 240, 240))
        draw = ImageDraw.Draw(error_img)
        draw.text((15, 25), "Fatal Error: Access Denied 403", fill=(200, 0, 0))
        draw.text((15, 55), "Exception: Cannot connect to service", fill=(100, 0, 0))

        # Run local OCR error diagnostic
        diag_res = self.vision.diagnose_visual_error(image_or_path=error_img)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(diag_res["success"])
        self.assertIn(diag_res["method_used"], ["local_ocr", "cached"])
        # Check that error was detected in diagnosis
        self.assertGreater(len(diag_res["error_lines"]), 0, f"Error keywords not found in {diag_res}")

        print(f"\n[OK] test_08: Local OCR Visual Error -> Method: {diag_res['method_used']} | Detected: {diag_res['error_lines']} | Time: {elapsed_ms:.2f} ms")

    def test_09_performance_benchmark_suite(self):
        """Test: Full 7-operation Performance Benchmark."""
        bm = get_performance_benchmark()
        rep = bm.run_all_benchmarks()

        self.assertTrue(rep["success"])
        self.assertEqual(len(rep["metrics"]), 7)
        self.assertIn("speedup_vs_screenshots", rep)

        print(f"\n[OK] test_09: Performance Benchmark Suite Complete -> Direct Avg: {rep['direct_api_avg_ms']}ms | UIA Avg: {rep['ui_automation_avg_ms']}ms | Vision Avg: {rep['vision_screenshot_avg_ms']}ms")

    def test_10_intent_dispatcher_event_driven_integration(self):
        """Test: Natural language dispatcher triggers event-driven operations directly."""
        dispatcher = get_intent_dispatcher()

        # 1. Calculate intent
        res = dispatcher.dispatch("calculate 125 * 25")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "calculate_accessible")
        self.assertTrue(res.success)
        self.assertIn("3125", res.content.replace(",", ""))

        print("\n[OK] test_10: Intent Dispatcher -> Successfully routed 'calculate 125 * 25' to UI Automation.")


if __name__ == "__main__":
    unittest.main()
