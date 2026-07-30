"""
CODEX Semantic Search

High-level semantic search combining vector similarity
with keyword filters and re-ranking capabilities.
"""

import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from .embedding_engine import EmbeddingEngine
from .vector_store import VectorStore
from ..models.knowledge_entry import KnowledgeEntry, KnowledgeEntryType

logger = get_logger(__name__)


class SemanticSearch:
    """
    High-level semantic search combining vector similarity
    with keyword filters and re-ranking.
    """
    
    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        vector_store: VectorStore,
        default_limit: int = 10,
        default_threshold: float = 0.5
    ):
        """
        Initialize semantic search.
        
        Args:
            embedding_engine: Embedding generation engine
            vector_store: Vector storage and search
            default_limit: Default result limit
            default_threshold: Default similarity threshold
        """
        self.embedding_engine = embedding_engine
        self.vector_store = vector_store
        self.default_limit = default_limit
        self.default_threshold = default_threshold
        
        logger.info("SemanticSearch initialized", 
                   default_limit=default_limit,
                   default_threshold=default_threshold)
    
    async def search(
        self,
        query: str,
        limit: Optional[int] = None,
        min_confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        source_engines: Optional[List[str]] = None,
        exclude_archived: bool = True,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search with filters.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            min_confidence: Minimum confidence score
            tags: Filter by tags
            entry_types: Filter by entry types
            source_engines: Filter by source engines
            exclude_archived: Whether to exclude archived entries
            threshold: Minimum similarity threshold
            
        Returns:
            List of search results with metadata
        """
        try:
            # Set defaults
            limit = limit or self.default_limit
            threshold = threshold or self.default_threshold
            
            # Generate query embedding
            query_vector = await self.embedding_engine.generate_embedding(query)
            
            # Build filters
            filters = {}
            if min_confidence is not None:
                filters["confidence_min"] = min_confidence
            if tags:
                filters["tags"] = tags
            if entry_types:
                filters["entry_type"] = entry_types[0]  # TODO: Support multiple types
            if source_engines:
                filters["source_engine"] = source_engines[0]  # TODO: Support multiple engines
            filters["exclude_archived"] = exclude_archived
            
            # Search vector store
            vector_results = await self.vector_store.search_by_filters(
                query_vector=query_vector,
                filters=filters,
                limit=limit,
                threshold=threshold
            )
            
            # Format results
            results = []
            for entry_id, similarity, entry_data in vector_results:
                result = {
                    "id": str(entry_id),
                    "similarity": similarity,
                    "key": entry_data["key"],
                    "value": entry_data["value"],
                    "entry_type": entry_data["entry_type"],
                    "source_engine": entry_data["source_engine"],
                    "source_agent": entry_data["source_agent"],
                    "confidence": entry_data["confidence"],
                    "tags": entry_data["tags"],
                    "access_count": entry_data["access_count"],
                    "last_accessed_at": entry_data["last_accessed_at"],
                    "created_at": entry_data["created_at"],
                    "search_weight": self._calculate_search_weight(similarity, entry_data)
                }
                results.append(result)
            
            # Sort by search weight
            results.sort(key=lambda x: x["search_weight"], reverse=True)
            
            logger.info("Semantic search completed", 
                       query_length=len(query),
                       filters_count=len(filters),
                       results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            return []
    
    async def hybrid_search(
        self,
        query: str,
        keyword_filters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query text
            keyword_filters: Keyword search filters
            tags: Filter by tags
            entry_types: Filter by entry types
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            rerank: Whether to re-rank results
            
        Returns:
            List of search results with metadata
        """
        try:
            # Semantic search
            semantic_results = await self.search(
                query=query,
                limit=limit,
                tags=tags,
                entry_types=entry_types,
                threshold=threshold
            )
            
            # Keyword search (if filters provided)
            keyword_results = []
            if keyword_filters:
                keyword_results = await self._keyword_search(
                    filters=keyword_filters,
                    tags=tags,
                    entry_types=entry_types,
                    limit=limit
                )
            
            # Combine results
            combined_results = self._combine_search_results(
                semantic_results, 
                keyword_results
            )
            
            # Re-rank if requested
            if rerank and len(combined_results) > 1:
                combined_results = await self._rerank_results(query, combined_results)
            
            # Apply final limit
            if limit:
                combined_results = combined_results[:limit]
            
            logger.info("Hybrid search completed", 
                       semantic_results=len(semantic_results),
                       keyword_results=len(keyword_results),
                       combined_results=len(combined_results),
                       reranked=rerank)
            
            return combined_results
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e))
            return []
    
    async def search_similar(
        self,
        entry_id: uuid.UUID,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find entries similar to a specific entry.
        
        Args:
            entry_id: Reference entry ID
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar entries
        """
        try:
            # Get the reference entry
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            result = await self.vector_store.db.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if not entry:
                logger.error("Reference entry not found", entry_id=str(entry_id))
                return []
            
            if not entry.embedding:
                logger.error("Reference entry has no embedding", entry_id=str(entry_id))
                return []
            
            # Search for similar entries
            similar_results = await self.vector_store.search_similar(
                query_vector=entry.embedding,
                limit=limit + 1,  # +1 to exclude the reference entry
                threshold=threshold
            )
            
            # Format results and exclude reference entry
            results = []
            for similar_id, similarity, entry_data in similar_results:
                if similar_id != entry_id:
                    result = {
                        "id": str(similar_id),
                        "similarity": similarity,
                        "key": entry_data["key"],
                        "value": entry_data["value"],
                        "entry_type": entry_data["entry_type"],
                        "source_engine": entry_data["source_engine"],
                        "source_agent": entry_data["source_agent"],
                        "confidence": entry_data["confidence"],
                        "tags": entry_data["tags"],
                        "access_count": entry_data["access_count"],
                        "last_accessed_at": entry_data["last_accessed_at"],
                        "created_at": entry_data["created_at"]
                    }
                    results.append(result)
            
            logger.info("Similar entries search completed", 
                       reference_id=str(entry_id),
                       results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Similar entries search failed", 
                        entry_id=str(entry_id), 
                        error=str(e))
            return []
    
    async def search_context(
        self,
        query: str,
        max_tokens: int = 4000,
        min_confidence: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Search and format results for LLM context injection.
        
        Args:
            query: Search query text
            max_tokens: Maximum tokens in context
            min_confidence: Minimum confidence score
            tags: Filter by tags
            
        Returns:
            Formatted context string for LLM
        """
        try:
            # Search for relevant entries
            results = await self.search(
                query=query,
                limit=50,  # Get more results to pack context
                min_confidence=min_confidence,
                tags=tags
            )
            
            if not results:
                return "No relevant knowledge found."
            
            # Pack context within token budget
            context_entries = []
            current_tokens = 0
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            for result in results:
                entry_text = f"Key: {result['key']}\nValue: {result['value']}\n"
                entry_tokens = len(entry_text) // 4
                
                if current_tokens + entry_tokens <= max_tokens:
                    context_entries.append({
                        "text": entry_text,
                        "similarity": result["similarity"],
                        "confidence": result["confidence"]
                    })
                    current_tokens += entry_tokens
                else:
                    break
            
            # Format context
            if not context_entries:
                return "No relevant knowledge fits within token budget."
            
            context_parts = [
                f"Knowledge Context (retrieved {len(context_entries)} entries, "
                f"~{current_tokens} tokens):\n"
            ]
            
            for i, entry in enumerate(context_entries, 1):
                context_parts.append(
                    f"{i}. {entry['text']}"
                    f"(similarity: {entry['similarity']:.3f}, "
                    f"confidence: {entry['confidence']:.3f})\n"
                )
            
            context = "".join(context_parts)
            
            logger.info("Context search completed", 
                       query_length=len(query),
                       max_tokens=max_tokens,
                       entries_packed=len(context_entries),
                       estimated_tokens=current_tokens)
            
            return context
            
        except Exception as e:
            logger.error("Context search failed", error=str(e))
            return "Error retrieving knowledge context."
    
    async def _keyword_search(
        self,
        filters: Dict[str, Any],
        tags: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform keyword-based search.
        
        Args:
            filters: Keyword filters
            tags: Filter by tags
            entry_types: Filter by entry types
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        try:
            # Build query
            query = select(KnowledgeEntry)
            
            # Apply filters
            if "key_contains" in filters:
                query = query.where(KnowledgeEntry.key.ilike(f"%{filters['key_contains']}%"))
            
            if "value_contains" in filters:
                query = query.where(KnowledgeEntry.value.ilike(f"%{filters['value_contains']}%"))
            
            if tags:
                query = query.where(KnowledgeEntry.tags.overlap(tags))
            
            if entry_types:
                query = query.where(KnowledgeEntry.entry_type.in_(entry_types))
            
            if "source_engine" in filters:
                query = query.where(KnowledgeEntry.source_engine == filters["source_engine"])
            
            if "confidence_min" in filters:
                query = query.where(KnowledgeEntry.confidence >= filters["confidence_min"])
            
            # Exclude archived
            query = query.where(KnowledgeEntry.is_archived == False)
            
            # Order by access count and confidence
            query = query.order_by(
                KnowledgeEntry.access_count.desc(),
                KnowledgeEntry.confidence.desc()
            ).limit(limit)
            
            # Execute query
            result = await self.vector_store.db.execute(query)
            entries = result.scalars().all()
            
            # Format results
            results = []
            for entry in entries:
                result = {
                    "id": str(entry.id),
                    "similarity": 0.0,  # No semantic similarity for keyword search
                    "key": entry.key,
                    "value": entry.value,
                    "entry_type": entry.entry_type,
                    "source_engine": entry.source_engine,
                    "source_agent": entry.source_agent,
                    "confidence": entry.confidence,
                    "tags": entry.tags,
                    "access_count": entry.access_count,
                    "last_accessed_at": entry.last_accessed_at,
                    "created_at": entry.created_at,
                    "search_weight": self._calculate_search_weight(0.0, entry.to_dict())
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error("Keyword search failed", error=str(e))
            return []
    
    def _combine_search_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword search results.
        
        Args:
            semantic_results: Semantic search results
            keyword_results: Keyword search results
            
        Returns:
            Combined and deduplicated results
        """
        # Combine results by ID
        combined = {}
        
        # Add semantic results
        for result in semantic_results:
            combined[result["id"]] = result
        
        # Add or merge keyword results
        for result in keyword_results:
            if result["id"] in combined:
                # Merge: boost existing result
                existing = combined[result["id"]]
                existing["search_weight"] *= 1.2  # Boost for appearing in both
            else:
                combined[result["id"]] = result
        
        # Convert to list and sort
        results = list(combined.values())
        results.sort(key=lambda x: x["search_weight"], reverse=True)
        
        return results
    
    async def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Re-rank search results using LLM for relevance.
        
        Args:
            query: Original search query
            results: Search results to re-rank
            
        Returns:
            Re-ranked results
        """
        try:
            # For now, implement simple re-ranking based on multiple factors
            # In a full implementation, this would use an LLM to score relevance
            
            reranked = results.copy()
            
            for result in reranked:
                # Calculate comprehensive score
                semantic_score = result["similarity"]
                confidence_score = result["confidence"]
                access_score = min(1.0, result["access_count"] / 100)  # Normalize access count
                
                # Weighted combination
                result["rerank_score"] = (
                    semantic_score * 0.5 +
                    confidence_score * 0.3 +
                    access_score * 0.2
                )
            
            # Sort by rerank score
            reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            # Update search weight
            for result in reranked:
                result["search_weight"] = result["rerank_score"]
            
            return reranked
            
        except Exception as e:
            logger.error("Result re-ranking failed", error=str(e))
            return results
    
    def _calculate_search_weight(
        self,
        similarity: float,
        entry_data: Dict[str, Any]
    ) -> float:
        """
        Calculate search weight for ranking.
        
        Args:
            similarity: Semantic similarity score
            entry_data: Entry data
            
        Returns:
            Search weight score
        """
        # Base weight from similarity
        weight = similarity
        
        # Boost from confidence
        confidence = entry_data.get("confidence", 0.0)
        weight += confidence * 0.2
        
        # Boost from access frequency
        access_count = entry_data.get("access_count", 0)
        access_boost = min(0.1, access_count / 1000)  # Cap at 0.1
        weight += access_boost
        
        # Boost from recent access
        last_accessed = entry_data.get("last_accessed_at")
        if last_accessed:
            days_since_access = (datetime.now(timezone.utc) - last_accessed).days
            if days_since_access < 7:
                weight += 0.1  # Recent access boost
        
        return min(1.0, weight)
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested queries
        """
        try:
            # For now, return simple suggestions based on entry keys
            # In a full implementation, this could use more sophisticated methods
            
            query = select(KnowledgeEntry.key).where(
                and_(
                    KnowledgeEntry.key.ilike(f"%{partial_query}%"),
                    KnowledgeEntry.is_archived == False
                )
            ).limit(limit)
            
            result = await self.vector_store.db.execute(query)
            keys = result.scalars().all()
            
            return list(keys)
            
        except Exception as e:
            logger.error("Search suggestions failed", error=str(e))
            return []
    
    async def analyze_search_patterns(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze search patterns and popular queries.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Search pattern analysis
        """
        try:
            # This would require search logging
            # For now, return basic statistics
            
            # Get most accessed entries
            query = select(
                KnowledgeEntry.key,
                KnowledgeEntry.access_count,
                KnowledgeEntry.entry_type
            ).where(
                KnowledgeEntry.is_archived == False
            ).order_by(
                KnowledgeEntry.access_count.desc()
            ).limit(10)
            
            result = await self.vector_store.db.execute(query)
            popular_entries = result.all()
            
            return {
                "popular_entries": [
                    {
                        "key": row.key,
                        "access_count": row.access_count,
                        "entry_type": row.entry_type
                    }
                    for row in popular_entries
                ],
                "analysis_period_days": days
            }
            
        except Exception as e:
            logger.error("Search pattern analysis failed", error=str(e))
            return {"error": str(e)}
