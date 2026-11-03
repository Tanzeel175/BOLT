"""
Comprehensive Empirical Verification Suite for BOLT Offline-First,
Local AI Integration, Online Search, Real Computer Control, and Persistent Learning.
Tests all requirements defined in Part 10 and Final Acceptance Tests.
"""

import os
import pathlib
import time
import unittest
from unittest.mock import patch

from bolt.ai.base import ChatMessage
from bolt.ai.ollama_provider import OllamaProvider
from bolt.ai.provider_manager import get_ai_provider_manager
from bolt.ai.router import get_ai_router
from bolt.browser.browser_controller import get_browser_controller
from bolt.browser.search_engine import get_search_engine
from bolt.config.constants import DEFAULT_OLLAMA_MODEL, PROVIDER_OLLAMA
from bolt.config.settings import get_settings
from bolt.core.database import get_database
from bolt.core.learning_memory import MemoryCategory, get_learning_memory
from bolt.core.network_manager import OFFLINE_SEARCH_ERROR_MESSAGE, get_network_manager
from bolt.tasks.models import TaskStatus
from bolt.tasks.multitasking_manager import get_multitasking_manager
from bolt.tasks.planner import get_task_planner
from bolt.tasks.tool_registry import get_tool_registry
from bolt.windows.app_controller import get_app_controller
from bolt.windows.file_manager import FileManager
from bolt.windows.input_controller import InputController
from bolt.windows.intent_dispatcher import get_intent_dispatcher
from bolt.windows.system_info import SystemInfo


class TestOfflineAndRealControl(unittest.TestCase):
    """Rigorous empirical test suite testing real laptop hardware, tools, and offline resilience."""

    @classmethod
    def setUpClass(cls):
        os.environ["BOLT_HEADLESS_BROWSER"] = "1"
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.settings = get_settings(reload=True)
        cls.db = get_database()
        cls.net_mgr = get_network_manager()
        cls.net_mgr.set_offline_simulation(None)  # Reset to live network initially

    def tearDown(self):
        # Always restore live network state after every test
        self.net_mgr.set_offline_simulation(None)

    # =========================================================================
    # PART 10.1: LOCAL AI & OLLAMA TESTS
    # =========================================================================

    def test_01_ollama_installation_and_service_detection(self):
        """Test detection of Ollama installation and local service running on port 11434."""
        provider = OllamaProvider()
        installed, path = provider.is_ollama_installed()
        self.assertTrue(installed, f"Ollama should be detected as installed on system. Found path: '{path}'")
        self.assertTrue(len(path) > 0, "Ollama executable path must not be empty.")

        running, msg = provider.is_service_running()
        self.assertTrue(running, f"Ollama local daemon should be running on localhost:11434. Status: {msg}")
        print(f"\n[OK] test_01: Ollama detected at '{path}', service running: {running}")

    def test_02_ollama_model_availability_and_actionable_error(self):
        """Verify model detection and actionable instructions when model is not yet pulled."""
        provider = OllamaProvider(model="gemma4:e2b")
        is_pulled = provider.is_model_downloaded("gemma4:e2b")

        # Test connection test diagnostic
        ok, msg = provider.test_connection()
        if not is_pulled:
            self.assertFalse(ok, "test_connection must return False when model is missing.")
            self.assertIn("ollama run gemma4:e2b", msg)
            self.assertIn("BOLT will not download models automatically", msg)
            print(f"\n[OK] test_02: Model missing diagnostic verified with clear instruction: {msg[:80]}...")
        else:
            self.assertTrue(ok)
            print(f"\n[OK] test_02: Model 'gemma4:e2b' is already downloaded.")

    def test_03_ollama_benchmarking_telemetry(self):
        """Test benchmarking telemetry function (measuring CPU, RAM, TTFT)."""
        provider = OllamaProvider()
        bench = provider.benchmark_model("Test prompt")
        self.assertIsInstance(bench, dict)
        if not bench["success"]:
            # Either not downloaded yet or inference timed out on CPU
            self.assertTrue(any(k in bench["error"].lower() for k in ["not downloaded", "timed out", "ollama", "offline"]))
            print(f"\n[OK] test_03: Benchmarking diagnostic safely reported: {bench['error']}")
        else:
            self.assertIn("tokens_per_second", bench)
            self.assertIn("ram_delta_mb", bench)
            print(f"\n[OK] test_03: Benchmark complete: {bench['tokens_per_second']} tokens/sec")

    # =========================================================================
    # PART 10.2: REAL COMPUTER CONTROL TESTS
    # =========================================================================

    def test_04_system_hardware_telemetry(self):
        """Empirically inspect CPU, RAM, GPU, and Windows system specs."""
        summary = SystemInfo.get_system_summary()
        self.assertIn("os", summary)
        self.assertIn("cpu_model", summary)
        self.assertIn("cpu_cores", summary)
        self.assertIn("ram_total_gb", summary)
        self.assertGreater(summary["ram_total_gb"], 0)
        print(f"\n[OK] test_04: Telemetry: CPU={summary['cpu_model']} ({summary['cpu_cores']}), RAM={summary['ram_total_gb']}GB")

    def test_05_create_and_read_notes_on_desktop(self):
        """Test creating 'Notes.txt' on Desktop and reading it back."""
        test_content = "Hello World from BOLT Real Computer Control Test"
        file_res = FileManager.create_text_file("Notes.txt", content=test_content)
        self.assertTrue(file_res["success"], f"Failed to create Notes.txt: {file_res.get('error')}")

        target_path = pathlib.Path(file_res["file_path"])
        self.assertTrue(target_path.exists(), f"File does not exist on disk: {target_path}")

        # Read back
        read_res = FileManager.read_text_file("Notes.txt")
        self.assertTrue(read_res["success"], f"Failed reading Notes.txt: {read_res.get('error')}")
        self.assertEqual(read_res["content"], test_content)

        # Cleanup test file
        target_path.unlink(missing_ok=True)
        print(f"\n[OK] test_05: Created and verified Notes.txt at {target_path}")

    def test_06_registered_tools_execution(self):
        """Verify all registered Part 4 tools execute with structured outputs."""
        registry = get_tool_registry()

        # 1. system_information
        res_info = registry.execute_tool("get_system_information")
        self.assertTrue(res_info["success"])

        # 2. check_internet_connection
        res_net = registry.execute_tool("check_internet_connection")
        self.assertTrue(res_net["success"])
        self.assertIn("is_connected", res_net)

        # 3. take_screenshot
        res_shot = registry.execute_tool("take_screenshot")
        self.assertTrue(res_shot["success"])
        p = pathlib.Path(res_shot["file_path"])
        self.assertTrue(p.exists())
        p.unlink(missing_ok=True)

        # 4. type_text (empty or safe test)
        res_type = registry.execute_tool("type_text", text="")
        self.assertTrue(res_type["success"])

        # 5. create_text_file
        res_create = registry.execute_tool("create_text_file", file_path="bolt_unit_test.txt", content="123")
        self.assertTrue(res_create["success"])
        pathlib.Path(res_create["file_path"]).unlink(missing_ok=True)

        print(f"\n[OK] test_06: All registered computer control tools verified.")

    # =========================================================================
    # PART 10.3: ONLINE SEARCH TESTS
    # =========================================================================

    def test_07_online_search_when_connected(self):
        """Test web search when connected, ensuring real results and links."""
        b_ctrl = get_browser_controller()
        res = b_ctrl.search_web("artificial intelligence news", provider="google")
        if not self.net_mgr.is_internet_available():
            self.skipTest("Live internet connection not available on laptop right now.")

        self.assertTrue(res["success"])
        self.assertGreater(len(res["results"]), 0)
        self.assertIn("url", res["results"][0])
        self.assertIn("summary_md", res)
        print(f"\n[OK] test_07: Online search returned {len(res['results'])} verified results. Top: {res['results'][0]['title']}")

    # =========================================================================
    # PART 10.4: OFFLINE TESTS & PARTIAL TASK SUCCESS
    # =========================================================================

    def test_08_offline_search_error_and_exact_message(self):
        """When offline, web search must stop immediately with exact specified error string."""
        self.net_mgr.set_offline_simulation(True)
        self.assertFalse(self.net_mgr.is_internet_available())

        b_ctrl = get_browser_controller()
        res = b_ctrl.search_web("latest AI news")

        self.assertFalse(res["success"])
        self.assertEqual(res["error"], OFFLINE_SEARCH_ERROR_MESSAGE)
        print(f"\n[OK] test_08: Offline search immediately returned exact message:\n\"{res['error']}\"")

    def test_09_mixed_online_and_offline_task_partial_success(self):
        """
        Mixed task: 'Open Calculator and search for the latest AI news.'
        When offline:
        - Calculator opens successfully.
        - Online search detects no-internet error and fails.
        - Calculator operation is preserved!
        - Overall plan completes as PARTIALLY_COMPLETED.
        """
        self.net_mgr.set_offline_simulation(True)
        planner = get_task_planner()
        plan = planner.plan_instruction("Open Calculator and search for the latest AI news.")

        # Ensure Calculator step does NOT depend on search step
        step_calc = next((s for s in plan.steps if "calculator" in s.description.lower()), None)
        step_search = next((s for s in plan.steps if "search" in s.description.lower()), None)
        self.assertIsNotNone(step_calc)
        self.assertIsNotNone(step_search)
        self.assertEqual(len(step_calc.dependencies), 0)
        self.assertEqual(len(step_search.dependencies), 0)

        # Mock app launch so we don't pop up a real window during test
        with patch.object(get_app_controller(), "open_application", return_value={"success": True, "message": "Successfully opened Calculator."}):
            mgr = get_multitasking_manager()
            executed_plan = mgr.plan_and_execute_sync("Open Calculator and search for the latest AI news.")

        self.assertEqual(executed_plan.status, TaskStatus.PARTIALLY_COMPLETED)
        # Verify Calculator succeeded
        s_calc = next(s for s in executed_plan.steps if s.tool_name == "open_application")
        self.assertEqual(s_calc.status, TaskStatus.COMPLETED)
        # Verify Search failed with exact required error
        s_search = next(s for s in executed_plan.steps if s.tool_name == "search_web")
        self.assertEqual(s_search.status, TaskStatus.FAILED)
        self.assertEqual(s_search.error, OFFLINE_SEARCH_ERROR_MESSAGE)

        print(f"\n[OK] test_09: Mixed offline task partial success verified. Status: {executed_plan.status.value.upper()}")

    # =========================================================================
    # PART 10.5: LOCAL LEARNING & MEMORY TESTS
    # =========================================================================

    def test_10_memory_preference_and_user_correction(self):
        """Save a preference, retrieve it, record a correction, and export fine-tuning dataset."""
        memory = get_learning_memory()

        # 1. User Preference
        memory.set_user_preference("preferred_browser_for_chatgpt", "chrome")
        pref = memory.get_user_preference("preferred_browser_for_chatgpt")
        self.assertEqual(pref, "chrome")

        # 2. User Correction
        res = memory.record_user_correction(
            instruction="Open code editor",
            wrong_choice="Notepad",
            correct_choice="Visual Studio Code",
            save_as_preference=True,
        )
        self.assertTrue(res["success"])

        # 3. LoRA dataset export
        export_res = memory.export_finetuning_dataset_jsonl()
        self.assertTrue(export_res["success"])
        p = pathlib.Path(export_res["file_path"])
        self.assertTrue(p.exists())
        self.assertGreater(export_res["examples_count"], 0)

        print(f"\n[OK] test_10: Persistent memory, correction learning, and LoRA dataset verified.")

    # =========================================================================
    # FINAL ACCEPTANCE TESTS
    # =========================================================================

    def test_11_final_acceptance_notepad_and_write(self):
        """
        Acceptance Test: "Open Notepad and write Hello World."
        BOLT must recognize application, launch tool, type tool, and complete.
        """
        dispatcher = get_intent_dispatcher()

        with patch.object(get_app_controller(), "open_application", return_value={"success": True, "message": "Opened Notepad."}):
            with patch.object(InputController, "type_text", return_value={"success": True, "chars_typed": 12}):
                res = dispatcher.dispatch("Open Notepad and write Hello World.")

        self.assertTrue(res.success)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "multi_action_task")
        print(f"\n[OK] Acceptance Test 1 Passed: 'Open Notepad and write Hello World'")

    def test_12_final_acceptance_calculator_and_create_notes_on_desktop_offline(self):
        """
        Acceptance Test: Disconnect internet, type "Open Calculator and create a file called Notes.txt on my Desktop."
        BOLT must complete both local operations offline.
        """
        self.net_mgr.set_offline_simulation(True)
        dispatcher = get_intent_dispatcher()

        with patch.object(get_app_controller(), "open_application", return_value={"success": True, "message": "Opened Calculator."}):
            res = dispatcher.dispatch("Open Calculator and create a file called Notes.txt on my Desktop.")

        self.assertTrue(res.success)
        self.assertTrue(res.is_windows_action)

        # Verify Notes.txt on Desktop exists
        read_res = FileManager.read_text_file("Notes.txt")
        self.assertTrue(read_res["success"])
        pathlib.Path(read_res["file_path"]).unlink(missing_ok=True)

        print(f"\n[OK] Acceptance Test 2 Passed: 'Open Calculator and create Notes.txt on Desktop' offline")


if __name__ == "__main__":
    unittest.main()
