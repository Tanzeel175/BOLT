"""Offline/Local fallback provider for BOLT."""

import platform
import time
from typing import Iterator, List, Optional, Tuple

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("MockProvider")


class MockProvider(AIProvider):
    """Local offline assistant engine providing diagnostics, guidance, and offline support."""

    def __init__(self, model: str = "bolt-local-mock-v1"):
        self.model = model or "bolt-local-mock-v1"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def display_name(self) -> str:
        return "Local / Mock Mode (Offline)"

    @property
    def available_models(self) -> List[str]:
        return ["bolt-local-mock-v1", "bolt-diagnostics"]

    @property
    def default_model(self) -> str:
        return "bolt-local-mock-v1"

    @property
    def is_configured(self) -> bool:
        return True

    def get_configuration_help(self) -> str:
        return (
            "Local / Mock Mode requires no configuration and functions fully offline. "
            "To connect to cloud AI models, configure Google Gemini or OpenAI in Settings (⚙)."
        )

    def generate_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        t0 = time.time()
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
                f"Features available in your system:\n"
                f"- 💬 **Real-time conversation** with full markdown support.\n"
                f"- 🧠 **AI Provider System:** Switch between Gemini, OpenAI, or local offline mode.\n"
                f"- 🖥️ **Windows 11 Control:** App discovery, window switching, hardware diagnostics.\n"
                f"- 🌐 **Browser Intelligence:** Multi-tab browsing, live search, website reading.\n"
                f"- 🗄️ **Persistent Memory:** Conversations and computer knowledge stored in SQLite.\n\n"
                f"To connect directly to Gemini or OpenAI, click the **Settings (⚙)** button in the top bar!"
            )
        elif any(w in query_lower for w in ["setting", "key", "api", "config"]):
            response_text = (
                f"### 🔑 How to configure your AI API:\n\n"
                f"1. Click the **⚙ Settings** button in the top right corner.\n"
                f"2. Select your AI Provider (**Google Gemini** or **OpenAI**).\n"
                f"3. Paste your API key (get a free Gemini key at [Google AI Studio](https://aistudio.google.com/)).\n"
                f"4. Click **🔌 Test Connection** and then **💾 Save Configuration**.\n\n"
                f"Keys are stored securely in `.env` and masked inside the interface."
            )
        elif any(w in query_lower for w in ["c++", "recursion", "code", "python"]):
            response_text = (
                f"### 💻 Technical Explanation (Local Mock Engine)\n\n"
                f"Here is an overview of your programming inquiry: *\"{last_message}\"*\n\n"
                f"```python\n"
                f"def example_recursive(n):\n"
                f"    if n <= 1: return 1\n"
                f"    return n * example_recursive(n - 1)\n"
                f"```\n\n"
                f"- **Base Case:** Stops endless execution.\n"
                f"- **Recursive Step:** Progresses toward termination.\n\n"
                f"> *Note: Connect Gemini or OpenAI in Settings to receive live, real-time code synthesis.*"
            )
        else:
            response_text = (
                f"### ⚡ BOLT Local Engine\n\n"
                f"I received your request: *\"{last_message}\"*\n\n"
                f"You are currently using BOLT's **Local / Mock Mode**.\n"
                f"To receive full natural language intelligence and dynamic cloud completions:\n"
                f"1. Open **Settings (⚙)**\n"
                f"2. Add your **Google Gemini** or **OpenAI** API key\n"
                f"3. Switch the active provider to Gemini or OpenAI."
            )

        words = response_text.split()
        tokens = int(len(words) * 1.3)
        duration = round(time.time() - t0, 3)

        return AIResponse(
            content=response_text,
            model=self.model,
            provider=self.provider_name,
            tokens_used=tokens,
            prompt_tokens=int(len(last_message.split()) * 1.3),
            completion_tokens=tokens,
            success=True,
            duration_seconds=duration,
        )

    def stream_response(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        full_resp = self.generate_response(messages, system_prompt, temperature, max_tokens)
        chunks = full_resp.content.split(" ")
        for c in chunks:
            yield c + " "

    def test_connection(self) -> Tuple[bool, str]:
        return True, "Local/Mock provider is always connected (offline mode)."
