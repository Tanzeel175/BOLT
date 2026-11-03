"""
Windows System Tray Subsystem for BOLT (Phase 10).
Provides tray icon, background minimizing, context menu, and desktop notifications.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from bolt.config.constants import APP_ICON_PNG, APP_ICON_ICO, APP_NAME
from bolt.core.logger import get_logger

logger = get_logger("SystemTray")


class BOLTSystemTray(QSystemTrayIcon):
    """System tray integration allowing BOLT to run quietly in the background."""

    open_requested = Signal()
    settings_requested = Signal()
    backup_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_show_callback=None,
        on_quit_callback=None,
    ):
        super().__init__(parent)
        self.parent_widget = parent
        self.on_show_callback = on_show_callback
        self.on_quit_callback = on_quit_callback
        self._init_tray()

    def _init_tray(self):
        # 1. Set Icon
        if APP_ICON_PNG.exists():
            self.setIcon(QIcon(str(APP_ICON_PNG)))
        elif APP_ICON_ICO.exists():
            self.setIcon(QIcon(str(APP_ICON_ICO)))

        self.setToolTip(f"{APP_NAME} — Personal Autonomous AI Assistant")

        # 2. Build Context Menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #30363d;
                margin: 4px 0;
            }
        """)

        action_open = QAction("⚡ Open BOLT", self)
        action_open.triggered.connect(self.open_requested.emit)
        menu.addAction(action_open)

        action_settings = QAction("⚙️ Settings", self)
        action_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(action_settings)

        action_backup = QAction("📦 Backup Data", self)
        action_backup.triggered.connect(self.backup_requested.emit)
        menu.addAction(action_backup)

        menu.addSeparator()

        action_quit = QAction("🚪 Exit BOLT", self)
        action_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(action_quit)

        self.menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        if self.on_show_callback:
            self.open_requested.connect(self.on_show_callback)
        if self.on_quit_callback:
            self.quit_requested.connect(self.on_quit_callback)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Toggle main window on tray click."""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_requested.emit()

    def show_desktop_notification(self, title: str, message: str, msec: int = 4000):
        """Display native Windows desktop notification banner."""
        try:
            self.showMessage(
                f"{APP_NAME}: {title}",
                message,
                QSystemTrayIcon.Information,
                msec,
            )
        except Exception as e:
            logger.debug(f"Tray notification failed: {e}")

    def notify_task_started(self, task_name: str) -> None:
        """Helper to notify task start."""
        self.show_desktop_notification("Task In Progress", f"Executing: {task_name}")

    def notify_task_completed(self, task_name: str, details: str = "") -> None:
        """Helper to notify task completion."""
        msg = f"Task completed: {task_name}" + (f"\n{details}" if details else "")
        self.show_desktop_notification("Task Succeeded", msg)

    def notify_security_alert(self, message: str) -> None:
        """Helper to notify security approval or violation."""
        self.show_desktop_notification("Security Notice", message)
