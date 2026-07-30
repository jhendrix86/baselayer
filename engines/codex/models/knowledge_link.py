"""
CODEX Knowledge Link Models

SQLAlchemy models for knowledge graph relationships
between knowledge entries.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Float,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarativeBase()


class KnowledgeLinkType(str, Enum):
    """Knowledge link relationship types."""
    RELATED = "related"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    EXAMPLE_OF = "example_of"
    CAUSES = "causes"
    CAUSED_BY = "caused_by"


class KnowledgeLink(Base):
    """
    Knowledge link model for graph relationships.
    
    Creates edges between knowledge entries to enable
    graph traversal and relationship discovery.
    """
    __tablename__ = "codex_knowledge_links"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    source_entry_id = Column(UUID(as_uuid=True), ForeignKey('codex_knowledge_entries.id'), nullable=False)
    target_entry_id = Column(UUID(as_uuid=True), ForeignKey('codex_knowledge_entries.id'), nullable=False)
    
    # Link properties
    link_type = Column(String(20), nullable=False)
    strength = Column(Float, nullable=False, default=0.5)
    
    # Metadata
    metadata = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    source_entry = relationship("KnowledgeEntry", foreign_keys=[source_entry_id], back_populates="outgoing_links")
    target_entry = relationship("KnowledgeEntry", foreign_keys=[target_entry_id], back_populates="incoming_links")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('source_entry_id', 'target_entry_id', 'link_type', name='uq_knowledge_link'),
        Index('idx_knowledge_link_source', 'source_entry_id'),
        Index('idx_knowledge_link_target', 'target_entry_id'),
        Index('idx_knowledge_link_type', 'link_type'),
        Index('idx_knowledge_link_strength', 'strength'),
        Index('idx_knowledge_link_created_at', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeLink(id={self.id}, type={self.link_type}, strength={self.strength})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "source_entry_id": str(self.source_entry_id),
            "target_entry_id": str(self.target_entry_id),
            "link_type": self.link_type,
            "strength": self.strength,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def is_symmetric(self) -> bool:
        """Check if link type is symmetric (bidirectional)."""
        symmetric_types = {
            KnowledgeLinkType.RELATED,
            KnowledgeLinkType.CONTRADICTS,
            KnowledgeLinkType.SUPPORTS
        }
        return self.link_type in symmetric_types
    
    @property
    def is_asymmetric(self) -> bool:
        """Check if link type is asymmetric (unidirectional)."""
        return not self.is_symmetric
    
    @property
    def inverse_type(self) -> Optional[str]:
        """Get the inverse link type for asymmetric relationships."""
        inverse_mapping = {
            KnowledgeLinkType.SUPERSEDES: KnowledgeLinkType.DERIVED_FROM,
            KnowledgeLinkType.DERIVED_FROM: KnowledgeLinkType.SUPERSEDES,
            KnowledgeLinkType.CAUSES: KnowledgeLinkType.CAUSED_BY,
            KnowledgeLinkType.CAUSED_BY: KnowledgeLinkType.CAUSES,
        }
        
        return inverse_mapping.get(self.link_type)
    
    def update_strength(self, new_strength: float) -> None:
        """Update link strength with validation."""
        if 0.0 <= new_strength <= 1.0:
            self.strength = new_strength
        else:
            raise ValueError("Strength must be between 0.0 and 1.0")
    
    def strengthen(self, amount: float = 0.1) -> None:
        """Increase link strength."""
        new_strength = min(1.0, self.strength + amount)
        self.update_strength(new_strength)
    
    def weaken(self, amount: float = 0.1) -> None:
        """Decrease link strength."""
        new_strength = max(0.0, self.strength - amount)
        self.update_strength(new_strength)
    
    def get_directional_description(self) -> str:
        """Get human-readable directional description."""
        if self.link_type == KnowledgeLinkType.RELATED:
            return "is related to"
        elif self.link_type == KnowledgeLinkType.SUPERSEDES:
            return "supersedes"
        elif self.link_type == KnowledgeLinkType.DERIVED_FROM:
            return "is derived from"
        elif self.link_type == KnowledgeLinkType.CONTRADICTS:
            return "contradicts"
        elif self.link_type == KnowledgeLinkType.SUPPORTS:
            return "supports"
        elif self.link_type == KnowledgeLinkType.EXAMPLE_OF:
            return "is an example of"
        elif self.link_type == KnowledgeLinkType.CAUSES:
            return "causes"
        elif self.link_type == KnowledgeLinkType.CAUSED_BY:
            return "is caused by"
        else:
            return "is linked to"
    
    def get_weight(self) -> float:
        """Get weighted link strength for graph algorithms."""
        # Different link types have different weights
        type_weights = {
            KnowledgeLinkType.SUPERSEDES: 1.0,
            KnowledgeLinkType.DERIVED_FROM: 0.8,
            KnowledgeLinkType.CAUSES: 0.9,
            KnowledgeLinkType.CAUSED_BY: 0.7,
            KnowledgeLinkType.CONTRADICTS: 0.6,
            KnowledgeLinkType.SUPPORTS: 0.8,
            KnowledgeLinkType.RELATED: 0.5,
            KnowledgeLinkType.EXAMPLE_OF: 0.4,
        }
        
        type_weight = type_weights.get(self.link_type, 0.5)
        return self.strength * type_weight
    
    def is_strong(self, threshold: float = 0.7) -> bool:
        """Check if link is strong based on threshold."""
        return self.strength >= threshold
    
    def is_weak(self, threshold: float = 0.3) -> bool:
        """Check if link is weak based on threshold."""
        return self.strength <= threshold
    
    def get_metadata_dict(self) -> dict:
        """Get metadata as dictionary."""
        if not self.metadata:
            return {}
        
        # Simple JSON parsing for metadata
        try:
            import json
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {"raw": self.metadata}
    
    def set_metadata(self, metadata_dict: dict) -> None:
        """Set metadata from dictionary."""
        import json
        self.metadata = json.dumps(metadata_dict)
    
    def add_metadata_field(self, key: str, value: str) -> None:
        """Add a field to metadata."""
        metadata = self.get_metadata_dict()
        metadata[key] = value
        self.set_metadata(metadata)
    
    def get_metadata_field(self, key: str, default: str = None) -> Optional[str]:
        """Get a field from metadata."""
        metadata = self.get_metadata_dict()
        return metadata.get(key, default)
    
    def get_age_days(self) -> float:
        """Get age of link in days."""
        if not self.created_at:
            return 0.0
        
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / (24 * 60 * 60)
    
    def is_recent(self, days: int = 30) -> bool:
        """Check if link is recent."""
        return self.get_age_days() <= days
    
    def get_summary(self) -> dict:
        """Get link summary for analytics."""
        return {
            "id": str(self.id),
            "link_type": self.link_type,
            "strength": self.strength,
            "weight": self.get_weight(),
            "is_symmetric": self.is_symmetric,
            "is_asymmetric": self.is_asymmetric,
            "age_days": self.get_age_days(),
            "is_recent": self.is_recent(),
            "has_metadata": self.metadata is not None
        }
