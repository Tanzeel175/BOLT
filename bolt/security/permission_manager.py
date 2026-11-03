"""
Central Permission Manager for BOLT (Phase 9).
Enforces security boundaries, evaluates tool executions, manages approval gates,
validates typed confirmation phrases, and logs all audit events.
"""

from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger
from bolt.security.audit_logger import SecurityAuditLogger, get_security_audit_logger
from bolt.security.models import (
    ApprovalDecision,
    ApprovalRequest,
    SecurityAuditRecord,
    SecurityPolicy,
    SecurityRiskLevel,
)
from bolt.security.risk_classifier import RiskClassifier

logger = get_logger("PermissionManager")


class PermissionManager:
    """Central authority controlling action permissions and human approval gates."""

    def __init__(
        self,
        audit_logger: Optional[SecurityAuditLogger] = None,
        db: Optional[Database] = None,
    ):
        self.audit_logger = audit_logger or get_security_audit_logger()
        self.db = db or get_database()
        self.policy = SecurityPolicy()
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._approved_tokens: Dict[str, float] = {}  # token -> expires_at
        self._load_policy_from_db()

    def _load_policy_from_db(self) -> None:
        """Load persistent security policy configuration from DB if present."""
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_policies (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                cursor.execute("SELECT key, value FROM security_policies;")
                rows = cursor.fetchall()
                for r in rows:
                    k, v = r[0], r[1]
                    if k == "mode":
                        self.policy.mode = v
                    elif k == "trusted_directories":
                        self.policy.trusted_directories = [p.strip() for p in v.split(";") if p.strip()]
                    elif k == "blocked_tools":
                        self.policy.blocked_tools = [b.strip() for b in v.split(";") if b.strip()]
        except Exception as e:
            logger.error(f"Failed loading security policy from DB: {e}")
        finally:
            conn.close()

    def save_policy_to_db(self) -> None:
        """Persist policy configuration to DB."""
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO security_policies (key, value, updated_at)
                    VALUES ('mode', ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                    """,
                    (self.policy.mode, utc_now_iso()),
                )
                cursor.execute(
                    """
                    INSERT INTO security_policies (key, value, updated_at)
                    VALUES ('trusted_directories', ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                    """,
                    (";".join(self.policy.trusted_directories), utc_now_iso()),
                )
                cursor.execute(
                    """
                    INSERT INTO security_policies (key, value, updated_at)
                    VALUES ('blocked_tools', ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
                    """,
                    (";".join(self.policy.blocked_tools), utc_now_iso()),
                )
        except Exception as e:
            logger.error(f"Failed saving security policy to DB: {e}")
        finally:
            conn.close()

    # -------------------------------------------------------------
    # 1. Action Evaluation & Risk Assessment
    # -------------------------------------------------------------

    def evaluate_action(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """
        Evaluate tool and parameters against security rules, assigning risk level
        and determining whether approval or typed confirmation is mandatory.
        """
        req = RiskClassifier.classify_action(tool_name, params, self.policy, context)

        # 1. Check permanently blocked tools
        if tool_name in self.policy.blocked_tools:
            req.status = ApprovalDecision.BLOCKED
            req.reason = f"Tool '{tool_name}' is permanently blocked by security policy."
            return req

        # 2. Level 1: Low Risk -> Auto-approved
        if req.risk_level == SecurityRiskLevel.LOW:
            req.status = ApprovalDecision.APPROVED_ONCE
            return req

        # 3. Level 2: Moderate Risk -> Check trusted dirs and session grants
        if req.risk_level == SecurityRiskLevel.MODERATE:
            if self.policy.is_path_trusted(req.target) or self.policy.is_session_granted(tool_name, req.target):
                req.status = ApprovalDecision.APPROVED_SESSION
                return req
            # Otherwise requires contextual approval
            req.status = ApprovalDecision.PENDING
            return req

        # 4. Level 3: High Risk -> Check explicit session grant for tool & target
        if req.risk_level == SecurityRiskLevel.HIGH:
            if self.policy.is_session_granted(tool_name, req.target):
                req.status = ApprovalDecision.APPROVED_SESSION
                return req
            req.status = ApprovalDecision.PENDING
            return req

        # 5. Level 4: Critical Risk -> ALWAYS requires explicit typed confirmation. Cannot be bypassed.
        if req.risk_level == SecurityRiskLevel.CRITICAL:
            req.status = ApprovalDecision.PENDING
            req.requires_typed_confirmation = True
            if not req.confirmation_phrase:
                req.confirmation_phrase = "CONFIRM"
            return req

        return req

    # -------------------------------------------------------------
    # 2. Tool Execution Authorization Gate
    # -------------------------------------------------------------

    def authorize_tool_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        approval_token: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[ApprovalRequest], str]:
        """
        Enforce permission check before tool execution.
        Returns:
            (authorized: bool, approval_request: Optional[ApprovalRequest], message: str)
        """
        # Check approval token if passed
        now = time.time()
        if approval_token and approval_token in self._approved_tokens:
            if self._approved_tokens[approval_token] > now:
                # Valid one-time or temporary token
                return (True, None, "Authorized by approval token.")
            else:
                del self._approved_tokens[approval_token]

        req = self.evaluate_action(tool_name, params, context)

        # Handle Blocked
        if req.status == ApprovalDecision.BLOCKED:
            audit = SecurityAuditRecord(
                action=req.action_type,
                tool_name=tool_name,
                risk_level=req.risk_level,
                target=req.target,
                decision=ApprovalDecision.BLOCKED,
                reason=req.reason,
                details=str(params),
                user_confirmed=False,
            )
            self.audit_logger.log_event(audit)
            return (False, req, f"Security Violation: {req.reason}")

        # Handle Pre-approved (Low risk or active Session Grant)
        if req.is_approved():
            audit = SecurityAuditRecord(
                action=req.action_type,
                tool_name=tool_name,
                risk_level=req.risk_level,
                target=req.target,
                decision=req.status,
                reason=req.reason,
                details=str(params),
                user_confirmed=False,
            )
            self.audit_logger.log_event(audit)
            return (True, None, f"Authorized ({req.risk_level.label})")

        # Action requires user approval
        self._pending_requests[req.request_id] = req
        audit = SecurityAuditRecord(
            action=req.action_type,
            tool_name=tool_name,
            risk_level=req.risk_level,
            target=req.target,
            decision=ApprovalDecision.PENDING,
            reason=req.reason,
            details=str(params),
            user_confirmed=False,
        )
        self.audit_logger.log_event(audit)
        return (False, req, f"Approval Required: {req.reason}")

    # -------------------------------------------------------------
    # 3. User Decision Recording & Confirmation Verification
    # -------------------------------------------------------------

    def record_user_decision(
        self,
        request_id: str,
        decision: ApprovalDecision,
        typed_phrase: Optional[str] = None,
        user_note: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Process user's approval or rejection response.
        Validates typed confirmation phrases for Level 4 Critical actions.
        """
        req = self._pending_requests.get(request_id)
        if not req:
            logger.warning(f"No pending approval request found for ID: {request_id}")
            return (False, f"Approval request '{request_id}' not found or already expired.")

        # Check typed confirmation phrase for Critical Risk
        if decision in (ApprovalDecision.APPROVED_ONCE, ApprovalDecision.APPROVED_SESSION):
            if req.requires_typed_confirmation:
                expected = (req.confirmation_phrase or "CONFIRM").strip().upper()
                actual = (typed_phrase or "").strip().upper()
                if actual != expected:
                    msg = f"Invalid confirmation phrase. Required: '{expected}', provided: '{actual}'."
                    logger.warning(msg)
                    return (False, msg)

        # Update request state
        req.status = decision
        req.decided_at = utc_now_iso()
        req.user_response = typed_phrase or user_note

        # If approved for session, register session grant
        if decision == ApprovalDecision.APPROVED_SESSION:
            self.policy.add_session_grant(req.tool_name, req.target)
            logger.info(f"Granted session permission for '{req.tool_name}' on target '{req.target}'")

        # Create one-time execution token if approved
        token = None
        if decision in (ApprovalDecision.APPROVED_ONCE, ApprovalDecision.APPROVED_SESSION):
            token = f"tok_{req.request_id[:8]}"
            self._approved_tokens[token] = time.time() + 300.0  # 5 minutes validity

        # Log audit entry
        audit = SecurityAuditRecord(
            action=req.action_type,
            tool_name=req.tool_name,
            risk_level=req.risk_level,
            target=req.target,
            decision=decision,
            reason=req.reason,
            details=f"User decision: {decision.value}. Note: {user_note or ''}",
            user_confirmed=True,
        )
        self.audit_logger.log_event(audit)

        # Clean up from pending
        del self._pending_requests[request_id]
        return (True, token or decision.value)

    # -------------------------------------------------------------
    # 4. Session & Policy Management
    # -------------------------------------------------------------

    def grant_session_permission(
        self, tool_name: str, target: Optional[str] = None, duration_seconds: float = 3600.0
    ) -> str:
        """Explicitly add a session grant."""
        grant_key = self.policy.add_session_grant(tool_name, target, duration_seconds)
        audit = SecurityAuditRecord(
            action="Session Permission Granted",
            tool_name=tool_name,
            risk_level=SecurityRiskLevel.MODERATE,
            target=target or "All Targets",
            decision=ApprovalDecision.APPROVED_SESSION,
            reason=f"User explicitly granted session permission for '{tool_name}' ({duration_seconds}s).",
            user_confirmed=True,
        )
        self.audit_logger.log_event(audit)
        return grant_key

    def revoke_session_permissions(self) -> None:
        """Revoke all temporary session permissions."""
        count = len(self.policy.session_grants)
        self.policy.clear_session_grants()
        self._approved_tokens.clear()
        audit = SecurityAuditRecord(
            action="Session Permissions Revoked",
            tool_name="permission_manager",
            risk_level=SecurityRiskLevel.LOW,
            target="Session Policy",
            decision=ApprovalDecision.APPROVED_ONCE,
            reason=f"Revoked {count} active session grants.",
            user_confirmed=True,
        )
        self.audit_logger.log_event(audit)
        logger.info(f"Revoked all {count} session grants.")

    def get_pending_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._pending_requests.get(request_id)

    def get_pending_requests(self) -> List[ApprovalRequest]:
        return list(self._pending_requests.values())

    def clear_pending_requests(self) -> None:
        self._pending_requests.clear()

    def get_security_policy(self) -> SecurityPolicy:
        return self.policy

    def update_security_policy(self, updates: Dict[str, Any]) -> None:
        """Update policy attributes and persist."""
        if "mode" in updates:
            self.policy.mode = str(updates["mode"]).lower()
        if "trusted_directories" in updates:
            self.policy.trusted_directories = list(updates["trusted_directories"])
        if "blocked_tools" in updates:
            self.policy.blocked_tools = list(updates["blocked_tools"])
        self.save_policy_to_db()


_PERMISSION_MANAGER: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    global _PERMISSION_MANAGER
    if _PERMISSION_MANAGER is None:
        _PERMISSION_MANAGER = PermissionManager()
    return _PERMISSION_MANAGER

