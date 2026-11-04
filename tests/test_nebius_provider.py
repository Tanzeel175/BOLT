"""
Unit Tests for Nebius Token Factory Provider Integration in BOLT.
Verifies safe architecture, connection testing, settings persistence,
and non-destructive fallback without requiring a live paid API key.
"""

import unittest
from unittest.mock import MagicMock, patch

from bolt.ai.nebius_provider import NebiusProvider
from bolt.ai.provider_manager import get_provider_manager
from bolt.config.constants import (
    DEFAULT_NEBIUS_BASE_URL,
    DEFAULT_NEBIUS_MODEL,
    PROVIDER_NEBIUS,
    PROVIDER_OLLAMA,
    SUPPORTED_NEBIUS_MODELS,
)
from bolt.config.settings import Settings, get_settings


class TestNebiusProvider(unittest.TestCase):
    """Test suite for Nebius Token Factory AI provider."""

    def setUp(self):
        self.provider = NebiusProvider(
            api_key="",
            model=DEFAULT_NEBIUS_MODEL,
            base_url=DEFAULT_NEBIUS_BASE_URL,
        )

    def test_01_provider_metadata_and_defaults(self):
        """Verify provider metadata adheres to official Nebius specifications."""
        self.assertEqual(self.provider.provider_name, "nebius")
        self.assertEqual(self.provider.display_name, "Nebius Token Factory")
        self.assertEqual(self.provider.default_model, DEFAULT_NEBIUS_MODEL)
        self.assertEqual(self.provider.base_url, "https://api.tokenfactory.nebius.com/v1")
        self.assertFalse(self.provider.is_configured)
        self.assertIn(DEFAULT_NEBIUS_MODEL, self.provider.available_models)
        self.assertIn("deepseek-ai/DeepSeek-V4-Flash-0731", self.provider.available_models)

    def test_02_connection_test_without_key(self):
        """Verify connection test gracefully fails with a clear message when key is not set."""
        ok, msg = self.provider.test_connection()
        self.assertFalse(ok)
        self.assertIn("not configured", msg.lower())

    def test_03_key_masking_security(self):
        """Verify secret API key is never exposed in plaintext."""
        p_with_key = NebiusProvider(api_key="nebius-secret-key-1234567890abcdef")
        masked = p_with_key.mask_key()
        self.assertNotIn("secret-key-1234567890", masked)
        self.assertTrue(masked.startswith("nebi"))
        self.assertTrue(masked.endswith("cdef"))

    @patch("requests.get")
    def test_04_connection_test_mocked_success(self, mock_get):
        """Verify connection test parses 200 OK from Nebius API endpoint."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct"},
                {"id": "deepseek-ai/DeepSeek-V3"},
            ]
        }
        mock_get.return_value = mock_resp

        p_configured = NebiusProvider(api_key="mock-key-xyz")
        ok, msg = p_configured.test_connection()
        self.assertTrue(ok)
        self.assertIn("successfully", msg.lower())
        self.assertIn("2 models available", msg)

    @patch("requests.get")
    def test_05_connection_test_mocked_401_invalid_key(self, mock_get):
        """Verify connection test handles 401 Unauthorized gracefully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        p_configured = NebiusProvider(api_key="invalid-key-xyz")
        ok, msg = p_configured.test_connection()
        self.assertFalse(ok)
        self.assertIn("401", msg)

    def test_06_provider_manager_integration(self):
        """Verify Nebius is registered in AIProviderManager."""
        pm = get_provider_manager()
        nebius_p = pm.get_provider("nebius")
        self.assertIsNotNone(nebius_p)
        self.assertEqual(nebius_p.provider_name, "nebius")

        # Test alias resolution
        token_factory_p = pm.get_provider("tokenfactory")
        self.assertEqual(token_factory_p.provider_name, "nebius")

    def test_07_offline_first_fallback(self):
        """Verify switching to Nebius without key gracefully preserves local model operation."""
        pm = get_provider_manager()
        nebius_p = pm.get_provider("nebius")
        saved_key = nebius_p.api_key
        try:
            nebius_p.api_key = ""
            ok, msg = pm.switch_default_provider("nebius")
            self.assertTrue(ok)
            self.assertIn("Notice", msg)
            self.assertIn("Local AI", msg)
        finally:
            nebius_p.api_key = saved_key
            pm.switch_default_provider(PROVIDER_OLLAMA)

    def test_08_settings_persistence(self):
        """Verify Nebius settings fields exist and can be persisted."""
        settings = get_settings()
        self.assertTrue(hasattr(settings, "nebius_api_key"))
        self.assertTrue(hasattr(settings, "nebius_model"))
        self.assertTrue(hasattr(settings, "nebius_base_url"))
        self.assertEqual(settings.nebius_base_url, DEFAULT_NEBIUS_BASE_URL)


if __name__ == "__main__":
    unittest.main()

