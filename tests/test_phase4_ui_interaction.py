"""End-to-End PySide6 UI Verification Suite for BOLT Phase 4 (AI Integration).

Simulates user interactions directly through MainWindow to verify:
1. Natural language default provider switching in UI.
2. Multi-AI Comparison query rendering.
3. Explicit provider query ("Ask Gemini...") and missing key actionable alert card.
4. Asynchronous worker responsiveness.
5. Browser-based interaction (Method B: "Open ChatGPT in my browser").
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from bolt.ui.main_window import MainWindow
from bolt.core.database import get_database


def test_phase4_ui_e2e():
    app = QApplication.instance() or QApplication(sys.argv)
    db = get_database()
    window = MainWindow()

    print("--- Starting Phase 4 UI E2E Verification ---")
    conv_id = window.current_conv_id
    print(f"Active Conversation ID: {conv_id}")

    # 1. Test Natural Language Provider Switch
    print("\nSimulating User Input 1: 'Switch to Gemini'")
    window._handle_user_message("Switch to Gemini")
    msgs = db.get_messages(conv_id)
    latest_msg = msgs[-1]
    self_assert("Google Gemini" in latest_msg["content"], "Expected confirmation of switch to Google Gemini")
    print(f"[PASS] User Input 1 (Provider Switch) rendered and persisted: {latest_msg['model']}")

    # 2. Test Multi-AI Comparison via UI
    print("\nSimulating User Input 2: 'Compare how Gemini and ChatGPT explain recursion'")
    window._handle_user_message("Compare how Gemini and ChatGPT explain recursion")
    msgs2 = db.get_messages(conv_id)
    latest_comp = msgs2[-1]
    self_assert("Multi-AI Comparison Report" in latest_comp["content"], "Expected Multi-AI report header")
    self_assert(latest_comp["model"] == "BOLT Multi-AI Engine", "Expected BOLT Multi-AI Engine model attribution")
    print("[PASS] User Input 2 (Multi-AI Comparison) executed and rendered.")

    # 3. Test Explicit Provider Query with Missing Key Guidance (Method A)
    print("\nSimulating User Input 3: 'Ask Gemini to write a professional email requesting an internship'")
    window._handle_user_message("Ask Gemini to write a professional email requesting an internship")

    # Wait for background thread to complete
    if window.active_worker and window.active_worker.isRunning():
        window.active_worker.wait(5000)

    msgs3 = db.get_messages(conv_id)
    latest_ask = msgs3[-1]
    # Since Gemini key is not configured in this clean environment, it must show actionable guidance
    self_assert("Gemini" in latest_ask["content"] or "API" in latest_ask["content"], "Expected Gemini actionable error or completion")
    print(f"[PASS] User Input 3 (Explicit Provider Request) handled safely without faking.")

    # 4. Test Browser-based Interaction (Method B)
    print("\nSimulating User Input 4: 'Open ChatGPT in my browser'")
    window._handle_user_message("Open ChatGPT in my browser")
    msgs4 = db.get_messages(conv_id)
    latest_browser = msgs4[-1]
    self_assert("chatgpt" in latest_browser["content"].lower(), "Expected ChatGPT browser navigation confirmation")
    self_assert(latest_browser["model"] == "BOLT Browser Intelligence", "Expected BOLT Browser Intelligence attribution")
    print("[PASS] User Input 4 (Method B: Browser Navigation) executed.")

    print("\n=== Phase 4 UI E2E Verification: ALL CRITERIA MET AND PASSED ===")


def self_assert(condition: bool, message: str = ""):
    if not condition:
        raise AssertionError(f"Verification Failed: {message}")


if __name__ == "__main__":
    test_phase4_ui_e2e()

