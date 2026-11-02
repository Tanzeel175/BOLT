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
                        url TEXT NOT NULL,
                        category TEXT DEFAULT 'General',
                        description TEXT DEFAULT '',
                        preferred_browser TEXT DEFAULT '',
                        last_successful_access TEXT,
                        access_count INTEGER DEFAULT 0,
                        auth_status TEXT DEFAULT 'none',
                        navigation_procedure TEXT DEFAULT 'direct_url',
                        is_verified INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

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
                    "CREATE INDEX IF NOT EXISTS idx_websites_url ON websites(url);"
                )

                # Seed initial default websites
                self._seed_initial_websites(cursor)
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

    def _seed_initial_websites(self, cursor: sqlite3.Cursor) -> None:
        """Seed default known websites into website registry if not already present."""
        initial_sites = [
            {
                "name": "chatgpt",
                "url": "https://chatgpt.com/",
                "category": "AI Assistant",
                "description": "OpenAI ChatGPT conversational AI web interface",
                "auth_status": "login_supported",
            },
            {
                "name": "gemini",
                "url": "https://gemini.google.com/",
                "category": "AI Assistant",
                "description": "Google Gemini conversational AI assistant",
                "auth_status": "login_supported",
            },
            {
                "name": "gmail",
                "url": "https://mail.google.com/",
                "category": "Email & Productivity",
                "description": "Google Mail web application",
                "auth_status": "login_required",
            },
            {
                "name": "google",
                "url": "https://www.google.com/",
                "category": "Search Engine",
                "description": "Google Web Search engine",
                "auth_status": "none",
            },
            {
                "name": "google drive",
                "url": "https://drive.google.com/",
                "category": "Cloud Storage & Productivity",
                "description": "Google Drive cloud file storage and office tools",
                "auth_status": "login_required",
            },
            {
                "name": "youtube",
                "url": "https://www.youtube.com/",
                "category": "Media & Video",
                "description": "YouTube video sharing and streaming platform",
                "auth_status": "none",
            },
        ]
        now = utc_now_iso()
        for site in initial_sites:
            cursor.execute("SELECT id FROM websites WHERE name = ?", (site["name"],))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO websites (
                        id, name, url, category, description,
                        preferred_browser, auth_status, navigation_procedure,
                        is_verified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        site["name"],
                        site["url"],
                        site["category"],
                        site["description"],
                        "",
                        site["auth_status"],
                        "direct_url",
                        1,
                        now,
                        now,
                    ),
                )

    def upsert_website(
        self,
        name: str,
        url: str,
        category: str = "General",
        description: str = "",
        preferred_browser: str = "",
        auth_status: str = "none",
        navigation_procedure: str = "direct_url",
        is_verified: bool = True,
    ) -> Dict[str, Any]:
        """Insert or update a website entry in the persistent website registry."""
        clean_name = name.strip().lower()
        clean_url = url.strip()
        now = utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM websites WHERE name = ?", (clean_name,))
                existing = cursor.fetchone()
                if existing:
                    site_id = existing["id"]
                    cursor.execute(
                        """
                        UPDATE websites
                        SET url = ?,
                            category = ?,
                            description = ?,
                            preferred_browser = ?,
                            auth_status = ?,
                            navigation_procedure = ?,
                            is_verified = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            clean_url,
                            category,
                            description,
                            preferred_browser,
                            auth_status,
                            navigation_procedure,
                            1 if is_verified else 0,
                            now,
                            site_id,
                        ),
                    )
                else:
                    site_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO websites (
                            id, name, url, category, description,
                            preferred_browser, auth_status, navigation_procedure,
                            is_verified, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            site_id,
                            clean_name,
                            clean_url,
                            category,
                            description,
                            preferred_browser,
                            auth_status,
                            navigation_procedure,
                            1 if is_verified else 0,
                            now,
                            now,
                        ),
                    )

                cursor.execute("SELECT * FROM websites WHERE id = ?", (site_id,))
                return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_website_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch website by its unique name/identifier."""
        clean = name.strip().lower()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM websites WHERE name = ?", (clean,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            # Try fuzzy match
            cursor.execute(
                "SELECT * FROM websites WHERE name LIKE ? OR description LIKE ? LIMIT 1",
                (f"%{clean}%", f"%{clean}%"),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_website_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch website by its URL (or prefix)."""
        clean = url.strip().rstrip("/")
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM websites WHERE url = ? OR url = ?", (clean, clean + "/"))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_websites(self) -> List[Dict[str, Any]]:
        """Fetch all websites in registry ordered by name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM websites ORDER BY name ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def record_website_access_success(self, site_id_or_name: str) -> None:
        """Record successful website access, increment counter, mark verified."""
        now = utc_now_iso()
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
                    (now, now, site_id_or_name, site_id_or_name.lower()),
                )
        finally:
            conn.close()

    def delete_website(self, site_id_or_name: str) -> None:
        """Delete a website from the registry."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "DELETE FROM websites WHERE id = ? OR name = ?",
                    (site_id_or_name, site_id_or_name.lower()),
                )
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
                    # Clear default flag on others
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


_DB_INSTANCE: Optional[Database] = None


def get_database() -> Database:
    """Singleton getter for the SQLite database manager."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = Database()
    return _DB_INSTANCE
