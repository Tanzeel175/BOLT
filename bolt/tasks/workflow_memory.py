"""Workflow Memory and Reuse Subsystem for BOLT (Phase 5)."""

import json
from typing import Any, Dict, List, Optional
from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger
from bolt.tasks.models import ExecutionPlan

logger = get_logger("WorkflowMemory")


class WorkflowMemory:
    """Stores, recalls, and re-validates multi-step workflows in SQLite memory."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def remember_workflow(
        self,
        name: str,
        user_query: str,
        plan: ExecutionPlan,
        result_summary: str = "",
    ) -> str:
        """Save a successfully executed workflow for future recall."""
        # Sanitize plan to ensure no secret credentials are saved
        steps_summary = " -> ".join([s.description for s in plan.steps])
        apps_used = list({s.active_application for s in plan.steps if s.active_application})
        tools_used = list({s.tool_name for s in plan.steps})

        plan_dict = plan.to_dict()
        # Clean any raw sensitive outputs from stored plan template
        for s in plan_dict.get("steps", []):
            s["result"] = None
            s["error"] = None
            s["status"] = "pending"

        plan_json = json.dumps(plan_dict)
        wf_id = self.db.save_workflow_template(
            name=name,
            user_query=user_query,
            plan_json=plan_json,
            steps_summary=steps_summary,
            apps_used=json.dumps(apps_used),
            tools_used=json.dumps(tools_used),
            result_summary=result_summary,
            is_successful=1,
        )
        logger.info(f"Remembered workflow '{name}' (ID: {wf_id})")
        return wf_id

    def recall_workflow_by_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Look up a previously successful workflow matching user's instruction or request."""
        matches = self.db.search_workflows(query)
        if matches:
            return matches[0]

        # Check for phrase match (e.g. "same process you used last time")
        all_wf = self.db.get_all_workflows()
        if all_wf and any(k in query.lower() for k in ["same process", "last time", "repeat workflow"]):
            return all_wf[0]

        return None

    def instantiate_plan_from_workflow(
        self,
        workflow_record: Dict[str, Any],
        new_instruction: str,
    ) -> Optional[ExecutionPlan]:
        """Create a fresh ExecutionPlan from a remembered template."""
        try:
            plan_json = workflow_record.get("plan_json", "{}")
            plan = ExecutionPlan.from_json(plan_json)
            plan.user_instruction = new_instruction
            plan.workflow_template_id = workflow_record.get("id")
            for s in plan.steps:
                s.status = s.status if s.status == "pending" else s.status
                s.result = None
                s.error = None
            return plan
        except Exception as e:
            logger.error(f"Failed instantiating plan from workflow template: {e}")
            return None


_WORKFLOW_MEM_INSTANCE: Optional[WorkflowMemory] = None


def get_workflow_memory() -> WorkflowMemory:
    global _WORKFLOW_MEM_INSTANCE
    if _WORKFLOW_MEM_INSTANCE is None:
        _WORKFLOW_MEM_INSTANCE = WorkflowMemory()
    return _WORKFLOW_MEM_INSTANCE

