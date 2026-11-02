"""
End-to-End UI Integration Test for BOLT Phase 3:
Browser and Website Intelligence inside MainWindow.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from bolt.ui.main_window import MainWindow
from bolt.core.database import get_database


def test_phase3_ui_e2e():
    app = QApplication.instance() or QApplication(sys.argv)
    db = get_database()
    window = MainWindow()

    print("--- Starting Phase 3 UI E2E Verification ---")
    conv_id = window.current_conv_id
    print(f"Active Conversation ID: {conv_id}")

    # 1. Test "Open ChatGPT"
    print("Simulating User Input 1: 'Open ChatGPT'")
    window._handle_user_message("Open ChatGPT")
    msgs = db.get_messages(conv_id)
    latest_msg = msgs[-1]
    print(f"Action 1 Result Model: {latest_msg['model']}")
    assert latest_msg["model"] == "BOLT Browser Intelligence", "Expected BOLT Browser Intelligence attribution"
    assert "ChatGPT" in latest_msg["content"] or "chatgpt.com" in latest_msg["content"]
    print("[PASS] User Input 1 successfully executed and rendered in chat.")

    # 2. Test "Search for the latest Python AI libraries"
    print("Simulating User Input 2: 'Search for the latest Python AI libraries'")
    window._handle_user_message("Search for the latest Python AI libraries")
    msgs2 = db.get_messages(conv_id)
    latest_search = msgs2[-1]
    assert latest_search["model"] == "BOLT Browser Intelligence"
    assert "Search Results" in latest_search["content"]
    print("[PASS] User Input 2 (Live Search) executed and persisted in SQLite.")

    # 3. Test "Open YouTube and search for C++ tutorials"
    print("Simulating User Input 3: 'Open YouTube and search for C++ tutorials'")
    window._handle_user_message("Open YouTube and search for C++ tutorials")
    msgs3 = db.get_messages(conv_id)
    latest_yt = msgs3[-1]
    assert "youtube" in latest_yt["content"].lower()
    print("[PASS] User Input 3 (YouTube Provider Search) executed.")

    # 4. Test "Read the current webpage and summarize it"
    print("Simulating User Input 4: 'Read the current webpage and summarize it'")
    window._handle_user_message("Read the current webpage and summarize it")
    msgs4 = db.get_messages(conv_id)
    latest_summary = msgs4[-1]
    assert "Webpage Summary" in latest_summary["content"]
    print("[PASS] User Input 4 (Webpage Reader) executed.")

    print("\n=== Phase 3 UI E2E Verification: ALL CRITERIA MET AND PASSED ===")


if __name__ == "__main__":
    test_phase3_ui_e2e()
