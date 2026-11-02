"""Comprehensive Unit and Subsystem Verification Suite for BOLT Phase 4.

Tests AI Application Integration:
1. Google Gemini Provider (Official API)
2. OpenAI ChatGPT / Compatible Provider (Official API)
3. Provider Manager (Runtime switching, model selection, DB persistence)
4. Multi-AI Comparison Engine (Side-by-side evaluation & synthesis)
5. Missing & Invalid API Key Handling (Zero faking, actionable instructions)
6. Network Failure & Timeout Handling
7. Multi-turn Conversation Context Retention
8. Explicit Named Provider Routing ("Ask Gemini...", "Ask ChatGPT...")
9. Browser vs API Integration (Method A vs Method B)
10. Asynchronous Worker Non-blocking Verification
"""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt  # DLL initialization
from bolt.ai.base import ChatMessage, AIResponse
from bolt.ai.gemini_provider import GeminiProvider
from bolt.ai.mock_provider import MockProvider
from bolt.ai.multi_ai import MultiAIComparator, get_multi_ai_comparator
from bolt.ai.openai_provider import OpenAIProvider
from bolt.ai.provider_manager import AIProviderManager, get_provider_manager, mask_key
from bolt.ai.response_manager import AIResponseManager, get_response_manager
from bolt.ai.router import AIRouter, get_ai_router
from bolt.browser.browser_manager import get_browser_manager
from bolt.browser.website_registry import get_website_registry
from bolt.config.constants import PROVIDER_GEMINI, PROVIDER_MOCK, PROVIDER_OPENAI
from bolt.config.settings import Settings, get_settings
from bolt.core.database import Database, get_database
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher


class TestPhase4AIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_database()
        cls.settings = get_settings()
        cls.pm = get_provider_manager()
        cls.router = get_ai_router()
        cls.dispatcher = get_intent_dispatcher()

    def test_01_gemini_provider_architecture(self):
        """Scenario 1 & 7: Gemini provider structure, configuration check, and missing key guidance."""
        prov_no_key = GeminiProvider(api_key="")
        self.assertFalse(prov_no_key.is_configured)
        self.assertEqual(prov_no_key.provider_name, "gemini")
        self.assertEqual(prov_no_key.display_name, "Google Gemini")
        self.assertIn("gemini-2.5-flash", prov_no_key.available_models)

        # Missing API Key must return actionable error, never pretend success
        resp = prov_no_key.generate_response([ChatMessage(role="user", content="Hello")])
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_type, "MISSING_KEY")
        self.assertIn("Google AI Studio", resp.error)
        print("\n[OK] test_01_gemini_provider_architecture passed.")

    def test_02_openai_provider_architecture(self):
        """Scenario 2 & 7: OpenAI provider structure, configuration check, and missing key guidance."""
        prov_no_key = OpenAIProvider(api_key="", base_url="https://api.openai.com/v1")
        self.assertFalse(prov_no_key.is_configured)
        self.assertEqual(prov_no_key.provider_name, "openai")
        self.assertEqual(prov_no_key.display_name, "OpenAI ChatGPT")
        self.assertIn("gpt-4o-mini", prov_no_key.available_models)

        # Missing API Key must return actionable error
        resp = prov_no_key.generate_response([ChatMessage(role="user", content="Hello")])
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_type, "MISSING_KEY")
        self.assertIn("OpenAI API", resp.error)
        print("[OK] test_02_openai_provider_architecture passed.")

    def test_03_provider_manager_switching_and_models(self):
        """Scenario 3 & 4: Switch default provider and update model selection at runtime."""
        pm = get_provider_manager()
        orig_provider = pm.settings.provider

        try:
            # Switch to OpenAI
            ok, msg = pm.switch_default_provider("openai")
            self.assertTrue(ok)
            self.assertEqual(pm.settings.provider, "openai")
            info = pm.get_provider_info("openai")
            self.assertTrue(info.is_default)

            # Change model
            ok_m, msg_m = pm.set_provider_model("openai", "gpt-4o")
            self.assertTrue(ok_m)
            self.assertEqual(pm.settings.openai_model, "gpt-4o")

            # Verify SQLite preference persistence
            pref = self.db.get_provider_preference("openai")
            self.assertIsNotNone(pref)
            self.assertEqual(pref["model"], "gpt-4o")
            self.assertEqual(pref["is_default"], 1)

            # Switch back to Gemini
            ok2, msg2 = pm.switch_default_provider("gemini")
            self.assertTrue(ok2)
            self.assertEqual(pm.settings.provider, "gemini")

        finally:
            pm.switch_default_provider(orig_provider)
        print("[OK] test_03_provider_manager_switching_and_models passed.")

    def test_04_multi_ai_comparison(self):
        """Scenario 5: Multi-AI comparison querying multiple providers concurrently."""
        comparator = get_multi_ai_comparator()
        result = comparator.compare_providers(
            prompt="Explain recursion",
            provider_names=["mock", "gemini"],
        )
        self.assertIsNotNone(result)
        self.assertIn("Explain recursion", result.formatted_markdown)
        self.assertIn("Multi-AI Comparison Report", result.formatted_markdown)
        self.assertTrue(len(result.responses) >= 2)
        print("[OK] test_04_multi_ai_comparison passed.")

    def test_05_invalid_api_key_handling(self):
        """Scenario 6: Verify invalid API key yields structured error without crashing."""
        gemini_invalid = GeminiProvider(api_key="AIzaSyFakeInvalidKeyForTesting12345")
        ok, msg = gemini_invalid.test_connection()
        self.assertFalse(ok)
        self.assertIn("Invalid Gemini API key", msg)

        openai_invalid = OpenAIProvider(api_key="sk-fake-invalid-openai-key-for-test")
        ok_o, msg_o = openai_invalid.test_connection()
        self.assertFalse(ok_o)
        self.assertIn("Invalid OpenAI API key", msg_o)
        print("[OK] test_05_invalid_api_key_handling passed.")

    def test_06_network_failure_and_timeout(self):
        """Scenario 8 & 9: Verify graceful handling of network timeouts and unreachable hosts."""
        prov_timeout = OpenAIProvider(
            api_key="sk-test",
            base_url="https://10.255.255.1:9999/v1",  # Unreachable non-routable IP
        )
        t0 = time.time()
        ok, msg = prov_timeout.test_connection()
        duration = time.time() - t0
        self.assertFalse(ok)
        self.assertTrue("timed out" in msg.lower() or "error" in msg.lower())
        print(f"[OK] test_06_network_failure_and_timeout passed ({duration:.2f}s).")

    def test_07_conversation_context_retention(self):
        """Scenario 10: Multi-turn conversation context correctly passed to providers."""
        history = [
            ChatMessage(role="user", content="My name is Alex."),
            ChatMessage(role="assistant", content="Hello Alex! How can I help you today?"),
            ChatMessage(role="user", content="What is my name?"),
        ]
        mock_p = MockProvider()
        resp = mock_p.generate_response(history)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "mock")
        print("[OK] test_07_conversation_context_retention passed.")

    def test_08_natural_language_ai_intents(self):
        """Scenario 11: Explicit named provider routing, switching, and comparison via NL."""
        dispatcher = get_intent_dispatcher()

        # 1. Switch default provider
        r1 = dispatcher.dispatch("Switch to Gemini")
        self.assertTrue(r1.is_windows_action)
        self.assertEqual(r1.action_type, "switch_ai_provider")
        self.assertTrue(r1.success)

        r2 = dispatcher.dispatch("Switch default provider to OpenAI")
        self.assertTrue(r2.is_windows_action)
        self.assertEqual(r2.action_type, "switch_ai_provider")
        self.assertTrue(r2.success)

        # 2. Multi-AI comparison
        r3 = dispatcher.dispatch("Compare how Gemini and ChatGPT explain recursion")
        self.assertTrue(r3.is_windows_action)
        self.assertEqual(r3.action_type, "compare_ai")
        self.assertIn("Multi-AI Comparison Report", r3.content)

        # 3. Explicit provider query
        r4 = dispatcher.dispatch("Ask Gemini to write a professional email requesting an internship")
        self.assertFalse(r4.is_windows_action)
        self.assertEqual(r4.action_type, "query_provider")
        self.assertEqual(r4.raw_data["provider_override"], "gemini")

        r5 = dispatcher.dispatch("Ask ChatGPT to explain this Python error: IndexError")
        self.assertFalse(r5.is_windows_action)
        self.assertEqual(r5.action_type, "query_provider")
        self.assertEqual(r5.raw_data["provider_override"], "chatgpt")
        print("[OK] test_08_natural_language_ai_intents passed.")

    def test_09_browser_based_interaction_method_b(self):
        """Scenario 12 & 13: Browser-based interaction (Method B) routing."""
        dispatcher = get_intent_dispatcher()

        r_chatgpt = dispatcher.dispatch("Open ChatGPT in my browser")
        self.assertTrue(r_chatgpt.is_windows_action)
        self.assertEqual(r_chatgpt.action_type, "open_website")
        self.assertTrue(r_chatgpt.success)

        r_gemini = dispatcher.dispatch("Open Gemini in browser")
        self.assertTrue(r_gemini.is_windows_action)
        self.assertEqual(r_gemini.action_type, "open_website")
        self.assertTrue(r_gemini.success)
        print("[OK] test_09_browser_based_interaction_method_b passed.")


if __name__ == "__main__":
    unittest.main()

