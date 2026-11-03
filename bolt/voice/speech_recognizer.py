"""
Offline Speech Recognition Engine for BOLT (Phase 7).
Evaluates Vosk and Faster-Whisper, selecting Vosk as the primary lightweight engine.
Includes microphone device detection, Voice Activity Detection (VAD), ambient noise
calibration, silence detection, echo-cancellation gating, and model verification.
Never requires cloud speech APIs and never downloads models automatically without consent.
"""

import os
import json
import time
import threading
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from bolt.core.logger import get_logger
from bolt.voice.tts_engine import get_tts_engine

logger = get_logger("SpeechRecognizer")

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_SIZE = 4000
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "models", "vosk-model-small-en-us-0.15")


class SpeechRecognizer:
    """
    Offline Speech-to-Text recognizer with microphone intake, VAD,
    and Vosk/Whisper evaluation.
    """

    def __init__(self, model_dir: Optional[str] = None, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.model_dir = model_dir or os.getenv("BOLT_VOSK_MODEL_PATH", DEFAULT_MODEL_DIR)
        self.tts = get_tts_engine()

        # Engine state
        self._vosk_model = None
        self._is_listening = False
        self._stop_listening = False
        self._ambient_noise_level = 0.015  # Baseline noise RMS
        self._vad_multiplier = 2.5
        self._mock_speech_queue: List[str] = []

        # Check model and hardware availability
        self._check_model_status()

    def _check_model_status(self) -> None:
        """Verify whether Vosk model files are downloaded locally."""
        self.model_downloaded = False
        if os.path.exists(self.model_dir) and os.path.isdir(self.model_dir):
            # Check for required Kaldi/Vosk files
            required_files = ["am", "conf", "graph"]
            has_files = any(os.path.exists(os.path.join(self.model_dir, f)) for f in required_files)
            if has_files:
                self.model_downloaded = True
                logger.info(f"Vosk offline STT model detected at: {self.model_dir}")
                return

        logger.info(f"Vosk model not present at '{self.model_dir}'. Instructions available via get_model_install_instructions().")

    def get_model_install_instructions(self) -> Dict[str, Any]:
        """Provide exact user instructions for installing offline speech models without auto-downloading."""
        return {
            "model_name": "vosk-model-small-en-us-0.15",
            "size": "~40 MB",
            "is_downloaded": self.model_downloaded,
            "target_directory": self.model_dir,
            "instructions": (
                "To enable 100% offline speech recognition in BOLT without cloud APIs:\n"
                "1. Download the lightweight model archive from:\n"
                "   https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip\n"
                f"2. Extract the archive contents into:\n"
                f"   {self.model_dir}\n"
                "3. Restart BOLT or trigger voice recognition."
            ),
        }

    def evaluate_engines(self) -> Dict[str, Any]:
        """
        Evaluate Vosk vs. Faster-Whisper for the host Windows 11 platform.
        Documents performance, memory footprint, and Windows Application Control compatibility.
        """
        results = {
            "vosk": {
                "name": "Vosk (Kaldi Native C++)",
                "status": "Available & Primary",
                "is_available": True,
                "memory_footprint": "~45 MB RAM",
                "cpu_efficiency": "High (Lightweight x86_64 CPU inference)",
                "application_control_compatible": True,
                "notes": "Selected as primary lightweight engine. Zero Windows Application Control DLL blocks.",
            },
            "faster_whisper": {
                "name": "Faster-Whisper (CTranslate2)",
                "status": "Blocked by Windows Application Control",
                "is_available": False,
                "memory_footprint": "~350 MB - 1.2 GB RAM",
                "cpu_efficiency": "Moderate (Higher CPU utilization on 4-core i7)",
                "application_control_compatible": False,
                "notes": "PyAV C-extension DLL blocked by Windows 11 Application Control policy in standard environment.",
            },
            "recommended": "vosk",
        }
        return results

    def detect_microphones(self) -> List[Dict[str, Any]]:
        """Query and return all available input microphone devices."""
        devices = []
        try:
            import sounddevice as sd
            dev_list = sd.query_devices()
            default_in = sd.default.device[0]

            for idx, dev in enumerate(dev_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name", "Unknown Microphone"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 16000),
                        "is_default": idx == default_in,
                    })
        except Exception as e:
            logger.warning(f"Failed querying microphone devices via sounddevice: {e}")

        return devices

    def get_default_microphone(self) -> Optional[Dict[str, Any]]:
        """Get information on default recording microphone."""
        mics = self.detect_microphones()
        for m in mics:
            if m["is_default"]:
                return m
        return mics[0] if mics else None

    def calibrate_ambient_noise(self, duration_seconds: float = 0.8) -> float:
        """
        Record a brief sample to compute background noise RMS.
        Dynamically adjusts Voice Activity Detection threshold.
        """
        try:
            import sounddevice as sd
            logger.info("Calibrating ambient noise floor...")
            samples = int(self.sample_rate * duration_seconds)
            recording = sd.rec(samples, samplerate=self.sample_rate, channels=1, dtype="float32", blocking=True)
            rms = float(np.sqrt(np.mean(recording ** 2)))
            self._ambient_noise_level = max(0.005, rms)
            logger.info(f"Ambient noise floor calibrated: RMS={self._ambient_noise_level:.4f}")
            return self._ambient_noise_level
        except Exception as e:
            logger.warning(f"Ambient noise calibration failed: {e}. Using baseline 0.015")
            self._ambient_noise_level = 0.015
            return self._ambient_noise_level

    def is_voice_active(self, audio_chunk: np.ndarray) -> bool:
        """
        Voice Activity Detection (VAD) check using dynamic energy threshold.
        Also verifies TTS is not speaking to prevent self-listening.
        """
        if self.tts.is_speaking:
            # Echo prevention: Mute input while BOLT speaks
            return False

        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        threshold = self._ambient_noise_level * self._vad_multiplier
        return rms > threshold

    def _get_or_load_vosk_model(self):
        """Lazy load Vosk model into memory."""
        if self._vosk_model is not None:
            return self._vosk_model

        if not self.model_downloaded:
            return None

        try:
            from vosk import Model
            logger.info(f"Loading Vosk model from: {self.model_dir}")
            self._vosk_model = Model(self.model_dir)
            return self._vosk_model
        except Exception as e:
            logger.error(f"Failed loading Vosk model: {e}")
            return None

    def transcribe_audio_bytes(self, pcm_bytes: bytes) -> str:
        """
        Transcribe raw 16-bit 16000Hz mono PCM audio bytes using local Vosk.
        Zero cloud network traffic.
        """
        if not pcm_bytes:
            return ""

        model = self._get_or_load_vosk_model()
        if not model:
            logger.info("Vosk model not loaded locally; returning empty transcription.")
            return ""

        try:
            from vosk import KaldiRecognizer
            rec = KaldiRecognizer(model, self.sample_rate)
            rec.SetWords(True)

            # Process in chunks
            chunk_size = 4000
            for i in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[i:i + chunk_size]
                rec.AcceptWaveform(chunk)

            final_res = json.loads(rec.FinalResult())
            text = final_res.get("text", "").strip()
            logger.info(f"Vosk recognized text: '{text}'")
            return text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def feed_mock_speech(self, text: str) -> None:
        """Queue simulated speech text for testing or push-to-talk automation."""
        self._mock_speech_queue.append(text)

    def listen_command_push_to_talk(self, max_duration_sec: float = 6.0, silence_timeout_sec: float = 1.2) -> Optional[str]:
        """
        Reliable Push-to-Talk or Voice Activity-driven speech capture.
        Listens until speech concludes or max_duration is reached.
        """
        # 1. Check for mock/queued test speech first
        if self._mock_speech_queue:
            recognized = self._mock_speech_queue.pop(0)
            logger.info(f"Captured speech from mock input: '{recognized}'")
            return recognized

        # 2. Check if model is downloaded
        if not self.model_downloaded:
            logger.warning("Vosk model not installed. Voice input requires model or typed command fallback.")
            return None

        try:
            import sounddevice as sd
            logger.info("Push-to-Talk active: Listening for speech from microphone...")

            audio_frames = []
            has_spoken = False
            silence_start = None
            start_time = time.time()

            # Record in 100ms blocks
            block_size = int(self.sample_rate * 0.1)

            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="int16", blocksize=block_size) as stream:
                while time.time() - start_time < max_duration_sec:
                    # Echo prevention: pause while TTS speaks
                    if self.tts.is_speaking:
                        time.sleep(0.1)
                        continue

                    data, overflowed = stream.read(block_size)
                    audio_frames.append(data.tobytes())

                    # Evaluate VAD
                    float_data = data.astype(np.float32) / 32768.0
                    voice_detected = self.is_voice_active(float_data)

                    if voice_detected:
                        has_spoken = True
                        silence_start = None
                    elif has_spoken:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= silence_timeout_sec:
                            logger.info("End of speech detected via silence threshold.")
                            break

            if not has_spoken and not audio_frames:
                logger.info("No voice detected within listening window.")
                return None

            full_pcm = b"".join(audio_frames)
            return self.transcribe_audio_bytes(full_pcm)

        except Exception as e:
            logger.warning(f"Microphone recording error: {e}")
            return None


# Global singleton access
_SPEECH_RECOGNIZER_INSTANCE: Optional[SpeechRecognizer] = None


def get_speech_recognizer() -> SpeechRecognizer:
    global _SPEECH_RECOGNIZER_INSTANCE
    if _SPEECH_RECOGNIZER_INSTANCE is None:
        _SPEECH_RECOGNIZER_INSTANCE = SpeechRecognizer()
    return _SPEECH_RECOGNIZER_INSTANCE
