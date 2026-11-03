"""
Lightweight offline memory retrieval system for BOLT (Phase 8).
Combines SQLite FTS5 BM25 search, token-overlap similarity, and relevance gating.
Operates 100% locally on CPU with zero online embedding APIs.
Ensures unrelated memories are never retrieved.
"""

import math
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from bolt.core.logger import get_logger
from bolt.memory.models import MemoryCategory, MemoryItem

logger = get_logger("MemoryRetriever")

# Common English stopwords to ignore when extracting task intent keywords
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "don't", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "won't", "would", "you", "your", "yours", "yourself",
    "yourselves", "please", "can", "could", "bolt", "hey",
}

# Domain semantic synonym expansion for common computer assistant phrases
INTENT_SYNONYMS: Dict[str, List[str]] = {
    "programming": ["coding", "developer", "ide", "editor", "code", "programming_app", "visual studio", "vscode", "pycharm"],
    "coding": ["programming", "developer", "ide", "editor", "code", "vscode"],
    "browser": ["web", "internet", "chrome", "edge", "brave", "firefox", "website", "online"],
    "usual": ["preferred", "favorite", "default", "standard"],
    "notes": ["notepad", "text", "memo", "obsidian", "editor"],
    "documents": ["docs", "word", "pdf", "folder", "assignments"],
    "environment": ["app", "workspace", "application", "tool"],
}


class MemoryRetriever:
    """Retrieves relevant memories using offline FTS5 BM25 and semantic token overlap."""

    def __init__(self, conn_getter):
        self._get_connection = conn_getter

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract meaningful alphanumeric search tokens, filtering stopwords."""
        clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower().replace("_", " "))
        tokens = [t.strip() for t in clean.split() if len(t.strip()) > 1]
        return [t for t in tokens if t not in STOPWORDS]

    def expand_query_terms(self, tokens: List[str]) -> Set[str]:
        """Expand tokens with domain-specific synonyms to bridge natural language gaps."""
        expanded = set(tokens)
        for t in tokens:
            if t in INTENT_SYNONYMS:
                expanded.update(INTENT_SYNONYMS[t])
        return expanded

    def score_memory_relevance(
        self,
        query_terms: Set[str],
        item: MemoryItem,
    ) -> float:
        """
        Calculate a normalized semantic relevance score (0.0 to 1.0).
        Evaluates exact key matches, partial key matches, content overlap, and importance.
        """
        if not query_terms:
            return 0.0

        key_tokens = set(self.extract_keywords(item.key.replace("_", " ")))
        content_tokens = set(self.extract_keywords(item.content))
        all_item_tokens = key_tokens.union(content_tokens)

        if not all_item_tokens:
            return 0.0

        # 1. Exact key token match bonus
        key_matches = query_terms.intersection(key_tokens)
        key_score = (len(key_matches) / max(len(key_tokens), 1)) * 0.60

        # Exact substring or key containment bonus
        key_str = item.key.replace("_", " ").lower()
        if any(t in key_str for t in query_terms):
            key_score += 0.20

        # 2. Content token match bonus
        content_matches = query_terms.intersection(content_tokens)
        content_score = (len(content_matches) / max(len(query_terms), 1)) * 0.20

        # 3. Frequency & importance weighting
        importance_bonus = min(item.importance * 0.05, 0.05)

        total_score = key_score + content_score + importance_bonus
        return min(total_score, 1.0)

    def retrieve_for_instruction(
        self,
        instruction: str,
        category: Optional[str] = None,
        limit: int = 3,
        min_relevance: float = 0.28,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve relevant memories for an instruction.
        CRITICAL: Applies min_relevance threshold so unrelated memories are discarded.
        """
        tokens = self.extract_keywords(instruction)
        if not tokens:
            return []

        expanded_terms = self.expand_query_terms(tokens)
        conn = self._get_connection()

        candidates: List[MemoryItem] = []
        try:
            cursor = conn.cursor()
            # 1. Attempt FTS5 full-text search first if available
            fts_query_parts = [f'"{t}"' for t in tokens if len(t) > 2]
            if fts_query_parts:
                fts_expr = " OR ".join(fts_query_parts)
                try:
                    if category:
                        cat_norm = MemoryCategory.normalize(category)
                        cursor.execute(
                            """
                            SELECT m.* FROM bolt_memories m
                            JOIN bolt_memories_fts f ON m.rowid = f.rowid
                            WHERE bolt_memories_fts MATCH ? AND m.category = ?
                            LIMIT 20;
                            """,
                            (fts_expr, cat_norm),
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT m.* FROM bolt_memories m
                            JOIN bolt_memories_fts f ON m.rowid = f.rowid
                            WHERE bolt_memories_fts MATCH ?
                            LIMIT 20;
                            """,
                            (fts_expr,),
                        )
                    for row in cursor.fetchall():
                        candidates.append(MemoryItem.from_row(row))
                except Exception as e:
                    logger.debug(f"FTS5 query failed or not ready, using direct query: {e}")

            # 2. Fetch category items if candidates empty or category specified
            if not candidates:
                if category:
                    cat_norm = MemoryCategory.normalize(category)
                    cursor.execute(
                        "SELECT * FROM bolt_memories WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT 30;",
                        (cat_norm,),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM bolt_memories ORDER BY importance DESC, updated_at DESC LIMIT 60;"
                    )
                for row in cursor.fetchall():
                    candidates.append(MemoryItem.from_row(row))

        finally:
            conn.close()

        # Score and filter candidates
        scored: List[Tuple[MemoryItem, float]] = []
        seen_keys = set()

        for item in candidates:
            if item.key in seen_keys:
                continue
            seen_keys.add(item.key)

            score = self.score_memory_relevance(expanded_terms, item)
            if score >= min_relevance:
                scored.append((item, score))

        # Sort by relevance score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
