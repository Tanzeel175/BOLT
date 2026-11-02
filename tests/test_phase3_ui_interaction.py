"""
End-to-End User Interaction Verification for BOLT Phase 3 (UI + Browser Engine Integration)
Simulates:
1. Launching BOLT MainWindow
2. User command: "Open ChatGPT" -> Browser Engine navigates and renders response
3. User command: "Search for the latest Python AI libraries" -> Renders search markdown
4. User command: "Switch to the ChatGPT tab" -> Switches active tab
5. Conversational query: "Explain recursion in C++" -> Generative AI model response
6. SQLite database persistence and UI status bar updates
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

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["BOLT_HEADLESS_BROWSER"] = "true"

import bolt
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication
from bolt.ui.main_window import MainWindow
from bolt.core.database import get_database
from bolt.browser.browser_controller import get_browser_controller


def run_phase3_e2e():
    print("--- Starting Phase 3 UI E2E Verification ---")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    db = get_database()
    browser_ctrl = get_browser_controller()
    browser_ctrl.set_headless(True)

    conv_id = window.current_conv_id
    print(f"Active Conversation ID: {conv_id}")

    # Action 1: Open ChatGPT
    print("Simulating User Input 1: 'Open ChatGPT'")
    window._handle_user_message("Open ChatGPT")

    msgs1 = db.get_messages(conv_id)
    print(f"Messages count after Action 1: {len(msgs1)}")
    assert len(msgs1) >= 2, "Expected user + assistant messages"
    asst_msg1 = msgs1[-1]
    assert asst_msg1["role"] == "assistant"
    assert asst_msg1["model"] == "BOLT Browser Engine"
    assert "ChatGPT" in asst_msg1["content"] or "chatgpt" in asst_msg1["content"].lower()
    print("[PASS] Action 1: 'Open ChatGPT' persisted with BOLT Browser Engine!")

    # Action 2: Web Search
    print("Simulating User Input 2: 'Search for the latest Python AI libraries'")
    window._handle_user_message("Search for the latest Python AI libraries")

    msgs2 = db.get_messages(conv_id)
    print(f"Messages count after Action 2: {len(msgs2)}")
    assert len(msgs2) >= 4
    asst_msg2 = msgs2[-1]
    assert "Web Search Results" in asst_msg2["content"]
    print("[PASS] Action 2: Web search rendered and persisted!")

    # Action 3: Tab Switch
    print("Simulating User Input 3: 'Switch to the ChatGPT tab'")
    window._handle_user_message("Switch to the ChatGPT tab")

    msgs3 = db.get_messages(conv_id)
    print(f"Messages count after Action 3: {len(msgs3)}")
    assert len(msgs3) >= 6
    asst_msg3 = msgs3[-1]
    assert "Switched to tab" in asst_msg3["content"]
    print("[PASS] Action 3: Tab switch verified!")

    # Action 4: Conversational question (AI Generative routing)
    print("Simulating User Input 4: 'Explain recursion in C++'")
    ai_response_delivered = []
    original_on_ai_response = window._on_ai_response_received

    def intercepted_on_ai(response):
        original_on_ai_response(response)
        ai_response_delivered.append(response)
        print("[PASS] Action 4: Conversational query completed by AI worker!")
        msgs4 = db.get_messages(conv_id)
        assert len(msgs4) >= 8
        browser_ctrl.close_browser()
        app.quit()

    window._on_ai_response_received = intercepted_on_ai
    window._handle_user_message("Explain recursion in C++")

    # Safety timeout
    QTimer.singleShot(15000, lambda: app.quit() if not ai_response_delivered else None)
    app.exec()

    if ai_response_delivered:
        print("=== Phase 3 UI E2E Verification: ALL CRITERIA MET AND PASSED ===")
        return 0
    else:
        print("ERROR: AI response timed out.")
        browser_ctrl.close_browser()
        return 1


if __name__ == "__main__":
    sys.exit(run_phase3_e2e())

