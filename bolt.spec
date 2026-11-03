# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for BOLT Personal Autonomous AI Assistant.
Packages BOLT as a standalone Windows 11 desktop application.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Base directory
BASE_DIR = Path.cwd()

# Data files to bundle with distribution
datas = [
    ('assets', 'assets'),
    ('.env.example', '.'),
]

# Hidden imports to ensure dynamic modules are packaged
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtNetwork',
    'sqlite3',
    'sounddevice',
    'vosk',
    'pyttsx3',
    'comtypes',
    'uiautomation',
    'winocr',
    'psutil',
    'requests',
    'dotenv',
    'pydantic',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'bolt',
    'bolt.__version__',
    'bolt.config.constants',
    'bolt.config.settings',
    'bolt.core.data_manager',
    'bolt.core.database',
    'bolt.core.logger',
    'bolt.core.network_manager',
    'bolt.ai.runtime_manager',
    'bolt.ai.local_brain',
    'bolt.ai.provider_gemini',
    'bolt.ai.provider_openai',
    'bolt.ai.provider_router',
    'bolt.browser.controller',
    'bolt.computer_control.direct_tools',
    'bolt.computer_control.ui_automation',
    'bolt.computer_control.controller',
    'bolt.voice.speech_recognition',
    'bolt.voice.speech_synthesis',
    'bolt.voice.voice_coordinator',
    'bolt.memory.database',
    'bolt.memory.memory_manager',
    'bolt.security.risk_engine',
    'bolt.security.permission_manager',
    'bolt.planner.task_planner',
    'bolt.ui.main_window',
    'bolt.ui.setup_wizard',
    'bolt.ui.settings_dialog',
    'bolt.ui.system_tray',
    'bolt.ui.styles.theme',
]

a = Analysis(
    ['run.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BOLT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon='assets/bolt_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BOLT',
)

