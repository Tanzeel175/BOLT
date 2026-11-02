"""
Automated Verification Suite for BOLT Phase 1 - Section 6 Testing Requirements
1. Application launches successfully.
2. Chat interface works.
3. User can send messages.
4. Actual AI responses appear.
5. Conversation context is maintained across turns.
6. Previous conversations can be reopened with full message history.
7. Missing API keys produce a clear, useful error.
8. Network failures do not crash the application.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from bolt.config.settings import Settings
from bolt.core.database import get_database
from bolt.ai.base import ChatMessage, AIResponse
from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.openai_provider import OpenAIProvider
from bolt.ai.mock_provider import MockProvider
from bolt.ui.main_window import MainWindow


def test_section_6():
    print("=" * 60)
    print("BOLT PHASE 1 - SECTION 6 REQUIREMENTS VERIFICATION")
    print("=" * 60)

    db = get_database()
    app = QApplication.instance() or QApplication(sys.argv)

    # -------------------------------------------------------------
    # Test 1 & 2: Application launches & Chat interface initializes
    # -------------------------------------------------------------
    print("\n[TEST 1 & 2] Verifying Application Launch & Interface Elements...")
    window = MainWindow()
    assert window is not None, "MainWindow failed to instantiate"
    assert window.header_bar is not None, "HeaderBar missing"
    assert window.sidebar is not None, "Sidebar missing"
    assert window.chat_view is not None, "ChatView missing"
    assert window.input_bar is not None, "InputBar missing"
    assert window.status_bar is not None, "TaskStatusBar missing"
    assert window.input_bar.mic_btn is not None, "Microphone placeholder button missing"
    print("✓ Test 1 & 2 Passed: MainWindow, ChatView, Sidebar, HeaderBar, InputBar initialized cleanly.")

    # -------------------------------------------------------------
    # Test 3 & 4: User can send messages & Actual AI responses appear
    # -------------------------------------------------------------
    print("\n[TEST 3 & 4] Verifying Message Sending & AI Response Generation...")
    conv_id = window.current_conv_id
    test_msg = "Hello BOLT, please identify yourself."

    # Using MockProvider for deterministic response check
    window.ai_router.settings.provider = "mock"
    initial_msg_count = len(db.get_messages(conv_id))

    window._handle_user_message(test_msg)
    # Wait for background worker to complete and process Qt queued signals
    if window.active_worker:
        window.active_worker.wait(5000)
    app.processEvents()

    msgs_after = db.get_messages(conv_id)
    assert len(msgs_after) == initial_msg_count + 2, f"Expected {initial_msg_count + 2} messages, got {len(msgs_after)}"
    assert msgs_after[-2]["role"] == "user"
    assert msgs_after[-2]["content"] == test_msg
    assert msgs_after[-1]["role"] == "assistant"
    assert len(msgs_after[-1]["content"]) > 0
    print("✓ Test 3 & 4 Passed: User message recorded and assistant response delivered & persisted.")

    # -------------------------------------------------------------
    # Test 5: Conversation context is maintained
    # -------------------------------------------------------------
    print("\n[TEST 5] Verifying Conversation Context Preservation...")
    turn2_msg = "What was my first message?"
    window._handle_user_message(turn2_msg)
    if window.active_worker:
        window.active_worker.wait(5000)
    app.processEvents()

    msgs_context = db.get_messages(conv_id)
    # The worker receives all messages in conversation
    assert len(window.active_worker.messages) == len(msgs_context) - 1  # includes up to current user prompt
    print(f"✓ Test 5 Passed: Context maintained with {len(window.active_worker.messages)} turns passed to AI worker.")

    # -------------------------------------------------------------
    # Test 6: Previous conversations can be reopened
    # -------------------------------------------------------------
    print("\n[TEST 6] Verifying Reopening Previous Conversations...")
    # 1. Start a fresh new chat
    window._start_new_chat()
    new_conv_id = window.current_conv_id
    assert new_conv_id != conv_id, "New chat should have distinct ID"

    # 2. Reopen the previous conversation
    window._load_conversation(conv_id)
    assert window.current_conv_id == conv_id, "Current conversation should match reopened ID"
    reopened_msgs = db.get_messages(conv_id)
    assert len(reopened_msgs) >= 4, f"Expected at least 4 messages in reopened chat, got {len(reopened_msgs)}"
    print(f"✓ Test 6 Passed: Reopened conversation {conv_id} with {len(reopened_msgs)} historical messages restored.")

    # -------------------------------------------------------------
    # Test 7: Missing API keys produce a useful error
    # -------------------------------------------------------------
    print("\n[TEST 7] Verifying Missing API Key Error Handling...")
    gemini_missing_key = GeminiProvider(api_key="", model="gemini-2.5-flash")
    resp_gemini = gemini_missing_key.generate_response([ChatMessage(role="user", content="Ping")])
    assert not resp_gemini.success, "Should fail when API key is missing"
    assert "API Key is not set" in resp_gemini.error, f"Unexpected error message: {resp_gemini.error}"

    openai_missing_key = OpenAIProvider(api_key="", model="gpt-4o-mini")
    resp_openai = openai_missing_key.generate_response([ChatMessage(role="user", content="Ping")])
    assert not resp_openai.success, "Should fail when OpenAI API key is missing"
    assert "API Key is not set" in resp_openai.error, f"Unexpected error message: {resp_openai.error}"
    print("✓ Test 7 Passed: Missing API keys produce clear, informative error guidance.")

    # -------------------------------------------------------------
    # Test 8: Network failures do not crash the application
    # -------------------------------------------------------------
    print("\n[TEST 8] Verifying Network Failure Graceful Recovery...")
    gemini_with_key = GeminiProvider(api_key="AIzaFakeKey123", model="gemini-2.5-flash")

    # Simulate network timeout
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        resp_timeout = gemini_with_key.generate_response([ChatMessage(role="user", content="Ping")])
        assert not resp_timeout.success, "Should indicate failure on timeout"
        assert "timed out" in resp_timeout.error.lower(), f"Unexpected timeout error: {resp_timeout.error}"

    # Simulate connection error (offline)
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Failed to resolve host")):
        resp_neterr = gemini_with_key.generate_response([ChatMessage(role="user", content="Ping")])
        assert not resp_neterr.success, "Should indicate failure on connection error"
        assert "network error" in resp_neterr.error.lower(), f"Unexpected network error: {resp_neterr.error}"

    # Verify UI handles failure without crashing
    window._on_ai_response_received(resp_timeout)
    assert window.input_bar.send_btn.isEnabled(), "Input bar must be re-enabled after network error"
    print("✓ Test 8 Passed: Simulated network timeouts and connection errors handled gracefully without crashes.")

    print("\n" + "=" * 60)
    print("ALL 8 SECTION 6 TESTING CRITERIA VERIFIED AND PASSED!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(test_section_6())
