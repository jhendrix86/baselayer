"""
CODX Similarity Search

Similarity search and retrieval for CODX knowledge engine
with advanced ranking and filtering.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
import numpy as np
from dataclasses import dataclass
from enum import Enum

from ..models.vector_embedding import VectorEmbedding, EmbeddingStatus, VectorStoreType
from .vector_store import VectorStore
from .embedding_generator import EmbeddingGenerator, calculate_similarity
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class SearchMode(str, Enum):
    """Search modes."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    GRAPH = "graph"


class RankingStrategy(str, Enum):
    """Ranking strategies."""
    SIMILARITY = "similarity"
    RECENCY = "recency"
    RELEVANCE = "relevance"
    CONFIDENCE = "confidence"
    QUALITY = "quality"
    CUSTOM = "custom"


@dataclass
class SearchResult:
    """Search result data class."""
    embedding_id: str
    text: str
    similarity: float
    distance: float
    source_type: str
    source_id: Optional[str]
    metadata: Dict[str, Any]
    ranking_score: float
    explanation: Optional[str] = None


class SimilaritySearch:
    """
    Similarity search engine for CODX knowledge engine.
    
    Provides advanced similarity search with multiple
    ranking strategies and filtering options.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: Optional[EmbeddingGenerator] = None
    ):
        """Initialize similarity search."""
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        
        # Search configuration
        self.default_top_k = 10
        self.default_threshold = 0.7
        self.default_mode = SearchMode.SEMANTIC
        self.default_ranking = RankingStrategy.SIMILARITY
        
        # Performance metrics
        self.search_stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "average_search_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Search cache
        self.search_cache: Dict[str, List[SearchResult]] = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(
            "Similarity search initialized",
            vector_store_type=vector_store.get_backend_info()["backend_type"],
            embedding_generator_available=embedding_generator is not None
        )
    
    async def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.SEMANTIC,
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        ranking_strategy: RankingStrategy = RankingStrategy.SIMILARITY,
        use_cache: bool = True,
        include_explanations: bool = False,
        boost_factors: Optional[Dict[str, float]] = None
    ) -> List[SearchResult]:
        """
        Perform similarity search.
        
        Args:
            query: Search query
            mode: Search mode (semantic, keyword, hybrid, graph)
            top_k: Number of results to return
            threshold: Similarity threshold
            filters: Search filters
            ranking_strategy: Ranking strategy
            use_cache: Whether to use search cache
            include_explanations: Include result explanations
            boost_factors: Boost factors for ranking
            
        Returns:
            List of search results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.search_stats["total_searches"] += 1
            
            # Check cache first
            cache_key = self._generate_cache_key(query, mode, filters, ranking_strategy)
            if use_cache and self._is_cache_valid(cache_key):
                self.search_stats["cache_hits"] += 1
                cached_results = self.search_cache[cache_key]
                
                logger.info(
                    "Search retrieved from cache",
                    query=query,
                    mode=mode,
                    results_count=len(cached_results)
                )
                
                return cached_results[:top_k]
            
            self.search_stats["cache_misses"] += 1
            
            # Perform search based on mode
            if mode == SearchMode.SEMANTIC:
                results = await self._semantic_search(
                    query, top_k, threshold, filters, ranking_strategy,
                    include_explanations, boost_factors
                )
            elif mode == SearchMode.KEYWORD:
                results = await self._keyword_search(
                    query, top_k, filters, ranking_strategy,
                    include_explanations, boost_factors
                )
            elif mode == SearchMode.HYBRID:
                results = await self._hybrid_search(
                    query, top_k, threshold, filters, ranking_strategy,
                    include_explanations, boost_factors
                )
            elif mode == SearchMode.GRAPH:
                results = await self._graph_search(
                    query, top_k, filters, ranking_strategy,
                    include_explanations, boost_factors
                )
            else:
                raise BaseLayerError(f"Unsupported search mode: {mode}")
            
            # Apply ranking
            results = self._apply_ranking(results, ranking_strategy, boost_factors)
            
            # Update cache
            if use_cache:
                self._cache_search(cache_key, results)
            
            # Update statistics
            search_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.search_stats["successful_searches"] += 1
            self.search_stats["average_search_time_ms"] = (
                (self.search_stats["average_search_time_ms"] * (self.search_stats["successful_searches"] - 1) + search_time) /
                self.search_stats["successful_searches"]
            )
            self.search_stats["average_results_count"] = (
                (self.search_stats["average_results_count"] * (self.search_stats["successful_searches"] - 1) + len(results)) /
                self.search_stats["successful_searches"]
            )
            
            logger.info(
                "Search completed successfully",
                query=query,
                mode=mode,
                results_count=len(results),
                search_time_ms=search_time,
                ranking_strategy=ranking_strategy
            )
            
            return results[:top_k]
            
        except Exception as e:
            self.search_stats["failed_searches"] += 1
            logger.error(
                "Search failed",
                error=str(e),
                query=query,
                mode=mode
            )
            raise BaseLayerError(f"Search failed: {str(e)}") from e
    
    async def _semantic_search(
        self,
        query: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        ranking_strategy: RankingStrategy,
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[SearchResult]:
        """Perform semantic search using embeddings."""
        try:
            if not self.embedding_generator:
                raise BaseLayerError("Embedding generator required for semantic search")
            
            # Generate query embedding
            query_embedding = await self.embedding_generator.generate_embedding(query)
            
            # Search vector store
            vector_results = await self.vector_store.search_similar(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold
            )
            
            # Convert to SearchResults
            results = []
            for vector_result in vector_results:
                result = SearchResult(
                    embedding_id=vector_result["embedding_id"],
                    text=vector_result["text"],
                    similarity=vector_result["similarity"],
                    distance=vector_result["distance"],
                    source_type=vector_result["source_type"],
                    source_id=vector_result["source_id"],
                    metadata=vector_result["metadata"],
                    ranking_score=vector_result["similarity"]
                )
                
                if include_explanations:
                    result.explanation = self._generate_semantic_explanation(
                        query, vector_result, threshold
                    )
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Semantic search failed",
                error=str(e),
                query=query
            )
            raise BaseLayerError(f"Semantic search failed: {str(e)}") from e
    
    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
        ranking_strategy: RankingStrategy,
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[SearchResult]:
        """Perform keyword search."""
        try:
            # Get embeddings from vector store
            embeddings = await self.vector_store.list_embeddings(
                limit=top_k * 2,  # Get more for better filtering
                filters=filters
            )
            
            # Calculate keyword similarity
            query_terms = query.lower().split()
            results = []
            
            for embedding in embeddings:
                text = embedding.text.lower()
                
                # Calculate keyword match score
                match_count = sum(1 for term in query_terms if term in text)
                keyword_score = match_count / len(query_terms) if query_terms else 0.0
                
                # Calculate similarity (placeholder)
                similarity = keyword_score
                
                if similarity > 0.1:  # Basic threshold
                    result = SearchResult(
                        embedding_id=str(embedding.id),
                        text=embedding.text,
                        similarity=similarity,
                        distance=1.0 - similarity,
                        source_type=embedding.source_type,
                        source_id=str(embedding.source_id) if embedding.source_id else None,
                        metadata={
                            "similarity_threshold": embedding.similarity_threshold,
                            "retrieval_score": embedding.retrieval_score,
                            "status": embedding.status,
                            "created_at": embedding.created_at.isoformat() if embedding.created_at else None,
                            "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None
                        },
                        ranking_score=similarity
                    )
                    
                    if include_explanations:
                        result.explanation = self._generate_keyword_explanation(
                            query, embedding, keyword_score
                        )
                    
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Keyword search failed",
                error=str(e),
                query=query
            )
            raise BaseLayerError(f"Keyword search failed: {str(e)}") from e
    
    async def _hybrid_search(
        self,
        query: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        ranking_strategy: RankingStrategy,
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[SearchResult]:
        """Perform hybrid search combining semantic and keyword."""
        try:
            # Perform both searches
            semantic_results = await self._semantic_search(
                query, top_k, threshold, filters, ranking_strategy,
                include_explanations, boost_factors
            )
            
            keyword_results = await self._keyword_search(
                query, top_k, filters, ranking_strategy,
                include_explanations, boost_factors
            )
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Add semantic results
            for result in semantic_results:
                combined_results[result.embedding_id] = result
            
            # Add keyword results with lower weight
            for result in keyword_results:
                if result.embedding_id in combined_results:
                    # Combine scores
                    existing = combined_results[result.embedding_id]
                    combined_score = (existing.similarity * 0.7) + (result.similarity * 0.3)
                    existing.similarity = combined_score
                    existing.ranking_score = combined_score
                else:
                    # Add with reduced weight
                    result.similarity *= 0.3
                    result.ranking_score *= 0.3
                    combined_results[result.embedding_id] = result
            
            results = list(combined_results.values())
            
            return results
            
        except Exception as e:
            logger.error(
                "Hybrid search failed",
                error=str(e),
                query=query
            )
            raise BaseLayerError(f"Hybrid search failed: {str(e)}") from e
    
    async def _graph_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
        ranking_strategy: RankingStrategy,
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[SearchResult]:
        """Perform graph-based search."""
        try:
            # Get embeddings with graph context
            embeddings = await self.vector_store.list_embeddings(
                limit=top_k * 2,
                filters=filters
            )
            
            # For now, use semantic search as base
            # In a full implementation, this would use graph traversal
            if not self.embedding_generator:
                return []
            
            query_embedding = await self.embedding_generator.generate_embedding(query)
            
            results = []
            for embedding in embeddings:
                if not embedding.embedding_vector:
                    continue
                
                # Calculate similarity
                similarity = calculate_similarity(query_embedding, embedding.embedding_vector)
                
                if similarity > 0.1:  # Basic threshold
                    result = SearchResult(
                        embedding_id=str(embedding.id),
                        text=embedding.text,
                        similarity=similarity,
                        distance=1.0 - similarity,
                        source_type=embedding.source_type,
                        source_id=str(embedding.source_id) if embedding.source_id else None,
                        metadata={
                            "similarity_threshold": embedding.similarity_threshold,
                            "retrieval_score": embedding.retrieval_score,
                            "status": embedding.status,
                            "created_at": embedding.created_at.isoformat() if embedding.created_at else None,
                            "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None,
                            "graph_context": True
                        },
                        ranking_score=similarity
                    )
                    
                    if include_explanations:
                        result.explanation = self._generate_graph_explanation(
                            query, embedding, similarity
                        )
                    
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Graph search failed",
                error=str(e),
                query=query
            )
            raise BaseLayerError(f"Graph search failed: {str(e)}") from e
    
    def _apply_ranking(
        self,
        results: List[SearchResult],
        ranking_strategy: RankingStrategy,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[SearchResult]:
        """Apply ranking strategy to results."""
        if not results:
            return results
        
        # Apply boost factors
        if boost_factors:
            for result in results:
                boosted_score = result.ranking_score
                
                # Apply source type boost
                source_boost = boost_factors.get(f"source_type:{result.source_type}", 1.0)
                boosted_score *= source_boost
                
                # Apply recency boost
                if result.metadata.get("created_at"):
                    created_at = datetime.fromisoformat(result.metadata["created_at"])
                    days_old = (datetime.now(timezone.utc) - created_at).days
                    recency_boost = boost_factors.get("recency", 1.0)
                    if days_old < 7:  # Recent
                        boosted_score *= recency_boost
                
                result.ranking_score = boosted_score
        
        # Apply ranking strategy
        if ranking_strategy == RankingStrategy.SIMILARITY:
            results.sort(key=lambda x: x.similarity, reverse=True)
        elif ranking_strategy == RankingStrategy.RECENCY:
            results.sort(key=lambda x: x.metadata.get("created_at", ""), reverse=True)
        elif ranking_strategy == RankingStrategy.RELEVANCE:
            results.sort(key=lambda x: x.ranking_score, reverse=True)
        elif ranking_strategy == RankingStrategy.CONFIDENCE:
            results.sort(key=lambda x: x.metadata.get("retrieval_score", 0), reverse=True)
        elif ranking_strategy == RankingStrategy.QUALITY:
            results.sort(key=lambda x: x.metadata.get("similarity_threshold", 0), reverse=True)
        elif ranking_strategy == RankingStrategy.CUSTOM:
            # Custom ranking logic would go here
            pass
        
        return results
    
    def _generate_semantic_explanation(
        self,
        query: str,
        result: Dict[str, Any],
        threshold: float
    ) -> str:
        """Generate explanation for semantic search result."""
        similarity = result["similarity"]
        
        if similarity >= 0.9:
            return f"High semantic similarity ({similarity:.3f}) to query"
        elif similarity >= 0.7:
            return f"Good semantic similarity ({similarity:.3f}) to query"
        elif similarity >= threshold:
            return f"Moderate semantic similarity ({similarity:.3f}) to query"
        else:
            return f"Low semantic similarity ({similarity:.3f}) to query"
    
    def _generate_keyword_explanation(
        self,
        query: str,
        embedding: VectorEmbedding,
        keyword_score: float
    ) -> str:
        """Generate explanation for keyword search result."""
        if keyword_score >= 0.8:
            return f"Strong keyword match ({keyword_score:.3f}) to query terms"
        elif keyword_score >= 0.5:
            return f"Good keyword match ({keyword_score:.3f}) to query terms"
        else:
            return f"Weak keyword match ({keyword_score:.3f}) to query terms"
    
    def _generate_graph_explanation(
        self,
        query: str,
        embedding: VectorEmbedding,
        similarity: float
    ) -> str:
        """Generate explanation for graph search result."""
        return f"Graph context match with semantic similarity ({similarity:.3f})"
    
    def _generate_cache_key(
        self,
        query: str,
        mode: SearchMode,
        filters: Optional[Dict[str, Any]],
        ranking_strategy: RankingStrategy
    ) -> str:
        """Generate cache key for search."""
        import hashlib
        key_data = {
            "query": query,
            "mode": mode,
            "filters": filters or {},
            "ranking": ranking_strategy
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.search_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_search(self, cache_key: str, results: List[SearchResult]) -> None:
        """Cache search results."""
        self.search_cache[cache_key] = results
        self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
        
        # Cleanup old cache entries
        self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.now(timezone.utc)
        keys_to_remove = []
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age_seconds = (current_time - timestamp).total_seconds()
            if age_seconds > self.cache_ttl:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in self.search_cache:
                del self.search_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    async def search_similar_embeddings(
        self,
        embedding_id: str,
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Find embeddings similar to a given embedding.
        
        Args:
            embedding_id: ID of embedding to find similar ones for
            top_k: Number of results to return
            threshold: Similarity threshold
            
        Returns:
            List of similar embeddings
        """
        try:
            # Get the reference embedding
            reference_embedding = await self.vector_store.get_embedding(embedding_id)
            if not reference_embedding or not reference_embedding.embedding_vector:
                return []
            
            # Search for similar embeddings
            vector_results = await self.vector_store.search_similar(
                query_vector=reference_embedding.embedding_vector,
                top_k=top_k + 1,  # +1 to exclude the reference
                threshold=threshold
            )
            
            # Convert to SearchResults and exclude reference
            results = []
            for vector_result in vector_results:
                if vector_result["embedding_id"] != embedding_id:
                    result = SearchResult(
                        embedding_id=vector_result["embedding_id"],
                        text=vector_result["text"],
                        similarity=vector_result["similarity"],
                        distance=vector_result["distance"],
                        source_type=vector_result["source_type"],
                        source_id=vector_result["source_id"],
                        metadata=vector_result["metadata"],
                        ranking_score=vector_result["similarity"],
                        explanation=f"Similar to embedding {embedding_id}"
                    )
                    results.append(result)
            
            logger.info(
                "Similar embeddings search completed",
                reference_embedding_id=embedding_id,
                results_count=len(results),
                threshold=threshold
            )
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(
                "Similar embeddings search failed",
                error=str(e),
                embedding_id=embedding_id
            )
            raise BaseLayerError(f"Similar embeddings search failed: {str(e)}") from e
    
    async def search_by_source(
        self,
        source_type: str,
        source_id: Optional[str] = None,
        top_k: int = 50
    ) -> List[SearchResult]:
        """
        Search embeddings by source.
        
        Args:
            source_type: Type of source
            source_id: Specific source ID
            top_k: Number of results to return
            
        Returns:
            List of embeddings from source
        """
        try:
            # Build filters
            filters = {"source_type": source_type}
            if source_id:
                filters["source_id"] = source_id
            
            # Get embeddings
            embeddings = await self.vector_store.list_embeddings(
                limit=top_k,
                filters=filters
            )
            
            # Convert to SearchResults
            results = []
            for embedding in embeddings:
                result = SearchResult(
                    embedding_id=str(embedding.id),
                    text=embedding.text,
                    similarity=1.0,  # Perfect match for source search
                    distance=0.0,
                    source_type=embedding.source_type,
                    source_id=str(embedding.source_id) if embedding.source_id else None,
                    metadata={
                        "similarity_threshold": embedding.similarity_threshold,
                        "retrieval_score": embedding.retrieval_score,
                        "status": embedding.status,
                        "created_at": embedding.created_at.isoformat() if embedding.created_at else None,
                        "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None
                    },
                    ranking_score=1.0,
                    explanation=f"From source {source_type}" + (f" ({source_id})" if source_id else "")
                )
                results.append(result)
            
            logger.info(
                "Source search completed",
                source_type=source_type,
                source_id=source_id,
                results_count=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Source search failed",
                error=str(e),
                source_type=source_type,
                source_id=source_id
            )
            raise BaseLayerError(f"Source search failed: {str(e)}") from e
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "total_searches": self.search_stats["total_searches"],
            "successful_searches": self.search_stats["successful_searches"],
            "failed_searches": self.search_stats["failed_searches"],
            "success_rate": (
                self.search_stats["successful_searches"] / self.search_stats["total_searches"]
                if self.search_stats["total_searches"] > 0 else 0.0
            ),
            "average_search_time_ms": self.search_stats["average_search_time_ms"],
            "average_results_count": self.search_stats["average_results_count"],
            "cache_hits": self.search_stats["cache_hits"],
            "cache_misses": self.search_stats["cache_misses"],
            "cache_hit_rate": (
                self.search_stats["cache_hits"] / 
                (self.search_stats["cache_hits"] + self.search_stats["cache_misses"])
                if (self.search_stats["cache_hits"] + self.search_stats["cache_misses"]) > 0 else 0.0
            ),
            "cache_size": len(self.search_cache)
        }
    
    def reset_stats(self) -> None:
        """Reset search statistics."""
        self.search_stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "average_search_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def clear_cache(self) -> None:
        """Clear search cache."""
        self.search_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Similarity search cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on similarity search."""
        try:
            # Test basic search
            test_query = "test search query"
            test_results = await self.search(
                query=test_query,
                top_k=5,
                use_cache=False
            )
            
            # Test vector store
            vector_store_health = await self.vector_store.health_check()
            
            # Test embedding generator
            embedding_generator_health = {"status": "not_available"}
            if self.embedding_generator:
                embedding_generator_health = await self.embedding_generator.health_check()
            
            health_status = {
                "status": "healthy",
                "search_working": True,
                "test_results_count": len(test_results),
                "vector_store_health": vector_store_health,
                "embedding_generator_health": embedding_generator_health,
                "cache_size": len(self.search_cache),
                "stats": self.get_search_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Similarity search health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Similarity search health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
