"""
CODX Knowledge Retriever

Knowledge retrieval and ranking for CODX knowledge engine
with advanced query processing and result aggregation.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
import numpy as np
from dataclasses import dataclass
from enum import Enum

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from ..vector.vector_store import VectorStore
from ..vector.similarity_search import SimilaritySearch, SearchMode, SearchResult
from ..graph.graph_traversal import GraphTraverser
from ..graph.graph_analytics import GraphAnalyzer
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class RetrievalMode(str, Enum):
    """Retrieval modes."""
    KNOWLEDGE_GRAPH = "knowledge_graph"
    VECTOR_SEARCH = "vector_search"
    HYBRID = "hybrid"
    GRAPH_TRAVERSAL = "graph_traversal"
    SEMANTIC_SEARCH = "semantic_search"


class RetrievalStrategy(str, Enum):
    """Retrieval strategies."""
    RELEVANCE = "relevance"
    RECENCY = "recency"
    CONFIDENCE = "confidence"
    QUALITY = "quality"
    COMBINED = "combined"
    CUSTOM = "custom"


@dataclass
class RetrievalResult:
    """Retrieval result data class."""
    item_id: str
    item_type: str  # "node", "edge", "graph"
    content: str
    title: Optional[str]
    description: Optional[str]
    metadata: Dict[str, Any]
    relevance_score: float
    confidence_score: float
    quality_score: float
    ranking_score: float
    source: Optional[str]
    created_at: Optional[datetime]
    explanation: Optional[str] = None


@dataclass
class RetrievalContext:
    """Retrieval context for query processing."""
    query: str
    query_type: str
    filters: Dict[str, Any]
    preferences: Dict[str, Any]
    user_context: Optional[Dict[str, Any]]
    session_context: Optional[Dict[str, Any]]
    retrieval_history: List[Dict[str, Any]]


class KnowledgeRetriever:
    """
    Knowledge retriever for CODX knowledge engine.
    
    Provides advanced knowledge retrieval with multiple
    strategies, ranking, and result aggregation.
    """
    
    def __init__(
        self,
        db_session,
        vector_store: VectorStore,
        graph_traverser: GraphTraverser,
        graph_analyzer: GraphAnalyzer
    ):
        """Initialize knowledge retriever."""
        self.db_session = db_session
        self.vector_store = vector_store
        self.graph_traverser = graph_traverser
        self.graph_analyzer = graph_analyzer
        
        # Retrieval configuration
        self.default_mode = RetrievalMode.HYBRID
        self.default_strategy = RetrievalStrategy.RELEVANCE
        self.default_top_k = 10
        self.default_threshold = 0.7
        
        # Performance metrics
        self.retrieval_stats = {
            "total_retrievals": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "average_retrieval_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Retrieval cache
        self.retrieval_cache: Dict[str, List[RetrievalResult]] = {}
        self.cache_ttl = 600  # 10 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(
            "Knowledge retriever initialized",
            default_mode=self.default_mode,
            default_strategy=self.default_strategy
        )
    
    async def retrieve(
        self,
        query: str,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        strategy: RetrievalStrategy = RetrievalStrategy.RELEVANCE,
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        context: Optional[RetrievalContext] = None,
        use_cache: bool = True,
        include_explanations: bool = False
    ) -> List[RetrievalResult]:
        """
        Retrieve knowledge based on query.
        
        Args:
            query: Knowledge query
            mode: Retrieval mode
            strategy: Ranking strategy
            top_k: Number of results to return
            threshold: Relevance threshold
            filters: Retrieval filters
            preferences: Retrieval preferences
            context: Retrieval context
            use_cache: Whether to use cache
            include_explanations: Include result explanations
            
        Returns:
            List of retrieval results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.retrieval_stats["total_retrievals"] += 1
            
            # Create context if not provided
            if not context:
                context = RetrievalContext(
                    query=query,
                    query_type="knowledge",
                    filters=filters or {},
                    preferences=preferences or {},
                    user_context=None,
                    session_context=None,
                    retrieval_history=[]
                )
            
            # Check cache first
            cache_key = self._generate_cache_key(query, mode, strategy, filters, preferences)
            if use_cache and self._is_cache_valid(cache_key):
                self.retrieval_stats["cache_hits"] += 1
                cached_results = self.retrieval_cache[cache_key]
                
                logger.info(
                    "Retrieval retrieved from cache",
                    query=query,
                    mode=mode,
                    results_count=len(cached_results)
                )
                
                return cached_results[:top_k]
            
            self.retrieval_stats["cache_misses"] += 1
            
            # Perform retrieval based on mode
            if mode == RetrievalMode.VECTOR_SEARCH:
                results = await self._vector_retrieval(
                    context, strategy, top_k, threshold, include_explanations
                )
            elif mode == RetrievalMode.KNOWLEDGE_GRAPH:
                results = await self._knowledge_graph_retrieval(
                    context, strategy, top_k, threshold, include_explanations
                )
            elif mode == RetrievalMode.HYBRID:
                results = await self._hybrid_retrieval(
                    context, strategy, top_k, threshold, include_explanations
                )
            elif mode == RetrievalMode.GRAPH_TRAVERSAL:
                results = await self._graph_traversal_retrieval(
                    context, strategy, top_k, threshold, include_explanations
                )
            elif mode == RetrievalMode.SEMANTIC_SEARCH:
                results = await self._semantic_retrieval(
                    context, strategy, top_k, threshold, include_explanations
                )
            else:
                raise BaseLayerError(f"Unsupported retrieval mode: {mode}")
            
            # Apply ranking strategy
            results = self._apply_ranking_strategy(results, strategy, context)
            
            # Update cache
            if use_cache:
                self._cache_retrieval(cache_key, results)
            
            # Update statistics
            retrieval_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.retrieval_stats["successful_retrievals"] += 1
            self.retrieval_stats["average_retrieval_time_ms"] = (
                (self.retrieval_stats["average_retrieval_time_ms"] * (self.retrieval_stats["successful_retrievals"] - 1) + retrieval_time) /
                self.retrieval_stats["successful_retrievals"]
            )
            self.retrieval_stats["average_results_count"] = (
                (self.retrieval_stats["average_results_count"] * (self.retrieval_stats["successful_retrievals"] - 1) + len(results)) /
                self.retrieval_stats["successful_retrievals"]
            )
            
            logger.info(
                "Knowledge retrieval completed successfully",
                query=query,
                mode=mode,
                strategy=strategy,
                results_count=len(results),
                retrieval_time_ms=retrieval_time
            )
            
            return results[:top_k]
            
        except Exception as e:
            self.retrieval_stats["failed_retrievals"] += 1
            logger.error(
                "Knowledge retrieval failed",
                error=str(e),
                query=query,
                mode=mode
            )
            raise BaseLayerError(f"Knowledge retrieval failed: {str(e)}") from e
    
    async def _vector_retrieval(
        self,
        context: RetrievalContext,
        strategy: RetrievalStrategy,
        top_k: int,
        threshold: float,
        include_explanations: bool
    ) -> List[RetrievalResult]:
        """Perform vector-based retrieval."""
        try:
            # Use similarity search
            search_results = await self.vector_store.search_similar(
                query_vector=[],  # Would need to generate query embedding
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
                    explanation=self._generate_vector_explanation(search_result, threshold) if include_explanations else None
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Vector retrieval failed",
                error=str(e),
                query=context.query
            )
            raise BaseLayerError(f"Vector retrieval failed: {str(e)}") from e
    
    async def _knowledge_graph_retrieval(
        self,
        context: RetrievalContext,
        strategy: RetrievalStrategy,
        top_k: int,
        threshold: float,
        include_explanations: bool
    ) -> List[RetrievalResult]:
        """Perform knowledge graph-based retrieval."""
        try:
            # Extract entities from query
            entities = self._extract_entities(context.query)
            
            # Search for nodes matching entities
            results = []
            for entity in entities:
                # Search nodes by title/content
                nodes = await self._search_nodes_by_entity(entity, top_k)
                
                for node in nodes:
                    # Calculate relevance score
                    relevance = self._calculate_node_relevance(node, entity)
                    
                    if relevance >= threshold:
                        result = RetrievalResult(
                            item_id=str(node.id),
                            item_type="node",
                            content=node.content or "",
                            title=node.title,
                            description=node.description,
                            metadata={
                                "node_type": node.node_type,
                                "status": node.status,
                                "keywords": node.keywords or [],
                                "tags": node.tags or {},
                                "confidence_score": node.confidence_score,
                                "quality_score": node.quality_score,
                                "relevance_score": node.relevance_score,
                                "source": node.source,
                                "author": node.author,
                                "level": node.level,
                                "path": node.path,
                                "access_count": node.access_count,
                                "update_count": node.update_count,
                                "created_at": node.created_at.isoformat() if node.created_at else None,
                                "updated_at": node.updated_at.isoformat() if node.updated_at else None,
                                "last_accessed": node.last_accessed.isoformat() if node.last_accessed else None
                            },
                            relevance_score=relevance,
                            confidence_score=node.confidence_score,
                            quality_score=node.quality_score,
                            ranking_score=relevance,
                            source=node.source,
                            created_at=node.created_at,
                            explanation=self._generate_node_explanation(node, entity, relevance) if include_explanations else None
                        )
                        results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(
                "Knowledge graph retrieval failed",
                error=str(e),
                query=context.query
            )
            raise BaseLayerError(f"Knowledge graph retrieval failed: {str(e)}") from e
    
    async def _hybrid_retrieval(
        self,
        context: RetrievalContext,
        strategy: RetrievalStrategy,
        top_k: int,
        threshold: float,
        include_explanations: bool
    ) -> List[RetrievalResult]:
        """Perform hybrid retrieval combining multiple sources."""
        try:
            # Perform vector retrieval
            vector_results = await self._vector_retrieval(
                context, strategy, top_k, threshold, include_explanations
            )
            
            # Perform knowledge graph retrieval
            graph_results = await self._knowledge_graph_retrieval(
                context, strategy, top_k, threshold, include_explanations
            )
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Add vector results with weight
            for result in vector_results:
                combined_results[result.item_id] = result
                result.ranking_score *= 0.6  # Weight for vector results
            
            # Add graph results with weight
            for result in graph_results:
                if result.item_id in combined_results:
                    # Combine scores
                    existing = combined_results[result.item_id]
                    combined_score = (existing.ranking_score + result.ranking_score) / 2
                    existing.ranking_score = combined_score
                else:
                    result.ranking_score *= 0.4  # Weight for graph results
                    combined_results[result.item_id] = result
            
            results = list(combined_results.values())
            
            return results
            
        except Exception as e:
            logger.error(
                "Hybrid retrieval failed",
                error=str(e),
                query=context.query
            )
            raise BaseLayerError(f"Hybrid retrieval failed: {str(e)}") from e
    
    async def _graph_traversal_retrieval(
        self,
        context: RetrievalContext,
        strategy: RetrievalStrategy,
        top_k: int,
        threshold: float,
        include_explanations: bool
    ) -> List[RetrievalResult]:
        """Perform graph traversal-based retrieval."""
        try:
            # Find starting nodes based on query
            start_nodes = await self._find_start_nodes(context.query, 5)
            
            if not start_nodes:
                return []
            
            # Perform BFS traversal from each start node
            all_results = []
            
            for start_node in start_nodes:
                traversal_result = await self.graph_traverser.breadth_first_search(
                    start_node_id=str(start_node.id),
                    max_depth=3,
                    max_nodes=top_k,
                    include_metadata=True
                )
                
                # Convert traversal results to retrieval results
                for node_data in traversal_result["traversal_order"]:
                    if node_data["depth"] > 0:  # Exclude start node
                        result = RetrievalResult(
                            item_id=node_data["id"],
                            item_type="node",
                            content=node_data.get("content", ""),
                            title=node_data["title"],
                            description=node_data.get("description"),
                            metadata=node_data.get("metadata", {}),
                            relevance_score=1.0 / (node_data["depth"] + 1),  # Higher score for closer nodes
                            confidence_score=node_data.get("confidence_score", 0.0),
                            quality_score=node_data.get("quality_score", 0.0),
                            ranking_score=1.0 / (node_data["depth"] + 1),
                            source=node_data.get("source"),
                            created_at=None,
                            explanation=self._generate_traversal_explanation(node_data) if include_explanations else None
                        )
                        all_results.append(result)
            
            return all_results[:top_k]
            
        except Exception as e:
            logger.error(
                "Graph traversal retrieval failed",
                error=str(e),
                query=context.query
            )
            raise BaseLayerError(f"Graph traversal retrieval failed: {str(e)}") from e
    
    async def _semantic_retrieval(
        self,
        context: RetrievalContext,
        strategy: RetrievalStrategy,
        top_k: int,
        threshold: float,
        include_explanations: bool
    ) -> List[RetrievalResult]:
        """Perform semantic retrieval using LLM understanding."""
        try:
            # Analyze query semantic meaning
            query_analysis = await self._analyze_query_semantics(context.query)
            
            # Search based on semantic understanding
            results = []
            
            # Search for concepts
            if query_analysis.get("concepts"):
                for concept in query_analysis["concepts"]:
                    concept_results = await self._search_by_concept(concept, top_k)
                    results.extend(concept_results)
            
            # Search for relationships
            if query_analysis.get("relationships"):
                for relationship in query_analysis["relationships"]:
                    rel_results = await self._search_by_relationship(relationship, top_k)
                    results.extend(rel_results)
            
            # Search for entities
            if query_analysis.get("entities"):
                for entity in query_analysis["entities"]:
                    entity_results = await self._search_by_entity(entity, top_k)
                    results.extend(entity_results)
            
            # Remove duplicates and apply threshold
            unique_results = {}
            for result in results:
                if result.relevance_score >= threshold:
                    if result.item_id not in unique_results:
                        unique_results[result.item_id] = result
                    else:
                        # Combine scores
                        existing = unique_results[result.item_id]
                        combined_score = (existing.relevance_score + result.relevance_score) / 2
                        existing.relevance_score = combined_score
                        existing.ranking_score = combined_score
            
            return list(unique_results.values())[:top_k]
            
        except Exception as e:
            logger.error(
                "Semantic retrieval failed",
                error=str(e),
                query=context.query
            )
            raise BaseLayerError(f"Semantic retrieval failed: {str(e)}") from e
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query."""
        # Simple entity extraction (would use NLP in production)
        words = query.lower().split()
        entities = []
        
        # Filter out stop words and extract potential entities
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should"}
        
        for word in words:
            if word not in stop_words and len(word) > 2:
                entities.append(word)
        
        return list(set(entities))
    
    async def _search_nodes_by_entity(self, entity: str, limit: int) -> List[KnowledgeNode]:
        """Search nodes by entity."""
        try:
            # This would use database search
            # Placeholder implementation
            return []
            
        except Exception as e:
            logger.error(
                "Node entity search failed",
                error=str(e),
                entity=entity
            )
            return []
    
    def _calculate_node_relevance(self, node: KnowledgeNode, entity: str) -> float:
        """Calculate relevance score for node."""
        score = 0.0
        
        # Title match
        if node.title and entity.lower() in node.title.lower():
            score += 0.5
        
        # Content match
        if node.content and entity.lower() in node.content.lower():
            score += 0.3
        
        # Keyword match
        if node.keywords:
            for keyword in node.keywords:
                if entity.lower() in keyword.lower():
                    score += 0.1
        
        # Quality and confidence boost
        score *= (node.confidence_score + node.quality_score) / 2
        
        return min(score, 1.0)
    
    async def _find_start_nodes(self, query: str, limit: int) -> List[KnowledgeNode]:
        """Find starting nodes for traversal."""
        try:
            # This would search for nodes matching query terms
            # Placeholder implementation
            return []
            
        except Exception as e:
            logger.error(
                "Start node search failed",
                error=str(e),
                query=query
            )
            return []
    
    async def _analyze_query_semantics(self, query: str) -> Dict[str, List[str]]:
        """Analyze query semantic meaning."""
        # Placeholder for semantic analysis
        # In production, this would use LLM or NLP models
        
        entities = self._extract_entities(query)
        
        return {
            "concepts": entities[:3],  # Top 3 as concepts
            "relationships": [],  # Would extract relationships
            "entities": entities
        }
    
    async def _search_by_concept(self, concept: str, limit: int) -> List[RetrievalResult]:
        """Search by concept."""
        # Placeholder for concept search
        return []
    
    async def _search_by_relationship(self, relationship: str, limit: int) -> List[RetrievalResult]:
        """Search by relationship."""
        # Placeholder for relationship search
        return []
    
    async def _search_by_entity(self, entity: str, limit: int) -> List[RetrievalResult]:
        """Search by entity."""
        # Placeholder for entity search
        return []
    
    def _apply_ranking_strategy(
        self,
        results: List[RetrievalResult],
        strategy: RetrievalStrategy,
        context: RetrievalContext
    ) -> List[RetrievalResult]:
        """Apply ranking strategy to results."""
        if not results:
            return results
        
        if strategy == RetrievalStrategy.RELEVANCE:
            results.sort(key=lambda x: x.relevance_score, reverse=True)
        elif strategy == RetrievalStrategy.RECENCY:
            results.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        elif strategy == RetrievalStrategy.CONFIDENCE:
            results.sort(key=lambda x: x.confidence_score, reverse=True)
        elif strategy == RetrievalStrategy.QUALITY:
            results.sort(key=lambda x: x.quality_score, reverse=True)
        elif strategy == RetrievalStrategy.COMBINED:
            # Combined scoring
            for result in results:
                result.ranking_score = (
                    result.relevance_score * 0.4 +
                    result.confidence_score * 0.3 +
                    result.quality_score * 0.2 +
                    (1.0 if result.created_at and (datetime.now(timezone.utc) - result.created_at).days < 30 else 0.0) * 0.1
                )
            results.sort(key=lambda x: x.ranking_score, reverse=True)
        elif strategy == RetrievalStrategy.CUSTOM:
            # Custom ranking based on preferences
            if context.preferences.get("boost_recent"):
                for result in results:
                    if result.created_at and (datetime.now(timezone.utc) - result.created_at).days < 7:
                        result.ranking_score *= 1.5
                results.sort(key=lambda x: x.ranking_score, reverse=True)
        
        return results
    
    def _generate_vector_explanation(self, search_result: SearchResult, threshold: float) -> str:
        """Generate explanation for vector search result."""
        similarity = search_result.similarity
        
        if similarity >= 0.9:
            return f"Very high semantic similarity ({similarity:.3f}) to query"
        elif similarity >= 0.7:
            return f"High semantic similarity ({similarity:.3f}) to query"
        elif similarity >= threshold:
            return f"Good semantic similarity ({similarity:.3f}) to query"
        else:
            return f"Low semantic similarity ({similarity:.3f}) to query"
    
    def _generate_node_explanation(self, node: KnowledgeNode, entity: str, relevance: float) -> str:
        """Generate explanation for node search result."""
        return f"Node '{node.title}' matches entity '{entity}' with relevance {relevance:.3f}"
    
    def _generate_traversal_explanation(self, node_data: Dict[str, Any]) -> str:
        """Generate explanation for traversal result."""
        return f"Node found at depth {node_data.get('depth', 0)} in graph traversal"
    
    def _generate_cache_key(
        self,
        query: str,
        mode: RetrievalMode,
        strategy: RetrievalStrategy,
        filters: Optional[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for retrieval."""
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
        if cache_key not in self.retrieval_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_retrieval(self, cache_key: str, results: List[RetrievalResult]) -> None:
        """Cache retrieval results."""
        self.retrieval_cache[cache_key] = results
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
            if key in self.retrieval_cache:
                del self.retrieval_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    async def retrieve_related(
        self,
        item_id: str,
        item_type: str = "node",
        relationship_types: Optional[List[str]] = None,
        max_depth: int = 2,
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        Retrieve related items based on relationships.
        
        Args:
            item_id: Starting item ID
            item_type: Type of starting item
            relationship_types: Types of relationships to follow
            max_depth: Maximum traversal depth
            top_k: Number of results to return
            
        Returns:
            List of related items
        """
        try:
            if item_type == "node":
                # Use graph traversal to find related nodes
                traversal_result = await self.graph_traverser.breadth_first_search(
                    start_node_id=item_id,
                    max_depth=max_depth,
                    max_nodes=top_k,
                    include_metadata=True
                )
                
                # Convert to retrieval results
                results = []
                for node_data in traversal_result["traversal_order"][1:]:  # Skip start node
                    result = RetrievalResult(
                        item_id=node_data["id"],
                        item_type="node",
                        content=node_data.get("content", ""),
                        title=node_data["title"],
                        description=node_data.get("description"),
                        metadata=node_data.get("metadata", {}),
                        relevance_score=1.0 / (node_data["depth"] + 1),
                        confidence_score=node_data.get("confidence_score", 0.0),
                        quality_score=node_data.get("quality_score", 0.0),
                        ranking_score=1.0 / (node_data["depth"] + 1),
                        source=node_data.get("source"),
                        created_at=None,
                        explanation=f"Related node at depth {node_data.get('depth', 0)}"
                    )
                    results.append(result)
                
                return results[:top_k]
            
            return []
            
        except Exception as e:
            logger.error(
                "Related items retrieval failed",
                error=str(e),
                item_id=item_id,
                item_type=item_type
            )
            raise BaseLayerError(f"Related items retrieval failed: {str(e)}") from e
    
    async def retrieve_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        top_k: int = 50
    ) -> List[RetrievalResult]:
        """
        Retrieve items based on metadata filters.
        
        Args:
            metadata_filters: Metadata filters
            top_k: Number of results to return
            
        Returns:
            List of matching items
        """
        try:
            # This would search database based on metadata
            # Placeholder implementation
            return []
            
        except Exception as e:
            logger.error(
                "Metadata retrieval failed",
                error=str(e),
                metadata_filters=metadata_filters
            )
            raise BaseLayerError(f"Metadata retrieval failed: {str(e)}") from e
    
    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return {
            "total_retrievals": self.retrieval_stats["total_retrievals"],
            "successful_retrievals": self.retrieval_stats["successful_retrievals"],
            "failed_retrievals": self.retrieval_stats["failed_retrievals"],
            "success_rate": (
                self.retrieval_stats["successful_retrievals"] / self.retrieval_stats["total_retrievals"]
                if self.retrieval_stats["total_retrievals"] > 0 else 0.0
            ),
            "average_retrieval_time_ms": self.retrieval_stats["average_retrieval_time_ms"],
            "average_results_count": self.retrieval_stats["average_results_count"],
            "cache_hits": self.retrieval_stats["cache_hits"],
            "cache_misses": self.retrieval_stats["cache_misses"],
            "cache_hit_rate": (
                self.retrieval_stats["cache_hits"] / 
                (self.retrieval_stats["cache_hits"] + self.retrieval_stats["cache_misses"])
                if (self.retrieval_stats["cache_hits"] + self.retrieval_stats["cache_misses"]) > 0 else 0.0
            ),
            "cache_size": len(self.retrieval_cache)
        }
    
    def reset_stats(self) -> None:
        """Reset retrieval statistics."""
        self.retrieval_stats = {
            "total_retrievals": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "average_retrieval_time_ms": 0,
            "average_results_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def clear_cache(self) -> None:
        """Clear retrieval cache."""
        self.retrieval_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Knowledge retriever cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on knowledge retriever."""
        try:
            # Test basic retrieval
            test_query = "test knowledge retrieval"
            test_results = await self.retrieve(
                query=test_query,
                top_k=3,
                use_cache=False
            )
            
            # Test dependencies
            vector_store_health = await self.vector_store.health_check()
            
            health_status = {
                "status": "healthy",
                "retrieval_working": True,
                "test_results_count": len(test_results),
                "vector_store_health": vector_store_health,
                "cache_size": len(self.retrieval_cache),
                "stats": self.get_retrieval_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Knowledge retriever health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Knowledge retriever health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
