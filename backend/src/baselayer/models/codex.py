"""
BaseLayer Codex/Memory Models

Knowledge management, categorization, and search indexing
for the Codex/Memory subsystem.
"""

from datetime import datetime

import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, Numeric, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID, ARRAY, TSVECTOR

from .base import BaseModel, UUIDType


class KnowledgeType(str, Enum):
    """Knowledge entry types."""
    DOCUMENT = "document"
    NOTE = "note"
    PROCEDURE = "procedure"
    POLICY = "policy"
    TEMPLATE = "template"
    CODE = "code"


class EntryType(str, Enum):
    """
    Presentation/format classification of a knowledge entry.

    Distinct from KnowledgeType (which classifies the *nature* of the
    knowledge); this classifies the *shape* of the content, and is what
    the codex analyzer infers from title/content heuristics
    (see codex/analyzer.py `_suggest_entry_type`).
    """
    DOCUMENT = "document"
    CODE = "code"
    FAQ = "faq"
    TUTORIAL = "tutorial"
    ARTICLE = "article"


class KnowledgeStatus(str, Enum):
    """Knowledge entry status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class SearchIndexType(str, Enum):
    """Search index types."""
    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class KnowledgeEntry(BaseModel):
    """
    Knowledge entry model for Codex/Memory subsystem.
    
    Stores and manages knowledge documents with categorization,
    search indexing, and version control.
    """
    
    __tablename__ = "knowledge_entries"
    
    # Basic information
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Knowledge entry title"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Brief description of the knowledge entry"
    )
    
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full content of the knowledge entry"
    )
    
    # Type and status
    knowledge_type: Mapped[KnowledgeType] = mapped_column(
        ENUM(KnowledgeType, name="knowledge_type"),
        nullable=False,
        index=True,
        comment="Type of knowledge entry"
    )

    entry_type: Mapped[EntryType] = mapped_column(
        ENUM(EntryType, name="entry_type"),
        nullable=False,
        default=EntryType.DOCUMENT,
        index=True,
        comment="Presentation/format classification of the entry"
    )
    
    status: Mapped[KnowledgeStatus] = mapped_column(
        ENUM(KnowledgeStatus, name="knowledge_status"),
        nullable=False,
        default=KnowledgeStatus.DRAFT,
        index=True,
        comment="Current status of the knowledge entry"
    )
    
    # Categorization
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("knowledge_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to the knowledge category"
    )
    
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Tags for categorization and search"
    )
    
    # Metadata
    source: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Source of the knowledge (URL, file path, etc.)"
    )
    
    author: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Author of the knowledge content"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Language code (ISO 639-1)"
    )
    
    # Version control
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Version of the knowledge entry"
    )
    
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent entry for version control"
    )
    
    # Search and indexing
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector"
    )
    
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Numeric),
        nullable=True,
        comment="Vector embedding for semantic search"
    )
    
    embedding_model: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Model used for generating embeddings"
    )
    
    # Access control
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="public",
        comment="Access level (public, restricted, private)"
    )
    
    required_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Roles required for access"
    )
    
    # Governance and compliance
    governance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether governance approval is required"
    )
    
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of user who approved the entry"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when entry was approved"
    )
    
    # Review and maintenance
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when entry was last reviewed"
    )
    
    next_review_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when next review is due"
    )
    
    review_frequency_days: Mapped[int] = mapped_column(
        String(5),
        nullable=True,
        comment="Frequency of review in days"
    )
    
    # Usage metrics
    view_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the entry has been viewed"
    )
    
    search_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the entry appeared in search results"
    )
    
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when entry was last accessed"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="knowledge_entries",
        foreign_keys="KnowledgeEntry.created_by",
        lazy="select"
    )
    
    category = relationship(
        "KnowledgeCategory",
        back_populates="entries",
        lazy="select"
    )
    
    parent = relationship(
        "KnowledgeEntry",
        remote_side="KnowledgeEntry.id",
        back_populates="children",
        lazy="select"
    )
    
    children = relationship(
        "KnowledgeEntry",
        back_populates="parent",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("title", "deleted_at", name="uq_knowledge_title_deleted"),
        Index("idx_knowledge_type_status", "knowledge_type", "status"),
        Index("idx_knowledge_category", "category_id"),
        Index("idx_knowledge_tags", "tags", postgresql_using="gin"),
        Index("idx_knowledge_search", "search_vector", postgresql_using="gin"),
        Index("idx_knowledge_access", "access_level"),
        Index("idx_knowledge_created_at", "created_at"),
        {"comment": "Knowledge entries with search and categorization"}
    )
    
    def __repr__(self) -> str:
        """String representation of the knowledge entry."""
        return f"<KnowledgeEntry(title='{self.title}', type='{self.knowledge_type}', status='{self.status}')>"
    
    @property
    def is_published(self) -> bool:
        """Check if knowledge entry is published."""
        return self.status == KnowledgeStatus.PUBLISHED
    
    @property
    def is_accessible(self, user_roles: list[str] | None = None) -> bool:
        """
        Check if knowledge entry is accessible to user.
        
        Args:
            user_roles: List of user roles
            
        Returns:
            bool: True if accessible
        """
        if self.access_level == "public":
            return True
        
        if self.access_level == "private":
            return False
        
        if self.access_level == "restricted" and user_roles:
            return any(role in self.required_roles for role in user_roles)
        
        return False
    
    def publish(self, approved_by: uuid.UUID | None = None) -> None:
        """
        Publish the knowledge entry.
        
        Args:
            approved_by: ID of user approving the publication
        """
        self.status = KnowledgeStatus.PUBLISHED
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()
        self.increment_version()
    
    def archive(self) -> None:
        """Archive the knowledge entry."""
        self.status = KnowledgeStatus.ARCHIVED
        self.increment_version()
    
    def deprecate(self) -> None:
        """Deprecate the knowledge entry."""
        self.status = KnowledgeStatus.DEPRECATED
        self.increment_version()
    
    def update_content(
        self,
        title: str | None = None,
        content: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        updated_by: uuid.UUID | None = None
    ) -> None:
        """
        Update the knowledge entry content.
        
        Args:
            title: New title
            content: New content
            description: New description
            tags: New tags
            updated_by: ID of user making the update
        """
        if title:
            self.title = title
        if content:
            self.content = content
        if description:
            self.description = description
        if tags is not None:
            self.tags = tags
        
        if updated_by:
            self.updated_by = updated_by
        
        self.increment_version()
    
    def record_access(self) -> None:
        """Record that the entry was accessed."""
        self.view_count = str(int(self.view_count) + 1)
        self.last_accessed_at = datetime.utcnow()
    
    def record_search_hit(self) -> None:
        """Record that the entry appeared in search results."""
        self.search_count = str(int(self.search_count) + 1)
    
    def schedule_review(self, frequency_days: int) -> None:
        """
        Schedule the next review.
        
        Args:
            frequency_days: Review frequency in days
        """
        self.review_frequency_days = str(frequency_days)
        self.last_reviewed_at = datetime.utcnow()
        self.next_review_at = datetime.utcnow() + datetime.timedelta(days=frequency_days)


class KnowledgeCategory(BaseModel):
    """
    Knowledge category model.
    
    Organizes knowledge entries into hierarchical categories.
    """
    
    __tablename__ = "knowledge_categories"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Category name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Category description"
    )
    
    # Hierarchy
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("knowledge_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent category for hierarchy"
    )
    
    level: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="0",
        comment="Category level in hierarchy"
    )
    
    path: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
        comment="Full path in hierarchy"
    )
    
    # Configuration
    color: Mapped[str] = mapped_column(
        String(7),
        nullable=True,
        comment="Color code for the category"
    )
    
    icon: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon name for the category"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the category is active"
    )
    
    # Access control
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="public",
        comment="Access level for the category"
    )
    
    # Relationships
    entries = relationship(
        "KnowledgeEntry",
        back_populates="category",
        lazy="select"
    )
    
    parent = relationship(
        "KnowledgeCategory",
        remote_side="KnowledgeCategory.id",
        back_populates="children",
        lazy="select"
    )
    
    children = relationship(
        "KnowledgeCategory",
        back_populates="parent",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_category_parent", "parent_id"),
        Index("idx_category_level", "level"),
        Index("idx_category_path", "path"),
        {"comment": "Knowledge categories for hierarchical organization"}
    )
    
    def __repr__(self) -> str:
        """String representation of the category."""
        return f"<KnowledgeCategory(name='{self.name}', level={self.level})>"
    
    @property
    def has_children(self) -> bool:
        """Check if category has children."""
        return bool(self.children)
    
    @property
    def full_path(self) -> str:
        """Get the full path of the category."""
        if self.path:
            return self.path
        return self.name
    
    def add_child(self, child_category: "KnowledgeCategory") -> None:
        """
        Add a child category.
        
        Args:
            child_category: Child category to add
        """
        child_category.parent_id = self.id
        child_category.level = str(int(self.level) + 1)
        child_category.path = f"{self.path}/{child_category.name}" if self.path else child_category.name


class KnowledgeTag(BaseModel):
    """
    Knowledge tag model.
    
    Provides flexible tagging system for knowledge entries.
    """
    
    __tablename__ = "knowledge_tags"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Tag name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Tag description"
    )
    
    # Metadata
    color: Mapped[str] = mapped_column(
        String(7),
        nullable=True,
        comment="Color code for the tag"
    )
    
    usage_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the tag has been used"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the tag is active"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_tag_usage", "usage_count"),
        {"comment": "Knowledge tags for flexible categorization"}
    )
    
    def __repr__(self) -> str:
        """String representation of the tag."""
        return f"<KnowledgeTag(name='{self.name}', usage={self.usage_count})>"
    
    def increment_usage(self) -> None:
        """Increment the usage count."""
        self.usage_count = str(int(self.usage_count) + 1)
    
    def decrement_usage(self) -> None:
        """Decrement the usage count."""
        current_usage = int(self.usage_count)
        if current_usage > 0:
            self.usage_count = str(current_usage - 1)


class SearchIndex(BaseModel):
    """
    Search index model.
    
    Manages search indexing for knowledge entries.
    """
    
    __tablename__ = "search_indices"
    
    # References
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the knowledge entry"
    )
    
    # Index configuration
    index_type: Mapped[SearchIndexType] = mapped_column(
        ENUM(SearchIndexType, name="search_index_type"),
        nullable=False,
        index=True,
        comment="Type of search index"
    )
    
    # Index data
    indexed_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Content that was indexed"
    )
    
    token_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of tokens in the index"
    )
    
    # Index metadata
    index_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Version of the index"
    )
    
    indexed_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when the index was created"
    )
    
    last_updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when the index was last updated"
    )
    
    # Search metrics
    search_hits: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of search hits"
    )
    
    last_searched_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Timestamp when the entry was last searched"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("entry_id", "index_type", name="uq_search_entry_type"),
        Index("idx_search_type_updated", "index_type", "last_updated_at"),
        {"comment": "Search indices for knowledge entries"}
    )
    
    def __repr__(self) -> str:
        """String representation of the search index."""
        return f"<SearchIndex(type='{self.index_type}', tokens={self.token_count})>"
    
    def record_search_hit(self) -> None:
        """Record a search hit."""
        self.search_hits = str(int(self.search_hits) + 1)
        self.last_searched_at = datetime.utcnow()
    
    def update_index(self, content: str, version: str = "1.0.0") -> None:
        """
        Update the search index.
        
        Args:
            content: Content to index
            version: Index version
        """
        self.indexed_content = content
        self.index_version = version
        self.last_updated_at = datetime.utcnow()
        
        # Simple token count (could be enhanced with proper tokenization)
        self.token_count = str(len(content.split()))
