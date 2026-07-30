"""
BaseLayer Knowledge Engine

Core knowledge management with CRUD operations,
version control, and AI integration for the Codex/Memory subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.codex import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag, SearchIndex,
    KnowledgeType, KnowledgeStatus, EntryType
)
from ..models.user import User
from .exceptions import (
    CodexError,
    KnowledgeNotFoundError,
    ValidationError,
    StorageError
)

logger = get_logger(__name__)


class KnowledgeEngine:
    """
    Core knowledge management engine.
    
    Handles knowledge entry CRUD operations, version control,
    and basic knowledge management with AI integration.
    """
    
    def __init__(self):
        self.entry_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 300  # 5 minutes
        self.version_history_limit: int = 10
        self.ai_enabled: bool = True
    
    async def create_knowledge_entry(
        self,
        title: str,
        content: str,
        entry_type: EntryType,
        knowledge_type: KnowledgeType,
        category_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: str = "en",
        access_level: str = "public",
        metadata: Optional[Dict[str, Any]] = None,
        author: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> KnowledgeEntry:
        """
        Create a new knowledge entry.
        
        Args:
            title: Entry title
            content: Entry content
            entry_type: Type of entry
            knowledge_type: Knowledge type
            category_id: Category ID
            tags: List of tags
            language: Content language
            access_level: Access level
            metadata: Additional metadata
            author: Entry author
            created_by: User who created the entry
            
        Returns:
            KnowledgeEntry: Created knowledge entry
            
        Raises:
            ValidationError: If validation fails
            StorageError: If storage fails
        """
        # Validate entry data
        await self._validate_entry_data({
            "title": title,
            "content": content,
            "entry_type": entry_type,
            "knowledge_type": knowledge_type,
            "language": language,
            "access_level": access_level
        })
        
        # Check for duplicates
        duplicate = await self._check_duplicate_entry(title, content)
        if duplicate:
            raise ValidationError(f"Duplicate entry detected: {duplicate.title}")
        
        async with get_db_session() as session:
            try:
                # Create knowledge entry
                entry = KnowledgeEntry(
                    title=title,
                    content=content,
                    entry_type=entry_type,
                    knowledge_type=knowledge_type,
                    category_id=uuid.UUID(category_id) if category_id else None,
                    language=language,
                    access_level=access_level,
                    status=KnowledgeStatus.DRAFT,
                    version="1.0.0",
                    metadata=metadata or {},
                    author=author,
                    created_by=created_by
                )
                
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                
                # Add tags
                if tags:
                    await self._add_tags_to_entry(session, entry.id, tags)
                
                # Create search index
                await self._create_search_index(entry)
                
                # Cache entry
                self._cache_entry(entry)
                
                logger.info(
                    "Knowledge entry created",
                    entry_id=str(entry.id),
                    title=title,
                    entry_type=entry_type.value,
                    user_id=str(created_by) if created_by else None
                )
                
                return entry
                
            except Exception as e:
                await session.rollback()
                raise StorageError(f"Failed to create knowledge entry: {str(e)}") from e
    
    async def get_knowledge_entry(
        self,
        entry_id: str,
        include_content: bool = True
    ) -> Optional[KnowledgeEntry]:
        """
        Get a knowledge entry by ID.
        
        Args:
            entry_id: Entry ID
            include_content: Whether to include content
            
        Returns:
            KnowledgeEntry: Knowledge entry or None
        """
        # Check cache first
        cache_key = f"entry_{entry_id}"
        if cache_key in self.entry_cache:
            cached_entry = self.entry_cache[cache_key]
            cache_age = datetime.utcnow() - cached_entry["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                # Return cached entry (without content if not requested)
                if not include_content:
                    entry_data = cached_entry["entry"].copy()
                    entry_data["content"] = "[Content not requested]"
                    return entry_data
                return cached_entry["entry"]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.id == uuid.UUID(entry_id),
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            entry = result.scalar_one_or_none()
            
            if entry:
                # Load tags and category
                await self._load_entry_relations(session, entry)
                
                # Cache entry
                self._cache_entry(entry)
                
                return entry
            
            return None
    
    async def update_knowledge_entry(
        self,
        entry_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[uuid.UUID] = None,
        create_version: bool = True
    ) -> KnowledgeEntry:
        """
        Update a knowledge entry.
        
        Args:
            entry_id: Entry ID
            updates: Fields to update
            updated_by: User who updated the entry
            create_version: Whether to create a new version
            
        Returns:
            KnowledgeEntry: Updated knowledge entry
            
        Raises:
            KnowledgeNotFoundError: If entry not found
            ValidationError: If validation fails
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.id == uuid.UUID(entry_id),
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            entry = result.scalar_one_or_none()
            
            if not entry:
                raise KnowledgeNotFoundError(f"Knowledge entry not found: {entry_id}")
            
            # Store old version if needed
            if create_version:
                await self._create_version_copy(session, entry)
            
            # Update fields
            if "title" in updates:
                entry.title = updates["title"]
            
            if "content" in updates:
                entry.content = updates["content"]
            
            if "entry_type" in updates:
                entry.entry_type = EntryType(updates["entry_type"])
            
            if "knowledge_type" in updates:
                entry.knowledge_type = KnowledgeType(updates["knowledge_type"])
            
            if "category_id" in updates:
                entry.category_id = uuid.UUID(updates["category_id"]) if updates["category_id"] else None
            
            if "language" in updates:
                entry.language = updates["language"]
            
            if "access_level" in updates:
                entry.access_level = updates["access_level"]
            
            if "status" in updates:
                entry.status = KnowledgeStatus(updates["status"])
            
            if "metadata" in updates:
                entry.metadata = updates["metadata"]
            
            if "author" in updates:
                entry.author = updates["author"]
            
            entry.updated_by = updated_by
            entry.increment_version()
            
            # Update tags if provided
            if "tags" in updates:
                await self._update_entry_tags(session, entry.id, updates["tags"])
            
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            
            # Update search index
            await self._update_search_index(entry)
            
            # Update cache
            self._cache_entry(entry)
            
            logger.info(
                "Knowledge entry updated",
                entry_id=entry_id,
                user_id=str(updated_by) if updated_by else None,
                version=entry.version
            )
            
            return entry
    
    async def delete_knowledge_entry(
        self,
        entry_id: str,
        deleted_by: Optional[uuid.UUID] = None,
        permanent: bool = False
    ) -> bool:
        """
        Delete a knowledge entry.
        
        Args:
            entry_id: Entry ID
            deleted_by: User who deleted the entry
            permanent: Whether to permanently delete
            
        Returns:
            bool: True if deleted successfully
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.id == uuid.UUID(entry_id),
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            entry = result.scalar_one_or_none()
            
            if not entry:
                return False
            
            if permanent:
                # Hard delete
                await session.delete(entry)
            else:
                # Soft delete
                entry.soft_delete(deleted_by)
                session.add(entry)
            
            await session.commit()
            
            # Remove from cache
            cache_key = f"entry_{entry_id}"
            self.entry_cache.pop(cache_key, None)
            
            # Remove from search index
            await self._remove_from_search_index(entry_id)
            
            logger.info(
                "Knowledge entry deleted",
                entry_id=entry_id,
                permanent=permanent,
                user_id=str(deleted_by) if deleted_by else None
            )
            
            return True
    
    async def list_knowledge_entries(
        self,
        status: Optional[KnowledgeStatus] = None,
        entry_type: Optional[EntryType] = None,
        knowledge_type: Optional[KnowledgeType] = None,
        category_id: Optional[str] = None,
        language: Optional[str] = None,
        access_level: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[KnowledgeEntry]:
        """
        List knowledge entries with optional filtering.
        
        Args:
            status: Filter by status
            entry_type: Filter by entry type
            knowledge_type: Filter by knowledge type
            category_id: Filter by category
            language: Filter by language
            access_level: Filter by access level
            author: Filter by author
            limit: Maximum number of results
            offset: Pagination offset
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            List[KnowledgeEntry]: List of knowledge entries
        """
        async with get_db_session() as session:
            query = select(KnowledgeEntry).where(KnowledgeEntry.deleted_at.is_(None))
            
            # Apply filters
            if status:
                query = query.where(KnowledgeEntry.status == status)
            
            if entry_type:
                query = query.where(KnowledgeEntry.entry_type == entry_type)
            
            if knowledge_type:
                query = query.where(KnowledgeEntry.knowledge_type == knowledge_type)
            
            if category_id:
                query = query.where(KnowledgeEntry.category_id == uuid.UUID(category_id))
            
            if language:
                query = query.where(KnowledgeEntry.language == language)
            
            if access_level:
                query = query.where(KnowledgeEntry.access_level == access_level)
            
            if author:
                query = query.where(KnowledgeEntry.author.ilike(f"%{author}%"))
            
            # Apply sorting
            sort_column = getattr(KnowledgeEntry, sort_by, KnowledgeEntry.created_at)
            if sort_order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            entries = result.scalars().all()
            
            # Load relations for each entry
            for entry in entries:
                await self._load_entry_relations(session, entry)
            
            return list(entries)
    
    async def search_knowledge_entries(
        self,
        query: str,
        search_type: str = "full_text",
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge entries.
        
        Args:
            query: Search query
            search_type: Type of search (full_text, semantic, hybrid)
            limit: Maximum number of results
            offset: Pagination offset
            filters: Additional filters
            
        Returns:
            List[Dict[str, Any]]: Search results
        """
        from .search import SearchEngine
        
        search_engine = SearchEngine()
        
        try:
            results = await search_engine.search(
                query=query,
                search_type=search_type,
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Knowledge search failed",
                query=query,
                search_type=search_type,
                error=str(e)
            )
            raise CodexError(f"Search failed: {str(e)}", search_query=query) from e
    
    async def get_entry_versions(
        self,
        entry_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a knowledge entry.
        
        Args:
            entry_id: Entry ID
            limit: Maximum number of versions
            
        Returns:
            List[Dict[str, Any]]: Version history
        """
        # In real implementation, this would query a version history table
        # For now, return current version info
        entry = await self.get_knowledge_entry(entry_id)
        
        if not entry:
            return []
        
        return [{
            "version": entry.version,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            "updated_by": str(entry.updated_by) if entry.updated_by else None,
            "title": entry.title,
            "content_length": len(entry.content),
            "metadata": entry.metadata
        }]
    
    async def get_entry_statistics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get knowledge entry statistics.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Statistics
        """
        async with get_db_session() as session:
            # Base query
            query = select(KnowledgeEntry).where(KnowledgeEntry.deleted_at.is_(None))
            
            # Apply period filter
            if period_start:
                query = query.where(KnowledgeEntry.created_at >= period_start)
            
            if period_end:
                query = query.where(KnowledgeEntry.created_at <= period_end)
            
            # Get total count
            result = await session.execute(
                select(func.count(KnowledgeEntry.id)).where(
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            total_entries = result.scalar() or 0
            
            # Get counts by status
            result = await session.execute(
                select(
                    KnowledgeEntry.status,
                    func.count(KnowledgeEntry.id)
                ).where(
                    KnowledgeEntry.deleted_at.is_(None)
                ).group_by(KnowledgeEntry.status)
            )
            status_counts = dict(result.all())
            
            # Get counts by type
            result = await session.execute(
                select(
                    KnowledgeEntry.knowledge_type,
                    func.count(KnowledgeEntry.id)
                ).where(
                    KnowledgeEntry.deleted_at.is_(None)
                ).group_by(KnowledgeEntry.knowledge_type)
            )
            type_counts = dict(result.all())
            
            # Get counts by language
            result = await session.execute(
                select(
                    KnowledgeEntry.language,
                    func.count(KnowledgeEntry.id)
                ).where(
                    KnowledgeEntry.deleted_at.is_(None)
                ).group_by(KnowledgeEntry.language)
            )
            language_counts = dict(result.all())
            
            statistics = {
                "total_entries": total_entries,
                "by_status": status_counts,
                "by_type": type_counts,
                "by_language": language_counts,
                "period": {
                    "start": period_start.isoformat() if period_start else None,
                    "end": period_end.isoformat() if period_end else None
                }
            }
            
            return statistics
    
    async def _validate_entry_data(self, entry_data: Dict[str, Any]) -> None:
        """
        Validate knowledge entry data.
        
        Args:
            entry_data: Entry data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        errors = []
        
        # Required fields
        if not entry_data.get("title") or len(entry_data["title"].strip()) < 3:
            errors.append("Title must be at least 3 characters long")
        
        if not entry_data.get("content") or len(entry_data["content"].strip()) < 10:
            errors.append("Content must be at least 10 characters long")
        
        # Language validation
        language = entry_data.get("language", "en")
        if not self._is_valid_language(language):
            errors.append(f"Invalid language: {language}")
        
        # Access level validation
        access_level = entry_data.get("access_level", "public")
        valid_levels = ["public", "restricted", "private"]
        if access_level not in valid_levels:
            errors.append(f"Invalid access level: {access_level}")
        
        # Content length check
        content = entry_data.get("content", "")
        if len(content) > 1000000:  # 1MB limit
            errors.append("Content too large (max 1MB)")
        
        if errors:
            raise ValidationError(
                f"Entry validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    async def _check_duplicate_entry(
        self,
        title: str,
        content: str
    ) -> Optional[KnowledgeEntry]:
        """
        Check for duplicate entries.
        
        Args:
            title: Entry title
            content: Entry content
            
        Returns:
            KnowledgeEntry: Duplicate entry or None
        """
        async with get_db_session() as session:
            # Check for exact title match
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.title == title,
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            duplicate = result.scalar_one_or_none()
            
            if duplicate:
                return duplicate
            
            # Check for content similarity (simplified)
            content_hash = hash(content.strip().lower())
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.deleted_at.is_(None)
                )
            )
            
            for entry in result.scalars():
                if hash(entry.content.strip().lower()) == content_hash:
                    return entry
            
            return None
    
    async def _add_tags_to_entry(
        self,
        session: AsyncSession,
        entry_id: uuid.UUID,
        tags: List[str]
    ) -> None:
        """Add tags to a knowledge entry."""
        for tag_name in tags:
            # Get or create tag
            result = await session.execute(
                select(KnowledgeTag).where(
                    KnowledgeTag.name == tag_name,
                    KnowledgeTag.deleted_at.is_(None)
                )
            )
            tag = result.scalar_one_or_none()
            
            if not tag:
                tag = KnowledgeTag(
                    name=tag_name,
                    description=f"Tag: {tag_name}",
                    color=self._generate_tag_color(tag_name)
                )
                session.add(tag)
                await session.flush()
            
            # Create entry-tag relationship
            # In real implementation, this would be a separate association table
            if not hasattr(entry, 'tags'):
                entry.tags = []
            entry.tags.append(tag)
    
    async def _update_entry_tags(
        self,
        session: AsyncSession,
        entry_id: uuid.UUID,
        tags: List[str]
    ) -> None:
        """Update tags for a knowledge entry."""
        # Remove existing tags
        # In real implementation, this would clear the association table
        
        # Add new tags
        await self._add_tags_to_entry(session, entry_id, tags)
    
    async def _create_search_index(self, entry: KnowledgeEntry) -> None:
        """Create search index for entry."""
        from .indexer import KnowledgeIndexer
        
        indexer = KnowledgeIndexer()
        
        try:
            await indexer.index_entry(entry)
        except Exception as e:
            logger.error(
                "Failed to create search index",
                entry_id=str(entry.id),
                error=str(e)
            )
    
    async def _update_search_index(self, entry: KnowledgeEntry) -> None:
        """Update search index for entry."""
        from .indexer import KnowledgeIndexer
        
        indexer = KnowledgeIndexer()
        
        try:
            await indexer.update_index(entry)
        except Exception as e:
            logger.error(
                "Failed to update search index",
                entry_id=str(entry.id),
                error=str(e)
            )
    
    async def _remove_from_search_index(self, entry_id: str) -> None:
        """Remove entry from search index."""
        from .indexer import KnowledgeIndexer
        
        indexer = KnowledgeIndexer()
        
        try:
            await indexer.remove_from_index(entry_id)
        except Exception as e:
            logger.error(
                "Failed to remove from search index",
                entry_id=entry_id,
                error=str(e)
            )
    
    async def _load_entry_relations(
        self,
        session: AsyncSession,
        entry: KnowledgeEntry
    ) -> None:
        """Load related data for entry."""
        # Load tags
        result = await session.execute(
            select(KnowledgeTag).join(
                # In real implementation, this would join through association table
                KnowledgeEntry.tags
            ).where(
                KnowledgeTag.deleted_at.is_(None)
            )
        )
        entry.tags = result.scalars().all()
        
        # Load category
        if entry.category_id:
            result = await session.execute(
                select(KnowledgeCategory).where(
                    KnowledgeCategory.id == entry.category_id,
                    KnowledgeCategory.deleted_at.is_(None)
                )
            )
            entry.category = result.scalar_one_or_none()
    
    async def _create_version_copy(
        self,
        session: AsyncSession,
        entry: KnowledgeEntry
    ) -> None:
        """Create a version copy of the entry."""
        # In real implementation, this would create a record in a version history table
        # For now, just log the version change
        logger.info(
            "Version copy created",
            entry_id=str(entry.id),
            version=entry.version
        )
    
    def _cache_entry(self, entry: KnowledgeEntry) -> None:
        """Cache a knowledge entry."""
        cache_key = f"entry_{str(entry.id)}"
        self.entry_cache[cache_key] = {
            "entry": entry,
            "cached_at": datetime.utcnow()
        }
    
    def _is_valid_language(self, language: str) -> bool:
        """Check if language code is valid."""
        valid_languages = {"en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko", "ar"}
        return language.lower() in valid_languages
    
    def _generate_tag_color(self, tag_name: str) -> str:
        """Generate a color for a tag based on its name."""
        colors = [
            "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
            "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16"
        ]
        
        # Simple hash-based color selection
        hash_value = hash(tag_name) % len(colors)
        return colors[hash_value]
