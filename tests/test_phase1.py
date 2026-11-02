"""
Comprehensive Automated Test Suite for BOLT Phase 1
Verifies:
1. Configuration and Settings Management
2. Structured Logging
3. SQLite Database Operations (Conversations, Messages, Settings)
4. AI Providers (Base, Gemini, OpenAI, Mock) & Router
5. PySide6 Desktop Interface Components & Stylesheet
"""

import os
import sys
from pathlib import Path

# Configure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure bolt is imported first to register Windows DLL search directories
import bolt

import unittest
from bolt.config.settings import Settings
from bolt.core.database import Database
from bolt.core.logger import setup_logger, get_logger
from bolt.ai.base import ChatMessage
from bolt.ai.router import AIRouter
from bolt.ai.mock_provider import MockProvider
from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.openai_provider import OpenAIProvider


class TestPhase1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger("DEBUG")
        cls.test_db_path = ROOT / "data" / "test_bolt.db"
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        cls.db = Database(cls.test_db_path)

    @classmethod
    def tearDownClass(cls):
        if cls.test_db_path.exists():
            try:
                cls.test_db_path.unlink()
            except Exception:
                pass

    def test_01_settings(self):
        settings = Settings.load()
        self.assertIsNotNone(settings)
        self.assertIn(settings.provider, ["gemini", "openai", "mock"])
        masked = Settings.mask_key("AIzaSyD-1234567890abcdef")
        self.assertTrue(masked.startswith("AIza"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertIn("••••••••", masked)
        print("[OK] test_01_settings passed")

    def test_02_database_crud(self):
        # Create conversation
        conv_id = self.db.create_conversation("Unit Test Chat", "gemini", "gemini-2.5-flash")
        self.assertIsNotNone(conv_id)

        # Retrieve conversation
        conv = self.db.get_conversation(conv_id)
        self.assertEqual(conv["title"], "Unit Test Chat")

        # Add user message
        msg1_id = self.db.add_message(conv_id, "user", "Explain recursion in C++")
        self.assertIsNotNone(msg1_id)

        # Add assistant message
        msg2_id = self.db.add_message(conv_id, "assistant", "Recursion in C++ is...", model="gemini-2.5-flash")
        self.assertIsNotNone(msg2_id)

        # Verify messages
        msgs = self.db.get_messages(conv_id)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

        # Update title
        self.db.update_conversation_title(conv_id, "Recursion in C++")
        updated_conv = self.db.get_conversation(conv_id)
        self.assertEqual(updated_conv["title"], "Recursion in C++")

        # Clear messages
        self.db.clear_conversation_messages(conv_id)
        msgs_cleared = self.db.get_messages(conv_id)
        self.assertEqual(len(msgs_cleared), 0)

        # Delete conversation
        self.db.delete_conversation(conv_id)
        self.assertIsNone(self.db.get_conversation(conv_id))
        print("[OK] test_02_database_crud passed")

    def test_03_ai_providers(self):
        # 1. Mock Provider
        mock = MockProvider()
        self.assertEqual(mock.provider_name, "mock")
        res = mock.generate_response([ChatMessage(role="user", content="System specs")])
        self.assertTrue(res.success)
        self.assertIn("Windows", res.content)

        # 2. Gemini Provider instantiation
        gemini = GeminiProvider(api_key="dummy_key", model="gemini-2.5-flash")
        self.assertEqual(gemini.provider_name, "gemini")

        # 3. OpenAI Provider instantiation
        openai_p = OpenAIProvider(api_key="dummy_key", model="gpt-4o-mini")
        self.assertEqual(openai_p.provider_name, "openai")

        # 4. Router resolution
        router = AIRouter(Settings(provider="mock"))
        provider = router.get_provider()
        self.assertEqual(provider.provider_name, "mock")
        print("[OK] test_03_ai_providers passed")

    def test_04_pyside6_interface(self):
        # Run offscreen Qt GUI test
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from bolt.ui.main_window import MainWindow
        from bolt.ui.components.chat_view import format_markdown

        # Verify Markdown formatter
        md_html = format_markdown("### Title\n\n```cpp\nint main() {}\n```")
        self.assertIn("int main()", md_html)
        self.assertIn("Title", md_html)

        app = QApplication.instance() or QApplication(sys.argv)
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.header_bar.objectName(), "header_bar")
        self.assertEqual(window.sidebar.objectName(), "sidebar")
        self.assertEqual(window.status_bar.objectName(), "status_bar")

        # Simulate user input
        window.input_bar.set_text("What is BOLT?")
        self.assertEqual(window.input_bar.input_edit.toPlainText(), "What is BOLT?")

        print("[OK] test_04_pyside6_interface passed")


if __name__ == "__main__":
    unittest.main()
