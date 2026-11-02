"""
Windows Window Management subsystem for BOLT.
Handles listing, identifying, switching, minimizing, maximizing, and closing windows.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Optional
from bolt.core.logger import get_logger

logger = get_logger("WindowManager")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# ShowWindow commands
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

WM_CLOSE = 0x0010

# Desktop access flags
DESKTOP_ENUMERATE = 0x0040
DESKTOP_READOBJECTS = 0x0001


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool


class WindowManager:
    """Controls and inspects visible top-level application windows on Windows 11."""

    def get_visible_windows(self) -> List[WindowInfo]:
        """
        Enumerate all visible user-facing application windows.
        Inspects Default desktop on WinSta0 to ensure windows in interactive sessions are found.
        """
        windows: List[WindowInfo] = []

        seen_hwnds = set()

        def enum_callback(hwnd, lparam):
            if hwnd in seen_hwnds:
                return True

            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()

            if not title:
                return True

            # Skip common background/hidden system/helper windows
            if title in ["Program Manager", "Settings", "Default IME", "MSCTFIME UI"]:
                return True
            if title.startswith("GDI+ Window"):
                return True

            seen_hwnds.add(hwnd)

            # Get Process ID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            is_min = bool(user32.IsIconic(hwnd))
            is_max = bool(user32.IsZoomed(hwnd))

            windows.append(
                WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    pid=pid.value,
                    is_visible=True,
                    is_minimized=is_min,
                    is_maximized=is_max,
                )
            )
            return True

        cb = WNDENUMPROC(enum_callback)

        # 1. Enumerate current session windows
        user32.EnumWindows(cb, 0)

        # 2. Enumerate interactive Default desktop windows to capture cross-desktop apps
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ENUMERATE | DESKTOP_READOBJECTS)
        if h_default:
            try:
                user32.EnumDesktopWindows(h_default, cb, 0)
            finally:
                user32.CloseDesktop(h_default)

        return windows

    def find_window_by_title(self, query: str) -> Optional[WindowInfo]:
        """Find the most relevant window matching a query string."""
        q_lower = query.lower()
        windows = self.get_visible_windows()

        # 1. Exact match
        for w in windows:
            if w.title.lower() == q_lower:
                return w

        # 2. Contains match
        for w in windows:
            if q_lower in w.title.lower():
                return w

        return None

    def find_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """Find the main top-level window for a given process ID."""
        windows = self.get_visible_windows()
        for w in windows:
            if w.pid == pid:
                return w
        return None

    def switch_to_window(self, hwnd: int) -> bool:
        """
        Bring window to foreground. If minimized, restores it first.
        Attaches input threads if needed to bypass Windows focus restrictions.
        """
        try:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                user32.ShowWindow(hwnd, SW_SHOWNORMAL)

            # Bring to front
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            logger.info(f"Switched to window [HWND {hwnd}]")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to window {hwnd}: {e}")
            return False

    def minimize_window(self, hwnd: int) -> bool:
        """Minimize the specified window."""
        res = user32.ShowWindow(hwnd, SW_MINIMIZE)
        logger.info(f"Minimized window [HWND {hwnd}]: {bool(res)}")
        return bool(res)

    def maximize_window(self, hwnd: int) -> bool:
        """Maximize the specified window."""
        res = user32.ShowWindow(hwnd, SW_MAXIMIZE)
        logger.info(f"Maximized window [HWND {hwnd}]: {bool(res)}")
        return bool(res)

    def restore_window(self, hwnd: int) -> bool:
        """Restore window from minimized or maximized state."""
        res = user32.ShowWindow(hwnd, SW_RESTORE)
        logger.info(f"Restored window [HWND {hwnd}]: {bool(res)}")
        return bool(res)

    def close_window(self, hwnd: int) -> bool:
        """Send WM_CLOSE to gracefully ask the window to terminate."""
        res = user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        logger.info(f"Sent WM_CLOSE to window [HWND {hwnd}]: {bool(res)}")
        return bool(res)


_WINDOW_MGR_INSTANCE: Optional[WindowManager] = None


def get_window_manager() -> WindowManager:
    global _WINDOW_MGR_INSTANCE
    if _WINDOW_MGR_INSTANCE is None:
        _WINDOW_MGR_INSTANCE = WindowManager()
    return _WINDOW_MGR_INSTANCE
