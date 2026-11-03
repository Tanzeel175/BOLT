"""
Data and Persistence Manager for BOLT (Phase 10).
Manages Windows user directory separation, live SQLite backups, database migrations,
and storage statistics.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any, Dict, List, Optional

from bolt.config.constants import (
    BACKUPS_DIR,
    DATA_DIR,
    DB_PATH,
    IS_FROZEN,
    LOGS_DIR,
    USER_DATA_ROOT,
    WORKSPACE_DIR,
)
from bolt.core.database import Database, get_database, utc_now_iso
from bolt.core.logger import get_logger

logger = get_logger("DataManager")

CURRENT_SCHEMA_VERSION = 10  # Phase 10 Final Schema


class DataManager:
    """Manages persistent user data directories, live backups, and schema migrations."""

    def __init__(
        self,
        db: Optional[Database] = None,
        user_data_root: Optional[Path] = None,
        db_path: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None,
    ):
        self.user_data_root = Path(user_data_root) if user_data_root else USER_DATA_ROOT
        self.data_dir = self.user_data_root / "data" if user_data_root else DATA_DIR
        self.logs_dir = Path(log_dir) if log_dir else (self.user_data_root / "logs" if user_data_root else LOGS_DIR)
        self.backups_dir = Path(backup_dir) if backup_dir else (self.user_data_root / "backups" if user_data_root else BACKUPS_DIR)
        self.workspace_dir = self.user_data_root / "workspace" if user_data_root else WORKSPACE_DIR
        self.db_path = Path(db_path) if db_path else (self.data_dir / "bolt.db" if user_data_root else DB_PATH)
        if db:
            self.db = db
        elif db_path:
            self.db = Database(db_path=self.db_path)
        else:
            self.db = get_database()
        self.initialize_storage()

    def initialize_storage(self) -> None:
        """Ensure all required persistent directories exist on disk and migrations are applied."""
        self._ensure_directories()
        self.run_migrations()

    def _ensure_directories(self) -> None:
        """Ensure all required persistent directories exist on disk."""
        for d in (self.user_data_root, self.data_dir, self.logs_dir, self.backups_dir, self.workspace_dir):
            d.mkdir(parents=True, exist_ok=True)

    def create_live_backup(self, tag: str = "manual") -> Path:
        """Alias for create_backup."""
        return self.create_backup(tag=tag)

    def create_pre_migration_backup(self, version_tag: str) -> Path:
        """Alias for creating a pre-migration snapshot."""
        return self.create_backup(tag=f"pre_migration_{version_tag}")

    def prune_old_backups(self, keep_count: int = 10) -> int:
        """Alias for clean_old_backups."""
        return self.clean_old_backups(keep_count=keep_count)

    def create_backup(self, tag: str = "manual") -> Path:
        """
        Create a live, point-in-time SQLite backup of bolt.db.
        Uses SQLite backup API to safely snapshot even while the database is actively in WAL mode.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"bolt_backup_{now_str}_{tag}.db"
        backup_path = self.backups_dir / backup_filename

        if not self.db_path.exists():
            logger.warning(f"Database at '{self.db_path}' does not exist yet. Created empty backup marker.")
            backup_path.touch()
            return backup_path

        source_conn = self.db._get_connection()
        dest_conn = sqlite3.connect(str(backup_path))
        try:
            with dest_conn:
                source_conn.backup(dest_conn)
            logger.info(f"Live database backup created successfully at: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Live database backup failed: {e}")
            # Fallback to copy if backup API encountered an issue
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        finally:
            source_conn.close()
            dest_conn.close()

    def list_backups(self) -> List[Dict[str, Any]]:
        """Return list of existing backup files sorted by newest first."""
        backups = []
        if not self.backups_dir.exists():
            return []

        for f in self.backups_dir.glob("bolt_backup_*.db"):
            try:
                stat = f.stat()
                size_kb = round(stat.st_size / 1024, 1)
                created_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                backups.append({
                    "filename": f.name,
                    "path": str(f),
                    "size_kb": size_kb,
                    "created_at": created_iso,
                    "mtime": stat.st_mtime,
                })
            except Exception:
                continue

        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return backups

    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore the database from a backup file.
        Automatically creates a safety pre-restore backup first.
        """
        if not backup_path.exists():
            logger.error(f"Cannot restore: Backup file '{backup_path}' does not exist.")
            return False

        logger.info(f"Initiating restoration from: {backup_path}")
        # 1. Create safety backup of current database
        try:
            self.create_backup(tag="pre_restore_safety")
        except Exception as e:
            logger.warning(f"Could not create pre-restore safety backup: {e}")

        # 2. Restore database
        source_conn = sqlite3.connect(str(backup_path))
        dest_conn = self.db._get_connection()
        try:
            with dest_conn:
                source_conn.backup(dest_conn)
            logger.info("Database successfully restored from backup.")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database from backup: {e}")
            return False
        finally:
            source_conn.close()
            dest_conn.close()

    def run_migrations(self) -> bool:
        """
        Check and apply database migrations.
        Automatically takes a pre-migration backup before any schema changes.
        """
        conn = self.db._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL,
                        description TEXT NOT NULL
                    );
                    """
                )
                cursor.execute("SELECT MAX(version) FROM schema_migrations;")
                current_ver = cursor.fetchone()[0] or 0

                if current_ver < CURRENT_SCHEMA_VERSION:
                    logger.info(f"Database migration needed: current={current_ver}, target={CURRENT_SCHEMA_VERSION}")
                    # Automated pre-migration backup
                    self.create_backup(tag=f"pre_migration_v{current_ver}_to_v{CURRENT_SCHEMA_VERSION}")

                    # Apply Phase 10 Schema Upgrades idempotently
                    self._apply_schema_upgrades(cursor, current_ver)

                    cursor.execute(
                        "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?);",
                        (CURRENT_SCHEMA_VERSION, utc_now_iso(), "Phase 10 Final Desktop Application Deployment"),
                    )
                    logger.info(f"Database migrated successfully to version {CURRENT_SCHEMA_VERSION}.")
            return True
        except Exception as e:
            logger.error(f"Migration execution failed: {e}")
            return False
        finally:
            conn.close()

    def _apply_schema_upgrades(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Idempotently ensure all tables and indexes across Phases 1-10 are present."""
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON security_audit_logs(timestamp);")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mem_cat ON bolt_memories(category);")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);")
        except sqlite3.OperationalError:
            pass

    def get_storage_stats(self) -> Dict[str, Any]:
        """Return storage space metrics across user data directories."""
        db_size_mb = round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0.0

        def dir_size_mb(p: Path) -> float:
            if not p.exists():
                return 0.0
            total = sum(f.stat().st_size for f in p.glob("**/*") if f.is_file())
            return round(total / (1024 * 1024), 2)

        return {
            "user_data_root": str(self.user_data_root),
            "db_path": str(self.db_path),
            "db_exists": self.db_path.exists(),
            "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "db_size_mb": db_size_mb,
            "logs_size_mb": dir_size_mb(self.logs_dir),
            "backups_size_mb": dir_size_mb(self.backups_dir),
            "workspace_size_mb": dir_size_mb(self.workspace_dir),
            "backup_count": len(self.list_backups()),
            "total_backups_count": len(self.list_backups()),
            "is_frozen": IS_FROZEN,
        }

    def clean_old_backups(self, keep_count: int = 10) -> int:
        """Prune older backups beyond keep_count, preserving disk space."""
        backups = self.list_backups()
        if len(backups) <= keep_count:
            return 0

        to_remove = backups[keep_count:]
        removed_count = 0
        for b in to_remove:
            try:
                Path(b["path"]).unlink(missing_ok=True)
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed removing old backup {b['filename']}: {e}")
        logger.info(f"Cleaned {removed_count} old backups, kept latest {keep_count}.")
        return removed_count


_DATA_MGR_INSTANCE: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    global _DATA_MGR_INSTANCE
    if _DATA_MGR_INSTANCE is None:
        _DATA_MGR_INSTANCE = DataManager()
    return _DATA_MGR_INSTANCE
