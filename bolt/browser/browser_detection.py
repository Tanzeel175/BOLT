"""
Browser Detection Subsystem for BOLT.
Scans Windows 11 registry and standard paths to detect installed browsers,
resolves their executable paths, identifies the system default browser,
and detects currently running browser processes.
"""

import os
import winreg
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import psutil

from bolt.core.logger import get_logger

logger = get_logger("BrowserDetection")


@dataclass
class BrowserInfo:
    name: str
    browser_type: str  # "chrome", "edge", "firefox", "brave", "opera", "other"
    executable_path: str
    is_default: bool = False
    is_running: bool = False
    running_pids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "browser_type": self.browser_type,
            "executable_path": self.executable_path,
            "is_default": self.is_default,
            "is_running": self.is_running,
            "running_pids": self.running_pids,
        }


class BrowserDetector:
    """Detects installed, default, and running web browsers on Windows 11."""

    # Standard browser registry app names and common locations
    KNOWN_BROWSERS = [
        {
            "name": "Google Chrome",
            "type": "chrome",
            "exe_names": ["chrome.exe"],
            "reg_app_path": "chrome.exe",
            "prog_id_keywords": ["chrome"],
            "fallback_paths": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ],
        },
        {
            "name": "Microsoft Edge",
            "type": "edge",
            "exe_names": ["msedge.exe"],
            "reg_app_path": "msedge.exe",
            "prog_id_keywords": ["edge", "msedge"],
            "fallback_paths": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            ],
        },
        {
            "name": "Brave Browser",
            "type": "brave",
            "exe_names": ["brave.exe"],
            "reg_app_path": "brave.exe",
            "prog_id_keywords": ["brave"],
            "fallback_paths": [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
        },
        {
            "name": "Mozilla Firefox",
            "type": "firefox",
            "exe_names": ["firefox.exe"],
            "reg_app_path": "firefox.exe",
            "prog_id_keywords": ["firefox"],
            "fallback_paths": [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ],
        },
        {
            "name": "Opera",
            "type": "opera",
            "exe_names": ["opera.exe", "launcher.exe"],
            "reg_app_path": "opera.exe",
            "prog_id_keywords": ["opera"],
            "fallback_paths": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
                r"C:\Program Files\Opera\launcher.exe",
            ],
        },
    ]

    def __init__(self):
        self._cached_browsers: Optional[List[BrowserInfo]] = None

    def get_default_browser_type(self) -> str:
        """Query Windows registry for user's default browser association."""
        try:
            key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                prog_id_lower = str(prog_id).lower()
                for b in self.KNOWN_BROWSERS:
                    if any(k in prog_id_lower for k in b["prog_id_keywords"]):
                        return b["type"]
        except Exception as e:
            logger.debug(f"Failed to query default browser UserChoice: {e}")

        # Fallback check under http
        try:
            key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                prog_id_lower = str(prog_id).lower()
                for b in self.KNOWN_BROWSERS:
                    if any(k in prog_id_lower for k in b["prog_id_keywords"]):
                        return b["type"]
        except Exception:
            pass

        return "edge"  # Standard Windows 11 default fallback

    def _find_executable_from_registry(self, app_path_name: str) -> Optional[str]:
        """Check HKLM and HKCU App Paths for registered browser executable."""
        hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        for hive in hives:
            try:
                reg_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_path_name}"
                with winreg.OpenKey(hive, reg_path) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val):
                        return val
            except Exception:
                continue
        return None

    def detect_installed_browsers(self, refresh: bool = False) -> List[BrowserInfo]:
        """Detect all installed browsers, their paths, default status, and running state."""
        if self._cached_browsers is not None and not refresh:
            # Refresh running process states dynamically
            self._update_running_processes(self._cached_browsers)
            return self._cached_browsers

        default_type = self.get_default_browser_type()
        detected: List[BrowserInfo] = []

        for b in self.KNOWN_BROWSERS:
            exe_path = self._find_executable_from_registry(b["reg_app_path"])
            if not exe_path:
                for candidate in b["fallback_paths"]:
                    if os.path.isfile(candidate):
                        exe_path = candidate
                        break

            if exe_path:
                is_default = (b["type"] == default_type)
                info = BrowserInfo(
                    name=b["name"],
                    browser_type=b["type"],
                    executable_path=exe_path,
                    is_default=is_default,
                    is_running=False,
                    running_pids=[],
                )
                detected.append(info)

        self._update_running_processes(detected)
        self._cached_browsers = detected
        logger.info(f"Detected {len(detected)} installed browsers (Default: {default_type})")
        return detected

    def _update_running_processes(self, browsers: List[BrowserInfo]) -> None:
        """Scan current OS process table and assign running state and PIDs to browsers."""
        running_map: Dict[str, List[int]] = {}

        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    pid = proc.info["pid"]
                    for b in self.KNOWN_BROWSERS:
                        if pname in [e.lower() for e in b["exe_names"]]:
                            running_map.setdefault(b["type"], []).append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"Error checking running browser processes: {e}")

        for b in browsers:
            pids = running_map.get(b.browser_type, [])
            b.is_running = len(pids) > 0
            b.running_pids = pids

    def get_preferred_or_default_browser(self, preferred_name_or_type: str = "") -> Optional[BrowserInfo]:
        """
        Get the requested browser by name/type, or return the system default browser.
        Falls back to any installed browser if default is not located.
        """
        installed = self.detect_installed_browsers()
        if not installed:
            return None

        clean_pref = preferred_name_or_type.strip().lower()
        if clean_pref:
            for b in installed:
                if clean_pref in b.name.lower() or clean_pref == b.browser_type:
                    return b

        # Find default browser
        for b in installed:
            if b.is_default:
                return b

        # Fallback to first available installed browser
        return installed[0]


_BROWSER_DETECTOR: Optional[BrowserDetector] = None


def get_browser_detector() -> BrowserDetector:
    global _BROWSER_DETECTOR
    if _BROWSER_DETECTOR is None:
        _BROWSER_DETECTOR = BrowserDetector()
    return _BROWSER_DETECTOR

