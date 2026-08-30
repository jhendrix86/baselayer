"""
BaseLayer Knowledge Indexer

Knowledge extraction, indexing, and search optimization
for the Codex/Memory subsystem.
"""

import asyncio
import hashlib
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from structlog import get_logger

from ..core.database import db_session_context
from ..models.codex import KnowledgeEntry, SearchIndex, SearchIndexType
from .exceptions import IndexError, AIModelError

logger = get_logger(__name__)


class KnowledgeIndexer:
    """
    Knowledge indexing and search optimization engine.
    
    Handles content extraction, embedding generation,
    and search index creation with AI integration.
    """
    
    def __init__(self):
        self.indexing_queue: asyncio.Queue = asyncio.Queue()
        self.indexing_active: bool = False
        self.max_concurrent_indexing: int = 2  # Optimized for i5-2400
        self.embedding_model: str = "text-embedding-ada-002"
        self.chunk_size: int = 1000  # Characters per chunk
        self.max_chunks: int = 10  # Maximum chunks per entry
    
    async def start_indexing_worker(self) -> None:
        """Start the background indexing worker."""
        if self.indexing_active:
            return
        
        self.indexing_active = True
        asyncio.create_task(self._indexing_worker_loop())
        
        logger.info("Knowledge indexing worker started")
    
    async def stop_indexing_worker(self) -> None:
        """Stop the indexing worker."""
        self.indexing_active = False
        logger.info("Knowledge indexing worker stopped")
    
    async def _indexing_worker_loop(self) -> None:
        """Main indexing worker loop."""
        while self.indexing_active:
            try:
                # Get next indexing task
                indexing_task = await asyncio.wait_for(
                    self.indexing_queue.get(),
                    timeout=60.0
                )
                await self._process_indexing_task(indexing_task)
                
            except asyncio.TimeoutError:
                # No indexing tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Indexing worker error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def index_entry(self, entry: KnowledgeEntry) -> None:
        """
        Index a knowledge entry for search, synchronously.

        Args:
            entry: Knowledge entry to index

        Note: this used to only enqueue onto self.indexing_queue for the
        background worker loop to drain - but nothing in this deployment
        ever calls start_indexing_worker() (no ARQ worker process is
        deployed; codex/tasks.py's initialize_codex() is never invoked),
        so every entry silently went unindexed forever. Does the real work
        directly instead - these are fast, single-row writes, fine to run
        inline on the request path.
        """
        await self._create_full_index(entry)

    async def update_index(self, entry: KnowledgeEntry) -> None:
        """
        Update search index for a knowledge entry, synchronously.

        Args:
            entry: Knowledge entry to update

        See index_entry()'s note - same reasoning applies here.
        """
        await self._update_full_index(entry)

    async def remove_from_index(self, entry_id: str) -> None:
        """
        Remove entry from search index, synchronously.

        Args:
            entry_id: Entry ID to remove

        See index_entry()'s note - same reasoning applies here.
        """
        await self._remove_full_index(entry_id)
    
    async def _process_indexing_task(self, task: Dict[str, Any]) -> None:
        """
        Process an indexing task.
        
        Args:
            task: Indexing task to process
        """
        try:
            task_type = task["type"]
            entry_id = task["entry_id"]
            
            if task_type == "index_entry":
                entry = task["entry"]
                await self._create_full_index(entry)
                
            elif task_type == "update_index":
                entry = task["entry"]
                await self._update_full_index(entry)
                
            elif task_type == "remove_index":
                await self._remove_full_index(entry_id)
                
            else:
                logger.warning(
                    "Unknown indexing task type",
                    task_type=task_type,
                    entry_id=entry_id
                )
                
        except Exception as e:
            logger.error(
                "Indexing task processing failed",
                task=task,
                error=str(e)
            )
    
    async def _create_full_index(self, entry: KnowledgeEntry) -> None:
        """
        Create full search index for an entry.
        
        Args:
            entry: Knowledge entry to index
        """
        async with db_session_context() as session:
            try:
                # Extract content and metadata
                content = self._extract_content(entry)
                metadata = self._extract_metadata(entry)
                
                # Generate search vector
                search_vector = self._generate_search_vector(content)
                
                # Generate embedding
                embedding = await self._generate_embedding(content)
                
                # Create search index record. embedding lives on
                # KnowledgeEntry itself (not SearchIndex, which has no such
                # column) - update the entry's own row for it.
                now = datetime.utcnow()
                search_index = SearchIndex(
                    entry_id=entry.id,
                    index_type=SearchIndexType.HYBRID,
                    indexed_content=search_vector,
                    token_count=str(len(search_vector.split())),
                    metadata_=metadata,
                    indexed_at=now,
                    last_updated_at=now
                )
                session.add(search_index)

                # entry.search_vector is what _full_text_search's real query
                # actually filters on (`search_vector @@ plainto_tsquery(...)`)
                # - a plain string assignment can't populate a real tsvector,
                # needs to_tsvector() computed in the UPDATE itself.
                entry_updates = {"search_vector": func.to_tsvector("english", content)}
                if embedding:
                    entry_updates["embedding"] = embedding

                await session.execute(
                    update(KnowledgeEntry)
                    .where(KnowledgeEntry.id == entry.id)
                    .values(**entry_updates)
                )

                await session.commit()

                logger.info(
                    "Search index created",
                    entry_id=str(entry.id),
                    content_length=len(content),
                    embedding_dim=len(embedding) if embedding else 0
                )
                
            except Exception as e:
                await session.rollback()
                raise IndexError(f"Failed to create index: {str(e)}") from e
    
    async def _update_full_index(self, entry: KnowledgeEntry) -> None:
        """
        Update full search index for an entry.
        
        Args:
            entry: Knowledge entry to update
        """
        async with db_session_context() as session:
            try:
                # Get existing index
                result = await session.execute(
                    select(SearchIndex).where(
                        SearchIndex.entry_id == entry.id
                    )
                )
                search_index = result.scalar_one_or_none()

                if search_index:
                    # Extract updated content and metadata
                    content = self._extract_content(entry)
                    metadata = self._extract_metadata(entry)

                    # Generate updated search vector and embedding
                    search_vector = self._generate_search_vector(content)
                    embedding = await self._generate_embedding(content)

                    # Update index
                    search_index.indexed_content = search_vector
                    search_index.token_count = str(len(search_vector.split()))
                    search_index.metadata_ = metadata
                    search_index.last_updated_at = datetime.utcnow()
                    session.add(search_index)

                    entry_updates = {"search_vector": func.to_tsvector("english", content)}
                    if embedding:
                        entry_updates["embedding"] = embedding

                    await session.execute(
                        update(KnowledgeEntry)
                        .where(KnowledgeEntry.id == entry.id)
                        .values(**entry_updates)
                    )

                    await session.commit()

                    logger.info(
                        "Search index updated",
                        entry_id=str(entry.id)
                    )
                else:
                    # Create new index if doesn't exist
                    await self._create_full_index(entry)
                
            except Exception as e:
                await session.rollback()
                raise IndexError(f"Failed to update index: {str(e)}") from e
    
    async def _remove_full_index(self, entry_id: str) -> None:
        """
        Remove search index for an entry.
        
        Args:
            entry_id: Entry ID to remove
        """
        async with db_session_context() as session:
            try:
                result = await session.execute(
                    select(SearchIndex).where(
                        SearchIndex.entry_id == uuid.UUID(entry_id)
                    )
                )
                search_index = result.scalar_one_or_none()
                
                if search_index:
                    await session.delete(search_index)
                    await session.commit()
                    
                    logger.info(
                        "Search index removed",
                        entry_id=entry_id
                    )
                
            except Exception as e:
                await session.rollback()
                raise IndexError(f"Failed to remove index: {str(e)}") from e
    
    def _extract_content(self, entry: KnowledgeEntry) -> str:
        """
        Extract searchable content from an entry.
        
        Args:
            entry: Knowledge entry
            
        Returns:
            str: Extracted content
        """
        # Combine title, content, and metadata for searching
        content_parts = []
        
        # Add title with higher weight
        if entry.title:
            content_parts.append(entry.title)
        
        # Add main content
        if entry.content:
            content_parts.append(entry.content)
        
        # Add author
        if entry.author:
            content_parts.append(entry.author)
        
        # Add metadata fields
        if entry.metadata_:
            metadata_text = []

            if entry.metadata_.get("description"):
                metadata_text.append(entry.metadata_["description"])

            if entry.metadata_.get("keywords"):
                metadata_text.extend(entry.metadata_["keywords"])

            if entry.metadata_.get("tags"):
                metadata_text.extend(entry.metadata_["tags"])
            
            content_parts.extend(metadata_text)
        
        # Combine all content
        full_content = " ".join(content_parts)
        
        # Clean and normalize content
        cleaned_content = self._clean_content(full_content)
        
        return cleaned_content
    
    def _extract_metadata(self, entry: KnowledgeEntry) -> Dict[str, Any]:
        """
        Extract metadata for indexing.
        
        Args:
            entry: Knowledge entry
            
        Returns:
            Dict[str, Any]: Extracted metadata
        """
        metadata = {
            "entry_id": str(entry.id),
            "title": entry.title,
            "entry_type": entry.entry_type.value,
            "knowledge_type": entry.knowledge_type.value,
            "language": entry.language,
            "access_level": entry.access_level,
            "status": entry.status.value,
            "author": entry.author,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            "content_length": len(entry.content) if entry.content else 0,
            "word_count": len(entry.content.split()) if entry.content else 0
        }
        
        # Add custom metadata
        if entry.metadata_:
            metadata.update({
                f"custom_{k}": v for k, v in entry.metadata_.items()
                if k not in ["description", "keywords", "tags"]
            })
        
        return metadata
    
    def _clean_content(self, content: str) -> str:
        """
        Clean and normalize content for indexing.
        
        Args:
            content: Raw content
            
        Returns:
            str: Cleaned content
        """
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Remove special characters except letters, numbers, and spaces
        content = re.sub(r'[^a-zA-Z0-9\s]', ' ', content)
        
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Convert to lowercase
        content = content.lower()
        
        # Trim whitespace
        content = content.strip()
        
        return content
    
    def _generate_search_vector(self, content: str) -> str:
        """
        Generate PostgreSQL tsvector content.
        
        Args:
            content: Content to vectorize
            
        Returns:
            str: Search vector content
        """
        # For now, return the content as-is
        # In real implementation, this would use PostgreSQL functions
        return content
    
    async def _generate_embedding(self, content: str) -> Optional[List[float]]:
        """
        Generate embedding for content using AI model.
        
        Args:
            content: Content to embed
            
        Returns:
            List[float]: Embedding vector or None if failed
        """
        try:
            # In real implementation, this would call an AI model API
            # For now, generate a mock embedding
            
            # Create a simple hash-based embedding
            hash_object = hashlib.sha256(content.encode('utf-8'))
            hash_hex = hash_object.hexdigest()
            
            # Convert to float values
            embedding = []
            for i in range(0, len(hash_hex), 2):
                byte_val = int(hash_hex[i:i+2], 16)
                embedding.append(byte_val / 255.0)
            
            # Pad to 384 dimensions (common for embeddings)
            while len(embedding) < 384:
                embedding.append(0.0)
            
            return embedding[:384]
            
        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                error=str(e)
            )
            return None
    
    async def reindex_all_entries(self) -> Dict[str, Any]:
        """
        Reindex all knowledge entries.
        
        Returns:
            Dict[str, Any]: Reindexing results
        """
        async with db_session_context() as session:
            # Get all entries
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            entries = result.scalars().all()
            
            results = {
                "total_entries": len(entries),
                "indexed": 0,
                "failed": 0,
                "errors": []
            }
            
            for entry in entries:
                try:
                    await self._create_full_index(entry)
                    results["indexed"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "entry_id": str(entry.id),
                        "title": entry.title,
                        "error": str(e)
                    })
            
            logger.info(
                "Reindexing completed",
                total=results["total_entries"],
                indexed=results["indexed"],
                failed=results["failed"]
            )
            
            return results
    
    async def optimize_search_index(self) -> Dict[str, Any]:
        """
        Optimize search index for better performance.
        
        Returns:
            Dict[str, Any]: Optimization results
        """
        async with db_session_context() as session:
            try:
                # Update PostgreSQL statistics
                await session.execute("ANALYZE search_index")
                
                # Rebuild search indexes if needed
                await session.execute(
                    "REINDEX INDEX IF EXISTS idx_search_content_vector"
                )
                
                await session.commit()
                
                results = {
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "operations": ["analyze", "reindex"]
                }
                
                logger.info("Search index optimization completed")
                
                return results
                
            except Exception as e:
                await session.rollback()
                raise IndexError(f"Index optimization failed: {str(e)}") from e
    
    async def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get search index statistics.
        
        Returns:
            Dict[str, Any]: Index statistics
        """
        async with db_session_context() as session:
            # Get total indexed entries
            result = await session.execute(
                select(func.count(SearchIndex.id))
            )
            total_indexed = result.scalar() or 0
            
            # Get entries with embeddings - embedding lives on KnowledgeEntry,
            # not SearchIndex
            result = await session.execute(
                select(func.count(KnowledgeEntry.id)).where(
                    KnowledgeEntry.embedding.is_not(None)
                )
            )
            with_embeddings = result.scalar() or 0

            # Get average content length
            result = await session.execute(
                select(func.avg(func.length(SearchIndex.indexed_content)))
            )
            avg_content_length = result.scalar() or 0
            
            # Get indexing queue size
            queue_size = self.indexing_queue.qsize()
            
            statistics = {
                "total_indexed": total_indexed,
                "with_embeddings": with_embeddings,
                "without_embeddings": total_indexed - with_embeddings,
                "embedding_coverage": (with_embeddings / total_indexed) if total_indexed > 0 else 0.0,
                "average_content_length": avg_content_length,
                "queue_size": queue_size,
                "indexing_active": self.indexing_active,
                "max_concurrent_indexing": self.max_concurrent_indexing,
                "embedding_model": self.embedding_model
            }
            
            return statistics
    
    async def rebuild_index_for_category(self, category_id: str) -> Dict[str, Any]:
        """
        Rebuild index for all entries in a category.
        
        Args:
            category_id: Category ID
            
        Returns:
            Dict[str, Any]: Rebuild results
        """
        async with db_session_context() as session:
            # Get entries in category
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.category_id == uuid.UUID(category_id),
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            entries = result.scalars().all()
            
            results = {
                "category_id": category_id,
                "total_entries": len(entries),
                "indexed": 0,
                "failed": 0
            }
            
            for entry in entries:
                try:
                    await self._update_full_index(entry)
                    results["indexed"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    logger.error(
                        "Failed to index category entry",
                        entry_id=str(entry.id),
                        category_id=category_id,
                        error=str(e)
                    )
            
            logger.info(
                "Category index rebuild completed",
                category_id=category_id,
                total=results["total_entries"],
                indexed=results["indexed"],
                failed=results["failed"]
            )
            
            return results
