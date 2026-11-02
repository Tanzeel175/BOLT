"""Input Bar component with multi-line text input, send button, and voice placeholder."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class ChatInputEdit(QTextEdit):
    """TextEdit that emits returnPressed on Enter, and inserts a newline on Shift+Enter."""

    returnPressed = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.returnPressed.emit()
        else:
            super().keyPressEvent(event)


class InputBar(QFrame):
    message_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("input_container")
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(10)

        # Voice Input Placeholder Button (Phase 7 requirement)
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(42, 42)
        self.mic_btn.setToolTip("Voice Assistant (Coming in Phase 7)")
        self.mic_btn.setStyleSheet(
            "QPushButton {"
            "   background-color: #21262d;"
            "   border: 1px solid #30363d;"
            "   border-radius: 21px;"
            "   font-size: 16px;"
            "}"
            "QPushButton:hover {"
            "   background-color: #30363d;"
            "   border-color: #58a6ff;"
            "}"
        )
        self.mic_btn.clicked.connect(self._on_mic_clicked)
        layout.addWidget(self.mic_btn)

        # Multi-line Text Input
        self.input_edit = ChatInputEdit()
        self.input_edit.setObjectName("chat_input")
        self.input_edit.setPlaceholderText(
            "Type a question or command for BOLT... (Press Enter to send, Shift+Enter for new line)"
        )
        self.input_edit.setFixedHeight(48)
        self.input_edit.returnPressed.connect(self._submit)
        layout.addWidget(self.input_edit)

        # Send Button
        self.send_btn = QPushButton("➤ Send")
        self.send_btn.setObjectName("primary_btn")
        self.send_btn.setFixedSize(85, 42)
        self.send_btn.setToolTip("Send instruction to BOLT (Enter)")
        self.send_btn.clicked.connect(self._submit)
        layout.addWidget(self.send_btn)

    def _submit(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.message_submitted.emit(text)
        self.input_edit.clear()

    def set_text(self, text: str):
        """Set text in the input box and focus it."""
        self.input_edit.setPlainText(text)
        self.input_edit.setFocus()

    def set_busy(self, busy: bool):
        """Disable input and send button while BOLT is generating."""
        self.send_btn.setEnabled(not busy)
        self.input_edit.setEnabled(not busy)
        if busy:
            self.send_btn.setText("⏳")
        else:
            self.send_btn.setText("➤ Send")
            self.input_edit.setFocus()

    def _on_mic_clicked(self):
        QMessageBox.information(
            self,
            "BOLT Voice Assistant",
            "Voice input and Wake-Word activation will be activated in Phase 7.\n\n"
            "Currently running in Phase 1 (Foundation & Desktop Interface). "
            "Please use keyboard input.",
        )

