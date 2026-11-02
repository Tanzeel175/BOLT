"""Data models for BOLT Task Planning, Dependencies, and Multitasking (Phase 5)."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid

from bolt.core.database import utc_now_iso


class TaskStatus(str, Enum):
    """Execution status for tasks and individual steps."""
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    """Risk tier for tool executions governing approval gates."""
    LOW = "low"                        # Automatic execution (opening apps/sites, searching, reading)
    APPROVAL_REQUIRED = "approval"      # Important file mods, script runs, deletion
    HIGH_RISK = "high_risk"            # Always require explicit confirmation (emails, purchases, forms)


@dataclass
class TaskStep:
    """A discrete executable action within a structured ExecutionPlan."""
    step_id: str
    description: str
    tool_name: str
    input_params: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    approval_prompt: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    active_application: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool_name": self.tool_name,
            "input_params": self.input_params,
            "expected_output": self.expected_output,
            "dependencies": self.dependencies,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "requires_approval": self.requires_approval,
            "approval_prompt": self.approval_prompt,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "active_application": self.active_application,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStep":
        raw_status = data.get("status", "pending")
        raw_risk = data.get("risk_level", "low")
        status = TaskStatus(raw_status) if raw_status in [s.value for s in TaskStatus] else TaskStatus.PENDING
        risk = RiskLevel(raw_risk) if raw_risk in [r.value for r in RiskLevel] else RiskLevel.LOW

        return cls(
            step_id=data.get("step_id", f"step_{uuid.uuid4().hex[:6]}"),
            description=data.get("description", ""),
            tool_name=data.get("tool_name", ""),
            input_params=data.get("input_params", {}),
            expected_output=data.get("expected_output", ""),
            dependencies=data.get("dependencies", []),
            status=status,
            risk_level=risk,
            requires_approval=data.get("requires_approval", False),
            approval_prompt=data.get("approval_prompt"),
            result=data.get("result"),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 2),
            active_application=data.get("active_application", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class ExecutionPlan:
    """Directed Acyclic Graph (DAG) plan of steps representing a multi-action user goal."""
    plan_id: str
    title: str
    user_instruction: str
    steps: List[TaskStep] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    workflow_template_id: Optional[str] = None

    def get_step(self, step_id: str) -> Optional[TaskStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_ready_steps(self) -> List[TaskStep]:
        """Return all pending steps whose prerequisite dependencies are completed."""
        ready: List[TaskStep] = []
        completed_step_ids = {s.step_id for s in self.steps if s.status == TaskStatus.COMPLETED}

        for step in self.steps:
            if step.status == TaskStatus.PENDING:
                if all(dep in completed_step_ids for dep in step.dependencies):
                    ready.append(step)
        return ready

    def is_completed(self) -> bool:
        """Check if all non-skipped steps are completed."""
        if not self.steps:
            return False
        return all(s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for s in self.steps)

    def is_failed(self) -> bool:
        """Check if all non-skipped steps have failed or no progress was made."""
        if not self.steps:
            return False
        has_any_completed = any(s.status == TaskStatus.COMPLETED for s in self.steps)
        all_done = all(s.status in (TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.CANCELLED) for s in self.steps)
        return all_done and not has_any_completed

    def has_failures(self) -> bool:
        return any(s.status == TaskStatus.FAILED for s in self.steps)

    def has_successes(self) -> bool:
        return any(s.status == TaskStatus.COMPLETED for s in self.steps)

    def progress_percentage(self) -> float:
        """Calculate overall percentage of completed steps."""
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED))
        return round((done / len(self.steps)) * 100.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "user_instruction": self.user_instruction,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "workflow_template_id": self.workflow_template_id,
            "progress_percent": self.progress_percentage(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        raw_status = data.get("status", "pending")
        status = TaskStatus(raw_status) if raw_status in [s.value for s in TaskStatus] else TaskStatus.PENDING

        steps = [TaskStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            title=data.get("title", "Task Execution Plan"),
            user_instruction=data.get("user_instruction", ""),
            steps=steps,
            status=status,
            created_at=data.get("created_at", utc_now_iso()),
            completed_at=data.get("completed_at"),
            workflow_template_id=data.get("workflow_template_id"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionPlan":
        return cls.from_dict(json.loads(json_str))


@dataclass
class TaskProgressUpdate:
    """Telemetry payload emitted during multi-action plan execution for UI rendering."""
    plan_id: str
    title: str
    status: TaskStatus
    current_step_id: str
    current_step_desc: str
    completed_steps: int
    total_steps: int
    progress_percent: float
    active_application: str
    waiting_reason: Optional[str] = None
    error_message: Optional[str] = None

