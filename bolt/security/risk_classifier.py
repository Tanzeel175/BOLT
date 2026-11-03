"""
Risk Classifier for BOLT (Phase 9).
Analyzes action types, tools, parameters, and system context to assign
one of 4 Action Risk Levels, identify target entities, detect system threats,
and generate diffs or preview changes.
"""

import difflib
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from bolt.security.models import ApprovalRequest, SecurityPolicy, SecurityRiskLevel
from bolt.windows.file_manager import FileManager

# Windows Protected System Directories that must NEVER be modified or silently elevated
SYSTEM_PROTECTED_DIRECTORIES = [
    r"c:\windows",
    r"c:\windows\system32",
    r"c:\windows\syswow64",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\programdata\microsoft\windows",
]

# Sensitive Administrator Elevation & System Destruction Tokens
ADMIN_ELEVATION_TOKENS = [
    "runas",
    "-verb runas",
    "elevate",
    "set-mppreference",
    "disable-realtime-monitoring",
    "net user",
    "net localgroup administrators",
    "bcdedit",
    "vssadmin delete shadows",
    "format c:",
    "del /f /s /q c:\\",
    "rmdir /s /q c:\\",
]


class RiskClassifier:
    """Evaluates actions against security rules, assigning risk level and generating previews."""

    @staticmethod
    def classify_action(
        tool_name: str,
        params: Dict[str, Any],
        policy: Optional[SecurityPolicy] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """
        Classifies an action into one of 4 Risk Levels and constructs an ApprovalRequest.
        """
        req = ApprovalRequest(
            tool_name=tool_name,
            parameters=params,
        )

        clean_tool = tool_name.lower().strip()

        # -------------------------------------------------------------
        # 1. CRITICAL RISK CHECK (Level 4): System directories, Admin elevation, Mass deletion
        # -------------------------------------------------------------
        critical_detected, crit_reason, crit_target = RiskClassifier._check_critical_threats(clean_tool, params)
        if critical_detected:
            req.risk_level = SecurityRiskLevel.CRITICAL
            req.action_type = "Critical System Operation"
            req.target = crit_target
            req.reason = crit_reason
            req.requires_typed_confirmation = True
            req.confirmation_phrase = "CONFIRM"
            return req

        # -------------------------------------------------------------
        # 2. HIGH RISK (Level 3): External comms, file deletion, financial, security changes
        # -------------------------------------------------------------
        if clean_tool in ("send_email", "send_gmail", "send_message"):
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "External Communication"
            recipient = params.get("recipient") or params.get("to") or "Unknown recipient"
            subject = params.get("subject") or "No Subject"
            body = params.get("body") or params.get("content") or ""
            req.target = f"Email to: {recipient}"
            req.reason = f"Sending an external email to '{recipient}' cannot be undone."
            req.proposed_changes = f"Subject: {subject}\n\n{body}"
            return req

        if clean_tool in ("delete_file", "delete_text_file"):
            target_path = params.get("file_path") or params.get("path") or ""
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "File Deletion"
            req.target = str(target_path)
            req.reason = f"Permanently deleting file '{Path(target_path).name}' from disk is irreversible."
            return req

        if clean_tool in ("memory_delete",):
            cat = params.get("category", "")
            key = params.get("key", "")
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "Memory Deletion"
            req.target = f"Memory: [{cat}] '{key}'"
            req.reason = f"Permanently removing user memory '{key}'."
            return req

        if clean_tool in ("submit_web_form",):
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "Web Form Submission"
            req.target = params.get("url") or "Web Form"
            req.reason = "Submitting forms online may transmit personal data or trigger external transactions."
            return req

        if clean_tool in ("make_purchase", "transfer_money"):
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "Financial Transaction"
            req.target = params.get("item") or params.get("destination") or "Financial Service"
            req.reason = "Financial transactions involve real monetary transfer and require explicit human authorization."
            return req

        if clean_tool in ("security_update_policy",):
            req.risk_level = SecurityRiskLevel.HIGH
            req.action_type = "Security Policy Modification"
            req.target = "BOLT Security Configuration"
            req.reason = "Modifying security policies directly impacts protection boundaries."
            return req

        # -------------------------------------------------------------
        # 3. MODERATE RISK (Level 2): File modification / overwrites, code execution, data entry
        # -------------------------------------------------------------
        if clean_tool in ("write_text_file", "edit_file", "append_text_file"):
            target_path_str = params.get("file_path") or params.get("path") or ""
            content = params.get("content") or ""
            allow_overwrite = params.get("allow_overwrite", True)

            # Resolve file on disk
            resolved_p = RiskClassifier._resolve_file_path(target_path_str)
            target_display = str(resolved_p) if resolved_p else target_path_str

            if resolved_p and resolved_p.exists() and allow_overwrite:
                # Modifying existing file -> Level 2 Moderate Risk
                req.risk_level = SecurityRiskLevel.MODERATE
                req.action_type = "Modify Existing File"
                req.target = target_display
                req.reason = f"Overwriting existing file '{resolved_p.name}' with updated content."

                # Generate unified diff
                try:
                    orig_text = resolved_p.read_text(encoding="utf-8", errors="replace")
                    diff_lines = list(
                        difflib.unified_diff(
                            orig_text.splitlines(keepends=True),
                            content.splitlines(keepends=True),
                            fromfile=f"a/{resolved_p.name}",
                            tofile=f"b/{resolved_p.name}",
                            n=3,
                        )
                    )
                    if diff_lines:
                        req.diff_preview = "".join(diff_lines[:40])
                    else:
                        req.proposed_changes = content[:300]
                except Exception:
                    req.proposed_changes = content[:300]

                return req

            # If creating a brand new file, it is low risk unless in policy strict mode
            req.risk_level = SecurityRiskLevel.LOW
            req.action_type = "Create New File"
            req.target = target_display
            req.reason = f"Creating new text file '{resolved_p.name if resolved_p else target_path_str}'."
            return req

        if clean_tool in ("run_python_script_safe",):
            script_path = params.get("script_path", "")
            req.risk_level = SecurityRiskLevel.MODERATE
            req.action_type = "Script Execution"
            req.target = str(script_path)
            req.reason = f"Executing local Python script '{Path(script_path).name}' in subprocess."
            return req

        if clean_tool in ("move_file", "move_folder"):
            src = params.get("source_path", "")
            dst = params.get("destination_path", "")
            req.risk_level = SecurityRiskLevel.MODERATE
            req.action_type = "Move Files/Folders"
            req.target = f"{src} -> {dst}"
            req.reason = f"Moving file from '{src}' to '{dst}' changes directory structure."
            return req

        if clean_tool in ("type_text", "press_key", "hotkey", "uia_set_element_value"):
            # Interactive input injection
            req.risk_level = SecurityRiskLevel.LOW  # Handled automatically in standard tasks
            req.action_type = "Input Injection"
            req.target = params.get("window_title") or params.get("element_name") or "Active Window"
            req.reason = "Typing or key input into desktop application."
            return req

        # -------------------------------------------------------------
        # 4. LOW RISK (Level 1): Automatic execution
        # -------------------------------------------------------------
        req.risk_level = SecurityRiskLevel.LOW
        req.action_type = "Ordinary Operation"
        req.target = (
            params.get("app_name")
            or params.get("url")
            or params.get("query")
            or params.get("file_path")
            or params.get("folder_name")
            or params.get("key")
            or "Desktop"
        )
        req.reason = f"Standard autonomous task execution for tool '{clean_tool}'."
        return req

    @staticmethod
    def _check_critical_threats(tool_name: str, params: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Detect critical destructive actions, system directory violations, and admin privilege elevation."""
        # 1. Mass deletion
        if tool_name in ("delete_directory", "delete_folder", "remove_directory"):
            target_dir = params.get("directory_path") or params.get("folder_path") or params.get("path") or ""
            return (
                True,
                f"Deleting entire directory tree at '{target_dir}' will permanently remove all files and subdirectories.",
                str(target_dir),
            )

        # 2. System protected directory checks
        file_targets = [
            params.get("file_path"),
            params.get("path"),
            params.get("destination_path"),
            params.get("source_path"),
            params.get("directory_path"),
            params.get("folder_path"),
        ]
        for ft in file_targets:
            if ft and isinstance(ft, str):
                ft_lower = ft.lower().strip()
                for sys_dir in SYSTEM_PROTECTED_DIRECTORIES:
                    if ft_lower.startswith(sys_dir):
                        return (
                            True,
                            f"Action targets protected Windows system path '{ft}'. Modification of system directories requires critical authorization.",
                            ft,
                        )

        # 3. Administrator privilege elevation and dangerous command inspection
        cmd_targets = [
            params.get("command"),
            params.get("script_path"),
            params.get("args"),
            params.get("query"),
        ]
        for ct in cmd_targets:
            if ct and isinstance(ct, str):
                ct_lower = ct.lower()
                for token in ADMIN_ELEVATION_TOKENS:
                    if token in ct_lower:
                        return (
                            True,
                            f"Detected potential privilege elevation or destructive system token ('{token}'). Silent escalation is blocked.",
                            ct,
                        )

        return (False, "", "")

    @staticmethod
    def _resolve_file_path(path_str: str) -> Optional[Path]:
        if not path_str:
            return None
        clean = path_str.strip().strip("'\"")
        p = Path(clean)
        if not p.is_absolute() and len(p.parts) == 1:
            desktop = FileManager.resolve_folder_alias("desktop")
            if desktop and (desktop / clean).exists():
                return desktop / clean
            return p.expanduser().resolve()
        return p.expanduser().resolve()
