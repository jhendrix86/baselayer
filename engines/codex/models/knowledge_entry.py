"""
CODEX Knowledge Entry Models

SQLAlchemy models for knowledge storage with pgvector embeddings
and semantic search capabilities.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    JSON, ForeignKey, Index, Float, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, VECTOR
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarativeBase()


class KnowledgeEntryType(str, Enum):
    """Knowledge entry types."""
    FACT = "fact"
    DECISION = "decision"
    PATTERN = "pattern"
    OUTCOME = "outcome"
    PREFERENCE = "preference"
    CONTEXT = "context"


class SourceEngine(str, Enum):
    """Source engines that create knowledge."""
    MINT = "mint"
    WIRE = "wire"
    PULSE = "pulse"
    GATE = "gate"
    HOOK = "hook"
    SYSTEM = "system"
    MANUAL = "manual"


class KnowledgeEntry(Base):
    """
    Knowledge entry model with semantic embeddings.
    
    Stores facts, decisions, patterns, and outcomes with
    pgvector embeddings for semantic search.
    """
    __tablename__ = "codex_knowledge_entries"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core fields
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    entry_type = Column(String(20), nullable=False, index=True)
    
    # Source tracking
    source_engine = Column(String(20), nullable=False, index=True)
    source_agent = Column(String(100), nullable=False)
    
    # Quality metrics
    confidence = Column(Float, nullable=False, default=0.0, index=True)
    tags = Column(ARRAY(String), default=list, index=True)
    
    # Semantic search
    embedding = Column(VECTOR(768), nullable=True, index=True)  # nomic-embed-text dimension
    
    # Usage tracking
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed_at = Column(DateTime(timezone=True))
    
    # Lifecycle
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    outgoing_links = relationship("KnowledgeLink", foreign_keys="KnowledgeLink.source_entry_id", back_populates="source_entry", cascade="all, delete-orphan")
    incoming_links = relationship("KnowledgeLink", foreign_keys="KnowledgeLink.target_entry_id", back_populates="target_entry", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_knowledge_key', 'key'),
        Index('idx_knowledge_entry_type', 'entry_type'),
        Index('idx_knowledge_source_engine', 'source_engine'),
        Index('idx_knowledge_confidence', 'confidence'),
        Index('idx_knowledge_tags', 'tags', postgresql_using='gin'),
        Index('idx_knowledge_embedding', 'embedding', postgresql_using='ivfflat'),
        Index('idx_knowledge_created_at', 'created_at'),
        Index('idx_knowledge_last_accessed', 'last_accessed_at'),
        Index('idx_knowledge_is_archived', 'is_archived'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeEntry(id={self.id}, key={self.key}, type={self.entry_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "key": self.key,
            "value": self.value,
            "entry_type": self.entry_type,
            "source_engine": self.source_engine,
            "source_agent": self.source_agent,
            "confidence": self.confidence,
            "tags": self.tags,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def days_since_creation(self) -> float:
        """Calculate days since creation."""
        if not self.created_at:
            return 0.0
        
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / (24 * 60 * 60)
    
    @property
    def days_since_last_access(self) -> float:
        """Calculate days since last access."""
        if not self.last_accessed_at:
            return self.days_since_creation
        
        delta = datetime.now(timezone.utc) - self.last_accessed_at
        return delta.total_seconds() / (24 * 60 * 60)
    
    @property
    def access_frequency(self) -> float:
        """Calculate access frequency (accesses per day)."""
        days = self.days_since_creation
        if days == 0:
            return float(self.access_count)
        return self.access_count / days
    
    def increment_access(self) -> None:
        """Increment access count and update last accessed timestamp."""
        self.access_count += 1
        self.last_accessed_at = datetime.now(timezone.utc)
    
    def add_tag(self, tag: str) -> None:
        """Add a tag if not already present."""
        if not self.tags:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag if present."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag: str) -> bool:
        """Check if entry has a specific tag."""
        return self.tags is not None and tag in self.tags
    
    def update_confidence(self, new_confidence: float) -> None:
        """Update confidence with validation."""
        if 0.0 <= new_confidence <= 1.0:
            self.confidence = new_confidence
        else:
            raise ValueError("Confidence must be between 0.0 and 1.0")
    
    def archive(self) -> None:
        """Archive the knowledge entry."""
        self.is_archived = True
    
    def unarchive(self) -> None:
        """Unarchive the knowledge entry."""
        self.is_archived = False
    
    def set_expiration(self, days: int) -> None:
        """Set expiration date from now."""
        if days > 0:
            self.expires_at = datetime.now(timezone.utc) + timezone.timedelta(days=days)
        else:
            self.expires_at = None
    
    def calculate_decay_score(self, base_decay_rate: float = 0.1) -> float:
        """Calculate decay score based on age and access patterns."""
        days_since_creation = self.days_since_creation
        days_since_access = self.days_since_last_access
        access_frequency = self.access_frequency
        
        # Base decay from age
        age_decay = 1.0 - (days_since_creation * base_decay_rate / 365.0)
        age_decay = max(0.0, age_decay)
        
        # Boost from recent access
        access_boost = 1.0 / (1.0 + days_since_access * 0.1)
        
        # Boost from access frequency
        frequency_boost = 1.0 / (1.0 + (1.0 / max(access_frequency, 0.1)))
        
        # Combined decay score
        decay_score = self.confidence * age_decay * access_boost * frequency_boost
        
        return min(1.0, decay_score)
    
    def should_decay(self, threshold: float = 0.3) -> bool:
        """Check if entry should be decayed based on threshold."""
        return self.calculate_decay_score() < threshold
    
    def should_prune(self, retention_days: int = 90) -> bool:
        """Check if entry should be pruned based on retention policy."""
        if not self.is_archived:
            return False
        
        days_since_creation = self.days_since_creation
        return days_since_creation > retention_days
    
    def get_related_tags(self, min_confidence: float = 0.5) -> List[str]:
        """Get related tags based on confidence and access patterns."""
        if not self.tags or self.confidence < min_confidence:
            return []
        
        # Return tags with higher confidence entries tend to use
        return [tag for tag in self.tags if tag not in ["system", "auto-generated"]]
    
    def get_search_weight(self) -> float:
        """Calculate search weight for ranking."""
        base_weight = self.confidence
        
        # Boost for recent access
        if self.days_since_last_access < 7:
            base_weight *= 1.2
        
        # Boost for high access frequency
        if self.access_frequency > 0.1:
            base_weight *= 1.1
        
        # Boost for recent creation
        if self.days_since_creation < 30:
            base_weight *= 1.1
        
        return min(1.0, base_weight)
    
    def validate_embedding(self) -> bool:
        """Validate embedding format and dimensions."""
        if self.embedding is None:
            return True
        
        # Check if it's a list/vector
        if not isinstance(self.embedding, list):
            return False
        
        # Check dimensions (should be 768 for nomic-embed-text)
        if len(self.embedding) != 768:
            return False
        
        # Check if all values are numbers
        for value in self.embedding:
            if not isinstance(value, (int, float)):
                return False
        
        return True
    
    def get_embedding_vector(self) -> Optional[List[float]]:
        """Get embedding as list of floats."""
        if not self.validate_embedding():
            return None
        
        return [float(x) for x in self.embedding]
    
    def get_summary(self) -> dict:
        """Get entry summary for analytics."""
        return {
            "id": str(self.id),
            "key": self.key,
            "entry_type": self.entry_type,
            "source_engine": self.source_engine,
            "confidence": self.confidence,
            "access_count": self.access_count,
            "days_since_creation": self.days_since_creation,
            "days_since_last_access": self.days_since_last_access,
            "access_frequency": self.access_frequency,
            "tag_count": len(self.tags) if self.tags else 0,
            "has_embedding": self.embedding is not None,
            "is_expired": self.is_expired,
            "is_archived": self.is_archived,
            "decay_score": self.calculate_decay_score()
        }
