"""SQLite storage manager for BOLT conversations, messages, and settings."""

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

                # Indexes for fast lookups
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id, created_at);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at DESC);"
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


_DB_INSTANCE: Optional[Database] = None


def get_database() -> Database:
    """Singleton getter for the SQLite database manager."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = Database()
    return _DB_INSTANCE
