"""
Windows File and Directory Management subsystem for BOLT.
Handles opening files, opening folders, searching files, and resolving common Windows paths.
"""

import os
import pathlib
from typing import Any, Dict, List, Optional
from bolt.core.logger import get_logger

logger = get_logger("FileManager")

# Canonical Windows User Directories
COMMON_WINDOWS_FOLDERS = {
    "desktop": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Desktop",
    "documents": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Documents",
    "downloads": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Downloads",
    "pictures": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Pictures",
    "music": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Music",
    "videos": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")) / "Videos",
    "userprofile": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")),
    "home": lambda: pathlib.Path(os.environ.get("USERPROFILE", "")),
    "temp": lambda: pathlib.Path(os.environ.get("TEMP", r"C:\Windows\Temp")),
    "program files": lambda: pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    "windows": lambda: pathlib.Path(os.environ.get("SystemRoot", r"C:\Windows")),
}


class FileManager:
    """Manages file searches, folder navigation, and file execution on Windows."""

    @staticmethod
    def resolve_folder_alias(folder_name: str) -> Optional[pathlib.Path]:
        """Resolve natural language folder aliases (e.g., 'downloads', 'my documents', 'desktop')."""
        clean = folder_name.lower().replace("my ", "").replace("folder", "").strip()

        # Handle OneDrive Desktop redirect if applicable
        if clean == "desktop" and "USERPROFILE" in os.environ:
            od_desktop = pathlib.Path(os.environ["USERPROFILE"]) / "OneDrive" / "Desktop"
            if od_desktop.exists():
                return od_desktop

        resolver = COMMON_WINDOWS_FOLDERS.get(clean)
        if resolver:
            path = resolver()
            if path.exists():
                return path

        # Try raw path
        p = pathlib.Path(folder_name)
        if p.exists() and p.is_dir():
            return p

        return None

    @staticmethod
    def open_item(path_str: str) -> Dict[str, Any]:
        """Open a file or directory using Windows shell default application association."""
        # 1. Check if it's a known folder alias
        resolved = FileManager.resolve_folder_alias(path_str)
        target_path = resolved or pathlib.Path(os.path.expandvars(path_str))

        if not target_path.exists():
            return {
                "success": False,
                "error": f"Path '{path_str}' does not exist on disk.",
                "path": str(target_path),
            }

        try:
            os.startfile(str(target_path))
            item_type = "Folder" if target_path.is_dir() else "File"
            logger.info(f"Opened {item_type}: {target_path}")
            return {
                "success": True,
                "item_type": item_type,
                "path": str(target_path),
                "message": f"Successfully opened {item_type.lower()}: `{target_path.name}`",
            }
        except Exception as e:
            logger.error(f"Failed to open '{path_str}': {e}")
            return {
                "success": False,
                "error": f"Failed to open '{path_str}': {e}",
                "path": str(target_path),
            }

    @staticmethod
    def search_files(
        query: str,
        start_dir: Optional[str] = None,
        max_results: int = 15,
        max_depth: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Search for files matching query within directory tree up to max_depth.
        Default start directory is user Desktop or UserProfile.
        """
        if start_dir:
            base_dir = FileManager.resolve_folder_alias(start_dir) or pathlib.Path(start_dir)
        else:
            base_dir = FileManager.resolve_folder_alias("desktop") or pathlib.Path.home()

        if not base_dir.exists():
            return []

        q_lower = query.lower()
        results = []

        try:
            for root, dirs, files in os.walk(base_dir):
                # Depth limit check
                rel_path = pathlib.Path(root).relative_to(base_dir)
                if len(rel_path.parts) >= max_depth:
                    dirs.clear()  # Don't recurse deeper
                    continue

                for f in files:
                    if q_lower in f.lower():
                        full_p = pathlib.Path(root) / f
                        try:
                            size_kb = round(full_p.stat().st_size / 1024, 1)
                        except Exception:
                            size_kb = 0

                        results.append({
                            "name": f,
                            "path": str(full_p),
                            "size_kb": size_kb,
                            "parent": root,
                        })
                        if len(results) >= max_results:
                            return results
        except Exception as e:
            logger.warning(f"Error during file search: {e}")

        return results


_FILE_MGR_INSTANCE: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    global _FILE_MGR_INSTANCE
    if _FILE_MGR_INSTANCE is None:
        _FILE_MGR_INSTANCE = FileManager()
    return _FILE_MGR_INSTANCE

