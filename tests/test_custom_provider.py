"""Unit and integration tests for CustomAIProvider (Any Model API Key) and routing."""

import unittest
from unittest.mock import MagicMock, patch

from bolt.ai.base import ChatMessage
from bolt.ai.custom_provider import CustomAIProvider, POPULAR_PRESETS
from bolt.ai.provider_manager import AIProviderManager
from bolt.ai.router import AIRouter
from bolt.config.constants import (
    DEFAULT_CUSTOM_BASE_URL,
    DEFAULT_CUSTOM_MODEL,
    DEFAULT_CUSTOM_NAME,
    PROVIDER_CUSTOM,
    PROVIDER_OLLAMA,
)
from bolt.config.settings import Settings
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher


class TestCustomAIProvider(unittest.TestCase):
    """Test CustomAIProvider initialization, configuration, and API calling."""

    def test_initialization_and_properties(self):
        provider = CustomAIProvider(
            name="Groq Cloud",
            api_key="gsk-test12345",
            base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
        )
        self.assertEqual(provider.provider_name, "custom")
        self.assertEqual(provider.display_name, "Any Model (Groq Cloud)")
        self.assertEqual(provider.default_model, "llama-3.3-70b-versatile")
        self.assertTrue(provider.is_configured)
        self.assertIn("llama-3.3-70b-versatile", provider.available_models)
        self.assertIn("deepseek-chat", provider.available_models)

    def test_unconfigured_when_empty_key(self):
        provider = CustomAIProvider(
            name="Custom Provider",
            api_key="",
            base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
        )
        self.assertFalse(provider.is_configured)
        resp = provider.generate_response([ChatMessage(role="user", content="hello")])
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_type, "MISSING_KEY")

    def test_local_endpoint_is_configured_without_key(self):
        provider = CustomAIProvider(
            name="LM Studio",
            api_key="",
            base_url="http://127.0.0.1:1234/v1",
            model="local-model",
        )
        self.assertTrue(provider.is_configured)

    def test_headers_and_openrouter_attribution(self):
        p1 = CustomAIProvider(api_key="sk-test", base_url="https://api.groq.com/openai/v1")
        h1 = p1._build_headers()
        self.assertEqual(h1["Authorization"], "Bearer sk-test")
        self.assertNotIn("HTTP-Referer", h1)

        p2 = CustomAIProvider(api_key="sk-or-test", base_url="https://openrouter.ai/api/v1")
        h2 = p2._build_headers()
        self.assertEqual(h2["Authorization"], "Bearer sk-or-test")
        self.assertEqual(h2["HTTP-Referer"], "https://github.com/BOLT-Assistant")

    @patch("requests.post")
    def test_generate_response_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Hello from Groq Llama!"}}],
            "usage": {"total_tokens": 42, "prompt_tokens": 12, "completion_tokens": 30},
        }
        mock_post.return_value = mock_resp

        provider = CustomAIProvider(
            name="Groq",
            api_key="gsk-test",
            base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
        )
        resp = provider.generate_response(
            messages=[ChatMessage(role="user", content="Hi")],
            system_prompt="You are BOLT.",
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "Hello from Groq Llama!")
        self.assertEqual(resp.tokens_used, 42)

    @patch("requests.post")
    def test_generate_response_invalid_key_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Invalid API Key"
        mock_resp.json.return_value = {"error": {"message": "Invalid API key provided", "code": "invalid_api_key"}}
        mock_post.return_value = mock_resp

        provider = CustomAIProvider(
            name="DeepSeek",
            api_key="sk-invalid",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        resp = provider.generate_response([ChatMessage(role="user", content="Hi")])
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_type, "INVALID_KEY")

    @patch("requests.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        provider = CustomAIProvider(
            name="Mistral",
            api_key="mistral-key",
            base_url="https://api.mistral.ai/v1",
            model="mistral-large-latest",
        )
        ok, msg = provider.test_connection()
        self.assertTrue(ok)
        self.assertIn("Successfully connected", msg)

    def test_presets_structure(self):
        self.assertIn("groq", POPULAR_PRESETS)
        self.assertIn("deepseek", POPULAR_PRESETS)
        self.assertIn("openrouter", POPULAR_PRESETS)
        self.assertIn("mistral", POPULAR_PRESETS)
        self.assertIn("lmstudio", POPULAR_PRESETS)


class TestSettingsAndRouterIntegration(unittest.TestCase):
    """Test Settings persistence and AIRouter fallback behavior."""

    def test_settings_custom_fields_defaults(self):
        s = Settings()
        self.assertEqual(s.custom_provider_name, DEFAULT_CUSTOM_NAME)
        self.assertEqual(s.custom_base_url, DEFAULT_CUSTOM_BASE_URL)
        self.assertEqual(s.custom_model, DEFAULT_CUSTOM_MODEL)
        self.assertEqual(s.custom_api_key, "")

    def test_router_falls_back_to_ollama_when_custom_unconfigured(self):
        s = Settings(
            provider="custom",
            custom_api_key="",
            custom_base_url="https://api.groq.com/openai/v1",
            ollama_model="gemma4:e2b",
        )
        # Mock provider manager
        mock_pm = MagicMock(spec=AIProviderManager)
        unconfigured_custom = CustomAIProvider(api_key="", base_url="https://api.groq.com/openai/v1")
        configured_ollama = MagicMock()
        configured_ollama.provider_name = "ollama"
        configured_ollama.display_name = "Ollama (Local AI)"
        configured_ollama.is_configured = True

        def mock_get_p(name):
            if name == "custom":
                return unconfigured_custom
            return configured_ollama

        mock_pm.get_provider.side_effect = mock_get_p

        router = AIRouter(settings=s, provider_mgr=mock_pm)
        resolved = router.get_provider()
        # Must resolve to local Ollama because custom is unconfigured!
        self.assertEqual(resolved.provider_name, "ollama")

    def test_intent_dispatcher_recognizes_switch_to_custom(self):
        dispatcher = WindowsIntentDispatcher()
        res = dispatcher.dispatch("switch to groq")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "switch_ai_provider")

        res_local = dispatcher.dispatch("prefer local model")
        self.assertTrue(res_local.is_windows_action)
        self.assertEqual(res_local.action_type, "switch_ai_provider")
        self.assertIn("Ollama", res_local.title)


if __name__ == "__main__":
    unittest.main()
