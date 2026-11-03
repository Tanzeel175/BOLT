r"""
Tests for Phase 10: Final Desktop Application and Windows Deployment.
Validates:
- DataManager: SQLite live WAL backups, pre-migration snapshots, user data isolation (%LOCALAPPDATA%\BOLT)
- LocalAIRuntimeManager: Ollama binary detection, service probe, model enumeration, offline reliability
- SetupWizard: First-run detection, system specification verification, checklist validation
- SettingsDialog: AI brain, voice, security permissions, backup triggers, safe reset
- SystemTray: Notification capabilities, context menu, background minimization
- Metadata & PyInstaller Spec: version_info.txt, bolt.spec, icon assets
- 100% Offline Guarantee: Zero network dependency for deployment and local administration
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Windows DLL directories & plugin paths for PySide6
if sys.platform == "win32":
    for p in sys.path:
        try:
            p_path = Path(p)
            for sub in ("PySide6", "shiboken6"):
                dll_dir = p_path / sub
                if dll_dir.is_dir() and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(dll_dir))

            pyside_dir = p_path / "PySide6"
            if pyside_dir.is_dir():
                plugins_dir = pyside_dir / "plugins"
                if plugins_dir.is_dir():
                    os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins_dir / "platforms")
        except Exception:
            pass

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for GUI tests
app = QApplication.instance()
if app is None:
    app = QApplication([])

from bolt.__version__ import __app_name__, __version__
from bolt.ai.runtime_manager import LocalAIRuntimeManager, get_runtime_manager
from bolt.config.constants import (
    APP_ICON_ICO,
    APP_ICON_PNG,
    APP_NAME,
    APP_USER_MODEL_ID,
    APP_VERSION,
    BACKUP_DIR,
    DATABASE_PATH,
    USER_DATA_ROOT,
)
from bolt.config.settings import get_settings
from bolt.core.data_manager import DataManager, get_data_manager
from bolt.ui.settings_dialog import SettingsDialog
from bolt.ui.setup_wizard import SetupWizardDialog, is_first_run, mark_first_run_complete
from bolt.ui.system_tray import BOLTSystemTray


class TestPhase10Deployment(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="bolt_test_phase10_")
        self.temp_root = Path(self.temp_dir)
        self.mock_db_path = self.temp_root / "test_bolt.db"
        self.mock_backup_dir = self.temp_root / "backups"
        self.mock_log_dir = self.temp_root / "logs"

        # Initialize mock SQLite DB with WAL mode
        conn = sqlite3.connect(str(self.mock_db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, key TEXT, value TEXT);")
        conn.execute("INSERT INTO test_data (key, value) VALUES ('test_key', 'test_value');")
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. User Data Isolation and DataManager Tests
    # -------------------------------------------------------------------------
    def test_01_user_data_isolation_paths(self):
        """Verify USER_DATA_ROOT and subdirectories are properly structured."""
        self.assertTrue(USER_DATA_ROOT.name.upper() == "BOLT" or "BOLT" in str(USER_DATA_ROOT))
        self.assertEqual(APP_NAME, "BOLT")
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(__version__, "1.0.0")
        self.assertIn("BOLT", APP_USER_MODEL_ID)

    def test_02_data_manager_initialization_and_metrics(self):
        """Verify DataManager creates directory hierarchy and computes storage metrics."""
        mgr = DataManager(
            user_data_root=self.temp_root,
            db_path=self.mock_db_path,
            backup_dir=self.mock_backup_dir,
            log_dir=self.mock_log_dir,
        )
        mgr.initialize_storage()

        self.assertTrue(self.mock_backup_dir.exists())
        self.assertTrue(self.mock_log_dir.exists())

        stats = mgr.get_storage_stats()
        self.assertTrue(stats["db_exists"])
        self.assertGreater(stats["db_size_bytes"], 0)
        self.assertGreaterEqual(stats["backup_count"], 0)

    def test_03_live_wal_sqlite_backup_and_restore(self):
        """Verify atomic live SQLite backup using SQLite online backup API and restoration."""
        mgr = DataManager(
            user_data_root=self.temp_root,
            db_path=self.mock_db_path,
            backup_dir=self.mock_backup_dir,
            log_dir=self.mock_log_dir,
        )
        mgr.initialize_storage()

        # Perform live backup
        backup_file = mgr.create_live_backup(tag="phase10_test")
        self.assertTrue(backup_file.exists())
        self.assertIn("phase10_test", backup_file.name)

        # Verify backup contains valid data
        b_conn = sqlite3.connect(str(backup_file))
        cursor = b_conn.cursor()
        cursor.execute("SELECT value FROM test_data WHERE key='test_key'")
        row = cursor.fetchone()
        b_conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "test_value")

        # Mutate main database
        conn = sqlite3.connect(str(self.mock_db_path))
        conn.execute("UPDATE test_data SET value='mutated_value' WHERE key='test_key'")
        conn.commit()
        conn.close()

        # Restore from backup
        restored = mgr.restore_backup(backup_file)
        self.assertTrue(restored)

        # Verify restored state
        r_conn = sqlite3.connect(str(self.mock_db_path))
        r_cur = r_conn.cursor()
        r_cur.execute("SELECT value FROM test_data WHERE key='test_key'")
        restored_val = r_cur.fetchone()[0]
        r_conn.close()
        self.assertEqual(restored_val, "test_value")

    def test_04_pre_migration_backup_and_pruning(self):
        """Verify pre-migration snapshot creation and backup rotation."""
        mgr = DataManager(
            user_data_root=self.temp_root,
            db_path=self.mock_db_path,
            backup_dir=self.mock_backup_dir,
            log_dir=self.mock_log_dir,
        )
        mgr.initialize_storage()

        # Create multiple backups
        b1 = mgr.create_pre_migration_backup("v1.0.0")
        b2 = mgr.create_live_backup("snapshot2")
        b3 = mgr.create_live_backup("snapshot3")

        backups = mgr.list_backups()
        self.assertGreaterEqual(len(backups), 3)

        # Prune keeping only 1
        deleted = mgr.prune_old_backups(keep_count=1)
        self.assertGreaterEqual(deleted, 2)
        self.assertLessEqual(len(mgr.list_backups()), 1)

    # -------------------------------------------------------------------------
    # 2. Local AI Runtime Manager Tests
    # -------------------------------------------------------------------------
    def test_05_runtime_manager_binary_and_status(self):
        """Verify LocalAIRuntimeManager inspection and status summary."""
        rt_mgr = get_runtime_manager()
        self.assertIsInstance(rt_mgr, LocalAIRuntimeManager)

        status = rt_mgr.get_status_summary()
        self.assertIn("ollama_installed", status)
        self.assertIn("service_running", status)
        self.assertIn("models_found", status)
        self.assertIn("recommended_present", status)
        self.assertIn("gemma4:e2b", status["recommended_present"])

    def test_06_runtime_manager_mock_service_probe(self):
        """Verify runtime manager handles HTTP responses cleanly when Ollama responds."""
        rt_mgr = LocalAIRuntimeManager(custom_binary_path="dummy_ollama.exe")

        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "models": [
                    {"name": "gemma4:e2b"},
                    {"name": "llama3.2:3b"},
                ]
            }
            mock_get.return_value = mock_resp

            self.assertTrue(rt_mgr.is_service_running())
            models = rt_mgr.get_installed_models()
            self.assertIn("gemma4:e2b", models)
            self.assertIn("llama3.2:3b", models)
            self.assertTrue(rt_mgr.is_recommended_model_installed())

    def test_07_runtime_manager_offline_resilience(self):
        """Verify runtime manager does not crash or hang when service is unavailable."""
        rt_mgr = LocalAIRuntimeManager(custom_binary_path="nonexistent_ollama_12345.exe")
        self.assertFalse(rt_mgr.is_installed())

        with patch("requests.get", side_effect=Exception("Connection refused")):
            self.assertFalse(rt_mgr.is_service_running())
            self.assertEqual(rt_mgr.get_installed_models(), [])
            self.assertFalse(rt_mgr.is_recommended_model_installed())

    # -------------------------------------------------------------------------
    # 3. Setup Wizard & First Run Tests
    # -------------------------------------------------------------------------
    def test_08_setup_wizard_first_run_cycle(self):
        """Verify first run flag detection, completion marking, and wizard checklist."""
        marker = self.temp_root / ".setup_completed"

        with patch("bolt.ui.setup_wizard.FIRST_RUN_MARKER", marker):
            self.assertTrue(is_first_run())
            mark_first_run_complete()
            self.assertFalse(is_first_run())

    def test_09_setup_wizard_checks_execution(self):
        """Verify setup wizard hardware, OS, and offline compatibility checks."""
        wizard = SetupWizardDialog()
        results = wizard.run_checks()

        self.assertIn("os_ok", results)
        self.assertIn("cpu_ok", results)
        self.assertIn("ram_ok", results)
        self.assertIn("storage_ok", results)
        self.assertIn("ollama_ok", results)
        self.assertIn("voice_ok", results)
        self.assertIn("specs", results)

        # Host system has 16GB RAM and Win11/x64
        self.assertTrue(results["ram_ok"])
        self.assertTrue(results["storage_ok"])
        wizard.close()

    # -------------------------------------------------------------------------
    # 4. Settings Dialog Tests
    # -------------------------------------------------------------------------
    def test_10_settings_dialog_tabs_and_values(self):
        """Verify settings dialog loads configurations across AI, Voice, Security, and Storage."""
        dialog = SettingsDialog()
        self.assertIsNotNone(dialog)

        # Check tab names or presence
        tab_count = dialog.tabs.count()
        self.assertGreaterEqual(tab_count, 4)

        # Verify setting load
        settings = get_settings()
        self.assertEqual(dialog.provider_combo.currentText().lower(), settings.provider.lower())

        # Test safe reset
        dialog.reset_to_defaults()
        self.assertEqual(dialog.provider_combo.currentText().lower(), "ollama")
        dialog.close()

    # -------------------------------------------------------------------------
    # 5. System Tray & Background Operation Tests
    # -------------------------------------------------------------------------
    def test_11_system_tray_creation_and_actions(self):
        """Verify system tray integration and notifications."""
        tray = BOLTSystemTray(on_show_callback=lambda: None, on_quit_callback=lambda: None)
        self.assertIsNotNone(tray)
        self.assertIsNotNone(tray.menu)

        # Test message dispatch does not raise exceptions
        tray.notify_task_started("Test Task")
        tray.notify_task_completed("Test Task", "Execution succeeded")
        tray.notify_security_alert("High Risk Action blocked")

    # -------------------------------------------------------------------------
    # 6. Windows Packaging Assets and Spec Validation
    # -------------------------------------------------------------------------
    def test_12_packaging_assets_and_spec_integrity(self):
        """Verify required icons, bolt.spec, and version_info.txt exist and are valid."""
        repo_root = Path(__file__).resolve().parent.parent

        spec_file = repo_root / "bolt.spec"
        self.assertTrue(spec_file.exists(), "bolt.spec must exist in project root")

        version_file = repo_root / "version_info.txt"
        self.assertTrue(version_file.exists(), "version_info.txt must exist in project root")

        ico_file = repo_root / "assets" / "bolt_icon.ico"
        self.assertTrue(ico_file.exists(), "assets/bolt_icon.ico must exist")

        png_file = repo_root / "assets" / "bolt_icon.png"
        self.assertTrue(png_file.exists(), "assets/bolt_icon.png must exist")

        shortcut_ps = repo_root / "scripts" / "create_shortcut.ps1"
        self.assertTrue(shortcut_ps.exists(), "scripts/create_shortcut.ps1 must exist")

        build_script = repo_root / "scripts" / "build_executable.py"
        self.assertTrue(build_script.exists(), "scripts/build_executable.py must exist")

        run_bat = repo_root / "run.bat"
        self.assertTrue(run_bat.exists(), "run.bat must exist")

        # Verify spec contents
        spec_text = spec_file.read_text(encoding="utf-8")
        self.assertIn("Analysis", spec_text)
        self.assertIn("EXE", spec_text)
        self.assertIn("COLLECT", spec_text)
        self.assertIn("assets/bolt_icon.ico", spec_text)
        self.assertIn("version_info.txt", spec_text)

        # Verify version_info contents
        version_text = version_file.read_text(encoding="utf-8")
        self.assertIn("BOLT Systems", version_text)
        self.assertIn("1.0.0.0", version_text)


if __name__ == "__main__":
    unittest.main()
