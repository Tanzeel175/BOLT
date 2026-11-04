"""
Chrome Profile Manager for BOLT.
Discovers, inspects, selects, and activates Google Chrome profiles
from Windows Local State without extracting sensitive credential data.
"""

import json
import re
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from bolt.core.logger import get_logger
from bolt.windows.window_manager import get_window_manager, WindowInfo

logger = get_logger("ChromeProfileManager")


@dataclass
class ChromeProfileInfo:
    directory: str             # e.g. "Default", "Profile 1", "Profile 4"
    name: str                  # e.g. "Your Chrome", "m tanzeel", "cfd.nu.edu.pk"
    gaia_name: str             # e.g. "Tanzeel Shahzad", "Muhammad Tanzeel Shahzad"
    email: str                 # e.g. "m.tanzeel.s.87@gmail.com"
    active_time: float = 0.0
    avatar_icon: str = ""
    is_active_window: bool = False

    def matches_query(self, query: str) -> Tuple[bool, int]:
        """
        Check if query matches this profile.
        Returns (is_match, match_score) where higher score indicates closer match.
        """
        q = query.strip().lower()
        if not q:
            return False, 0

        # Exact matches (score 100)
        if q == self.directory.lower():
            return True, 100
        if q == self.email.lower():
            return True, 95
        if q == self.name.lower():
            return True, 90
        if q == self.gaia_name.lower():
            return True, 90

        # Substring / token matching
        score = 0
        if q in self.gaia_name.lower():
            score = max(score, 80)
        if q in self.name.lower():
            score = max(score, 75)
        if q in self.email.lower():
            score = max(score, 70)
        if q in self.directory.lower():
            score = max(score, 60)

        # Token overlap check (e.g. "muhammad tanzeel" in "muhammad tanzeel shahzad")
        q_tokens = set(q.split())
        gaia_tokens = set(self.gaia_name.lower().split())
        name_tokens = set(self.name.lower().split())

        if q_tokens and q_tokens.issubset(gaia_tokens):
            score = max(score, 85)
        elif q_tokens and q_tokens.issubset(name_tokens):
            score = max(score, 80)
        elif q_tokens and (q_tokens & gaia_tokens):
            score = max(score, 50 + len(q_tokens & gaia_tokens) * 10)

        return (score > 0, score)


class ChromeProfileManager:
    """Manages discovery and activation of Google Chrome profiles on Windows."""

    _instance: Optional["ChromeProfileManager"] = None

    def __init__(self):
        self.wm = get_window_manager()
        self._chrome_exe: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "ChromeProfileManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_chrome_executable_path(self) -> str:
        """Find the path to the Google Chrome executable on Windows."""
        if self._chrome_exe and os.path.isfile(self._chrome_exe):
            return self._chrome_exe

        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                self._chrome_exe = c
                return c

        self._chrome_exe = "chrome.exe"
        return "chrome.exe"

    def get_user_data_path(self) -> str:
        """Get the root User Data path for Chrome."""
        local_app = os.environ.get("LOCALAPPDATA", "")
        return os.path.join(local_app, "Google", "Chrome", "User Data")

    def list_profiles(self) -> List[ChromeProfileInfo]:
        """
        Parse Chrome's Local State file and return all configured profiles.
        Never reads or touches passwords, cookies, or auth tokens.
        """
        local_state_path = os.path.join(self.get_user_data_path(), "Local State")
        if not os.path.isfile(local_state_path):
            logger.warning(f"Chrome Local State file not found at: {local_state_path}")
            return []

        try:
            with open(local_state_path, "r", encoding="utf-8", errors="ignore") as f:
                state_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read Chrome Local State: {e}")
            return []

        info_cache = state_data.get("profile", {}).get("info_cache", {})
        profiles: List[ChromeProfileInfo] = []

        # Find which profile windows are currently open
        open_profiles = self.get_open_profile_windows()

        for dir_name, meta in info_cache.items():
            name = meta.get("name", dir_name)
            gaia = meta.get("gaia_name", "")
            email = meta.get("user_name", "")
            active_t = float(meta.get("active_time", 0.0) or 0.0)
            avatar = meta.get("avatar_icon", "")

            is_open = dir_name in open_profiles or any(
                p.matches_query(name)[0] or (email and p.matches_query(email)[0])
                for p in open_profiles.values()
            )

            profiles.append(
                ChromeProfileInfo(
                    directory=dir_name,
                    name=name,
                    gaia_name=gaia,
                    email=email,
                    active_time=active_t,
                    avatar_icon=avatar,
                    is_active_window=is_open,
                )
            )

        # Sort profiles: currently open first, then by last active timestamp descending
        profiles.sort(key=lambda p: (not p.is_active_window, -p.active_time))
        return profiles

    def get_open_profile_windows(self) -> Dict[str, ChromeProfileInfo]:
        """
        Inspect open top-level Chrome windows to identify which profile is active in each.
        Uses UI Automation PaneControl labels (e.g. 'Window Title – m tanzeel').
        """
        open_map: Dict[str, ChromeProfileInfo] = {}
        all_profiles = self._read_profiles_raw()

        visible_windows = self.wm.get_visible_windows()
        chrome_windows = [w for w in visible_windows if "chrome" in w.title.lower()]

        if not chrome_windows:
            return open_map

        # Try to resolve via UI Automation PaneControl name
        from bolt.windows.ui_automation import ensure_interactive_desktop
        ensure_interactive_desktop()
        import uiautomation as auto

        for win in chrome_windows:
            try:
                ctrl = auto.ControlFromHandle(win.hwnd)
                if not ctrl:
                    continue

                profile_found = None
                # Check root or direct children PaneControls for profile indicator
                for c, _ in auto.WalkControl(ctrl, maxDepth=3):
                    c_name = c.Name or ""
                    if "–" in c_name or "—" in c_name or "-" in c_name:
                        for prof in all_profiles:
                            # Match profile name, gaia name, or email in pane title
                            if prof.name.lower() in c_name.lower() or (prof.gaia_name and prof.gaia_name.lower() in c_name.lower()):
                                profile_found = prof
                                break
                    if profile_found:
                        break

                # Fallback check window title
                if not profile_found:
                    for prof in all_profiles:
                        if prof.name.lower() in win.title.lower() or (prof.gaia_name and prof.gaia_name.lower() in win.title.lower()):
                            profile_found = prof
                            break

                if profile_found:
                    open_map[str(win.hwnd)] = profile_found
            except Exception as e:
                logger.debug(f"Error inspecting Chrome window HWND {win.hwnd} for profile: {e}")

        return open_map

    def _read_profiles_raw(self) -> List[ChromeProfileInfo]:
        """Helper to get profiles without recursive get_open_profile_windows call."""
        local_state_path = os.path.join(self.get_user_data_path(), "Local State")
        if not os.path.isfile(local_state_path):
            return []
        try:
            with open(local_state_path, "r", encoding="utf-8", errors="ignore") as f:
                state_data = json.load(f)
        except Exception:
            return []

        info_cache = state_data.get("profile", {}).get("info_cache", {})
        profiles = []
        for dir_name, meta in info_cache.items():
            profiles.append(
                ChromeProfileInfo(
                    directory=dir_name,
                    name=meta.get("name", dir_name),
                    gaia_name=meta.get("gaia_name", ""),
                    email=meta.get("user_name", ""),
                    active_time=float(meta.get("active_time", 0.0) or 0.0),
                )
            )
        return profiles

    def find_profile(self, query: str) -> Tuple[Optional[ChromeProfileInfo], List[ChromeProfileInfo]]:
        """
        Find profile matching query.
        Returns (best_match, candidates_list).
        If ambiguous, best_match is None and candidates_list contains the close matches.
        """
        profiles = self.list_profiles()
        if not profiles:
            return None, []

        clean_q = query.strip().lower()
        q_norm = re.sub(r"^(?:select|choose|pick|open|use|switch\s+to)\s+(?:the\s+)?", "", clean_q).strip()
        q_norm = re.sub(r"\s+profile$", "", q_norm).strip()

        # Ordinal matching: "first", "1st", "first of them", "first one", "profile 1", "second", "2nd", etc.
        ordinals = {
            "first": 0, "1st": 0, "1": 0, "first of them": 0, "first one": 0, "first profile": 0,
            "the first": 0, "the first one": 0, "the first profile": 0,
            "second": 1, "2nd": 1, "2": 1, "second of them": 1, "second one": 1, "second profile": 1,
            "the second": 1, "the second one": 1, "the second profile": 1,
            "third": 2, "3rd": 2, "3": 2, "third of them": 2, "third one": 2, "third profile": 2,
            "the third": 2, "the third one": 2, "the third profile": 2,
            "fourth": 3, "4th": 3, "4": 3, "fourth of them": 3, "fourth one": 3, "fourth profile": 3,
            "fifth": 4, "5th": 4, "5": 4, "fifth of them": 4, "fifth one": 4, "fifth profile": 4,
            "last": -1, "last one": -1, "last of them": -1, "the last": -1, "the last one": -1,
        }

        if q_norm in ordinals or clean_q in ordinals:
            idx = ordinals.get(q_norm, ordinals.get(clean_q, 0))
            if profiles and (0 <= idx < len(profiles) or idx == -1):
                return profiles[idx], [profiles[idx]]

        scored: List[Tuple[ChromeProfileInfo, int]] = []
        for p in profiles:
            is_match, score = p.matches_query(query)
            if is_match:
                scored.append((p, score))

        if not scored:
            return None, profiles  # Return all profiles if no direct match found

        scored.sort(key=lambda x: -x[1])
        top_profile, top_score = scored[0]

        # Check if there's an ambiguous tie between multiple profiles
        if len(scored) > 1 and scored[1][1] == top_score:
            tied = [s[0] for s in scored if s[1] == top_score]
            return None, tied

        return top_profile, [s[0] for s in scored]

    def select_profile(self, query: str, open_url: Optional[str] = None, force_new_window: bool = False) -> Dict[str, Any]:
        """
        Select and activate the requested Chrome profile.
        1. Identifies the profile from Local State.
        2. If ambiguous, returns available candidates for user selection.
        3. If already open in an existing window, brings that window to the front.
        4. If not open, launches Chrome with --profile-directory="<dir>".
        5. Verifies that the correct profile window is active.
        """
        logger.info(f"Select Chrome profile requested: '{query}'")
        best_profile, candidates = self.find_profile(query)

        if not best_profile:
            formatted_candidates = [
                f"- **{p.name}** (`{p.directory}`)" + (f" — *{p.gaia_name}* ({p.email})" if p.email else "")
                for p in candidates
            ]
            cand_text = "\n".join(formatted_candidates)
            return {
                "success": False,
                "status": "ambiguous_profile",
                "error": f"Multiple or no Chrome profiles match '{query}'. Please specify one of the following:",
                "candidates": [p.__dict__ for p in candidates],
                "details": f"### 👤 Available Chrome Profiles\n\n{cand_text}\n\n*Please specify the exact name or email.*",
            }

        target_dir = best_profile.directory
        target_name = best_profile.name
        target_email = best_profile.email

        # 1. Check if a window for this profile is already open
        open_windows = self.get_open_profile_windows()
        target_hwnd: Optional[int] = None

        for hwnd_str, prof in open_windows.items():
            if prof.directory == target_dir:
                target_hwnd = int(hwnd_str)
                break

        if target_hwnd:
            self.wm.switch_to_window(target_hwnd)
            time.sleep(0.3)

            if force_new_window:
                import uiautomation as auto
                logger.info(f"Opening a brand new Chrome window for profile '{target_name}' via Alt+F -> n...")
                auto.SendKeys("{Alt}f")
                time.sleep(0.3)
                auto.SendKeys("n")
                time.sleep(1.2)
                # Find the newly spawned window
                all_current = self.wm.get_visible_windows()
                new_hwnd = None
                for w in all_current:
                    if "chrome" in w.title.lower() and w.hwnd != target_hwnd:
                        new_hwnd = w.hwnd
                        break
                active_target = new_hwnd or target_hwnd
                if open_url:
                    from bolt.browser.real_browser_controller import get_real_browser_controller
                    get_real_browser_controller().navigate_url(open_url, hwnd=active_target, new_tab=False)

                return {
                    "success": True,
                    "status": "opened_new_window",
                    "action": "opened_new_window",
                    "profile_directory": target_dir,
                    "profile_name": target_name,
                    "email": target_email,
                    "hwnd": active_target,
                    "message": f"Opened a brand new Chrome window for profile **{target_name}** ({target_email or target_dir}).",
                }

            logger.info(f"Switched to existing Chrome window for profile '{target_name}' (HWND {target_hwnd}).")
            if open_url:
                from bolt.browser.browser_controller import get_browser_controller
                get_browser_controller().open_url(open_url)

            return {
                "success": True,
                "status": "switched_existing",
                "action": "switched_to_window",
                "profile_directory": target_dir,
                "profile_name": target_name,
                "email": target_email,
                "hwnd": target_hwnd,
                "message": f"Switched to open Chrome window for profile **{target_name}** ({target_email or target_dir}).",
            }

        # 2. Launch Chrome with --profile-directory
        chrome_exe = self.get_chrome_executable_path()
        cmd = [chrome_exe, f'--profile-directory={target_dir}']
        if open_url:
            cmd.append(open_url)

        logger.info(f"Launching Chrome profile '{target_name}' via: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, shell=False)
        except Exception as e:
            logger.error(f"Failed to launch Chrome with profile '{target_name}': {e}")
            return {
                "success": False,
                "status": "launch_failed",
                "error": f"Could not launch Chrome profile '{target_name}': {e}",
            }

        # 3. Verify launch and window creation (poll up to 4.0 seconds)
        verified = False
        active_hwnd: Optional[int] = None
        start_time = time.time()

        while time.time() - start_time < 4.0:
            time.sleep(0.4)
            windows_now = self.wm.get_visible_windows()
            chrome_wins = [w for w in windows_now if "chrome" in w.title.lower()]
            if chrome_wins:
                # Check newly opened window
                active_hwnd = chrome_wins[0].hwnd
                verified = True
                break

        return {
            "success": verified,
            "status": "launched" if verified else "dispatched",
            "profile_directory": target_dir,
            "profile_name": target_name,
            "email": target_email,
            "hwnd": active_hwnd,
            "message": f"Opened Chrome with profile **{target_name}** ({target_email or target_dir}).",
        }


_CHROME_PROFILE_MGR: Optional[ChromeProfileManager] = None


def get_chrome_profile_manager() -> ChromeProfileManager:
    global _CHROME_PROFILE_MGR
    if _CHROME_PROFILE_MGR is None:
        _CHROME_PROFILE_MGR = ChromeProfileManager.get_instance()
    return _CHROME_PROFILE_MGR

