"""
Offline Voice Controller for BOLT (Phase 7).
Provides high-level unified interface for local speech synthesis (TTS),
offline speech recognition (STT), Push-to-Talk, wake word detection,
and conversational state management.
Never requires cloud speech APIs.
"""

from typing import Any, Dict, List, Optional
from bolt.core.logger import get_logger
from bolt.voice.tts_engine import TTSEngine, get_tts_engine
from bolt.voice.speech_recognizer import SpeechRecognizer, get_speech_recognizer
from bolt.voice.wake_word import WakeWordDetector, get_wake_word_detector
from bolt.voice.conversation_mode import ConversationSession, get_conversation_session
from bolt.voice.voice_pipeline import VoicePipeline, get_voice_pipeline

logger = get_logger("VoiceController")


class VoiceController:
    """
    Unified Voice Controller integrating TTS, STT, wake word, and conversation flow.
    """

    def __init__(
        self,
        tts: Optional[TTSEngine] = None,
        recognizer: Optional[SpeechRecognizer] = None,
        wake_detector: Optional[WakeWordDetector] = None,
        session: Optional[ConversationSession] = None,
        pipeline: Optional[VoicePipeline] = None,
    ):
        self.tts = tts or get_tts_engine()
        self.recognizer = recognizer or get_speech_recognizer()
        self.wake_detector = wake_detector or get_wake_word_detector()
        self.session = session or get_conversation_session()
        self.pipeline = pipeline or get_voice_pipeline()

    @property
    def is_tts_available(self) -> bool:
        """True if offline TTS voices are available."""
        return len(self.tts.available_voices) > 0 or getattr(self.tts, "_is_speaking", False)

    @property
    def is_stt_available(self) -> bool:
        """True if offline STT model is downloaded locally."""
        return self.recognizer.model_downloaded

    @property
    def is_speaking(self) -> bool:
        """True if audio is currently playing."""
        return self.tts.is_speaking

    @property
    def is_wake_word_enabled(self) -> bool:
        return self.wake_detector.is_enabled

    def set_wake_word_enabled(self, enabled: bool) -> None:
        self.wake_detector.set_enabled(enabled)

    @property
    def status_summary(self) -> str:
        """Human-readable status of the voice subsystem."""
        tts_part = "TTS Ready" if self.is_tts_available else "TTS Unavailable"
        stt_part = "STT Ready" if self.is_stt_available else "STT Model Needed"
        return f"Voice: {tts_part} (Offline) | {stt_part}"

    def speak(self, text: str) -> bool:
        """Speak text aloud using offline TTS."""
        return self.tts.speak(text)

    def speak_async(self, text: str) -> None:
        """Speak text asynchronously in a background worker thread."""
        self.tts.speak_async(text)

    def stop_speaking(self) -> None:
        """Interrupt and silence ongoing speech."""
        self.tts.stop_speaking()

    def listen_command(self, max_duration_sec: float = 6.0) -> Optional[str]:
        """Listen for a single spoken voice command via Push-to-Talk or VAD."""
        return self.recognizer.listen_command_push_to_talk(max_duration_sec=max_duration_sec)

    def process_voice_instruction(self, text: str, speak: bool = True) -> Dict[str, Any]:
        """Execute a recognized text instruction through the full BOLT pipeline and speak results."""
        return self.pipeline.process_spoken_utterance(text, speak_output=speak)

    def listen_and_execute(self, max_duration_sec: float = 6.0) -> Dict[str, Any]:
        """Perform end-to-end voice capture -> task execution -> spoken response."""
        return self.pipeline.listen_and_execute(max_duration_sec=max_duration_sec)

    def feed_mock_speech(self, text: str) -> None:
        """Feed simulated speech input for automated testing and test verification."""
        self.recognizer.feed_mock_speech(text)

    def get_model_status(self) -> Dict[str, Any]:
        """Get model status and setup instructions for offline speech recognition."""
        return self.recognizer.get_model_install_instructions()

    def evaluate_speech_engines(self) -> Dict[str, Any]:
        """Benchmark and evaluate offline STT engines (Vosk vs Faster-Whisper)."""
        return self.recognizer.evaluate_engines()


_VOICE_CONTROLLER_INSTANCE: Optional[VoiceController] = None


def get_voice_controller() -> VoiceController:
    global _VOICE_CONTROLLER_INSTANCE
    if _VOICE_CONTROLLER_INSTANCE is None:
        _VOICE_CONTROLLER_INSTANCE = VoiceController()
    return _VOICE_CONTROLLER_INSTANCE
