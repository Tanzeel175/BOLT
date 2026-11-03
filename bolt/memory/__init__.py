"""
BOLT Persistent Long-Term Memory and Continuous Learning Subsystem (Phase 8).
Exports the memory manager, categories, data models, and retrieval components.
"""

from bolt.memory.manager import MemoryManager, get_memory_manager
from bolt.memory.models import (
    CorrectionRecord,
    ExtractedContext,
    MemoryCategory,
    MemoryItem,
)
from bolt.memory.retriever import MemoryRetriever
from bolt.memory.corrections import CorrectionHandler
from bolt.memory.context_extractor import ConversationContextExtractor

__all__ = [
    "MemoryManager",
    "get_memory_manager",
    "MemoryCategory",
    "MemoryItem",
    "CorrectionRecord",
    "ExtractedContext",
    "MemoryRetriever",
    "CorrectionHandler",
    "ConversationContextExtractor",
]

