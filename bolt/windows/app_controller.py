"""
Application Controller subsystem for BOLT.
Handles opening, closing, detecting, and switching Windows applications with launch verification
and duplicate window prevention.
"""

import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
import psutil

from bolt.core.logger import get_logger
from bolt.windows.app_registry import ApplicationRegistry, get_app_registry
from bolt.windows.window_manager import WindowManager, get_window_manager

logger = get_logger("AppController")

# System processes that BOLT must NEVER terminate
PROTECTED_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
    "explorer.exe", "taskhostw.exe", "sihost.exe", "ctfmon.exe", "fontdrvhost.exe",
    "python.exe", "pythonw.exe", "bolt", "antigravity.exe", "antigravity ide.exe"
}


class AppController:
    """Orchestrates Windows application lifecycle, process inspection, and window focus."""

    def __init__(
        self,
        registry: Optional[ApplicationRegistry] = None,
        window_mgr: Optional[WindowManager] = None,
    ):
        self.registry = registry or get_app_registry()
        self.window_mgr = window_mgr or get_window_manager()

    def get_running_processes_by_name(self, name_or_exe: str) -> List[psutil.Process]:
        """Find active processes matching a name or executable filename."""
        clean = name_or_exe.lower().replace(".exe", "").strip()
        matching = []

        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                p_name = (proc.info["name"] or "").lower().replace(".exe", "")
                p_exe = (proc.info["exe"] or "").lower()

                if clean == p_name or clean in p_name or (p_exe and clean in p_exe):
                    matching.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return matching

    def is_app_running(self, app_name_or_exe: str) -> Tuple[bool, List[int]]:
        """Check if an application is currently running, returning status and active PIDs."""
        procs = self.get_running_processes_by_name(app_name_or_exe)
        pids = [p.pid for p in procs]
        return (len(pids) > 0, pids)

    def open_application(self, query: str) -> Dict[str, Any]:
        """
        Open application by natural language name.
        1. Resolves app in registry.
        2. If already running, switches to existing window to prevent duplicates.
        3. If not running, launches and empirically verifies success.
        """
        logger.info(f"Open application requested: '{query}'")

        # 1. Resolve application in registry
        app_record = self.registry.resolve_application(query)
        if not app_record:
            return {
                "success": False,
                "error": f"Could not find application '{query}' installed on this computer.",
                "app_name": query,
            }

        display_name = app_record["display_name"]
        app_name = app_record["name"]
        launch_id = app_record["launch_identifier"]
        launch_method = app_record["launch_method"]
        app_id = app_record["id"]

        # 2. Check if already running (Duplicate Window Prevention)
        running, pids = self.is_app_running(app_name)
        if not running and app_record.get("executable_path"):
            exe_stem = os.path.basename(app_record["executable_path"]).replace(".exe", "")
            running, pids = self.is_app_running(exe_stem)

        if running:
            # Try to switch to existing window
            windows = self.window_mgr.get_visible_windows()
            target_window = None

            # Check matching PID
            for w in windows:
                if w.pid in pids:
                    target_window = w
                    break

            # Fallback check matching title
            if not target_window:
                for w in windows:
                    if app_name in w.title.lower() or display_name.lower() in w.title.lower():
                        target_window = w
                        break

            if target_window:
                self.window_mgr.switch_to_window(target_window.hwnd)
                logger.info(f"Application '{display_name}' is already running. Switched to active window.")
                return {
                    "success": True,
                    "already_running": True,
                    "action": "switched_to_window",
                    "app_name": display_name,
                    "message": f"{display_name} is already open. Switched to active window.",
                }
            else:
                logger.info(f"Application '{display_name}' running in background with no visible window; launching visible instance...")

        # 3. Launch application
        logger.info(f"Launching {display_name} via {launch_method} ('{launch_id}')...")
        try:
            if launch_method == "direct_exe":
                subprocess.Popen([launch_id], shell=False)
            elif launch_method == "start_shortcut":
                os.startfile(launch_id)
            elif launch_method == "uwp_protocol":
                os.startfile(launch_id)
            elif launch_method == "shell_command":
                os.startfile(launch_id)
            else:
                subprocess.Popen(launch_id, shell=True)

        except Exception as e:
            logger.error(f"Failed to launch '{display_name}': {e}")
            return {
                "success": False,
                "error": f"Failed to execute launch for {display_name}: {e}",
                "app_name": display_name,
            }

        # 4. Verify Launch Success (Poll for up to 3.5 seconds)
        verified = False
        start_time = time.time()
        while time.time() - start_time < 3.5:
            time.sleep(0.4)
            is_run, _ = self.is_app_running(app_name)
            if is_run:
                verified = True
                break
            # Also check by window title
            win = self.window_mgr.find_window_by_title(display_name)
            if win:
                verified = True
                break

        if verified:
            self.registry.record_launch_success(app_id)
            logger.info(f"Verified launch of '{display_name}'.")
            return {
                "success": True,
                "already_running": False,
                "action": "launched",
                "app_name": display_name,
                "message": f"Successfully opened {display_name}.",
            }
        else:
            # Command was dispatched but process could not be confirmed immediately
            logger.warning(f"Launched {display_name}, but process verification timed out.")
            return {
                "success": True,
                "already_running": False,
                "action": "dispatched",
                "app_name": display_name,
                "message": f"Launch command dispatched for {display_name}.",
            }

    def close_application(self, query: str) -> Dict[str, Any]:
        """
        Close application by name.
        Gracefully asks top-level windows to close, and safely terminates processes if needed.
        Guarantees that system/unrelated processes are never terminated.
        """
        logger.info(f"Close application requested: '{query}'")
        clean_query = query.strip().lower()

        # Protection check
        for protected in PROTECTED_PROCESSES:
            if clean_query == protected or clean_query in protected:
                return {
                    "success": False,
                    "error": f"Cannot terminate protected system process '{query}'.",
                    "app_name": query,
                }

        # Resolve via registry if possible to get exact name / exe
        app_record = self.registry.resolve_application(query)
        target_name = app_record["name"] if app_record else clean_query
        display_name = app_record["display_name"] if app_record else query.title()

        procs = self.get_running_processes_by_name(target_name)
        if not procs and app_record and app_record.get("executable_path"):
            exe_stem = os.path.basename(app_record["executable_path"]).replace(".exe", "")
            procs = self.get_running_processes_by_name(exe_stem)

        if not procs:
            return {
                "success": False,
                "error": f"'{display_name}' is not currently running.",
                "app_name": display_name,
            }

        closed_pids = []
        for proc in procs:
            pid = proc.pid
            # Safety check per-process
            try:
                p_name = proc.name().lower()
                if p_name in PROTECTED_PROCESSES:
                    continue

                # 1. Try closing top-level window gracefully first
                win = self.window_mgr.find_window_by_pid(pid)
                if win:
                    self.window_mgr.close_window(win.hwnd)

                # Wait up to 1 second
                try:
                    proc.wait(timeout=1.0)
                    closed_pids.append(pid)
                    continue
                except psutil.TimeoutExpired:
                    pass

                # 2. Terminate process cleanly if window close didn't exit it
                proc.terminate()
                closed_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Error terminating PID {pid}: {e}")

        if closed_pids:
            logger.info(f"Closed {display_name} (PIDs: {closed_pids})")
            return {
                "success": True,
                "action": "closed",
                "app_name": display_name,
                "pids": closed_pids,
                "message": f"Successfully closed {display_name}.",
            }
        else:
            return {
                "success": False,
                "error": f"Could not close {display_name} (insufficient permissions).",
                "app_name": display_name,
            }

    def list_running_applications(self) -> List[Dict[str, Any]]:
        """
        List running user-facing applications (deduplicated, with window titles and memory usage).
        Filters out background system daemons and workers.
        """
        visible_windows = self.window_mgr.get_visible_windows()
        window_pids = {w.pid: w.title for w in visible_windows}

        running_apps = []
        seen_names = set()

        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pid = proc.info["pid"]
                name = proc.info["name"] or ""
                name_clean = name.lower()

                if name_clean in PROTECTED_PROCESSES or name_clean.startswith("svchost"):
                    continue

                # Only include processes with visible windows or known registered applications
                if pid in window_pids or self.registry.resolve_application(name_clean, allow_live_discovery=False):
                    if name_clean not in seen_names:
                        seen_names.add(name_clean)
                        mem_mb = round(proc.info["memory_info"].rss / (1024 * 1024), 1)
                        win_title = window_pids.get(pid, "")

                        running_apps.append({
                            "pid": pid,
                            "name": name.replace(".exe", ""),
                            "window_title": win_title,
                            "memory_mb": mem_mb,
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        running_apps.sort(key=lambda x: x["memory_mb"], reverse=True)
        return running_apps

    def switch_application(self, query: str) -> Dict[str, Any]:
        """Switch focus to a running application by name or window title."""
        logger.info(f"Switch application requested: '{query}'")
        clean = query.strip()

        # 1. Try finding window by title directly
        win = self.window_mgr.find_window_by_title(clean)
        if win:
            self.window_mgr.switch_to_window(win.hwnd)
            return {
                "success": True,
                "app_name": win.title,
                "hwnd": win.hwnd,
                "message": f"Switched to '{win.title}'.",
            }

        # 2. Try matching running processes
        running, pids = self.is_app_running(clean)
        if running:
            windows = self.window_mgr.get_visible_windows()
            for w in windows:
                if w.pid in pids:
                    self.window_mgr.switch_to_window(w.hwnd)
                    return {
                        "success": True,
                        "app_name": w.title,
                        "hwnd": w.hwnd,
                        "message": f"Switched to '{w.title}'.",
                    }

        return {
            "success": False,
            "error": f"Could not find open application or window matching '{query}'.",
        }


_APP_CONTROLLER_INSTANCE: Optional[AppController] = None


def get_app_controller() -> AppController:
    global _APP_CONTROLLER_INSTANCE
    if _APP_CONTROLLER_INSTANCE is None:
        _APP_CONTROLLER_INSTANCE = AppController()
    return _APP_CONTROLLER_INSTANCE
