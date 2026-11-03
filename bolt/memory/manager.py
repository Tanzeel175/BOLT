"""
Central Persistent Long-Term Memory Manager for BOLT (Phase 8).
Implements persistent local memory across 5 categories:
1. Personal Preferences
2. Computer Knowledge
3. Workflow Memory
4. Conversation Memory
5. Learning from Corrections

Provides SQLite persistence, FTS5 full-text indexing, lightweight semantic retrieval,
path verification, structured context extraction, and local JSON/JSONL export.
Zero dependencies on cloud memory services or external embedding APIs.
"""

import json
import os
import pathlib
import re
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from bolt.config.constants import DATA_DIR
from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger
from bolt.memory.context_extractor import ConversationContextExtractor
from bolt.memory.corrections import CorrectionHandler
from bolt.memory.models import (
    CorrectionRecord,
    ExtractedContext,
    MemoryCategory,
    MemoryItem,
)
from bolt.memory.retriever import MemoryRetriever

logger = get_logger("MemoryManager")


class MemoryManager:
    """Manages all persistent memory operations, local retrieval, and continuous learning."""

    _instance: Optional["MemoryManager"] = None

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self._init_memory_schema()
        self.retriever = MemoryRetriever(self.db._get_connection)
        self.correction_handler = CorrectionHandler()
        self.context_extractor = ConversationContextExtractor()
        self.current_context = ExtractedContext()
        self._seed_initial_computer_knowledge()

    @classmethod
    def get_instance(cls, db: Optional[Database] = None) -> "MemoryManager":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    def _init_memory_schema(self) -> None:
        """Create structured memory tables, indices, and FTS5 search index."""
        conn = self.db._get_connection()
        try:
            with conn:
                # 1. Main memories table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bolt_memories (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        importance REAL DEFAULT 1.0,
                        access_count INTEGER DEFAULT 0,
                        last_accessed_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(category, key)
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_cat ON bolt_memories(category);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_key ON bolt_memories(key);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_cat_key ON bolt_memories(category, key);"
                )

                # 2. SQLite FTS5 Full-Text Search Virtual Table
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS bolt_memories_fts USING fts5(
                        key,
                        content,
                        category,
                        content='bolt_memories',
                        content_rowid='rowid'
                    );
                    """
                )

                # 3. Synchronize triggers for automatic FTS5 index maintenance
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS trig_bolt_memories_ai AFTER INSERT ON bolt_memories BEGIN
                        INSERT INTO bolt_memories_fts(rowid, key, content, category)
                        VALUES (new.rowid, new.key, new.content, new.category);
                    END;
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS trig_bolt_memories_ad AFTER DELETE ON bolt_memories BEGIN
                        INSERT INTO bolt_memories_fts(bolt_memories_fts, rowid, key, content, category)
                        VALUES ('delete', old.rowid, old.key, old.content, old.category);
                    END;
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS trig_bolt_memories_au AFTER UPDATE ON bolt_memories BEGIN
                        INSERT INTO bolt_memories_fts(bolt_memories_fts, rowid, key, content, category)
                        VALUES ('delete', old.rowid, old.key, old.content, old.category);
                        INSERT INTO bolt_memories_fts(rowid, key, content, category)
                        VALUES (new.rowid, new.key, new.content, new.category);
                    END;
                    """
                )

                # 4. Migrate existing items from bolt_learning_memory if present
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='bolt_learning_memory';"
                )
                if cursor.fetchone():
                    cursor.execute("SELECT * FROM bolt_learning_memory;")
                    for r in cursor.fetchall():
                        cat_norm = MemoryCategory.normalize(r["category"])
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO bolt_memories (
                                id, category, key, content, metadata_json, importance,
                                access_count, last_accessed_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, '{}', ?, 0, NULL, ?, ?);
                            """,
                            (r["id"], cat_norm, r["key"], r["value_json"], r["confidence"], r["created_at"], r["updated_at"])
                        )

            logger.info("Memory schema and FTS5 index initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize memory schema: {e}")
        finally:
            conn.close()

    def _seed_initial_computer_knowledge(self) -> None:
        """Seed baseline computer knowledge about host laptop if not already established."""
        try:
            # Common file extensions
            self.save_memory(
                category=MemoryCategory.COMPUTER_KNOWLEDGE,
                key="supported_file_extensions",
                content=[".txt", ".py", ".pdf", ".md", ".json", ".csv", ".docx", ".html", ".png", ".jpg"],
                importance=0.8,
            )
            # Supported automation methods
            self.save_memory(
                category=MemoryCategory.COMPUTER_KNOWLEDGE,
                key="supported_automation_methods",
                content=[
                    "Direct Windows APIs (Win32, ShellExecute)",
                    "Windows UI Automation & Accessibility (InvokePattern, ValuePattern)",
                    "Keyboard & Structured Mouse (SendInput, Hotkeys)",
                    "Local Windows Media OCR (100% on CPU)",
                    "Local Vision Diagnosis (Screenshot-on-Demand)",
                ],
                importance=0.9,
            )
            # Standard folders
            user_profile = os.environ.get("USERPROFILE", "")
            if user_profile:
                self.save_memory(
                    category=MemoryCategory.COMPUTER_KNOWLEDGE,
                    key="common_folder_desktop",
                    content=str(pathlib.Path(user_profile) / "Desktop"),
                    importance=0.9,
                )
                self.save_memory(
                    category=MemoryCategory.COMPUTER_KNOWLEDGE,
                    key="common_folder_downloads",
                    content=str(pathlib.Path(user_profile) / "Downloads"),
                    importance=0.9,
                )
                self.save_memory(
                    category=MemoryCategory.COMPUTER_KNOWLEDGE,
                    key="common_folder_documents",
                    content=str(pathlib.Path(user_profile) / "Documents"),
                    importance=0.9,
                )
        except Exception as e:
            logger.debug(f"Computer knowledge seeding skipped: {e}")

    # =========================================================================
    # CORE MEMORY OPERATIONS (Section 4 Requirements)
    # =========================================================================

    def save_memory(
        self,
        category: Union[MemoryCategory, str],
        key: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 1.0,
    ) -> bool:
        """
        Save or upsert a memory item into persistent SQLite storage.
        Auto-encodes dict/list as JSON strings.
        """
        cat_norm = MemoryCategory.normalize(category)
        clean_key = key.strip().lower()
        now = utc_now_iso()

        content_str = json.dumps(content) if not isinstance(content, str) else content
        meta_str = json.dumps(metadata or {})

        conn = self.db._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO bolt_memories (
                        id, category, key, content, metadata_json, importance,
                        access_count, last_accessed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        content = excluded.content,
                        metadata_json = excluded.metadata_json,
                        importance = excluded.importance,
                        updated_at = excluded.updated_at;
                    """,
                    (str(uuid.uuid4()), cat_norm, clean_key, content_str, meta_str, importance, now, now),
                )
            logger.info(f"Memory saved [{cat_norm}]: '{clean_key}'")
            return True
        except Exception as e:
            logger.error(f"Error saving memory '{clean_key}': {e}")
            return False
        finally:
            conn.close()

    def retrieve_memory(
        self,
        category: Union[MemoryCategory, str],
        key: str,
    ) -> Optional[MemoryItem]:
        """
        Retrieve a specific memory item by category and key.
        Increments access count and updates last_accessed_at timestamp.
        """
        cat_norm = MemoryCategory.normalize(category)
        clean_key = key.strip().lower()
        now = utc_now_iso()

        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM bolt_memories WHERE category = ? AND key = ? LIMIT 1;",
                    (cat_norm, clean_key),
                )
                row = cursor.fetchone()
                if row:
                    item = MemoryItem.from_row(row)
                    item.access_count += 1
                    item.last_accessed_at = now
                    # Update access statistics
                    conn.execute(
                        """
                        UPDATE bolt_memories
                        SET access_count = access_count + 1, last_accessed_at = ?
                        WHERE category = ? AND key = ?;
                        """,
                        (now, cat_norm, clean_key),
                    )
                    return item
                return None
        except Exception as e:
            logger.error(f"Error retrieving memory '{clean_key}': {e}")
            return None
        finally:
            conn.close()

    def update_memory(
        self,
        category: Union[MemoryCategory, str],
        key: str,
        content: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: Optional[float] = None,
    ) -> bool:
        """
        Update fields of an existing memory item. Returns False if memory not found.
        """
        cat_norm = MemoryCategory.normalize(category)
        clean_key = key.strip().lower()
        now = utc_now_iso()

        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if content is not None:
            content_str = json.dumps(content) if not isinstance(content, str) else content
            updates.append("content = ?")
            params.append(content_str)
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata))
        if importance is not None:
            updates.append("importance = ?")
            params.append(float(importance))

        params.extend([cat_norm, clean_key])
        sql = f"UPDATE bolt_memories SET {', '.join(updates)} WHERE category = ? AND key = ?;"

        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                if cursor.rowcount > 0:
                    logger.info(f"Updated memory [{cat_norm}]: '{clean_key}'")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating memory '{clean_key}': {e}")
            return False
        finally:
            conn.close()

    def search_memory(
        self,
        query: str,
        category: Optional[Union[MemoryCategory, str]] = None,
        limit: int = 5,
        min_relevance: float = 0.28,
    ) -> List[Dict[str, Any]]:
        """
        Search memories matching a query.
        Applies min_relevance threshold so unrelated memories are discarded.
        """
        cat_norm = MemoryCategory.normalize(category) if category else None
        scored_items = self.retriever.retrieve_for_instruction(
            instruction=query,
            category=cat_norm,
            limit=limit,
            min_relevance=min_relevance,
        )

        results = []
        for item, score in scored_items:
            data = item.to_dict()
            data["relevance_score"] = round(score, 3)
            results.append(data)
        return results

    def delete_memory(
        self,
        category: Union[MemoryCategory, str],
        key: str,
    ) -> bool:
        """Delete a memory item from persistent storage."""
        cat_norm = MemoryCategory.normalize(category)
        clean_key = key.strip().lower()

        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM bolt_memories WHERE category = ? AND key = ?;",
                    (cat_norm, clean_key),
                )
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted memory [{cat_norm}]: '{clean_key}'")
                return deleted
        except Exception as e:
            logger.error(f"Error deleting memory '{clean_key}': {e}")
            return False
        finally:
            conn.close()

    def list_memories(
        self,
        category: Optional[Union[MemoryCategory, str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List stored memories, optionally filtered by category."""
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            if category:
                cat_norm = MemoryCategory.normalize(category)
                cursor.execute(
                    "SELECT * FROM bolt_memories WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?;",
                    (cat_norm, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM bolt_memories ORDER BY category ASC, importance DESC, updated_at DESC LIMIT ?;",
                    (limit,),
                )
            rows = cursor.fetchall()
            return [MemoryItem.from_row(r).to_dict() for r in rows]
        except Exception as e:
            logger.error(f"Error listing memories: {e}")
            return []
        finally:
            conn.close()

    def export_memory(
        self,
        output_path: Optional[str] = None,
        category: Optional[Union[MemoryCategory, str]] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export stored memories to a local file in JSON or JSONL format.
        Useful for backups, offline inspection, and future fine-tuning datasets.
        """
        memories = self.list_memories(category=category, limit=1000)
        export_dir = DATA_DIR / "memory_exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        fmt = format.lower().strip()
        cat_suffix = f"_{MemoryCategory.normalize(category)}" if category else ""
        ext = "jsonl" if fmt == "jsonl" else "json"

        target_path = pathlib.Path(output_path) if output_path else export_dir / f"bolt_memories{cat_suffix}.{ext}"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                if fmt == "jsonl":
                    for m in memories:
                        f.write(json.dumps(m) + "\n")
                else:
                    json.dump(memories, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "file_path": str(target_path),
                "count": len(memories),
                "format": fmt,
                "message": f"Successfully exported {len(memories)} memories to `{target_path.name}`.",
            }
        except Exception as e:
            logger.error(f"Failed exporting memories: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # SPECIALIZED CATEGORY HELPERS (Sections 2.A - 2.E)
    # =========================================================================

    # ---------------- 2.A Personal Preferences ----------------
    def set_user_preference(self, preference_name: str, value: Any) -> bool:
        """Store an explicitly established personal preference."""
        clean_key = preference_name.strip().lower()
        return self.save_memory(MemoryCategory.PERSONAL_PREFERENCES, clean_key, value)

    save_user_preference = set_user_preference

    def get_user_preference(self, preference_name: str, default: Any = None) -> Any:
        """Retrieve a stored personal preference."""
        clean_key = preference_name.strip().lower()
        item = self.retrieve_memory(MemoryCategory.PERSONAL_PREFERENCES, clean_key)
        return item.value() if item else default

    # ---------------- 2.B Computer Knowledge Memory ----------------
    def verify_computer_knowledge(self, key: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify that stored computer knowledge paths and applications exist on disk.
        Prevents blindly trusting outdated information (Section 2.B Requirement).
        """
        items = []
        if key:
            it = self.retrieve_memory(MemoryCategory.COMPUTER_KNOWLEDGE, key)
            if it:
                items.append(it)
        else:
            raw_list = self.list_memories(MemoryCategory.COMPUTER_KNOWLEDGE)
            for r in raw_list:
                items.append(MemoryItem.from_row(r))

        verified = []
        outdated = []

        for item in items:
            val = item.value()
            if isinstance(val, str) and ("\\" in val or "/" in val):
                p = pathlib.Path(val)
                if p.exists():
                    verified.append({"key": item.key, "path": val, "exists": True})
                else:
                    outdated.append({"key": item.key, "path": val, "exists": False})

        return {
            "success": True,
            "verified_count": len(verified),
            "outdated_count": len(outdated),
            "verified": verified,
            "outdated": outdated,
        }

    # ---------------- 2.C Workflow Memory ----------------
    def remember_workflow(
        self,
        name: str,
        user_query: str,
        plan_json: str,
        steps_summary: str,
        apps_used: List[str],
        tools_used: List[str],
        result_summary: str = "",
        is_successful: bool = True,
    ) -> bool:
        """Store a successful task sequence into Workflow Memory."""
        wf_data = {
            "name": name,
            "user_query": user_query,
            "plan_json": plan_json,
            "steps_summary": steps_summary,
            "apps_used": apps_used,
            "tools_used": tools_used,
            "result_summary": result_summary,
            "is_successful": is_successful,
            "timestamp": utc_now_iso(),
        }
        clean_key = f"workflow_{re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())}"
        return self.save_memory(MemoryCategory.WORKFLOW_MEMORY, clean_key, wf_data, importance=1.2)

    def retrieve_workflow(self, query_or_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a remembered workflow template matching a user query or name."""
        matches = self.search_memory(query_or_name, category=MemoryCategory.WORKFLOW_MEMORY, limit=1)
        if matches:
            val = matches[0].get("value")
            return val if isinstance(val, dict) else json.loads(val)
        return None

    # ---------------- 2.D Conversation Memory ----------------
    def record_conversation_context(
        self,
        user_message: str,
        assistant_message: str = "",
    ) -> ExtractedContext:
        """
        Extract structured context (active project, ongoing task, referenced files)
        from a conversation turn and persist to Conversation Memory without raw message dumps.
        """
        updated_ctx = self.context_extractor.extract_from_interaction(
            user_message, assistant_message, self.current_context
        )
        self.current_context = updated_ctx

        # Save active context
        self.save_memory(
            category=MemoryCategory.CONVERSATION_MEMORY,
            key="active_session_context",
            content=updated_ctx.to_dict(),
            importance=0.9,
        )
        if updated_ctx.active_project:
            proj_key = f"project_{re.sub(r'[^a-zA-Z0-9_]', '_', updated_ctx.active_project.lower())}"
            self.save_memory(
                category=MemoryCategory.CONVERSATION_MEMORY,
                key=proj_key,
                content=updated_ctx.to_dict(),
                importance=1.0,
            )

        return updated_ctx

    def get_active_context(self) -> ExtractedContext:
        """Retrieve currently active conversation context."""
        it = self.retrieve_memory(MemoryCategory.CONVERSATION_MEMORY, "active_session_context")
        if it:
            val = it.value()
            if isinstance(val, dict):
                return ExtractedContext(
                    active_project=val.get("active_project"),
                    ongoing_task=val.get("ongoing_task"),
                    active_files=val.get("active_files", []),
                    key_entities=val.get("key_entities", {}),
                    summary=val.get("summary", ""),
                    timestamp=val.get("timestamp", utc_now_iso()),
                )
        return self.current_context

    # ---------------- 2.E Learning from Corrections ----------------
    def handle_user_correction(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Check if text is a correction or preference directive.
        If yes, saves mistake & correction, sets permanent preference, and returns response.
        """
        parsed = self.correction_handler.parse_correction(text)
        if not parsed:
            return None

        # 1. Record in corrections category
        corr_key = f"correction_{re.sub(r'[^a-zA-Z0-9_]', '_', parsed['preference_key'])}_{int(uuid.uuid4().hex[:6], 16)}"
        self.save_memory(
            category=MemoryCategory.CORRECTIONS,
            key=corr_key,
            content={
                "instruction": text,
                "wrong": parsed.get("wrong", ""),
                "corrected": parsed["corrected"],
                "preference_key": parsed["preference_key"],
                "timestamp": utc_now_iso(),
            },
            importance=1.0,
        )

        # 2. Save as permanent preference
        self.set_user_preference(parsed["preference_key"], parsed["corrected"])

        # If it's a browser preference for a specific site
        if "preferred_browser_for_" in parsed["preference_key"]:
            site_target = parsed["preference_key"].replace("preferred_browser_for_", "")
            try:
                from bolt.browser.website_registry import get_website_registry
                get_website_registry().set_preferred_browser(site_target, parsed["corrected"])
            except Exception as e:
                logger.debug(f"Could not update website registry browser: {e}")

        return parsed

    # =========================================================================
    # TASK EXECUTION PRE-RETRIEVAL (Section 3 Requirement)
    # =========================================================================

    def retrieve_relevant_preferences_for_task(self, instruction: str) -> Dict[str, Any]:
        """
        Retrieve relevant personal preferences and computer knowledge before task execution.
        Discards unrelated memories.
        """
        clean = instruction.lower().strip()
        matched_prefs: Dict[str, Any] = {}

        # 1. Browser preferences for specific web targets
        if any(w in clean for w in ["chatgpt", "gemini", "gmail", "google", "youtube"]):
            for site in ["chatgpt", "gemini", "gmail", "google", "youtube"]:
                if site in clean:
                    pref_b = self.get_user_preference(f"preferred_browser_for_{site}")
                    if pref_b:
                        matched_prefs["preferred_browser"] = str(pref_b).lower()
                        matched_prefs["target_site"] = site
                        break

        # 2. General browser preference
        if "preferred_browser" not in matched_prefs and any(w in clean for w in ["browser", "web", "internet", "website", "online"]):
            pref_b = self.get_user_preference("preferred_browser")
            if pref_b:
                matched_prefs["preferred_browser"] = str(pref_b).lower()
                matched_prefs["preferred_browser"] = pref_b

        # 3. Programming / Code Environment preference ("usual programming environment")
        if any(w in clean for w in ["programming", "coding", "developer", "ide"]):
            pref_ide = self.get_user_preference("preferred_programming_app") or self.get_user_preference("preferred_ide")
            if pref_ide:
                matched_prefs["preferred_programming_app"] = pref_ide

        # 4. Text / Notes preference ("usual text editor", "usual notes app")
        if any(w in clean for w in ["notes", "note", "text editor", "memo"]):
            pref_notes = self.get_user_preference("preferred_notes_app") or self.get_user_preference("preferred_text_editor")
            if pref_notes:
                matched_prefs["preferred_notes_app"] = pref_notes

        # 5. Search memories matching instruction with relevance threshold
        search_hits = self.search_memory(instruction, category=MemoryCategory.PERSONAL_PREFERENCES, limit=2)
        for hit in search_hits:
            k = hit["key"]
            if k not in matched_prefs:
                matched_prefs[k] = hit["value"]

        return matched_prefs


_MEMORY_MANAGER_INSTANCE: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Global singleton access to MemoryManager."""
    global _MEMORY_MANAGER_INSTANCE
    if _MEMORY_MANAGER_INSTANCE is None:
        _MEMORY_MANAGER_INSTANCE = MemoryManager.get_instance()
    return _MEMORY_MANAGER_INSTANCE
