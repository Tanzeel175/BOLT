"""Multitasking Manager and Subsystem Coordinator for BOLT (Phase 5)."""

from typing import Any, Dict, List, Optional
from bolt.browser.browser_controller import BrowserController, get_browser_controller
from bolt.core.logger import get_logger
from bolt.tasks.execution_engine import ExecutionEngine, TaskExecutionWorker
from bolt.tasks.models import ExecutionPlan, TaskStatus
from bolt.tasks.planner import TaskPlanner, get_task_planner
from bolt.tasks.workflow_memory import WorkflowMemory, get_workflow_memory
from bolt.windows.app_controller import AppController, get_app_controller
from bolt.windows.file_manager import FileManager
from bolt.windows.window_manager import WindowManager, get_window_manager

logger = get_logger("MultitaskingManager")


class MultitaskingManager:
    """Coordinates Windows apps, Playwright browser sessions, AI providers, and Task Plans."""

    def __init__(
        self,
        planner: Optional[TaskPlanner] = None,
        app_ctrl: Optional[AppController] = None,
        win_mgr: Optional[WindowManager] = None,
        browser_ctrl: Optional[BrowserController] = None,
        workflow_mem: Optional[WorkflowMemory] = None,
    ):
        self.planner = planner or get_task_planner()
        self.app_ctrl = app_ctrl or get_app_controller()
        self.win_mgr = win_mgr or get_window_manager()
        self.browser_ctrl = browser_ctrl or get_browser_controller()
        self.workflow_mem = workflow_mem or get_workflow_memory()

        self._active_workers: Dict[str, TaskExecutionWorker] = {}
        self.last_active_plan: Optional[ExecutionPlan] = None

    def plan_and_execute_sync(self, instruction: str, conversation_id: Optional[str] = None) -> ExecutionPlan:
        """Synchronously plan and execute an instruction (ideal for unit testing and headless execution)."""
        plan = self.planner.plan_instruction(instruction)
        self.last_active_plan = plan
        engine = ExecutionEngine(workflow_memory=self.workflow_mem)
        executed_plan = engine.execute_plan(plan, conversation_id=conversation_id)
        self.last_active_plan = executed_plan
        return executed_plan

    def provide_user_decision(
        self,
        approved: bool,
        user_response: Optional[str] = None,
        session_grant: bool = False,
        typed_phrase: Optional[str] = None,
    ) -> Optional[ExecutionPlan]:
        """Deliver user's approval or rejection response to the currently waiting plan."""
        if not self.last_active_plan or self.last_active_plan.status != TaskStatus.WAITING_APPROVAL:
            return None

        # Find waiting step
        waiting_steps = [s for s in self.last_active_plan.steps if s.status == TaskStatus.WAITING_APPROVAL]
        if not waiting_steps:
            return None

        step = waiting_steps[0]
        engine = ExecutionEngine(workflow_memory=self.workflow_mem)
        executed_plan = engine.provide_approval(
            self.last_active_plan,
            step.step_id,
            approved=approved,
            user_response=user_response,
            session_grant=session_grant,
            typed_phrase=typed_phrase,
        )
        self.last_active_plan = executed_plan
        return executed_plan

    def create_execution_worker(
        self,
        instruction: str,
        conversation_id: Optional[str] = None,
    ) -> TaskExecutionWorker:
        """Create an asynchronous QThread worker for PySide6 GUI multitasking."""
        plan = self.planner.plan_instruction(instruction)
        worker = TaskExecutionWorker(plan=plan, conversation_id=conversation_id)
        self._active_workers[plan.plan_id] = worker

        # Auto cleanup on finish
        worker.plan_completed.connect(lambda pid, p: self._active_workers.pop(pid, None))
        return worker

    def get_active_worker(self, plan_id: str) -> Optional[TaskExecutionWorker]:
        return self._active_workers.get(plan_id)

    def pause_execution(self, plan_id: Optional[str] = None) -> bool:
        """Pause active task worker(s) or plan."""
        paused_any = False
        if plan_id and plan_id in self._active_workers:
            self._active_workers[plan_id].pause_task()
            return True
        for worker in self._active_workers.values():
            worker.pause_task()
            paused_any = True
        if self.last_active_plan and self.last_active_plan.status == TaskStatus.IN_PROGRESS:
            self.last_active_plan.status = TaskStatus.PENDING
            paused_any = True
        return paused_any

    def resume_execution(self, plan_id: Optional[str] = None) -> bool:
        """Resume active task worker(s) or plan."""
        resumed_any = False
        if plan_id and plan_id in self._active_workers:
            self._active_workers[plan_id].resume_task()
            return True
        for worker in self._active_workers.values():
            worker.resume_task()
            resumed_any = True
        return resumed_any

    def cancel_execution(self, plan_id: Optional[str] = None) -> bool:
        """Cancel active task worker(s) or plan."""
        cancelled_any = False
        if plan_id and plan_id in self._active_workers:
            self._active_workers[plan_id].cancel_task()
            return True
        for worker in self._active_workers.values():
            worker.cancel_task()
            cancelled_any = True
        if self.last_active_plan and self.last_active_plan.status in (TaskStatus.IN_PROGRESS, TaskStatus.WAITING_APPROVAL):
            self.last_active_plan.status = TaskStatus.CANCELLED
            cancelled_any = True
        return cancelled_any

    @staticmethod
    def format_plan_summary_markdown(plan: ExecutionPlan) -> str:
        """Format an execution report in clean GitHub-style Markdown."""
        status_icons = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.PARTIALLY_COMPLETED: "⚠️",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "⏹️",
            TaskStatus.WAITING_APPROVAL: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.PENDING: "⚪",
            TaskStatus.SKIPPED: "⏭️",
        }

        icon = status_icons.get(plan.status, "📋")
        md = [
            f"### {icon} Task Execution: {plan.title}\n",
            f"**Status:** `{plan.status.value.upper()}` • **Progress:** {plan.progress_percentage()}%\n",
            f"**Original Request:** *\"{plan.user_instruction}\"*\n\n",
            "#### 📋 Step Breakdown:\n",
        ]

        for s in plan.steps:
            s_icon = status_icons.get(s.status, "⚪")
            app_tag = f" `[{s.active_application}]`" if s.active_application else ""
            res_preview = ""
            if s.result:
                if isinstance(s.result, dict) and "message" in s.result:
                    res_preview = f" — *{s.result['message']}*"
                elif isinstance(s.result, dict) and "content" in s.result:
                    preview_text = s.result["content"][:120].replace("\n", " ").strip()
                    res_preview = f" — *\"{preview_text}...\"*"

            err_tag = f"\n  - ⚠️ *Error:* `{s.error}`" if s.error else ""
            md.append(f"- {s_icon} **{s.description}**{app_tag}{res_preview}{err_tag}")

        # Check if plan is waiting for approval
        waiting_steps = [s for s in plan.steps if s.status == TaskStatus.WAITING_APPROVAL]
        if waiting_steps:
            w = waiting_steps[0]
            md.append("\n\n> ⏳ **Action Required:** " + (w.approval_prompt or f"Please approve: {w.description}"))
            md.append("\n> *Reply `yes` / `approve` to proceed or `no` / `cancel` to reject.*")

        return "\n".join(md)


_COORDINATOR_INSTANCE: Optional[MultitaskingManager] = None


def get_multitasking_manager() -> MultitaskingManager:
    global _COORDINATOR_INSTANCE
    if _COORDINATOR_INSTANCE is None:
        _COORDINATOR_INSTANCE = MultitaskingManager()
    return _COORDINATOR_INSTANCE
