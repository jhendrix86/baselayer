"""
BaseLayer Search Engine

Full-text and semantic search capabilities for the Codex/Memory subsystem.
"""

import asyncio
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_, text
from sqlalchemy.sql.expression import cast
from sqlalchemy.dialects.postgresql import TSVECTOR
from structlog import get_logger

from ..core.database import db_session_context
from ..models.codex import (
    KnowledgeEntry, KnowledgeTag, SearchIndex,
    KnowledgeStatus, EntryType
)
from .exceptions import SearchError

logger = get_logger(__name__)


class SearchEngine:
    """
    Advanced search engine with full-text and semantic search.
    
    Supports multiple search types, ranking, and optimization
    with performance tuning for i5-2400 hardware.
    """
    
    def __init__(self):
        self.search_cache: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}
        self.cache_ttl: int = 600  # 10 minutes
        self.max_results: int = 100
        self.semantic_enabled: bool = True
        self.ai_model_timeout: int = 30  # seconds
    
    async def search(
        self,
        query: str,
        search_type: str = "full_text",
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        include_highlights: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge entries.
        
        Args:
            query: Search query
            search_type: Type of search (full_text, semantic, hybrid)
            limit: Maximum number of results
            offset: Pagination offset
            filters: Additional filters
            sort_by: Sort method (relevance, date, title)
            include_highlights: Whether to include search highlights
            
        Returns:
            List[Dict[str, Any]]: Search results
        """
        # Check cache first
        cache_key = self._generate_cache_key(query, search_type, filters, sort_by)
        cached_results = self._get_from_cache(cache_key)
        
        if cached_results:
            return cached_results[offset:offset + limit]
        
        try:
            if search_type == "full_text":
                results = await self._full_text_search(query, limit, offset, filters, sort_by, include_highlights)
            elif search_type == "semantic":
                results = await self._semantic_search(query, limit, offset, filters, sort_by, include_highlights)
            elif search_type == "hybrid":
                results = await self._hybrid_search(query, limit, offset, filters, sort_by, include_highlights)
            else:
                raise SearchError(f"Unknown search type: {search_type}", search_type=search_type)
            
            # Cache results
            self._set_cache(cache_key, results)
            
            return results
            
        except Exception as e:
            logger.error(
                "Search operation failed",
                query=query,
                search_type=search_type,
                error=str(e)
            )
            raise SearchError(f"Search failed: {str(e)}", search_query=query) from e
    
    async def _full_text_search(
        self,
        query: str,
        limit: int,
        offset: int,
        filters: Optional[Dict[str, Any]],
        sort_by: str,
        include_highlights: bool
    ) -> List[Dict[str, Any]]:
        """Perform full-text search using PostgreSQL tsvector."""
        async with db_session_context() as session:
            # Build base query with full-text search
            search_query = f"""
                SELECT 
                    ke.*,
                    ts_rank(search_vector, plainto_tsquery(:query)) as relevance,
                    ts_headline('english', ke.content, plainto_tsquery(:query)) as highlight
                FROM knowledge_entries ke
                WHERE 
                    ke.deleted_at IS NULL
                    AND search_vector @@ plainto_tsquery(:query)
            """
            
            # Add filters
            where_conditions = []
            params = {"query": query}
            
            if filters:
                if filters.get("status"):
                    where_conditions.append("ke.status = :status")
                    params["status"] = filters["status"]
                
                if filters.get("entry_type"):
                    where_conditions.append("ke.entry_type = :entry_type")
                    params["entry_type"] = filters["entry_type"]
                
                if filters.get("knowledge_type"):
                    where_conditions.append("ke.knowledge_type = :knowledge_type")
                    params["knowledge_type"] = filters["knowledge_type"]
                
                if filters.get("category_id"):
                    where_conditions.append("ke.category_id = :category_id")
                    params["category_id"] = filters["category_id"]
                
                if filters.get("language"):
                    where_conditions.append("ke.language = :language")
                    params["language"] = filters["language"]
                
                if filters.get("author"):
                    where_conditions.append("ke.author ILIKE :author")
                    params["author"] = f"%{filters['author']}%"
                
                if filters.get("tags"):
                    # Join with tags
                    search_query += """
                        AND ke.id IN (
                            SELECT ket.knowledge_entry_id
                            FROM knowledge_entry_tags ket
                            JOIN knowledge_tags kt ON kt.id = ket.knowledge_tag_id
                            WHERE kt.name IN :tags
                        )
                    """
                    params["tags"] = tuple(filters["tags"])
                
                if where_conditions:
                    search_query += " AND " + " AND ".join(where_conditions)
            
            # Add sorting
            if sort_by == "relevance":
                search_query += " ORDER BY relevance DESC, ke.created_at DESC"
            elif sort_by == "date":
                search_query += " ORDER BY ke.created_at DESC"
            elif sort_by == "title":
                search_query += " ORDER BY ke.title ASC"
            else:
                search_query += " ORDER BY relevance DESC"
            
            # Add pagination
            search_query += " LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
            
            # Execute query
            result = await session.execute(text(search_query), params)
            rows = result.fetchall()
            
            results = []
            for row in rows:
                entry_data = {
                    "id": str(row.id),
                    "title": row.title,
                    "content": row.content if include_highlights else None,
                    "entry_type": row.entry_type.value,
                    "knowledge_type": row.knowledge_type.value,
                    "language": row.language,
                    "access_level": row.access_level,
                    "status": row.status.value,
                    "author": row.author,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "relevance": float(row.relevance),
                    "search_type": "full_text"
                }
                
                if include_highlights and hasattr(row, 'highlight'):
                    entry_data["highlight"] = row.highlight
                
                results.append(entry_data)
            
            return results
    
    async def _semantic_search(
        self,
        query: str,
        limit: int,
        offset: int,
        filters: Optional[Dict[str, Any]],
        sort_by: str,
        include_highlights: bool
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using AI embeddings."""
        if not self.semantic_enabled:
            # Fallback to full-text search
            return await self._full_text_search(query, limit, offset, filters, sort_by, include_highlights)
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query)
            
            # Search for similar entries
            async with db_session_context() as session:
                # Get entries with embeddings
                base_query = select(KnowledgeEntry).where(
                    KnowledgeEntry.deleted_at.is_(None),
                    KnowledgeEntry.embedding.is_not(None)
                )
                
                # Apply filters
                if filters:
                    if filters.get("status"):
                        base_query = base_query.where(KnowledgeEntry.status == filters["status"])
                    
                    if filters.get("entry_type"):
                        base_query = base_query.where(KnowledgeEntry.entry_type == filters["entry_type"])
                    
                    if filters.get("knowledge_type"):
                        base_query = base_query.where(KnowledgeEntry.knowledge_type == filters["knowledge_type"])
                    
                    if filters.get("category_id"):
                        base_query = base_query.where(KnowledgeEntry.category_id == uuid.UUID(filters["category_id"]))
                    
                    if filters.get("language"):
                        base_query = base_query.where(KnowledgeEntry.language == filters["language"])
                    
                    if filters.get("author"):
                        base_query = base_query.where(KnowledgeEntry.author.ilike(f"%{filters['author']}%"))
                
                # Get all matching entries
                result = await session.execute(base_query)
                entries = result.scalars().all()
                
                # Calculate similarity scores
                scored_entries = []
                for entry in entries:
                    if entry.embedding:
                        similarity = self._calculate_similarity(query_embedding, entry.embedding)
                        scored_entries.append((entry, similarity))
                
                # Sort by similarity
                scored_entries.sort(key=lambda x: x[1], reverse=True)
                
                # Apply pagination
                paginated_entries = scored_entries[offset:offset + limit]
                
                results = []
                for entry, similarity in paginated_entries:
                    entry_data = {
                        "id": str(entry.id),
                        "title": entry.title,
                        "content": entry.content if include_highlights else None,
                        "entry_type": entry.entry_type.value,
                        "knowledge_type": entry.knowledge_type.value,
                        "language": entry.language,
                        "access_level": entry.access_level,
                        "status": entry.status.value,
                        "author": entry.author,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                        "relevance": similarity,
                        "search_type": "semantic"
                    }
                    
                    if include_highlights:
                        entry_data["highlight"] = self._generate_semantic_highlight(entry, query)
                    
                    results.append(entry_data)
                
                return results
                
        except Exception as e:
            logger.error(
                "Semantic search failed, falling back to full-text",
                query=query,
                error=str(e)
            )
            return await self._full_text_search(query, limit, offset, filters, sort_by, include_highlights)
    
    async def _hybrid_search(
        self,
        query: str,
        limit: int,
        offset: int,
        filters: Optional[Dict[str, Any]],
        sort_by: str,
        include_highlights: bool
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining full-text and semantic."""
        try:
            # Get results from both search types
            full_text_results = await self._full_text_search(query, limit * 2, 0, filters, "relevance", include_highlights)
            semantic_results = await self._semantic_search(query, limit * 2, 0, filters, "relevance", include_highlights)
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Add full-text results with weight
            for result in full_text_results:
                entry_id = result["id"]
                if entry_id not in combined_results:
                    combined_results[entry_id] = result.copy()
                    combined_results[entry_id]["ft_relevance"] = result["relevance"]
                    combined_results[entry_id]["semantic_relevance"] = 0.0
                else:
                    # Update relevance if better
                    if result["relevance"] > combined_results[entry_id]["ft_relevance"]:
                        combined_results[entry_id]["ft_relevance"] = result["relevance"]
            
            # Add semantic results with weight
            for result in semantic_results:
                entry_id = result["id"]
                if entry_id not in combined_results:
                    combined_results[entry_id] = result.copy()
                    combined_results[entry_id]["ft_relevance"] = 0.0
                    combined_results[entry_id]["semantic_relevance"] = result["relevance"]
                else:
                    # Update relevance if better
                    if result["relevance"] > combined_results[entry_id]["semantic_relevance"]:
                        combined_results[entry_id]["semantic_relevance"] = result["relevance"]
            
            # Calculate hybrid relevance (weighted average)
            for entry_id, result in combined_results.items():
                ft_weight = 0.6  # Full-text gets higher weight
                semantic_weight = 0.4
                
                hybrid_relevance = (
                    result["ft_relevance"] * ft_weight +
                    result["semantic_relevance"] * semantic_weight
                )
                
                result["relevance"] = hybrid_relevance
                result["search_type"] = "hybrid"
            
            # Sort by hybrid relevance
            sorted_results = sorted(
                combined_results.values(),
                key=lambda x: x["relevance"],
                reverse=True
            )
            
            # Apply pagination
            paginated_results = sorted_results[offset:offset + limit]
            
            return paginated_results
            
        except Exception as e:
            logger.error(
                "Hybrid search failed, falling back to full-text",
                query=query,
                error=str(e)
            )
            return await self._full_text_search(query, limit, offset, filters, sort_by, include_highlights)
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query."""
        # In real implementation, this would call an AI model
        # For now, return a mock embedding
        import hashlib
        
        # Create a simple hash-based embedding
        hash_object = hashlib.md5(query.encode())
        hash_hex = hash_object.hexdigest()
        
        # Convert to float values (simplified)
        embedding = []
        for i in range(0, len(hash_hex), 2):
            byte_val = int(hash_hex[i:i+2], 16)
            embedding.append(byte_val / 255.0)
        
        # Pad to 384 dimensions (common for embeddings)
        while len(embedding) < 384:
            embedding.append(0.0)
        
        return embedding[:384]
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        if len(embedding1) != len(embedding2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(b * b for b in embedding2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _generate_semantic_highlight(self, entry: KnowledgeEntry, query: str) -> str:
        """Generate semantic search highlight."""
        # Simple keyword highlighting
        query_words = query.lower().split()
        content = entry.content
        
        # Find first occurrence of any query word
        for word in query_words:
            if word in content.lower():
                start_idx = content.lower().find(word)
                if start_idx != -1:
                    # Extract context around the match
                    start = max(0, start_idx - 100)
                    end = min(len(content), start_idx + len(word) + 100)
                    snippet = content[start:end]
                    
                    # Highlight the matched word
                    highlighted = snippet.replace(word, f"**{word}**")
                    return f"...{highlighted}..."
        
        # Return first 200 characters if no match found
        return content[:200] + "..."
    
    async def search_suggestions(
        self,
        query: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            query: Partial search query
            limit: Maximum number of suggestions
            
        Returns:
            List[str]: Search suggestions
        """
        async with db_session_context() as session:
            # Search for titles that start with the query
            result = await session.execute(
                select(KnowledgeEntry.title).where(
                    KnowledgeEntry.deleted_at.is_(None),
                    KnowledgeEntry.title.ilike(f"{query}%")
                ).limit(limit)
            )
            
            suggestions = [row[0] for row in result.all()]
            
            # Add popular search terms if needed
            if len(suggestions) < limit:
                popular_terms = await self._get_popular_search_terms(limit - len(suggestions))
                suggestions.extend(popular_terms)
            
            return suggestions[:limit]
    
    async def _get_popular_search_terms(self, limit: int) -> List[str]:
        """Get popular search terms."""
        # In real implementation, this would come from search analytics
        # For now, return mock popular terms
        popular_terms = [
            "system architecture",
            "database design",
            "API documentation",
            "security best practices",
            "performance optimization",
            "workflow automation",
            "user management",
            "revenue tracking",
            "knowledge base",
            "troubleshooting guide"
        ]
        
        return popular_terms[:limit]
    
    async def get_search_analytics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get search analytics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Search analytics
        """
        # In real implementation, this would query search logs
        # For now, return mock analytics
        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "total_searches": 1250,
            "unique_queries": 890,
            "average_results_per_search": 15.5,
            "zero_results_rate": 0.08,
            "popular_queries": [
                {"query": "system architecture", "count": 45},
                {"query": "database design", "count": 38},
                {"query": "API documentation", "count": 32}
            ],
            "search_types": {
                "full_text": 0.65,
                "semantic": 0.25,
                "hybrid": 0.10
            },
            "average_response_time_ms": 120
        }
    
    def _generate_cache_key(
        self,
        query: str,
        search_type: str,
        filters: Optional[Dict[str, Any]],
        sort_by: str
    ) -> str:
        """Generate cache key for search results."""
        import hashlib
        
        key_data = f"{query}:{search_type}:{sort_by}"
        
        if filters:
            # Sort filter keys for consistent cache keys
            sorted_filters = sorted(filters.items())
            key_data += ":" + str(sorted_filters)
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get search results from cache."""
        if key not in self.search_cache:
            return None
        
        timestamp, results = self.search_cache[key]
        if datetime.utcnow() - timestamp > timedelta(seconds=self.cache_ttl):
            del self.search_cache[key]
            return None
        
        return results
    
    def _set_cache(self, key: str, results: List[Dict[str, Any]]) -> None:
        """Set search results in cache."""
        self.search_cache[key] = (datetime.utcnow(), results)
        
        # Limit cache size
        if len(self.search_cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self.search_cache.keys(),
                key=lambda k: self.search_cache[k][0]
            )[:100]
            
            for old_key in oldest_keys:
                del self.search_cache[old_key]
    
    def clear_cache(self) -> None:
        """Clear search cache."""
        self.search_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get search cache statistics."""
        return {
            "cache_size": len(self.search_cache),
            "cache_ttl": self.cache_ttl,
            "max_results": self.max_results,
            "semantic_enabled": self.semantic_enabled,
            "oldest_cache": min(
                (timestamp for timestamp, _ in self.search_cache.values()),
                default=None
            ) if self.search_cache else None
        }
