"""Chat View component displaying rich conversation bubbles and markdown rendering."""

from datetime import datetime
from typing import Optional
import markdown

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def format_markdown(text: str) -> str:
    """Convert markdown text to styled HTML suitable for QTextBrowser."""
    html_body = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
    )

    styled_html = f"""
    <html>
    <head>
    <style>
        body {{
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
            color: #e6edf3;
            line-height: 1.5;
            margin: 0px;
            padding: 0px;
        }}
        p {{ margin: 4px 0px 8px 0px; }}
        h1, h2, h3, h4 {{
            color: #58a6ff;
            margin: 10px 0px 6px 0px;
            font-weight: 600;
        }}
        h1 {{ font-size: 17px; }}
        h2 {{ font-size: 15px; }}
        h3 {{ font-size: 14px; }}
        code {{
            font-family: 'Cascadia Code', 'Consolas', monospace;
            background-color: #21262d;
            color: #79c0ff;
            padding: 2px 5px;
            border-radius: 4px;
            font-size: 12px;
        }}
        pre {{
            background-color: #0b0f19;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 10px;
            margin: 8px 0px;
        }}
        pre code {{
            background-color: transparent;
            padding: 0px;
            color: #e6edf3;
        }}
        ul, ol {{
            margin: 4px 0px 8px 20px;
            padding: 0px;
        }}
        li {{ margin-bottom: 4px; }}
        blockquote {{
            border-left: 3px solid #58a6ff;
            margin: 6px 0px;
            padding-left: 10px;
            color: #8b949e;
        }}
        table {{
            border-collapse: collapse;
            margin: 8px 0px;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #30363d;
            padding: 6px 10px;
            text-align: left;
        }}
        th {{
            background-color: #161b22;
            color: #58a6ff;
        }}
        a {{
            color: #58a6ff;
            text-decoration: none;
        }}
    </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    return styled_html


class MessageCard(QFrame):
    """Visual card for an individual user or assistant message."""

    def __init__(self, role: str, content: str, timestamp: str = "", model: str = "", parent=None):
        super().__init__(parent)
        self.raw_content = content
        self.role = role
        self._init_ui(role, content, timestamp, model)

    def _init_ui(self, role: str, content: str, timestamp: str, model: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        is_user = role == "user"

        # Frame Styling
        if is_user:
            self.setStyleSheet(
                "MessageCard {"
                "   background-color: #1f2937;"
                "   border: 1px solid #374151;"
                "   border-radius: 8px;"
                "   margin-left: 60px;"
                "   margin-right: 4px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "MessageCard {"
                "   background-color: #161b22;"
                "   border: 1px solid #30363d;"
                "   border-left: 3px solid #58a6ff;"
                "   border-radius: 8px;"
                "   margin-left: 4px;"
                "   margin-right: 60px;"
                "}"
            )

        # Header Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Role Avatar / Badge
        role_label = QLabel("👤 YOU" if is_user else "⚡ BOLT")
        if is_user:
            role_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #a5d6ff;")
        else:
            role_label.setStyleSheet("font-size: 11px; font-weight: 800; color: #58a6ff;")
        header_layout.addWidget(role_label)

        if not is_user and model:
            model_tag = QLabel(f"[{model}]")
            model_tag.setStyleSheet("font-size: 10px; color: #8b949e;")
            header_layout.addWidget(model_tag)

        header_layout.addStretch()

        # Timestamp
        time_display = timestamp[11:16] if len(timestamp) >= 16 else datetime.now().strftime("%H:%M")
        time_label = QLabel(time_display)
        time_label.setStyleSheet("font-size: 10px; color: #8b949e;")
        header_layout.addWidget(time_label)

        # Copy Button
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setFixedSize(26, 22)
        self.copy_btn.setToolTip("Copy message to clipboard")
        self.copy_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 11px; padding: 0px; } "
            "QPushButton:hover { background-color: #30363d; border-radius: 3px; }"
        )
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(self.copy_btn)

        layout.addLayout(header_layout)

        # Content Browser
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet(
            "QTextBrowser { background-color: transparent; border: none; }"
        )
        self.content_browser.setHtml(format_markdown(content))
        self.content_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Auto-adjust height to document contents
        doc = self.content_browser.document()
        doc.adjustSize()
        height = max(40, int(doc.size().height()) + 15)
        self.content_browser.setMinimumHeight(height)

        layout.addWidget(self.content_browser)

    def append_chunk(self, chunk: str):
        """Append streamed token/chunk to the message and update markdown rendering."""
        self.raw_content += chunk
        self.content_browser.setHtml(format_markdown(self.raw_content))
        doc = self.content_browser.document()
        doc.adjustSize()
        height = max(40, int(doc.size().height()) + 15)
        self.content_browser.setMinimumHeight(height)

    def set_content(self, text: str):
        """Update entire message content."""
        self.raw_content = text
        self.content_browser.setHtml(format_markdown(text))
        doc = self.content_browser.document()
        doc.adjustSize()
        height = max(40, int(doc.size().height()) + 15)
        self.content_browser.setMinimumHeight(height)

    def _copy_to_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.raw_content, QClipboard.Clipboard)
            self.copy_btn.setText("✓")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋"))


class ChatView(QScrollArea):
    """Scrollable container for all chat messages with empty state suggestions."""

    suggestion_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_scroll_area")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Inner container
        self.container = QWidget()
        self.container.setObjectName("chat_container")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(20, 20, 20, 20)
        self.container_layout.setSpacing(14)
        self.container_layout.addStretch()

        self.setWidget(self.container)
        self.empty_state_widget: Optional[QWidget] = None
        self._show_empty_state()

    def _show_empty_state(self):
        """Display an attractive welcome card when no messages exist."""
        if self.empty_state_widget:
            return

        self.empty_state_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(12)

        icon_label = QLabel("⚡")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px; color: #58a6ff;")
        empty_layout.addWidget(icon_label)

        welcome_title = QLabel("BOLT – Personal Autonomous AI Assistant")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f0f6fc;")
        empty_layout.addWidget(welcome_title)

        welcome_sub = QLabel(
            "Ready to operate your Windows 11 PC, answer questions, and execute autonomous workflows."
        )
        welcome_sub.setAlignment(Qt.AlignCenter)
        welcome_sub.setStyleSheet("font-size: 13px; color: #8b949e; max-width: 600px;")
        empty_layout.addWidget(welcome_sub)

        # Quick action suggestions
        suggestions_box = QWidget()
        sug_layout = QHBoxLayout(suggestions_box)
        sug_layout.setSpacing(10)

        prompts = [
            "Open ChatGPT",
            "Open Notepad",
            "Search for Python AI libraries",
            "System specifications",
        ]

        for p in prompts:
            btn = QPushButton(f"💡 {p}")
            btn.setStyleSheet(
                "QPushButton {"
                "   background-color: #161b22;"
                "   border: 1px solid #30363d;"
                "   border-radius: 16px;"
                "   padding: 6px 14px;"
                "   font-size: 12px;"
                "   color: #c9d1d9;"
                "}"
                "QPushButton:hover {"
                "   background-color: #21262d;"
                "   border-color: #58a6ff;"
                "   color: #58a6ff;"
                "}"
            )
            btn.clicked.connect(lambda checked, text=p: self.suggestion_clicked.emit(text))
            sug_layout.addWidget(btn)

        empty_layout.addWidget(suggestions_box)

        # Insert before stretch
        self.container_layout.insertWidget(0, self.empty_state_widget)

    def _hide_empty_state(self):
        if self.empty_state_widget:
            self.container_layout.removeWidget(self.empty_state_widget)
            self.empty_state_widget.deleteLater()
            self.empty_state_widget = None

    def add_message(self, role: str, content: str, timestamp: str = "", model: str = "") -> MessageCard:
        """Add a new message bubble to the chat."""
        self._hide_empty_state()

        card = MessageCard(role=role, content=content, timestamp=timestamp, model=model)
        # Insert right before the trailing stretch
        count = self.container_layout.count()
        self.container_layout.insertWidget(count - 1, card)

        # Auto-scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)
        return card

    def create_streaming_card(self, role: str = "assistant", initial_text: str = "", model: str = "") -> MessageCard:
        """Create a message card ready for real-time streamed token chunks."""
        return self.add_message(role=role, content=initial_text, model=model)

    def clear_chat(self):
        """Remove all messages and display empty state."""
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._show_empty_state()

    def _scroll_to_bottom(self):
        vbar = self.verticalScrollBar()
        if vbar:
            vbar.setValue(vbar.maximum())
