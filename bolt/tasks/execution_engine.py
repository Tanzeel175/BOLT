"""Task Execution Engine and Background Worker for BOLT (Phase 5)."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger
from bolt.tasks.dependency_manager import DependencyManager
from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskProgressUpdate, TaskStatus, TaskStep
from bolt.tasks.recovery_manager import TaskRecoveryManager
from bolt.tasks.tool_registry import ToolRegistry, get_tool_registry
from bolt.tasks.workflow_memory import WorkflowMemory, get_workflow_memory

logger = get_logger("ExecutionEngine")


class ExecutionEngine:
    """Core synchronous/orchestration engine executing DAG tasks with approval gates and recovery."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        db: Optional[Database] = None,
        workflow_memory: Optional[WorkflowMemory] = None,
        on_progress: Optional[Callable[[TaskProgressUpdate], None]] = None,
        on_approval_needed: Optional[Callable[[str, str, str, str], None]] = None,
    ):
        self.tool_registry = tool_registry or get_tool_registry()
        self.db = db or get_database()
        self.workflow_memory = workflow_memory or get_workflow_memory()
        self.on_progress = on_progress
        self.on_approval_needed = on_approval_needed

        self._pause_event = threading.Event()
        self._pause_event.set()  # Set = running, Clear = paused
        self._cancel_flag = False
        self._waiting_approval_step: Optional[TaskStep] = None

    def execute_plan(self, plan: ExecutionPlan, conversation_id: Optional[str] = None) -> ExecutionPlan:
        """Execute all steps in an ExecutionPlan respecting DAG dependencies and approval gates."""
        logger.info(f"Starting execution of plan: '{plan.title}' ({plan.plan_id})")
        if self._cancel_flag:
            plan.status = TaskStatus.CANCELLED
            return plan

        plan.status = TaskStatus.IN_PROGRESS
        self._pause_event.set()

        # Record in SQLite tasks table
        self.db.create_task_record(
            task_id=plan.plan_id,
            conversation_id=conversation_id,
            instruction=plan.user_instruction,
            title=plan.title,
            status=plan.status.value,
            plan_json=plan.to_json(),
        )

        while not plan.is_completed() and not plan.is_failed():
            # Check for cancellation
            if self._cancel_flag:
                logger.info(f"Execution cancelled by user for plan: {plan.plan_id}")
                plan.status = TaskStatus.CANCELLED
                break

            # Check for pause
            self._pause_event.wait()
            if self._cancel_flag:
                plan.status = TaskStatus.CANCELLED
                break

            ready_steps = plan.get_ready_steps()
            if not ready_steps:
                # No ready steps. Check if any steps are still running or waiting approval
                if plan.status == TaskStatus.WAITING_APPROVAL:
                    # Waiting for user input or approval, break execution loop until user action
                    break

                # If no steps are pending, or remaining pending steps have unmet dependencies that failed
                failed_step_ids = {s.step_id for s in plan.steps if s.status == TaskStatus.FAILED}
                for s in plan.steps:
                    if s.status == TaskStatus.PENDING and any(d in failed_step_ids for d in s.dependencies):
                        s.status = TaskStatus.SKIPPED
                        s.error = "Skipped because prerequisite step failed."

                has_pending = any(s.status == TaskStatus.PENDING for s in plan.steps)
                if has_pending:
                    logger.error("Deadlock or unmet dependencies detected in plan execution.")
                    if any(s.status == TaskStatus.COMPLETED for s in plan.steps):
                        plan.status = TaskStatus.PARTIALLY_COMPLETED
                    else:
                        plan.status = TaskStatus.FAILED
                break

            # Determine whether independent ready steps can run in parallel
            if len(ready_steps) > 1 and all(
                DependencyManager.can_run_in_parallel(ready_steps[0], ready_steps[i])
                for i in range(1, len(ready_steps))
            ):
                logger.info(f"Executing {len(ready_steps)} independent steps in parallel.")
                with ThreadPoolExecutor(max_workers=min(3, len(ready_steps))) as pool:
                    futures = {pool.submit(self._execute_single_step, s, plan): s for s in ready_steps}
                    for f in as_completed(futures):
                        f.result()
            else:
                # Execute next sequential ready step
                step = ready_steps[0]
                self._execute_single_step(step, plan)

                if plan.status == TaskStatus.WAITING_APPROVAL:
                    # Break to wait for user approval response
                    break

            # Update progress telemetry
            self._emit_progress(plan)

        # Finalize plan state
        if plan.is_completed():
            plan.status = TaskStatus.COMPLETED
            plan.completed_at = utc_now_iso()
            logger.info(f"Plan completed successfully: {plan.title}")
            # Remember successful workflow in SQLite
            self.workflow_memory.remember_workflow(
                name=plan.title,
                user_query=plan.user_instruction,
                plan=plan,
                result_summary="Completed successfully with verified deliverables.",
            )
        elif any(s.status == TaskStatus.COMPLETED for s in plan.steps) and any(s.status == TaskStatus.FAILED for s in plan.steps):
            plan.status = TaskStatus.PARTIALLY_COMPLETED
            plan.completed_at = utc_now_iso()
            logger.info(f"Plan partially completed: {plan.title} (some steps succeeded, some failed)")
        elif plan.status not in (TaskStatus.WAITING_APPROVAL, TaskStatus.CANCELLED):
            plan.status = TaskStatus.FAILED
            plan.completed_at = utc_now_iso()

        # Update final state in database
        self.db.update_task_record(
            task_id=plan.plan_id,
            status=plan.status.value,
            progress=plan.progress_percentage(),
            plan_json=plan.to_json(),
            completed_at=plan.completed_at,
        )
        self._emit_progress(plan)
        return plan

    def _execute_single_step(self, step: TaskStep, plan: ExecutionPlan) -> None:
        """Execute a single step with security evaluation, approval checking, tool execution, and error recovery."""
        from bolt.security import get_permission_manager, ApprovalDecision, SecurityRiskLevel
        perm_mgr = get_permission_manager()

        # 1. Resolve input placeholders from earlier steps to evaluate exact parameters
        resolved_inputs = DependencyManager.resolve_step_inputs(step, plan)

        # 2. Security & Risk Assessment (Phase 9)
        req = perm_mgr.evaluate_action(step.tool_name, resolved_inputs)

        # Map SecurityRiskLevel to TaskStep.risk_level
        risk_map = {
            SecurityRiskLevel.LOW: RiskLevel.LOW,
            SecurityRiskLevel.MODERATE: RiskLevel.MODERATE,
            SecurityRiskLevel.HIGH: RiskLevel.HIGH_RISK,
            SecurityRiskLevel.CRITICAL: RiskLevel.CRITICAL,
        }
        step.risk_level = risk_map.get(req.risk_level, step.risk_level)
        step.requires_typed_confirmation = req.requires_typed_confirmation
        step.confirmation_phrase = req.confirmation_phrase

        # Handle Policy Block
        if req.status == ApprovalDecision.BLOCKED:
            step.status = TaskStatus.FAILED
            step.error = f"Security Policy Block: {req.reason}"
            plan.status = TaskStatus.FAILED
            logger.error(f"Step '{step.step_id}' blocked by security policy: {req.reason}")
            return

        # 3. Approval Gate Check
        is_user_approved = getattr(step, "_approved_by_user", False)
        needs_approval = (
            not is_user_approved
            and (
                step.requires_approval
                or step.risk_level in (RiskLevel.APPROVAL_REQUIRED, RiskLevel.MODERATE, RiskLevel.HIGH_RISK, RiskLevel.CRITICAL)
            )
            and not req.is_approved()
        )

        if needs_approval:
            step.status = TaskStatus.WAITING_APPROVAL
            plan.status = TaskStatus.WAITING_APPROVAL
            self._waiting_approval_step = step
            prompt = req.format_display_markdown() if req else (step.approval_prompt or f"Action requires user approval: {step.description}")
            step.approval_prompt = prompt
            logger.info(f"Step '{step.step_id}' is waiting for user approval: {prompt}")

            # Register request under step_id for decision lookup
            perm_mgr._pending_requests[step.step_id] = req

            if self.on_approval_needed:
                self.on_approval_needed(plan.plan_id, step.step_id, step.description, prompt)
            return

        # 4. Mark in progress
        step.status = TaskStatus.IN_PROGRESS
        step.started_at = utc_now_iso()
        self._emit_progress(plan, current_step=step)

        # 5. Invoke tool handler (bypassing redundant security prompt since step was already vetted)
        logger.info(f"Executing step '{step.step_id}' ({step.tool_name})...")
        res = self.tool_registry.execute_tool(step.tool_name, bypass_security_check=True, **resolved_inputs)

        # 6. Handle Tool Result & Verification
        if res.get("success", False):
            # Check if tool itself returned a human-in-the-loop requirement
            if res.get("requires_approval") or res.get("waiting_for_user"):
                step.status = TaskStatus.WAITING_APPROVAL
                plan.status = TaskStatus.WAITING_APPROVAL
                self._waiting_approval_step = step
                setattr(step, "_tool_completed_waiting", True)
                prompt = res.get("question") or res.get("details") or step.description
                if self.on_approval_needed:
                    self.on_approval_needed(plan.plan_id, step.step_id, step.description, prompt)
                return

            step.result = res.get("result", res)
            step.status = TaskStatus.COMPLETED
            step.completed_at = utc_now_iso()
            step.error = None
            logger.info(f"Step '{step.step_id}' completed successfully.")
        else:
            err_msg = res.get("error", "Unknown tool execution failure")
            can_recover, action_desc = TaskRecoveryManager.handle_step_failure(step, plan, err_msg)
            if can_recover:
                logger.info(f"Recovery initiated for step '{step.step_id}': {action_desc}")
                # Re-try immediately
                self._execute_single_step(step, plan)
            else:
                logger.error(f"Recovery failed for step '{step.step_id}': {action_desc}")

    def provide_approval(
        self,
        plan: ExecutionPlan,
        step_id: str,
        approved: bool,
        user_response: Optional[str] = None,
        session_grant: bool = False,
        typed_phrase: Optional[str] = None,
    ) -> ExecutionPlan:
        """Deliver user's approval or rejection response and resume plan execution."""
        step = plan.get_step(step_id)
        if not step or step.status != TaskStatus.WAITING_APPROVAL:
            logger.warning(f"No step waiting for approval matching step_id: {step_id}")
            return plan

        from bolt.security import get_permission_manager, ApprovalDecision
        perm_mgr = get_permission_manager()

        if approved:
            # Check typed confirmation phrase for Critical Risk
            if step.requires_typed_confirmation:
                expected = (step.confirmation_phrase or "CONFIRM").strip().upper()
                actual = (typed_phrase or user_response or "").strip().upper()
                if actual != expected:
                    logger.warning(f"Confirmation phrase mismatch for step '{step_id}': expected '{expected}', got '{actual}'")
                    step.error = f"Incorrect confirmation phrase. You must type '{expected}'."
                    return plan

            decision = ApprovalDecision.APPROVED_SESSION if session_grant else ApprovalDecision.APPROVED_ONCE
            perm_mgr.record_user_decision(step_id, decision, typed_phrase=typed_phrase or user_response)

            logger.info(f"User APPROVED step '{step_id}' ({decision.value}). Continuing execution.")
            setattr(step, "_approved_by_user", True)
            step.requires_approval = False
            step.risk_level = RiskLevel.LOW
            if user_response:
                step.input_params["user_response"] = user_response

            if step.tool_name in ("request_user_approval", "ask_user_input") or getattr(step, "_tool_completed_waiting", False):
                step.status = TaskStatus.COMPLETED
                step.result = {"approved": True, "user_response": user_response}
                step.completed_at = utc_now_iso()
            else:
                step.status = TaskStatus.PENDING

            plan.status = TaskStatus.IN_PROGRESS
            self._waiting_approval_step = None
            return self.execute_plan(plan)
        else:
            perm_mgr.record_user_decision(step_id, ApprovalDecision.REJECTED, user_note=user_response)
            logger.info(f"User REJECTED step '{step_id}'. Marking step skipped.")
            step.status = TaskStatus.SKIPPED
            step.error = "Action rejected by user."
            plan.status = TaskStatus.IN_PROGRESS
            self._waiting_approval_step = None
            return self.execute_plan(plan)

    def pause(self) -> None:
        """Pause execution without terminating active tasks."""
        self._pause_event.clear()
        logger.info("Execution paused.")

    def resume(self) -> None:
        """Resume execution from paused state."""
        self._pause_event.set()
        logger.info("Execution resumed.")

    def cancel(self) -> None:
        """Cancel execution of future actions."""
        self._cancel_flag = True
        self._pause_event.set()
        logger.info("Execution cancellation requested.")

    def _emit_progress(self, plan: ExecutionPlan, current_step: Optional[TaskStep] = None) -> None:
        """Send progress telemetry."""
        if not self.on_progress:
            return

        active_app = current_step.active_application if current_step else ""
        step_id = current_step.step_id if current_step else ""
        step_desc = current_step.description if current_step else plan.title
        waiting_reason = current_step.approval_prompt if current_step and current_step.status == TaskStatus.WAITING_APPROVAL else None

        completed = sum(1 for s in plan.steps if s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED))
        update = TaskProgressUpdate(
            plan_id=plan.plan_id,
            title=plan.title,
            status=plan.status,
            current_step_id=step_id,
            current_step_desc=step_desc,
            completed_steps=completed,
            total_steps=len(plan.steps),
            progress_percent=plan.progress_percentage(),
            active_application=active_app,
            waiting_reason=waiting_reason,
            error_message=current_step.error if current_step else None,
        )
        self.on_progress(update)


class TaskExecutionWorker(QThread):
    """Asynchronous background worker thread running ExecutionEngine for PySide6 UI."""

    progress_updated = Signal(object)      # Emits TaskProgressUpdate
    step_started = Signal(str, str, str)   # plan_id, step_id, description
    step_completed = Signal(str, str)      # plan_id, step_id
    step_failed = Signal(str, str, str)    # plan_id, step_id, error
    approval_requested = Signal(str, str, str, str)  # plan_id, step_id, action, prompt
    plan_completed = Signal(str, object)   # plan_id, ExecutionPlan
    plan_paused = Signal(str)              # plan_id
    plan_resumed = Signal(str)             # plan_id
    plan_cancelled = Signal(str)           # plan_id

    def __init__(self, plan: ExecutionPlan, conversation_id: Optional[str] = None):
        super().__init__()
        self.plan = plan
        self.conversation_id = conversation_id
        self.engine = ExecutionEngine(
            on_progress=self._on_engine_progress,
            on_approval_needed=self._on_engine_approval,
        )

    def run(self):
        try:
            self.engine.execute_plan(self.plan, self.conversation_id)
            self.plan_completed.emit(self.plan.plan_id, self.plan)
        except Exception as e:
            logger.exception("TaskExecutionWorker encountered an unexpected error.")
            self.plan.status = TaskStatus.FAILED
            self.plan_completed.emit(self.plan.plan_id, self.plan)

    def _on_engine_progress(self, update: TaskProgressUpdate):
        self.progress_updated.emit(update)

    def _on_engine_approval(self, plan_id: str, step_id: str, action: str, prompt: str):
        self.approval_requested.emit(plan_id, step_id, action, prompt)

    def pause_task(self):
        self.engine.pause()
        self.plan_paused.emit(self.plan.plan_id)

    def resume_task(self):
        self.engine.resume()
        self.plan_resumed.emit(self.plan.plan_id)

    def cancel_task(self):
        self.engine.cancel()
        self.plan_cancelled.emit(self.plan.plan_id)

    def provide_approval(self, step_id: str, approved: bool, user_response: Optional[str] = None):
        """Resume thread after delivering approval decision."""
        self.engine.provide_approval(self.plan, step_id, approved, user_response)
        self.plan_completed.emit(self.plan.plan_id, self.plan)
