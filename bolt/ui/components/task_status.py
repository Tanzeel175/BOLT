"""Task status bar component showing execution state and system telemetry."""

import platform
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class TaskStatusBar(QFrame):
    """Task Status Bar displaying real-time execution progress, AI activity, and system state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status_bar")
        self.setFixedHeight(32)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Status Indicator (Dot + Label)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("status_dot_ready")
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #c9d1d9;")
        layout.addWidget(self.status_label)

        # Active Task / Operation Indicator
        self.task_detail_label = QLabel("")
        self.task_detail_label.setStyleSheet("font-size: 11px; color: #8b949e;")
        layout.addWidget(self.task_detail_label)

        layout.addStretch()

        # System Telemetry
        sys_info = f"Windows 11 | Python {platform.python_version()} | Phase 1 Foundation"
        self.sys_label = QLabel(sys_info)
        self.sys_label.setStyleSheet("font-size: 11px; color: #484f58;")
        layout.addWidget(self.sys_label)

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

