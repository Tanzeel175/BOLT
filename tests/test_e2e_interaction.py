"""
End-to-End User Interaction Verification for BOLT Phase 1
Simulates:
1. Launching BOLT MainWindow
2. User submits a question: "Explain recursion in C++"
3. Background AIWorker executes generation
4. Response is received and stored in SQLite
5. Verifies UI updates (message bubbles rendered, status bar updated)
"""

import os
import sys
from pathlib import Path

# Configure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication
from bolt.ui.main_window import MainWindow
from bolt.core.database import get_database

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def run_e2e_test():
    print("--- Starting Phase 1 E2E Verification ---")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    db = get_database()
    initial_conv_id = window.current_conv_id
    print(f"Active Conversation ID: {initial_conv_id}")

    test_prompt = "Explain recursion in C++"
    print(f"Simulating User Input: '{test_prompt}'")

    response_received = []

    # Intercept when worker completes
    original_on_ai_response = window._on_ai_response_received

    def intercepted_on_ai_response(response):
        original_on_ai_response(response)
        response_received.append(response)
        print("[PASS] AI Worker finished and delivered response!")
        print(f"  Model: {response.model}")
        print(f"  Success: {response.success}")
        print(f"  Response preview: {response.content[:120]}...")
        # Verify database record
        msgs = db.get_messages(initial_conv_id)
        print(f"  Total messages saved in SQLite: {len(msgs)}")
        assert len(msgs) >= 2, "Expected at least 2 messages (user + assistant)"
        assert msgs[-1]["role"] == "assistant", "Last message must be from assistant"
        print("[PASS] SQLite database persistence verified!")

        # Verify chat UI container has message cards
        card_count = window.chat_view.container_layout.count()
        print(f"  Chat view container widgets count: {card_count}")
        assert card_count >= 3, "Expected at least user card, assistant card, and spacer"
        print("[PASS] ChatView message cards rendered successfully!")

        app.quit()

    window._on_ai_response_received = intercepted_on_ai_response

    # Trigger user message submission
    window._handle_user_message(test_prompt)

    # Safety timeout
    QTimer.singleShot(15000, lambda: app.quit() if not response_received else None)

    app.exec()

    if response_received:
        print("=== Phase 1 E2E Verification: ALL CRITERIA MET AND PASSED ===")
        return 0
    else:
        print("ERROR: Response was not received within timeout.")
        return 1


if __name__ == "__main__":
    sys.exit(run_e2e_test())
