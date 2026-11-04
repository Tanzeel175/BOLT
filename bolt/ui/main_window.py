"""Main Application Window for BOLT with Windows Computer Understanding and Control."""

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
    APP_ICON_PNG,
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
from bolt.ui.components.task_activity_panel import TaskActivityPanel
from bolt.ui.settings_dialog import SettingsDialog
from bolt.ui.system_tray import BOLTSystemTray
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher

logger = get_logger("MainWindow")


class AIWorker(QThread):
    """Background worker thread for live real-time streaming AI queries."""
    chunk_received = Signal(str)  # Emits each text chunk as it arrives
    finished = Signal(object)     # Emits AIResponse

    def __init__(
        self,
        router: AIRouter,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        provider_override: Optional[str] = None,
    ):
        super().__init__()
        self.router = router
        self.messages = messages
        self.system_prompt = system_prompt
        self.provider_override = provider_override
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            provider = self.router.get_provider(self.provider_override)
            sys_prompt = self.system_prompt or self.router.settings.system_prompt

            full_chunks = []
            for chunk in self.router.stream(
                self.messages,
                system_prompt=sys_prompt,
                provider_override=self.provider_override,
            ):
                if self._is_cancelled:
                    break
                full_chunks.append(chunk)
                self.chunk_received.emit(chunk)

            complete_text = "".join(full_chunks)
            if not complete_text.strip():
                # Fallback to generate if stream was empty
                response = self.router.generate(
                    self.messages,
                    self.system_prompt,
                    provider_override=self.provider_override,
                )
                self.finished.emit(response)
                return

            is_err = complete_text.startswith("⚠️") or complete_text.startswith("[Streaming error")
            response = AIResponse(
                content=complete_text,
                model=provider.default_model,
                provider=provider.provider_name,
                tokens_used=len(complete_text.split()),
                success=not is_err,
                error=complete_text if is_err else None,
            )
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


class VoiceListenWorker(QThread):
    """Background worker for Push-to-Talk audio listening and transcription."""
    finished = Signal(str, str)  # (transcribed_text, error)

    def run(self):
        try:
            from bolt.voice import get_voice_controller
            vc = get_voice_controller()
            text = vc.listen_command(max_duration_sec=6.0)
            self.finished.emit(text or "", "")
        except Exception as e:
            logger.exception("VoiceListenWorker encountered error.")
            self.finished.emit("", str(e))


class MainWindow(QMainWindow):
    """BOLT Main Desktop Interface Window."""

    def __init__(self):
        super().__init__()
        self.settings: Settings = get_settings()
        self.db: Database = get_database()
        self.ai_router: AIRouter = get_ai_router()
        self.intent_dispatcher: WindowsIntentDispatcher = get_intent_dispatcher()

        self.current_conv_id: Optional[str] = None
        self.active_worker: Optional[AIWorker] = None

        self._init_window()
        self._init_layout()
        self._connect_signals()
        self._init_system_tray()
        self._load_conversations_and_initial_chat()

    def _init_window(self):
        from PySide6.QtGui import QIcon
        self.setWindowTitle(f"{APP_NAME} — {APP_SUBTITLE} (v{APP_VERSION})")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))

    def _init_system_tray(self):
        """Initialize Windows system tray icon and background minimize behavior."""
        self.tray = BOLTSystemTray(self)
        self.tray.open_requested.connect(self._restore_from_tray)
        self.tray.settings_requested.connect(self._open_settings)
        self.tray.backup_requested.connect(self._on_tray_backup_requested)
        self.tray.quit_requested.connect(self._on_tray_quit_requested)
        self.tray.show()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_backup_requested(self):
        from bolt.core.data_manager import get_data_manager
        bp = get_data_manager().create_backup(tag="tray_quick")
        if self.tray:
            self.tray.show_desktop_notification("Backup Complete", f"Snapshot saved:\n{bp.name}")

    def _on_tray_quit_requested(self):
        from PySide6.QtWidgets import QApplication
        if hasattr(self, "tray") and self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """Minimize to system tray so BOLT continues running in background."""
        if hasattr(self, "tray") and self.tray and self.tray.isVisible():
            self.hide()
            self.tray.show_desktop_notification("BOLT Running in Background", "Click tray icon to reopen.")
            event.ignore()
        else:
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Check first-run onboarding wizard
        try:
            from bolt.ui.setup_wizard import is_first_run, SetupWizardDialog
            if is_first_run():
                wizard = SetupWizardDialog(self)
                wizard.exec()
        except Exception as e:
            logger.debug(f"First-run check note: {e}")

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

        # Phase 5: Task Activity Panel (Collapsible Dock on Right)
        self.task_panel = TaskActivityPanel(self)
        self.task_panel.setVisible(False)
        body_layout.addWidget(self.task_panel)

        root_layout.addWidget(body_widget, stretch=1)

        # 3. Bottom Task Status Bar
        self.status_bar = TaskStatusBar(self)
        root_layout.addWidget(self.status_bar)

        # Sync Header Model Badge
        self._sync_header_badge()

    def _sync_header_badge(self):
        """Update header pill based on active provider and model."""
        active_p = self.ai_router.get_provider()
        provider = active_p.provider_name
        model = active_p.default_model
        if provider == "gemini" and not self.settings.gemini_api_key.strip():
            self.header_bar.update_model_badge("Gemini (No Key)", "Local Demo Mode")
        elif provider == "openai" and not self.settings.openai_api_key.strip():
            self.header_bar.update_model_badge("OpenAI (No Key)", "Local Demo Mode")
        elif provider == "custom" and not self.settings.custom_api_key.strip() and "localhost" not in self.settings.custom_base_url and "127.0.0.1" not in self.settings.custom_base_url:
            self.header_bar.update_model_badge("Custom (No Key)", "Local Demo Mode")
        else:
            self.header_bar.update_model_badge(active_p.display_name, model)

    def _connect_signals(self):
        # Header actions
        self.header_bar.settings_requested.connect(self._open_settings)
        self.header_bar.clear_chat_requested.connect(self._clear_current_chat)
        self.header_bar.provider_selected.connect(self._on_quick_provider_switch)

        # Sidebar actions
        self.sidebar.new_chat_requested.connect(self._start_new_chat)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.sidebar.conversation_deleted.connect(self._delete_conversation)

        # Chat View suggestions
        self.chat_view.suggestion_clicked.connect(self.input_bar.set_text)

        # Input submission
        self.input_bar.message_submitted.connect(self._handle_user_message)
        self.input_bar.voice_requested.connect(self._on_voice_requested)

        # Task Activity Panel controls (Phase 5 & Phase 9)
        self.task_panel.pause_requested.connect(self._on_task_pause_requested)
        self.task_panel.resume_requested.connect(self._on_task_resume_requested)
        self.task_panel.cancel_requested.connect(self._on_task_cancel_requested)
        self.task_panel.security_approval_decided.connect(self._on_task_security_approval_decided)

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

    def _handle_user_message(self, text: str, from_voice: bool = False):
        """Process user input, record in DB, update UI, and dispatch to Windows Engine or AI worker."""
        if not self.current_conv_id:
            self._start_new_chat()

        self._last_from_voice = from_voice

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

        # 4. Check if instruction is a direct Windows, Browser, Multi-AI, or Multi-Task Operation
        intent = self.intent_dispatcher.dispatch(text)
        if intent.is_windows_action:
            if intent.action_type == "multi_action_task":
                model_used = "BOLT Task Planner"
                if intent.raw_data and "plan" in intent.raw_data:
                    from bolt.tasks.models import ExecutionPlan, TaskStatus
                    plan_obj = ExecutionPlan.from_dict(intent.raw_data["plan"])
                    self.task_panel.set_plan(plan_obj)
                    self.task_panel.setVisible(True)
                    if plan_obj.status == TaskStatus.WAITING_APPROVAL:
                        waiting_steps = [s for s in plan_obj.steps if s.status == TaskStatus.WAITING_APPROVAL]
                        if waiting_steps:
                            w = waiting_steps[0]
                            self.task_panel.show_approval_prompt(
                                w.step_id,
                                w.approval_prompt or "Approval required to proceed.",
                                is_critical=w.risk_level.value in ("critical", "4") or getattr(w, "requires_typed_confirmation", False),
                                confirmation_phrase=getattr(w, "confirmation_phrase", "CONFIRM") or "CONFIRM",
                            )
            elif intent.action_type == "compare_ai":
                model_used = "BOLT Multi-AI Engine"
            elif intent.action_type in [
                "open_website", "multi_browser_nav", "web_search",
                "site_search", "read_webpage", "switch_tab", "close_tab", "list_tabs"
            ]:
                model_used = "BOLT Browser Intelligence"
            elif intent.action_type == "switch_ai_provider":
                model_used = "BOLT Provider Manager"
            else:
                model_used = "BOLT Windows Engine"

            # Store assistant action response in SQLite
            self.db.add_message(
                conversation_id=self.current_conv_id,
                role="assistant",
                content=intent.content,
                model=model_used,
            )
            # Render response card
            self.chat_view.add_message(
                role="assistant",
                content=intent.content,
                model=model_used,
            )
            if intent.success:
                self.status_bar.set_ready(f"Completed • {intent.title}")
            else:
                self.status_bar.set_error(intent.title)

            # Speak voice response if request came from voice
            if from_voice:
                from bolt.voice import get_voice_pipeline, get_voice_controller
                spoken = get_voice_pipeline()._generate_spoken_feedback(text, intent)
                get_voice_controller().speak_async(spoken)
            return

        # 5. Otherwise, pass to AI Generative Model
        provider_override = None
        if intent.raw_data and "provider_override" in intent.raw_data:
            provider_override = intent.raw_data["provider_override"]

        active_provider = self.ai_router.get_provider(provider_override)
        self.input_bar.set_busy(True)
        self.status_bar.set_thinking(f"Thinking with {active_provider.display_name}...")

        # Create active streaming message card immediately for instant feedback
        self.current_streaming_card = self.chat_view.create_streaming_card(
            role="assistant",
            initial_text="⏳ *Thinking...*",
            model=active_provider.default_model,
        )
        self._streaming_has_started = False

        # Build ChatMessage history for AI model
        chat_history = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in messages
        ]

        # Launch background worker thread
        self.active_worker = AIWorker(
            router=self.ai_router,
            messages=chat_history,
            system_prompt=self.settings.system_prompt,
            provider_override=provider_override,
        )
        self.active_worker.chunk_received.connect(self._on_ai_chunk_received)
        self.active_worker.finished.connect(self._on_ai_response_received)
        self.active_worker.start()

    def _on_ai_chunk_received(self, chunk: str):
        """Append real-time token to visible message card."""
        if hasattr(self, "current_streaming_card") and self.current_streaming_card:
            if not getattr(self, "_streaming_has_started", False):
                self.current_streaming_card.set_content(chunk)
                self._streaming_has_started = True
            else:
                self.current_streaming_card.append_chunk(chunk)
            self.chat_view._scroll_to_bottom()

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

            # Ensure streaming card contains final full content
            if hasattr(self, "current_streaming_card") and self.current_streaming_card:
                self.current_streaming_card.set_content(content)
                self.current_streaming_card = None
            else:
                self.chat_view.add_message(
                    role="assistant",
                    content=content,
                    model=model_used,
                )

            self.status_bar.set_ready(f"Completed • Model: {model_used}")
            logger.info("AI response received and rendered successfully.")

            # Speak AI response if query came from voice
            if getattr(self, "_last_from_voice", False):
                from bolt.voice import get_voice_controller
                get_voice_controller().speak_async(content)
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
            if self.current_conv_id:
                self.db.add_message(
                    conversation_id=self.current_conv_id,
                    role="assistant",
                    content=error_card_content,
                    model=response.model or "System Alert",
                    tokens=0,
                )
            if hasattr(self, "current_streaming_card") and self.current_streaming_card:
                self.current_streaming_card.set_content(error_card_content)
                self.current_streaming_card = None
            else:
                self.chat_view.add_message(
                    role="assistant",
                    content=error_card_content,
                    model=response.model or "System Alert",
                )
            logger.warning(f"AI response failed: {err_msg}")

    def _open_settings(self):
        """Display the Settings Dialog."""
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_quick_provider_switch(self, provider_id: str):
        """Quickly switch AI Provider from header badge dropdown."""
        from bolt.ai.provider_manager import get_provider_manager
        pm = get_provider_manager()
        provider = pm.get_provider(provider_id)

        # If switching to a cloud/custom provider without an API key:
        if not provider.is_configured and provider.provider_name in ("openai", "gemini", "custom"):
            QMessageBox.information(
                self,
                "API Key Configuration Required",
                f"To use {provider.display_name}, please configure your API key in Settings (⚙).\n\n"
                f"BOLT is keeping Local AI (Ollama) active so all tasks continue running offline without interruption.",
            )
            self._open_settings()
            return

        ok, msg = pm.switch_default_provider(provider_id)
        self.settings = get_settings(reload=True)
        pm.refresh_settings(self.settings)
        self.ai_router = get_ai_router(reload=True)
        self._sync_header_badge()
        self.status_bar.set_ready(f"Active Provider: {provider.display_name}")

    def _on_settings_saved(self):
        """Reload settings, update header badge, and refresh router."""
        from bolt.ai.provider_manager import get_provider_manager
        self.settings = get_settings(reload=True)
        get_provider_manager(reload=True)
        self.ai_router = get_ai_router(reload=True)
        self._sync_header_badge()
        self.status_bar.refresh_telemetry()
        self.status_bar.set_ready("Settings updated successfully")
        logger.info("Settings reloaded and synced across UI.")

    # ---------------- Phase 5: Task Activity Panel Callbacks ----------------

    def _on_task_pause_requested(self):
        from bolt.tasks.multitasking_manager import get_multitasking_manager
        mgr = get_multitasking_manager()
        if mgr.last_active_plan and mgr.last_active_plan.plan_id in mgr._active_workers:
            mgr._active_workers[mgr.last_active_plan.plan_id].pause_task()
        self.status_bar.set_ready("Task paused")

    def _on_task_resume_requested(self):
        from bolt.tasks.multitasking_manager import get_multitasking_manager
        mgr = get_multitasking_manager()
        if mgr.last_active_plan and mgr.last_active_plan.plan_id in mgr._active_workers:
            mgr._active_workers[mgr.last_active_plan.plan_id].resume_task()
        self.status_bar.set_ready("Task resumed")

    def _on_task_cancel_requested(self):
        from bolt.tasks.multitasking_manager import get_multitasking_manager
        mgr = get_multitasking_manager()
        if mgr.last_active_plan and mgr.last_active_plan.plan_id in mgr._active_workers:
            mgr._active_workers[mgr.last_active_plan.plan_id].cancel_task()
        self.status_bar.set_ready("Task cancelled")

    def _on_task_security_approval_decided(
        self,
        step_id: str,
        approved: bool,
        session_grant: bool = False,
        typed_phrase: Optional[str] = None,
    ):
        from bolt.tasks.multitasking_manager import get_multitasking_manager
        from bolt.tasks.models import TaskStatus
        mgr = get_multitasking_manager()
        res_plan = mgr.provide_user_decision(
            approved=approved,
            session_grant=session_grant,
            typed_phrase=typed_phrase,
        )
        if res_plan:
            self.task_panel.set_plan(res_plan)
            summary_md = mgr.format_plan_summary_markdown(res_plan)
            if self.current_conv_id:
                self.db.add_message(
                    conversation_id=self.current_conv_id,
                    role="assistant",
                    content=summary_md,
                    model="BOLT Task Planner",
                )
            self.chat_view.add_message(
                role="assistant",
                content=summary_md,
                model="BOLT Task Planner",
            )

    # ---------------- Phase 7: Push-to-Talk Voice Callbacks ----------------

    def _on_voice_requested(self):
        """User pressed Push-to-Talk button."""
        from bolt.voice import get_voice_controller
        vc = get_voice_controller()

        if not vc.is_stt_available:
            info = vc.get_model_status()
            QMessageBox.information(
                self,
                "BOLT Voice Assistant (Offline STT)",
                info["instructions"],
            )
            return

        self.input_bar.set_recording(True)
        self.status_bar.set_thinking("Listening for speech (Push-to-Talk)... Speak now.")
        self.voice_worker = VoiceListenWorker(self)
        self.voice_worker.finished.connect(self._on_voice_transcription_finished)
        self.voice_worker.start()

    def _on_voice_transcription_finished(self, text: str, error: str):
        """Handle captured speech transcription result."""
        self.input_bar.set_recording(False)
        if text:
            self.input_bar.set_text(text)
            self.status_bar.set_ready(f"Heard: '{text}'")
            self._handle_user_message(text, from_voice=True)
        else:
            self.status_bar.set_ready("Voice listening finished (no speech captured).")
