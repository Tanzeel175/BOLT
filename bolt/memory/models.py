"""
Data models and category definitions for BOLT Long-Term Memory (Phase 8).
Supports persistent local memory, structured context extraction, and correction learning.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional
import uuid


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class MemoryCategory(str, Enum):
    """
    Core memory categories defined in Phase 8 architecture.
    Aliases mapped for seamless backward compatibility with earlier subsystems.
    """
    PERSONAL_PREFERENCES = "personal_preferences"
    COMPUTER_KNOWLEDGE = "computer_knowledge"
    WORKFLOW_MEMORY = "workflow_memory"
    CONVERSATION_MEMORY = "conversation_memory"
    CORRECTIONS = "corrections"

    # Backward compatibility aliases
    USER_PREFERENCES = "personal_preferences"
    APPLICATION_KNOWLEDGE = "computer_knowledge"
    SUCCESSFUL_WORKFLOWS = "workflow_memory"
    CONVERSATION_CONTEXT = "conversation_memory"
    ERRORS_AND_SOLUTIONS = "corrections"
    TOOL_EXECUTION_EXAMPLES = "computer_knowledge"

    @classmethod
    def normalize(cls, cat: Any) -> str:
        """Normalize string or enum into a canonical category name."""
        if isinstance(cat, MemoryCategory):
            return cat.value
        s = str(cat).lower().strip().replace(" ", "_")
        aliases = {
            "preferences": cls.PERSONAL_PREFERENCES.value,
            "user_preferences": cls.PERSONAL_PREFERENCES.value,
            "personal_preferences": cls.PERSONAL_PREFERENCES.value,
            "pref": cls.PERSONAL_PREFERENCES.value,
            "computer": cls.COMPUTER_KNOWLEDGE.value,
            "computer_knowledge": cls.COMPUTER_KNOWLEDGE.value,
            "application_knowledge": cls.COMPUTER_KNOWLEDGE.value,
            "app_knowledge": cls.COMPUTER_KNOWLEDGE.value,
            "hardware": cls.COMPUTER_KNOWLEDGE.value,
            "workflow": cls.WORKFLOW_MEMORY.value,
            "workflows": cls.WORKFLOW_MEMORY.value,
            "workflow_memory": cls.WORKFLOW_MEMORY.value,
            "successful_workflows": cls.WORKFLOW_MEMORY.value,
            "conversation": cls.CONVERSATION_MEMORY.value,
            "conversation_memory": cls.CONVERSATION_MEMORY.value,
            "conversation_context": cls.CONVERSATION_MEMORY.value,
            "context": cls.CONVERSATION_MEMORY.value,
            "correction": cls.CORRECTIONS.value,
            "corrections": cls.CORRECTIONS.value,
            "errors_and_solutions": cls.CORRECTIONS.value,
            "learning": cls.CORRECTIONS.value,
        }
        return aliases.get(s, s)


@dataclass
class MemoryItem:
    """Represents a discrete memory unit stored in the SQLite database."""
    category: str
    key: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0
    access_count: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_accessed_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def value(self) -> Any:
        """Parse content as JSON if applicable, otherwise return raw string."""
        try:
            return json.loads(self.content)
        except (json.JSONDecodeError, TypeError):
            return self.content

    def to_dict(self) -> Dict[str, Any]:
        """Convert memory item to dictionary for serialization."""
        return {
            "id": self.id,
            "category": self.category,
            "key": self.key,
            "content": self.content,
            "value": self.value(),
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "MemoryItem":
        """Construct a MemoryItem from an SQLite Row object."""
        meta = {}
        if "metadata_json" in row.keys() and row["metadata_json"]:
            try:
                meta = json.loads(row["metadata_json"])
            except Exception:
                meta = {}
        elif "value_json" in row.keys() and row["value_json"]:
            # Fallback for older bolt_learning_memory rows
            try:
                meta = {"raw_json": json.loads(row["value_json"])}
            except Exception:
                meta = {}

        content_val = ""
        if "content" in row.keys() and row["content"] is not None:
            content_val = row["content"]
        elif "value_json" in row.keys() and row["value_json"] is not None:
            content_val = row["value_json"]

        return cls(
            id=row["id"] if "id" in row.keys() else str(uuid.uuid4()),
            category=row["category"],
            key=row["key"],
            content=content_val,
            metadata=meta,
            importance=float(row["importance"]) if "importance" in row.keys() and row["importance"] is not None else 1.0,
            access_count=int(row["access_count"]) if "access_count" in row.keys() and row["access_count"] is not None else 0,
            last_accessed_at=row["last_accessed_at"] if "last_accessed_at" in row.keys() else None,
            created_at=row["created_at"] if "created_at" in row.keys() else utc_now_iso(),
            updated_at=row["updated_at"] if "updated_at" in row.keys() else utc_now_iso(),
        )


@dataclass
class CorrectionRecord:
    """Structured record of a learned user correction."""
    instruction: str
    wrong_action: str
    corrected_action: str
    feedback_reason: str = ""
    preference_saved: bool = False
    preference_key: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instruction": self.instruction,
            "wrong_action": self.wrong_action,
            "corrected_action": self.corrected_action,
            "feedback_reason": self.feedback_reason,
            "preference_saved": self.preference_saved,
            "preference_key": self.preference_key,
            "timestamp": self.timestamp,
        }


@dataclass
class ExtractedContext:
    """Structured high-level context extracted from conversations."""
    active_project: Optional[str] = None
    ongoing_task: Optional[str] = None
    active_files: List[str] = field(default_factory=list)
    key_entities: Dict[str, str] = field(default_factory=dict)
    summary: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_project": self.active_project,
            "ongoing_task": self.ongoing_task,
            "active_files": self.active_files,
            "key_entities": self.key_entities,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }
