"""
BaseLayer Memory Interface

Abstract interface for Codex integration.
Provides contract for knowledge storage and retrieval.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MemoryInterface(ABC):
    """
    Abstract interface for memory/knowledge storage.
    
    This interface defines the contract that all engines
    use to interact with the Codex knowledge system.
    Concrete implementations will be provided by Engine 5.
    """
    
    @abstractmethod
    async def store(
        self,
        key: str,
        value: Any,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        source: Optional[str] = None
    ) -> bool:
        """
        Store a value in memory.
        
        Args:
            key: Unique key for the value
            value: Value to store
            tags: Optional list of tags for categorization
            confidence: Confidence score (0.0-1.0)
            source: Optional source identifier
            
        Returns:
            True if stored successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        key: str
    ) -> Optional[Any]:
        """
        Retrieve a value by key.
        
        Args:
            key: Key to retrieve
            
        Returns:
            Stored value or None if not found
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memory by query and tags.
        
        Args:
            query: Search query
            tags: Optional list of tags to filter by
            limit: Maximum number of results
            
        Returns:
            List of search results with metadata
        """
        pass
    
    @abstractmethod
    async def update(
        self,
        key: str,
        value: Any,
        confidence: Optional[float] = None
    ) -> bool:
        """
        Update an existing value.
        
        Args:
            key: Key to update
            value: New value
            confidence: Optional new confidence score
            
        Returns:
            True if updated successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        key: str
    ) -> bool:
        """
        Delete a value by key.
        
        Args:
            key: Key to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def search_semantic(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memory semantically.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results ranked by semantic similarity
        """
        pass
    
    @abstractmethod
    async def get_context(
        self,
        query: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Get relevant context within token budget.
        
        Args:
            query: Query to find relevant context for
            max_tokens: Maximum number of tokens to include
            
        Returns:
            Formatted context string ready for LLM injection
        """
        pass
    
    @abstractmethod
    async def link(
        self,
        source_key: str,
        target_key: str,
        link_type: str,
        strength: float = 1.0
    ) -> bool:
        """
        Create a knowledge link between entries.
        
        Args:
            source_key: Source entry key
            target_key: Target entry key
            link_type: Type of relationship
            strength: Strength of relationship (0.0-1.0)
            
        Returns:
            True if link created successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_related(
        self,
        key: str,
        depth: int = 2,
        min_strength: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Get related knowledge entries.
        
        Args:
            key: Starting entry key
            depth: Maximum traversal depth
            min_strength: Minimum link strength to follow
            
        Returns:
            List of related entries with relationship info
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get memory system statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if memory system is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass


class MemoryError(Exception):
    """Memory-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        """Initialize memory error."""
        super().__init__(message)
        self.message: str = message
        self.error_code: Optional[str] = error_code


class MemoryConfig:
    """Configuration for memory interface."""
    
    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        retry_attempts: int = 3,
        timeout_seconds: int = 30
    ) -> None:
        """Initialize memory configuration."""
        self.cache_size: int = cache_size
        self.cache_ttl: int = cache_ttl
        self.retry_attempts: int = retry_attempts
        self.timeout_seconds: int = timeout_seconds


# Memory interface factory
def create_memory_interface(
    implementation: str = "mock",
    config: Optional[MemoryConfig] = None
) -> MemoryInterface:
    """
    Create memory interface implementation.
    
    Args:
        implementation: Type of implementation ("mock", "codex")
        config: Optional configuration
        
    Returns:
        Memory interface instance
    """
    if implementation == "mock":
        from .mock_memory import MockMemoryInterface
        return MockMemoryInterface(config or MemoryConfig())
    elif implementation == "codex":
        from .codex_memory import CodexMemoryInterface
        return CodexMemoryInterface(config or MemoryConfig())
    else:
        raise MemoryError(f"Unknown memory implementation: {implementation}")
