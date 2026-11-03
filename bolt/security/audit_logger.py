"""
Security Audit Logger for BOLT (Phase 9).
Provides immutable persistence of every security check, permission decision,
approval, rejection, and policy block to SQLite and rotating log files.
"""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from bolt.config.constants import DATA_DIR, LOGS_DIR
from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger
from bolt.security.models import ApprovalDecision, SecurityAuditRecord, SecurityRiskLevel

logger = get_logger("SecurityAuditLogger")


class SecurityAuditLogger:
    """Manages recording and querying security audit logs."""

    def __init__(self, db: Optional[Database] = None, log_file: Optional[Path] = None):
        self.db = db or get_database()
        self.log_file = log_file or (LOGS_DIR / "security.log")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the security_audit_logs table if not exists."""
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_audit_logs (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        risk_level INTEGER NOT NULL,
                        target TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        details TEXT,
                        user_confirmed INTEGER DEFAULT 0
                    );
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_security_audit_timestamp
                    ON security_audit_logs(timestamp);
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_security_audit_risk
                    ON security_audit_logs(risk_level);
                    """
                )
        except Exception as e:
            logger.error(f"Failed to initialize security audit schema: {e}")
        finally:
            conn.close()

    def log_event(self, record: SecurityAuditRecord) -> None:
        """Persist security event to SQLite and rotating audit log file."""
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO security_audit_logs (
                        id, timestamp, action, tool_name, risk_level, target, decision, reason, details, user_confirmed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        record.record_id,
                        record.timestamp,
                        record.action,
                        record.tool_name,
                        int(record.risk_level),
                        record.target,
                        record.decision.value,
                        record.reason,
                        record.details,
                        1 if record.user_confirmed else 0,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to write security audit to DB: {e}")
        finally:
            conn.close()

        # Append to security.log
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                log_line = (
                    f"[{record.timestamp}] [{record.risk_level.label}] "
                    f"[{record.decision.value.upper()}] tool='{record.tool_name}' "
                    f"target='{record.target}' reason='{record.reason}' confirmed={record.user_confirmed}\n"
                )
                f.write(log_line)
        except Exception as e:
            logger.warning(f"Failed appending to security log file: {e}")

    def get_recent_logs(
        self,
        limit: int = 50,
        risk_level: Optional[SecurityRiskLevel] = None,
        decision: Optional[ApprovalDecision] = None,
    ) -> List[SecurityAuditRecord]:
        """Query recent security records with optional filtering."""
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM security_audit_logs"
            params: List[Any] = []
            clauses = []

            if risk_level is not None:
                clauses.append("risk_level = ?")
                params.append(int(risk_level))
            if decision is not None:
                clauses.append("decision = ?")
                params.append(decision.value)

            if clauses:
                query += " WHERE " + " AND ".join(clauses)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [SecurityAuditRecord.from_row(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed querying security audit logs: {e}")
            return []
        finally:
            conn.close()

    def get_audit_stats(self) -> Dict[str, Any]:
        """Return summary statistics of security decisions."""
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM security_audit_logs;")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT decision, COUNT(*) FROM security_audit_logs GROUP BY decision;")
            by_decision = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT risk_level, COUNT(*) FROM security_audit_logs GROUP BY risk_level;")
            by_risk = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_events": total,
                "decisions": by_decision,
                "risk_levels": by_risk,
            }
        except Exception as e:
            logger.error(f"Failed gathering audit stats: {e}")
            return {"total_events": 0, "decisions": {}, "risk_levels": {}}
        finally:
            conn.close()

    def export_audit_log(self, output_path: Optional[str] = None, format: str = "json") -> str:
        """Export all security logs to a local JSON or JSONL file."""
        records = self.get_recent_logs(limit=1000)
        data = [r.to_dict() for r in records]

        if not output_path:
            out_file = DATA_DIR / f"security_audit_export.{format}"
        else:
            out_file = Path(output_path).expanduser().resolve()

        out_file.parent.mkdir(parents=True, exist_ok=True)
        if format.lower() == "jsonl":
            with open(out_file, "w", encoding="utf-8") as f:
                for d in data:
                    f.write(json.dumps(d) + "\n")
        else:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        logger.info(f"Exported {len(data)} security audit records to {out_file}")
        return str(out_file)


_AUDIT_LOGGER: Optional[SecurityAuditLogger] = None


def get_security_audit_logger() -> SecurityAuditLogger:
    global _AUDIT_LOGGER
    if _AUDIT_LOGGER is None:
        _AUDIT_LOGGER = SecurityAuditLogger()
    return _AUDIT_LOGGER

