"""
Automated Comprehensive Test Suite for BOLT Phase 3: Browser and Website Intelligence.
Verifies all Phase 3 requirements on Windows 11.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import unittest

from bolt.browser.ai_web_interaction import get_ai_web_interaction
from bolt.browser.browser_detection import get_browser_detector
from bolt.browser.browser_manager import get_browser_manager
from bolt.browser.content_reader import get_content_reader
from bolt.browser.navigator import get_browser_navigator
from bolt.browser.search_engine import get_search_engine
from bolt.browser.website_registry import get_website_registry
from bolt.tasks.tool_registry import get_tool_registry
from bolt.windows.intent_dispatcher import get_intent_dispatcher


class TestPhase3BrowserIntelligence(unittest.TestCase):
    """Test suite validating Phase 3 Browser and Website Intelligence."""

    @classmethod
    def setUpClass(cls):
        sys.stdout.reconfigure(encoding="utf-8")
        cls.detector = get_browser_detector()
        cls.registry = get_website_registry()
        cls.browser_mgr = get_browser_manager()
        cls.search_engine = get_search_engine()
        cls.reader = get_content_reader()
        cls.navigator = get_browser_navigator()
        cls.dispatcher = get_intent_dispatcher()
        cls.tool_registry = get_tool_registry()

    def test_01_browser_detection(self):
        """Verify detection of installed browsers, executable paths, and system default."""
        browsers = self.detector.detect_installed_browsers(refresh=True)
        self.assertGreaterEqual(len(browsers), 1, "At least one browser should be detected on Windows 11.")

        types = [b.browser_type for b in browsers]
        self.assertTrue(
            any(t in types for t in ["edge", "chrome", "brave", "firefox"]),
            f"Expected common browser in {types}",
        )

        default_browser = self.detector.get_preferred_or_default_browser()
        self.assertIsNotNone(default_browser, "Default browser should be identified.")
        self.assertTrue(default_browser.executable_path, "Default browser must have an executable path.")
        print(f"[OK] test_01_browser_detection passed: {len(browsers)} browsers detected (Default: {default_browser.name}).")

    def test_02_website_registry(self):
        """Verify persistent SQLite website registry, initial seeds, aliases, and URL validation."""
        all_sites = self.registry.get_all_registered_websites()
        self.assertGreaterEqual(len(all_sites), 6, "Initial 6 default websites must be present.")

        names = [s.name for s in all_sites]
        for expected in ["chatgpt", "gemini", "gmail", "google", "google drive", "youtube"]:
            self.assertIn(expected, names, f"Expected seed website '{expected}' in registry.")

        # Test alias translation
        mail_site = self.registry.find_website("email")
        self.assertIsNotNone(mail_site)
        self.assertEqual(mail_site.name, "gmail")

        gpt_site = self.registry.find_website("chat gpt")
        self.assertIsNotNone(gpt_site)
        self.assertEqual(gpt_site.name, "chatgpt")

        # Test URL validation
        self.assertEqual(self.registry.validate_url("google.com"), "https://google.com")
        self.assertEqual(self.registry.validate_url("https://example.com/test"), "https://example.com/test")
        self.assertIsNone(self.registry.validate_url("not a url with spaces"))

        # Test adding new website
        new_site = self.registry.register_website(
            name="github",
            url="https://github.com",
            category="Development",
            description="Code hosting platform",
        )
        self.assertIsNotNone(new_site)
        self.assertEqual(new_site.name, "github")
        print("[OK] test_02_website_registry passed (Seeds, Aliases, Validation, Upsert).")

    def test_03_search_engine(self):
        """Verify live web search retrieval, titles, clean URLs, and snippets."""
        resp = self.search_engine.search_web("Python programming language", max_results=3)
        self.assertEqual(resp.query, "Python programming language")
        self.assertGreater(resp.total_results, 0, "Web search should return results.")

        for item in resp.items:
            self.assertTrue(item.title, "Search result item must have a title.")
            self.assertTrue(item.url.startswith("http"), "Search result URL must be HTTP/HTTPS.")

        # Test provider search URL generator
        yt_url = self.search_engine.get_search_url_for_provider("youtube", "C++ tutorials")
        self.assertIn("youtube.com/results?search_query=", yt_url)
        print(f"[OK] test_03_search_engine passed ({resp.total_results} results retrieved).")

    def test_04_content_reader(self):
        """Verify accessible webpage reading, heading extraction, and summarization."""
        content = self.reader.read_webpage("https://www.google.com")
        self.assertTrue(content.is_available)
        self.assertEqual(content.status_code, 200)
        self.assertIn("Google", content.title)

        summary_md = self.reader.format_page_summary_markdown(content)
        self.assertIn("Webpage Summary", summary_md)
        print("[OK] test_04_content_reader passed (Google parsed and summarized).")

    def test_05_error_and_login_detection(self):
        """Verify handling of invalid URLs and detection of login/auth screens."""
        # 1. Invalid domain
        invalid_res = self.reader.read_webpage("https://fake-nonexistent-domain-99999.xyz")
        self.assertFalse(invalid_res.is_available)
        self.assertIn("unavailable", invalid_res.title.lower())

        # 2. Login URL
        login_res = self.reader.read_webpage("https://accounts.google.com/signin")
        self.assertTrue(login_res.is_login_page)
        print("[OK] test_05_error_and_login_detection passed (Invalid URL & Auth Detection).")

    def test_06_ai_web_interaction(self):
        """Verify AI service detection and API vs. Web Interface coordination."""
        ai_inter = get_ai_web_interaction()
        info = ai_inter.identify_ai_service("Can you open ChatGPT for me?")
        self.assertIsNotNone(info)
        self.assertEqual(info.service_key, "chatgpt")
        self.assertEqual(info.web_url, "https://chatgpt.com/")

        gemini_info = ai_inter.identify_ai_service("Open Gemini")
        self.assertIsNotNone(gemini_info)
        self.assertEqual(gemini_info.service_key, "gemini")
        print("[OK] test_06_ai_web_interaction passed.")

    def test_07_structured_tools_registry(self):
        """Verify Tool Registry schemas and structured function execution."""
        tool_defs = self.tool_registry.get_tool_definitions()
        tool_names = [t["name"] for t in tool_defs]
        for expected in ["open_website", "open_multiple_tabs", "search_web", "read_webpage", "switch_browser_tab"]:
            self.assertIn(expected, tool_names)

        # Execute read tool
        res = self.tool_registry.execute_tool("read_webpage", url="https://www.google.com")
        self.assertTrue(res["success"])
        print("[OK] test_07_structured_tools_registry passed.")

    def test_08_intent_dispatcher_browser_intents(self):
        """Verify natural language dispatching for all required Phase 3 commands."""
        # 1. "Open ChatGPT."
        res1 = self.dispatcher.dispatch("Open ChatGPT.")
        self.assertTrue(res1.is_windows_action)
        self.assertEqual(res1.action_type, "open_website")

        # 2. "Visit Gemini."
        res2 = self.dispatcher.dispatch("Visit Gemini.")
        self.assertTrue(res2.is_windows_action)
        self.assertEqual(res2.action_type, "open_website")

        # 3. "Go to Gmail."
        res3 = self.dispatcher.dispatch("Go to Gmail.")
        self.assertTrue(res3.is_windows_action)
        self.assertEqual(res3.action_type, "open_website")

        # 4. "Open ChatGPT and Gemini in separate tabs."
        res4 = self.dispatcher.dispatch("Open ChatGPT and Gemini in separate tabs.")
        self.assertTrue(res4.is_windows_action)
        self.assertEqual(res4.action_type, "multi_tab_navigation")

        # 5. "Search for the latest Python AI libraries."
        res5 = self.dispatcher.dispatch("Search for the latest Python AI libraries.")
        self.assertTrue(res5.is_windows_action)
        self.assertEqual(res5.action_type, "search_web")

        # 6. "Open this URL: https://www.google.com/"
        res6 = self.dispatcher.dispatch("Open this URL: https://www.google.com/")
        self.assertTrue(res6.is_windows_action)
        self.assertIn(res6.action_type, ["open_url", "open_website"])

        # 7. "Switch to the ChatGPT tab."
        res7 = self.dispatcher.dispatch("Switch to the ChatGPT tab.")
        self.assertTrue(res7.is_windows_action)
        self.assertEqual(res7.action_type, "switch_tab")

        # 8. "Read the current webpage and summarize it."
        res8 = self.dispatcher.dispatch("Read the current webpage and summarize it.")
        self.assertTrue(res8.is_windows_action)
        self.assertEqual(res8.action_type, "read_webpage")

        # 9. "Open YouTube and search for C++ tutorials."
        res9 = self.dispatcher.dispatch("Open YouTube and search for C++ tutorials.")
        self.assertTrue(res9.is_windows_action)
        self.assertEqual(res9.action_type, "search_web")

        # 10. "What browsers are installed?"
        res10 = self.dispatcher.dispatch("What browsers are installed?")
        self.assertTrue(res10.is_windows_action)
        self.assertEqual(res10.action_type, "list_browsers")

        print("[OK] test_08_intent_dispatcher_browser_intents passed (All 10 NL commands verified).")


if __name__ == "__main__":
    unittest.main()
