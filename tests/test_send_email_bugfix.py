"""
Unit and integration tests for the BOLT send_email bug fix.

Verifies:
1. Unconfigured send_email handler returns success: False, status: "not_configured",
   and error: "Email sending is not configured. No email was sent."
2. The handler never returns status: "sent" or fake success confirmations.
3. Existing permission checks and user approval mechanisms (Level 3 High Risk) are preserved.
4. Execution through ToolRegistry without approval requires human approval.
5. Execution with approval executes the handler and reports failure cleanly without fake delivery.
6. The DAG ExecutionEngine and TaskPlanner recognize that the email step failed and mark the plan FAILED.
7. TaskRecoveryManager does not misclassify configuration failure as transient.
8. No real emails or network connections are made during testing.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bolt.tasks.tool_registry import ToolRegistry, get_tool_registry
from bolt.security.permission_manager import get_permission_manager, ApprovalDecision
from bolt.security.models import SecurityRiskLevel
from bolt.tasks.models import ExecutionPlan, TaskStep, TaskStatus, RiskLevel
from bolt.tasks.execution_engine import ExecutionEngine
from bolt.tasks.recovery_manager import TaskRecoveryManager


class TestSendEmailBugFix(unittest.TestCase):
    def setUp(self):
        self.tool_reg = get_tool_registry()
        self.perm_mgr = get_permission_manager()
        self.perm_mgr.revoke_session_permissions()

    def tearDown(self):
        self.perm_mgr.revoke_session_permissions()

    def test_01_handler_direct_returns_not_configured(self):
        """Direct call to _send_email_handler must return success=False, status='not_configured', and specific error."""
        res = self.tool_reg._send_email_handler(
            recipient="client@example.com",
            subject="Quarterly Invoice",
            body="Please find invoice attached.",
        )
        self.assertFalse(res.get("success"), "Handler must return success=False when unconfigured.")
        self.assertEqual(res.get("status"), "not_configured")
        self.assertEqual(
            res.get("error"),
            "Email sending is not configured. No email was sent.",
        )
        self.assertEqual(res.get("recipient"), "client@example.com")
        self.assertEqual(res.get("subject"), "Quarterly Invoice")
        self.assertNotEqual(res.get("status"), "sent", "Handler must NEVER report status='sent'.")
        self.assertNotIn("Successfully sent", str(res), "No fake delivery confirmation message permitted.")

    def test_02_tool_registry_registration(self):
        """Tool registry must have send_email registered with expected parameter schema."""
        tool = self.tool_reg._tools.get("send_email")
        self.assertIsNotNone(tool, "send_email must be registered in ToolRegistry.")
        params = tool["parameters"]
        self.assertIn("recipient", params["properties"])
        self.assertIn("subject", params["properties"])
        self.assertIn("body", params["properties"])
        self.assertEqual(set(params["required"]), {"recipient", "subject", "body"})

    def test_03_permission_check_preserved_level3_high_risk(self):
        """Calling send_email without approval must be intercepted by Level 3 High Risk gate."""
        payload = {
            "recipient": "partner@venture.com",
            "subject": "Confidential Term Sheet",
            "body": "Terms outlined below.",
        }
        auth, req, msg = self.perm_mgr.authorize_tool_execution("send_email", payload)
        self.assertFalse(auth, "Must not be pre-authorized without explicit user decision.")
        self.assertIsNotNone(req)
        self.assertEqual(req.risk_level, SecurityRiskLevel.HIGH)
        self.assertEqual(req.status, ApprovalDecision.PENDING)
        self.assertIn("partner@venture.com", req.target)
        self.assertIn("Confidential Term Sheet", req.proposed_changes)

    def test_04_execute_tool_without_token_requires_approval(self):
        """Executing send_email via execute_tool without approval token halts with approval request."""
        res = self.tool_reg.execute_tool(
            "send_email",
            recipient="test@example.org",
            subject="Hello",
            body="Test message",
        )
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))
        self.assertTrue(res.get("waiting_for_user"))
        self.assertIn("approval_request", res)

    def test_05_execute_tool_with_token_reports_not_configured(self):
        """Executing send_email with approval token passes security gate, but returns not_configured."""
        payload = {
            "recipient": "director@company.com",
            "subject": "Monthly Summary",
            "body": "Report body.",
        }
        # Step 1: Request authorization
        auth, req, _ = self.perm_mgr.authorize_tool_execution("send_email", payload)
        self.assertFalse(auth)

        # Step 2: User approves once
        ok, token = self.perm_mgr.record_user_decision(req.request_id, ApprovalDecision.APPROVED_ONCE)
        self.assertTrue(ok)
        self.assertTrue(token.startswith("tok_"))

        # Step 3: Re-execute with token
        res = self.tool_reg.execute_tool("send_email", approval_token=token, **payload)
        self.assertFalse(res.get("requires_approval", False), "Security check should pass with valid token.")
        self.assertFalse(res.get("blocked", False), "Should not be blocked by policy.")
        self.assertFalse(res.get("success"), "Unconfigured handler must return success=False.")
        self.assertEqual(res.get("status"), "not_configured")
        self.assertEqual(res.get("error"), "Email sending is not configured. No email was sent.")
        self.assertNotEqual(res.get("status"), "sent")

    def test_06_execution_engine_records_failure_and_understands_email_not_sent(self):
        """ExecutionEngine executing a send_email step pauses for approval, then upon approval marks step FAILED and plan FAILED."""
        plan_id = "test_plan_email_failure"
        step = TaskStep(
            step_id="step_send",
            description="Send email notification",
            tool_name="send_email",
            input_params={
                "recipient": "ops@infra.net",
                "subject": "Server Alert",
                "body": "CPU usage spike detected.",
            },
            expected_output="Email delivery confirmation",
            risk_level=RiskLevel.HIGH_RISK,
        )
        plan = ExecutionPlan(
            plan_id=plan_id,
            title="Notification Workflow",
            user_instruction="Send server alert email to ops@infra.net",
            steps=[step],
        )

        engine = ExecutionEngine(tool_registry=self.tool_reg)
        engine.execute_plan(plan)

        # 1. Step initially pauses waiting for approval
        self.assertEqual(step.status, TaskStatus.WAITING_APPROVAL)
        self.assertEqual(plan.status, TaskStatus.WAITING_APPROVAL)

        # 2. User grants approval to proceed
        engine.provide_approval(plan, "step_send", approved=True)

        # 3. Upon execution, the step must fail cleanly because email is not configured
        self.assertNotEqual(step.status, TaskStatus.COMPLETED)
        self.assertEqual(step.status, TaskStatus.FAILED)
        self.assertEqual(step.error, "Email sending is not configured. No email was sent.")
        self.assertEqual(plan.status, TaskStatus.FAILED)
        self.assertIsNone(step.completed_at)

    def test_07_recovery_manager_does_not_retry_configuration_error(self):
        """TaskRecoveryManager must not misclassify configuration failure as transient or retryable."""
        step = TaskStep(
            step_id="s1",
            description="Send Email",
            tool_name="send_email",
            input_params={"recipient": "a@b.com", "subject": "Hi", "body": "Msg"},
        )
        plan = ExecutionPlan(
            plan_id="p1",
            title="Plan",
            user_instruction="send email",
            steps=[step],
        )

        can_recover, desc = TaskRecoveryManager.handle_step_failure(
            step, plan, "Email sending is not configured. No email was sent."
        )
        self.assertFalse(can_recover, "Configuration error must be permanent and not retried.")
        self.assertEqual(step.status, TaskStatus.FAILED)
        self.assertIn("permanently failed", desc.lower())


if __name__ == "__main__":
    unittest.main()
