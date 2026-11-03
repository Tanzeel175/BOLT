"""Task Recovery and Fault Tolerance Manager for BOLT (Phase 5)."""

from typing import Any, Dict, Optional, Tuple
from bolt.core.logger import get_logger
from bolt.tasks.models import ExecutionPlan, TaskStatus, TaskStep

logger = get_logger("RecoveryManager")


class TaskRecoveryManager:
    """Handles automatic retries, alternative fallback tools, and decision escalations for failed steps."""

    @staticmethod
    def handle_step_failure(
        step: TaskStep,
        plan: ExecutionPlan,
        error_msg: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate failure and determine next action.
        Returns:
            (can_recover: bool, recovery_action_description: Optional[str])
        """
        step.error = error_msg
        step.retry_count += 1
        logger.warning(
            f"Step '{step.step_id}' ({step.tool_name}) failed (Attempt {step.retry_count}/{step.max_retries}): {error_msg}"
        )

        # 1. Check for alternative fallback methods first (e.g. switch search engine or AI provider)
        fallback_applied, desc = TaskRecoveryManager._apply_fallback_route(step)
        if fallback_applied:
            step.status = TaskStatus.PENDING
            step.error = None
            return True, desc

        # 2. Check if eligible for direct retry on transient network/system faults
        if step.retry_count <= step.max_retries:
            is_transient = any(
                term in error_msg.lower()
                for term in ["timeout", "connection", "network", "busy", "temporary", "page.goto", "lock"]
            )
            if is_transient:
                step.status = TaskStatus.PENDING
                step.error = None
                return True, f"Retrying step '{step.step_id}' (attempt {step.retry_count}/{step.max_retries}) after transient fault."

        # 3. Cannot auto-recover; mark failed and preserve prior completed steps
        step.status = TaskStatus.FAILED
        plan.status = TaskStatus.FAILED
        return False, f"Step '{step.step_id}' permanently failed: {error_msg}"

    @staticmethod
    def _apply_fallback_route(step: TaskStep) -> Tuple[bool, Optional[str]]:
        """Try an alternative provider, search engine, or tool."""
        # A. Web Search Fallback: Google -> DuckDuckGo -> Bing
        if step.tool_name == "search_web":
            current_prov = step.input_params.get("provider", "google")
            if current_prov == "google":
                step.input_params["provider"] = "duckduckgo"
                return True, "Switching web search engine fallback to DuckDuckGo."
            elif current_prov == "duckduckgo":
                step.input_params["provider"] = "bing"
                return True, "Switching web search engine fallback to Bing."

        # B. AI Provider Fallback: Gemini -> OpenAI -> Ollama -> Mock
        elif step.tool_name == "generate_ai_response":
            current_ai = step.input_params.get("provider", "")
            if current_ai in ("gemini", "openai"):
                step.input_params["provider"] = "ollama"
                return True, "Switching AI generation fallback to Local Ollama Brain."
            elif current_ai == "ollama":
                step.input_params["provider"] = "mock"
                return True, "Switching AI generation fallback to Local Mock Engine."
            elif current_ai != "mock":
                step.input_params["provider"] = "mock"
                return True, "Switching AI generation fallback to Local Mock Engine."

        # C. File Search Fallback: expand search directory if query had a strict folder
        elif step.tool_name == "search_files":
            if not step.input_params.get("broad_search"):
                step.input_params["broad_search"] = True
                step.input_params["max_results"] = 20
                return True, "Broadening file search across user home directory."

        # D. Application Launch Fallback: uninstalled IDE or browser fallback
        elif step.tool_name == "open_application":
            app_req = step.input_params.get("app_name", "").lower()
            if any(b in app_req for b in ["chrome", "brave", "firefox"]) and app_req != "msedge":
                step.input_params["app_name"] = "Microsoft Edge"
                return True, "Target browser not found; falling back to Microsoft Edge."
            elif any(e in app_req for e in ["code", "vscode", "pycharm", "sublime"]) and app_req != "notepad":
                step.input_params["app_name"] = "Notepad"
                return True, "Target code editor not installed; falling back to Windows Notepad."

        return False, None
