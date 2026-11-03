"""
Comprehensive Verification Suite for BOLT Phase 8: Long-Term Memory and Continuous Learning.
Tests:
1. Category-segregated local SQLite memory architecture.
2. Core memory operations: save_memory, retrieve_memory, update_memory, search_memory, delete_memory, list_memories, export_memory.
3. Offline persistence across application restarts.
4. Personal preference storage & retrieval (e.g. 'Always open ChatGPT in Chrome').
5. Memory-driven execution (e.g. 'Open my usual programming environment').
6. Computer knowledge verification and outdated path detection.
7. Workflow memory retention & reuse ('same process as last time').
8. Structured conversation context extraction without raw message dumps.
9. Learning from user corrections ('You opened Edge, but I prefer Chrome').
10. Keyword & FTS5 BM25 search with relevance gating (unrelated memories discarded).
11. Local export to JSON and JSONL formats.
12. ToolRegistry integration for all 7 Phase 8 memory tools.
13. Complete offline operation without cloud memory or online embedding APIs.
"""

import json
import os
import pathlib
import tempfile
import unittest

from bolt.core.database import Database
from bolt.core.network_manager import get_network_manager
from bolt.memory.manager import MemoryManager, get_memory_manager
from bolt.memory.models import ExtractedContext, MemoryCategory, MemoryItem
from bolt.tasks.tool_registry import get_tool_registry
from bolt.windows.intent_dispatcher import get_intent_dispatcher


class TestPhase8MemoryAndLearning(unittest.TestCase):
    """Test suite for Phase 8 persistent memory and continuous learning."""

    def setUp(self):
        self.memory = get_memory_manager()
        self.dispatcher = get_intent_dispatcher()
        self.registry = get_tool_registry()
        self.network = get_network_manager()

    def test_01_memory_category_segregation(self):
        """Req 2: Verify separate memory categories and category isolation."""
        self.memory.save_memory(MemoryCategory.PERSONAL_PREFERENCES, "test_pref", "dark_mode")
        self.memory.save_memory(MemoryCategory.COMPUTER_KNOWLEDGE, "test_cpu", "Intel i7")
        self.memory.save_memory(MemoryCategory.WORKFLOW_MEMORY, "test_wf", {"steps": ["open", "search"]})
        self.memory.save_memory(MemoryCategory.CONVERSATION_MEMORY, "test_conv", {"topic": "ai"})
        self.memory.save_memory(MemoryCategory.CORRECTIONS, "test_corr", {"wrong": "a", "corrected": "b"})

        # Check category isolation
        prefs = self.memory.list_memories(MemoryCategory.PERSONAL_PREFERENCES)
        pref_keys = [p["key"] for p in prefs]
        self.assertIn("test_pref", pref_keys)
        self.assertNotIn("test_cpu", pref_keys)

        comp = self.memory.list_memories(MemoryCategory.COMPUTER_KNOWLEDGE)
        comp_keys = [c["key"] for c in comp]
        self.assertIn("test_cpu", comp_keys)
        self.assertNotIn("test_pref", comp_keys)

        print("\n[OK] test_01: Category segregation verified across all 5 memory categories.")

    def test_02_core_memory_crud_operations(self):
        """Req 4: Test save_memory, retrieve_memory, update_memory, search_memory, delete_memory."""
        # 1. save_memory
        ok = self.memory.save_memory(
            category=MemoryCategory.PERSONAL_PREFERENCES,
            key="test_crud_key",
            content="Initial Content",
            metadata={"source": "unit_test"},
            importance=1.5,
        )
        self.assertTrue(ok)

        # 2. retrieve_memory (increments access count)
        item = self.memory.retrieve_memory(MemoryCategory.PERSONAL_PREFERENCES, "test_crud_key")
        self.assertIsNotNone(item)
        self.assertEqual(item.content, "Initial Content")
        self.assertEqual(item.importance, 1.5)
        self.assertGreaterEqual(item.access_count, 1)

        # 3. update_memory
        up_ok = self.memory.update_memory(
            category=MemoryCategory.PERSONAL_PREFERENCES,
            key="test_crud_key",
            content="Updated Content",
            importance=1.8,
        )
        self.assertTrue(up_ok)
        item_updated = self.memory.retrieve_memory(MemoryCategory.PERSONAL_PREFERENCES, "test_crud_key")
        self.assertEqual(item_updated.content, "Updated Content")
        self.assertEqual(item_updated.importance, 1.8)

        # 4. delete_memory
        del_ok = self.memory.delete_memory(MemoryCategory.PERSONAL_PREFERENCES, "test_crud_key")
        self.assertTrue(del_ok)
        item_deleted = self.memory.retrieve_memory(MemoryCategory.PERSONAL_PREFERENCES, "test_crud_key")
        self.assertIsNone(item_deleted)

        print("\n[OK] test_02: Core CRUD operations (save, retrieve, update, delete) verified.")

    def test_03_offline_persistence_across_restarts(self):
        """Req 1: Memory must retain relevant knowledge after application restart."""
        # Save preference
        self.memory.set_user_preference("restart_persistence_test", "persisted_value_123")

        # Simulate restart by instantiating fresh Database and MemoryManager
        fresh_db = Database()
        fresh_memory = MemoryManager(db=fresh_db)

        # Retrieve through fresh instance
        retrieved = fresh_memory.get_user_preference("restart_persistence_test")
        self.assertEqual(retrieved, "persisted_value_123")

        print("\n[OK] test_03: Persistence across simulated restart verified.")

    def test_04_personal_preferences_chatgpt_in_chrome(self):
        """Req 2.A: Example 'Always open ChatGPT in Chrome' -> stores preference and applies next time."""
        # 1. User sets preference
        res = self.dispatcher.dispatch("Always open ChatGPT in Chrome.")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "learned_preference")

        # 2. Verify stored in personal preferences
        pref = self.memory.get_user_preference("preferred_browser_for_chatgpt")
        self.assertEqual(pref.lower(), "chrome")

        # 3. Verify retrieval helper finds it for task
        task_prefs = self.memory.retrieve_relevant_preferences_for_task("Open ChatGPT")
        self.assertEqual(task_prefs.get("preferred_browser"), "chrome")

        print(f"\n[OK] test_04: 'Always open ChatGPT in Chrome' preference stored and retrieved.")

    def test_05_memory_driven_usual_programming_environment(self):
        """Req 3: Example 'Open my usual programming environment' -> identifies, verifies, opens."""
        # 1. Establish preferred programming application
        self.memory.set_user_preference("preferred_programming_app", "Notepad")  # Using Notepad as verified installed app

        # 2. Dispatch natural language instruction
        res = self.dispatcher.dispatch("Open my usual programming environment")
        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "open_usual_environment")
        self.assertTrue(res.success)
        self.assertIn("Notepad", res.content)

        # Clean up Notepad process
        from bolt.windows.app_controller import get_app_controller
        get_app_controller().close_application("notepad")

        print(f"\n[OK] test_05: 'Open my usual programming environment' resolved Notepad from preferences.")

    def test_06_computer_knowledge_verification(self):
        """Req 2.B: Do not blindly trust outdated info; verify important paths and procedures."""
        # Store an existing path and a non-existent outdated path
        existing_dir = str(pathlib.Path.home())
        fake_dir = r"C:\NonExistent\FakeFolder\Outdated123"

        self.memory.save_memory(MemoryCategory.COMPUTER_KNOWLEDGE, "valid_home_path", existing_dir)
        self.memory.save_memory(MemoryCategory.COMPUTER_KNOWLEDGE, "outdated_fake_path", fake_dir)

        # Run verification
        report = self.memory.verify_computer_knowledge()
        self.assertTrue(report["success"])

        verified_paths = [v["path"] for v in report["verified"]]
        outdated_paths = [o["path"] for o in report["outdated"]]

        self.assertIn(existing_dir, verified_paths)
        self.assertIn(fake_dir, outdated_paths)

        print(f"\n[OK] test_06: Computer knowledge verification: {report['verified_count']} valid, {report['outdated_count']} outdated.")

    def test_07_workflow_memory_retention_and_recall(self):
        """Req 2.C: Example 'Prepare my research summary using the same process as last time'."""
        # 1. Remember a workflow
        wf_name = "AI Research Summary Workflow"
        user_query = "research the latest AI news and summarize"
        plan_json = json.dumps({"title": wf_name, "steps": [{"step_id": "s1", "description": "Search web", "tool_name": "search_web"}]})
        
        ok = self.memory.remember_workflow(
            name=wf_name,
            user_query=user_query,
            plan_json=plan_json,
            steps_summary="search_web -> summarize",
            apps_used=["msedge"],
            tools_used=["search_web", "gemini_generate"],
            result_summary="AI summary generated successfully.",
        )
        self.assertTrue(ok)

        # 2. Retrieve workflow matching 'same process as last time'
        recalled = self.memory.retrieve_workflow("AI Research Summary")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled["name"], wf_name)
        self.assertIn("search_web", recalled["tools_used"])

        print(f"\n[OK] test_07: Workflow memory retention and recall verified: '{recalled['name']}'.")

    def test_08_structured_conversation_context_extraction(self):
        """Req 2.D: Extract useful info and store in structured form without raw message dumps."""
        user_msg = "Please analyze the Python errors in my assignment project and check file script.py and data.csv."
        assistant_msg = "I will inspect script.py and data.csv to debug the assignment project."

        ctx = self.memory.record_conversation_context(user_msg, assistant_msg)
        self.assertIsInstance(ctx, ExtractedContext)
        self.assertIn("Assignment", ctx.active_project)
        self.assertTrue(any("script.py" in f for f in ctx.active_files))
        self.assertTrue(any("data.csv" in f for f in ctx.active_files))

        # Retrieve stored context
        active_ctx = self.memory.get_active_context()
        self.assertEqual(active_ctx.active_project, ctx.active_project)

        print(f"\n[OK] test_08: Structured conversation context: Project='{ctx.active_project}', Files={ctx.active_files}.")

    def test_09_learning_from_user_corrections(self):
        """Req 2.E: Example 'You opened Edge, but I prefer Chrome' -> recognizes mistake, saves preference."""
        correction_text = "You opened Edge, but I prefer Chrome."
        res = self.dispatcher.dispatch(correction_text)

        self.assertTrue(res.is_windows_action)
        self.assertEqual(res.action_type, "learned_preference")
        self.assertIn("chrome", res.content.lower())
        self.assertIn("edge", res.content.lower())

        # Verify preference was permanently stored
        pref_browser = self.memory.get_user_preference("preferred_browser")
        self.assertEqual(pref_browser.lower(), "chrome")

        print(f"\n[OK] test_09: Learned from user correction: Edge -> Chrome permanently saved.")

    def test_10_memory_search_and_relevance_gating(self):
        """Req 3: Keyword & FTS5 search; discard unrelated memories."""
        # Save specific memories
        self.memory.save_memory(MemoryCategory.PERSONAL_PREFERENCES, "preferred_programming_editor", "Visual Studio Code")
        self.memory.save_memory(MemoryCategory.PERSONAL_PREFERENCES, "preferred_lunch_spot", "Cafeteria")

        # Query relevant to programming editor in personal preferences
        matches = self.memory.search_memory("programming editor coding", category=MemoryCategory.PERSONAL_PREFERENCES, limit=3)
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["key"], "preferred_programming_editor")

        # Unrelated query should be gated out and return empty
        unrelated = self.memory.search_memory("astronomy telescope nebula galaxy", min_relevance=0.4)
        self.assertEqual(len(unrelated), 0)

        print(f"\n[OK] test_10: Relevance gating: relevant matched '{matches[0]['key']}', unrelated safely gated to 0.")

    def test_11_memory_export_json_and_jsonl(self):
        """Req 4: Test export_memory to JSON and JSONL formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "exported_memories.json")
            jsonl_path = os.path.join(tmpdir, "exported_memories.jsonl")

            # 1. JSON Export
            res_json = self.memory.export_memory(output_path=json_path, format="json")
            self.assertTrue(res_json["success"])
            self.assertTrue(os.path.isfile(json_path))
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertIsInstance(data, list)
                self.assertGreater(len(data), 0)

            # 2. JSONL Export
            res_jsonl = self.memory.export_memory(output_path=jsonl_path, format="jsonl")
            self.assertTrue(res_jsonl["success"])
            self.assertTrue(os.path.isfile(jsonl_path))
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
                self.assertGreater(len(lines), 0)

        print(f"\n[OK] test_11: Memory export verified for both JSON and JSONL formats.")

    def test_12_tool_registry_memory_tools(self):
        """Req 4: Verify all 7 memory tools registered in ToolRegistry."""
        required_tools = [
            "memory_save",
            "memory_retrieve",
            "memory_update",
            "memory_search",
            "memory_delete",
            "memory_list",
            "memory_export",
        ]
        registered_names = [t["name"] for t in self.registry.get_tool_definitions()]
        for rt in required_tools:
            self.assertIn(rt, registered_names, f"Missing tool: {rt}")

        # Execute memory_save via tool registry
        save_res = self.registry.execute_tool(
            "memory_save",
            category="personal_preferences",
            key="tool_registry_test_key",
            content="Tool Registry Test Value",
            importance=1.2,
        )
        self.assertTrue(save_res["success"])

        # Execute memory_retrieve via tool registry
        get_res = self.registry.execute_tool(
            "memory_retrieve",
            category="personal_preferences",
            key="tool_registry_test_key",
        )
        self.assertTrue(get_res["success"])
        self.assertEqual(get_res["memory"]["key"], "tool_registry_test_key")

        print(f"\n[OK] test_12: All 7 Phase 8 memory tools registered and verified via ToolRegistry.")

    def test_13_offline_memory_guarantee(self):
        """Req 1 & 3: Operates 100% locally with zero internet or cloud memory dependencies."""
        self.network.simulate_offline(True)
        try:
            # All memory operations must succeed while offline
            self.assertTrue(self.memory.save_memory(MemoryCategory.PERSONAL_PREFERENCES, "offline_key", "offline_val"))
            retrieved = self.memory.retrieve_memory(MemoryCategory.PERSONAL_PREFERENCES, "offline_key")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.content, "offline_val")

            searched = self.memory.search_memory("offline_key")
            self.assertGreater(len(searched), 0)
        finally:
            self.network.simulate_offline(None)

        print("\n[OK] test_13: Complete offline memory operation verified with zero network access.")


if __name__ == "__main__":
    unittest.main()
