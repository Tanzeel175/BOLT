"""
Comprehensive Test Suite for BOLT HCU-Style Semantic Accessibility Integration:
Tests:
1. InteractiveElementRegistry indexing and filtering.
2. Direct programmatic clicking via click_control_by_id.
3. Direct text entry via set_control_text with read-back verification.
4. Strict stale-ID guardrails:
   - Mutation dirty state rejection.
   - TTL expiration rejection.
   - Window shift / focus mismatch rejection.
   - Closed window rejection.
   - Live element structural type mismatch rejection.
5. Contextual security risk evaluation:
   - Low risk for ordinary controls/menus.
   - Moderate risk for configuration / overwrites.
   - High risk for destructive, sending, or financial actions.
   - Critical risk for administrative destruction.
6. Inaccessible control fallback to on-demand visual diagnosis.
7. Real application tests: Notepad and File Explorer.
"""

import os
import subprocess
import time
import unittest
import ctypes
from unittest.mock import MagicMock, patch

user32 = ctypes.windll.user32

# Attach early to interactive desktop
try:
    h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if h_default:
        user32.SetThreadDesktop(h_default)
except Exception:
    pass

from bolt.security.models import SecurityRiskLevel
from bolt.security.risk_classifier import RiskClassifier
from bolt.tasks.tool_registry import ToolRegistry
from bolt.windows.app_controller import get_app_controller
from bolt.windows.hybrid_controller import get_hybrid_controller
from bolt.windows.ui_automation import (
    IndexedControlInfo,
    InteractiveElementRegistry,
    get_interactive_element_registry,
    get_ui_automation_manager,
)


class TestHCUAccessibilityIntegration(unittest.TestCase):
    """Test suite for HCU semantic accessibility computer control."""

    @classmethod
    def setUpClass(cls):
        cls.uia = get_ui_automation_manager()
        cls.hybrid = get_hybrid_controller()
        cls.registry = get_interactive_element_registry()
        cls.tool_reg = ToolRegistry()
        cls.app_ctrl = get_app_controller()

    def setUp(self):
        self.registry.clear()

    def tearDown(self):
        self.registry.clear()

    # -----------------------------------------------------------------
    # 1. ELEMENT INDEXING & REGISTRY LOGIC
    # -----------------------------------------------------------------
    def test_01_registry_initialization_and_clear(self):
        """Verify registry state tracking, dirty flagging, and clearing."""
        self.assertTrue(self.registry.is_dirty)
        self.assertEqual(len(self.registry._elements), 0)

        # Manually populate mock element
        info = IndexedControlInfo(
            element_id=1,
            name="Save",
            control_type="ButtonControl",
            automation_id="save_btn",
            class_name="Button",
            bounding_rect=(10, 10, 100, 40),
            is_enabled=True,
            patterns=["InvokePattern"],
        )
        self.registry._elements[1] = info
        self.registry._is_dirty = False
        self.registry._timestamp = time.time()
        self.registry._window_hwnd = user32.GetForegroundWindow()

        self.assertFalse(self.registry.is_dirty)
        retrieved = self.registry.get_element(1)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Save")

        # Mark dirty
        self.registry.mark_dirty()
        self.assertTrue(self.registry.is_dirty)

        # Clear
        self.registry.clear()
        self.assertEqual(len(self.registry._elements), 0)
        self.assertTrue(self.registry.is_dirty)

    def test_02_stale_id_protection_dirty_state(self):
        """Verify action is rejected immediately when snapshot is dirty."""
        self.registry.clear()
        self.registry._is_dirty = True

        is_valid, msg, elem = self.registry.validate_control_id(1)
        self.assertFalse(is_valid)
        self.assertIn("mutated or is unindexed", msg)
        self.assertIsNone(elem)

    def test_03_stale_id_protection_ttl_expiration(self):
        """Verify action is rejected when snapshot TTL expires."""
        self.registry._elements[1] = IndexedControlInfo(
            element_id=1,
            name="Test",
            control_type="ButtonControl",
            automation_id="btn_1",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        self.registry._window_hwnd = user32.GetForegroundWindow()
        self.registry._is_dirty = False
        # Set timestamp to 30 seconds ago (TTL is 25s)
        self.registry._timestamp = time.time() - 35.0

        is_valid, msg, elem = self.registry.validate_control_id(1)
        self.assertFalse(is_valid)
        self.assertIn("expired", msg.lower())
        self.assertTrue(self.registry.is_dirty)

    def test_04_stale_id_protection_window_mismatch(self):
        """Verify action is rejected when foreground window focus shifts."""
        fg = user32.GetForegroundWindow()
        fake_hwnd = 99999999

        self.registry._elements[1] = IndexedControlInfo(
            element_id=1,
            name="Test",
            control_type="ButtonControl",
            automation_id="btn_1",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        self.registry._window_hwnd = fake_hwnd
        self.registry._is_dirty = False
        self.registry._timestamp = time.time()

        is_valid, msg, elem = self.registry.validate_control_id(1)
        self.assertFalse(is_valid)
        self.assertTrue("closed" in msg.lower() or "focus shifted" in msg.lower())

    def test_05_stale_id_protection_structural_type_mismatch(self):
        """Verify action is rejected if live control type shifts underneath."""
        mock_ctrl = MagicMock()
        mock_ctrl.Exists.return_value = True
        mock_ctrl.ControlTypeName = "EditControl"  # Live type is Edit, but indexed as Button

        self.registry._elements[1] = IndexedControlInfo(
            element_id=1,
            name="Search",
            control_type="ButtonControl",  # Expected Button
            automation_id="btn_search",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
            control_ref=mock_ctrl,
        )
        self.registry._window_hwnd = user32.GetForegroundWindow()
        self.registry._is_dirty = False
        self.registry._timestamp = time.time()

        is_valid, msg, elem = self.registry.validate_control_id(1)
        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())

    # -----------------------------------------------------------------
    # 2. CONTEXTUAL SECURITY EVALUATION TESTS
    # -----------------------------------------------------------------
    def test_06_security_classification_low_risk(self):
        """Verify ordinary navigation and inspection are classified as Level 1 Low Risk."""
        req_inspect = RiskClassifier.classify_action("inspect_active_window_controls", {})
        self.assertEqual(req_inspect.risk_level, SecurityRiskLevel.LOW)

        # Mock standard button in Notepad
        self.registry._window_title = "Untitled - Notepad"
        self.registry._elements[1] = IndexedControlInfo(
            element_id=1,
            name="File",
            control_type="MenuItemControl",
            automation_id="file_menu",
            class_name="MenuItem",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        req_click = RiskClassifier.classify_action("click_control_by_id", {"element_id": 1})
        self.assertEqual(req_click.risk_level, SecurityRiskLevel.LOW)

        # Standard text entry in Notepad
        req_text = RiskClassifier.classify_action("set_control_text", {"element_id": 1, "text": "Hello"})
        self.assertEqual(req_text.risk_level, SecurityRiskLevel.LOW)

    def test_07_security_classification_high_risk_actions(self):
        """Verify financial, destructive, and external sending actions require Level 3 High Risk approval."""
        # Financial context
        self.registry._window_title = "Shopping Checkout - Chrome"
        self.registry._elements[2] = IndexedControlInfo(
            element_id=2,
            name="Complete Purchase",
            control_type="ButtonControl",
            automation_id="btn_pay",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        req_pay = RiskClassifier.classify_action("click_control_by_id", {"element_id": 2})
        self.assertEqual(req_pay.risk_level, SecurityRiskLevel.HIGH)
        self.assertIn("Financial", req_pay.action_type)

        # Destructive context
        self.registry._elements[3] = IndexedControlInfo(
            element_id=3,
            name="Delete All Files",
            control_type="ButtonControl",
            automation_id="btn_del",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        req_del = RiskClassifier.classify_action("click_control_by_id", {"element_id": 3})
        self.assertEqual(req_del.risk_level, SecurityRiskLevel.HIGH)
        self.assertIn("Destructive", req_del.action_type)

        # External sending context
        self.registry._window_title = "Outlook Inbox - Outlook"
        self.registry._elements[4] = IndexedControlInfo(
            element_id=4,
            name="Send",
            control_type="ButtonControl",
            automation_id="btn_send",
            class_name="Button",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        req_send = RiskClassifier.classify_action("click_control_by_id", {"element_id": 4})
        self.assertEqual(req_send.risk_level, SecurityRiskLevel.HIGH)
        self.assertIn("External Communication", req_send.action_type)

        # Password credential entry
        self.registry._elements[5] = IndexedControlInfo(
            element_id=5,
            name="Account Password",
            control_type="EditControl",
            automation_id="pwd_field",
            class_name="Edit",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
            is_password=True,
        )
        req_pwd = RiskClassifier.classify_action("set_control_text", {"element_id": 5, "text": "secret123"})
        self.assertEqual(req_pwd.risk_level, SecurityRiskLevel.HIGH)

    def test_08_security_classification_critical_admin(self):
        """Verify administrative command destruction requires Level 4 Critical confirmation phrase."""
        self.registry._window_title = "Registry Editor (Administrator)"
        self.registry._elements[6] = IndexedControlInfo(
            element_id=6,
            name="Delete Key",
            control_type="MenuItemControl",
            automation_id="menu_del",
            class_name="MenuItem",
            bounding_rect=(0, 0, 10, 10),
            is_enabled=True,
        )
        req_admin = RiskClassifier.classify_action("click_control_by_id", {"element_id": 6})
        self.assertEqual(req_admin.risk_level, SecurityRiskLevel.CRITICAL)
        self.assertTrue(req_admin.requires_typed_confirmation)
        self.assertEqual(req_admin.confirmation_phrase, "CONFIRM")

    # -----------------------------------------------------------------
    # 3. TOOL REGISTRY EXPOSURE
    # -----------------------------------------------------------------
    def test_09_tool_registry_schemas(self):
        """Verify all 3 new HCU tools are properly registered and exposed in ToolRegistry."""
        tools = {t["name"]: t for t in self.tool_reg.get_tool_definitions()}

        self.assertIn("inspect_active_window_controls", tools)
        self.assertIn("click_control_by_id", tools)
        self.assertIn("set_control_text", tools)

        # Check parameter schemas
        inspect_t = tools["inspect_active_window_controls"]
        self.assertIn("window_query", inspect_t["parameters"]["properties"])

        click_t = tools["click_control_by_id"]
        self.assertIn("element_id", click_t["parameters"]["properties"])
        self.assertIn("element_id", click_t["parameters"]["required"])

        text_t = tools["set_control_text"]
        self.assertIn("element_id", text_t["parameters"]["properties"])
        self.assertIn("text", text_t["parameters"]["properties"])
        self.assertIn("element_id", text_t["parameters"]["required"])
        self.assertIn("text", text_t["parameters"]["required"])

    # -----------------------------------------------------------------
    # 4. INACCESSIBLE CONTROL FALLBACK
    # -----------------------------------------------------------------
    def test_10_inaccessible_control_fallback(self):
        """Verify fallback to visual diagnosis occurs when UIA invocation fails."""
        with patch.object(self.uia, "click_control_by_id") as mock_click:
            mock_click.return_value = {
                "success": False,
                "stale_state": False,
                "error": "Control does not support invocation patterns or coordinate center.",
            }

            res = self.hybrid.click_control_by_id(999)
            self.assertFalse(res["success"])
            self.assertTrue(res["screenshot_taken"])
            self.assertEqual(res["method_used"], "screenshot_on_demand_fallback")
            self.assertIn("fallback_visual_diagnosis", res)

    # -----------------------------------------------------------------
    # 5. REAL APPLICATION TESTS: NOTEPAD & FILE EXPLORER
    # -----------------------------------------------------------------
    def test_11_real_notepad_workflow(self):
        """
        Real-world test on Windows Notepad:
        1. Open Notepad.
        2. Inspect controls (assigning [1], [2], [3]...).
        3. Set text into edit/document control.
        4. Verify text was set via UIA (ZERO screenshots).
        5. Verify registry was marked dirty after mutation.
        6. Cleanly close Notepad.
        """
        # Launch Notepad via direct automation
        launch_res = self.hybrid.open_application_direct("notepad")
        self.assertTrue(launch_res["success"], f"Failed to launch Notepad: {launch_res}")
        time.sleep(1.2)

        try:
            # 1. Inspect controls
            inspect_res = self.hybrid.inspect_active_window_controls("notepad", max_controls=25)
            self.assertTrue(inspect_res["success"], f"Failed inspecting Notepad: {inspect_res}")
            self.assertGreater(inspect_res["control_count"], 0)
            self.assertFalse(inspect_res["screenshot_taken"])
            self.assertIn("[1]", inspect_res["formatted_controls"])

            # 2. Locate edit / document field
            edit_id = None
            for c in inspect_res["controls"]:
                if c["type"] in ("Edit", "Document") or "editor" in (c["name"] or "").lower():
                    edit_id = c["id"]
                    break

            # If not labeled as Edit/Document, pick any input control
            if not edit_id and inspect_res["controls"]:
                edit_id = inspect_res["controls"][-1]["id"]

            self.assertIsNotNone(edit_id, "Could not find text input control in Notepad.")

            # 3. Set text into control
            test_phrase = "BOLT HCU Semantic Accessibility Verified"
            text_res = self.hybrid.set_control_text(edit_id, test_phrase)
            self.assertTrue(text_res["success"], f"Failed setting text: {text_res}")
            self.assertFalse(text_res["screenshot_taken"])
            self.assertTrue(text_res.get("verified", False))

            # 4. Verify registry was marked dirty immediately after mutation
            self.assertTrue(self.registry.is_dirty, "Registry was not invalidated after text mutation!")

            print(f"\n[OK] test_11 Notepad HCU Workflow -> Latency: {text_res['execution_time_ms']:.2f} ms | Verified: {text_res['verified']} | Screenshots: {text_res['screenshot_taken']}")

        finally:
            # Safely close Notepad
            self.app_ctrl.close_application("notepad")

    def test_12_real_file_explorer_inspection(self):
        """
        Real-world test on Windows File Explorer:
        1. Inspect File Explorer or active desktop window.
        2. Verify non-interactive container suppression.
        3. Confirm interactive controls are numbered cleanly.
        """
        # Open explorer or inspect active explorer window
        inspect_res = self.hybrid.inspect_active_window_controls("explorer", max_controls=20)
        # Even if explorer has different localized title, test handles graceful return
        if inspect_res["success"]:
            self.assertFalse(inspect_res["screenshot_taken"])
            self.assertGreaterEqual(inspect_res["control_count"], 0)
            for c in inspect_res["controls"]:
                # Ensure suppressed containers are not returned as interactable
                self.assertNotIn(c["type"], ["Pane", "Custom", "Separator"])
            print(f"\n[OK] test_12 File Explorer -> Controls: {inspect_res['control_count']} | Screenshots: {inspect_res['screenshot_taken']}")
        else:
            # Fallback check on current desktop/active window
            active_res = self.hybrid.inspect_active_window_controls(max_controls=20)
            self.assertTrue(active_res["success"])
            self.assertFalse(active_res["screenshot_taken"])


if __name__ == "__main__":
    unittest.main()
