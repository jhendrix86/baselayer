"""
CODEX Knowledge Manager

Core knowledge operations API for CRUD, search,
and knowledge graph management.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..models.knowledge_entry import KnowledgeEntry, KnowledgeEntryType, SourceEngine
from ..models.knowledge_link import KnowledgeLink, KnowledgeLinkType
from ..models.knowledge_snapshot import KnowledgeSnapshot
from ..vector.embedding_engine import EmbeddingEngine
from ..vector.vector_store import VectorStore
from ..vector.semantic_search import SemanticSearch

logger = get_logger(__name__)


class KnowledgeManager:
    """
    Core knowledge operations manager.
    
    Provides CRUD operations, semantic search, knowledge graph
    traversal, and maintenance functions for the knowledge base.
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        redis_client=None,
        embedding_model: str = "nomic-embed-text"
    ):
        """
        Initialize knowledge manager.
        
        Args:
            db_session: Async SQLAlchemy session
            redis_client: Redis client for caching
            embedding_model: Ollama embedding model
        """
        self.db = db_session
        self.redis_client = redis_client
        
        # Initialize vector components
        self.embedding_engine = EmbeddingEngine(
            redis_client=redis_client,
            model=embedding_model
        )
        self.vector_store = VectorStore(db_session)
        self.semantic_search = SemanticSearch(
            embedding_engine=self.embedding_engine,
            vector_store=self.vector_store
        )
        
        logger.info("KnowledgeManager initialized", 
                   embedding_model=embedding_model)
    
    async def store(
        self,
        key: str,
        value: str,
        entry_type: KnowledgeEntryType,
        source_engine: SourceEngine,
        source_agent: str,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        generate_embedding: bool = True
    ) -> KnowledgeEntry:
        """
        Store a new knowledge entry.
        
        Args:
            key: Unique key for the entry
            value: Knowledge content
            entry_type: Type of knowledge
            source_engine: Engine that created it
            source_agent: Agent that created it
            tags: Optional tags
            confidence: Confidence score (0.0-1.0)
            generate_embedding: Whether to generate embedding
            
        Returns:
            Created knowledge entry
        """
        try:
            # Check for existing entry
            existing = await self.retrieve_by_key(key)
            if existing:
                raise BaseLayerError(f"Knowledge entry with key '{key}' already exists")
            
            # Create new entry
            entry = KnowledgeEntry(
                key=key,
                value=value,
                entry_type=entry_type,
                source_engine=source_engine,
                source_agent=source_agent,
                tags=tags or [],
                confidence=confidence
            )
            
            self.db.add(entry)
            await self.db.flush()
            
            # Generate and store embedding
            if generate_embedding:
                embedding = await self.embedding_engine.generate_embedding(value)
                entry.embedding = embedding
                
                # Store in vector store
                await self.vector_store.store_embedding(entry.id, embedding)
            
            await self.db.commit()
            
            logger.info("Knowledge entry stored", 
                       key=key,
                       entry_type=entry_type,
                       source_engine=source_engine,
                       has_embedding=bool(entry.embedding))
            
            return entry
            
        except Exception as e:
            logger.error("Failed to store knowledge entry", 
                        key=key, 
                        error=str(e))
            await self.db.rollback()
            raise BaseLayerError(f"Failed to store knowledge entry: {e}")
    
    async def retrieve_by_key(self, key: str) -> Optional[KnowledgeEntry]:
        """
        Retrieve knowledge entry by key.
        
        Args:
            key: Entry key
            
        Returns:
            Knowledge entry or None
        """
        try:
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.key == key)
            result = await self.db.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if entry:
                # Increment access count
                entry.increment_access()
                await self.db.commit()
            
            return entry
            
        except Exception as e:
            logger.error("Failed to retrieve knowledge entry", 
                        key=key, 
                        error=str(e))
            return None
    
    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        min_confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        entry_types: Optional[List[KnowledgeEntryType]] = None,
        source_engines: Optional[List[SourceEngine]] = None,
        exclude_archived: bool = True,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search.
        
        Args:
            query: Search query
            limit: Maximum results
            min_confidence: Minimum confidence
            tags: Filter by tags
            entry_types: Filter by entry types
            source_engines: Filter by source engines
            exclude_archived: Exclude archived entries
            threshold: Similarity threshold
            
        Returns:
            List of search results
        """
        try:
            # Convert enums to strings for search
            entry_type_strs = [et.value for et in entry_types] if entry_types else None
            source_engine_strs = [se.value for se in source_engines] if source_engines else None
            
            results = await self.semantic_search.search(
                query=query,
                limit=limit,
                min_confidence=min_confidence,
                tags=tags,
                entry_types=entry_type_strs,
                source_engines=source_engine_strs,
                exclude_archived=exclude_archived,
                threshold=threshold
            )
            
            logger.info("Semantic search completed", 
                       query_length=len(query),
                       results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            return []
    
    async def search_keyword(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        entry_types: Optional[List[KnowledgeEntryType]] = None,
        limit: int = 10
    ) -> List[KnowledgeEntry]:
        """
        Perform keyword search.
        
        Args:
            query: Search query
            tags: Filter by tags
            entry_types: Filter by entry types
            limit: Maximum results
            
        Returns:
            List of matching entries
        """
        try:
            # Build search query
            search_query = select(KnowledgeEntry).where(
                or_(
                    KnowledgeEntry.key.ilike(f"%{query}%"),
                    KnowledgeEntry.value.ilike(f"%{query}%")
                )
            )
            
            # Apply filters
            if tags:
                search_query = search_query.where(KnowledgeEntry.tags.overlap(tags))
            
            if entry_types:
                search_query = search_query.where(
                    KnowledgeEntry.entry_type.in_([et.value for et in entry_types])
                )
            
            # Exclude archived
            search_query = search_query.where(KnowledgeEntry.is_archived == False)
            
            # Order and limit
            search_query = search_query.order_by(
                KnowledgeEntry.access_count.desc(),
                KnowledgeEntry.confidence.desc()
            ).limit(limit)
            
            result = await self.db.execute(search_query)
            entries = result.scalars().all()
            
            # Increment access counts
            for entry in entries:
                entry.increment_access()
            
            await self.db.commit()
            
            logger.info("Keyword search completed", 
                       query_length=len(query),
                       results_found=len(entries))
            
            return list(entries)
            
        except Exception as e:
            logger.error("Keyword search failed", error=str(e))
            return []
    
    async def update(
        self,
        key: str,
        value: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        regenerate_embedding: bool = False
    ) -> Optional[KnowledgeEntry]:
        """
        Update existing knowledge entry.
        
        Args:
            key: Entry key
            value: New value (optional)
            confidence: New confidence (optional)
            tags: New tags (optional)
            regenerate_embedding: Whether to regenerate embedding
            
        Returns:
            Updated entry or None
        """
        try:
            entry = await self.retrieve_by_key(key)
            if not entry:
                return None
            
            # Update fields
            if value is not None:
                entry.value = value
                if regenerate_embedding:
                    # Generate new embedding
                    embedding = await self.embedding_engine.generate_embedding(value)
                    entry.embedding = embedding
                    await self.vector_store.store_embedding(entry.id, embedding)
            
            if confidence is not None:
                entry.update_confidence(confidence)
            
            if tags is not None:
                entry.tags = tags
            
            await self.db.commit()
            
            logger.info("Knowledge entry updated", key=key)
            return entry
            
        except Exception as e:
            logger.error("Failed to update knowledge entry", 
                        key=key, 
                        error=str(e))
            await self.db.rollback()
            return None
    
    async def archive(self, key: str) -> bool:
        """
        Archive a knowledge entry (soft delete).
        
        Args:
            key: Entry key
            
        Returns:
            True if successful
        """
        try:
            entry = await self.retrieve_by_key(key)
            if not entry:
                return False
            
            entry.archive()
            await self.db.commit()
            
            logger.info("Knowledge entry archived", key=key)
            return True
            
        except Exception as e:
            logger.error("Failed to archive knowledge entry", 
                        key=key, 
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def link(
        self,
        source_key: str,
        target_key: str,
        link_type: KnowledgeLinkType,
        strength: float = 0.5,
        metadata: Optional[str] = None
    ) -> Optional[KnowledgeLink]:
        """
        Create a knowledge link between entries.
        
        Args:
            source_key: Source entry key
            target_key: Target entry key
            link_type: Type of relationship
            strength: Link strength (0.0-1.0)
            metadata: Optional metadata
            
        Returns:
            Created link or None
        """
        try:
            # Get entries
            source_entry = await self.retrieve_by_key(source_key)
            target_entry = await self.retrieve_by_key(target_key)
            
            if not source_entry or not target_entry:
                return None
            
            # Check for existing link
            existing_stmt = select(KnowledgeLink).where(
                and_(
                    KnowledgeLink.source_entry_id == source_entry.id,
                    KnowledgeLink.target_entry_id == target_entry.id,
                    KnowledgeLink.link_type == link_type
                )
            )
            existing_result = await self.db.execute(existing_stmt)
            existing_link = existing_result.scalar_one_or_none()
            
            if existing_link:
                # Update existing link
                existing_link.update_strength(strength)
                if metadata:
                    existing_link.metadata = metadata
                link = existing_link
            else:
                # Create new link
                link = KnowledgeLink(
                    source_entry_id=source_entry.id,
                    target_entry_id=target_entry.id,
                    link_type=link_type,
                    strength=strength,
                    metadata=metadata
                )
                self.db.add(link)
            
            await self.db.commit()
            
            logger.info("Knowledge link created", 
                       source_key=source_key,
                       target_key=target_key,
                       link_type=link_type)
            
            return link
            
        except Exception as e:
            logger.error("Failed to create knowledge link", 
                        source_key=source_key,
                        target_key=target_key,
                        error=str(e))
            await self.db.rollback()
            return None
    
    async def get_related(
        self,
        key: str,
        depth: int = 2,
        min_strength: float = 0.3,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get related knowledge entries via graph traversal.
        
        Args:
            key: Starting entry key
            depth: Maximum traversal depth
            min_strength: Minimum link strength
            max_results: Maximum results
            
        Returns:
            List of related entries with relationship info
        """
        try:
            # Get starting entry
            start_entry = await self.retrieve_by_key(key)
            if not start_entry:
                return []
            
            # Perform graph traversal
            visited = set()
            results = []
            current_depth = 0
            
            async def traverse(entry_id: uuid.UUID, current_depth: int, path: List[str]):
                if current_depth >= depth or len(results) >= max_results:
                    return
                
                if entry_id in visited:
                    return
                
                visited.add(entry_id)
                
                # Get outgoing links
                links_stmt = select(KnowledgeLink).where(
                    and_(
                        KnowledgeLink.source_entry_id == entry_id,
                        KnowledgeLink.strength >= min_strength
                    )
                ).options(selectinload(KnowledgeLink.target_entry))
                
                links_result = await self.db.execute(links_stmt)
                links = links_result.scalars().all()
                
                for link in links:
                    if link.target_entry and not link.target_entry.is_archived:
                        # Add to results
                        result = {
                            "entry": link.target_entry.to_dict(),
                            "relationship": link.get_directional_description(),
                            "strength": link.strength,
                            "link_type": link.link_type,
                            "depth": current_depth,
                            "path": path + [link.target_entry.key]
                        }
                        results.append(result)
                        
                        # Continue traversal
                        await traverse(
                            link.target_entry_id,
                            current_depth + 1,
                            path + [link.target_entry.key]
                        )
            
            await traverse(start_entry.id, 0, [key])
            
            # Sort by strength and depth
            results.sort(key=lambda x: (-x["strength"], x["depth"]))
            
            logger.info("Related knowledge retrieved", 
                       key=key,
                       depth=depth,
                       results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Failed to get related knowledge", 
                        key=key, 
                        error=str(e))
            return []
    
    async def get_context(
        self,
        query: str,
        max_tokens: int = 4000,
        min_confidence: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Build context for LLM from relevant knowledge.
        
        Args:
            query: Query for context
            max_tokens: Maximum tokens
            min_confidence: Minimum confidence
            tags: Filter by tags
            
        Returns:
            Formatted context string
        """
        try:
            context = await self.semantic_search.search_context(
                query=query,
                max_tokens=max_tokens,
                min_confidence=min_confidence,
                tags=tags
            )
            
            logger.info("Context built", 
                       query_length=len(query),
                       max_tokens=max_tokens,
                       context_length=len(context))
            
            return context
            
        except Exception as e:
            logger.error("Failed to build context", error=str(e))
            return "Error building knowledge context."
    
    async def decay(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Decay confidence of old, low-access entries.
        
        Args:
            dry_run: If True, don't actually decay
            
        Returns:
            Decay operation results
        """
        try:
            # Get candidates for decay
            decay_threshold = 0.3
            days_threshold = 30
            
            candidates_stmt = select(KnowledgeEntry).where(
                and_(
                    KnowledgeEntry.is_archived == False,
                    KnowledgeEntry.confidence > decay_threshold,
                    KnowledgeEntry.days_since_last_access > days_threshold
                )
            )
            
            result = await self.db.execute(candidates_stmt)
            candidates = result.scalars().all()
            
            decayed_entries = []
            for entry in candidates:
                decay_score = entry.calculate_decay_score()
                
                if entry.should_decay(decay_threshold):
                    old_confidence = entry.confidence
                    new_confidence = decay_score
                    
                    if not dry_run:
                        entry.update_confidence(new_confidence)
                    
                    decayed_entries.append({
                        "key": entry.key,
                        "old_confidence": old_confidence,
                        "new_confidence": new_confidence,
                        "decay_score": decay_score
                    })
            
            if not dry_run and decayed_entries:
                await self.db.commit()
            
            results = {
                "candidates_found": len(candidates),
                "entries_decayed": len(decayed_entries),
                "dry_run": dry_run,
                "decay_threshold": decay_threshold,
                "days_threshold": days_threshold,
                "decayed_entries": decayed_entries
            }
            
            logger.info("Knowledge decay completed", results=results)
            return results
            
        except Exception as e:
            logger.error("Knowledge decay failed", error=str(e))
            return {"error": str(e)}
    
    async def prune(self, retention_days: int = 90, dry_run: bool = False) -> Dict[str, Any]:
        """
        Permanently delete archived entries past retention period.
        
        Args:
            retention_days: Retention period in days
            dry_run: If True, don't actually delete
            
        Returns:
            Prune operation results
        """
        try:
            # Get candidates for pruning
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            candidates_stmt = select(KnowledgeEntry).where(
                and_(
                    KnowledgeEntry.is_archived == True,
                    KnowledgeEntry.created_at < cutoff_date
                )
            )
            
            result = await self.db.execute(candidates_stmt)
            candidates = result.scalars().all()
            
            pruned_entries = []
            for entry in candidates:
                # Delete embeddings first
                await self.vector_store.delete_embedding(entry.id)
                
                # Delete links
                links_stmt = select(KnowledgeLink).where(
                    or_(
                        KnowledgeLink.source_entry_id == entry.id,
                        KnowledgeLink.target_entry_id == entry.id
                    )
                )
                links_result = await self.db.execute(links_stmt)
                links = links_result.scalars().all()
                
                for link in links:
                    if not dry_run:
                        await self.db.delete(link)
                
                # Delete entry
                if not dry_run:
                    await self.db.delete(entry)
                
                pruned_entries.append({
                    "key": entry.key,
                    "entry_type": entry.entry_type,
                    "created_at": entry.created_at.isoformat(),
                    "days_old": entry.days_since_creation
                })
            
            if not dry_run and pruned_entries:
                await self.db.commit()
            
            results = {
                "candidates_found": len(candidates),
                "entries_pruned": len(pruned_entries),
                "dry_run": dry_run,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "pruned_entries": pruned_entries
            }
            
            logger.info("Knowledge pruning completed", results=results)
            return results
            
        except Exception as e:
            logger.error("Knowledge pruning failed", error=str(e))
            await self.db.rollback()
            return {"error": str(e)}
    
    async def snapshot(self) -> KnowledgeSnapshot:
        """
        Generate daily knowledge snapshot.
        
        Returns:
            Created snapshot
        """
        try:
            # Get current statistics
            total_stmt = select(func.count(KnowledgeEntry.id)).where(
                KnowledgeEntry.is_archived == False
            )
            total_result = await self.db.execute(total_stmt)
            total_entries = total_result.scalar()
            
            # Get distribution by type
            type_stmt = select(
                KnowledgeEntry.entry_type,
                func.count(KnowledgeEntry.id)
            ).where(
                KnowledgeEntry.is_archived == False
            ).group_by(KnowledgeEntry.entry_type)
            type_result = await self.db.execute(type_stmt)
            entries_by_type = {row.entry_type: row.count for row in type_result}
            
            # Get distribution by engine
            engine_stmt = select(
                KnowledgeEntry.source_engine,
                func.count(KnowledgeEntry.id)
            ).where(
                KnowledgeEntry.is_archived == False
            ).group_by(KnowledgeEntry.source_engine)
            engine_result = await self.db.execute(engine_stmt)
            entries_by_engine = {row.source_engine: row.count for row in engine_result}
            
            # Get confidence distribution
            confidence_ranges = {
                "0.0-0.1": 0, "0.1-0.2": 0, "0.2-0.3": 0,
                "0.3-0.4": 0, "0.4-0.5": 0, "0.5-0.6": 0,
                "0.6-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0
            }
            
            confidence_stmt = select(KnowledgeEntry.confidence).where(
                KnowledgeEntry.is_archived == False
            )
            confidence_result = await self.db.execute(confidence_stmt)
            
            total_confidence = 0.0
            for row in confidence_result.scalars():
                total_confidence += row.confidence
                
                # Categorize into ranges
                if row.confidence < 0.1:
                    confidence_ranges["0.0-0.1"] += 1
                elif row.confidence < 0.2:
                    confidence_ranges["0.1-0.2"] += 1
                elif row.confidence < 0.3:
                    confidence_ranges["0.2-0.3"] += 1
                elif row.confidence < 0.4:
                    confidence_ranges["0.3-0.4"] += 1
                elif row.confidence < 0.5:
                    confidence_ranges["0.4-0.5"] += 1
                elif row.confidence < 0.6:
                    confidence_ranges["0.5-0.6"] += 1
                elif row.confidence < 0.7:
                    confidence_ranges["0.6-0.7"] += 1
                elif row.confidence < 0.8:
                    confidence_ranges["0.7-0.8"] += 1
                elif row.confidence < 0.9:
                    confidence_ranges["0.8-0.9"] += 1
                else:
                    confidence_ranges["0.9-1.0"] += 1
            
            avg_confidence = total_confidence / total_entries if total_entries > 0 else 0.0
            
            # Get other metrics
            archived_stmt = select(func.count(KnowledgeEntry.id)).where(
                KnowledgeEntry.is_archived == True
            )
            archived_result = await self.db.execute(archived_stmt)
            archived_count = archived_result.scalar()
            
            # New entries today
            today = datetime.now(timezone.utc).date()
            new_today_stmt = select(func.count(KnowledgeEntry.id)).where(
                and_(
                    KnowledgeEntry.created_at >= today,
                    KnowledgeEntry.is_archived == False
                )
            )
            new_today_result = await self.db.execute(new_today_stmt)
            new_entries_today = new_today_result.scalar()
            
            # Entries with embeddings
            embedding_stmt = select(func.count(KnowledgeEntry.id)).where(
                and_(
                    KnowledgeEntry.embedding.isnot(None),
                    KnowledgeEntry.is_archived == False
                )
            )
            embedding_result = await self.db.execute(embedding_stmt)
            entries_with_embeddings = embedding_result.scalar()
            
            # Total links
            links_stmt = select(func.count(KnowledgeLink.id))
            links_result = await self.db.execute(links_stmt)
            total_links = links_result.scalar()
            
            # Create snapshot
            snapshot = KnowledgeSnapshot(
                snapshot_date=datetime.now(timezone.utc),
                total_entries=total_entries,
                entries_by_type=entries_by_type,
                entries_by_engine=entries_by_engine,
                entries_by_confidence=confidence_ranges,
                avg_confidence=avg_confidence,
                archived_count=archived_count,
                expired_count=0,  # TODO: Calculate expired entries
                new_entries_today=new_entries_today,
                entries_with_embeddings=entries_with_embeddings,
                total_links=total_links
            )
            
            self.db.add(snapshot)
            await self.db.commit()
            
            logger.info("Knowledge snapshot created", 
                       total_entries=total_entries,
                       avg_confidence=avg_confidence)
            
            return snapshot
            
        except Exception as e:
            logger.error("Failed to create knowledge snapshot", error=str(e))
            await self.db.rollback()
            raise BaseLayerError(f"Failed to create knowledge snapshot: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.
        
        Returns:
            Statistics dictionary
        """
        try:
            # Get basic counts
            total_stmt = select(func.count(KnowledgeEntry.id))
            total_result = await self.db.execute(total_stmt)
            total_entries = total_result.scalar()
            
            active_stmt = select(func.count(KnowledgeEntry.id)).where(
                KnowledgeEntry.is_archived == False
            )
            active_result = await self.db.execute(active_stmt)
            active_entries = active_result.scalar()
            
            archived_stmt = select(func.count(KnowledgeEntry.id)).where(
                KnowledgeEntry.is_archived == True
            )
            archived_result = await self.db.execute(archived_stmt)
            archived_entries = archived_result.scalar()
            
            # Get embedding stats
            embedding_stats = await self.vector_store.get_embedding_stats()
            
            # Get link stats
            links_stmt = select(func.count(KnowledgeLink.id))
            links_result = await self.db.execute(links_stmt)
            total_links = links_result.scalar()
            
            # Get latest snapshot
            latest_snapshot_stmt = select(KnowledgeSnapshot).order_by(
                KnowledgeSnapshot.snapshot_date.desc()
            ).limit(1)
            latest_result = await self.db.execute(latest_snapshot_stmt)
            latest_snapshot = latest_result.scalar_one_or_none()
            
            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "archived_entries": archived_entries,
                "total_links": total_links,
                "embedding_stats": embedding_stats,
                "latest_snapshot": latest_snapshot.get_summary() if latest_snapshot else None,
                "health_score": latest_snapshot.get_health_score() if latest_snapshot else 0.0
            }
            
        except Exception as e:
            logger.error("Failed to get knowledge stats", error=str(e))
            return {"error": str(e)}
