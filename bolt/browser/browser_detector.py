"""
Browser Discovery and Detection subsystem for BOLT.
Detects installed browsers, executable paths, Windows default browser, and active browser processes.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import winreg
import psutil

from bolt.core.logger import get_logger

logger = get_logger("BrowserDetector")

# Known Windows browser executable names and metadata
KNOWN_BROWSERS = {
    "msedge": {
        "display_name": "Microsoft Edge",
        "exe_name": "msedge.exe",
        "channel": "msedge",
        "common_paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "chrome": {
        "display_name": "Google Chrome",
        "exe_name": "chrome.exe",
        "channel": "chrome",
        "common_paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
    },
    "brave": {
        "display_name": "Brave Browser",
        "exe_name": "brave.exe",
        "channel": "chrome",  # Chromium based
        "common_paths": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
    },
    "firefox": {
        "display_name": "Mozilla Firefox",
        "exe_name": "firefox.exe",
        "channel": "firefox",
        "common_paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    },
    "opera": {
        "display_name": "Opera",
        "exe_name": "opera.exe",
        "channel": "chrome",
        "common_paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
            r"C:\Program Files\Opera\opera.exe",
        ],
    },
}


class BrowserDetector:
    """Detects installed Windows web browsers and current default/running state."""

    def __init__(self):
        self._installed_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def detect_installed_browsers(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Discover all installed browsers by checking Windows Registry and standard installation paths.
        Returns mapping of browser_id -> {display_name, exe_path, channel, is_default, is_running}.
        """
        if self._installed_cache is not None and not force_refresh:
            return self._installed_cache

        logger.info("Detecting installed web browsers on system...")
        discovered: Dict[str, Dict[str, Any]] = {}
        default_browser_id = self.get_default_browser_id()

        # 1. Inspect Windows Registry StartMenuInternet
        registry_paths = self._scan_start_menu_internet_registry()

        # 2. Check each known browser against registry or filesystem
        for browser_id, info in KNOWN_BROWSERS.items():
            exe_path = registry_paths.get(browser_id)

            if not exe_path:
                for candidate in info["common_paths"]:
                    cand_path = Path(candidate)
                    if cand_path.is_file():
                        exe_path = str(cand_path)
                        break

            if exe_path and os.path.isfile(exe_path):
                is_running, pids = self.is_browser_running(browser_id)
                discovered[browser_id] = {
                    "id": browser_id,
                    "display_name": info["display_name"],
                    "exe_name": info["exe_name"],
                    "exe_path": exe_path,
                    "channel": info["channel"],
                    "is_default": (browser_id == default_browser_id),
                    "is_running": is_running,
                    "pids": pids,
                }
                logger.debug(f"Discovered browser: {info['display_name']} -> {exe_path}")

        self._installed_cache = discovered
        logger.info(f"Discovered {len(discovered)} web browser(s). Default: '{default_browser_id}'")
        return discovered

    def _scan_start_menu_internet_registry(self) -> Dict[str, str]:
        """Scan HKLM and HKCU StartMenuInternet registry keys for browser executables."""
        results: Dict[str, str] = {}
        hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
        subkey = r"SOFTWARE\Clients\StartMenuInternet"

        for hive in hives:
            try:
                with winreg.OpenKey(hive, subkey) as root_key:
                    num_subkeys = winreg.QueryInfoKey(root_key)[0]
                    for i in range(num_subkeys):
                        name = winreg.EnumKey(root_key, i)
                        try:
                            cmd_key_path = f"{subkey}\\{name}\\shell\\open\\command"
                            with winreg.OpenKey(hive, cmd_key_path) as cmd_key:
                                cmd_val, _ = winreg.QueryValueEx(cmd_key, "")
                                clean_path = cmd_val.strip().strip('"')
                                if os.path.isfile(clean_path):
                                    lower_clean = clean_path.lower()
                                    if "msedge" in lower_clean:
                                        results["msedge"] = clean_path
                                    elif "chrome" in lower_clean and "brave" not in lower_clean:
                                        results["chrome"] = clean_path
                                    elif "brave" in lower_clean:
                                        results["brave"] = clean_path
                                    elif "firefox" in lower_clean:
                                        results["firefox"] = clean_path
                                    elif "opera" in lower_clean:
                                        results["opera"] = clean_path
                        except OSError:
                            continue
            except OSError:
                continue

        return results

    def get_default_browser_id(self) -> str:
        """
        Identify default web browser using Windows UserChoice registry association for https.
        Returns browser ID ('msedge', 'chrome', 'brave', 'firefox', etc.).
        """
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
            ) as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                prog_lower = (prog_id or "").lower()
                if "msedge" in prog_lower:
                    return "msedge"
                elif "chrome" in prog_lower:
                    return "chrome"
                elif "brave" in prog_lower:
                    return "brave"
                elif "firefox" in prog_lower:
                    return "firefox"
                elif "opera" in prog_lower:
                    return "opera"
        except OSError:
            pass

        # Fallback to Microsoft Edge on Windows 11
        return "msedge"

    def is_browser_running(self, browser_id_or_exe: str) -> tuple[bool, List[int]]:
        """Check if a specific browser process is currently running."""
        clean = browser_id_or_exe.lower().replace(".exe", "").strip()
        exe_name = KNOWN_BROWSERS.get(clean, {}).get("exe_name", f"{clean}.exe").lower()

        pids: List[int] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname == exe_name or clean in pname:
                    pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return (len(pids) > 0, pids)

    def get_preferred_or_default_browser(self, preferred: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the browser dictionary to use.
        Returns preferred browser if installed, otherwise default browser, or first available.
        """
        installed = self.detect_installed_browsers()
        if not installed:
            return None

        if preferred and preferred.lower() in installed:
            return installed[preferred.lower()]

        default_id = self.get_default_browser_id()
        if default_id in installed:
            return installed[default_id]

        return next(iter(installed.values()))


_DETECTOR_INSTANCE: Optional[BrowserDetector] = None


def get_browser_detector() -> BrowserDetector:
    """Singleton getter for BrowserDetector."""
    global _DETECTOR_INSTANCE
    if _DETECTOR_INSTANCE is None:
        _DETECTOR_INSTANCE = BrowserDetector()
    return _DETECTOR_INSTANCE

