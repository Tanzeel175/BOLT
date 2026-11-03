"""
BOLT - Build Executable Script
Packages BOLT into a standalone Windows 11 executable using PyInstaller and bolt.spec.
"""

import os
import subprocess
import sys
from pathlib import Path


def build():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("=" * 60)
    print("BOLT Windows Desktop Packaging & Build Utility")
    print(f"Working Directory: {root_dir}")
    print("=" * 60)

    spec_file = root_dir / "bolt.spec"
    if not spec_file.exists():
        print(f"Error: {spec_file} not found!", file=sys.stderr)
        sys.exit(1)

    # Use virtual environment PyInstaller if available
    python_exe = sys.executable
    venv_pyinstaller = Path(python_exe).parent / "pyinstaller.exe"
    if venv_pyinstaller.exists():
        pyinstaller_cmd = [str(venv_pyinstaller)]
    else:
        pyinstaller_cmd = [python_exe, "-m", "PyInstaller"]

    cmd = pyinstaller_cmd + ["--noconfirm", "--clean", str(spec_file)]

    print(f"Executing: {' '.join(cmd)}\n")
    try:
        proc = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] PyInstaller build failed with exit code: {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode)

    exe_path = root_dir / "dist" / "BOLT" / "BOLT.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Target Binary: {exe_path}")
        print(f"Executable Size: {size_mb:.2f} MB")
        print("=" * 60)
        print("To launch: double-click dist\\BOLT\\BOLT.exe or run.bat")
        print("To create shortcuts: powershell -ExecutionPolicy Bypass -File scripts\\create_shortcut.ps1")
    else:
        print(f"\n[FAIL] Build finished but {exe_path} was not created.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    build()
