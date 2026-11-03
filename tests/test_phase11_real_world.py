"""
Empirical Acceptance Tests for BOLT Phase 11: Real-World Testing & Intelligence Improvement.
Validates 22 natural language instructions and edge cases against real application components:
- Natural Language Understanding (flexible phrasing, no fixed syntax)
- Multi-App Multitasking Workflows (Internships summary, Programming project diagnosis, Research reports)
- Memory Quality & Retrieval (Workspace location, Preferred browser, Corrections, Conflict resolution)
- Error Recovery & Reliability (Uninstalled app fallback, Offline search, Token substitution)
- Security Approval Gates & Task Lifecycle Controls (Pause, Resume, Cancel)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
import sys
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Windows DLL directories for PySide6
if sys.platform == "win32":
    for p in sys.path:
        try:
            p_path = Path(p)
            for sub in ("PySide6", "shiboken6"):
                dll_dir = p_path / sub
                if dll_dir.is_dir() and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(dll_dir))
        except Exception:
            pass

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from bolt.core.network_manager import get_network_manager
from bolt.memory.manager import get_memory_manager
from bolt.tasks.dependency_manager import DependencyManager
from bolt.tasks.execution_engine import ExecutionEngine
from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskStatus, TaskStep
from bolt.tasks.multitasking_manager import get_multitasking_manager
from bolt.tasks.planner import get_task_planner
from bolt.tasks.recovery_manager import TaskRecoveryManager
from bolt.tasks.tool_registry import get_tool_registry
from bolt.windows.file_manager import FileManager, get_file_manager
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher


class TestPhase11RealWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dispatcher = get_intent_dispatcher()
        cls.planner = get_task_planner()
        cls.mem = get_memory_manager()
        cls.tools = get_tool_registry()
        cls.net_mgr = get_network_manager()

        # Create temporary workspace test directory
        cls.test_dir = Path(tempfile.mkdtemp(prefix="bolt_phase11_test_"))
        cls.test_workspace = cls.test_dir / "workspace"
        cls.test_downloads = cls.test_dir / "downloads"
        cls.test_workspace.mkdir(parents=True, exist_ok=True)
        cls.test_downloads.mkdir(parents=True, exist_ok=True)

        # Seed test files
        (cls.test_downloads / "report_2026.pdf").write_text("Dummy PDF content", encoding="utf-8")
        (cls.test_workspace / "main_project.py").write_text("print('Hello from project')", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.dispatcher.browser_controller.close_browser()
        except Exception:
            pass
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Natural Language Instructions
    # -------------------------------------------------------------------------
    def test_01_command_open_browser_and_search(self):
        """Test: 'Open my browser and search for the latest AI tools.'"""
        cmd = "Open my browser and search for the latest AI tools."
        plan = self.planner.plan_instruction(cmd)
        self.assertGreaterEqual(len(plan.steps), 2)
        # Verify first step opens browser and second step searches web
        step_tools = [s.tool_name for s in plan.steps]
        self.assertIn("open_website", step_tools)
        self.assertIn("search_web", step_tools)

    def test_02_command_find_recent_python_project(self):
        """Test: 'Find the Python project I was working on yesterday.'"""
        cmd = "Find the Python project I was working on yesterday."
        res = self.dispatcher.dispatch(cmd)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "find_python_project")
        self.assertTrue(res.success)
        self.assertIn("Python Project", res.title)

    def test_03_command_open_gemini_and_ask_code_explanation(self):
        """Test: 'Open Gemini and ask it to explain this code.'"""
        cmd = "Open Gemini and ask it to explain this code."
        res = self.dispatcher.dispatch(cmd)
        # Should route to Gemini provider with query
        self.assertEqual(res.action_type, "query_provider")
        self.assertIn("gemini", res.raw_data.get("provider_override", ""))

    def test_04_command_compare_two_websites(self):
        """Test: 'Compare the information from these two websites.'"""
        cmd = "Compare the information from these two websites."
        res = self.dispatcher.dispatch(cmd)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "compare_websites")
        self.assertTrue(res.success)
        self.assertIn("Comparative Web Analysis", res.content)

    def test_05_command_find_most_recent_pdf_in_downloads(self):
        """Test: 'Open my downloads folder and find the most recent PDF.'"""
        # Test FileManager.get_recent_files on populated folder
        recent = FileManager.get_recent_files(folder_alias=str(self.test_downloads), extension=".pdf")
        self.assertGreaterEqual(len(recent), 1)
        self.assertEqual(recent[0]["name"], "report_2026.pdf")

        # Test intent dispatcher recognition
        cmd = "Open my downloads folder and find the most recent PDF."
        res = self.dispatcher.dispatch(cmd)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "recent_files")

    def test_06_command_prepare_email(self):
        """Test: 'Prepare an email using the information we discussed.'"""
        cmd = "Prepare an email using the information we discussed."
        plan = self.planner.plan_instruction(cmd)
        self.assertEqual(plan.title, "Email Preparation & Approval")
        # Step 2 must be approval required
        self.assertTrue(plan.steps[1].requires_approval)
        self.assertEqual(plan.steps[1].risk_level, RiskLevel.APPROVAL_REQUIRED)

    def test_07_command_continue_and_pause_task_lifecycle(self):
        """Test: 'Continue the task you were performing before I paused it.' and 'Pause task'"""
        # Test Pause dispatch
        res_pause = self.dispatcher.dispatch("pause task")
        self.assertTrue(res_pause.is_windows_action)
        self.assertEqual(res_pause.action_type, "pause_task")

        # Test Continue / Resume dispatch
        res_resume = self.dispatcher.dispatch("Continue the task you were performing before I paused it.")
        self.assertTrue(res_resume.is_windows_action)
        self.assertEqual(res_resume.action_type, "resume_task")

    # -------------------------------------------------------------------------
    # 2. Multi-App Workflow Testing (Section 3)
    # -------------------------------------------------------------------------
    def test_08_multitask_workflow_a_internships_summary(self):
        """Test: Example A - Search internships, compare requirements, prepare summary document and save to workspace."""
        cmd = "Search for three AI internship opportunities, compare their requirements, prepare a summary document and save it in my workspace."
        plan = self.planner.plan_instruction(cmd)
        self.assertGreaterEqual(len(plan.steps), 4)

        # Step 1: Search
        self.assertEqual(plan.steps[0].tool_name, "search_web")
        # Step 2: Compare
        self.assertEqual(plan.steps[1].tool_name, "generate_ai_response")
        self.assertIn("step_1", plan.steps[1].dependencies)
        # Step 3: Summary document
        self.assertEqual(plan.steps[2].tool_name, "generate_ai_response")
        self.assertIn("step_2", plan.steps[2].dependencies)
        # Step 4: Write text file in workspace (NOT type_text!)
        self.assertEqual(plan.steps[3].tool_name, "write_text_file")
        self.assertEqual(plan.steps[3].input_params.get("folder_alias"), "workspace")

    def test_09_multitask_workflow_b_programming_fix(self):
        """Test: Example B - Open VS Code, open my project, run the Python file, identify the error and help me fix it."""
        cmd = "Open VS Code, open my project, run the Python file, identify the error and help me fix it."
        plan = self.planner.plan_instruction(cmd)
        self.assertEqual(plan.title, "Programming Project Diagnosis")
        tools = [s.tool_name for s in plan.steps]
        self.assertIn("search_files", tools)
        self.assertIn("open_application", tools)
        self.assertIn("run_python_script_safe", tools)
        self.assertIn("generate_ai_response", tools)
        self.assertIn("request_user_approval", tools)

    def test_10_multitask_workflow_c_research_report(self):
        """Test: Example C - Research a topic using the browser, ask my configured AI model to analyze the information, and prepare a report."""
        cmd = "Research a topic using the browser, ask my configured AI model to analyze the information, and prepare a report."
        plan = self.planner.plan_instruction(cmd)
        self.assertEqual(plan.title, "AI Research & Summarization")
        tools = [s.tool_name for s in plan.steps]
        self.assertIn("open_website", tools)
        self.assertIn("search_web", tools)
        self.assertIn("generate_ai_response", tools)

    # -------------------------------------------------------------------------
    # 3. Memory Quality & Preference Retention (Section 4)
    # -------------------------------------------------------------------------
    def test_11_memory_preferred_browser_retention(self):
        """Test: 'Remember that my preferred browser is Brave.'"""
        cmd = "Remember that my preferred browser is Brave."
        res = self.dispatcher.dispatch(cmd)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "learned_preference")

        # Verify saved in SQLite
        saved_pref = self.mem.get_user_preference("preferred_browser")
        self.assertEqual(saved_pref.lower(), "brave")

    def test_12_memory_workspace_location_retention(self):
        """Test: 'Remember that my workspace is at C:\\Users\\tanze\\OneDrive\\Desktop\\BOLT\\workspace'"""
        target_ws = str(self.test_workspace)
        cmd = f"Remember that my workspace is at {target_ws}"
        res = self.dispatcher.dispatch(cmd)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "learned_preference")

        # Verify saved in SQLite
        saved_ws = self.mem.get_user_preference("workspace_location")
        self.assertEqual(saved_ws, target_ws)
        # Verify FileManager resolves it
        self.assertEqual(FileManager.get_workspace_path(), Path(target_ws))

    def test_13_memory_list_preferences(self):
        """Test: 'What are my preferences?'"""
        res = self.dispatcher.dispatch("What are my preferences?")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "list_preferences")
        self.assertIn("Personal Preferences", res.title)
        self.assertIn("preferred_browser", res.content)

    def test_14_memory_open_usual_browser(self):
        """Test: 'Open my usual browser'"""
        self.mem.save_user_preference("preferred_browser", "brave")
        res = self.dispatcher.dispatch("Open my usual browser")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "open_usual_environment")
        self.assertIn("brave", res.content.lower())

    # -------------------------------------------------------------------------
    # 4. Dependency Token Resolution & Parallel Execution
    # -------------------------------------------------------------------------
    def test_15_dependency_token_resolution_robustness(self):
        """Verify DependencyManager substitutes strings, dictionaries, and fallback keys."""
        plan = ExecutionPlan(
            plan_id="test_plan",
            title="Test Token Resolution",
            user_instruction="test",
            steps=[
                TaskStep(
                    step_id="step_1",
                    description="AI step",
                    tool_name="generate_ai_response",
                    result="AI generated summary text.",
                    status=TaskStatus.COMPLETED,
                ),
                TaskStep(
                    step_id="step_2",
                    description="Write step",
                    tool_name="write_text_file",
                    input_params={
                        "file_path": "out.txt",
                        "content": "${step_1.content}",  # String step has no attr 'content', should resolve gracefully
                    },
                ),
            ],
        )

        resolved = DependencyManager.resolve_step_inputs(plan.steps[1], plan)
        self.assertEqual(resolved["content"], "AI generated summary text.")

    # -------------------------------------------------------------------------
    # 5. Reliability & Error Recovery (Section 5)
    # -------------------------------------------------------------------------
    def test_16_recovery_uninstalled_application_fallback(self):
        """Test recovery fallback when requested editor or browser is not installed."""
        step = TaskStep(
            step_id="step_app",
            description="Launch editor",
            tool_name="open_application",
            input_params={"app_name": "sublime"},
        )
        plan = ExecutionPlan(plan_id="p1", title="App Recovery", user_instruction="test", steps=[step])

        can_recover, desc = TaskRecoveryManager.handle_step_failure(step, plan, "App not found")
        self.assertTrue(can_recover)
        self.assertEqual(step.input_params["app_name"], "Notepad")
        self.assertIn("Notepad", desc)

    def test_17_recovery_offline_search_graceful_exit(self):
        """Test offline search immediate notice without silent cloud leakage."""
        self.net_mgr.set_offline_simulation(True)
        try:
            res = self.tools.execute_tool("search_web", query="latest news")
            self.assertFalse(res["success"])
            self.assertIn("No internet connection detected", res["error"])
        finally:
            self.net_mgr.set_offline_simulation(None)

    def test_18_recovery_ai_provider_fallback(self):
        """Test AI provider fallback to Ollama then Mock."""
        step = TaskStep(
            step_id="step_ai",
            description="AI generation",
            tool_name="generate_ai_response",
            input_params={"provider": "gemini"},
        )
        plan = ExecutionPlan(plan_id="p2", title="AI Recovery", user_instruction="test", steps=[step])

        # Attempt 1: Gemini -> Ollama
        can_recover, desc = TaskRecoveryManager.handle_step_failure(step, plan, "API error")
        self.assertTrue(can_recover)
        self.assertEqual(step.input_params["provider"], "ollama")

        # Attempt 2: Ollama -> Mock
        can_recover, desc = TaskRecoveryManager.handle_step_failure(step, plan, "Ollama connection refused")
        self.assertTrue(can_recover)
        self.assertEqual(step.input_params["provider"], "mock")

    # -------------------------------------------------------------------------
    # 6. Computer Control & Direct Security Gates
    # -------------------------------------------------------------------------
    def test_19_security_gate_delete_directory_critical(self):
        """Test security gate intercepting Level 4 Critical directory deletion."""
        res = self.dispatcher.dispatch("delete directory C:\\test_danger_dir")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "security_approval_required")
        self.assertIn("CRITICAL", res.title)

    def test_20_security_gate_delete_file_high_risk(self):
        """Test security gate intercepting Level 3 High Risk file deletion."""
        res = self.dispatcher.dispatch("delete file C:\\important_data.csv")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "security_approval_required")
        self.assertIn("HIGH RISK", res.title)

    def test_21_direct_ui_automation_calculator(self):
        """Test accessible calculator execution without screenshots."""
        res = self.dispatcher.dispatch("calculate 125 * 8")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "calculate_accessible")
        self.assertTrue(res.success)
        self.assertIn("1000", res.content)

    def test_22_system_diagnostics_telemetry(self):
        """Test 'What are my system specs?'"""
        res = self.dispatcher.dispatch("What are my system specs?")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "system_info")
        self.assertTrue(res.success)
        self.assertIn("Windows 11", res.content)


if __name__ == "__main__":
    unittest.main()
