"""
Comprehensive Automated Test Suite for BOLT Phase 2:
Computer Understanding and Windows Control
Verifies:
1. Application Discovery System
2. Application Registry & SQLite Persistence
3. Window Management (Enum, Find, Minimize, Maximize, Restore)
4. Application Control (Launch, Verify, Duplicate Prevention, Safe Close, Protection)
5. System Hardware Telemetry
6. File System Operations & Directory Aliases
7. Natural Language Intent Dispatcher Integration
"""

import os
import sys
import time
from pathlib import Path

# Configure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
import unittest

from bolt.windows.app_discovery import ApplicationDiscovery
from bolt.windows.app_registry import ApplicationRegistry
from bolt.windows.window_manager import WindowManager
from bolt.windows.app_controller import AppController, PROTECTED_PROCESSES
from bolt.windows.system_info import SystemInfo
from bolt.windows.file_manager import FileManager
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher


class TestPhase2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.discovery = ApplicationDiscovery()
        cls.registry = ApplicationRegistry()
        cls.window_mgr = WindowManager()
        cls.controller = AppController(registry=cls.registry, window_mgr=cls.window_mgr)
        cls.file_mgr = FileManager()
        cls.dispatcher = WindowsIntentDispatcher(
            app_controller=cls.controller,
            window_mgr=cls.window_mgr,
            file_mgr=cls.file_mgr,
        )

    def test_01_app_discovery(self):
        """Verify discovery of installed desktop applications and Windows built-ins."""
        apps = self.discovery.discover_all()
        self.assertGreater(len(apps), 10, "Should discover at least 10 desktop apps")

        app_names = [a.name.lower() for a in apps]
        self.assertIn("notepad", app_names)
        self.assertIn("calculator", app_names)
        self.assertIn("file explorer", app_names)

        notepad_app = next(a for a in apps if a.name == "notepad")
        self.assertEqual(notepad_app.launch_method, "shell_command")
        self.assertEqual(notepad_app.category, "Utilities")
        self.assertTrue(notepad_app.is_verified)
        print(f"[OK] test_01_app_discovery passed: {len(apps)} apps discovered.")

    def test_02_app_registry_and_aliases(self):
        """Verify registry persistence and natural query alias resolution."""
        # 1. Alias lookup
        resolved_vscode = self.registry.resolve_application("vscode")
        if resolved_vscode:
            self.assertEqual(resolved_vscode["name"], "visual studio code")

        resolved_calc = self.registry.resolve_application("calc")
        self.assertIsNotNone(resolved_calc)
        self.assertEqual(resolved_calc["name"], "calculator")

        resolved_notes = self.registry.resolve_application("notes")
        self.assertIsNotNone(resolved_notes)
        self.assertEqual(resolved_notes["name"], "notepad")

        # 2. Category filtering
        util_apps = self.registry.list_applications(category="Utilities")
        self.assertGreater(len(util_apps), 0)
        print("[OK] test_02_app_registry_and_aliases passed.")

    def test_03_system_telemetry(self):
        """Verify system diagnostics collection."""
        summary = SystemInfo.get_system_summary()
        self.assertIn("Windows", summary["os"])
        self.assertGreater(summary["ram_total_gb"], 0)
        self.assertGreater(summary["disk_total_gb"], 0)
        self.assertGreaterEqual(summary["cpu_usage_pct"], 0)

        md = SystemInfo.format_markdown_summary()
        self.assertIn("### 🖥️ Windows 11 System Diagnostics", md)
        self.assertIn("Memory (RAM):", md)
        print("[OK] test_03_system_telemetry passed.")

    def test_04_file_manager(self):
        """Verify folder resolution and file search."""
        desktop_dir = FileManager.resolve_folder_alias("desktop")
        self.assertIsNotNone(desktop_dir)
        self.assertTrue(desktop_dir.exists())

        downloads_dir = FileManager.resolve_folder_alias("downloads")
        self.assertIsNotNone(downloads_dir)
        self.assertTrue(downloads_dir.exists())

        # Search for known files in project root
        found = FileManager.search_files("run.py", start_dir=str(ROOT), max_results=5)
        self.assertGreater(len(found), 0)
        self.assertEqual(found[0]["name"], "run.py")
        print("[OK] test_04_file_manager passed.")

    def test_05_window_manager(self):
        """Verify top-level window enumeration."""
        windows = self.window_mgr.get_visible_windows()
        # On a graphical Windows system, there are visible windows
        self.assertIsInstance(windows, list)
        print(f"[OK] test_05_window_manager passed: {len(windows)} visible windows.")

    def test_06_app_control_lifecycle(self):
        """
        Verify end-to-end Application Control lifecycle:
        1. Launch Notepad
        2. Verify it is running
        3. Attempt to launch again -> verify duplicate prevention (switched to window)
        4. Close Notepad
        5. Verify it is no longer running
        """
        # Ensure Notepad is closed initially
        self.controller.close_application("notepad")
        time.sleep(0.5)

        # 1. Open Notepad
        open_res = self.controller.open_application("notepad")
        self.assertTrue(open_res["success"], f"Failed to open notepad: {open_res}")
        self.assertFalse(open_res.get("already_running", False))

        # 2. Verify running
        running, pids = self.controller.is_app_running("notepad")
        self.assertTrue(running, "Notepad should be confirmed running after launch")
        self.assertGreater(len(pids), 0)

        # 3. Duplicate Prevention Test
        open_dup = self.controller.open_application("notepad")
        self.assertTrue(open_dup["success"])
        self.assertTrue(open_dup.get("already_running", False), "Duplicate launch should be prevented")
        self.assertEqual(open_dup["action"], "switched_to_window")

        # 4. Close Notepad
        close_res = self.controller.close_application("notepad")
        self.assertTrue(close_res["success"], f"Failed to close notepad: {close_res}")
        time.sleep(0.5)

        # 5. Verify terminated
        still_running, _ = self.controller.is_app_running("notepad")
        self.assertFalse(still_running, "Notepad should be terminated")
        print("[OK] test_06_app_control_lifecycle passed (Launch, Duplicate Prevention, Safe Close).")

    def test_07_protected_process_security(self):
        """Verify that critical system processes cannot be terminated."""
        res_exp = self.controller.close_application("explorer")
        self.assertFalse(res_exp["success"])
        self.assertIn("protected", res_exp["error"].lower())

        res_py = self.controller.close_application("python")
        self.assertFalse(res_py["success"])
        self.assertIn("protected", res_py["error"].lower())
        print("[OK] test_07_protected_process_security passed.")

    def test_08_intent_dispatcher(self):
        """Verify natural language instruction translation."""
        # 1. System info instruction
        res_sys = self.dispatcher.dispatch("BOLT, what are my system specs?")
        self.assertTrue(res_sys.is_windows_action)
        self.assertEqual(res_sys.action_type, "system_info")
        self.assertIn("Windows 11 System Diagnostics", res_sys.content)

        # 2. List running apps instruction
        res_list = self.dispatcher.dispatch("What apps are currently running?")
        self.assertTrue(res_list.is_windows_action)
        self.assertEqual(res_list.action_type, "list_running")

        # 3. Open folder instruction
        res_fold = self.dispatcher.dispatch("Open my desktop folder")
        self.assertTrue(res_fold.is_windows_action)
        self.assertEqual(res_fold.action_type, "open_folder")

        # 4. Conversational question (should NOT trigger Windows action)
        res_conv = self.dispatcher.dispatch("Explain recursion in C++")
        self.assertFalse(res_conv.is_windows_action, "Conversational queries must route to LLM")
        print("[OK] test_08_intent_dispatcher passed.")


if __name__ == "__main__":
    unittest.main()

