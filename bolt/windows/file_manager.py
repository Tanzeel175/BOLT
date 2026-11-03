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
    "workspace": lambda: FileManager.get_workspace_path(),
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
    def get_workspace_path() -> pathlib.Path:
        """Resolve workspace directory from memory preferences or constants."""
        try:
            from bolt.memory.manager import get_memory_manager
            mem = get_memory_manager()
            saved_ws = mem.get_user_preference("workspace_location") or mem.get_user_preference("workspace_folder")
            if saved_ws and pathlib.Path(saved_ws).exists():
                return pathlib.Path(saved_ws)
        except Exception:
            pass
        from bolt.config.constants import WORKSPACE_DIR
        return WORKSPACE_DIR

    @staticmethod
    def get_recent_files(
        folder_alias: str = "downloads",
        extension: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Locate the most recently created or modified files in a target directory.
        Allows instructions like: 'Open my downloads folder and find the most recent PDF'.
        """
        folder_path = FileManager.resolve_folder_alias(folder_alias)
        if not folder_path or not folder_path.exists():
            folder_path = pathlib.Path.home() / "Downloads"

        if not folder_path.exists():
            return []

        matched = []
        ext_clean = extension.lower().strip() if extension else ""
        if ext_clean and not ext_clean.startswith("."):
            ext_clean = f".{ext_clean}"

        try:
            for item in folder_path.iterdir():
                try:
                    if item.is_file():
                        if ext_clean and item.suffix.lower() != ext_clean:
                            continue
                        stat = item.stat()
                        matched.append({
                            "name": item.name,
                            "path": str(item.resolve()),
                            "size_kb": round(stat.st_size / 1024, 1),
                            "modified_at": stat.st_mtime,
                            "extension": item.suffix.lower(),
                        })
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            logger.warning(f"Error enumerating recent files in '{folder_path}': {e}")
            return []

        matched.sort(key=lambda x: x["modified_at"], reverse=True)
        return matched[:limit]

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

    @staticmethod
    def create_text_file(
        file_path_or_name: str,
        content: str = "",
        folder_alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new text file at the specified location or within a resolved folder.
        Default location is user Desktop if only a filename is passed.
        """
        clean_path = file_path_or_name.strip().strip("'\"")
        p = pathlib.Path(clean_path)

        # If it's just a file name (no directory separators), put on Desktop or specified alias
        if not p.is_absolute() and len(p.parts) == 1:
            target_folder = FileManager.resolve_folder_alias(folder_alias or "desktop") or pathlib.Path.home()
            target_path = target_folder / clean_path
        else:
            target_path = p.expanduser().resolve()

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            logger.info(f"Created text file at: {target_path}")
            return {
                "success": True,
                "file_path": str(target_path),
                "file_name": target_path.name,
                "bytes_written": len(content.encode("utf-8")),
                "message": f"Successfully created file `{target_path.name}` at `{target_path.parent}`.",
            }
        except Exception as e:
            logger.error(f"Failed to create text file '{file_path_or_name}': {e}")
            return {
                "success": False,
                "error": f"Failed to create file: {e}",
                "file_path": str(target_path),
            }

    @staticmethod
    def read_text_file(file_path: str) -> Dict[str, Any]:
        """Read and return content of a text file."""
        clean_path = file_path.strip().strip("'\"")
        p = pathlib.Path(clean_path)
        if not p.is_absolute() and len(p.parts) == 1:
            desktop = FileManager.resolve_folder_alias("desktop")
            if desktop and (desktop / clean_path).exists():
                p = desktop / clean_path
            else:
                p = p.expanduser().resolve()
        else:
            p = p.expanduser().resolve()

        if not p.exists():
            return {"success": False, "error": f"File does not exist: {p}"}

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "file_path": str(p),
                "file_name": p.name,
                "content": text,
                "size_chars": len(text),
                "message": f"Read {len(text)} characters from `{p.name}`.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed reading file: {e}"}

    @staticmethod
    def write_text_file(
        file_path: str,
        content: str,
        allow_overwrite: bool = True,
        folder_alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write content to text file, with optional overwrite protection and destination folder alias."""
        clean_path = file_path.strip().strip("'\"")
        p = pathlib.Path(clean_path)
        if not p.is_absolute() and len(p.parts) == 1:
            target_folder = FileManager.resolve_folder_alias(folder_alias or "desktop")
            if target_folder:
                target_folder.mkdir(parents=True, exist_ok=True)
                p = target_folder / clean_path
            else:
                p = p.expanduser().resolve()
        else:
            p = p.expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)

        if p.exists() and not allow_overwrite:
            stem = p.stem
            ext = p.suffix
            counter = 1
            while (p.parent / f"{stem}_{counter}{ext}").exists():
                counter += 1
            p = p.parent / f"{stem}_{counter}{ext}"

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(p),
                "file_name": p.name,
                "bytes_written": len(content.encode("utf-8")),
                "message": f"Successfully written to `{p.name}`.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed writing file: {e}"}

    @staticmethod
    def delete_file(file_path: str) -> Dict[str, Any]:
        """Safely delete a file with existence verification and protected path checks."""
        clean_path = file_path.strip().strip("'\"")
        p = pathlib.Path(clean_path)
        if not p.is_absolute() and len(p.parts) == 1:
            desktop = FileManager.resolve_folder_alias("desktop")
            if desktop and (desktop / clean_path).exists():
                p = desktop / clean_path
            else:
                p = p.expanduser().resolve()
        else:
            p = p.expanduser().resolve()

        if not p.exists():
            return {"success": False, "error": f"File does not exist: {p}"}
        if p.is_dir():
            return {"success": False, "error": f"Target path '{p}' is a directory, not a file. Use delete_directory."}

        # Guard against system directories
        sys_drive = os.environ.get("SystemDrive", "C:").lower()
        p_str = str(p).lower()
        if p_str in (f"{sys_drive}\\", f"{sys_drive}/", f"{sys_drive}") or "windows" in p_str.split(os.sep):
            return {"success": False, "error": f"Cannot delete protected system file: {p}"}

        try:
            file_name = p.name
            size_bytes = p.stat().st_size
            p.unlink()
            logger.info(f"Deleted file: {p}")
            return {
                "success": True,
                "file_path": str(p),
                "file_name": file_name,
                "bytes_freed": size_bytes,
                "message": f"Successfully deleted file `{file_name}` ({size_bytes} bytes).",
            }
        except Exception as e:
            logger.error(f"Failed deleting file '{file_path}': {e}")
            return {"success": False, "error": f"Failed deleting file: {e}"}

    @staticmethod
    def delete_directory(dir_path: str) -> Dict[str, Any]:
        """Safely delete a directory and its contents with critical guardrails."""
        import shutil
        clean_path = dir_path.strip().strip("'\"")
        resolved = FileManager.resolve_folder_alias(clean_path)
        p = (resolved or pathlib.Path(clean_path)).expanduser().resolve()

        if not p.exists():
            return {"success": False, "error": f"Directory does not exist: {p}"}
        if not p.is_dir():
            return {"success": False, "error": f"Target path '{p}' is not a directory."}

        # Guard against root/userprofile/windows directories
        sys_drive = os.environ.get("SystemDrive", "C:").lower()
        user_prof = os.environ.get("USERPROFILE", "").lower()
        p_str = str(p).lower()

        if p_str in (f"{sys_drive}\\", f"{sys_drive}/", f"{sys_drive}", user_prof):
            return {"success": False, "error": f"Refusing to delete critical root/user home directory: {p}"}
        if "windows" in p_str.split(os.sep) or "program files" in p_str.split(os.sep):
            return {"success": False, "error": f"Refusing to delete Windows system directory: {p}"}

        try:
            shutil.rmtree(p)
            logger.info(f"Deleted directory: {p}")
            return {
                "success": True,
                "directory_path": str(p),
                "directory_name": p.name,
                "message": f"Successfully deleted directory `{p.name}` and all contents.",
            }
        except Exception as e:
            logger.error(f"Failed deleting directory '{dir_path}': {e}")
            return {"success": False, "error": f"Failed deleting directory: {e}"}


_FILE_MGR_INSTANCE: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    global _FILE_MGR_INSTANCE
    if _FILE_MGR_INSTANCE is None:
        _FILE_MGR_INSTANCE = FileManager()
    return _FILE_MGR_INSTANCE

