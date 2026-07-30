"""
CODEX Vector Store

PostgreSQL + pgvector integration for storing and searching
vector embeddings with IVFFlat indexing.
"""

import uuid
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_, func
from sqlalchemy.dialects.postgresql import vector

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..models.knowledge_entry import KnowledgeEntry

logger = get_logger(__name__)


class VectorStore:
    """
    PostgreSQL + pgvector integration for vector storage and search.
    
    Uses IVFFlat indexing for fast semantic search on knowledge
    entries with cosine similarity.
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        index_type: str = "ivfflat",
        distance_metric: str = "cosine",
        list_count: int = 100
    ):
        """
        Initialize vector store.
        
        Args:
            db_session: Async SQLAlchemy session
            index_type: pgvector index type (ivfflat or hnsw)
            distance_metric: Distance metric (cosine, euclidean, manhattan)
            list_count: Number of lists for IVFFlat index
        """
        self.db = db_session
        self.index_type = index_type
        self.distance_metric = distance_metric
        self.list_count = list_count
        
        logger.info("VectorStore initialized", 
                   index_type=index_type,
                   distance_metric=distance_metric,
                   list_count=list_count)
    
    async def store_embedding(self, entry_id: uuid.UUID, embedding: List[float]) -> bool:
        """
        Store embedding for a knowledge entry.
        
        Args:
            entry_id: Knowledge entry ID
            embedding: Embedding vector
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update the entry with embedding
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            result = await self.db.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if not entry:
                logger.error("Knowledge entry not found", entry_id=str(entry_id))
                return False
            
            # Update embedding
            entry.embedding = embedding
            await self.db.commit()
            
            logger.debug("Embedding stored", entry_id=str(entry_id))
            return True
            
        except Exception as e:
            logger.error("Failed to store embedding", 
                        entry_id=str(entry_id), 
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def store_batch_embeddings(self, embeddings: Dict[uuid.UUID, List[float]]) -> int:
        """
        Store multiple embeddings efficiently.
        
        Args:
            embeddings: Dictionary of entry_id -> embedding
            
        Returns:
            Number of embeddings stored successfully
        """
        if not embeddings:
            return 0
        
        try:
            # Get all entries
            entry_ids = list(embeddings.keys())
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.id.in_(entry_ids))
            result = await self.db.execute(stmt)
            entries = result.scalars().all()
            
            # Update embeddings
            stored_count = 0
            for entry in entries:
                if entry.id in embeddings:
                    entry.embedding = embeddings[entry.id]
                    stored_count += 1
            
            await self.db.commit()
            
            logger.info("Batch embeddings stored", 
                       total_requested=len(embeddings),
                       stored=stored_count)
            
            return stored_count
            
        except Exception as e:
            logger.error("Failed to store batch embeddings", error=str(e))
            await self.db.rollback()
            return 0
    
    async def search_similar(
        self, 
        query_vector: List[float], 
        limit: int = 10,
        threshold: float = 0.5,
        exclude_archived: bool = True
    ) -> List[Tuple[uuid.UUID, float, Dict[str, Any]]]:
        """
        Search for similar entries using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            exclude_archived: Whether to exclude archived entries
            
        Returns:
            List of (entry_id, similarity_score, entry_data) tuples
        """
        try:
            # Build query with vector similarity
            if self.distance_metric == "cosine":
                # Cosine similarity query
                similarity_expr = text("1 - (embedding <=> :query_vector)")
            else:
                # Default to cosine similarity
                similarity_expr = text("1 - (embedding <=> :query_vector)")
            
            # Base query
            query = select(
                KnowledgeEntry.id,
                similarity_expr.label('similarity'),
                KnowledgeEntry.key,
                KnowledgeEntry.value,
                KnowledgeEntry.entry_type,
                KnowledgeEntry.source_engine,
                KnowledgeEntry.source_agent,
                KnowledgeEntry.confidence,
                KnowledgeEntry.tags,
                KnowledgeEntry.access_count,
                KnowledgeEntry.last_accessed_at,
                KnowledgeEntry.created_at
            ).where(
                and_(
                    KnowledgeEntry.embedding.isnot(None),
                    similarity_expr >= threshold
                )
            )
            
            # Exclude archived if requested
            if exclude_archived:
                query = query.where(KnowledgeEntry.is_archived == False)
            
            # Order by similarity and limit
            query = query.order_by(text('similarity DESC')).limit(limit)
            
            # Execute query
            result = await self.db.execute(query, {"query_vector": query_vector})
            rows = result.all()
            
            # Format results
            results = []
            for row in rows:
                entry_data = {
                    "key": row.key,
                    "value": row.value,
                    "entry_type": row.entry_type,
                    "source_engine": row.source_engine,
                    "source_agent": row.source_agent,
                    "confidence": row.confidence,
                    "tags": row.tags,
                    "access_count": row.access_count,
                    "last_accessed_at": row.last_accessed_at,
                    "created_at": row.created_at
                }
                results.append((row.id, float(row.similarity), entry_data))
            
            logger.debug("Vector search completed", 
                       query_vector_length=len(query_vector),
                       threshold=threshold,
                       results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            return []
    
    async def search_by_filters(
        self,
        query_vector: List[float],
        filters: Dict[str, Any],
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Tuple[uuid.UUID, float, Dict[str, Any]]]:
        """
        Search with additional filters.
        
        Args:
            query_vector: Query embedding vector
            filters: Dictionary of filters (entry_type, source_engine, tags, etc.)
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of (entry_id, similarity_score, entry_data) tuples
        """
        try:
            # Build base query
            similarity_expr = text("1 - (embedding <=> :query_vector)")
            
            query = select(
                KnowledgeEntry.id,
                similarity_expr.label('similarity'),
                KnowledgeEntry.key,
                KnowledgeEntry.value,
                KnowledgeEntry.entry_type,
                KnowledgeEntry.source_engine,
                KnowledgeEntry.source_agent,
                KnowledgeEntry.confidence,
                KnowledgeEntry.tags,
                KnowledgeEntry.access_count,
                KnowledgeEntry.last_accessed_at,
                KnowledgeEntry.created_at
            ).where(
                and_(
                    KnowledgeEntry.embedding.isnot(None),
                    similarity_expr >= threshold
                )
            )
            
            # Apply filters
            if "entry_type" in filters:
                query = query.where(KnowledgeEntry.entry_type == filters["entry_type"])
            
            if "source_engine" in filters:
                query = query.where(KnowledgeEntry.source_engine == filters["source_engine"])
            
            if "source_agent" in filters:
                query = query.where(KnowledgeEntry.source_agent == filters["source_agent"])
            
            if "tags" in filters and filters["tags"]:
                # Filter by tags (contains any)
                query = query.where(KnowledgeEntry.tags.overlap(filters["tags"]))
            
            if "confidence_min" in filters:
                query = query.where(KnowledgeEntry.confidence >= filters["confidence_min"])
            
            if "confidence_max" in filters:
                query = query.where(KnowledgeEntry.confidence <= filters["confidence_max"])
            
            if "exclude_archived" in filters and filters["exclude_archived"]:
                query = query.where(KnowledgeEntry.is_archived == False)
            
            # Order and limit
            query = query.order_by(text('similarity DESC')).limit(limit)
            
            # Execute query
            result = await self.db.execute(query, {"query_vector": query_vector})
            rows = result.all()
            
            # Format results
            results = []
            for row in rows:
                entry_data = {
                    "key": row.key,
                    "value": row.value,
                    "entry_type": row.entry_type,
                    "source_engine": row.source_engine,
                    "source_agent": row.source_agent,
                    "confidence": row.confidence,
                    "tags": row.tags,
                    "access_count": row.access_count,
                    "last_accessed_at": row.last_accessed_at,
                    "created_at": row.created_at
                }
                results.append((row.id, float(row.similarity), entry_data))
            
            return results
            
        except Exception as e:
            logger.error("Filtered vector search failed", error=str(e))
            return []
    
    async def delete_embedding(self, entry_id: uuid.UUID) -> bool:
        """
        Delete embedding for a knowledge entry.
        
        Args:
            entry_id: Knowledge entry ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Set embedding to null
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            result = await self.db.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if not entry:
                logger.error("Knowledge entry not found", entry_id=str(entry_id))
                return False
            
            entry.embedding = None
            await self.db.commit()
            
            logger.debug("Embedding deleted", entry_id=str(entry_id))
            return True
            
        except Exception as e:
            logger.error("Failed to delete embedding", 
                        entry_id=str(entry_id), 
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored embeddings.
        
        Returns:
            Dictionary with embedding statistics
        """
        try:
            # Total entries with embeddings
            total_with_embeddings = await self.db.scalar(
                select(func.count(KnowledgeEntry.id)).where(
                    KnowledgeEntry.embedding.isnot(None)
                )
            )
            
            # Total entries
            total_entries = await self.db.scalar(
                select(func.count(KnowledgeEntry.id))
            )
            
            # Coverage percentage
            coverage = (total_with_embeddings / total_entries * 100) if total_entries > 0 else 0
            
            # By entry type
            by_type = {}
            type_query = select(
                KnowledgeEntry.entry_type,
                func.count(KnowledgeEntry.id)
            ).where(
                KnowledgeEntry.embedding.isnot(None)
            ).group_by(KnowledgeEntry.entry_type)
            
            type_result = await self.db.execute(type_query)
            for row in type_result:
                by_type[row.entry_type] = row.count
            
            # By source engine
            by_engine = {}
            engine_query = select(
                KnowledgeEntry.source_engine,
                func.count(KnowledgeEntry.id)
            ).where(
                KnowledgeEntry.embedding.isnot(None)
            ).group_by(KnowledgeEntry.source_engine)
            
            engine_result = await self.db.execute(engine_query)
            for row in engine_result:
                by_engine[row.source_engine] = row.count
            
            return {
                "total_entries": total_entries,
                "entries_with_embeddings": total_with_embeddings,
                "coverage_percentage": coverage,
                "by_entry_type": by_type,
                "by_source_engine": by_engine,
                "index_type": self.index_type,
                "distance_metric": self.distance_metric
            }
            
        except Exception as e:
            logger.error("Failed to get embedding stats", error=str(e))
            return {"error": str(e)}
    
    async def create_vector_index(self) -> bool:
        """
        Create vector index for efficient search.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create IVFFlat index
            if self.index_type == "ivfflat":
                index_sql = text(f"""
                    CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_ivfflat 
                    ON codex_knowledge_entries 
                    USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = {self.list_count})
                """)
            else:
                # HNSW index (alternative)
                index_sql = text("""
                    CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_hnsw 
                    ON codex_knowledge_entries 
                    USING hnsw (embedding vector_cosine_ops)
                """)
            
            await self.db.execute(index_sql)
            await self.db.commit()
            
            logger.info("Vector index created", 
                       index_type=self.index_type,
                       list_count=self.list_count)
            
            return True
            
        except Exception as e:
            logger.error("Failed to create vector index", error=str(e))
            await self.db.rollback()
            return False
    
    async def drop_vector_index(self) -> bool:
        """
        Drop vector index.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            index_name = f"idx_knowledge_embedding_{self.index_type}"
            drop_sql = text(f"DROP INDEX IF EXISTS {index_name}")
            
            await self.db.execute(drop_sql)
            await self.db.commit()
            
            logger.info("Vector index dropped", index_name=index_name)
            return True
            
        except Exception as e:
            logger.error("Failed to drop vector index", error=str(e))
            await self.db.rollback()
            return False
    
    async def rebuild_vector_index(self) -> bool:
        """
        Rebuild vector index (drop and recreate).
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Rebuilding vector index")
        
        # Drop existing index
        drop_success = await self.drop_vector_index()
        if not drop_success:
            return False
        
        # Create new index
        create_success = await self.create_vector_index()
        return create_success
    
    async def optimize_vector_search(self) -> Dict[str, Any]:
        """
        Optimize vector search performance.
        
        Returns:
            Dictionary with optimization results
        """
        try:
            results = {}
            
            # Analyze table
            await self.db.execute(text("ANALYZE codex_knowledge_entries"))
            results["analyzed"] = True
            
            # Check index exists
            index_query = text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'codex_knowledge_entries' 
                AND indexname LIKE '%embedding%'
            """)
            
            index_result = await self.db.execute(index_query)
            indexes = index_result.all()
            
            results["existing_indexes"] = [
                {"name": row.indexname, "definition": row.indexdef} 
                for row in indexes
            ]
            
            # Get table size
            size_query = text("""
                SELECT 
                    pg_total_relation_size('codex_knowledge_entries') as total_size,
                    pg_relation_size('codex_knowledge_entries') as table_size
            """)
            
            size_result = await self.db.execute(size_query)
            size_data = size_result.first()
            
            results["table_size_mb"] = size_data.total_size / (1024 * 1024)
            results["table_size_only_mb"] = size_data.table_size / (1024 * 1024)
            
            await self.db.commit()
            
            logger.info("Vector search optimization completed", results=results)
            return results
            
        except Exception as e:
            logger.error("Vector search optimization failed", error=str(e))
            return {"error": str(e)}
    
    async def validate_embedding_dimensions(self, expected_dimensions: int) -> Dict[str, Any]:
        """
        Validate that all embeddings have expected dimensions.
        
        Args:
            expected_dimensions: Expected embedding dimension
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Check for invalid dimensions
            invalid_query = text("""
                SELECT COUNT(*) as count
                FROM codex_knowledge_entries 
                WHERE embedding IS NOT NULL 
                AND array_length(embedding, 1) != :expected_dimensions
            """)
            
            result = await self.db.execute(invalid_query, {"expected_dimensions": expected_dimensions})
            invalid_count = result.scalar()
            
            # Get total with embeddings
            total_query = text("""
                SELECT COUNT(*) as count
                FROM codex_knowledge_entries 
                WHERE embedding IS NOT NULL
            """)
            
            total_result = await self.db.execute(total_query)
            total_count = total_result.scalar()
            
            validation_result = {
                "expected_dimensions": expected_dimensions,
                "total_with_embeddings": total_count,
                "invalid_dimensions": invalid_count,
                "valid_percentage": ((total_count - invalid_count) / total_count * 100) if total_count > 0 else 100,
                "is_valid": invalid_count == 0
            }
            
            if invalid_count > 0:
                logger.warning("Invalid embedding dimensions found", validation_result)
            else:
                logger.info("Embedding dimensions validated", validation_result)
            
            return validation_result
            
        except Exception as e:
            logger.error("Embedding dimension validation failed", error=str(e))
            return {"error": str(e)}
