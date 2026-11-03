"""
Security and Permission Data Models for BOLT (Phase 9).
Defines 4-level action risk classification, approval requests, audit records,
and security policies.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from bolt.core.database import utc_now_iso


class SecurityRiskLevel(IntEnum):
    """
    4-Tier Action Risk Classification for BOLT.
    Level 1: Low Risk - Execute automatically without prompt.
    Level 2: Moderate Risk - Contextual approval (file edits, script runs, moving files).
    Level 3: High Risk - Explicit approval required (emails, file deletes, purchases, external data).
    Level 4: Critical Risk - Strong confirmation with typed confirmation phrase (mass delete, admin commands, security alterations).
    """
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        names = {
            1: "LOW RISK (Level 1)",
            2: "MODERATE RISK (Level 2)",
            3: "HIGH RISK (Level 3)",
            4: "CRITICAL RISK (Level 4)",
        }
        return names.get(self.value, f"LEVEL {self.value}")

    @property
    def color(self) -> str:
        colors = {
            1: "#3fb950",  # Green
            2: "#d29922",  # Yellow/Gold
            3: "#f0883e",  # Orange
            4: "#f85149",  # Red
        }
        return colors.get(self.value, "#c9d1d9")

    @classmethod
    def from_string(cls, val: str) -> "SecurityRiskLevel":
        v = val.lower().strip()
        if v in ("low", "1", "level 1", "level_1"):
            return cls.LOW
        if v in ("moderate", "approval", "approval_required", "2", "level 2", "level_2"):
            return cls.MODERATE
        if v in ("high", "high_risk", "3", "level 3", "level_3"):
            return cls.HIGH
        if v in ("critical", "critical_risk", "4", "level 4", "level_4"):
            return cls.CRITICAL
        return cls.LOW


class ApprovalDecision(str, Enum):
    """Possible outcomes for an approval request."""
    PENDING = "pending"
    APPROVED_ONCE = "approved_once"
    APPROVED_SESSION = "approved_session"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Detailed approval request object presented to the user or task engine."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    action_type: str = ""
    risk_level: SecurityRiskLevel = SecurityRiskLevel.LOW
    target: str = ""
    reason: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    proposed_changes: Optional[str] = None
    diff_preview: Optional[str] = None
    requires_typed_confirmation: bool = False
    confirmation_phrase: Optional[str] = None
    status: ApprovalDecision = ApprovalDecision.PENDING
    created_at: str = field(default_factory=utc_now_iso)
    decided_at: Optional[str] = None
    user_response: Optional[str] = None

    def is_approved(self) -> bool:
        return self.status in (ApprovalDecision.APPROVED_ONCE, ApprovalDecision.APPROVED_SESSION)

    def format_display_markdown(self) -> str:
        """Format a clear, GitHub-style Markdown security approval card."""
        badge_icon = {
            SecurityRiskLevel.LOW: "🟢",
            SecurityRiskLevel.MODERATE: "🟡",
            SecurityRiskLevel.HIGH: "🟠",
            SecurityRiskLevel.CRITICAL: "🔴",
        }.get(self.risk_level, "🛡️")

        lines = [
            f"### {badge_icon} Security Approval Required: `{self.risk_level.label}`\n",
            f"- **Action:** `{self.tool_name}` ({self.action_type or 'Operation'})",
            f"- **Target:** `{self.target or 'System'}`",
            f"- **Reason:** {self.reason}",
        ]

        # Target parameters summary
        if self.parameters:
            filtered_params = {k: v for k, v in self.parameters.items() if k not in ("content", "password", "api_key")}
            if filtered_params:
                lines.append(f"- **Parameters:** `{json.dumps(filtered_params)}`")

        # Proposed changes or diff preview
        if self.diff_preview:
            lines.append("\n**Proposed Changes (Diff):**\n```diff\n" + self.diff_preview.strip() + "\n```")
        elif self.proposed_changes:
            preview = self.proposed_changes[:500] + ("..." if len(self.proposed_changes) > 500 else "")
            lines.append(f"\n**Proposed Content / Preview:**\n```\n{preview}\n```")

        # Confirmation instruction
        lines.append("\n---")
        if self.requires_typed_confirmation:
            lines.append(
                f"> ⚠️ **CRITICAL ACTION:** This action is irreversible or high-impact.\n"
                f"> Type **`{self.confirmation_phrase or 'CONFIRM'}`** to authorize this operation, or reply `reject` to abort."
            )
        else:
            lines.append(
                "> **Options:** Reply `approve` / `yes` to execute once, `allow session` to remember for this task, or `reject` to cancel."
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "action_type": self.action_type,
            "risk_level": int(self.risk_level),
            "risk_label": self.risk_level.label,
            "target": self.target,
            "reason": self.reason,
            "parameters": self.parameters,
            "proposed_changes": self.proposed_changes,
            "diff_preview": self.diff_preview,
            "requires_typed_confirmation": self.requires_typed_confirmation,
            "confirmation_phrase": self.confirmation_phrase,
            "status": self.status.value,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "user_response": self.user_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        risk_val = data.get("risk_level", 1)
        if isinstance(risk_val, int):
            risk = SecurityRiskLevel(risk_val)
        else:
            risk = SecurityRiskLevel.from_string(str(risk_val))

        status_val = data.get("status", "pending")
        status = ApprovalDecision(status_val) if status_val in [d.value for d in ApprovalDecision] else ApprovalDecision.PENDING

        return cls(
            request_id=data.get("request_id", str(uuid.uuid4())),
            tool_name=data.get("tool_name", ""),
            action_type=data.get("action_type", ""),
            risk_level=risk,
            target=data.get("target", ""),
            reason=data.get("reason", ""),
            parameters=data.get("parameters", {}),
            proposed_changes=data.get("proposed_changes"),
            diff_preview=data.get("diff_preview"),
            requires_typed_confirmation=data.get("requires_typed_confirmation", False),
            confirmation_phrase=data.get("confirmation_phrase"),
            status=status,
            created_at=data.get("created_at", utc_now_iso()),
            decided_at=data.get("decided_at"),
            user_response=data.get("user_response"),
        )


@dataclass
class SecurityAuditRecord:
    """Audit log entry capturing every security evaluation, authorization, or block."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)
    action: str = ""
    tool_name: str = ""
    risk_level: SecurityRiskLevel = SecurityRiskLevel.LOW
    target: str = ""
    decision: ApprovalDecision = ApprovalDecision.PENDING
    reason: str = ""
    details: str = ""
    user_confirmed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "tool_name": self.tool_name,
            "risk_level": int(self.risk_level),
            "risk_label": self.risk_level.label,
            "target": self.target,
            "decision": self.decision.value,
            "reason": self.reason,
            "details": self.details,
            "user_confirmed": self.user_confirmed,
        }

    @classmethod
    def from_row(cls, row: Any) -> "SecurityAuditRecord":
        d = dict(row)
        risk_raw = d.get("risk_level", 1)
        try:
            risk = SecurityRiskLevel(int(risk_raw))
        except (ValueError, TypeError):
            risk = SecurityRiskLevel.LOW

        dec_raw = d.get("decision", "pending")
        decision = ApprovalDecision(dec_raw) if dec_raw in [x.value for x in ApprovalDecision] else ApprovalDecision.PENDING

        return cls(
            record_id=d.get("id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", utc_now_iso()),
            action=d.get("action", ""),
            tool_name=d.get("tool_name", ""),
            risk_level=risk,
            target=d.get("target", ""),
            decision=decision,
            reason=d.get("reason", ""),
            details=d.get("details", ""),
            user_confirmed=bool(d.get("user_confirmed", 0)),
        )


@dataclass
class SecurityPolicy:
    """Active security configuration and permission boundaries for BOLT."""
    mode: str = "standard"  # "standard", "strict", "autonomous"
    trusted_directories: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    require_typed_confirmation: bool = True
    session_grants: Dict[str, float] = field(default_factory=dict)  # grant_key -> expires_at_unix

    def is_session_granted(self, tool_name: str, target: Optional[str] = None) -> bool:
        """Check if an active, unexpired session grant covers this tool and target."""
        now = time.time()
        # General tool grant
        keys_to_check = [f"tool:{tool_name}"]
        if target:
            clean_target = target.strip().lower()
            keys_to_check.append(f"tool_target:{tool_name}:{clean_target}")

        for k in keys_to_check:
            exp = self.session_grants.get(k)
            if exp and exp > now:
                return True
        return False

    def add_session_grant(self, tool_name: str, target: Optional[str] = None, duration_seconds: float = 3600.0) -> str:
        """Grant temporary approval for a tool/target in this session."""
        now = time.time()
        if target:
            clean_target = target.strip().lower()
            key = f"tool_target:{tool_name}:{clean_target}"
        else:
            key = f"tool:{tool_name}"
        self.session_grants[key] = now + duration_seconds
        return key

    def clear_session_grants(self) -> None:
        """Revoke all session grants."""
        self.session_grants.clear()

    def is_path_trusted(self, path_str: str) -> bool:
        """Check if a file or directory is in the trusted directories list."""
        if not path_str:
            return False
        clean = path_str.strip().lower().replace("/", "\\")
        for td in self.trusted_directories:
            td_clean = td.strip().lower().replace("/", "\\")
            if clean.startswith(td_clean):
                return True
        return False
