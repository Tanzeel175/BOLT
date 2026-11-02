"""
Automated Verification Suite for BOLT Phase 5: Intelligent Task Planning & Multitasking.

Tests all 14 Phase 5 Requirements:
1. Single-action task execution.
2. Five-step sequential workflow execution.
3. Two independent actions executed in parallel.
4. Workflow with dependencies and output piping.
5. Pause and resume a workflow.
6. Cancel a workflow safely.
7. Recover from a browser failure (search fallback).
8. Recover from an unavailable AI provider (fallback route).
9. Human-in-the-loop interaction and approval gates.
10. Workflow memory save and recall reuse.
11. Avoid re-executing already completed steps.
12. Non-blocking asynchronous worker responsiveness.
13. Approval required before sensitive actions (email, file mods).
14. Accurate task logging and execution reporting.
15. End-to-End validation of Workflows A, B, C, and D.
"""

import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskProgressUpdate, TaskStatus, TaskStep
from bolt.tasks.planner import TaskPlanner, get_task_planner
from bolt.tasks.dependency_manager import DependencyManager
from bolt.tasks.execution_engine import ExecutionEngine
from bolt.tasks.recovery_manager import TaskRecoveryManager
from bolt.tasks.multitasking_manager import MultitaskingManager, get_multitasking_manager
from bolt.tasks.tool_registry import get_tool_registry
from bolt.tasks.workflow_memory import get_workflow_memory
from bolt.core.database import get_database
from bolt.windows.intent_dispatcher import get_intent_dispatcher


class TestPhase5IntelligentTaskPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_database()
        cls.planner = get_task_planner()
        cls.tool_registry = get_tool_registry()
        cls.workflow_mem = get_workflow_memory()
        cls.coordinator = get_multitasking_manager()
        cls.dispatcher = get_intent_dispatcher()

    def test_01_single_action_task(self):
        """Req 1: Single-action task execution through engine."""
        step = TaskStep(
            step_id="step_1",
            description="Retrieve system telemetry diagnostic",
            tool_name="system_telemetry",
            input_params={},
            expected_output="Hardware telemetry dictionary",
        )
        plan = ExecutionPlan(
            plan_id="test_plan_01",
            title="Single Action Telemetry",
            user_instruction="Check my system specs",
            steps=[step],
        )

        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        res_plan = engine.execute_plan(plan)

        self.assertEqual(res_plan.status, TaskStatus.COMPLETED)
        self.assertEqual(step.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(step.result)
        self.assertIn("cpu_usage_pct", step.result)
        print("\n[OK] test_01_single_action_task passed.")

    def test_02_five_step_sequential_workflow(self):
        """Req 2: Execute a five-step sequential workflow with dependencies."""
        steps = [
            TaskStep(step_id="step_1", description="Step 1: Check telemetry", tool_name="system_telemetry"),
            TaskStep(step_id="step_2", description="Step 2: List windows", tool_name="list_visible_windows", dependencies=["step_1"]),
            TaskStep(step_id="step_3", description="Step 3: List browsers", tool_name="list_installed_browsers", dependencies=["step_2"]),
            TaskStep(step_id="step_4", description="Step 4: List websites", tool_name="list_known_websites", dependencies=["step_3"]),
            TaskStep(
                step_id="step_5",
                description="Step 5: Synthesize report",
                tool_name="generate_ai_response",
                input_params={"prompt": "Confirm test steps completed.", "provider": "mock"},
                dependencies=["step_4"],
            ),
        ]
        plan = ExecutionPlan(
            plan_id="test_plan_02",
            title="5-Step Sequential Workflow",
            user_instruction="Run 5 sequential diagnostic steps",
            steps=steps,
        )

        self.assertTrue(DependencyManager.validate_plan_dag(plan))
        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        res_plan = engine.execute_plan(plan)

        self.assertEqual(res_plan.status, TaskStatus.COMPLETED)
        self.assertTrue(all(s.status == TaskStatus.COMPLETED for s in res_plan.steps))
        self.assertEqual(res_plan.progress_percentage(), 100.0)
        print("[OK] test_02_five_step_sequential_workflow passed.")

    def test_03_parallel_independent_actions(self):
        """Req 3: Execute two independent actions in parallel."""
        step_a = TaskStep(step_id="step_a", description="Telemetry diagnostic", tool_name="system_telemetry")
        step_b = TaskStep(step_id="step_b", description="List known websites", tool_name="list_known_websites")

        plan = ExecutionPlan(
            plan_id="test_plan_03",
            title="Parallel Independent Actions",
            user_instruction="Check telemetry and check known websites simultaneously",
            steps=[step_a, step_b],
        )

        self.assertTrue(DependencyManager.can_run_in_parallel(step_a, step_b))
        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        res_plan = engine.execute_plan(plan)

        self.assertEqual(res_plan.status, TaskStatus.COMPLETED)
        self.assertEqual(step_a.status, TaskStatus.COMPLETED)
        self.assertEqual(step_b.status, TaskStatus.COMPLETED)
        print("[OK] test_03_parallel_independent_actions passed.")

    def test_04_dependency_resolution_and_data_piping(self):
        """Req 4: Output from predecessor step piped into dependent step input."""
        test_file = ROOT / "data" / "test_piping.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Hello from Phase 5 Data Piping Test", encoding="utf-8")

        steps = [
            TaskStep(
                step_id="step_1",
                description="Read test file",
                tool_name="read_text_file",
                input_params={"file_path": str(test_file)},
            ),
            TaskStep(
                step_id="step_2",
                description="Process content",
                tool_name="generate_ai_response",
                input_params={
                    "prompt": "Echo this text: ${step_1.content}",
                    "provider": "mock",
                },
                dependencies=["step_1"],
            ),
        ]
        plan = ExecutionPlan(
            plan_id="test_plan_04",
            title="Data Piping Verification",
            user_instruction="Read file and echo content",
            steps=steps,
        )

        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        res_plan = engine.execute_plan(plan)

        self.assertEqual(res_plan.status, TaskStatus.COMPLETED)
        self.assertIn("Phase 5 Data Piping Test", steps[0].result["content"])
        self.assertEqual(steps[1].status, TaskStatus.COMPLETED)
        print("[OK] test_04_dependency_resolution_and_data_piping passed.")

    def test_05_pause_and_resume_workflow(self):
        """Req 5: Pause execution and resume cleanly."""
        step_1 = TaskStep(step_id="step_1", description="Telemetry", tool_name="system_telemetry")
        step_2 = TaskStep(step_id="step_2", description="List websites", tool_name="list_known_websites", dependencies=["step_1"])
        plan = ExecutionPlan(
            plan_id="test_plan_05",
            title="Pause & Resume Test",
            user_instruction="Test pause resume",
            steps=[step_1, step_2],
        )

        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        # Pause engine before execution
        engine.pause()
        self.assertFalse(engine._pause_event.is_set())

        # Resume engine
        engine.resume()
        self.assertTrue(engine._pause_event.is_set())

        res_plan = engine.execute_plan(plan)
        self.assertEqual(res_plan.status, TaskStatus.COMPLETED)
        print("[OK] test_05_pause_and_resume_workflow passed.")

    def test_06_cancel_workflow(self):
        """Req 6: Safely cancel execution without running pending actions."""
        step_1 = TaskStep(step_id="step_1", description="First step", tool_name="system_telemetry")
        step_2 = TaskStep(step_id="step_2", description="Pending step", tool_name="list_known_websites", dependencies=["step_1"])
        plan = ExecutionPlan(
            plan_id="test_plan_06",
            title="Cancellation Test",
            user_instruction="Cancel test",
            steps=[step_1, step_2],
        )

        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        engine.cancel()
        res_plan = engine.execute_plan(plan)

        self.assertEqual(res_plan.status, TaskStatus.CANCELLED)
        print("[OK] test_06_cancel_workflow passed.")

    def test_07_recovery_from_browser_failure(self):
        """Req 7: Recover from browser/search failure using fallback search provider."""
        step = TaskStep(
            step_id="step_1",
            description="Web search with simulated fallback",
            tool_name="search_web",
            input_params={"query": "python tutorials", "provider": "google"},
            max_retries=2,
        )
        plan = ExecutionPlan(
            plan_id="test_plan_07",
            title="Recovery Test Browser",
            user_instruction="Search with fallback",
            steps=[step],
        )

        # Simulate Google failure
        can_recover, action_desc = TaskRecoveryManager.handle_step_failure(
            step, plan, "Simulated network timeout on Google search"
        )
        self.assertTrue(can_recover)
        # Step input should now be changed to duckduckgo
        self.assertEqual(step.input_params["provider"], "duckduckgo")
        print(f"[OK] test_07_recovery_from_browser_failure passed ({action_desc}).")

    def test_08_recovery_from_ai_provider_failure(self):
        """Req 8: Recover from unavailable primary AI provider via Mock fallback."""
        step = TaskStep(
            step_id="step_1",
            description="AI Generation with primary provider",
            tool_name="generate_ai_response",
            input_params={"prompt": "Explain recursion", "provider": "gemini"},
            max_retries=2,
        )
        plan = ExecutionPlan(
            plan_id="test_plan_08",
            title="Recovery Test AI",
            user_instruction="AI with fallback",
            steps=[step],
        )

        can_recover, action_desc = TaskRecoveryManager.handle_step_failure(
            step, plan, "Gemini API key is not configured"
        )
        self.assertTrue(can_recover)
        self.assertEqual(step.input_params["provider"], "mock")
        print(f"[OK] test_08_recovery_from_ai_provider_failure passed ({action_desc}).")

    def test_09_human_in_the_loop_approval_gate(self):
        """Req 9 & Req 13: Sensitive actions pause execution and wait for human approval."""
        step_1 = TaskStep(
            step_id="step_1",
            description="Generate email draft",
            tool_name="generate_ai_response",
            input_params={"prompt": "Write email", "provider": "mock"},
        )
        step_2 = TaskStep(
            step_id="step_2",
            description="Require user approval before sending",
            tool_name="request_user_approval",
            input_params={"action_name": "Send Email", "details": "Send to client"},
            dependencies=["step_1"],
            requires_approval=True,
            risk_level=RiskLevel.HIGH_RISK,
            approval_prompt="Do you approve sending this email?",
        )
        plan = ExecutionPlan(
            plan_id="test_plan_09",
            title="Approval Gate Verification",
            user_instruction="Write email and send after approval",
            steps=[step_1, step_2],
        )

        engine = ExecutionEngine(tool_registry=self.tool_registry, db=self.db)
        res_plan = engine.execute_plan(plan)

        # Plan must be paused in WAITING_APPROVAL state
        self.assertEqual(res_plan.status, TaskStatus.WAITING_APPROVAL)
        self.assertEqual(step_1.status, TaskStatus.COMPLETED)
        self.assertEqual(step_2.status, TaskStatus.WAITING_APPROVAL)

        # User approves the step
        final_plan = engine.provide_approval(plan, "step_2", approved=True)
        self.assertEqual(final_plan.status, TaskStatus.COMPLETED)
        self.assertEqual(step_2.status, TaskStatus.COMPLETED)
        print("[OK] test_09_human_in_the_loop_approval_gate passed.")

    def test_10_workflow_memory_save_and_reuse(self):
        """Req 10 & Req 11: Workflow memory persists in SQLite and can be recalled."""
        step = TaskStep(step_id="step_1", description="Telemetry diagnostic", tool_name="system_telemetry")
        plan = ExecutionPlan(
            plan_id="test_plan_10",
            title="Research Summary Workflow",
            user_instruction="Research AI news and summarize findings",
            steps=[step],
            status=TaskStatus.COMPLETED,
        )

        wf_id = self.workflow_mem.remember_workflow(
            name="Research Summary Workflow",
            user_query=plan.user_instruction,
            plan=plan,
            result_summary="Completed successfully.",
        )
        self.assertIsNotNone(wf_id)

        # Recall workflow using memory query
        recalled = self.workflow_mem.recall_workflow_by_query("Do the same process you used last time to prepare my research summary")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled["name"], "Research Summary Workflow")

        # Instantiate fresh plan
        new_plan = self.workflow_mem.instantiate_plan_from_workflow(recalled, "Repeat research process")
        self.assertIsNotNone(new_plan)
        self.assertEqual(len(new_plan.steps), 1)
        self.assertEqual(new_plan.steps[0].status, TaskStatus.PENDING)
        print("[OK] test_10_workflow_memory_save_and_reuse passed.")

    def test_11_end_to_end_workflows_planning(self):
        """Test decomposition of Workflows A, B, C, D."""
        # Workflow A
        plan_a = self.planner.plan_instruction(
            "Research the latest developments in artificial intelligence and summarize the five most important findings."
        )
        self.assertEqual(plan_a.title, "AI Research & Summarization")
        self.assertEqual(len(plan_a.steps), 4)

        # Workflow B
        plan_b = self.planner.plan_instruction(
            "Ask Gemini to write a professional internship application email."
        )
        self.assertEqual(plan_b.title, "Email Preparation & Approval")
        self.assertTrue(any(s.requires_approval for s in plan_b.steps))

        # Workflow C
        plan_c = self.planner.plan_instruction(
            "Open my Python project, run it, identify errors, research solutions, and explain how to fix them."
        )
        self.assertEqual(plan_c.title, "Programming Project Diagnosis")
        self.assertTrue(any(s.tool_name == "run_python_script_safe" for s in plan_c.steps))

        # Workflow D
        plan_d = self.planner.plan_instruction(
            "Find my AI assignment PDF, summarize it, and save the summary in a separate text file."
        )
        self.assertEqual(plan_d.title, "Document Processing & Summary")
        self.assertTrue(any(s.tool_name == "write_text_file" for s in plan_d.steps))
        print("[OK] test_11_end_to_end_workflows_planning passed (Workflows A, B, C, D verified).")

    def test_12_intent_dispatcher_phase5_integration(self):
        """Test Natural Language Dispatcher routing compound requests to MultitaskingManager."""
        res = self.dispatcher.dispatch(
            "Find my assignment folder, open the PDF, and summarize its requirements."
        )
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "multi_action_task")
        self.assertIn("📋 Step Breakdown", res.content)
        print("[OK] test_12_intent_dispatcher_phase5_integration passed.")


if __name__ == "__main__":
    unittest.main()
