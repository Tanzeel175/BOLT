"""
Windows Application Discovery System for BOLT.
Discovers desktop applications, Start Menu shortcuts, Registry entries, and Windows built-ins.
"""

import os
import pathlib
import winreg
from dataclasses import dataclass
from typing import Dict, List, Optional
from bolt.core.logger import get_logger

logger = get_logger("AppDiscovery")


@dataclass
class DiscoveredApp:
    name: str                   # Normalized name (e.g., "visual studio code")
    display_name: str           # Human-readable title (e.g., "Visual Studio Code")
    launch_identifier: str      # Path to exe or .lnk or protocol URI
    launch_method: str          # "direct_exe", "start_shortcut", "uwp_protocol", "shell_command"
    executable_path: str = ""   # Resolved binary if known
    category: str = "General"   # "Browsers", "Development", "Productivity", "Media", "System", "Utilities"
    discovery_source: str = "start_menu"
    is_verified: bool = False


# Common Windows 11 Built-in Applications
SYSTEM_BUILTINS: List[DiscoveredApp] = [
    DiscoveredApp(
        name="notepad",
        display_name="Notepad",
        launch_identifier="notepad.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\notepad.exe"),
        category="Utilities",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="calculator",
        display_name="Calculator",
        launch_identifier="calc.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\calc.exe"),
        category="Utilities",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="paint",
        display_name="Paint",
        launch_identifier="mspaint.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\mspaint.exe"),
        category="Media",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="file explorer",
        display_name="File Explorer",
        launch_identifier="explorer.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\explorer.exe"),
        category="System",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="command prompt",
        display_name="Command Prompt",
        launch_identifier="cmd.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\cmd.exe"),
        category="Development",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="powershell",
        display_name="Windows PowerShell",
        launch_identifier="powershell.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"),
        category="Development",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="task manager",
        display_name="Task Manager",
        launch_identifier="taskmgr.exe",
        launch_method="shell_command",
        executable_path=os.path.expandvars(r"%SystemRoot%\System32\taskmgr.exe"),
        category="System",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="settings",
        display_name="Windows Settings",
        launch_identifier="ms-settings:",
        launch_method="uwp_protocol",
        category="System",
        discovery_source="system_builtins",
        is_verified=True,
    ),
    DiscoveredApp(
        name="snipping tool",
        display_name="Snipping Tool",
        launch_identifier="snippingtool.exe",
        launch_method="shell_command",
        category="Utilities",
        discovery_source="system_builtins",
        is_verified=True,
    ),
]


def categorize_application(name: str, path: str) -> str:
    """Infer application category based on name and executable hints."""
    n = name.lower()
    p = path.lower()

    if any(k in n or k in p for k in ["chrome", "brave", "firefox", "edge", "opera", "browser"]):
        return "Browsers"
    if any(k in n or k in p for k in ["code", "visual studio", "pycharm", "intellij", "git", "terminal", "python", "sublime", "vim", "ide"]):
        return "Development"
    if any(k in n or k in p for k in ["word", "excel", "powerpoint", "onenote", "office", "acrobat", "pdf", "calc"]):
        return "Productivity"
    if any(k in n or k in p for k in ["vlc", "spotify", "music", "media", "paint", "photoshop", "capcut", "video"]):
        return "Media"
    if any(k in n or k in p for k in ["settings", "control", "taskmgr", "explorer", "system", "disk"]):
        return "System"
    return "General"


class ApplicationDiscovery:
    """Scanner for discovering installed desktop apps across Windows 11."""

    def __init__(self):
        self.cached_apps: Dict[str, DiscoveredApp] = {}

    def discover_all(self) -> List[DiscoveredApp]:
        """Run all discovery pipelines and return unified deduplicated list."""
        apps: Dict[str, DiscoveredApp] = {}

        # 1. Start with Built-in Windows tools
        for app in SYSTEM_BUILTINS:
            apps[app.name] = app

        # 2. Scan Registry App Paths
        reg_apps = self._scan_registry_app_paths()
        for app in reg_apps:
            if app.name not in apps:
                apps[app.name] = app

        # 3. Scan Start Menu Shortcuts
        start_apps = self._scan_start_menu()
        for app in start_apps:
            if app.name not in apps:
                apps[app.name] = app

        # 4. Scan Registry Uninstall Keys
        uninstall_apps = self._scan_registry_uninstall()
        for app in uninstall_apps:
            if app.name not in apps:
                apps[app.name] = app

        self.cached_apps = apps
        logger.info(f"Application Discovery complete. Discovered {len(apps)} applications.")
        return list(apps.values())

    def _scan_start_menu(self) -> List[DiscoveredApp]:
        """Scan User and System Start Menu directories for .lnk shortcuts."""
        results = []
        directories = []

        if "APPDATA" in os.environ:
            user_start = pathlib.Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            if user_start.exists():
                directories.append((user_start, "start_menu_user"))

        if "PROGRAMDATA" in os.environ:
            common_start = pathlib.Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            if common_start.exists():
                directories.append((common_start, "start_menu_common"))

        for dir_path, source in directories:
            try:
                for lnk in dir_path.rglob("*.lnk"):
                    stem = lnk.stem.strip()
                    # Skip uninstallers, help manuals, web links
                    stem_lower = stem.lower()
                    if any(bad in stem_lower for bad in ["uninstall", "remove", "help", "readme", "website"]):
                        continue

                    category = categorize_application(stem, str(lnk))
                    results.append(
                        DiscoveredApp(
                            name=stem_lower,
                            display_name=stem,
                            launch_identifier=str(lnk),
                            launch_method="start_shortcut",
                            executable_path="",
                            category=category,
                            discovery_source=source,
                            is_verified=lnk.exists(),
                        )
                    )
            except Exception as e:
                logger.warning(f"Error scanning Start Menu at {dir_path}: {e}")

        return results

    def _scan_registry_app_paths(self) -> List[DiscoveredApp]:
        """Scan HKLM and HKCU App Paths for registered executables."""
        results = []
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub_name) as sub_key:
                                raw_path, _ = winreg.QueryValueEx(sub_key, "")
                                if raw_path:
                                    resolved_path = os.path.expandvars(raw_path.strip().strip('"'))
                                    clean_name = sub_name.lower().replace(".exe", "").strip()
                                    display_name = clean_name.replace("-", " ").replace("_", " ").title()
                                    category = categorize_application(clean_name, resolved_path)
                                    is_ver = os.path.exists(resolved_path)

                                    results.append(
                                        DiscoveredApp(
                                            name=clean_name,
                                            display_name=display_name,
                                            launch_identifier=resolved_path,
                                            launch_method="direct_exe",
                                            executable_path=resolved_path,
                                            category=category,
                                            discovery_source="registry_app_paths",
                                            is_verified=is_ver,
                                        )
                                    )
                        except Exception:
                            continue
            except Exception:
                continue

        return results

    def _scan_registry_uninstall(self) -> List[DiscoveredApp]:
        """Scan Registry Uninstall keys for installed programs with InstallLocation or DisplayIcon."""
        results = []
        subkeys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for root, sub_path in subkeys:
            try:
                with winreg.OpenKey(root, sub_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub_name) as app_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                                except FileNotFoundError:
                                    continue

                                if not display_name or not display_name.strip():
                                    continue

                                display_name = display_name.strip()
                                norm_name = display_name.lower()

                                # Try to get executable from DisplayIcon or InstallLocation
                                exe_path = ""
                                try:
                                    icon, _ = winreg.QueryValueEx(app_key, "DisplayIcon")
                                    if icon and ".exe" in icon.lower():
                                        clean_icon = icon.split(",")[0].strip().strip('"')
                                        if os.path.exists(clean_icon):
                                            exe_path = clean_icon
                                except Exception:
                                    pass

                                if not exe_path:
                                    try:
                                        loc, _ = winreg.QueryValueEx(app_key, "InstallLocation")
                                        if loc and os.path.isdir(loc):
                                            # Look for exe matching name
                                            for candidate in pathlib.Path(loc).glob("*.exe"):
                                                if "uninstall" not in candidate.name.lower():
                                                    exe_path = str(candidate)
                                                    break
                                    except Exception:
                                        pass

                                if exe_path:
                                    results.append(
                                        DiscoveredApp(
                                            name=norm_name,
                                            display_name=display_name,
                                            launch_identifier=exe_path,
                                            launch_method="direct_exe",
                                            executable_path=exe_path,
                                            category=categorize_application(display_name, exe_path),
                                            discovery_source="registry_uninstall",
                                            is_verified=os.path.exists(exe_path),
                                        )
                                    )
                        except Exception:
                            continue
            except Exception:
                continue

        return results

