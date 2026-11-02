"""
End-to-End User Interaction Verification for BOLT Phase 2 (UI + Windows Intent Integration)
Simulates:
1. Launching BOLT MainWindow
2. User submits a Windows command: "Open Notepad"
3. MainWindow intercepts via WindowsIntentDispatcher
4. Application is launched & verified
5. Response message is rendered in UI and saved in SQLite
6. User asks for system specs: "What are my system specs?"
7. Verifies system diagnostic markdown rendering in chat
"""

import os
import sys
import time
from pathlib import Path

# Configure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication
from bolt.ui.main_window import MainWindow
from bolt.core.database import get_database
from bolt.windows.app_controller import get_app_controller

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def run_phase2_e2e():
    print("--- Starting Phase 2 UI E2E Verification ---")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    db = get_database()
    controller = get_app_controller()

    conv_id = window.current_conv_id
    print(f"Active Conversation ID: {conv_id}")

    # Step 1: Simulate "Open Notepad"
    print("Simulating User Input 1: 'Open Notepad'")
    window._handle_user_message("Open Notepad")

    # Verify message persisted in SQLite
    msgs = db.get_messages(conv_id)
    print(f"Total messages saved after action 1: {len(msgs)}")
    assert len(msgs) >= 2, "Expected at least 2 messages (user + assistant)"
    user_msg = msgs[-2]
    asst_msg = msgs[-1]
    assert user_msg["role"] == "user" and "Open Notepad" in user_msg["content"]
    assert asst_msg["role"] == "assistant"
    print(f"[PASS] Action 1 persisted: {asst_msg['content'][:60]}...")

    # Verify Notepad is running
    is_running, pids = controller.is_app_running("notepad")
    print(f"Notepad running check: {is_running}, PIDs: {pids}")
    assert is_running, "Notepad should be confirmed running"

    # Step 2: Simulate "What are my system specs?"
    print("Simulating User Input 2: 'What are my system specs?'")
    window._handle_user_message("What are my system specs?")

    msgs2 = db.get_messages(conv_id)
    print(f"Total messages saved after action 2: {len(msgs2)}")
    assert len(msgs2) >= 4, "Expected 4 messages after 2 commands"
    sys_asst_msg = msgs2[-1]
    assert "Windows 11 System Diagnostics" in sys_asst_msg["content"]
    print(f"[PASS] Action 2 persisted: System Diagnostics rendered!")

    # Step 3: Clean up Notepad
    close_res = controller.close_application("notepad")
    print(f"Cleaned up Notepad: {close_res['success']}")

    print("=== Phase 2 UI E2E Verification: ALL CRITERIA MET AND PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(run_phase2_e2e())

