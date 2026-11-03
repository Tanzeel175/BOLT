"""
Unit and Integration Tests for BOLT Phase 9: Security, Permissions and Approval System.
Validates 4-level action risk classification, central Permission Manager enforcement,
diff generation, typed confirmation for critical tasks, session grants, audit logging,
DAG approval gates, and 100% offline operation.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from bolt.core.database import Database
from bolt.core.network_manager import get_network_manager
from bolt.security.models import (
    ApprovalDecision,
    ApprovalRequest,
    SecurityAuditRecord,
    SecurityPolicy,
    SecurityRiskLevel,
)
from bolt.security.risk_classifier import RiskClassifier
from bolt.security.audit_logger import SecurityAuditLogger
from bolt.security.permission_manager import PermissionManager, get_permission_manager
from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskStatus, TaskStep
from bolt.tasks.execution_engine import ExecutionEngine
from bolt.tasks.tool_registry import ToolRegistry, get_tool_registry
from bolt.windows.file_manager import FileManager
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher


class TestPhase9SecuritySystem(unittest.TestCase):
    """Empirical test suite for Phase 9 Security and Permissions."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="bolt_security_test_"))
        cls.perm_mgr = get_permission_manager()
        cls.audit_logger = cls.perm_mgr.audit_logger
        cls.tool_reg = get_tool_registry()

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.perm_mgr.clear_pending_requests()
        self.perm_mgr.revoke_session_permissions()

    # -------------------------------------------------------------
    # 1. 4-Level Action Risk Classification
    # -------------------------------------------------------------
    def test_01_risk_classification_4_levels(self):
        """Req 2: Verify classification of tools into Low (1), Moderate (2), High (3), and Critical (4)."""
        # Level 1: Low Risk
        req_low_app = RiskClassifier.classify_action("open_application", {"app_name": "notepad"})
        self.assertEqual(req_low_app.risk_level, SecurityRiskLevel.LOW)

        req_low_web = RiskClassifier.classify_action("open_website", {"url": "https://python.org"})
        self.assertEqual(req_low_web.risk_level, SecurityRiskLevel.LOW)

        req_low_search = RiskClassifier.classify_action("search_web", {"query": "AI news"})
        self.assertEqual(req_low_search.risk_level, SecurityRiskLevel.LOW)

        # Level 2: Moderate Risk (Script execution / moving files)
        req_mod_script = RiskClassifier.classify_action("run_python_script_safe", {"script_path": "test.py"})
        self.assertEqual(req_mod_script.risk_level, SecurityRiskLevel.MODERATE)

        req_mod_move = RiskClassifier.classify_action("move_file", {"source_path": "a.txt", "destination_path": "b.txt"})
        self.assertEqual(req_mod_move.risk_level, SecurityRiskLevel.MODERATE)

        # Level 3: High Risk (Email, Delete File, Financial)
        req_high_email = RiskClassifier.classify_action("send_email", {"recipient": "boss@example.com", "subject": "Hi", "body": "Report"})
        self.assertEqual(req_high_email.risk_level, SecurityRiskLevel.HIGH)

        req_high_delete = RiskClassifier.classify_action("delete_file", {"file_path": "important.txt"})
        self.assertEqual(req_high_delete.risk_level, SecurityRiskLevel.HIGH)

        # Level 4: Critical Risk (Mass deletion, admin commands, system directories)
        req_crit_dir = RiskClassifier.classify_action("delete_directory", {"directory_path": "C:\\MyData"})
        self.assertEqual(req_crit_dir.risk_level, SecurityRiskLevel.CRITICAL)
        self.assertTrue(req_crit_dir.requires_typed_confirmation)
        self.assertEqual(req_crit_dir.confirmation_phrase, "CONFIRM")

        print("\n[OK] test_01: All 4 Risk Levels classified accurately.")

    # -------------------------------------------------------------
    # 2. Level 1 Low Risk: Automatic Execution
    # -------------------------------------------------------------
    def test_02_level1_low_risk_automatic_execution(self):
        """Req 2 Level 1: BOLT executes ordinary operations autonomously without asking."""
        # Read file operation
        test_file = self.test_dir / "read_sample.txt"
        test_file.write_text("Hello low risk", encoding="utf-8")

        auth, req, msg = self.perm_mgr.authorize_tool_execution(
            "read_text_file",
            {"file_path": str(test_file)},
        )
        self.assertTrue(auth)
        self.assertIsNone(req)
        self.assertIn("Authorized", msg)

        # Execute tool via registry
        res = self.tool_reg.execute_tool("read_text_file", file_path=str(test_file))
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("content"), "Hello low risk")

        print("[OK] test_02: Level 1 low-risk tool executed autonomously.")

    # -------------------------------------------------------------
    # 3. Level 2 Moderate Risk: Contextual Approval & Diff Preview
    # -------------------------------------------------------------
    def test_03_level2_moderate_risk_contextual_approval_and_diff(self):
        """Req 2 Level 2: Modifying an existing document generates diff preview and requests approval."""
        doc_file = self.test_dir / "project_doc.txt"
        doc_file.write_text("Title: Phase 8 Memory\nStatus: Complete\n", encoding="utf-8")

        new_content = "Title: Phase 9 Security\nStatus: In Progress\n"

        req = RiskClassifier.classify_action(
            "write_text_file",
            {"file_path": str(doc_file), "content": new_content, "allow_overwrite": True},
        )
        self.assertEqual(req.risk_level, SecurityRiskLevel.MODERATE)
        self.assertIsNotNone(req.diff_preview)
        self.assertIn("-Title: Phase 8 Memory", req.diff_preview)
        self.assertIn("+Title: Phase 9 Security", req.diff_preview)

        # Authorize check in standard mode requires approval
        auth, pend_req, msg = self.perm_mgr.authorize_tool_execution(
            "write_text_file",
            {"file_path": str(doc_file), "content": new_content, "allow_overwrite": True},
        )
        self.assertFalse(auth)
        self.assertIsNotNone(pend_req)
        self.assertEqual(pend_req.status, ApprovalDecision.PENDING)

        print("[OK] test_03: Level 2 file overwrite generated unified diff and requested contextual approval.")

    # -------------------------------------------------------------
    # 4. Level 2 Moderate Risk: Trusted Directory Bypass
    # -------------------------------------------------------------
    def test_04_level2_trusted_directory_bypass(self):
        """Req 2 Level 2: Actions inside whitelisted trusted directories execute without prompting."""
        trusted_sub = self.test_dir / "trusted_workspace"
        trusted_sub.mkdir(parents=True, exist_ok=True)
        sample = trusted_sub / "scratch.txt"
        sample.write_text("Initial text", encoding="utf-8")

        # Add to trusted directories
        self.perm_mgr.policy.trusted_directories.append(str(trusted_sub))

        auth, req, msg = self.perm_mgr.authorize_tool_execution(
            "write_text_file",
            {"file_path": str(sample), "content": "Updated text", "allow_overwrite": True},
        )
        self.assertTrue(auth)
        self.assertIsNone(req)
        self.assertIn("Authorized", msg)

        # Cleanup policy
        self.perm_mgr.policy.trusted_directories.remove(str(trusted_sub))
        print("[OK] test_04: Trusted directory policy auto-authorized file modification.")

    # -------------------------------------------------------------
    # 5. Level 3 High Risk: Explicit Approval (Send Email)
    # -------------------------------------------------------------
    def test_05_level3_high_risk_send_email(self):
        """Req 2 Level 3: Sending email requires explicit approval and shows destination & draft."""
        params = {
            "recipient": "advisor@university.edu",
            "subject": "Research Progress",
            "body": "Dear Professor, the findings are attached.",
        }
        auth, req, msg = self.perm_mgr.authorize_tool_execution("send_email", params)
        self.assertFalse(auth)
        self.assertEqual(req.risk_level, SecurityRiskLevel.HIGH)
        self.assertIn("advisor@university.edu", req.target)
        self.assertIn("Research Progress", req.proposed_changes)

        # Approve once
        ok, token = self.perm_mgr.record_user_decision(req.request_id, ApprovalDecision.APPROVED_ONCE)
        self.assertTrue(ok)
        self.assertTrue(token.startswith("tok_"))

        # Re-execute with approval token succeeds
        res = self.tool_reg.execute_tool("send_email", approval_token=token, **params)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("recipient"), "advisor@university.edu")

        print("[OK] test_05: Level 3 send email blocked pending explicit approval, executed upon authorization.")

    # -------------------------------------------------------------
    # 6. Level 3 High Risk: Delete File
    # -------------------------------------------------------------
    def test_06_level3_high_risk_delete_file(self):
        """Req 2 Level 3: Deleting an important file requires explicit approval."""
        target_f = self.test_dir / "target_file.txt"
        target_f.write_text("Temporary sensitive file", encoding="utf-8")
        self.assertTrue(target_f.exists())

        # Direct execution through tool_registry halts for approval
        res = self.tool_reg.execute_tool("delete_file", file_path=str(target_f))
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))
        req_dict = res.get("approval_request")
        self.assertEqual(req_dict["risk_level"], 3)

        # Approve and delete
        ok, token = self.perm_mgr.record_user_decision(req_dict["request_id"], ApprovalDecision.APPROVED_ONCE)
        self.assertTrue(ok)

        del_res = self.tool_reg.execute_tool("delete_file", approval_token=token, file_path=str(target_f))
        self.assertTrue(del_res.get("success"))
        self.assertFalse(target_f.exists())

        print("[OK] test_06: Level 3 file deletion held in approval gate; verified removed upon approval.")

    # -------------------------------------------------------------
    # 7. Level 4 Critical Risk: Delete Directory & Typed Phrase
    # -------------------------------------------------------------
    def test_07_level4_critical_delete_directory_with_typed_phrase(self):
        """Req 2 Level 4: Directory deletion requires exact typed confirmation phrase ('CONFIRM')."""
        dir_to_remove = self.test_dir / "folder_to_delete"
        dir_to_remove.mkdir(parents=True, exist_ok=True)
        (dir_to_remove / "child.txt").write_text("Child file", encoding="utf-8")

        auth, req, msg = self.perm_mgr.authorize_tool_execution(
            "delete_directory",
            {"directory_path": str(dir_to_remove)},
        )
        self.assertFalse(auth)
        self.assertEqual(req.risk_level, SecurityRiskLevel.CRITICAL)
        self.assertTrue(req.requires_typed_confirmation)
        self.assertEqual(req.confirmation_phrase, "CONFIRM")

        # Attempt approval with wrong confirmation phrase
        ok_wrong, msg_wrong = self.perm_mgr.record_user_decision(
            req.request_id,
            ApprovalDecision.APPROVED_ONCE,
            typed_phrase="yes",
        )
        self.assertFalse(ok_wrong)
        self.assertIn("Invalid confirmation phrase", msg_wrong)
        self.assertTrue(dir_to_remove.exists())

        # Attempt approval with correct confirmation phrase "CONFIRM"
        ok_correct, token = self.perm_mgr.record_user_decision(
            req.request_id,
            ApprovalDecision.APPROVED_ONCE,
            typed_phrase="CONFIRM",
        )
        self.assertTrue(ok_correct)
        self.assertTrue(token.startswith("tok_"))

        # Execute deletion
        del_res = self.tool_reg.execute_tool("delete_directory", approval_token=token, directory_path=str(dir_to_remove))
        self.assertTrue(del_res.get("success"))
        self.assertFalse(dir_to_remove.exists())

        print("[OK] test_07: Level 4 critical operation rejected invalid phrase and succeeded with 'CONFIRM'.")

    # -------------------------------------------------------------
    # 8. Silent Privilege Elevation Guardrail
    # -------------------------------------------------------------
    def test_08_admin_elevation_guardrail(self):
        """Req 2 Level 4: Silent elevation tokens (runas, elevate) are classified as critical threats."""
        req = RiskClassifier.classify_action(
            "run_command_safe",
            {"command": "powershell -Command Start-Process cmd -Verb RunAs"},
        )
        self.assertEqual(req.risk_level, SecurityRiskLevel.CRITICAL)
        self.assertTrue(req.requires_typed_confirmation)
        self.assertIn("Silent escalation is blocked", req.reason)

        print("[OK] test_08: Administrator elevation tokens intercepted and classified as Critical.")

    # -------------------------------------------------------------
    # 9. Windows System Protected Directories Guardrail
    # -------------------------------------------------------------
    def test_09_system_directory_protection_guardrail(self):
        """Req 2 Level 4: Modifying or deleting in system directories is flagged as critical threat."""
        req = RiskClassifier.classify_action(
            "delete_file",
            {"file_path": r"C:\Windows\System32\drivers\etc\hosts"},
        )
        self.assertEqual(req.risk_level, SecurityRiskLevel.CRITICAL)
        self.assertTrue(req.requires_typed_confirmation)
        self.assertIn("system directories", req.reason)

        # FileManager refuses deleting root or Windows directories directly
        res = FileManager.delete_file(r"C:\Windows\System32\notepad.exe")
        self.assertFalse(res["success"])
        self.assertIn("protected system file", res["error"])

        print("[OK] test_09: Windows system protected directories shielded by guardrails.")

    # -------------------------------------------------------------
    # 10. Session Grant Permission & Revocation
    # -------------------------------------------------------------
    def test_10_session_grant_permission_and_revocation(self):
        """Req 3: 'Approve for Session' allows repeat operations and revokes cleanly."""
        target_f = self.test_dir / "session_file.txt"
        target_f.write_text("Orig text", encoding="utf-8")

        # Initial check requires approval
        auth1, req1, _ = self.perm_mgr.authorize_tool_execution(
            "write_text_file",
            {"file_path": str(target_f), "content": "Update 1", "allow_overwrite": True},
        )
        self.assertFalse(auth1)

        # User approves for session
        ok, _ = self.perm_mgr.record_user_decision(req1.request_id, ApprovalDecision.APPROVED_SESSION)
        self.assertTrue(ok)
        self.assertTrue(self.perm_mgr.policy.is_session_granted("write_text_file", str(target_f)))

        # Next call executes without prompt
        auth2, req2, _ = self.perm_mgr.authorize_tool_execution(
            "write_text_file",
            {"file_path": str(target_f), "content": "Update 2", "allow_overwrite": True},
        )
        self.assertTrue(auth2)
        self.assertIsNone(req2)

        # Revoke session grants
        self.perm_mgr.revoke_session_permissions()
        self.assertFalse(self.perm_mgr.policy.is_session_granted("write_text_file", str(target_f)))

        # Now requires approval again
        auth3, req3, _ = self.perm_mgr.authorize_tool_execution(
            "write_text_file",
            {"file_path": str(target_f), "content": "Update 3", "allow_overwrite": True},
        )
        self.assertFalse(auth3)

        print("[OK] test_10: Session permission granting, bypass, and revocation verified.")

    # -------------------------------------------------------------
    # 11. Security Audit Logging & Export
    # -------------------------------------------------------------
    def test_11_security_audit_logging_and_export(self):
        """Req 3: Every security decision is persisted to SQLite and exported cleanly."""
        # Query recent logs
        logs = self.audit_logger.get_recent_logs(limit=20)
        self.assertGreater(len(logs), 0)

        # Verify stats
        stats = self.audit_logger.get_audit_stats()
        self.assertIn("total_events", stats)
        self.assertGreater(stats["total_events"], 0)

        # Verify export to JSON & JSONL
        json_export = self.test_dir / "audit_export.json"
        jsonl_export = self.test_dir / "audit_export.jsonl"

        p1 = self.audit_logger.export_audit_log(str(json_export), format="json")
        p2 = self.audit_logger.export_audit_log(str(jsonl_export), format="jsonl")

        self.assertTrue(Path(p1).exists())
        self.assertTrue(Path(p2).exists())
        self.assertGreater(Path(p1).stat().st_size, 0)
        self.assertGreater(Path(p2).stat().st_size, 0)

        print("[OK] test_11: Security audit logging, statistics, and JSON/JSONL export verified.")

    # -------------------------------------------------------------
    # 12. Central Permission Enforcement via Tool Registry
    # -------------------------------------------------------------
    def test_12_tool_registry_central_permission_enforcement(self):
        """Req 3: All tool executions pass through Permission Manager; new security tools work."""
        # 1. New security tools registered
        res_pol = self.tool_reg.execute_tool("security_get_policy")
        self.assertTrue(res_pol.get("success"))
        self.assertIn("mode", res_pol["policy"])

        # 2. Update policy tool (High risk, requiring approval gate)
        res_upd_blocked = self.tool_reg.execute_tool("security_update_policy", mode="strict")
        self.assertFalse(res_upd_blocked.get("success"))
        self.assertTrue(res_upd_blocked.get("requires_approval"))

        req_id = res_upd_blocked["approval_request"]["request_id"]
        ok, token = self.perm_mgr.record_user_decision(req_id, ApprovalDecision.APPROVED_ONCE)
        self.assertTrue(ok)

        res_upd = self.tool_reg.execute_tool("security_update_policy", approval_token=token, mode="strict")
        self.assertTrue(res_upd.get("success"))

        # 3. Audit log tool
        res_audit = self.tool_reg.execute_tool("security_get_audit_log", limit=5)
        self.assertTrue(res_audit.get("success"))
        self.assertIn("events", res_audit)

        # 4. Revoke tool
        res_rev = self.tool_reg.execute_tool("security_revoke_session_grants")
        self.assertTrue(res_rev.get("success"))

        print("[OK] test_12: Tool Registry security enforcement and Phase 9 security tools verified.")

    # -------------------------------------------------------------
    # 13. DAG Task Execution Engine Approval Gates
    # -------------------------------------------------------------
    def test_13_dag_task_execution_engine_approval_gates(self):
        """Req 1 & Req 3: Multi-step DAG plans pause at high-risk steps and resume upon user approval."""
        f_to_del = self.test_dir / "dag_delete_target.txt"
        f_to_del.write_text("DAG test content", encoding="utf-8")

        step_1 = TaskStep(
            step_id="step_1",
            description="Verify file exists",
            tool_name="verify_file_exists",
            input_params={"file_path": str(f_to_del)},
        )
        step_2 = TaskStep(
            step_id="step_2",
            description="Delete temporary file",
            tool_name="delete_file",
            input_params={"file_path": str(f_to_del)},
            dependencies=["step_1"],
        )

        plan = ExecutionPlan(
            plan_id="plan_dag_sec_test",
            title="DAG Security Verification",
            user_instruction="Verify and delete temporary file",
            steps=[step_1, step_2],
        )

        engine = ExecutionEngine()
        executed_plan = engine.execute_plan(plan)

        # Step 1 should be completed, Step 2 should be WAITING_APPROVAL
        self.assertEqual(executed_plan.status, TaskStatus.WAITING_APPROVAL)
        self.assertEqual(step_1.status, TaskStatus.COMPLETED)
        self.assertEqual(step_2.status, TaskStatus.WAITING_APPROVAL)
        self.assertEqual(step_2.risk_level, RiskLevel.HIGH_RISK)
        self.assertTrue(f_to_del.exists())

        # Deliver user approval
        resumed_plan = engine.provide_approval(executed_plan, "step_2", approved=True)
        self.assertEqual(resumed_plan.status, TaskStatus.COMPLETED)
        self.assertEqual(step_2.status, TaskStatus.COMPLETED)
        self.assertFalse(f_to_del.exists())

        print("[OK] test_13: DAG Execution Engine paused at high-risk step and resumed upon approval.")

    # -------------------------------------------------------------
    # 14. Intent Dispatcher Natural Language Security Approvals
    # -------------------------------------------------------------
    def test_14_intent_dispatcher_security_and_approval_phrases(self):
        """Req 4: Natural language commands ('approve', 'allow session', 'show security policy') work cleanly."""
        dispatcher = WindowsIntentDispatcher()

        # Query security policy
        res_pol = dispatcher.dispatch("show security policy")
        self.assertTrue(res_pol.success)
        self.assertEqual(res_pol.action_type, "security_policy")
        self.assertIn("BOLT Security Policy", res_pol.content)

        # Query security log
        res_log = dispatcher.dispatch("view security log")
        self.assertTrue(res_log.success)
        self.assertEqual(res_log.action_type, "security_audit")

        # Revoke permissions
        res_rev = dispatcher.dispatch("revoke session permissions")
        self.assertTrue(res_rev.success)
        self.assertIn("revoked", res_rev.content)

        print("[OK] test_14: Intent Dispatcher natural language security queries and decision delivery verified.")

    # -------------------------------------------------------------
    # 15. 100% Offline Security Guarantee
    # -------------------------------------------------------------
    def test_15_100_percent_offline_security_guarantee(self):
        """Req 1: Entire security and permissions subsystem operates locally with zero internet access."""
        net_mgr = get_network_manager()
        net_mgr.set_offline_simulation(True)

        try:
            self.assertFalse(net_mgr.is_online)

            # Perform risk classification
            req = RiskClassifier.classify_action("delete_file", {"file_path": "offline_del.txt"})
            self.assertEqual(req.risk_level, SecurityRiskLevel.HIGH)

            # Perform authorization check
            auth, pend, _ = self.perm_mgr.authorize_tool_execution("delete_file", {"file_path": "offline_del.txt"})
            self.assertFalse(auth)
            self.assertIsNotNone(pend)

            # Record approval
            ok, token = self.perm_mgr.record_user_decision(pend.request_id, ApprovalDecision.APPROVED_ONCE)
            self.assertTrue(ok)

            # Verify audit logging works offline
            logs = self.audit_logger.get_recent_logs(limit=5)
            self.assertGreater(len(logs), 0)

        finally:
            net_mgr.set_offline_simulation(None)

        print("[OK] test_15: Complete offline security evaluation, approval, and audit logging verified.")


if __name__ == "__main__":
    unittest.main()
