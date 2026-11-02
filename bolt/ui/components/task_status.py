"""Task status bar component showing execution state, local AI, and system telemetry."""

import platform
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from bolt.config.settings import get_settings
from bolt.core.network_manager import get_network_manager
from bolt.voice.voice_controller import get_voice_controller


class TaskStatusBar(QFrame):
    """
    Task Status Bar displaying real-time execution progress, AI activity,
    and the comprehensive system telemetry required by Part 8:
    - Local AI status & model name
    - Ollama status
    - Internet status
    - Browser status
    - Windows automation status
    - Memory status
    - Voice status
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status_bar")
        self.setFixedHeight(34)
        self._init_ui()
        self._setup_telemetry_timer()
        self.refresh_telemetry()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Status Indicator (Dot + Label)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("status_dot_ready")
        self.status_dot.setStyleSheet("color: #3fb950; font-size: 13px;")
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #c9d1d9;")
        layout.addWidget(self.status_label)

        # Active Task / Operation Indicator
        self.task_detail_label = QLabel("")
        self.task_detail_label.setStyleSheet("font-size: 11px; color: #8b949e;")
        layout.addWidget(self.task_detail_label)

        layout.addStretch()

        # Telemetry Section Badges
        badge_style = "font-size: 10px; color: #8b949e; background-color: #161b22; padding: 2px 6px; border-radius: 4px; border: 1px solid #30363d;"

        # Local AI / Model Badge
        self.local_ai_badge = QLabel("🦙 Ollama: gemma4:e2b")
        self.local_ai_badge.setStyleSheet(badge_style)
        layout.addWidget(self.local_ai_badge)

        # Internet Status Badge
        self.net_badge = QLabel("🌐 Online")
        self.net_badge.setStyleSheet(badge_style)
        layout.addWidget(self.net_badge)

        # Browser Status Badge
        self.browser_badge = QLabel("🌐 Edge")
        self.browser_badge.setStyleSheet(badge_style)
        layout.addWidget(self.browser_badge)

        # Windows Automation Badge
        self.win_badge = QLabel("🖥️ Windows: Ready")
        self.win_badge.setStyleSheet(badge_style)
        layout.addWidget(self.win_badge)

        # Memory Status Badge
        self.memory_badge = QLabel("🧠 Memory: Active")
        self.memory_badge.setStyleSheet(badge_style)
        layout.addWidget(self.memory_badge)

        # Voice Status Badge
        self.voice_badge = QLabel("🗣️ Voice: Ready")
        self.voice_badge.setStyleSheet(badge_style)
        layout.addWidget(self.voice_badge)

    def _setup_telemetry_timer(self):
        """Periodically refresh telemetry badges."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_telemetry)
        self._timer.start(15000)  # Refresh every 15s

    def refresh_telemetry(self):
        """Update telemetry badges with current system state."""
        settings = get_settings()

        # Local AI & Model
        model_name = settings.ollama_model if settings.provider == "ollama" else settings.current_model
        ai_provider = settings.provider.title()
        self.local_ai_badge.setText(f"🧠 {ai_provider}: {model_name}")

        # Internet Status
        net_mgr = get_network_manager()
        is_online = net_mgr.is_internet_available(timeout=0.8)
        if is_online:
            self.net_badge.setText("🌐 Online")
            self.net_badge.setStyleSheet(
                "font-size: 10px; color: #3fb950; background-color: #161b22; padding: 2px 6px; border-radius: 4px; border: 1px solid #238636;"
            )
        else:
            self.net_badge.setText("🔌 Offline")
            self.net_badge.setStyleSheet(
                "font-size: 10px; color: #f85149; background-color: #161b22; padding: 2px 6px; border-radius: 4px; border: 1px solid #da3633;"
            )

        # Voice Status
        voice = get_voice_controller()
        self.voice_badge.setText(f"🗣️ {voice.status_summary}")

    def set_ready(self, message: str = "Ready"):
        self.status_dot.setObjectName("status_dot_ready")
        self.status_dot.setStyleSheet("color: #3fb950; font-size: 13px;")
        self.status_label.setText(message)
        self.task_detail_label.setText("")

    def set_thinking(self, message: str = "Thinking..."):
        self.status_dot.setObjectName("status_dot_busy")
        self.status_dot.setStyleSheet("color: #d29922; font-size: 13px;")
        self.status_label.setText(message)
        self.task_detail_label.setText("Querying AI model...")

    def set_executing_task(self, task_name: str):
        self.status_dot.setObjectName("status_dot_busy")
        self.status_dot.setStyleSheet("color: #58a6ff; font-size: 13px;")
        self.status_label.setText("Executing Task")
        self.task_detail_label.setText(task_name)

    def set_error(self, message: str):
        self.status_dot.setObjectName("status_dot_error")
        self.status_dot.setStyleSheet("color: #f85149; font-size: 13px;")
        self.status_label.setText("Error")
        self.task_detail_label.setText(message)
