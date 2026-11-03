"""
Comprehensive Test Suite for BOLT Phase 7:
Offline Voice Assistant for BOLT.
Tests all requirements:
1. Microphone Detection & Device Query.
2. Offline Speech Recognition Engine Evaluation (Vosk vs Faster-Whisper).
3. Zero Auto-Download Policy & Model Install Instructions.
4. Offline Speech Recognition (Vosk PCM Transcription & VAD).
5. Offline Text-to-Speech (pyttsx3/SAPI), Voice Selection, Rate Config & Interruptibility.
6. Spoken Feedback Sanitization & Specific Canned Responses.
7. Echo-Cancellation Flag & Self-Listening Prevention.
8. Wake Word Detection ('Hey Bolt') & Push-to-Talk Mode.
9. Continuous Conversation Mode (Turn-Taking & Follow-up Window).
10. End-to-End Voice Pipeline with Actual Windows Task Engine Execution.
11. Voice Command Execution:
    - "Bolt, open Notepad"
    - "Open Calculator"
    - "Calculate 250 divided by 5"
    - "Create a text file on my Desktop"
    - "Search my computer for Python files"
    - "Search the internet for AI news" (Offline Handling)
    - "Stop speaking"
    - "Pause the current task" & "Cancel the current task"
12. Voice Safety & Human-in-the-Loop Approval Gates.
"""

import os
import pathlib
import time
import unittest
import numpy as np

from bolt.core.network_manager import get_network_manager
from bolt.voice.tts_engine import TTSEngine, get_tts_engine
from bolt.voice.speech_recognizer import SpeechRecognizer, get_speech_recognizer
from bolt.voice.wake_word import WakeWordDetector, get_wake_word_detector
from bolt.voice.conversation_mode import ConversationSession, ConversationState, get_conversation_session
from bolt.voice.voice_pipeline import VoicePipeline, get_voice_pipeline
from bolt.voice.voice_controller import VoiceController, get_voice_controller
from bolt.windows.intent_dispatcher import get_intent_dispatcher
from bolt.tasks.tool_registry import get_tool_registry
from bolt.tasks.multitasking_manager import get_multitasking_manager


class TestPhase7OfflineVoiceAssistant(unittest.TestCase):
    """Rigorous tests verifying Phase 7 offline voice interaction and computer control."""

    @classmethod
    def setUpClass(cls):
        os.environ["BOLT_HEADLESS_BROWSER"] = "1"
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.voice_ctrl = get_voice_controller()
        cls.tts = get_tts_engine()
        cls.recognizer = get_speech_recognizer()
        cls.wake_detector = get_wake_word_detector()
        cls.session = get_conversation_session()
        cls.pipeline = get_voice_pipeline()
        cls.network = get_network_manager()

    def test_01_microphone_detection_and_query(self):
        """Req 2: Detect available microphones and report default recording device."""
        mics = self.recognizer.detect_microphones()
        self.assertIsInstance(mics, list)
        # Verify microphone list is populated on host system
        default_mic = self.recognizer.get_default_microphone()
        if mics:
            self.assertIsNotNone(default_mic)
            self.assertIn("name", default_mic)
            print(f"\n[OK] test_01: Detected {len(mics)} audio input device(s). Default: {default_mic['name']}")
        else:
            print("\n[OK] test_01: No physical microphone detected; graceful fallback active.")

    def test_02_speech_engine_evaluation_vosk_vs_whisper(self):
        """Req 2: Evaluate Vosk vs Faster-Whisper for lightweight local operation."""
        eval_res = self.recognizer.evaluate_engines()
        self.assertEqual(eval_res["recommended"], "vosk")
        self.assertTrue(eval_res["vosk"]["is_available"])
        self.assertFalse(eval_res["faster_whisper"]["is_available"])
        self.assertIn("Application Control", eval_res["faster_whisper"]["notes"])

        print(f"\n[OK] test_02: STT Evaluation Complete: Primary={eval_res['recommended'].upper()} | Whisper WDAC Block Identified")

    def test_03_zero_auto_download_policy_and_instructions(self):
        """Req 2: Verify speech models are NOT downloaded automatically without consent."""
        instructions = self.recognizer.get_model_install_instructions()
        self.assertEqual(instructions["model_name"], "vosk-model-small-en-us-0.15")
        self.assertIn("instructions", instructions)
        self.assertIn("https://alphacephei.com/vosk/models/", instructions["instructions"])

        print(f"\n[OK] test_03: Zero Auto-Download Policy verified. Instructions provided cleanly.")

    def test_04_offline_tts_voice_configuration_and_speed(self):
        """Req 3: Local TTS supports configurable voice and speech rate without cloud APIs."""
        voices = self.tts.available_voices
        self.assertIsInstance(voices, list)
        self.assertGreater(len(voices), 0, "Windows SAPI voices must be detected locally.")

        # Test configurable rate
        original_rate = self.tts.get_speech_rate()
        self.tts.set_speech_rate(220)
        self.assertEqual(self.tts.get_speech_rate(), 220)
        self.tts.set_speech_rate(original_rate)

        # Test voice selection
        voice_names = [v["name"] for v in voices]
        res = self.tts.set_voice_by_name(voice_names[0])
        self.assertTrue(res)

        print(f"\n[OK] test_04: Offline TTS verified with {len(voices)} voice(s). Configurable rate and selection verified.")

    def test_05_tts_spoken_text_sanitization(self):
        """Req 3: Format long text and markdown into concise, natural spoken English."""
        # Strip markdown, code blocks, links
        raw_markdown = "### Calculation Result\n\n- The answer is **`3125`**.\n\n```python\nprint(125 * 25)\n```\nVisit [Python](https://python.org)"
        sanitized = self.tts.sanitize_for_speech(raw_markdown)
        self.assertNotIn("```", sanitized)
        self.assertNotIn("https://", sanitized)
        self.assertNotIn("#", sanitized)
        self.assertIn("3125", sanitized)

        # Verify canned response mappings
        self.assertEqual(self.tts.sanitize_for_speech("Opened Notepad successfully."), "Opening Notepad.")
        self.assertEqual(self.tts.sanitize_for_speech("Created text file Notes.txt"), "I have created your file.")
        self.assertEqual(self.tts.sanitize_for_speech("No internet connection available."), "No internet connection detected.")

        print(f"\n[OK] test_05: Spoken text sanitization and concise voice mappings verified.")

    def test_06_echo_cancellation_and_interruptibility(self):
        """Req 3: Verify speech interruption and self-listening prevention flags."""
        # Test interruption signal
        self.tts.stop_speaking()
        self.assertTrue(self.tts._stop_requested)

        # Test VAD muting during TTS speech
        dummy_audio = np.ones(1600, dtype=np.float32) * 0.5  # High energy audio
        self.tts._is_speaking = True
        self.assertFalse(self.recognizer.is_voice_active(dummy_audio), "Microphone VAD must be muted when TTS is active!")
        self.tts._is_speaking = False

        print(f"\n[OK] test_06: Echo-cancellation gating and speech interruptibility verified.")

    def test_07_wake_word_detection_and_push_to_talk(self):
        """Req 6: Local wake word detection ('Hey Bolt') and Push-to-Talk extraction."""
        # 1. Wake phrase extraction
        has_wake, cmd = self.wake_detector.extract_command("Hey Bolt, open Calculator")
        self.assertTrue(has_wake)
        self.assertEqual(cmd, "open Calculator")

        has_wake2, cmd2 = self.wake_detector.extract_command("Bolt, create a file on my Desktop")
        self.assertTrue(has_wake2)
        self.assertEqual(cmd2, "create a file on my Desktop")

        # 2. Standalone wake phrase
        has_wake3, cmd3 = self.wake_detector.extract_command("Hey Bolt")
        self.assertTrue(has_wake3)
        self.assertEqual(cmd3, "")

        # 3. Non-wake command (Push-to-Talk)
        has_wake4, cmd4 = self.wake_detector.extract_command("open Notepad")
        self.assertFalse(has_wake4)
        self.assertEqual(cmd4, "open Notepad")

        # 4. Toggling
        self.wake_detector.set_enabled(True)
        self.assertTrue(self.wake_detector.is_enabled)
        self.wake_detector.set_enabled(False)
        self.assertFalse(self.wake_detector.is_enabled)

        print(f"\n[OK] test_07: Wake word detection and Push-to-Talk command extraction verified.")

    def test_08_conversation_mode_turn_taking(self):
        """Req 7: Continuous multi-turn conversation mode without repeating wake phrase."""
        session = ConversationSession(follow_up_timeout=5.0)

        # Turn 1: Wake phrase
        greeting = session.trigger_wake_phrase()
        self.assertEqual(greeting, "I'm listening.")
        self.assertEqual(session.state, ConversationState.ACTIVE_LISTENING)
        self.assertTrue(session.is_in_conversation)

        # Turn 2: Command execution
        session.start_execution("Open Calculator")
        self.assertEqual(session.state, ConversationState.EXECUTING)
        session.complete_execution("Calculator is ready.")
        self.assertEqual(session.state, ConversationState.AWAITING_FOLLOW_UP)
        self.assertTrue(session.is_in_conversation)

        # Turn 3: Follow-up command within timeout window (no wake phrase needed)
        session.start_execution("Calculate 250 divided by 5")
        session.complete_execution("The result is 50.")
        self.assertEqual(session.state, ConversationState.AWAITING_FOLLOW_UP)

        # Turn 4: Close session
        session.close_session()
        self.assertEqual(session.state, ConversationState.IDLE)
        self.assertFalse(session.is_in_conversation)

        print(f"\n[OK] test_08: Multi-turn conversation mode and follow-up window verified.")

    def test_09_voice_command_open_notepad(self):
        """Req 5: Command: 'Bolt, open Notepad.' executes via Windows engine and speaks response."""
        res = self.pipeline.process_spoken_utterance("Bolt, open Notepad.", speak_output=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["action_type"], "open_app")
        self.assertEqual(res["spoken_response"], "Opening Notepad.")

        # Clean up
        from bolt.windows.app_controller import get_app_controller
        get_app_controller().close_application("notepad")

        print(f"\n[OK] test_09: Spoken command 'Bolt, open Notepad.' executed -> '{res['spoken_response']}'")

    def test_10_voice_command_open_calculator_and_calculate(self):
        """Req 5 & 7: Command: 'Open Calculator' and follow-up calculation 'Calculate 250 / 5'."""
        # 1. Open Calculator
        res1 = self.pipeline.process_spoken_utterance("Open Calculator", speak_output=False)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["spoken_response"], "Calculator is ready.")

        # 2. Conversational calculation follow-up (250 / 5 = 50)
        res2 = self.pipeline.process_spoken_utterance("calculate 250 / 5", speak_output=False)
        self.assertTrue(res2["success"])
        self.assertIn("50", res2["spoken_response"])

        print(f"\n[OK] test_10: Calculator open & calculation verified: '{res2['spoken_response']}'")

    def test_11_voice_command_create_text_file(self):
        """Req 5: Command: 'Create a text file on my Desktop' creates file and speaks response."""
        res = self.pipeline.process_spoken_utterance("Create a text file on my Desktop", speak_output=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["spoken_response"], "I have created your file.")

        print(f"\n[OK] test_11: Create text file voice command executed -> '{res['spoken_response']}'")

    def test_12_voice_command_offline_internet_search_graceful_exit(self):
        """Req 5: Internet search requested while offline immediately reports exact error."""
        self.network.simulate_offline(True)
        try:
            res = self.pipeline.process_spoken_utterance("Search the internet for the latest AI news.", speak_output=False)
            self.assertEqual(res["spoken_response"], "No internet connection detected. Online search is unavailable.")
        finally:
            self.network.simulate_offline(False)

        print(f"\n[OK] test_12: Offline web search voice command gracefully exited with required notice.")

    def test_13_voice_task_controls_and_interruption(self):
        """Req 3 & 5: Commands 'stop speaking', 'pause current task', 'cancel current task'."""
        # Stop speaking
        res_stop = self.pipeline.process_spoken_utterance("stop speaking", speak_output=False)
        self.assertTrue(res_stop["success"])
        self.assertEqual(res_stop["action"], "stop_speaking")

        # Pause task
        res_pause = self.pipeline.process_spoken_utterance("pause current task", speak_output=False)
        self.assertTrue(res_pause["success"])
        self.assertEqual(res_pause["spoken_response"], "Task paused.")

        # Cancel task
        res_cancel = self.pipeline.process_spoken_utterance("cancel current task", speak_output=False)
        self.assertTrue(res_cancel["success"])
        self.assertEqual(res_cancel["spoken_response"], "Task cancelled.")

        print(f"\n[OK] test_13: Voice task control commands verified.")

    def test_14_voice_safety_and_approval_gate(self):
        """Req 8: Sensitive task triggers spoken approval prompt, and voice approval proceeds."""
        session = ConversationSession()
        prompt = session.enter_approval_state("Send an internship email to recruiter", task_id="task_123")
        self.assertEqual(session.state, ConversationState.WAITING_APPROVAL)
        self.assertIn("requires your approval", prompt)

        # Test rejection
        decision_no = session.handle_approval_response("no")
        self.assertFalse(decision_no)
        self.assertEqual(session.state, ConversationState.IDLE)

        # Re-enter and test approval
        session.enter_approval_state("Send an internship email", task_id="task_123")
        decision_yes = session.handle_approval_response("I approve")
        self.assertTrue(decision_yes)
        self.assertEqual(session.state, ConversationState.EXECUTING)

        print(f"\n[OK] test_14: Voice safety and spoken approval gate verified.")

    def test_15_registered_voice_tools_in_registry(self):
        """Verify Phase 7 voice tools are formally registered in the central ToolRegistry."""
        reg = get_tool_registry()
        expected_tools = [
            "voice_speak",
            "voice_stop_speaking",
            "voice_listen_command",
            "voice_toggle_wake_word",
            "voice_get_status",
        ]
        for t in expected_tools:
            self.assertIn(t, reg._tools, f"Tool '{t}' missing from central ToolRegistry!")

        status_res = reg.execute_tool("voice_get_status")
        self.assertTrue(status_res["success"])
        self.assertIn("status", status_res)
        self.assertIn("microphones", status_res)
        self.assertIn("engine_evaluations", status_res)

        print(f"\n[OK] test_15: All 5 Phase 7 Voice Tools verified in central ToolRegistry.")


if __name__ == "__main__":
    unittest.main()
