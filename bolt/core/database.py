"""SQLite storage manager for BOLT conversations, messages, settings, and application registry."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bolt.config.constants import DB_PATH, DATA_DIR
from bolt.core.logger import get_logger

logger = get_logger("Database")


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize database schema if not already present."""
        logger.info(f"Initializing database at: {self.db_path}")
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()

                # Conversations table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Messages table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        model TEXT DEFAULT '',
                        tokens INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    );
                    """
                )

                # Settings table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Tasks table (Foundation for Phase 2 & 5 Task Engine)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT,
                        instruction TEXT NOT NULL,
                        status TEXT NOT NULL,
                        plan_json TEXT DEFAULT '{}',
                        result_json TEXT DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        completed_at TEXT
                    );
                    """
                )

                # Application Registry table (Phase 2)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS applications (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        executable_path TEXT DEFAULT '',
                        launch_identifier TEXT NOT NULL,
                        launch_method TEXT NOT NULL,
                        category TEXT DEFAULT 'General',
                        discovery_source TEXT NOT NULL,
                        is_verified INTEGER DEFAULT 0,
                        last_successful_launch TEXT,
                        launch_count INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Website Registry table (Phase 3)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS websites (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL DEFAULT '',
                        url TEXT NOT NULL,
                        category TEXT DEFAULT 'General',
                        description TEXT DEFAULT '',
                        preferred_browser TEXT DEFAULT '',
                        last_successful_access TEXT,
                        access_count INTEGER DEFAULT 0,
                        auth_status TEXT DEFAULT 'none',
                        navigation_procedure TEXT DEFAULT '',
                        is_verified INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Migration: Ensure display_name column exists
                cursor.execute("PRAGMA table_info(websites);")
                columns = [col[1] for col in cursor.fetchall()]
                if "display_name" not in columns:
                    cursor.execute("ALTER TABLE websites ADD COLUMN display_name TEXT DEFAULT '';")
                    cursor.execute("UPDATE websites SET display_name = name WHERE display_name = '';")

                # AI Provider Preferences table (Phase 4)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_provider_preferences (
                        provider TEXT PRIMARY KEY,
                        model TEXT NOT NULL,
                        is_default INTEGER NOT NULL DEFAULT 0,
                        is_available INTEGER NOT NULL DEFAULT 1,
                        last_status TEXT DEFAULT '',
                        last_checked_at TEXT
                    );
                    """
                )

                # AI Connection Test Logs table (Phase 4)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_connection_logs (
                        id TEXT PRIMARY KEY,
                        provider TEXT NOT NULL,
                        status TEXT NOT NULL,
                        latency_ms INTEGER DEFAULT 0,
                        message TEXT DEFAULT '',
                        tested_at TEXT NOT NULL
                    );
                    """
                )

                # Workflows Memory table (Phase 5: Workflow Memory & Reuse)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workflows (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        user_query TEXT NOT NULL,
                        plan_json TEXT NOT NULL DEFAULT '{}',
                        steps_summary TEXT NOT NULL DEFAULT '',
                        apps_used TEXT NOT NULL DEFAULT '[]',
                        tools_used TEXT NOT NULL DEFAULT '[]',
                        result_summary TEXT DEFAULT '',
                        execution_count INTEGER NOT NULL DEFAULT 1,
                        is_successful INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        last_executed_at TEXT NOT NULL
                    );
                    """
                )

                # Migration: Ensure tasks table has Phase 5 columns
                cursor.execute("PRAGMA table_info(tasks);")
                task_cols = [col[1] for col in cursor.fetchall()]
                if "title" not in task_cols:
                    cursor.execute("ALTER TABLE tasks ADD COLUMN title TEXT DEFAULT 'Task';")
                if "progress" not in task_cols:
                    cursor.execute("ALTER TABLE tasks ADD COLUMN progress REAL DEFAULT 0.0;")
                if "current_step_id" not in task_cols:
                    cursor.execute("ALTER TABLE tasks ADD COLUMN current_step_id TEXT DEFAULT '';")

                # Indexes for fast lookups
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id, created_at);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at DESC);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_apps_name ON applications(name);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_apps_category ON applications(category);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_websites_name ON websites(name);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_websites_category ON websites(category);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ai_logs_provider ON ai_connection_logs(provider, tested_at DESC);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_workflows_name ON workflows(name);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at DESC);"
                )

                # Seed initial verified websites (Section 3 of Phase 3 Requirements)
                seed_websites = [
                    ("chatgpt", "ChatGPT", "https://chatgpt.com/", "AI Assistant", "OpenAI conversational assistant", "required"),
                    ("gemini", "Gemini", "https://gemini.google.com/", "AI Assistant", "Google Gemini conversational assistant", "required"),
                    ("gmail", "Gmail", "https://mail.google.com/", "Communication", "Google Webmail service", "required"),
                    ("google", "Google", "https://www.google.com/", "Search Engine", "Google Search Engine", "none"),
                    ("google drive", "Google Drive", "https://drive.google.com/", "Cloud Storage", "Google Cloud Storage and Documents", "required"),
                    ("youtube", "YouTube", "https://www.youtube.com/", "Media", "Online Video Streaming", "none"),
                ]
                now_str = utc_now_iso()
                for w_name, w_disp, w_url, w_cat, w_desc, w_auth in seed_websites:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO websites (
                            id, name, display_name, url, category, description,
                            auth_status, is_verified, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (str(uuid.uuid4()), w_name, w_disp, w_url, w_cat, w_desc, w_auth, now_str, now_str)
                    )
            logger.info("Database schema verified successfully.")
        finally:
            conn.close()

    # ---------------- Conversations ----------------

    def create_conversation(
        self,
        title: str = "New Conversation",
        provider: str = "gemini",
        model: str = "gemini-2.5-flash",
    ) -> str:
        """Create a new conversation session and return its UUID."""
        conv_id = str(uuid.uuid4())
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO conversations (id, title, provider, model, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (conv_id, title, provider, model, now, now),
                )
            logger.debug(f"Created conversation: {conv_id} ({title})")
            return conv_id
        finally:
            conn.close()

    def get_conversations(self) -> List[Dict[str, Any]]:
        """Return all conversations ordered by last update descending."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title, provider, model, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single conversation by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, provider, model, created_at, updated_at FROM conversations WHERE id = ?",
                (conv_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_conversation_title(self, conv_id: str, title: str) -> None:
        """Update conversation title."""
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title, now, conv_id),
                )
        finally:
            conn.close()

    def touch_conversation(self, conv_id: str) -> None:
        """Update the updated_at timestamp of a conversation."""
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conv_id),
                )
        finally:
            conn.close()

    def delete_conversation(self, conv_id: str) -> None:
        """Delete a conversation and all its cascade-associated messages."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            logger.debug(f"Deleted conversation: {conv_id}")
        finally:
            conn.close()

    # ---------------- Messages ----------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: str = "",
        tokens: int = 0,
    ) -> str:
        """Add a message to a conversation."""
        msg_id = str(uuid.uuid4())
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, role, content, model, tokens, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (msg_id, conversation_id, role, content, model, tokens, now),
                )
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
            return msg_id
        finally:
            conn.close()

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Fetch all messages for a given conversation in chronological order."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, conversation_id, role, content, model, tokens, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def clear_conversation_messages(self, conversation_id: str) -> None:
        """Clear all messages from a conversation."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        finally:
            conn.close()

    # ---------------- Application Registry (Phase 2) ----------------

    def upsert_application(
        self,
        name: str,
        display_name: str,
        launch_identifier: str,
        launch_method: str = "direct_exe",
        executable_path: str = "",
        category: str = "General",
        discovery_source: str = "start_menu",
        is_verified: int = 0,
    ) -> str:
        """Insert or update an application in the registry."""
        normalized_name = name.strip().lower()
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM applications WHERE name = ?", (normalized_name,))
            existing = cursor.fetchone()

            if existing:
                app_id = existing["id"]
                with conn:
                    conn.execute(
                        """
                        UPDATE applications
                        SET display_name = ?, executable_path = ?, launch_identifier = ?,
                            launch_method = ?, category = ?, discovery_source = ?,
                            is_verified = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            display_name,
                            executable_path,
                            launch_identifier,
                            launch_method,
                            category,
                            discovery_source,
                            is_verified,
                            now,
                            app_id,
                        ),
                    )
            else:
                app_id = str(uuid.uuid4())
                with conn:
                    conn.execute(
                        """
                        INSERT INTO applications (
                            id, name, display_name, executable_path, launch_identifier,
                            launch_method, category, discovery_source, is_verified,
                            last_successful_launch, launch_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?)
                        """,
                        (
                            app_id,
                            normalized_name,
                            display_name,
                            executable_path,
                            launch_identifier,
                            launch_method,
                            category,
                            discovery_source,
                            is_verified,
                            now,
                            now,
                        ),
                    )
            return app_id
        finally:
            conn.close()

    def get_application_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up application by exact normalized name."""
        normalized = name.strip().lower()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications WHERE name = ?", (normalized,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_applications(self, query: str) -> List[Dict[str, Any]]:
        """Search applications by name or display name."""
        q = f"%{query.strip().lower()}%"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM applications
                WHERE name LIKE ? OR display_name LIKE ?
                ORDER BY launch_count DESC, display_name ASC
                """,
                (q, q),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_applications(self) -> List[Dict[str, Any]]:
        """Fetch all registered applications."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications ORDER BY display_name ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def record_app_launch_success(self, app_id: str) -> None:
        """Record successful launch, increment launch count and mark verified."""
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE applications
                    SET last_successful_launch = ?,
                        launch_count = launch_count + 1,
                        is_verified = 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, app_id),
                )
        finally:
            conn.close()

    def delete_application(self, app_id: str) -> None:
        """Delete an application from registry."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        finally:
            conn.close()

    # ---------------- Website Registry (Phase 3) ----------------

    def upsert_website(
        self,
        name: str,
        display_name: str,
        url: str,
        category: str = "General",
        description: str = "",
        preferred_browser: str = "",
        auth_status: str = "none",
        navigation_procedure: str = "",
        is_verified: int = 1,
    ) -> str:
        """Insert or update a registered website in SQLite knowledge store."""
        now = utc_now_iso()
        site_id = str(uuid.uuid4())
        name_clean = name.strip().lower()

        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO websites (
                        id, name, display_name, url, category, description,
                        preferred_browser, auth_status, navigation_procedure,
                        is_verified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        display_name = excluded.display_name,
                        url = excluded.url,
                        category = excluded.category,
                        description = excluded.description,
                        preferred_browser = CASE WHEN excluded.preferred_browser != '' THEN excluded.preferred_browser ELSE websites.preferred_browser END,
                        auth_status = excluded.auth_status,
                        navigation_procedure = CASE WHEN excluded.navigation_procedure != '' THEN excluded.navigation_procedure ELSE websites.navigation_procedure END,
                        is_verified = excluded.is_verified,
                        updated_at = excluded.updated_at;
                    """,
                    (
                        site_id, name_clean, display_name, url, category, description,
                        preferred_browser, auth_status, navigation_procedure,
                        is_verified, now, now
                    ),
                )
            logger.debug(f"Upserted website: '{name_clean}' -> {url}")
            return site_id
        finally:
            conn.close()

    def get_website_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch website record by case-insensitive name."""
        name_clean = name.strip().lower()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM websites WHERE name = ?", (name_clean,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_websites(self, query: str) -> List[Dict[str, Any]]:
        """Fuzzy search websites by name, display name, url, or description."""
        q = f"%{query.strip().lower()}%"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM websites
                WHERE name LIKE ? OR display_name LIKE ? OR url LIKE ? OR description LIKE ?
                ORDER BY access_count DESC, display_name ASC
                """,
                (q, q, q, q),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_websites(self) -> List[Dict[str, Any]]:
        """Fetch all registered websites."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM websites ORDER BY access_count DESC, display_name ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def record_website_access_success(self, name_or_id: str) -> None:
        """Record successful website visit, increment access count, and update timestamp."""
        now = utc_now_iso()
        name_clean = name_or_id.strip().lower()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE websites
                    SET last_successful_access = ?,
                        access_count = access_count + 1,
                        is_verified = 1,
                        updated_at = ?
                    WHERE id = ? OR name = ?
                    """,
                    (now, now, name_or_id, name_clean),
                )
        finally:
            conn.close()

    def delete_website(self, site_id: str) -> None:
        """Delete website from registry."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM websites WHERE id = ? OR name = ?", (site_id, site_id.lower()))
        finally:
            conn.close()

    # ---------------- AI Provider Preferences & Logs (Phase 4) ----------------

    def set_provider_preference(
        self,
        provider: str,
        model: str,
        is_default: bool = False,
        is_available: bool = True,
        last_status: str = "",
    ) -> None:
        """Persist or update AI provider preference and status."""
        conn = self._get_connection()
        now = utc_now_iso()
        norm_provider = provider.lower().strip()
        try:
            with conn:
                if is_default:
                    conn.execute("UPDATE ai_provider_preferences SET is_default = 0")

                conn.execute(
                    """
                    INSERT INTO ai_provider_preferences (provider, model, is_default, is_available, last_status, last_checked_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider) DO UPDATE SET
                        model = excluded.model,
                        is_default = CASE WHEN excluded.is_default = 1 THEN 1 ELSE is_default END,
                        is_available = excluded.is_available,
                        last_status = excluded.last_status,
                        last_checked_at = excluded.last_checked_at
                    """,
                    (norm_provider, model, 1 if is_default else 0, 1 if is_available else 0, last_status, now),
                )
        finally:
            conn.close()

    def set_default_provider(self, provider: str) -> None:
        """Set a provider as the default AI engine."""
        conn = self._get_connection()
        norm_provider = provider.lower().strip()
        try:
            with conn:
                conn.execute("UPDATE ai_provider_preferences SET is_default = 0")
                conn.execute(
                    "UPDATE ai_provider_preferences SET is_default = 1 WHERE provider = ?",
                    (norm_provider,),
                )
        finally:
            conn.close()

    def get_provider_preference(self, provider: str) -> Optional[Dict[str, Any]]:
        """Fetch saved preference for a specific provider."""
        conn = self._get_connection()
        norm_provider = provider.lower().strip()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT provider, model, is_default, is_available, last_status, last_checked_at FROM ai_provider_preferences WHERE provider = ?",
                (norm_provider,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_provider_preferences(self) -> List[Dict[str, Any]]:
        """Fetch all stored AI provider preferences."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT provider, model, is_default, is_available, last_status, last_checked_at FROM ai_provider_preferences ORDER BY is_default DESC, provider ASC"
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def log_connection_test(
        self, provider: str, status: str, latency_ms: int = 0, message: str = ""
    ) -> None:
        """Record an AI provider connection health check log."""
        conn = self._get_connection()
        log_id = str(uuid.uuid4())
        now = utc_now_iso()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO ai_connection_logs (id, provider, status, latency_ms, message, tested_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (log_id, provider.lower().strip(), status, latency_ms, message, now),
                )
        finally:
            conn.close()

    def get_recent_connection_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent connection logs."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, provider, status, latency_ms, message, tested_at
                FROM ai_connection_logs
                ORDER BY tested_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ---------------- Phase 5: Tasks & Execution History ----------------

    def create_task_record(
        self,
        task_id: str,
        conversation_id: Optional[str],
        instruction: str,
        title: str = "Task",
        status: str = "PENDING",
        plan_json: str = "{}",
    ) -> str:
        """Create a new task execution record in SQLite (idempotent upsert)."""
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO tasks (id, conversation_id, title, instruction, status, plan_json, result_json, progress, current_step_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, '{}', 0.0, '', ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        plan_json = excluded.plan_json
                    """,
                    (task_id, conversation_id, title, instruction, status, plan_json, now),
                )
            return task_id
        finally:
            conn.close()

    def update_task_record(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        current_step_id: Optional[str] = None,
        plan_json: Optional[str] = None,
        result_json: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Update an existing task's execution state."""
        conn = self._get_connection()
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if progress is not None:
            updates.append("progress = ?")
            params.append(float(progress))
        if current_step_id is not None:
            updates.append("current_step_id = ?")
            params.append(current_step_id)
        if plan_json is not None:
            updates.append("plan_json = ?")
            params.append(plan_json)
        if result_json is not None:
            updates.append("result_json = ?")
            params.append(result_json)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        if not updates:
            conn.close()
            return

        params.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        try:
            with conn:
                conn.execute(sql, tuple(params))
        finally:
            conn.close()

    def get_task_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a task record by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_recent_task_records(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieve recent task execution records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, conversation_id, title, instruction, status, progress, current_step_id, created_at, completed_at
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ---------------- Phase 5: Workflow Memory & Reuse ----------------

    def save_workflow_template(
        self,
        name: str,
        user_query: str,
        plan_json: str,
        steps_summary: str,
        apps_used: str = "[]",
        tools_used: str = "[]",
        result_summary: str = "",
        is_successful: int = 1,
    ) -> str:
        """Store or update a successful workflow template for future recall."""
        conn = self._get_connection()
        now = utc_now_iso()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, execution_count FROM workflows WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:
                wf_id = existing["id"]
                count = existing["execution_count"] + 1
                with conn:
                    conn.execute(
                        """
                        UPDATE workflows
                        SET user_query = ?, plan_json = ?, steps_summary = ?, apps_used = ?,
                            tools_used = ?, result_summary = ?, execution_count = ?,
                            is_successful = ?, last_executed_at = ?
                        WHERE id = ?
                        """,
                        (
                            user_query, plan_json, steps_summary, apps_used,
                            tools_used, result_summary, count, is_successful, now, wf_id,
                        ),
                    )
                return wf_id
            else:
                wf_id = str(uuid.uuid4())
                with conn:
                    conn.execute(
                        """
                        INSERT INTO workflows (
                            id, name, user_query, plan_json, steps_summary,
                            apps_used, tools_used, result_summary, execution_count,
                            is_successful, created_at, last_executed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                        """,
                        (
                            wf_id, name, user_query, plan_json, steps_summary,
                            apps_used, tools_used, result_summary, is_successful, now, now,
                        ),
                    )
                return wf_id
        finally:
            conn.close()

    def get_workflow_template(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a workflow template by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_workflows(self) -> List[Dict[str, Any]]:
        """List all remembered workflows sorted by execution count and recency."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, user_query, plan_json, steps_summary, apps_used, tools_used,
                       result_summary, execution_count, is_successful, created_at, last_executed_at
                FROM workflows
                ORDER BY execution_count DESC, last_executed_at DESC
                """
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def search_workflows(self, query: str) -> List[Dict[str, Any]]:
        """Search remembered workflows by name or user query."""
        q = f"%{query.strip().lower()}%"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM workflows
                WHERE LOWER(name) LIKE ? OR LOWER(user_query) LIKE ?
                ORDER BY execution_count DESC, last_executed_at DESC
                """,
                (q, q),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def record_workflow_execution(self, workflow_id: str, is_successful: bool = True) -> None:
        """Increment execution count and update timestamp of a workflow."""
        conn = self._get_connection()
        now = utc_now_iso()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE workflows
                    SET execution_count = execution_count + 1,
                        is_successful = ?,
                        last_executed_at = ?
                    WHERE id = ?
                    """,
                    (1 if is_successful else 0, now, workflow_id),
                )
        finally:
            conn.close()


_DB_INSTANCE: Optional[Database] = None


def get_database() -> Database:
    """Singleton getter for the SQLite database manager."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = Database()
    return _DB_INSTANCE
