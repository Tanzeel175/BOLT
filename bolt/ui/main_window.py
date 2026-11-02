"""Main Application Window for BOLT."""

from typing import List, Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from bolt.ai.base import ChatMessage, AIResponse
from bolt.ai.router import AIRouter, get_ai_router
from bolt.config.constants import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
)
from bolt.config.settings import Settings, get_settings
from bolt.core.database import Database, get_database
from bolt.core.logger import get_logger
from bolt.ui.components.header import HeaderBar
from bolt.ui.components.sidebar import Sidebar
from bolt.ui.components.chat_view import ChatView
from bolt.ui.components.input_bar import InputBar
from bolt.ui.components.task_status import TaskStatusBar
from bolt.ui.components.settings_dialog import SettingsDialog

logger = get_logger("MainWindow")


class AIWorker(QThread):
    """Background worker thread for non-blocking AI queries."""
    finished = Signal(object)  # Emits AIResponse

    def __init__(self, router: AIRouter, messages: List[ChatMessage], system_prompt: Optional[str] = None):
        super().__init__()
        self.router = router
        self.messages = messages
        self.system_prompt = system_prompt

    def run(self):
        try:
            response = self.router.generate(self.messages, self.system_prompt)
            self.finished.emit(response)
        except Exception as e:
            logger.exception("AIWorker encountered an unexpected error.")
            err_resp = AIResponse(
                content="",
                model="error",
                success=False,
                error=f"Worker exception: {e}",
            )
            self.finished.emit(err_resp)


class MainWindow(QMainWindow):
    """BOLT Main Desktop Interface Window."""

    def __init__(self):
        super().__init__()
        self.settings: Settings = get_settings()
        self.db: Database = get_database()
        self.ai_router: AIRouter = get_ai_router()

        self.current_conv_id: Optional[str] = None
        self.active_worker: Optional[AIWorker] = None

        self._init_window()
        self._init_layout()
        self._connect_signals()
        self._load_conversations_and_initial_chat()

    def _init_window(self):
        self.setWindowTitle(f"{APP_NAME} – {APP_SUBTITLE} (v{APP_VERSION})")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

    def _init_layout(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header Bar
        self.header_bar = HeaderBar(self)
        root_layout.addWidget(self.header_bar)

        # 2. Middle Body: Split Sidebar & Chat Workspace
        body_widget = QWidget(self)
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar (Conversations)
        self.sidebar = Sidebar(self)
        body_layout.addWidget(self.sidebar)

        # Chat Workspace (Chat view + Input Bar)
        chat_workspace = QWidget(self)
        chat_layout = QVBoxLayout(chat_workspace)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self.chat_view = ChatView(self)
        chat_layout.addWidget(self.chat_view, stretch=1)

        self.input_bar = InputBar(self)
        chat_layout.addWidget(self.input_bar)

        body_layout.addWidget(chat_workspace, stretch=1)
        root_layout.addWidget(body_widget, stretch=1)

        # 3. Bottom Task Status Bar
        self.status_bar = TaskStatusBar(self)
        root_layout.addWidget(self.status_bar)

        # Sync Header Model Badge
        self._sync_header_badge()

    def _sync_header_badge(self):
        """Update header pill based on active provider and model."""
        provider = self.settings.provider
        model = self.settings.current_model
        if provider == "gemini" and not self.settings.gemini_api_key.strip():
            self.header_bar.update_model_badge("Gemini (No Key)", "Local Demo Mode")
        elif provider == "openai" and not self.settings.openai_api_key.strip():
            self.header_bar.update_model_badge("OpenAI (No Key)", "Local Demo Mode")
        else:
            self.header_bar.update_model_badge(provider, model)

    def _connect_signals(self):
        # Header actions
        self.header_bar.settings_requested.connect(self._open_settings)
        self.header_bar.clear_chat_requested.connect(self._clear_current_chat)

        # Sidebar actions
        self.sidebar.new_chat_requested.connect(self._start_new_chat)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.sidebar.conversation_deleted.connect(self._delete_conversation)

        # Chat View suggestions
        self.chat_view.suggestion_clicked.connect(self.input_bar.set_text)

        # Input submission
        self.input_bar.message_submitted.connect(self._handle_user_message)

    def _load_conversations_and_initial_chat(self):
        """Load conversation list from SQLite and open the latest or create a new one."""
        conversations = self.db.get_conversations()
        if conversations:
            latest_id = conversations[0]["id"]
            self.sidebar.set_conversations(conversations, active_id=latest_id)
            self._load_conversation(latest_id)
        else:
            self.sidebar.set_conversations([])
            self._start_new_chat()

    def _start_new_chat(self):
        """Create a fresh conversation session."""
        conv_id = self.db.create_conversation(
            title="New Chat",
            provider=self.settings.provider,
            model=self.settings.current_model,
        )
        self.current_conv_id = conv_id
        conversations = self.db.get_conversations()
        self.sidebar.set_conversations(conversations, active_id=conv_id)
        self.chat_view.clear_chat()
        self.status_bar.set_ready("New conversation ready")
        logger.info(f"Started new conversation: {conv_id}")

    def _load_conversation(self, conv_id: str):
        """Load all messages for the specified conversation from SQLite."""
        self.current_conv_id = conv_id
        self.chat_view.clear_chat()

        messages = self.db.get_messages(conv_id)
        for msg in messages:
            self.chat_view.add_message(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["created_at"],
                model=msg.get("model", ""),
            )

        conv = self.db.get_conversation(conv_id)
        title = conv["title"] if conv else "Chat"
        self.status_bar.set_ready(f"Loaded: {title}")
        logger.info(f"Loaded conversation: {conv_id} ({len(messages)} messages)")

    def _clear_current_chat(self):
        """Clear all messages from the current conversation."""
        if not self.current_conv_id:
            return
        confirm = QMessageBox.question(
            self,
            "Clear Conversation",
            "Are you sure you want to clear all messages in this conversation?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.db.clear_conversation_messages(self.current_conv_id)
            self.chat_view.clear_chat()
            self.status_bar.set_ready("Conversation cleared")

    def _delete_conversation(self, conv_id: str):
        """Delete conversation and load next available."""
        self.db.delete_conversation(conv_id)
        conversations = self.db.get_conversations()

        if self.current_conv_id == conv_id:
            if conversations:
                new_active = conversations[0]["id"]
                self.sidebar.set_conversations(conversations, active_id=new_active)
                self._load_conversation(new_active)
            else:
                self._start_new_chat()
        else:
            self.sidebar.set_conversations(conversations, active_id=self.current_conv_id)

    def _handle_user_message(self, text: str):
        """Process user input, record in DB, update UI, and dispatch to AI worker."""
        if not self.current_conv_id:
            self._start_new_chat()

        # 1. Store user message in SQLite
        self.db.add_message(
            conversation_id=self.current_conv_id,
            role="user",
            content=text,
        )

        # 2. Render user message card in ChatView
        self.chat_view.add_message(role="user", content=text)

        # 3. Update Conversation Title if it's the first message
        messages = self.db.get_messages(self.current_conv_id)
        if len(messages) <= 2:
            title = text[:35].replace("\n", " ").strip()
            if len(text) > 35:
                title += "..."
            self.db.update_conversation_title(self.current_conv_id, title)
            conversations = self.db.get_conversations()
            self.sidebar.set_conversations(conversations, active_id=self.current_conv_id)

        # 4. Set UI to busy / thinking state
        self.input_bar.set_busy(True)
        self.status_bar.set_thinking(f"Thinking with {self.settings.provider.upper()}...")

        # 5. Build ChatMessage history for AI model
        chat_history = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in messages
        ]

        # 6. Launch background worker thread
        self.active_worker = AIWorker(
            router=self.ai_router,
            messages=chat_history,
            system_prompt=self.settings.system_prompt,
        )
        self.active_worker.finished.connect(self._on_ai_response_received)
        self.active_worker.start()

    def _on_ai_response_received(self, response: AIResponse):
        """Handle AI completion returned by background worker."""
        self.input_bar.set_busy(False)

        if response.success:
            content = response.content
            model_used = response.model

            # Save assistant message to SQLite
            if self.current_conv_id:
                self.db.add_message(
                    conversation_id=self.current_conv_id,
                    role="assistant",
                    content=content,
                    model=model_used,
                    tokens=response.tokens_used,
                )

            # Display assistant message card
            self.chat_view.add_message(
                role="assistant",
                content=content,
                model=model_used,
            )
            self.status_bar.set_ready(f"Completed • Model: {model_used}")
            logger.info("AI response received and rendered successfully.")
        else:
            err_msg = response.error or "Unknown error generating response."
            self.status_bar.set_error(err_msg)

            # Render an error alert message card in chat
            error_card_content = (
                f"### ⚠️ Could not generate response\n\n"
                f"**Error Details:** `{err_msg}`\n\n"
                f"**How to resolve:**\n"
                f"- If using Gemini or OpenAI, verify your API Key in **Settings (⚙)**.\n"
                f"- Check your internet connectivity.\n"
                f"- You can switch provider to **Local / Mock Mode** in Settings."
            )
            self.chat_view.add_message(
                role="assistant",
                content=error_card_content,
                model="System Alert",
            )
            logger.warning(f"AI response failed: {err_msg}")

    def _open_settings(self):
        """Display the Settings Dialog."""
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self):
        """Reload settings, update header badge, and refresh router."""
        self.settings = get_settings(reload=True)
        self.ai_router = get_ai_router()
        self._sync_header_badge()
        self.status_bar.set_ready("Settings updated successfully")
        logger.info("Settings reloaded and synced across UI.")

