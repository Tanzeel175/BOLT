"""
Internet Search Engine subsystem for BOLT.
Retrieves web search results, extracts titles, URLs, and summaries, and generates search navigation URLs.
"""

import urllib.parse
from typing import Any, Dict, List, Optional
import requests

from bolt.core.logger import get_logger
from bolt.core.network_manager import get_network_manager, OFFLINE_SEARCH_ERROR_MESSAGE

logger = get_logger("SearchEngine")

SEARCH_PROVIDERS = {
    "google": "https://www.google.com/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "github": "https://github.com/search?q={query}",
}


class SearchEngine:
    """Provides search query resolution, online result extraction, and direct search URL synthesis."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    @staticmethod
    def build_search_url(query: str, provider: str = "google") -> str:
        """Construct direct search URL for a specified engine."""
        prov_key = provider.lower().strip()
        template = SEARCH_PROVIDERS.get(prov_key, SEARCH_PROVIDERS["google"])
        encoded = urllib.parse.quote_plus(query.strip())
        return template.format(query=encoded)

    def search_online(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Execute an online search query.
        Uses DuckDuckGo Instant Topic / Related Topic API + structured fallback.
        Returns list of {title, url, snippet}.
        Raises ConnectionError if internet is unavailable.
        """
        net_mgr = get_network_manager()
        if not net_mgr.is_internet_available():
            logger.warning("Search aborted: No internet connectivity detected.")
            raise ConnectionError(OFFLINE_SEARCH_ERROR_MESSAGE)

        logger.info(f"Executing web search for: '{query}'")
        clean_query = query.strip()
        results: List[Dict[str, str]] = []

        # 1. Query DuckDuckGo Instant Answer API
        try:
            api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(clean_query)}&format=json&no_html=1&skip_disambig=0"
            resp = self.session.get(api_url, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()

                # Primary Abstract
                heading = data.get("Heading", "")
                abstract = data.get("AbstractText", "")
                abstract_url = data.get("AbstractURL", "")

                if abstract and heading:
                    results.append({
                        "title": heading,
                        "url": abstract_url or self.build_search_url(clean_query, "google"),
                        "snippet": abstract,
                    })

                # Related Topics
                for topic in data.get("RelatedTopics", []):
                    if len(results) >= max_results:
                        break
                    # Sometimes topics are grouped inside 'Topics' list
                    if "Topics" in topic:
                        for sub_t in topic["Topics"]:
                            if len(results) >= max_results:
                                break
                            if "Text" in sub_t and "FirstURL" in sub_t:
                                results.append({
                                    "title": sub_t.get("Text", "").split(" - ")[0],
                                    "url": sub_t.get("FirstURL", ""),
                                    "snippet": sub_t.get("Text", ""),
                                })
                    elif "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })
        except Exception as e:
            logger.warning(f"Instant API query failed: {e}")

        # 2. If results are sparse, add direct search destination links
        if len(results) < max_results:
            google_url = self.build_search_url(clean_query, "google")
            results.append({
                "title": f"Google Search: \"{clean_query}\"",
                "url": google_url,
                "snippet": f"View complete real-time web results for '{clean_query}' on Google Search.",
            })

            youtube_url = self.build_search_url(clean_query, "youtube")
            results.append({
                "title": f"YouTube Video Results: \"{clean_query}\"",
                "url": youtube_url,
                "snippet": f"Watch video tutorials, demonstrations, and guides for '{clean_query}' on YouTube.",
            })

        logger.info(f"Retrieved {len(results)} search items for '{query}'")
        return results[:max_results]

    def format_results_markdown(self, query: str, results: List[Dict[str, str]], provider: str = "google") -> str:
        """Format search results into clean, readable GitHub-style Markdown."""
        search_url = self.build_search_url(query, provider)
        lines = [
            f"### 🔍 Web Search Results: *\"{query}\"*\n",
            f"Direct Search Link: [{provider.title()} Search]({search_url})\n",
        ]

        for i, item in enumerate(results, 1):
            title = item.get("title", f"Result #{i}")
            url = item.get("url", "#")
            snippet = item.get("snippet", "")
            lines.append(f"**{i}. [{title}]({url})**")
            if snippet:
                lines.append(f"> {snippet}\n")
            else:
                lines.append(f"> `{url}`\n")

        return "\n".join(lines)


_SEARCH_ENGINE_INSTANCE: Optional[SearchEngine] = None


def get_search_engine() -> SearchEngine:
    """Singleton getter for SearchEngine."""
    global _SEARCH_ENGINE_INSTANCE
    if _SEARCH_ENGINE_INSTANCE is None:
        _SEARCH_ENGINE_INSTANCE = SearchEngine()
    return _SEARCH_ENGINE_INSTANCE

