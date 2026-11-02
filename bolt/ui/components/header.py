"""Header Bar component for BOLT desktop interface."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HeaderBar(QFrame):
    settings_requested = Signal()
    clear_chat_requested = Signal()

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

        # Model Badge Pill
        self.model_badge = QLabel("● Provider: Ollama")
        self.model_badge.setStyleSheet(
            "background-color: #21262d; color: #58a6ff; border: 1px solid #30363d; "
            "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )
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

    def update_model_badge(self, provider_name: str, model_name: str):
        """Update the model status pill with current provider and model."""
        p_upper = provider_name.upper()
        if provider_name == "ollama":
            display_text = f"● LOCAL AI: {model_name}"
            color = "#58a6ff"
        elif provider_name == "mock":
            display_text = f"● OFFLINE MOCK: {model_name}"
            color = "#e3b341"
        else:
            display_text = f"● {p_upper}: {model_name}"
            color = "#7ee787"

        self.model_badge.setText(display_text)
        self.model_badge.setStyleSheet(
            f"background-color: #21262d; color: {color}; border: 1px solid #30363d; "
            f"border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )
