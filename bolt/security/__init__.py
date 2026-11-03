"""
Security and Permissions Subsystem for BOLT (Phase 9).
Provides 4-level action risk classification, centralized permission enforcement,
approval gates, typed confirmation phrases, and immutable audit logging.
"""

from bolt.security.models import (
    ApprovalDecision,
    ApprovalRequest,
    SecurityAuditRecord,
    SecurityPolicy,
    SecurityRiskLevel,
)
from bolt.security.risk_classifier import RiskClassifier
from bolt.security.audit_logger import (
    SecurityAuditLogger,
    get_security_audit_logger,
)
from bolt.security.permission_manager import (
    PermissionManager,
    get_permission_manager,
)

__all__ = [
    "SecurityRiskLevel",
    "ApprovalDecision",
    "ApprovalRequest",
    "SecurityAuditRecord",
    "SecurityPolicy",
    "RiskClassifier",
    "SecurityAuditLogger",
    "get_security_audit_logger",
    "PermissionManager",
    "get_permission_manager",
]
