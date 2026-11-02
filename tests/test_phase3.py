"""
Comprehensive Automated Test Suite for BOLT Phase 3:
Browser and Website Intelligence
Verifies:
1. Browser Discovery and Detection
2. Website Registry, Aliases, and Knowledge Store
3. Internet Search Engine & Query Synthesis
4. Webpage Content Reader, Heading/Link Extraction
5. Login / Authentication Wall Detection
6. Tab Management (Multi-tab open, Tab Reuse, Tab Switch, Tab Close)
7. Content Reading & Summarization
8. Invalid URL and Connection Failure Handling
9. Natural Language Intent Dispatcher for Web Operations
"""

import os
import sys
import unittest
from pathlib import Path

# Configure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bolt
from bolt.browser.browser_detector import BrowserDetector, get_browser_detector
from bolt.browser.website_registry import WebsiteRegistry, get_website_registry
from bolt.browser.search_engine import SearchEngine, get_search_engine
from bolt.browser.content_reader import ContentReader, get_content_reader
from bolt.browser.browser_controller import BrowserController, get_browser_controller
from bolt.browser.ai_web_interaction import get_ai_web_interaction
from bolt.tasks.tool_registry import get_tool_registry
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher


class TestPhase3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Force headless mode for automated test execution
        os.environ["BOLT_HEADLESS_BROWSER"] = "true"

        cls.detector = BrowserDetector()
        cls.registry = WebsiteRegistry()
        cls.search_engine = SearchEngine()
        cls.content_reader = ContentReader()
        cls.controller = BrowserController(
            detector=cls.detector,
            registry=cls.registry,
            content_reader=cls.content_reader,
            search_engine=cls.search_engine,
        )
        cls.controller.set_headless(True)
        cls.dispatcher = WindowsIntentDispatcher(browser_controller=cls.controller)

    @classmethod
    def tearDownClass(cls):
        cls.controller.close_browser()

    def test_01_browser_detection(self):
        """Verify installed browsers and default browser detection."""
        browsers = self.detector.detect_installed_browsers()
        self.assertGreater(len(browsers), 0, "Should detect at least one installed browser")
        self.assertIn("msedge", browsers, "Microsoft Edge should be detected on Windows 11")

        default_id = self.detector.get_default_browser_id()
        self.assertIn(default_id, ["msedge", "chrome", "brave", "firefox"])
        print(f"[OK] test_01_browser_detection passed: Detected {list(browsers.keys())}, default: {default_id}")

    def test_02_website_registry(self):
        """Verify website registry, alias resolution, and URL validation."""
        # 1. Alias lookup
        gpt = self.registry.resolve_website("gpt")
        self.assertIsNotNone(gpt)
        self.assertEqual(gpt["url"], "https://chatgpt.com/")

        gemini = self.registry.resolve_website("gemini")
        self.assertIsNotNone(gemini)
        self.assertEqual(gemini["url"], "https://gemini.google.com/")

        gmail = self.registry.resolve_website("mail")
        self.assertIsNotNone(gmail)
        self.assertEqual(gmail["url"], "https://mail.google.com/")

        # 2. URL validation
        self.assertTrue(self.registry.is_valid_url("https://example.com"))
        self.assertTrue(self.registry.is_valid_url("google.com"))
        self.assertFalse(self.registry.is_valid_url("javascript:alert(1)"))
        self.assertFalse(self.registry.is_valid_url("file:///etc/passwd"))

        # 3. Dynamic registration
        reg_res = self.registry.register_website(
            name="python_org",
            url="https://www.python.org/",
            display_name="Python Official",
            category="Development",
            description="Python Programming Language Portal",
        )
        self.assertTrue(reg_res["success"])
        resolved = self.registry.resolve_website("python_org")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["url"], "https://www.python.org/")
        print("[OK] test_02_website_registry passed.")

    def test_03_search_engine(self):
        """Verify web search extraction and URL builders."""
        # 1. URL builders
        google_url = self.search_engine.build_search_url("C++ tutorials", "google")
        self.assertIn("google.com/search?q=", google_url)

        youtube_url = self.search_engine.build_search_url("C++ tutorials", "youtube")
        self.assertIn("youtube.com/results?search_query=", youtube_url)

        # 2. Search retrieval
        results = self.search_engine.search_online("Python programming language", max_results=3)
        self.assertGreater(len(results), 0)
        self.assertTrue(any("python" in r["title"].lower() or "python" in r["snippet"].lower() for r in results))

        # 3. Markdown formatting
        md = self.search_engine.format_results_markdown("Python", results)
        self.assertIn("Web Search Results", md)
        print("[OK] test_03_search_engine passed.")

    def test_04_content_reader(self):
        """Verify HTML parsing, heading extraction, and link parsing."""
        sample_html = """
        <html>
            <head><title>Python AI Tools Guide</title><meta name="description" content="Guide to AI libraries"/></head>
            <body>
                <h1>Top Python AI Libraries</h1>
                <h2>1. PyTorch</h2>
                <p>PyTorch is a machine learning framework based on the Torch library.</p>
                <h2>2. TensorFlow</h2>
                <p>TensorFlow is an end-to-end open source platform for machine learning.</p>
                <a href="https://pytorch.org">PyTorch Official</a>
                <a href="https://tensorflow.org">TensorFlow Official</a>
            </body>
        </html>
        """
        parsed = self.content_reader.parse_content(sample_html, base_url="https://example.com")
        self.assertEqual(parsed["title"], "Python AI Tools Guide")
        self.assertEqual(parsed["meta_description"], "Guide to AI libraries")
        self.assertEqual(len(parsed["headings"]), 3)
        self.assertEqual(len(parsed["paragraphs"]), 2)
        self.assertEqual(len(parsed["links"]), 2)
        self.assertFalse(parsed["requires_auth"])

        summary = self.content_reader.summarize_page(parsed, url="https://example.com")
        self.assertIn("Python AI Tools Guide", summary)
        self.assertIn("Top Python AI Libraries", summary)
        print("[OK] test_04_content_reader passed.")

    def test_05_auth_detection(self):
        """Verify authentication / login wall detection."""
        login_html = """
        <html>
            <head><title>Sign in to Account</title></head>
            <body>
                <h2>Sign in to continue</h2>
                <form action="/login" method="post">
                    <input type="text" name="username" placeholder="Email"/>
                    <input type="password" name="password" placeholder="Password"/>
                    <button type="submit">Sign in</button>
                </form>
            </body>
        </html>
        """
        parsed = self.content_reader.parse_content(login_html)
        self.assertTrue(parsed["requires_auth"])
        self.assertIn("Password input detected on page", parsed["auth_reasons"])

        summary = self.content_reader.summarize_page(parsed)
        self.assertIn("Authentication Required", summary)
        print("[OK] test_05_auth_detection passed.")

    def test_06_open_website_and_tabs(self):
        """Verify opening websites in separate tabs and verifying navigation."""
        # 1. Open example.com in tab 1
        res1 = self.controller.open_url("https://example.com")
        self.assertTrue(res1["success"], f"Failed to open example.com: {res1}")
        self.assertIn("Example Domain", res1["title"])

        # 2. Open example.org in tab 2
        res2 = self.controller.open_url("https://example.org")
        self.assertTrue(res2["success"], f"Failed to open example.org: {res2}")

        tabs = self.controller.get_open_tabs()
        self.assertGreaterEqual(len(tabs), 2, "Should have at least 2 open tabs")
        print(f"[OK] test_06_open_website_and_tabs passed: {len(tabs)} tabs open.")

    def test_07_tab_reuse(self):
        """Verify tab reuse when requesting an already opened website."""
        initial_tabs_count = len(self.controller.get_open_tabs())

        # Request example.com again
        res_reuse = self.controller.open_url("https://example.com")
        self.assertTrue(res_reuse["success"])
        self.assertEqual(res_reuse["action"], "reused_tab", "Existing tab should be reused")

        # Tab count should not have increased
        after_tabs_count = len(self.controller.get_open_tabs())
        self.assertEqual(initial_tabs_count, after_tabs_count, "No new tab should be spawned on reuse")
        print("[OK] test_07_tab_reuse passed.")

    def test_08_switch_and_close_tab(self):
        """Verify switching between tabs and closing tabs."""
        # Switch to example.org tab
        switch_res = self.controller.switch_to_tab("example.org")
        self.assertTrue(switch_res["success"], f"Failed to switch tab: {switch_res}")
        self.assertIn("example.org", switch_res["url"].lower())

        # Close current tab
        close_res = self.controller.close_tab()
        self.assertTrue(close_res["success"], f"Failed to close tab: {close_res}")
        print("[OK] test_08_switch_and_close_tab passed.")

    def test_09_read_current_page(self):
        """Verify reading and summarizing the active webpage."""
        read_res = self.controller.read_current_page()
        self.assertTrue(read_res["success"], f"Failed to read current page: {read_res}")
        self.assertIn("summary", read_res)
        self.assertIn("Example Domain", read_res["summary"])
        print("[OK] test_09_read_current_page passed.")

    def test_10_invalid_url_handling(self):
        """Verify that invalid or unreachable URLs return clean errors without crashing."""
        # 1. Invalid syntax
        bad_syntax = self.controller.open_url("not_a_valid_url_at_all_123!!")
        self.assertFalse(bad_syntax["success"])
        self.assertIn("neither a known website nor a valid web URL", bad_syntax["error"])

        # 2. Non-existent domain (DNS failure)
        dns_fail = self.controller.open_url("https://this-domain-does-not-exist-12345.fake/")
        self.assertFalse(dns_fail["success"])
        self.assertIn("Failed to load", dns_fail["error"])
        print("[OK] test_10_invalid_url_handling passed.")

    def test_11_multi_tab_navigation(self):
        """Verify opening multiple URLs in separate tabs sequentially."""
        res_multi = self.controller.open_multiple_urls([
            "https://example.com",
            "https://example.org",
        ])
        self.assertEqual(len(res_multi), 2)
        self.assertTrue(all(r["success"] for r in res_multi))
        print("[OK] test_11_multi_tab_navigation passed.")

    def test_12_intent_dispatcher_phase3(self):
        """Verify natural language instruction classification for all Phase 3 commands."""
        # 1. Direct website navigation
        res_gpt = self.dispatcher.dispatch("Open ChatGPT")
        self.assertTrue(res_gpt.is_windows_action)
        self.assertEqual(res_gpt.action_type, "open_website")

        # 2. Direct URL navigation
        res_url = self.dispatcher.dispatch("Open this URL: https://www.google.com/")
        self.assertTrue(res_url.is_windows_action)
        self.assertEqual(res_url.action_type, "open_website")

        # 3. Multi-website tabs
        res_multi = self.dispatcher.dispatch("Open ChatGPT and Gemini in separate tabs")
        self.assertTrue(res_multi.is_windows_action)
        self.assertEqual(res_multi.action_type, "multi_browser_nav")

        # 4. Web search command
        res_search = self.dispatcher.dispatch("Search for the latest Python AI libraries")
        self.assertTrue(res_search.is_windows_action)
        self.assertEqual(res_search.action_type, "web_search")
        self.assertIn("Web Search Results", res_search.content)

        # 5. Site-specific search command
        res_yt = self.dispatcher.dispatch("Open YouTube and search for C++ tutorials")
        self.assertTrue(res_yt.is_windows_action)
        self.assertEqual(res_yt.action_type, "site_search")

        # 6. Tab switch command
        res_tab = self.dispatcher.dispatch("Switch to the ChatGPT tab")
        self.assertTrue(res_tab.is_windows_action)
        self.assertEqual(res_tab.action_type, "switch_tab")

        # 7. Webpage summarization command
        res_read = self.dispatcher.dispatch("Read the current webpage and summarize it")
        self.assertTrue(res_read.is_windows_action)
        self.assertEqual(res_read.action_type, "read_webpage")

        # 8. Conversational prompt should NOT trigger browser or windows action
        res_conv = self.dispatcher.dispatch("Explain recursion in C++")
        self.assertFalse(res_conv.is_windows_action, "Conversational questions must route to LLM")
        print("[OK] test_12_intent_dispatcher_phase3 passed.")

    def test_13_ai_web_interaction(self):
        """Verify AI service recognition and web endpoint identification."""
        ai_inter = get_ai_web_interaction()
        info = ai_inter.identify_ai_service("Open ChatGPT for me")
        self.assertIsNotNone(info)
        self.assertEqual(info.service_key, "chatgpt")
        self.assertEqual(info.web_url, "https://chatgpt.com/")

        gemini_info = ai_inter.identify_ai_service("Visit Gemini")
        self.assertIsNotNone(gemini_info)
        self.assertEqual(gemini_info.service_key, "gemini")
        print("[OK] test_13_ai_web_interaction passed.")

    def test_14_tool_registry(self):
        """Verify structured tools registered for AI function calling."""
        tr = get_tool_registry()
        defs = tr.get_tool_definitions()
        names = [d["name"] for d in defs]
        for expected in ["open_website", "open_multiple_tabs", "search_web", "read_webpage", "switch_browser_tab", "list_known_websites"]:
            self.assertIn(expected, names)

        # Execute read_webpage tool
        res = tr.execute_tool("read_webpage", url="https://example.com")
        self.assertTrue(res["success"])
        print("[OK] test_14_tool_registry passed.")


if __name__ == "__main__":
    unittest.main()
