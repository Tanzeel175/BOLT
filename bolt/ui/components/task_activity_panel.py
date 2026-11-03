"""Task Activity Panel for BOLT Desktop Interface (Phase 5)."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bolt.tasks.models import ExecutionPlan, TaskProgressUpdate, TaskStatus, TaskStep


class StepItemWidget(QFrame):
    """Widget displaying a single step within the Task Activity Panel."""

    def __init__(self, step: TaskStep, parent=None):
        super().__init__(parent)
        self.step_id = step.step_id
        self._init_ui(step)

    def _init_ui(self, step: TaskStep):
        self.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        # Status icon
        icons = {
            TaskStatus.COMPLETED: ("✅", "#3fb950"),
            TaskStatus.IN_PROGRESS: ("🔄", "#58a6ff"),
            TaskStatus.WAITING_APPROVAL: ("⏳", "#d29922"),
            TaskStatus.FAILED: ("⚠️", "#f85149"),
            TaskStatus.CANCELLED: ("⏹️", "#8b949e"),
            TaskStatus.SKIPPED: ("⏭️", "#8b949e"),
            TaskStatus.PENDING: ("⚪", "#484f58"),
        }
        icon_str, color = icons.get(step.status, ("⚪", "#484f58"))
        self.icon_label = QLabel(icon_str)
        self.icon_label.setStyleSheet(f"font-size: 13px; color: {color};")
        top_layout.addWidget(self.icon_label)

        # Step description
        self.desc_label = QLabel(step.description)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #e6edf3; font-size: 12px; font-weight: 500;")
        top_layout.addWidget(self.desc_label, 1)

        # App badge
        if step.active_application:
            app_badge = QLabel(step.active_application)
            app_badge.setStyleSheet("""
                background-color: #21262d;
                color: #8b949e;
                font-size: 10px;
                border-radius: 4px;
                padding: 2px 6px;
            """)
            top_layout.addWidget(app_badge)

        layout.addLayout(top_layout)

        # Result preview or error
        if step.error:
            err_label = QLabel(f"⚠️ Error: {step.error}")
            err_label.setStyleSheet("color: #f85149; font-size: 11px;")
            err_label.setWordWrap(True)
            layout.addWidget(err_label)
        elif step.result and isinstance(step.result, dict) and "message" in step.result:
            res_label = QLabel(f"✓ {step.result['message']}")
            res_label.setStyleSheet("color: #7ee787; font-size: 11px;")
            res_label.setWordWrap(True)
            layout.addWidget(res_label)


class TaskActivityPanel(QFrame):
    """Panel displaying active workflow progress, steps breakdown, and controls."""

    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()
    approval_decided = Signal(str, bool)  # step_id, approved
    security_approval_decided = Signal(str, bool, bool, str)  # step_id, approved, session_grant, typed_phrase

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("task_activity_panel")
        self.setFixedWidth(340)
        self.current_plan: Optional[ExecutionPlan] = None
        self.waiting_step_id: Optional[str] = None
        self.is_critical: bool = False
        self.confirmation_phrase: str = "CONFIRM"
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#task_activity_panel {
                background-color: #0d1117;
                border-left: 1px solid #30363d;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Header with title & status badge
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("⚡ Task Activity")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #58a6ff;")
        header_layout.addWidget(self.title_label)

        self.status_badge = QLabel("READY")
        self.status_badge.setStyleSheet("""
            background-color: #21262d;
            color: #8b949e;
            font-size: 10px;
            font-weight: 700;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        header_layout.addWidget(self.status_badge, alignment=Qt.AlignRight)
        layout.addLayout(header_layout)

        # Task Name
        self.task_name_label = QLabel("No active workflow")
        self.task_name_label.setWordWrap(True)
        self.task_name_label.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.task_name_label)

        # 2. Progress Bar
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #21262d;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)

        self.progress_text = QLabel("0% (0/0 steps)")
        self.progress_text.setStyleSheet("color: #8b949e; font-size: 11px;")
        progress_layout.addWidget(self.progress_text)
        layout.addLayout(progress_layout)

        # 3. Steps Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(6)
        self.steps_layout.addStretch()
        self.scroll_area.setWidget(self.steps_container)
        layout.addWidget(self.scroll_area, 1)

        # 4. Human-in-the-Loop & Security Approval Card (hidden by default)
        self.approval_card = QFrame()
        self.approval_card.setStyleSheet("""
            QFrame {
                background-color: #1e1e0a;
                border: 1px solid #d29922;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        appr_layout = QVBoxLayout(self.approval_card)
        appr_layout.setContentsMargins(8, 8, 8, 8)
        appr_layout.setSpacing(6)

        self.appr_badge_label = QLabel("🛡️ SECURITY APPROVAL REQUIRED")
        self.appr_badge_label.setStyleSheet("color: #ffd60a; font-size: 11px; font-weight: 700;")
        appr_layout.addWidget(self.appr_badge_label)

        self.appr_prompt_label = QLabel("Approval required to continue")
        self.appr_prompt_label.setWordWrap(True)
        self.appr_prompt_label.setStyleSheet("color: #c9d1d9; font-size: 11px; font-weight: 500;")
        appr_layout.addWidget(self.appr_prompt_label)

        # Proposed changes / diff preview
        self.appr_preview_text = QTextEdit()
        self.appr_preview_text.setReadOnly(True)
        self.appr_preview_text.setMaximumHeight(85)
        self.appr_preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #58a6ff;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid #30363d;
                border-radius: 4px;
            }
        """)
        self.appr_preview_text.setVisible(False)
        appr_layout.addWidget(self.appr_preview_text)

        # Critical confirmation container
        self.critical_container = QWidget()
        crit_layout = QVBoxLayout(self.critical_container)
        crit_layout.setContentsMargins(0, 2, 0, 2)
        crit_layout.setSpacing(4)

        self.critical_label = QLabel("⚠️ Critical Action: Type CONFIRM to enable:")
        self.critical_label.setStyleSheet("color: #f85149; font-size: 10px; font-weight: 600;")
        crit_layout.addWidget(self.critical_label)

        self.input_confirmation = QLineEdit()
        self.input_confirmation.setPlaceholderText("Type CONFIRM here...")
        self.input_confirmation.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #f85149;
                font-weight: 700;
                border: 1px solid #da3633;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
            }
        """)
        self.input_confirmation.textChanged.connect(self._on_confirmation_text_changed)
        crit_layout.addWidget(self.input_confirmation)
        self.critical_container.setVisible(False)
        appr_layout.addWidget(self.critical_container)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_approve = QPushButton("✅ Approve")
        self.btn_approve.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 600;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2ea043; }
            QPushButton:disabled { background-color: #21262d; color: #484f58; }
        """)
        self.btn_approve.clicked.connect(self._on_approve_clicked)
        btn_layout.addWidget(self.btn_approve)

        self.btn_session = QPushButton("🛡️ Session")
        self.btn_session.setToolTip("Allow this action for the rest of this session")
        self.btn_session.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                color: #ffffff;
                font-weight: 600;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #388bfd; }
        """)
        self.btn_session.clicked.connect(self._on_session_clicked)
        btn_layout.addWidget(self.btn_session)

        self.btn_reject = QPushButton("❌ Reject")
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #da3633;
                color: #ffffff;
                font-weight: 600;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #f85149; }
        """)
        self.btn_reject.clicked.connect(self._on_reject_clicked)
        btn_layout.addWidget(self.btn_reject)

        appr_layout.addLayout(btn_layout)
        self.approval_card.setVisible(False)
        layout.addWidget(self.approval_card)

        # 5. Bottom Controls (Pause, Resume, Cancel)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        self.btn_pause.clicked.connect(self.pause_requested.emit)
        ctrl_layout.addWidget(self.btn_pause)

        self.btn_resume = QPushButton("▶ Resume")
        self.btn_resume.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        self.btn_resume.clicked.connect(self.resume_requested.emit)
        ctrl_layout.addWidget(self.btn_resume)

        self.btn_cancel = QPushButton("⏹ Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #f85149;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        ctrl_layout.addWidget(self.btn_cancel)

        layout.addLayout(ctrl_layout)

    def set_plan(self, plan: ExecutionPlan):
        """Bind an ExecutionPlan to the panel and render all steps."""
        self.current_plan = plan
        self.task_name_label.setText(plan.title)
        self.update_progress(
            TaskProgressUpdate(
                plan_id=plan.plan_id,
                title=plan.title,
                status=plan.status,
                current_step_id="",
                current_step_desc=plan.title,
                completed_steps=sum(1 for s in plan.steps if s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)),
                total_steps=len(plan.steps),
                progress_percent=plan.progress_percentage(),
                active_application="",
            )
        )
        self._render_steps(plan.steps)

    def update_progress(self, update: TaskProgressUpdate):
        """Update progress bar and status badge from live telemetry."""
        status_val = update.status.value.upper() if hasattr(update.status, "value") else str(update.status).upper()
        self.status_badge.setText(status_val)

        # Color-code status badge
        if status_val == "COMPLETED":
            self.status_badge.setStyleSheet("background-color: #238636; color: #fff; border-radius: 4px; padding: 3px 8px; font-weight: 700;")
        elif status_val in ("RUNNING", "IN_PROGRESS"):
            self.status_badge.setStyleSheet("background-color: #1f6feb; color: #fff; border-radius: 4px; padding: 3px 8px; font-weight: 700;")
        elif status_val == "WAITING_APPROVAL":
            self.status_badge.setStyleSheet("background-color: #d29922; color: #fff; border-radius: 4px; padding: 3px 8px; font-weight: 700;")
        elif status_val == "FAILED":
            self.status_badge.setStyleSheet("background-color: #da3633; color: #fff; border-radius: 4px; padding: 3px 8px; font-weight: 700;")

        self.progress_bar.setValue(int(update.progress_percent))
        self.progress_text.setText(f"{update.progress_percent}% ({update.completed_steps}/{update.total_steps} steps)")

        if self.current_plan:
            self._render_steps(self.current_plan.steps)

    def show_approval_prompt(
        self,
        step_id: str,
        prompt: str,
        is_critical: bool = False,
        confirmation_phrase: str = "CONFIRM",
        preview_diff: Optional[str] = None,
    ):
        """Display the security approval card for human confirmation."""
        self.waiting_step_id = step_id
        self.is_critical = is_critical
        self.confirmation_phrase = confirmation_phrase
        self.appr_prompt_label.setText(prompt)

        if is_critical:
            self.appr_badge_label.setText("🔴 CRITICAL RISK ACTION REQUIRED")
            self.appr_badge_label.setStyleSheet("color: #f85149; font-size: 11px; font-weight: 700;")
            self.critical_container.setVisible(True)
            self.input_confirmation.clear()
            self.btn_approve.setEnabled(False)
            self.btn_session.setVisible(False)
        else:
            self.appr_badge_label.setText("🛡️ SECURITY APPROVAL REQUIRED")
            self.appr_badge_label.setStyleSheet("color: #ffd60a; font-size: 11px; font-weight: 700;")
            self.critical_container.setVisible(False)
            self.btn_approve.setEnabled(True)
            self.btn_session.setVisible(True)

        if preview_diff:
            self.appr_preview_text.setPlainText(preview_diff)
            self.appr_preview_text.setVisible(True)
        else:
            self.appr_preview_text.setVisible(False)

        self.approval_card.setVisible(True)

    def hide_approval_prompt(self):
        """Hide the approval card."""
        self.waiting_step_id = None
        self.is_critical = False
        self.approval_card.setVisible(False)

    def _on_confirmation_text_changed(self, text: str):
        if self.is_critical:
            matches = text.strip().upper() == (self.confirmation_phrase or "CONFIRM").upper()
            self.btn_approve.setEnabled(matches)

    def _on_approve_clicked(self):
        if self.waiting_step_id:
            step_id = self.waiting_step_id
            typed = self.input_confirmation.text().strip() if self.is_critical else ""
            self.hide_approval_prompt()
            self.approval_decided.emit(step_id, True)
            self.security_approval_decided.emit(step_id, True, False, typed)

    def _on_session_clicked(self):
        if self.waiting_step_id:
            step_id = self.waiting_step_id
            self.hide_approval_prompt()
            self.approval_decided.emit(step_id, True)
            self.security_approval_decided.emit(step_id, True, True, "")

    def _on_reject_clicked(self):
        if self.waiting_step_id:
            step_id = self.waiting_step_id
            self.hide_approval_prompt()
            self.approval_decided.emit(step_id, False)
            self.security_approval_decided.emit(step_id, False, False, "")

    def _render_steps(self, steps: List[TaskStep]):
        """Clear and redraw steps checklist."""
        while self.steps_layout.count() > 1:
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for s in steps:
            w = StepItemWidget(s, self.steps_container)
            self.steps_layout.insertWidget(self.steps_layout.count() - 1, w)

