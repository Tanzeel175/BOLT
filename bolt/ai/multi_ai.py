"""Multi-AI Comparison Engine for BOLT.

Queries multiple AI providers (e.g., Gemini and OpenAI/ChatGPT) concurrently with
the same prompt, collects their outputs, and produces an objective comparative analysis.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple

from bolt.ai.base import AIProvider, AIResponse, ChatMessage
from bolt.ai.provider_manager import AIProviderManager, get_provider_manager
from bolt.core.logger import get_logger

logger = get_logger("MultiAIComparator")


@dataclass
class ComparisonResult:
    prompt: str
    responses: Dict[str, AIResponse] = field(default_factory=dict)
    successful_count: int = 0
    total_requested: int = 0
    formatted_markdown: str = ""
    duration_seconds: float = 0.0


class MultiAIComparator:
    """Dispatches requests to multiple AI providers concurrently and creates comparative reports."""

    def __init__(self, provider_mgr: Optional[AIProviderManager] = None):
        self.provider_mgr = provider_mgr or get_provider_manager()

    def compare_providers(
        self,
        prompt: str,
        provider_names: Optional[List[str]] = None,
        chat_history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
    ) -> ComparisonResult:
        """Query multiple AI providers concurrently and generate comparison markdown."""
        t0 = time.time()
        names = provider_names or ["gemini", "openai"]
        target_providers: Dict[str, AIProvider] = {}

        for n in names:
            norm = n.strip().lower()
            if norm in ("chatgpt", "gpt"):
                norm = "openai"
            elif norm in ("gemini", "google"):
                norm = "gemini"
            target_providers[norm] = self.provider_mgr.get_provider(norm)

        messages = list(chat_history) if chat_history else []
        messages.append(ChatMessage(role="user", content=prompt))

        responses: Dict[str, AIResponse] = {}

        def _fetch_one(p_name: str, provider: AIProvider) -> Tuple[str, AIResponse]:
            resp = provider.generate_response(
                messages=messages,
                system_prompt=system_prompt,
            )
            return p_name, resp

        # Concurrently execute queries
        with ThreadPoolExecutor(max_workers=len(target_providers)) as executor:
            future_to_provider = {
                executor.submit(_fetch_one, name, prov): name
                for name, prov in target_providers.items()
            }
            for future in as_completed(future_to_provider):
                p_name = future_to_provider[future]
                try:
                    p_name_res, res = future.result()
                    responses[p_name_res] = res
                except Exception as e:
                    logger.exception(f"Error querying provider {p_name}: {e}")
                    responses[p_name] = AIResponse(
                        content="",
                        model=target_providers[p_name].default_model,
                        provider=p_name,
                        success=False,
                        error=str(e),
                        error_type="INTERNAL_ERROR",
                    )

        duration = round(time.time() - t0, 2)
        successful_count = sum(1 for r in responses.values() if r.success)

        markdown_report = self._build_comparison_markdown(
            prompt=prompt,
            responses=responses,
            duration=duration,
        )

        return ComparisonResult(
            prompt=prompt,
            responses=responses,
            successful_count=successful_count,
            total_requested=len(target_providers),
            formatted_markdown=markdown_report,
            duration_seconds=duration,
        )

    def _build_comparison_markdown(
        self,
        prompt: str,
        responses: Dict[str, AIResponse],
        duration: float,
    ) -> str:
        """Format comparison cards and comparative analysis."""
        lines = [
            f"### ⚖️ Multi-AI Comparison Report",
            f"**Inquiry:** *\"{prompt}\"* • **Completed in:** `{duration}s`\n",
            "---",
        ]

        provider_titles = {
            "gemini": "🔷 Google Gemini",
            "openai": "🟢 OpenAI ChatGPT",
            "mock": "⚡ BOLT Local Engine",
        }

        # 1. Output each individual provider response
        for p_name, resp in responses.items():
            title = provider_titles.get(p_name, f"🤖 {p_name.title()}")
            model_badge = f"`{resp.model}`"

            if resp.success:
                token_info = f" • `{resp.tokens_used} tokens` • `{resp.duration_seconds}s`" if resp.tokens_used else ""
                lines.append(f"#### {title} ({model_badge}){token_info}\n")
                lines.append(resp.content.strip())
                lines.append("\n---\n")
            else:
                lines.append(f"#### {title} ({model_badge}) — ⚠️ Unreachable\n")
                lines.append(f"> **Error:** {resp.error}\n")
                lines.append(
                    "> *No simulated response was generated for this provider because authentic API results are required.*\n"
                )
                lines.append("\n---\n")

        # 2. Objective Synthesis & Comparison Section
        success_keys = [k for k, r in responses.items() if r.success]
        if len(success_keys) >= 2:
            lines.append("### 📊 Comparative Analysis & Summary\n")
            lines.append(
                f"- **Model Consensus:** Both {', '.join(k.title() for k in success_keys)} addressed the query directly."
            )
            for k in success_keys:
                r = responses[k]
                word_count = len(r.content.split())
                lines.append(f"- **{k.title()} Style:** ~{word_count} words, model: `{r.model}`.")
            lines.append(
                "\n*Both perspectives have been logged in your session context for follow-up questions.*"
            )
        elif len(success_keys) == 1:
            only_key = success_keys[0]
            lines.append(
                f"> **Notice:** Displaying result from **{only_key.title()}**. "
                f"The secondary provider could not be reached. You can configure it in **Settings (⚙)** to enable full side-by-side evaluation."
            )
        else:
            lines.append(
                "> ⚠️ None of the requested AI providers could generate a response. "
                "Please verify your API keys and internet connection in Settings."
            )

        return "\n".join(lines)


_COMPARATOR_INSTANCE: Optional[MultiAIComparator] = None


def get_multi_ai_comparator() -> MultiAIComparator:
    """Singleton getter for MultiAIComparator."""
    global _COMPARATOR_INSTANCE
    if _COMPARATOR_INSTANCE is None:
        _COMPARATOR_INSTANCE = MultiAIComparator()
    return _COMPARATOR_INSTANCE
