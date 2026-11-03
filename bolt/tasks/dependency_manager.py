"""Task Dependency Management and Output Pipeline for BOLT (Phase 5)."""

import re
from typing import Any, Dict, List, Set
from bolt.core.logger import get_logger
from bolt.tasks.models import ExecutionPlan, TaskStatus, TaskStep

logger = get_logger("DependencyManager")


class DependencyManager:
    """Validates DAG constraints, identifies executable steps, and resolves step output piping."""

    @staticmethod
    def validate_plan_dag(plan: ExecutionPlan) -> bool:
        """Validate that steps form an acyclic dependency graph without dangling dependencies."""
        step_ids = {s.step_id for s in plan.steps}

        # Check for non-existent dependencies
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    logger.error(f"Step '{step.step_id}' references unknown dependency: '{dep}'")
                    return False

        # Cycle detection using topological sort / DFS
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def has_cycle(step_id: str) -> bool:
            visiting.add(step_id)
            step = plan.get_step(step_id)
            if step:
                for dep in step.dependencies:
                    if dep in visiting:
                        return True
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
            visiting.remove(step_id)
            visited.add(step_id)
            return False

        for s in plan.steps:
            if s.step_id not in visited:
                if has_cycle(s.step_id):
                    logger.error(f"Circular dependency detected in plan: {plan.plan_id}")
                    return False
        return True

    @staticmethod
    def get_executable_steps(plan: ExecutionPlan) -> List[TaskStep]:
        """Return pending steps whose prerequisite dependencies have all completed successfully."""
        ready: List[TaskStep] = []
        completed_step_ids = {
            s.step_id for s in plan.steps if s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        }

        for step in plan.steps:
            if step.status == TaskStatus.PENDING:
                if all(dep in completed_step_ids for dep in step.dependencies):
                    ready.append(step)
        return ready

    @staticmethod
    def resolve_step_inputs(step: TaskStep, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Substitute placeholder tokens like '${step_1.result}' or '${step_1.content}'
        with actual evaluated outputs from preceding completed steps.
        """
        resolved: Dict[str, Any] = {}

        for key, val in step.input_params.items():
            if isinstance(val, str) and "${" in val:
                resolved[key] = DependencyManager._substitute_tokens(val, plan)
            elif isinstance(val, list):
                resolved[key] = [
                    DependencyManager._substitute_tokens(item, plan) if isinstance(item, str) else item
                    for item in val
                ]
            elif isinstance(val, dict):
                resolved[key] = {
                    k: DependencyManager._substitute_tokens(v, plan) if isinstance(v, str) else v
                    for k, v in val.items()
                }
            else:
                resolved[key] = val

        return resolved

    @staticmethod
    def _substitute_tokens(text: str, plan: ExecutionPlan) -> Any:
        """Resolve '${step_id.attribute}' pattern to actual object or string replacement."""
        pattern = r"\$\{([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\}"
        matches = list(re.finditer(pattern, text))
        if not matches:
            return text

        # If the entire string is exactly a token (e.g. "${step_1.result}"), return the raw object
        if len(matches) == 1 and matches[0].group(0) == text:
            dep_id = matches[0].group(1)
            attr = matches[0].group(2)
            dep_step = plan.get_step(dep_id)
            if not dep_step or dep_step.result is None:
                return text
            if attr:
                if isinstance(dep_step.result, dict):
                    if attr in dep_step.result:
                        return dep_step.result[attr]
                    for fb in ("content", "result", "summary", "text", "message"):
                        if fb in dep_step.result:
                            return dep_step.result[fb]
                    return text
                elif isinstance(dep_step.result, str) and attr in ("content", "result", "summary", "text"):
                    return dep_step.result
                elif hasattr(dep_step.result, attr):
                    return getattr(dep_step.result, attr, text)
            return dep_step.result

        # Otherwise perform string substitution
        result_str = text
        for m in matches:
            token = m.group(0)
            dep_id = m.group(1)
            attr = m.group(2)
            dep_step = plan.get_step(dep_id)
            replacement = ""
            if dep_step and dep_step.result is not None:
                if attr and isinstance(dep_step.result, dict):
                    val = dep_step.result.get(attr)
                    if val is None:
                        for fb in ("content", "result", "summary", "text", "message"):
                            if fb in dep_step.result:
                                val = dep_step.result[fb]
                                break
                    replacement = str(val or "")
                elif attr and isinstance(dep_step.result, str) and attr in ("content", "result", "summary", "text"):
                    replacement = dep_step.result
                elif attr and hasattr(dep_step.result, attr):
                    replacement = str(getattr(dep_step.result, attr, ""))
                else:
                    replacement = str(dep_step.result)
            result_str = result_str.replace(token, replacement)

        return result_str

    @staticmethod
    def can_run_in_parallel(step_a: TaskStep, step_b: TaskStep) -> bool:
        """
        Check if two independent steps can safely run in parallel without resource conflicts.
        Mutating file writes or window focus actions should not collide.
        """
        conflicting_tools = {"switch_to_window", "write_text_file", "close_application"}
        if step_a.tool_name in conflicting_tools or step_b.tool_name in conflicting_tools:
            return False

        # Conflicting files
        file_a = step_a.input_params.get("file_path")
        file_b = step_b.input_params.get("file_path")
        if file_a and file_b and file_a == file_b:
            return False

        return True

