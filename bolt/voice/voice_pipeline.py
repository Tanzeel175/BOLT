"""
Complete Voice Interaction Pipeline for BOLT (Phase 7).
Implements the full end-to-end voice loop:
Microphone -> VAD -> Speech Recognition -> Text Command -> Local AI Understanding
-> Task Planner -> Registered Windows Tool -> Execution Verification -> Spoken Response.
Guarantees that voice commands use the exact same task execution engine and security gates as typed commands.
"""

import time
from typing import Any, Dict, Optional, Tuple
from bolt.core.logger import get_logger
from bolt.core.network_manager import get_network_manager
from bolt.voice.speech_recognizer import SpeechRecognizer, get_speech_recognizer
from bolt.voice.tts_engine import TTSEngine, get_tts_engine
from bolt.voice.wake_word import WakeWordDetector, get_wake_word_detector
from bolt.voice.conversation_mode import ConversationSession, ConversationState, get_conversation_session
from bolt.windows.intent_dispatcher import WindowsIntentDispatcher, get_intent_dispatcher

logger = get_logger("VoicePipeline")


class VoicePipeline:
    """
    Coordinates offline speech intake, command routing through the BOLT execution
    engine, and local speech synthesis feedback.
    """

    def __init__(
        self,
        recognizer: Optional[SpeechRecognizer] = None,
        tts: Optional[TTSEngine] = None,
        wake_detector: Optional[WakeWordDetector] = None,
        session: Optional[ConversationSession] = None,
        dispatcher: Optional[WindowsIntentDispatcher] = None,
    ):
        self.recognizer = recognizer or get_speech_recognizer()
        self.tts = tts or get_tts_engine()
        self.wake_detector = wake_detector or get_wake_word_detector()
        self.session = session or get_conversation_session()
        self.dispatcher = dispatcher or get_intent_dispatcher()
        self.network = get_network_manager()

    def process_spoken_utterance(self, raw_speech_text: str, speak_output: bool = True) -> Dict[str, Any]:
        """
        Processes a recognized voice command through the complete BOLT pipeline:
        VAD/STT text -> Intent Analysis -> System Execution -> Verification -> Spoken Response.
        """
        start_time = time.perf_counter()
        logger.info(f"Processing voice utterance: '{raw_speech_text}'")

        if not raw_speech_text or not raw_speech_text.strip():
            return {
                "success": False,
                "command": "",
                "error": "No speech detected.",
                "spoken_response": "",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        text_clean = raw_speech_text.strip()
        lower = text_clean.lower()

        # ---------------- 1. Voice Interruption Commands ----------------
        if lower in ["stop speaking", "be quiet", "shut up", "stop talking", "silence"]:
            self.tts.stop_speaking()
            return {
                "success": True,
                "command": text_clean,
                "action": "stop_speaking",
                "spoken_response": "",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # ---------------- 2. Task Control Voice Commands ----------------
        if lower in ["pause task", "pause the task", "pause current task", "pause the current task"]:
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            mgr = get_multitasking_manager()
            mgr.pause_execution()
            spoken = "Task paused."
            if speak_output:
                self.tts.speak(spoken)
            return {
                "success": True,
                "command": text_clean,
                "action": "pause_task",
                "spoken_response": spoken,
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        if lower in ["cancel task", "cancel the task", "cancel current task", "cancel the current task", "abort task"]:
            from bolt.tasks.multitasking_manager import get_multitasking_manager
            mgr = get_multitasking_manager()
            mgr.cancel_execution()
            spoken = "Task cancelled."
            if speak_output:
                self.tts.speak(spoken)
            return {
                "success": True,
                "command": text_clean,
                "action": "cancel_task",
                "spoken_response": spoken,
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # ---------------- 3. Approval Response Handling ----------------
        if self.session.state == ConversationState.WAITING_APPROVAL:
            approval_decision = self.session.handle_approval_response(text_clean)
            if approval_decision is not None:
                from bolt.tasks.multitasking_manager import get_multitasking_manager
                mgr = get_multitasking_manager()
                mgr.provide_approval(approved=approval_decision)
                spoken = "Proceeding with approved task." if approval_decision else "Action cancelled."
                if speak_output:
                    self.tts.speak(spoken)
                return {
                    "success": True,
                    "command": text_clean,
                    "action": "approval_decision",
                    "approved": approval_decision,
                    "spoken_response": spoken,
                    "execution_time_ms": (time.perf_counter() - start_time) * 1000,
                }

        # ---------------- 4. Wake Phrase Evaluation & Stripping ----------------
        has_wake, command_text = self.wake_detector.extract_command(text_clean)

        # Standalone wake phrase ("Hey Bolt" with no immediate command)
        if has_wake and not command_text:
            greeting = self.session.trigger_wake_phrase()
            if speak_output:
                self.tts.speak(greeting)
            return {
                "success": True,
                "command": text_clean,
                "action": "wake_word_activated",
                "spoken_response": greeting,
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
            }

        # If wake word not present and not in active conversation, allow Push-to-Talk or direct execution
        active_command = command_text if has_wake else text_clean
        self.session.start_execution(active_command)

        # ---------------- 5. Execute Command via BOLT Task Engine ----------------
        # Route through IntentDispatcher (handles Windows control, files, UIA, browser, DAG tasks)
        intent_res = self.dispatcher.dispatch(active_command)
        spoken_response = ""

        if intent_res.is_windows_action:
            spoken_response = self._generate_spoken_feedback(active_command, intent_res)
        else:
            # Query local AI engine for conversational/instruction understanding
            from bolt.ai.router import get_ai_router
            ai_router = get_ai_router()
            ai_reply = ai_router.generate_response(active_command)
            spoken_response = self.tts.sanitize_for_speech(ai_reply, max_chars=180)

        # ---------------- 6. Execution Verification & Spoken Output ----------------
        if not intent_res.success and intent_res.is_windows_action:
            # Check if failure is due to offline internet requirement
            if not self.network.is_online and any(k in active_command.lower() for k in ["search", "internet", "web", "online"]):
                spoken_response = "No internet connection detected. Online search is unavailable."
            elif not spoken_response or "failed" in spoken_response.lower():
                spoken_response = "I could not complete that operation."

        # Speak response aloud
        if speak_output and spoken_response:
            self.tts.speak(spoken_response)

        self.session.complete_execution(spoken_response)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": intent_res.success,
            "command": active_command,
            "action_type": getattr(intent_res, "action_type", "ai_chat"),
            "spoken_response": spoken_response,
            "intent_result": intent_res.to_dict() if hasattr(intent_res, "to_dict") else None,
            "execution_time_ms": elapsed_ms,
        }

    def _generate_spoken_feedback(self, command: str, intent_res: Any) -> str:
        """Construct a concise, natural spoken response for Windows/task actions."""
        cmd_lower = command.lower()
        action = getattr(intent_res, "action_type", "")
        raw = getattr(intent_res, "raw_data", {}) or {}

        # Calculation result
        if action == "calculate_accessible" or "calculate" in cmd_lower:
            calc_val = raw.get("result", "")
            if calc_val:
                return f"The result is {calc_val}."
            return self.tts.sanitize_for_speech(intent_res.content)

        # Open application
        if action == "open_app":
            if "notepad" in cmd_lower:
                return "Opening Notepad."
            if "calc" in cmd_lower:
                return "Calculator is ready."
            app_name = raw.get("app_name", intent_res.title.replace("Open ", ""))
            return f"Opening {app_name}."

        # Create or write file
        if action in ("create_file", "write_file") or "create a text file" in cmd_lower or "notes.txt" in cmd_lower:
            return "I have created your file."

        # Open folder
        if action == "open_folder" or "folder" in cmd_lower:
            folder = raw.get("folder", "folder")
            return f"Opened your {folder.title()} folder."

        # Search computer files
        if action == "search_files" or "search my computer" in cmd_lower:
            count = raw.get("count", len(raw.get("files", [])))
            return f"Found {count} matching files on your computer."

        # Web search
        if action in ("web_search", "site_search"):
            if not self.network.is_online or not intent_res.success:
                return "No internet connection detected. Online search is unavailable."
            return self.tts.sanitize_for_speech(intent_res.content, max_chars=160)

        # Multi-action DAG task
        if action == "multi_action_task":
            if raw.get("status") == "waiting_approval":
                return self.session.enter_approval_state(intent_res.title)
            return self.tts.sanitize_for_speech(intent_res.title, max_chars=120)

        # Fallback to sanitized content
        return self.tts.sanitize_for_speech(intent_res.content, max_chars=140)

    def listen_and_execute(self, max_duration_sec: float = 6.0) -> Dict[str, Any]:
        """
        Complete end-to-end cycle:
        Listens via microphone (Push-to-Talk or VAD) -> transcribes -> executes -> speaks.
        """
        logger.info("Voice pipeline: listening for command...")
        speech_text = self.recognizer.listen_command_push_to_talk(max_duration_sec=max_duration_sec)

        if not speech_text:
            return {
                "success": False,
                "command": "",
                "error": "No voice command received or microphone inactive.",
                "spoken_response": "",
            }

        return self.process_spoken_utterance(speech_text, speak_output=True)


_VOICE_PIPELINE_INSTANCE: Optional[VoicePipeline] = None


def get_voice_pipeline() -> VoicePipeline:
    global _VOICE_PIPELINE_INSTANCE
    if _VOICE_PIPELINE_INSTANCE is None:
        _VOICE_PIPELINE_INSTANCE = VoicePipeline()
    return _VOICE_PIPELINE_INSTANCE
