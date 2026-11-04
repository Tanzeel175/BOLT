"""Header Bar component for BOLT desktop interface."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HeaderBar(QFrame):
    settings_requested = Signal()
    clear_chat_requested = Signal()
    provider_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header_bar")
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

        # Brand Container (Logo + Name + Tagline)
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)

        title_label = QLabel("⚡ BOLT")
        title_label.setStyleSheet(
            "font-size: 19px; font-weight: 800; color: #58a6ff; letter-spacing: 1px;"
        )

        subtitle_label = QLabel("Personal Autonomous AI Assistant • Windows 11")
        subtitle_label.setStyleSheet("font-size: 11px; color: #8b949e;")

        brand_layout.addWidget(title_label)
        brand_layout.addWidget(subtitle_label)
        layout.addLayout(brand_layout)

        layout.addStretch()

        # Model Badge Pill (Clickable Dropdown Button)
        self.model_badge = QPushButton("● LOCAL AI: gemma4:e2b ▾")
        self.model_badge.setToolTip("Click to quickly switch AI Engine or configure any model API key")
        self.model_badge.setCursor(Qt.PointingHandCursor)
        self.model_badge.setStyleSheet(
            "QPushButton { background-color: #21262d; color: #58a6ff; border: 1px solid #30363d; "
            "border-radius: 12px; padding: 4px 14px; font-size: 11px; font-weight: 600; text-align: center; } "
            "QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }"
        )
        self.model_badge.clicked.connect(self._show_model_menu)
        layout.addWidget(self.model_badge)

        # Action Buttons
        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.setToolTip("Clear messages in current conversation")
        self.clear_btn.clicked.connect(self.clear_chat_requested.emit)
        layout.addWidget(self.clear_btn)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setToolTip("Configure AI Provider, API Keys, and Models")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

    def _show_model_menu(self):
        """Open quick model switcher popup menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
                color: #c9d1d9;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #30363d;
                margin: 4px 8px;
            }
        """)

        act_local = menu.addAction("💻 Local AI Engine (Ollama - gemma4:e2b) [Offline]")
        act_local.triggered.connect(lambda: self.provider_selected.emit("ollama"))

        act_nebius = menu.addAction("🚀 Nebius Token Factory (Cloud Models)")
        act_nebius.triggered.connect(lambda: self.provider_selected.emit("nebius"))

        act_custom = menu.addAction("🌐 Any Model / Custom (Groq, DeepSeek, OpenRouter, Mistral, LM Studio)")
        act_custom.triggered.connect(lambda: self.provider_selected.emit("custom"))

        menu.addSeparator()

        act_gemini = menu.addAction("✨ Google Gemini (API)")
        act_gemini.triggered.connect(lambda: self.provider_selected.emit("gemini"))

        act_openai = menu.addAction("⚡ OpenAI ChatGPT (API)")
        act_openai.triggered.connect(lambda: self.provider_selected.emit("openai"))

        act_mock = menu.addAction("🧪 Offline Mock Engine")
        act_mock.triggered.connect(lambda: self.provider_selected.emit("mock"))

        menu.addSeparator()

        act_config = menu.addAction("⚙️ Configure API Keys & Models...")
        act_config.triggered.connect(lambda: self.settings_requested.emit())

        menu.exec(self.model_badge.mapToGlobal(self.model_badge.rect().bottomLeft()))

    def update_model_badge(self, provider_name: str, model_name: str):
        """Update the model status pill with current provider and model."""
        p_upper = provider_name.upper()
        if provider_name.lower() in ("ollama", "local_ai", "local"):
            display_text = f"● LOCAL AI: {model_name} ▾"
            color = "#58a6ff"
        elif provider_name.lower() in ("nebius", "tokenfactory", "token_factory"):
            display_text = f"● NEBIUS: {model_name} ▾"
            color = "#79c0ff"
        elif provider_name.lower() in ("custom", "any model"):
            display_text = f"● ANY MODEL: {model_name} ▾"
            color = "#bc8cff"
        elif provider_name.lower() == "mock":
            display_text = f"● OFFLINE MOCK: {model_name} ▾"
            color = "#e3b341"
        else:
            display_text = f"● {p_upper}: {model_name} ▾"
            color = "#7ee787"

        self.model_badge.setText(display_text)
        self.model_badge.setStyleSheet(
            f"QPushButton {{ background-color: #21262d; color: {color}; border: 1px solid #30363d; "
            f"border-radius: 12px; padding: 4px 14px; font-size: 11px; font-weight: 600; text-align: center; }} "
            f"QPushButton:hover {{ background-color: #30363d; border-color: {color}; }}"
        )
