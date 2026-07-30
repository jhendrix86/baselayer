"""
CODX Retrieval Engine

Main retrieval engine orchestrator for CODX knowledge engine
with unified interface and advanced features.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
from dataclasses import dataclass
from enum import Enum

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from ..vector.vector_store import VectorStore
from ..vector.similarity_search import SimilaritySearch, SearchMode, SearchResult
from ..graph.graph_traversal import GraphTraverser
from ..graph.graph_analytics import GraphAnalyzer
from .knowledge_retriever import KnowledgeRetriever, RetrievalMode, RetrievalStrategy, RetrievalResult
from .query_processor import QueryProcessor, ProcessedQuery
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class RetrievalEngine:
    """
    Main retrieval engine for CODX knowledge engine.
    
    Orchestrates all retrieval components including
    vector search, graph traversal, and knowledge retrieval.
    """
    
    def __init__(
        self,
        db_session,
        vector_store: VectorStore,
        similarity_search: SimilaritySearch,
        graph_traverser: GraphTraverser,
        graph_analyzer: GraphAnalyzer,
        query_processor: QueryProcessor,
        knowledge_retriever: KnowledgeRetriever
    ):
        """Initialize retrieval engine."""
        self.db_session = db_session
        self.vector_store = vector_store
        self.similarity_search = similarity_search
        self.graph_traverser = graph_traverser
        self.graph_analyzer = graph_analyzer
        self.query_processor = query_processor
        self.knowledge_retriever = knowledge_retriever
        
        # Engine configuration
        self.default_mode = "hybrid"
        self.default_strategy = "relevance"
        self.default_top_k = 10
        self.default_threshold = 0.7
        
        # Performance metrics
        self.engine_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_query_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "component_usage": {
                "vector_search": 0,
                "graph_traversal": 0,
                "knowledge_retrieval": 0,
                "query_processing": 0
            }
        }
        
        # Query cache
        self.query_cache: Dict[str, List[RetrievalResult]] = {}
        self.cache_ttl = 900  # 15 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(
            "Retrieval engine initialized",
            default_mode=self.default_mode,
            default_strategy=self.default_strategy
        )
    
    async def query(
        self,
        query: str,
        mode: Optional[str] = None,
        strategy: Optional[str] = None,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        include_explanations: bool = False,
        boost_factors: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Execute a knowledge query.
        
        Args:
            query: Knowledge query
            mode: Retrieval mode (vector, graph, hybrid, etc.)
            strategy: Ranking strategy
            top_k: Number of results to return
            threshold: Relevance threshold
            filters: Query filters
            preferences: Query preferences
            context: Query context
            use_cache: Whether to use cache
            include_explanations: Include result explanations
            boost_factors: Boost factors for ranking
            
        Returns:
            Query results with metadata
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.engine_stats["total_queries"] += 1
            
            # Set defaults
            query_mode = mode or self.default_mode
            query_strategy = strategy or self.default_strategy
            query_top_k = top_k or self.default_top_k
            query_threshold = threshold or self.default_threshold
            
            # Check cache first
            cache_key = self._generate_cache_key(
                query, query_mode, query_strategy, filters, preferences
            )
            if use_cache and self._is_cache_valid(cache_key):
                self.engine_stats["cache_hits"] += 1
                cached_results = self.query_cache[cache_key]
                
                logger.info(
                    "Query retrieved from cache",
                    query=query,
                    mode=query_mode,
                    results_count=len(cached_results)
                )
                
                return {
                    "query": query,
                    "mode": query_mode,
                    "strategy": query_strategy,
                    "results": cached_results[:query_top_k],
                    "total_found": len(cached_results),
                    "execution_time_ms": 0,
                    "from_cache": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            self.engine_stats["cache_misses"] += 1
            
            # Process query
            processed_query = await self.query_processor.process_query(
                query=query,
                context=context,
                use_cache=use_cache
            )
            
            # Execute query based on mode
            if query_mode == "vector":
                results = await self._execute_vector_query(
                    processed_query, query_strategy, query_top_k, query_threshold,
                    filters, preferences, include_explanations, boost_factors
                )
                self.engine_stats["component_usage"]["vector_search"] += 1
            
            elif query_mode == "graph":
                results = await self._execute_graph_query(
                    processed_query, query_strategy, query_top_k, query_threshold,
                    filters, preferences, include_explanations, boost_factors
                )
                self.engine_stats["component_usage"]["graph_traversal"] += 1
            
            elif query_mode == "knowledge":
                results = await self._execute_knowledge_query(
                    processed_query, query_strategy, query_top_k, query_threshold,
                    filters, preferences, include_explanations, boost_factors
                )
                self.engine_stats["component_usage"]["knowledge_retrieval"] += 1
            
            elif query_mode == "hybrid":
                results = await self._execute_hybrid_query(
                    processed_query, query_strategy, query_top_k, query_threshold,
                    filters, preferences, include_explanations, boost_factors
                )
                # Update component usage
                self.engine_stats["component_usage"]["vector_search"] += 1
                self.engine_stats["component_usage"]["graph_traversal"] += 1
                self.engine_stats["component_usage"]["knowledge_retrieval"] += 1
            
            else:
                raise BaseLayerError(f"Unsupported query mode: {query_mode}")
            
            # Update cache
            if use_cache:
                self._cache_query(cache_key, results)
            
            # Update statistics
            query_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.engine_stats["successful_queries"] += 1
            self.engine_stats["average_query_time_ms"] = (
                (self.engine_stats["average_query_time_ms"] * (self.engine_stats["successful_queries"] - 1) + query_time) /
                self.engine_stats["successful_queries"]
            )
            self.engine_stats["average_results_count"] = (
                (self.engine_stats["average_results_count"] * (self.engine_stats["successful_queries"] - 1) + len(results)) /
                self.engine_stats["successful_queries"]
            )
            
            response = {
                "query": query,
                "mode": query_mode,
                "strategy": query_strategy,
                "results": results[:query_top_k],
                "total_found": len(results),
                "execution_time_ms": query_time,
                "from_cache": False,
                "processed_query": processed_query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "threshold": query_threshold,
                    "filters": filters or {},
                    "preferences": preferences or {},
                    "boost_factors": boost_factors or {}
                }
            }
            
            logger.info(
                "Query executed successfully",
                query=query,
                mode=query_mode,
                results_count=len(results),
                execution_time_ms=query_time
            )
            
            return response
            
        except Exception as e:
            self.engine_stats["failed_queries"] += 1
            logger.error(
                "Query execution failed",
                error=str(e),
                query=query,
                mode=query_mode
            )
            raise BaseLayerError(f"Query execution failed: {str(e)}") from e
    
    async def _execute_vector_query(
        self,
        processed_query: ProcessedQuery,
        strategy: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]],
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[RetrievalResult]:
        """Execute vector-based query."""
        try:
            # Use similarity search
            search_results = await self.similarity_search.search(
                query=processed_query.normalized_query,
                mode=SearchMode.SEMANTIC,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                ranking_strategy=strategy,
                include_explanations=include_explanations,
                boost_factors=boost_factors
            )
            
            # Convert to retrieval results
            results = []
            for search_result in search_results:
                result = RetrievalResult(
                    item_id=search_result.embedding_id,
                    item_type="embedding",
                    content=search_result.text,
                    title=None,
                    description=None,
                    metadata=search_result.metadata,
                    relevance_score=search_result.similarity,
                    confidence_score=search_result.metadata.get("retrieval_score", 0.0),
                    quality_score=search_result.metadata.get("similarity_threshold", 0.0),
                    ranking_score=search_result.ranking_score,
                    source=search_result.source_type,
                    created_at=None,
                    explanation=search_result.explanation
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Vector query execution failed",
                error=str(e),
                query=processed_query.normalized_query
            )
            raise BaseLayerError(f"Vector query execution failed: {str(e)}") from e
    
    async def _execute_graph_query(
        self,
        processed_query: ProcessedQuery,
        strategy: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]],
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[RetrievalResult]:
        """Execute graph-based query."""
        try:
            # Use knowledge retriever with graph mode
            results = await self.knowledge_retriever.retrieve(
                query=processed_query.normalized_query,
                mode=RetrievalMode.GRAPH_TRAVERSAL,
                strategy=RetrievalStrategy(strategy),
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                preferences=preferences,
                context=None,
                use_cache=True,
                include_explanations=include_explanations
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Graph query execution failed",
                error=str(e),
                query=processed_query.normalized_query
            )
            raise BaseLayerError(f"Graph query execution failed: {str(e)}") from e
    
    async def _execute_knowledge_query(
        self,
        processed_query: ProcessedQuery,
        strategy: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]],
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[RetrievalResult]:
        """Execute knowledge-based query."""
        try:
            # Use knowledge retriever with knowledge graph mode
            results = await self.knowledge_retriever.retrieve(
                query=processed_query.normalized_query,
                mode=RetrievalMode.KNOWLEDGE_GRAPH,
                strategy=RetrievalStrategy(strategy),
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                preferences=preferences,
                context=None,
                use_cache=True,
                include_explanations=include_explanations
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Knowledge query execution failed",
                error=str(e),
                query=processed_query.normalized_query
            )
            raise BaseLayerError(f"Knowledge query execution failed: {str(e)}") from e
    
    async def _execute_hybrid_query(
        self,
        processed_query: ProcessedQuery,
        strategy: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]],
        include_explanations: bool,
        boost_factors: Optional[Dict[str, float]]
    ) -> List[RetrievalResult]:
        """Execute hybrid query combining multiple sources."""
        try:
            # Execute vector query
            vector_results = await self._execute_vector_query(
                processed_query, strategy, top_k, threshold,
                filters, preferences, include_explanations, boost_factors
            )
            
            # Execute knowledge graph query
            knowledge_results = await self._execute_knowledge_query(
                processed_query, strategy, top_k, threshold,
                filters, preferences, include_explanations, boost_factors
            )
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Add vector results with weight
            for result in vector_results:
                combined_results[result.item_id] = result
                result.ranking_score *= 0.6  # Weight for vector results
            
            # Add knowledge results with weight
            for result in knowledge_results:
                if result.item_id in combined_results:
                    # Combine scores
                    existing = combined_results[result.item_id]
                    combined_score = (existing.ranking_score + result.ranking_score) / 2
                    existing.ranking_score = combined_score
                else:
                    result.ranking_score *= 0.4  # Weight for knowledge results
                    combined_results[result.item_id] = result
            
            results = list(combined_results.values())
            
            # Sort by final ranking score
            results.sort(key=lambda x: x.ranking_score, reverse=True)
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(
                "Hybrid query execution failed",
                error=str(e),
                query=processed_query.normalized_query
            )
            raise BaseLayerError(f"Hybrid query execution failed: {str(e)}") from e
    
    async def find_similar(
        self,
        item_id: str,
        item_type: str = "node",
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Find items similar to a given item.
        
        Args:
            item_id: ID of item to find similar ones for
            item_type: Type of item (node, edge, embedding)
            top_k: Number of results to return
            threshold: Similarity threshold
            filters: Search filters
            
        Returns:
            List of similar items
        """
        try:
            if item_type == "embedding":
                # Use similarity search
                search_results = await self.similarity_search.search_similar_embeddings(
                    embedding_id=item_id,
                    top_k=top_k,
                    threshold=threshold
                )
                
                # Convert to retrieval results
                results = []
                for search_result in search_results:
                    result = RetrievalResult(
                        item_id=search_result.embedding_id,
                        item_type="embedding",
                        content=search_result.text,
                        title=None,
                        description=None,
                        metadata=search_result.metadata,
                        relevance_score=search_result.similarity,
                        confidence_score=search_result.metadata.get("retrieval_score", 0.0),
                        quality_score=search_result.metadata.get("similarity_threshold", 0.0),
                        ranking_score=search_result.similarity,
                        source=search_result.source_type,
                        created_at=None,
                        explanation=f"Similar to embedding {item_id}"
                    )
                    results.append(result)
                
                return results
            
            elif item_type == "node":
                # Use knowledge retriever
                results = await self.knowledge_retriever.retrieve_related(
                    item_id=item_id,
                    item_type="node",
                    relationship_types=None,
                    max_depth=2,
                    top_k=top_k
                )
                
                return results
            
            else:
                logger.warning(f"Unsupported item type for similarity search: {item_type}")
                return []
                
        except Exception as e:
            logger.error(
                "Similar items search failed",
                error=str(e),
                item_id=item_id,
                item_type=item_type
            )
            raise BaseLayerError(f"Similar items search failed: {str(e)}") from e
    
    async def explore(
        self,
        start_item_id: str,
        max_depth: int = 3,
        max_items: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Explore knowledge graph from a starting item.
        
        Args:
            start_item_id: Starting item ID
            max_depth: Maximum exploration depth
            max_items: Maximum number of items to return
            filters: Exploration filters
            include_metadata: Include detailed metadata
            
        Returns:
            Exploration results with graph structure
        """
        try:
            # Use graph traversal for exploration
            traversal_result = await self.graph_traverser.breadth_first_search(
                start_node_id=start_item_id,
                max_depth=max_depth,
                max_nodes=max_items,
                include_metadata=include_metadata
            )
            
            # Analyze explored subgraph
            subgraph_analysis = {
                "start_item_id": start_item_id,
                "exploration_depth": max_depth,
                "items_explored": len(traversal_result["traversal_order"]),
                "max_depth_reached": traversal_result["max_depth"],
                "traversal_path": traversal_result["traversal_order"],
                "node_distances": traversal_result["node_distances"],
                "execution_time_ms": traversal_result["execution_time_ms"],
                "metadata": traversal_result["metadata"]
            }
            
            # Get additional graph analytics if requested
            if include_metadata:
                # This would analyze the explored subgraph
                subgraph_analysis["graph_metrics"] = {
                    "density": 0.0,  # Would calculate from traversal
                    "connectivity": 0.0,
                    "clustering": 0.0
                }
            
            logger.info(
                "Knowledge exploration completed",
                start_item_id=start_item_id,
                items_explored=len(traversal_result["traversal_order"]),
                max_depth=traversal_result["max_depth"]
            )
            
            return subgraph_analysis
            
        except Exception as e:
            logger.error(
                "Knowledge exploration failed",
                error=str(e),
                start_item_id=start_item_id
            )
            raise BaseLayerError(f"Knowledge exploration failed: {str(e)}") from e
    
    async def recommend(
        self,
        user_context: Dict[str, Any],
        item_type: str = "node",
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Generate recommendations based on user context.
        
        Args:
            user_context: User context and preferences
            item_type: Type of items to recommend
            top_k: Number of recommendations to return
            filters: Recommendation filters
            
        Returns:
            List of recommended items
        """
        try:
            # Extract user preferences and history from context
            user_preferences = user_context.get("preferences", {})
            user_history = user_context.get("history", [])
            user_profile = user_context.get("profile", {})
            
            # Generate recommendation query based on context
            recommendation_query = self._generate_recommendation_query(
                user_preferences, user_history, user_profile
            )
            
            # Execute recommendation query
            results = await self.query(
                query=recommendation_query,
                mode="hybrid",
                strategy="relevance",
                top_k=top_k,
                filters=filters,
                preferences=user_preferences,
                context=user_context,
                use_cache=False  # Don't cache recommendations
            )
            
            # Filter and rank recommendations
            recommendations = []
            for result in results["results"]:
                # Apply recommendation-specific filtering
                if self._is_relevant_recommendation(result, user_context):
                    recommendations.append(result)
            
            logger.info(
                "Recommendations generated",
                user_context_keys=list(user_context.keys()),
                recommendations_count=len(recommendations)
            )
            
            return recommendations[:top_k]
            
        except Exception as e:
            logger.error(
                "Recommendation generation failed",
                error=str(e),
                user_context_keys=list(user_context.keys()) if user_context else []
            )
            raise BaseLayerError(f"Recommendation generation failed: {str(e)}") from e
    
    def _generate_recommendation_query(
        self,
        user_preferences: Dict[str, Any],
        user_history: List[Dict[str, Any]],
        user_profile: Dict[str, Any]
    ) -> str:
        """Generate recommendation query from user context."""
        query_parts = []
        
        # Add preferences to query
        if user_preferences.get("interests"):
            interests = user_preferences["interests"]
            if isinstance(interests, list):
                query_parts.append(" OR ".join(interests))
        
        # Add recent history to query
        if user_history:
            recent_items = user_history[-5:]  # Last 5 items
            recent_terms = []
            for item in recent_items:
                if item.get("query"):
                    recent_terms.append(item["query"])
                elif item.get("title"):
                    recent_terms.append(item["title"])
            
            if recent_terms:
                query_parts.append(" OR ".join(recent_terms))
        
        # Add profile attributes to query
        if user_profile.get("expertise"):
            query_parts.append(user_profile["expertise"])
        
        if user_profile.get("role"):
            query_parts.append(user_profile["role"])
        
        return " OR ".join(query_parts) if query_parts else "recommendations"
    
    def _is_relevant_recommendation(
        self,
        result: RetrievalResult,
        user_context: Dict[str, Any]
    ) -> bool:
        """Check if recommendation is relevant to user context."""
        # Basic relevance check
        if result.relevance_score < 0.3:
            return False
        
        # Check against user preferences
        user_preferences = user_context.get("preferences", {})
        
        if user_preferences.get("exclude_types"):
            exclude_types = user_preferences["exclude_types"]
            if result.item_type in exclude_types:
                return False
        
        if user_preferences.get("min_quality"):
            if result.quality_score < user_preferences["min_quality"]:
                return False
        
        return True
    
    def _generate_cache_key(
        self,
        query: str,
        mode: str,
        strategy: str,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for query."""
        import hashlib
        key_data = {
            "query": query,
            "mode": mode,
            "strategy": strategy,
            "filters": filters or {},
            "preferences": preferences or {}
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.query_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_query(self, cache_key: str, results: List[RetrievalResult]) -> None:
        """Cache query results."""
        self.query_cache[cache_key] = results
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
            if key in self.query_cache:
                del self.query_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    async def get_engine_stats(self) -> Dict[str, Any]:
        """Get retrieval engine statistics."""
        component_stats = {}
        for component, usage in self.engine_stats["component_usage"].items():
            component_stats[component] = {
                "usage_count": usage,
                "usage_percentage": (
                    usage / self.engine_stats["total_queries"] * 100
                    if self.engine_stats["total_queries"] > 0 else 0.0
                )
            }
        
        return {
            "total_queries": self.engine_stats["total_queries"],
            "successful_queries": self.engine_stats["successful_queries"],
            "failed_queries": self.engine_stats["failed_queries"],
            "success_rate": (
                self.engine_stats["successful_queries"] / self.engine_stats["total_queries"]
                if self.engine_stats["total_queries"] > 0 else 0.0
            ),
            "average_query_time_ms": self.engine_stats["average_query_time_ms"],
            "average_results_count": self.engine_stats["average_results_count"],
            "cache_hits": self.engine_stats["cache_hits"],
            "cache_misses": self.engine_stats["cache_misses"],
            "cache_hit_rate": (
                self.engine_stats["cache_hits"] / 
                (self.engine_stats["cache_hits"] + self.engine_stats["cache_misses"])
                if (self.engine_stats["cache_hits"] + self.engine_stats["cache_misses"]) > 0 else 0.0
            ),
            "cache_size": len(self.query_cache),
            "component_usage": component_stats
        }
    
    def reset_stats(self) -> None:
        """Reset retrieval engine statistics."""
        self.engine_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_query_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "component_usage": {
                "vector_search": 0,
                "graph_traversal": 0,
                "knowledge_retrieval": 0,
                "query_processing": 0
            }
        }
    
    def clear_cache(self) -> None:
        """Clear query cache."""
        self.query_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Retrieval engine cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on retrieval engine."""
        try:
            # Test basic query
            test_query = "test retrieval engine query"
            test_result = await self.query(
                query=test_query,
                mode="vector",
                top_k=3,
                use_cache=False
            )
            
            # Test component health
            vector_health = await self.vector_store.health_check()
            similarity_health = await self.similarity_search.health_check()
            graph_health = await self.graph_traverser.health_check()
            retriever_health = await self.knowledge_retriever.health_check()
            
            health_status = {
                "status": "healthy",
                "query_working": True,
                "test_results_count": len(test_result["results"]),
                "component_health": {
                    "vector_store": vector_health,
                    "similarity_search": similarity_health,
                    "graph_traverser": graph_health,
                    "knowledge_retriever": retriever_health
                },
                "cache_size": len(self.query_cache),
                "stats": await self.get_engine_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Retrieval engine health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Retrieval engine health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
