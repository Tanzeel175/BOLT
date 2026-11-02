"""AI Response and Workflow Task Manager for BOLT.

Handles formatting, metadata attribution, token summaries, and prepares structured
drafts and diagnostic responses for future approval-gated automated workflows.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import time

from bolt.ai.base import AIResponse, ChatMessage
from bolt.core.logger import get_logger

logger = get_logger("AIResponseManager")


@dataclass
class WorkflowArtifact:
    artifact_type: str  # "email_draft", "code_explanation", "summary", "general"
    title: str
    content: str
    provider: str
    model: str
    is_ready_for_approval: bool = False
    created_at: float = 0.0


class AIResponseManager:
    """Manages AI responses, formatting, and workflow artifact preparation."""

    def __init__(self):
        self._artifacts: List[WorkflowArtifact] = []

    def format_assistant_message(
        self,
        response: AIResponse,
        original_prompt: str = "",
    ) -> str:
        """Format an AIResponse into clean, richly annotated Markdown for chat display."""
        if not response.success:
            return self.format_error_card(response)

        content = response.content.strip()

        # Check if the prompt was an explicit workflow request (e.g. Email draft)
        prompt_lower = original_prompt.lower()
        if any(w in prompt_lower for w in ["write an email", "draft an email", "email requesting", "professional email"]):
            artifact = WorkflowArtifact(
                artifact_type="email_draft",
                title="Professional Email Draft",
                content=content,
                provider=response.provider,
                model=response.model,
                is_ready_for_approval=True,
                created_at=time.time(),
            )
            self._artifacts.append(artifact)
            return (
                f"{content}\n\n"
                f"> 📋 **Workflow Prepared:** Email draft has been structured and retained in memory. "
                f"*(Note: External dispatch remains subject to Phase 9 Approval System)*"
            )

        elif any(w in prompt_lower for w in ["explain this python error", "explain this error", "diagnose error", "python error"]):
            artifact = WorkflowArtifact(
                artifact_type="code_explanation",
                title="Python Error Diagnosis",
                content=content,
                provider=response.provider,
                model=response.model,
                is_ready_for_approval=False,
                created_at=time.time(),
            )
            self._artifacts.append(artifact)
            return content

        return content

    def format_error_card(self, response: AIResponse) -> str:
        """Produce an actionable, beautifully styled error card when a provider fails."""
        provider_name = response.provider.title() or "AI Provider"
        err_type = response.error_type or "PROVIDER_ERROR"
        err_msg = response.error or "Unknown error occurred."

        lines = [
            f"### ⚠️ {provider_name} Request Failed",
            f"**Error Code:** `{err_type}`\n",
            f"**Details:** {err_msg}\n",
            "**Recommended Resolution:**",
        ]

        if err_type == "MISSING_KEY":
            lines.extend([
                f"- Open **Settings (⚙)** in the top bar.",
                f"- Paste your API key for **{provider_name}**.",
                f"- Alternatively, switch to **Local / Mock Mode** for offline assistance.",
            ])
        elif err_type == "INVALID_KEY":
            lines.extend([
                f"- Verify that your API key is active and correctly pasted without extra spaces.",
                f"- For Gemini: test or generate a new key at [Google AI Studio](https://aistudio.google.com/).",
                f"- For OpenAI: verify credentials at [OpenAI API Keys](https://platform.openai.com/api-keys).",
            ])
        elif err_type == "RATE_LIMIT":
            lines.extend([
                f"- Provider rate limit or quota has been reached.",
                f"- Please wait a moment before sending another message or switch to an alternate provider.",
            ])
        elif err_type in ("NETWORK_ERROR", "TIMEOUT"):
            lines.extend([
                f"- Check your internet connection.",
                f"- Verify if any firewall or corporate proxy is blocking outbound HTTPS requests.",
            ])
        else:
            lines.extend([
                f"- Verify your provider settings and model availability.",
                f"- Test provider connectivity in Settings (⚙).",
            ])

        return "\n".join(lines)

    def get_recent_artifacts(self) -> List[WorkflowArtifact]:
        """Return prepared workflow artifacts."""
        return list(self._artifacts)


_RESPONSE_MGR_INSTANCE: Optional[AIResponseManager] = None


def get_response_manager() -> AIResponseManager:
    """Singleton getter for AIResponseManager."""
    global _RESPONSE_MGR_INSTANCE
    if _RESPONSE_MGR_INSTANCE is None:
        _RESPONSE_MGR_INSTANCE = AIResponseManager()
    return _RESPONSE_MGR_INSTANCE

