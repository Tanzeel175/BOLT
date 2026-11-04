"""
Settings and Configuration Management Dialog for BOLT (Phase 10).
Provides tabbed configuration for Local AI, Cloud APIs, Voice Hardware, Default Browser,
Security Permissions, and Persistent Data Backups.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bolt.config.constants import (
    APP_ICON_PNG,
    APP_NAME,
    APP_VERSION,
    AVAILABLE_PROVIDERS,
    DEFAULT_CUSTOM_BASE_URL,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_CUSTOM_NAME,
    DEFAULT_OLLAMA_MODEL,
    PROVIDER_CUSTOM,
    PROVIDER_GEMINI,
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)
from bolt.ai.custom_provider import POPULAR_PRESETS, CustomAIProvider
from bolt.config.settings import Settings, get_settings
from bolt.core.data_manager import get_data_manager
from bolt.ai.runtime_manager import get_runtime_manager
from bolt.security import get_permission_manager
from bolt.voice.speech_recognizer import get_speech_recognizer
from bolt.voice.tts_engine import get_tts_engine


class SettingsDialog(QDialog):
    """Configuration management dialog."""

    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Settings & Configuration")
        self.setMinimumSize(660, 540)
        self.resize(680, 580)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))

        self.settings = get_settings()
        self.data_mgr = get_data_manager()
        self.runtime_mgr = get_runtime_manager()
        self.perm_mgr = get_permission_manager()

        self._init_ui()
        self._load_current_values()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #161b22;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #21262d;
                color: #8b949e;
                padding: 8px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-bottom: none;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                color: #c9d1d9;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #58a6ff;
            }
            QLabel {
                font-size: 11px;
                color: #c9d1d9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: AI Brain
        self._build_ai_tab()
        # Tab 2: Voice & Audio
        self._build_voice_tab()
        # Tab 3: Security & Permissions
        self._build_security_tab()
        # Tab 4: User Data & Backups
        self._build_data_tab()

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_reset = QPushButton("Reset to Defaults")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #da3633;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2b1d1d; }
        """)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        btn_layout.addWidget(self.btn_reset)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 700;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _build_ai_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)

        # Provider
        self.combo_provider = QComboBox()
        self.combo_provider.addItems([
            PROVIDER_OLLAMA,
            PROVIDER_CUSTOM,
            PROVIDER_GEMINI,
            PROVIDER_OPENAI,
            PROVIDER_MOCK,
        ])
        self.provider_combo = self.combo_provider
        form.addRow("Default AI Provider:", self.combo_provider)

        # Section 1: Local Ollama AI (Recommended & Offline)
        sep1 = QLabel("<b>💻 Local AI Engine (Ollama — Offline & Recommended)</b>")
        sep1.setStyleSheet("color: #58a6ff; margin-top: 6px;")
        form.addRow(sep1)

        self.input_ollama_model = QLineEdit()
        self.input_ollama_model.setPlaceholderText(DEFAULT_OLLAMA_MODEL)
        form.addRow("Local Ollama Model:", self.input_ollama_model)

        ollama_url_box = QHBoxLayout()
        self.input_ollama_url = QLineEdit()
        self.input_ollama_url.setPlaceholderText("http://127.0.0.1:11434")
        self.btn_test_ollama = QPushButton("Test Ollama")
        self.btn_test_ollama.setStyleSheet("padding: 4px 10px; font-weight: 600;")
        self.btn_test_ollama.clicked.connect(self._on_test_ollama_clicked)
        ollama_url_box.addWidget(self.input_ollama_url, 1)
        ollama_url_box.addWidget(self.btn_test_ollama)
        form.addRow("Ollama Service URL:", ollama_url_box)

        self.label_ollama_status = QLabel("")
        self.label_ollama_status.setStyleSheet("font-size: 10px; color: #8b949e;")
        form.addRow("", self.label_ollama_status)

        # Section 2: Any Model / Custom API Key
        sep2 = QLabel("<b>🌐 Any Model / Custom API Key (Groq, DeepSeek, OpenRouter, Mistral, LM Studio, etc.)</b>")
        sep2.setStyleSheet("color: #bc8cff; margin-top: 8px;")
        form.addRow(sep2)

        self.combo_preset = QComboBox()
        self.combo_preset.addItem("Custom / Manual Configuration", "custom")
        for p_key, p_data in POPULAR_PRESETS.items():
            self.combo_preset.addItem(f"{p_data['name']} Preset", p_key)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_selected)
        form.addRow("Quick Presets:", self.combo_preset)

        self.input_custom_name = QLineEdit()
        self.input_custom_name.setPlaceholderText(DEFAULT_CUSTOM_NAME)
        form.addRow("Provider Name / Label:", self.input_custom_name)

        self.input_custom_url = QLineEdit()
        self.input_custom_url.setPlaceholderText(DEFAULT_CUSTOM_BASE_URL)
        form.addRow("API Base URL:", self.input_custom_url)

        custom_key_box = QHBoxLayout()
        self.input_custom_key = QLineEdit()
        self.input_custom_key.setEchoMode(QLineEdit.Password)
        self.input_custom_key.setPlaceholderText("Enter API key for any model...")
        self.btn_toggle_custom = QPushButton("👁️")
        self.btn_toggle_custom.setFixedWidth(32)
        self.btn_toggle_custom.clicked.connect(lambda: self._toggle_echo(self.input_custom_key))
        custom_key_box.addWidget(self.input_custom_key, 1)
        custom_key_box.addWidget(self.btn_toggle_custom)
        form.addRow("API Key:", custom_key_box)

        custom_model_box = QHBoxLayout()
        self.input_custom_model = QLineEdit()
        self.input_custom_model.setPlaceholderText(DEFAULT_CUSTOM_MODEL)
        self.btn_test_custom = QPushButton("Test Connection")
        self.btn_test_custom.setStyleSheet("padding: 4px 10px; font-weight: 600;")
        self.btn_test_custom.clicked.connect(self._on_test_custom_clicked)
        custom_model_box.addWidget(self.input_custom_model, 1)
        custom_model_box.addWidget(self.btn_test_custom)
        form.addRow("Model Name:", custom_model_box)

        self.label_custom_status = QLabel("")
        self.label_custom_status.setStyleSheet("font-size: 10px; color: #8b949e;")
        form.addRow("", self.label_custom_status)

        # Section 3: Gemini & OpenAI APIs (Optional)
        sep3 = QLabel("<b>☁️ Specific Cloud APIs (Optional)</b>")
        sep3.setStyleSheet("color: #7ee787; margin-top: 8px;")
        form.addRow(sep3)

        # Gemini API Key (Masked with reveal toggle)
        gemini_box = QHBoxLayout()
        self.input_gemini_key = QLineEdit()
        self.input_gemini_key.setEchoMode(QLineEdit.Password)
        self.btn_toggle_gemini = QPushButton("👁️")
        self.btn_toggle_gemini.setFixedWidth(32)
        self.btn_toggle_gemini.clicked.connect(lambda: self._toggle_echo(self.input_gemini_key))
        gemini_box.addWidget(self.input_gemini_key, 1)
        gemini_box.addWidget(self.btn_toggle_gemini)
        form.addRow("Gemini API Key:", gemini_box)

        # OpenAI API Key (Masked with reveal toggle)
        openai_box = QHBoxLayout()
        self.input_openai_key = QLineEdit()
        self.input_openai_key.setEchoMode(QLineEdit.Password)
        self.btn_toggle_openai = QPushButton("👁️")
        self.btn_toggle_openai.setFixedWidth(32)
        self.btn_toggle_openai.clicked.connect(lambda: self._toggle_echo(self.input_openai_key))
        openai_box.addWidget(self.input_openai_key, 1)
        openai_box.addWidget(self.btn_toggle_openai)
        form.addRow("OpenAI API Key:", openai_box)

        # Section 4: General AI Creativity
        sep4 = QLabel("<b>⚙️ Generation Parameters</b>")
        sep4.setStyleSheet("color: #e3b341; margin-top: 8px;")
        form.addRow(sep4)

        # Temperature
        self.slider_temp = QSlider(Qt.Horizontal)
        self.slider_temp.setRange(0, 100)
        self.label_temp_val = QLabel("0.7")
        self.slider_temp.valueChanged.connect(lambda v: self.label_temp_val.setText(f"{v/100:.2f}"))
        temp_box = QHBoxLayout()
        temp_box.addWidget(self.slider_temp, 1)
        temp_box.addWidget(self.label_temp_val)
        form.addRow("Temperature (Creativity):", temp_box)

        scroll.setWidget(tab)
        self.tabs.addTab(scroll, "🧠 AI Brain")

    def _build_voice_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)

        # Microphone device
        self.combo_mic = QComboBox()
        try:
            mics = get_speech_recognizer().list_microphones()
            if mics:
                for m in mics:
                    self.combo_mic.addItem(f"[{m['index']}] {m['name']}", m['index'])
            else:
                self.combo_mic.addItem("Default Windows Audio Input", -1)
        except Exception:
            self.combo_mic.addItem("Default Windows Audio Input", -1)
        form.addRow("Microphone Input:", self.combo_mic)

        # Voice interaction mode
        self.combo_voice_mode = QComboBox()
        self.combo_voice_mode.addItems(["Push-to-Talk (Default)", "Wake Word ('Hey Bolt')", "Disabled"])
        form.addRow("Voice Interaction Mode:", self.combo_voice_mode)

        # TTS voice
        self.combo_tts_voice = QComboBox()
        try:
            voices = get_tts_engine().get_available_voices()
            for v in voices:
                self.combo_tts_voice.addItem(v["name"], v["name"])
        except Exception:
            self.combo_tts_voice.addItem("Default Windows SAPI Voice", "")
        form.addRow("Text-to-Speech Voice:", self.combo_tts_voice)

        # Speech rate
        self.slider_rate = QSlider(Qt.Horizontal)
        self.slider_rate.setRange(100, 300)
        self.label_rate_val = QLabel("200 wpm")
        self.slider_rate.valueChanged.connect(lambda v: self.label_rate_val.setText(f"{v} wpm"))
        rate_box = QHBoxLayout()
        rate_box.addWidget(self.slider_rate, 1)
        rate_box.addWidget(self.label_rate_val)
        form.addRow("Speech Rate:", rate_box)

        self.tabs.addTab(tab, "🎙️ Voice & Audio")

    def _build_security_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)

        # Security mode
        self.combo_sec_mode = QComboBox()
        self.combo_sec_mode.addItems(["standard", "strict", "autonomous"])
        form.addRow("Security Mode:", self.combo_sec_mode)

        # Trusted directories
        self.input_trusted_dirs = QLineEdit()
        self.input_trusted_dirs.setPlaceholderText("C:\\Path\\To\\Workspace;C:\\Projects (semicolon separated)")
        form.addRow("Trusted Directories:", self.input_trusted_dirs)

        # Blocked tools
        self.input_blocked_tools = QLineEdit()
        self.input_blocked_tools.setPlaceholderText("make_purchase;delete_directory (semicolon separated)")
        form.addRow("Permanently Blocked Tools:", self.input_blocked_tools)

        # Revoke Session Grants Button
        btn_revoke = QPushButton("Revoke All Active Session Grants")
        btn_revoke.setStyleSheet("background-color: #21262d; color: #f0883e; border: 1px solid #30363d; padding: 4px 10px; border-radius: 4px;")
        btn_revoke.clicked.connect(self._on_revoke_grants_clicked)
        form.addRow("Session Permissions:", btn_revoke)

        self.tabs.addTab(tab, "🛡️ Security")

    def _build_data_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(12)

        stats = self.data_mgr.get_storage_stats()
        info_label = QLabel(
            f"<b>Persistent Storage Status:</b><br>"
            f"• User Data Root: <code>{stats['user_data_root']}</code><br>"
            f"• SQLite Database: <code>{stats['db_path']}</code> ({stats['db_size_mb']} MB)<br>"
            f"• Backups Count: <b>{stats['total_backups_count']}</b> ({stats['backups_size_mb']} MB)<br>"
            f"• Logs Directory: <code>{stats['logs_size_mb']} MB</code>"
        )
        info_label.setStyleSheet("color: #8b949e; line-height: 140%;")
        vbox.addWidget(info_label)

        btn_box = QHBoxLayout()
        btn_backup = QPushButton("📦 Create Manual Backup")
        btn_backup.setStyleSheet("background-color: #1f6feb; color: #fff; font-weight: 600; padding: 6px 12px; border-radius: 4px;")
        btn_backup.clicked.connect(self._on_create_backup_clicked)
        btn_box.addWidget(btn_backup)

        btn_clean = QPushButton("🧹 Prune Old Backups (Keep 10)")
        btn_clean.setStyleSheet("background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 6px 12px; border-radius: 4px;")
        btn_clean.clicked.connect(self._on_clean_backups_clicked)
        btn_box.addWidget(btn_clean)
        vbox.addLayout(btn_box)

        vbox.addStretch()
        self.tabs.addTab(tab, "💾 Persistent Data")

    def _toggle_echo(self, line_edit: QLineEdit):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
        else:
            line_edit.setEchoMode(QLineEdit.Password)

    def _on_preset_selected(self, index: int):
        preset_key = self.combo_preset.currentData()
        if preset_key in POPULAR_PRESETS:
            data = POPULAR_PRESETS[preset_key]
            self.input_custom_name.setText(data["name"])
            self.input_custom_url.setText(data["base_url"])
            self.input_custom_model.setText(data["default_model"])

    def _on_test_ollama_clicked(self):
        from bolt.ai.provider_manager import get_provider_manager
        pm = get_provider_manager()
        ok, msg, latency = pm.test_provider(PROVIDER_OLLAMA)
        if ok:
            self.label_ollama_status.setStyleSheet("font-size: 10px; color: #3fb950;")
            self.label_ollama_status.setText(f"✅ Local Ollama is connected & running ({latency} ms)")
        else:
            self.label_ollama_status.setStyleSheet("font-size: 10px; color: #f85149;")
            self.label_ollama_status.setText(f"⚠️ {msg}")

    def _on_test_custom_clicked(self):
        provider = CustomAIProvider(
            name=self.input_custom_name.text().strip() or "Custom Provider",
            api_key=self.input_custom_key.text().strip(),
            base_url=self.input_custom_url.text().strip(),
            model=self.input_custom_model.text().strip() or "default",
        )
        ok, msg = provider.test_connection()
        if ok:
            self.label_custom_status.setStyleSheet("font-size: 10px; color: #3fb950;")
            self.label_custom_status.setText(f"✅ {msg}")
        else:
            self.label_custom_status.setStyleSheet("font-size: 10px; color: #f85149;")
            self.label_custom_status.setText(f"⚠️ {msg}")

    def _load_current_values(self):
        # AI Tab
        idx = self.combo_provider.findText(self.settings.provider)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)
        self.input_ollama_model.setText(self.settings.ollama_model)
        self.input_ollama_url.setText(self.settings.ollama_base_url)
        self.input_custom_name.setText(self.settings.custom_provider_name)
        self.input_custom_url.setText(self.settings.custom_base_url)
        self.input_custom_key.setText(self.settings.custom_api_key)
        self.input_custom_model.setText(self.settings.custom_model)
        self.input_gemini_key.setText(self.settings.gemini_api_key)
        self.input_openai_key.setText(self.settings.openai_api_key)
        temp_val = int(self.settings.temperature * 100)
        self.slider_temp.setValue(temp_val)
        self.label_temp_val.setText(f"{self.settings.temperature:.2f}")

        # Voice Tab
        self.slider_rate.setValue(200)

        # Security Tab
        sec_mode_idx = self.combo_sec_mode.findText(self.perm_mgr.policy.mode)
        if sec_mode_idx >= 0:
            self.combo_sec_mode.setCurrentIndex(sec_mode_idx)
        self.input_trusted_dirs.setText(";".join(self.perm_mgr.policy.trusted_directories))
        self.input_blocked_tools.setText(";".join(self.perm_mgr.policy.blocked_tools))

    def _on_save_clicked(self):
        """Save settings and apply."""
        self.settings.provider = self.combo_provider.currentText()
        self.settings.ollama_model = self.input_ollama_model.text().strip() or DEFAULT_OLLAMA_MODEL
        self.settings.ollama_base_url = self.input_ollama_url.text().strip() or "http://127.0.0.1:11434"
        self.settings.custom_provider_name = self.input_custom_name.text().strip() or DEFAULT_CUSTOM_NAME
        self.settings.custom_base_url = self.input_custom_url.text().strip()
        self.settings.custom_api_key = self.input_custom_key.text().strip()
        self.settings.custom_model = self.input_custom_model.text().strip() or DEFAULT_CUSTOM_MODEL
        self.settings.gemini_api_key = self.input_gemini_key.text().strip()
        self.settings.openai_api_key = self.input_openai_key.text().strip()
        self.settings.temperature = self.slider_temp.value() / 100.0
        self.settings.save()

        # Update security policy
        trusted = [p.strip() for p in self.input_trusted_dirs.text().split(";") if p.strip()]
        blocked = [b.strip() for b in self.input_blocked_tools.text().split(";") if b.strip()]
        self.perm_mgr.update_security_policy({
            "mode": self.combo_sec_mode.currentText(),
            "trusted_directories": trusted,
            "blocked_tools": blocked,
        })

        self.settings_saved.emit()
        self.accept()

    def _on_create_backup_clicked(self):
        try:
            bp = self.data_mgr.create_backup(tag="user_manual")
            QMessageBox.information(self, "Backup Created", f"Successfully created database snapshot:\n\n{bp.name}")
        except Exception as e:
            QMessageBox.warning(self, "Backup Failed", f"Could not create backup: {e}")

    def _on_clean_backups_clicked(self):
        count = self.data_mgr.clean_old_backups(keep_count=10)
        QMessageBox.information(self, "Backups Cleaned", f"Removed {count} old backup file(s).")

    def _on_revoke_grants_clicked(self):
        self.perm_mgr.revoke_session_permissions()
        QMessageBox.information(self, "Permissions Revoked", "All temporary session grants have been revoked.")

    def reset_to_defaults(self) -> None:
        """Reset application configuration to safe offline defaults."""
        self.settings.provider = PROVIDER_OLLAMA
        self.settings.ollama_model = DEFAULT_OLLAMA_MODEL
        self.settings.temperature = 0.7
        self.settings.save()
        self._load_current_values()

    def _on_reset_clicked(self):
        reply = QMessageBox.question(
            self,
            "Reset Configuration",
            "Are you sure you want to reset settings to default values?\n\n"
            "NOTE: Your conversations, memory, workflows, and database records will NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.reset_to_defaults()
            QMessageBox.information(self, "Settings Reset", "Application settings have been reset to defaults.")
