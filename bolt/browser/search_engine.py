"""
Internet Search Engine for BOLT (Phase 3).
Executes live online searches, extracts structured titles, URLs, and summaries,
formats search results for chat rendering, and launches search queries in browsers.
"""

import base64
import re
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from bolt.core.logger import get_logger

logger = get_logger("SearchEngine")


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


@dataclass
class SearchResponse:
    query: str
    provider: str
    total_results: int
    items: List[SearchResultItem]
    markdown_content: str
    search_url: str


class SearchEngine:
    """Live web search provider for BOLT."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    @staticmethod
    def clean_bing_redirect(raw_url: str) -> str:
        """Decode Bing's redirect link parameter u=a1<base64> to obtain direct website URL."""
        if "bing.com/ck/a?" in raw_url and "u=" in raw_url:
            try:
                parsed = urllib.parse.urlparse(raw_url)
                qs = urllib.parse.parse_qs(parsed.query)
                u_param = qs.get("u", [""])[0]
                if u_param.startswith("a1"):
                    base64_str = u_param[2:]
                    # Fix padding if necessary
                    rem = len(base64_str) % 4
                    if rem:
                        base64_str += "=" * (4 - rem)
                    decoded = base64.b64decode(base64_str).decode("utf-8", errors="ignore")
                    if decoded.startswith("http"):
                        return decoded
            except Exception:
                pass
        return raw_url

    def search_web(self, query: str, max_results: int = 5) -> SearchResponse:
        """
        Execute live web search for a query and return structured search items.
        Extracts verified titles, URLs, and contextual snippets.
        """
        clean_query = query.strip()
        encoded_query = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.bing.com/search?q={encoded_query}"

        items: List[SearchResultItem] = []
        logger.info(f"Executing web search for: '{clean_query}'")

        try:
            resp = requests.get(search_url, headers=self.HEADERS, timeout=12.0)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for li in soup.select("li.b_algo"):
                    if len(items) >= max_results:
                        break

                    h2 = li.select_one("h2 a")
                    if not h2:
                        continue

                    title = h2.get_text(strip=True)
                    raw_href = h2.get("href", "")
                    clean_url = self.clean_bing_redirect(raw_href)

                    # Extract snippet
                    snippet_el = li.select_one(".b_caption p") or li.select_one(".b_snippet")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if title and clean_url and clean_url.startswith("http"):
                        items.append(SearchResultItem(title=title, url=clean_url, snippet=snippet))

        except Exception as e:
            logger.error(f"Search request failed for '{clean_query}': {e}")

        # Format markdown response
        if items:
            rows = []
            for i, it in enumerate(items, 1):
                snippet_text = f"\n  *{it.snippet}*" if it.snippet else ""
                rows.append(f"{i}. **[{it.title}]({it.url})**{snippet_text}\n  `{it.url}`")

            markdown = (
                f"### 🔍 Search Results for: *\"{clean_query}\"*\n\n"
                + "\n\n".join(rows)
                + f"\n\n---\n*Found {len(items)} web results via Bing Search. Ask BOLT to open any result.*"
            )
        else:
            markdown = (
                f"### 🔍 Web Search for: *\"{clean_query}\"*\n\n"
                f"I prepared a live search on your default browser:\n"
                f"- [Open Search in Browser]({search_url})\n\n"
                f"No instant snippets were returned from the automated endpoint."
            )

        return SearchResponse(
            query=clean_query,
            provider="Bing Search",
            total_results=len(items),
            items=items,
            markdown_content=markdown,
            search_url=search_url,
        )

    @staticmethod
    def get_search_url_for_provider(provider: str, query: str) -> str:
        """Construct a search query URL for a specific provider (Google, YouTube, Bing)."""
        clean_query = urllib.parse.quote_plus(query.strip())
        p_lower = provider.strip().lower()

        if "youtube" in p_lower:
            return f"https://www.youtube.com/results?search_query={clean_query}"
        elif "google" in p_lower:
            return f"https://www.google.com/search?q={clean_query}"
        elif "duck" in p_lower:
            return f"https://duckduckgo.com/?q={clean_query}"
        else:
            return f"https://www.bing.com/search?q={clean_query}"


_SEARCH_ENGINE: Optional[SearchEngine] = None


def get_search_engine() -> SearchEngine:
    global _SEARCH_ENGINE
    if _SEARCH_ENGINE is None:
        _SEARCH_ENGINE = SearchEngine()
    return _SEARCH_ENGINE

