"""
Structured Conversation Context Extractor for BOLT (Phase 8).
Extracts active projects, ongoing tasks, referenced files, and core entities
from conversation turns into structured memory records without storing raw message dumps.
"""

import os
import re
from typing import Any, Dict, List, Optional

from bolt.core.logger import get_logger
from bolt.memory.models import ExtractedContext

logger = get_logger("ContextExtractor")

# File extension pattern for detecting filenames and paths
FILE_PATTERN = re.compile(
    r"(?:[a-zA-Z]:[\\/][^\s\"'<>]+\.[a-zA-Z0-9]+|(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z0-9]{1,6})",
    re.IGNORECASE,
)

# Common project/task indicator patterns
PROJECT_PATTERNS = [
    re.compile(r"(?:my|the)\s+([a-zA-Z0-9_\-\s]{2,30}?)\s+project", re.IGNORECASE),
    re.compile(r"project\s+(?:called|named)?\s*[\"']?([a-zA-Z0-9_\-\s]{2,30}?)[\"']?(?:[,\.\s]|$)", re.IGNORECASE),
    re.compile(r"working\s+on\s+([a-zA-Z0-9_\-\s]{2,30}?)(?:[,\.\s]|$)", re.IGNORECASE),
]

TASK_PATTERNS = [
    re.compile(r"^(?:please\s+)?(develop|create|build|implement|debug|refactor|test|analyze|summarize|write)\s+([^\n\.,]+)", re.IGNORECASE),
    re.compile(r"task\s+(?:is\s+to\s+|to\s+)?([^\n\.,]+)", re.IGNORECASE),
]


class ConversationContextExtractor:
    """Extracts high-level structured context and entities from conversation turns."""

    @staticmethod
    def extract_from_interaction(
        user_message: str,
        assistant_message: str = "",
        existing_context: Optional[ExtractedContext] = None,
    ) -> ExtractedContext:
        """
        Analyze conversation turn and extract structured metadata:
        - Active project
        - Ongoing task
        - Active files
        - Key entities
        """
        ctx = existing_context or ExtractedContext()
        text = f"{user_message} {assistant_message}".strip()

        # 1. Detect file references
        found_files = FILE_PATTERN.findall(text)
        valid_extensions = {".py", ".txt", ".md", ".json", ".csv", ".pdf", ".html", ".css", ".js", ".ts", ".cpp", ".docx"}
        for f in found_files:
            _, ext = os.path.splitext(f)
            if ext.lower() in valid_extensions and f not in ctx.active_files:
                ctx.active_files.append(f)

        # 2. Detect active project
        for p in PROJECT_PATTERNS:
            m = p.search(user_message)
            if m:
                proj_name = m.group(1).strip()
                if proj_name.lower() not in ["new", "current", "this", "my", "our"]:
                    ctx.active_project = proj_name.title()
                    break

        # 3. Detect ongoing task
        for t in TASK_PATTERNS:
            m = t.search(user_message)
            if m:
                if len(m.groups()) == 2:
                    action = m.group(1).strip()
                    detail = m.group(2).strip()
                    ctx.ongoing_task = f"{action} {detail}".strip()
                else:
                    ctx.ongoing_task = m.group(1).strip()
                break

        # 4. Generate summary
        parts = []
        if ctx.active_project:
            parts.append(f"Project: {ctx.active_project}")
        if ctx.ongoing_task:
            parts.append(f"Task: {ctx.ongoing_task}")
        if ctx.active_files:
            parts.append(f"Files: {', '.join(ctx.active_files[:4])}")

        ctx.summary = " • ".join(parts) if parts else user_message[:100]
        return ctx

