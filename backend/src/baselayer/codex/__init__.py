"""
BaseLayer Codex/Memory Module

Knowledge management, search, and AI integration
for the Codex/Memory subsystem.
"""

from .engine import KnowledgeEngine
from .search import SearchEngine
from .indexer import KnowledgeIndexer
from .extractor import KnowledgeExtractor
from .analyzer import KnowledgeAnalyzer
from .exceptions import (
    CodexError,
    KnowledgeNotFoundError,
    SearchError,
    IndexError,
    ExtractionError,
    AnalysisError,
)

__all__ = [
    # Core components
    "KnowledgeEngine",
    "SearchEngine",
    "KnowledgeIndexer",
    "KnowledgeExtractor",
    "KnowledgeAnalyzer",
    # Exceptions
    "CodexError",
    "KnowledgeNotFoundError",
    "SearchError",
    "IndexError",
    "ExtractionError",
    "AnalysisError",
]
