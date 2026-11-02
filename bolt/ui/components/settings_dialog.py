"""Settings Dialog for configuring AI providers, Ollama, API keys, models, and parameters."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.ollama_provider import OllamaProvider
from bolt.ai.openai_provider import OpenAIProvider
from bolt.config.constants import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    PROVIDER_GEMINI,
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)
from bolt.config.settings import Settings, get_settings
from bolt.core.logger import get_logger

logger = get_logger("SettingsDialog")


class ConnectionTestWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, provider: str, api_key: str, model: str, base_url: str):
        super().__init__()
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def run(self):
        try:
            if self.provider == PROVIDER_OLLAMA:
                p = OllamaProvider(base_url=self.base_url, model=self.model)
                ok, msg = p.test_connection()
                self.finished.emit(ok, msg)

            elif self.provider == PROVIDER_GEMINI:
                if not self.api_key.strip():
                    self.finished.emit(False, "Gemini API Key is empty.")
                    return
                p = GeminiProvider(api_key=self.api_key, model=self.model)
                ok, msg = p.test_connection()
                if ok:
                    self.finished.emit(True, "Successfully connected to Google Gemini API!")
                else:
                    self.finished.emit(False, f"Connection failed: {msg}")

            elif self.provider == PROVIDER_OPENAI:
                if not self.api_key.strip() and "localhost" not in self.base_url:
                    self.finished.emit(False, "OpenAI API Key is empty.")
                    return
                p = OpenAIProvider(api_key=self.api_key, model=self.model, base_url=self.base_url)
                ok, msg = p.test_connection()
                if ok:
                    self.finished.emit(True, "Successfully connected to OpenAI API!")
                else:
                    self.finished.emit(False, f"Connection failed: {msg}")

            else:
                self.finished.emit(True, "Mock/Local provider is always connected.")
        except Exception as e:
            self.finished.emit(False, f"Test error: {e}")


class SettingsDialog(QDialog):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BOLT – Settings & Configuration")
        self.setFixedSize(580, 720)
        self.setModal(True)
        self.settings = get_settings()
        self.test_worker = None
        self._init_ui()
        self._load_current_values()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        title_label = QLabel("⚙ Assistant Configuration")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #58a6ff;")
        main_layout.addWidget(title_label)

        # --- Section 1: AI Provider Selection ---
        provider_group = QGroupBox("Active AI Provider (Offline-First Architecture)")
        provider_group.setStyleSheet("QGroupBox { font-weight: 600; color: #c9d1d9; }")
        provider_layout = QFormLayout(provider_group)
        provider_layout.setSpacing(10)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("🦙 Ollama Local AI (Default Brain - Zero Internet)", PROVIDER_OLLAMA)
        self.provider_combo.addItem("Google Gemini (Online Cloud API)", PROVIDER_GEMINI)
        self.provider_combo.addItem("OpenAI ChatGPT (Online Cloud API)", PROVIDER_OPENAI)
        self.provider_combo.addItem("Mock / Test Mode (Offline Diagnostic)", PROVIDER_MOCK)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addRow("Default Brain:", self.provider_combo)
        main_layout.addWidget(provider_group)

        # --- Section 2: Ollama Local AI Settings ---
        self.ollama_group = QGroupBox("🦙 Ollama Local Model Settings")
        self.ollama_group.setStyleSheet("QGroupBox { font-weight: 600; color: #c9d1d9; }")
        ollama_layout = QFormLayout(self.ollama_group)

        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.addItems([
            "gemma4:e2b",
            "gemma4:e4b",
            "gemma2:2b",
            "qwen2.5:3b",
            "llama3.2:3b",
        ])
        ollama_layout.addRow("Local Model:", self.ollama_model_combo)

        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://127.0.0.1:11434")
        ollama_layout.addRow("Service URL:", self.ollama_url_edit)

        self.ollama_threads_spin = QSpinBox()
        self.ollama_threads_spin.setRange(1, 16)
        self.ollama_threads_spin.setValue(4)
        ollama_layout.addRow("CPU Threads:", self.ollama_threads_spin)
        main_layout.addWidget(self.ollama_group)

        # --- Section 3: Google Gemini Config ---
        self.gemini_group = QGroupBox("Google Gemini Settings (Optional Cloud)")
        self.gemini_group.setStyleSheet("QGroupBox { font-weight: 600; color: #c9d1d9; }")
        gemini_layout = QFormLayout(self.gemini_group)

        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_key_edit.setPlaceholderText("Enter Gemini API Key...")
        gemini_layout.addRow("API Key:", self.gemini_key_edit)

        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.setEditable(True)
        self.gemini_model_combo.addItems([
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
        ])
        gemini_layout.addRow("Model:", self.gemini_model_combo)
        main_layout.addWidget(self.gemini_group)

        # --- Section 4: OpenAI Config ---
        self.openai_group = QGroupBox("OpenAI Settings (Optional Cloud)")
        self.openai_group.setStyleSheet("QGroupBox { font-weight: 600; color: #c9d1d9; }")
        openai_layout = QFormLayout(self.openai_group)

        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_key_edit.setPlaceholderText("Enter OpenAI API Key (sk-...)")
        openai_layout.addRow("API Key:", self.openai_key_edit)

        self.openai_model_combo = QComboBox()
        self.openai_model_combo.setEditable(True)
        self.openai_model_combo.addItems([
            "gpt-4o-mini",
            "gpt-4o",
            "o3-mini",
        ])
        openai_layout.addRow("Model:", self.openai_model_combo)

        self.openai_base_url_edit = QLineEdit()
        self.openai_base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        openai_layout.addRow("Base URL:", self.openai_base_url_edit)
        main_layout.addWidget(self.openai_group)

        # --- Section 5: Model Parameters ---
        params_group = QGroupBox("Inference Parameters")
        params_group.setStyleSheet("QGroupBox { font-weight: 600; color: #c9d1d9; }")
        params_layout = QFormLayout(params_group)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setValue(0.7)
        params_layout.addRow("Temperature:", self.temp_spin)

        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(256, 16384)
        self.tokens_spin.setSingleStep(256)
        self.tokens_spin.setValue(2048)
        params_layout.addRow("Max Tokens:", self.tokens_spin)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setFixedHeight(65)
        params_layout.addRow("System Prompt:", self.system_prompt_edit)
        main_layout.addWidget(params_group)

        # --- Connection Test Status Label ---
        self.test_status_label = QLabel("")
        self.test_status_label.setWordWrap(True)
        self.test_status_label.setStyleSheet("font-size: 11px; padding: 2px;")
        main_layout.addWidget(self.test_status_label)

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.test_btn = QPushButton("🔌 Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.test_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾 Save Configuration")
        self.save_btn.setObjectName("primary_btn")
        self.save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(self.save_btn)

        main_layout.addLayout(btn_layout)

    def _load_current_values(self):
        """Populate widgets with current Settings values."""
        idx = self.provider_combo.findData(self.settings.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        self.ollama_model_combo.setCurrentText(self.settings.ollama_model)
        self.ollama_url_edit.setText(self.settings.ollama_base_url)
        self.ollama_threads_spin.setValue(self.settings.ollama_cpu_threads)

        self.gemini_key_edit.setText(self.settings.gemini_api_key)
        self.gemini_model_combo.setCurrentText(self.settings.gemini_model)

        self.openai_key_edit.setText(self.settings.openai_api_key)
        self.openai_model_combo.setCurrentText(self.settings.openai_model)
        self.openai_base_url_edit.setText(self.settings.openai_base_url)

        self.temp_spin.setValue(self.settings.temperature)
        self.tokens_spin.setValue(self.settings.max_tokens)
        self.system_prompt_edit.setPlainText(self.settings.system_prompt)

        self._on_provider_changed()

    def _on_provider_changed(self):
        provider = self.provider_combo.currentData()
        self.ollama_group.setEnabled(provider == PROVIDER_OLLAMA)
        self.gemini_group.setEnabled(provider == PROVIDER_GEMINI)
        self.openai_group.setEnabled(provider == PROVIDER_OPENAI)

    def _test_connection(self):
        provider = self.provider_combo.currentData()
        api_key = (
            self.gemini_key_edit.text() if provider == PROVIDER_GEMINI
            else self.openai_key_edit.text()
        )
        model = (
            self.ollama_model_combo.currentText() if provider == PROVIDER_OLLAMA
            else self.gemini_model_combo.currentText() if provider == PROVIDER_GEMINI
            else self.openai_model_combo.currentText()
        )
        base_url = (
            self.ollama_url_edit.text() if provider == PROVIDER_OLLAMA
            else self.openai_base_url_edit.text()
        )

        self.test_status_label.setText("Testing connection...")
        self.test_status_label.setStyleSheet("color: #d29922; font-size: 11px;")
        self.test_btn.setEnabled(False)

        self.test_worker = ConnectionTestWorker(provider, api_key, model, base_url)
        self.test_worker.finished.connect(self._on_test_finished)
        self.test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.test_btn.setEnabled(True)
        if success:
            self.test_status_label.setText(f"✓ {message}")
            self.test_status_label.setStyleSheet("color: #3fb950; font-size: 11px; font-weight: 600;")
        else:
            self.test_status_label.setText(f"✗ {message}")
            self.test_status_label.setStyleSheet("color: #f85149; font-size: 11px;")

    def _save_settings(self):
        """Save settings to .env and notify parent."""
        self.settings.provider = self.provider_combo.currentData()
        self.settings.ollama_model = self.ollama_model_combo.currentText().strip() or DEFAULT_OLLAMA_MODEL
        self.settings.ollama_base_url = self.ollama_url_edit.text().strip() or "http://127.0.0.1:11434"
        self.settings.ollama_cpu_threads = int(self.ollama_threads_spin.value())

        self.settings.gemini_api_key = self.gemini_key_edit.text().strip()
        self.settings.gemini_model = self.gemini_model_combo.currentText().strip() or DEFAULT_GEMINI_MODEL

        self.settings.openai_api_key = self.openai_key_edit.text().strip()
        self.settings.openai_model = self.openai_model_combo.currentText().strip() or DEFAULT_OPENAI_MODEL
        self.settings.openai_base_url = self.openai_base_url_edit.text().strip() or "https://api.openai.com/v1"

        self.settings.temperature = round(self.temp_spin.value(), 2)
        self.settings.max_tokens = int(self.tokens_spin.value())
        self.settings.system_prompt = self.system_prompt_edit.toPlainText().strip()

        try:
            self.settings.save()
            logger.info("Saved settings to .env successfully.")
            self.settings_saved.emit()
            self.accept()
        except Exception as e:
            logger.exception("Failed to save settings.")
            QMessageBox.critical(self, "Error Saving Settings", f"Could not save configuration: {e}")
