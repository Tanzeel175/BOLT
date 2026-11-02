"""Sidebar component showing conversation history and management."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
)


class Sidebar(QFrame):
    new_chat_requested = Signal()
    conversation_selected = Signal(str)  # Passes conv_id
    conversation_deleted = Signal(str)   # Passes conv_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(260)
        self._conversations_map: Dict[str, Dict[str, Any]] = {}
        self._current_conv_id: Optional[str] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # New Chat Button
        self.new_chat_btn = QPushButton("+ New Chat")
        self.new_chat_btn.setObjectName("new_chat_btn")
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_chat_btn)

        # Section Header
        history_header = QLabel("CONVERSATIONS")
        history_header.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px; margin-top: 8px;"
        )
        layout.addWidget(history_header)

        # Conversations List
        self.conv_list = QListWidget()
        self.conv_list.setObjectName("conv_list")
        self.conv_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conv_list.customContextMenuRequested.connect(self._show_context_menu)
        self.conv_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.conv_list)

        # Footer Stats / Info
        self.footer_label = QLabel("Storage: Local SQLite")
        self.footer_label.setStyleSheet("font-size: 11px; color: #484f58;")
        self.footer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer_label)

    def set_conversations(self, conversations: List[Dict[str, Any]], active_id: Optional[str] = None):
        """Populate the list of conversations."""
        self.conv_list.clear()
        self._conversations_map.clear()
        self._current_conv_id = active_id

        selected_item = None
        for conv in conversations:
            conv_id = conv["id"]
            title = conv["title"] or "Untitled Chat"
            self._conversations_map[conv_id] = conv

            item = QListWidgetItem(f"💬  {title}")
            item.setData(Qt.UserRole, conv_id)
            item.setToolTip(f"{title}\nCreated: {conv.get('created_at', '')[:16]}")
            self.conv_list.addItem(item)

            if active_id and conv_id == active_id:
                selected_item = item

        if selected_item:
            self.conv_list.setCurrentItem(selected_item)

        self.footer_label.setText(f"{len(conversations)} chats stored in SQLite")

    def _on_item_clicked(self, item: QListWidgetItem):
        conv_id = item.data(Qt.UserRole)
        if conv_id and conv_id != self._current_conv_id:
            self._current_conv_id = conv_id
            self.conversation_selected.emit(conv_id)

    def _show_context_menu(self, position):
        item = self.conv_list.itemAt(position)
        if not item:
            return

        conv_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Chat")
        action = menu.exec(self.conv_list.mapToGlobal(position))

        if action == delete_action:
            self.conversation_deleted.emit(conv_id)

