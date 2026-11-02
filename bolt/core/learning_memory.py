"""
Local Learning, Persistent Memory, and LoRA Fine-Tuning Dataset Subsystem for BOLT (Part 6).
Improves BOLT's intelligence over time using SQLite persistence across 7 categories:
1. User preferences
2. Application knowledge
3. Computer knowledge
4. Successful workflows
5. Tool execution examples
6. Errors and solutions
7. Conversation context
Prepares structured JSONL datasets for future LoRA fine-tuning without claiming weight modification.
"""

from enum import Enum
import json
import pathlib
import uuid
from typing import Any, Dict, List, Optional
from bolt.config.constants import DATA_DIR
from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger

logger = get_logger("LearningMemory")


class MemoryCategory(str, Enum):
    USER_PREFERENCES = "user_preferences"
    APPLICATION_KNOWLEDGE = "application_knowledge"
    COMPUTER_KNOWLEDGE = "computer_knowledge"
    SUCCESSFUL_WORKFLOWS = "successful_workflows"
    TOOL_EXECUTION_EXAMPLES = "tool_execution_examples"
    ERRORS_AND_SOLUTIONS = "errors_and_solutions"
    CONVERSATION_CONTEXT = "conversation_context"


class LearningMemory:
    """Manages persistent SQLite memory, preference retrieval, and LoRA dataset generation."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self._init_memory_tables()

    def _init_memory_tables(self) -> None:
        """Create learning memory and fine-tuning tables if not existing."""
        conn = self.db._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bolt_learning_memory (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value_json TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        source TEXT DEFAULT 'user',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(category, key)
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bolt_finetuning_dataset (
                        id TEXT PRIMARY KEY,
                        instruction TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        tool TEXT NOT NULL,
                        arguments_json TEXT NOT NULL,
                        expected_result_json TEXT NOT NULL,
                        user_correction TEXT DEFAULT '',
                        is_validated INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_learning_category ON bolt_learning_memory(category);"
                )
        except Exception as e:
            logger.error(f"Failed to initialize learning memory tables: {e}")

    # ---------------- 1. Memory Storage & Retrieval ----------------

    def save_memory(
        self,
        category: MemoryCategory,
        key: str,
        value: Any,
        confidence: float = 1.0,
        source: str = "user",
    ) -> bool:
        """Store or update a memory record in SQLite."""
        cat_str = category.value if isinstance(category, MemoryCategory) else str(category)
        clean_key = key.strip().lower()
        now = utc_now_iso()
        val_json = json.dumps(value)

        conn = self.db._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO bolt_learning_memory (id, category, key, value_json, confidence, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value_json = excluded.value_json,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        updated_at = excluded.updated_at;
                    """,
                    (str(uuid.uuid4()), cat_str, clean_key, val_json, confidence, source, now, now),
                )
            logger.info(f"Saved memory [{cat_str}]: '{clean_key}'")
            return True
        except Exception as e:
            logger.error(f"Error saving memory '{clean_key}': {e}")
            return False

    def get_memory(self, category: MemoryCategory, key: str, default: Any = None) -> Any:
        """Retrieve a memory record value by category and key."""
        cat_str = category.value if isinstance(category, MemoryCategory) else str(category)
        clean_key = key.strip().lower()

        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value_json FROM bolt_learning_memory WHERE category = ? AND key = ? LIMIT 1;",
                    (cat_str, clean_key),
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row["value_json"])
        except Exception as e:
            logger.error(f"Error retrieving memory '{clean_key}': {e}")

        return default

    def list_memories(self, category: MemoryCategory) -> List[Dict[str, Any]]:
        """List all memories under a given category."""
        cat_str = category.value if isinstance(category, MemoryCategory) else str(category)
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT key, value_json, confidence, source, updated_at FROM bolt_learning_memory WHERE category = ? ORDER BY updated_at DESC;",
                    (cat_str,),
                )
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "key": row["key"],
                        "value": json.loads(row["value_json"]),
                        "confidence": row["confidence"],
                        "source": row["source"],
                        "updated_at": row["updated_at"],
                    })
                return results
        except Exception as e:
            logger.error(f"Error listing memories for '{cat_str}': {e}")
            return []

    # ---------------- 2. Convenience Helpers: Preferences & Knowledge ----------------

    def set_user_preference(self, preference_name: str, value: Any) -> bool:
        """Save a user preference (e.g. 'preferred_browser_for_chatgpt': 'chrome')."""
        return self.save_memory(MemoryCategory.USER_PREFERENCES, preference_name, value)

    def get_user_preference(self, preference_name: str, default: Any = None) -> Any:
        """Retrieve a user preference."""
        return self.get_memory(MemoryCategory.USER_PREFERENCES, preference_name, default=default)

    def record_user_correction(
        self,
        instruction: str,
        wrong_choice: str,
        correct_choice: str,
        save_as_preference: bool = False,
    ) -> Dict[str, Any]:
        """
        Record and learn from a user correction (e.g. 'You selected the wrong app. Use VS Code instead.').
        """
        logger.info(f"Learning from user correction: was '{wrong_choice}', corrected to '{correct_choice}'")

        # Save to errors_and_solutions
        corr_key = f"correction_{instruction.strip().lower()[:40]}"
        self.save_memory(
            MemoryCategory.ERRORS_AND_SOLUTIONS,
            corr_key,
            {
                "instruction": instruction,
                "wrong": wrong_choice,
                "corrected": correct_choice,
                "timestamp": utc_now_iso(),
            },
        )

        # Record into fine-tuning dataset
        self.record_finetuning_example(
            instruction=instruction,
            intent=f"open_or_use_{correct_choice.lower()}",
            tool="open_application",
            arguments={"app_name": correct_choice},
            expected_result={"success": True, "app_name": correct_choice},
            user_correction=f"User corrected from '{wrong_choice}' to '{correct_choice}'.",
        )

        if save_as_preference:
            pref_key = f"preferred_app_for_{instruction.strip().lower()[:30]}"
            self.set_user_preference(pref_key, correct_choice)

        return {
            "success": True,
            "instruction": instruction,
            "wrong_choice": wrong_choice,
            "correct_choice": correct_choice,
            "saved_as_preference": save_as_preference,
            "message": f"Learned correction: will prefer '{correct_choice}' for '{instruction}'.",
        }

    # ---------------- 3. LoRA Fine-Tuning Dataset Preparation ----------------

    def record_finetuning_example(
        self,
        instruction: str,
        intent: str,
        tool: str,
        arguments: Dict[str, Any],
        expected_result: Dict[str, Any],
        user_correction: str = "",
    ) -> bool:
        """
        Store a structured demonstration example for future LoRA fine-tuning.
        """
        conn = self.db._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO bolt_finetuning_dataset (id, instruction, intent, tool, arguments_json, expected_result_json, user_correction, is_validated, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?);
                    """,
                    (
                        str(uuid.uuid4()),
                        instruction.strip(),
                        intent.strip(),
                        tool.strip(),
                        json.dumps(arguments),
                        json.dumps(expected_result),
                        user_correction.strip(),
                        utc_now_iso(),
                    ),
                )
            logger.debug(f"Recorded fine-tuning example for instruction: '{instruction[:40]}'")
            return True
        except Exception as e:
            logger.error(f"Error recording fine-tuning example: {e}")
            return False

    def export_finetuning_dataset_jsonl(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Export all recorded examples into a clean JSONL dataset ready for LoRA fine-tuning.
        """
        if not output_path:
            ds_dir = DATA_DIR / "datasets"
            ds_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(ds_dir / "bolt_finetune_dataset.jsonl")

        p = pathlib.Path(output_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        conn = self.db._get_connection()
        examples_count = 0
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM bolt_finetuning_dataset ORDER BY created_at ASC;")
                rows = cursor.fetchall()
                with open(p, "w", encoding="utf-8") as f:
                    for row in rows:
                        item = {
                            "id": row["id"],
                            "instruction": row["instruction"],
                            "intent": row["intent"],
                            "tool": row["tool"],
                            "arguments": json.loads(row["arguments_json"]),
                            "expected_result": json.loads(row["expected_result_json"]),
                            "user_correction": row["user_correction"],
                            "created_at": row["created_at"],
                        }
                        f.write(json.dumps(item) + "\n")
                        examples_count += 1

            return {
                "success": True,
                "file_path": str(p),
                "examples_count": examples_count,
                "message": f"Exported {examples_count} fine-tuning examples to `{p.name}`.",
            }
        except Exception as e:
            logger.error(f"Failed exporting fine-tuning dataset: {e}")
            return {"success": False, "error": str(e)}

    # ---------------- 4. Prompt Context Injection ----------------

    def get_prompt_context_injection(self) -> str:
        """
        Build dynamic context string summarizing user preferences and learned corrections
        to inject into local model system prompts without model retraining.
        """
        prefs = self.list_memories(MemoryCategory.USER_PREFERENCES)
        if not prefs:
            return ""

        lines = ["\n### User Preferences & Persistent Memories:"]
        for p in prefs[:10]:
            lines.append(f"- {p['key']}: {p['value']}")

        return "\n".join(lines)


_LEARNING_MEMORY_INSTANCE: Optional[LearningMemory] = None


def get_learning_memory() -> LearningMemory:
    global _LEARNING_MEMORY_INSTANCE
    if _LEARNING_MEMORY_INSTANCE is None:
        _LEARNING_MEMORY_INSTANCE = LearningMemory()
    return _LEARNING_MEMORY_INSTANCE
