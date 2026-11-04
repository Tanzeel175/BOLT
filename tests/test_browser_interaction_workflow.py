"""
Automated Regression and Unit Tests for BOLT Browser Interaction and Multi-Step Workflows.
Verifies Chrome profile detection, window/tab inspection, webpage interaction,
DAG task planning, and safe Gmail draft preparation without sending emails.
"""

import os
import unittest

from bolt.browser.chrome_profile_manager import (
    ChromeProfileInfo,
    ChromeProfileManager,
    get_chrome_profile_manager,
)
from bolt.browser.real_browser_controller import (
    RealBrowserController,
    get_real_browser_controller,
)
from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskStatus, TaskStep
from bolt.tasks.planner import TaskPlanner, get_task_planner
from bolt.tasks.tool_registry import ToolRegistry, get_tool_registry
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher


class TestChromeProfileManager(unittest.TestCase):
    """Test Chrome profile discovery, parsing, and query matching."""

    def setUp(self):
        self.mgr = get_chrome_profile_manager()

    def test_list_profiles_discovers_configured_profiles(self):
        profiles = self.mgr.list_profiles()
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0, "Should discover at least one Chrome profile on laptop.")
        
        # Verify no credentials leaked
        for p in profiles:
            self.assertTrue(hasattr(p, "directory"))
            self.assertTrue(hasattr(p, "name"))
            self.assertTrue(hasattr(p, "email"))
            self.assertFalse(hasattr(p, "password"))
            self.assertFalse(hasattr(p, "cookie"))
            self.assertFalse(hasattr(p, "token"))

    def test_find_profile_fuzzy_and_exact(self):
        # Test finding profile by exact or fuzzy name
        prof, _ = self.mgr.find_profile("m tanzeel")
        self.assertIsNotNone(prof)
        self.assertEqual(prof.directory, "Profile 1")

        prof2, _ = self.mgr.find_profile("Work")
        self.assertIsNotNone(prof2)
        self.assertEqual(prof2.directory, "Profile 6")

        prof3, _ = self.mgr.find_profile("Muhammad tanzeel shahzad")
        self.assertIsNotNone(prof3)
        self.assertIn(prof3.directory, ("Profile 4", "Profile 1"))

    def test_profile_matches_query_scoring(self):
        p = ChromeProfileInfo(
            directory="Profile 1",
            name="m tanzeel",
            gaia_name="m tanzeel shahzad",
            email="m.tanzeel.s.87@gmail.com",
        )
        matched, score = p.matches_query("m tanzeel")
        self.assertTrue(matched)
        self.assertGreaterEqual(score, 80)

        matched_email, score_email = p.matches_query("m.tanzeel.s.87@gmail.com")
        self.assertTrue(matched_email)
        self.assertGreaterEqual(score_email, 90)


class TestRealBrowserController(unittest.TestCase):
    """Test real browser window inspection, tab listing, and control access."""

    def setUp(self):
        self.rbc = get_real_browser_controller()

    def test_get_open_chrome_windows(self):
        windows = self.rbc.get_open_chrome_windows()
        self.assertIsInstance(windows, list)
        # Windows should have expected keys
        for w in windows:
            self.assertIn("hwnd", w)
            self.assertIn("title", w)
            self.assertIn("profile_name", w)

    def test_get_chrome_tabs(self):
        tabs = self.rbc.get_chrome_tabs()
        self.assertIsInstance(tabs, list)
        for t in tabs:
            self.assertIn("index", t)
            self.assertIn("title", t)
            self.assertIn("is_active", t)

    def test_inspect_webpage_structure(self):
        # Inspect active page
        res = self.rbc.inspect_webpage(max_elements=15)
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success"))
        self.assertIn("elements", res)
        self.assertIn("formatted", res)


class TestTaskPlannerBrowserDAG(unittest.TestCase):
    """Test multi-step task decomposition for browser and email workflows."""

    def setUp(self):
        self.planner = get_task_planner()

    def test_gmail_workflow_decomposition(self):
        instruction = "open the browser and go to specific profile Muhammad tanzeel shahzad and open gmail and mail to test@example.com"
        plan = self.planner.plan_instruction(instruction)

        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(plan.title, "Email Preparation & Approval")
        self.assertEqual(len(plan.steps), 4)

        # Step 1: Profile selection
        self.assertEqual(plan.steps[0].tool_name, "select_browser_profile")
        self.assertIn("Muhammad tanzeel shahzad", plan.steps[0].input_params.get("profile_name", ""))

        # Step 2: Navigate Gmail
        self.assertEqual(plan.steps[1].tool_name, "navigate_browser_url")
        self.assertIn("mail.google.com", plan.steps[1].input_params.get("url", ""))

        # Step 3: Wait for Compose
        self.assertEqual(plan.steps[2].tool_name, "wait_for_browser_element")

        # Step 4: Draft email (Compose + fields)
        self.assertEqual(plan.steps[3].tool_name, "draft_browser_email")
        self.assertEqual(plan.steps[3].input_params.get("recipient"), "test@example.com")

    def test_single_open_browser_no_duplicates(self):
        plan = self.planner.plan_instruction("open browser")
        self.assertEqual(len(plan.steps), 1, "Should have exactly 1 step, no duplicate step_1.")
        self.assertEqual(plan.steps[0].tool_name, "open_application")
        self.assertEqual(plan.steps[0].input_params.get("app_name"), "Google Chrome")

    def test_compound_research_workflow(self):
        instruction = "Open Chrome, search for Python tutorials and save three useful links."
        plan = self.planner.plan_instruction(instruction)
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[0].tool_name, "open_application")
        self.assertEqual(plan.steps[1].tool_name, "search_web")
        self.assertEqual(plan.steps[2].tool_name, "type_text")


class TestToolRegistryBrowserTools(unittest.TestCase):
    """Test that all required browser interaction tools are registered."""

    def setUp(self):
        self.tr = get_tool_registry()

    def test_all_browser_tools_registered(self):
        defs = self.tr.get_tool_definitions()
        tool_names = {t["name"] for t in defs}

        required_tools = [
            "list_browser_profiles",
            "select_browser_profile",
            "navigate_browser_url",
            "get_browser_tabs",
            "switch_browser_tab",
            "inspect_browser_page",
            "click_browser_element",
            "type_browser_element",
            "scroll_browser_page",
            "wait_for_browser_element",
            "draft_browser_email",
        ]

        for rt in required_tools:
            self.assertIn(rt, tool_names, f"Tool '{rt}' must be registered in ToolRegistry.")

    def test_list_browser_profiles_tool_execution(self):
        res = self.tr.execute_tool("list_browser_profiles", bypass_security_check=True)
        self.assertTrue(res.get("success"))
        profiles = res.get("result", [])
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0)


class TestIntentDispatcherBrowserRouting(unittest.TestCase):
    """Test IntentDispatcher resolution for browser instructions."""

    def setUp(self):
        self.disp = get_intent_dispatcher()

    def test_open_browser_resolves_as_action(self):
        for phrase in ["open browser", "open the browser", "open the chrome", "open chrome"]:
            res = self.disp.dispatch(phrase)
            self.assertTrue(res.is_windows_action, f"Phrase '{phrase}' must be recognized as windows action.")
            self.assertIn(res.action_type, ("open_app", "multi_action_task"))

    def test_list_profiles_resolves(self):
        res = self.disp.dispatch("list profiles")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "list_profiles")

    def test_compound_gmail_workflow_routes_to_task_planner(self):
        instruction = "open the browser and go to specific profile Muhammad tanzeel shahzad and open gmail and mail to test@example.com"
        res = self.disp.dispatch(instruction)
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "multi_action_task")


if __name__ == "__main__":
    unittest.main()

