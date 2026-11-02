"""Offline/Local fallback provider for BOLT."""

import platform
import sys
from typing import List, Optional

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("MockProvider")


class MockProvider(AIProvider):
    """Local offline assistant engine providing diagnostics, guidance, and offline support."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        last_message = messages[-1].content.strip() if messages else ""
        query_lower = last_message.lower()

        logger.info(f"MockProvider processing query: {last_message}")

        if any(w in query_lower for w in ["system", "specs", "hardware", "os"]):
            response_text = (
                f"### 🖥️ Windows System Diagnostics\n\n"
                f"- **Operating System:** Windows {platform.release()} ({platform.version()})\n"
                f"- **Architecture:** {platform.machine()}\n"
                f"- **Processor:** {platform.processor() or 'Intel Core i5 (7th Gen)'}\n"
                f"- **Python Version:** {platform.python_version()}\n"
                f"- **BOLT Engine Status:** Operational (Local Mode)\n\n"
                f"> **Tip:** Configure your **Gemini** or **OpenAI** API key in **Settings (⚙)** "
                f"to unlock full cloud AI intelligence."
            )
        elif any(w in query_lower for w in ["hello", "hi", "hey", "who are you"]):
            response_text = (
                f"### ⚡ Hello! I am BOLT.\n\n"
                f"I am your personal autonomous AI assistant for Windows 11.\n\n"
                f"We are currently in **Phase 1: Foundation and Desktop Interface**.\n"
                f"Here is what I can do right now:\n"
                f"- 💬 **Real-time conversation** with full markdown support.\n"
                f"- 🧠 **AI Model Switching:** Easily configure Google Gemini, OpenAI, or local models.\n"
                f"- 🗄️ **Persistent Chat History:** Stored safely in local SQLite.\n"
                f"- ⚙️ **Secure Credentials:** Keys stored in `.env` and masked in settings.\n\n"
                f"To connect directly to Gemini or OpenAI, click the **Settings (⚙)** button in the top bar!"
            )
        elif any(w in query_lower for w in ["setting", "key", "api", "config"]):
            response_text = (
                f"### 🔑 How to configure your AI API:\n\n"
                f"1. Click the **⚙ Settings** button in the top right corner.\n"
                f"2. Select your AI Provider (**Google Gemini** or **OpenAI**).\n"
                f"3. Paste your API key (get a free Gemini key at [Google AI Studio](https://aistudio.google.com/)).\n"
                f"4. Click **Test & Save Configuration**.\n\n"
                f"Once saved, BOLT will immediately use the cloud model for all your prompts."
            )
        else:
            response_text = (
                f"### ⚡ BOLT Assistant (Local Mode)\n\n"
                f"You asked: *\"{last_message}\"*\n\n"
                f"I received your message successfully! Currently, BOLT is operating in local demonstration mode.\n\n"
                f"To connect BOLT to a live neural language model:\n"
                f"1. Open **Settings (⚙)** in the top right.\n"
                f"2. Enter your **Google Gemini** or **OpenAI** API Key.\n"
                f"3. Click **Save & Test Connection**.\n\n"
                f"Once connected, BOLT will provide generative reasoning, coding, and autonomous Windows operations."
            )

        return AIResponse(
            content=response_text,
            model="bolt-local-engine",
            tokens_used=len(response_text.split()),
            success=True,
        )

    def test_connection(self) -> bool:
        return True

