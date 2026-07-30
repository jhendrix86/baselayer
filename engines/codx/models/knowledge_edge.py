"""
CODX Knowledge Edge Models

SQLAlchemy models for knowledge relationships,
edges, and graph connections.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    JSON, ForeignKey, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class EdgeType(str, Enum):
    """Knowledge edge types."""
    IS_A = "is_a"
    IS_PART_OF = "is_part_of"
    RELATES_TO = "relates_to"
    DEPENDS_ON = "depends_on"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    CONTAINS = "contains"
    SIMILAR_TO = "similar_to"
    CONTRADICTS = "contradicts"
    EXAMPLE_OF = "example_of"
    DEFINES = "defines"
    IMPLEMENTS = "implements"
    REFERENCES = "references"
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    CAUSES = "causes"
    ENABLES = "enables"
    REQUIRES = "requires"
    EXCLUDES = "excludes"
    SYNONYM_OF = "synonym_of"
    ANTONYM_OF = "antonym_of"
    HYPERNYM_OF = "hypernym_of"
    HYPONYM_OF = "hyponym_of"
    MERONYM_OF = "meronym_of"
    HOLONYM_OF = "holonym_of"
    MEMBER_OF = "member_of"
    INSTANCE_OF = "instance_of"
    PROPERTY_OF = "property_of"
    VALUE_OF = "value_of"


class EdgeStatus(str, Enum):
    """Knowledge edge status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class KnowledgeEdge(Base):
    """
    Knowledge edge model for CODX engine.
    
    Represents relationships, connections, and dependencies
    between knowledge nodes in the graph.
    """
    __tablename__ = "codx_knowledge_edges"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Edge information
    edge_type = Column(String(50), nullable=False, default=EdgeType.RELATES_TO)
    status = Column(String(20), nullable=False, default=EdgeStatus.ACTIVE)
    
    # Source and target nodes
    source_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_nodes.id'), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_nodes.id'), nullable=False)
    
    # Edge properties
    weight = Column(Float, default=1.0)
    confidence = Column(Float, default=1.0)
    strength = Column(Float, default=1.0)
    bidirectional = Column(Boolean, default=False)
    
    # Temporal information
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    
    # Content and metadata
    label = Column(String(500))
    description = Column(Text)
    properties = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)
    
    # Context information
    context = Column(Text)
    evidence = Column(Text)
    source = Column(String(200))
    created_by = Column(String(200))
    
    # Usage statistics
    access_count = Column(Integer, default=0)
    update_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    source_node = relationship("KnowledgeNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node = relationship("KnowledgeNode", foreign_keys=[target_id], back_populates="incoming_edges")
    
    # Indexes
    __table_args__ = (
        Index('idx_edge_type', 'edge_type'),
        Index('idx_edge_status', 'status'),
        Index('idx_edge_source_id', 'source_id'),
        Index('idx_edge_target_id', 'target_id'),
        Index('idx_edge_created_at', 'created_at'),
        Index('idx_edge_weight', 'weight'),
        Index('idx_edge_confidence', 'confidence'),
        Index('idx_edge_bidirectional', 'bidirectional'),
        Index('idx_edge_source_target', 'source_id', 'target_id'),
        Index('idx_edge_properties', 'properties', postgresql_using='gin'),
        Index('idx_edge_metadata', 'metadata', postgresql_using='gin'),
        Index('idx_edge_context', 'context'),
        Index('idx_edge_source', 'source'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeEdge(id={self.id}, type={self.edge_type}, source={self.source_id}, target={self.target_id})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "edge_type": self.edge_type,
            "status": self.status,
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "weight": self.weight,
            "confidence": self.confidence,
            "strength": self.strength,
            "bidirectional": self.bidirectional,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "label": self.label,
            "description": self.description,
            "properties": self.properties or {},
            "metadata": self.metadata or {},
            "context": self.context,
            "evidence": self.evidence,
            "source": self.source,
            "created_by": self.created_by,
            "access_count": self.access_count,
            "update_count": self.update_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if edge is active."""
        return self.status == EdgeStatus.ACTIVE
    
    @property
    def is_bidirectional(self) -> bool:
        """Check if edge is bidirectional."""
        return self.bidirectional
    
    @property
    def is_temporal(self) -> bool:
        """Check if edge has temporal constraints."""
        return self.valid_from is not None or self.valid_to is not None
    
    @property
    def is_valid_now(self) -> bool:
        """Check if edge is currently valid."""
        if not self.is_temporal:
            return True
        
        now = datetime.now(timezone.utc)
        
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_to and now > self.valid_to:
            return False
        
        return True
    
    def update_access(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
    
    def increment_update_count(self) -> None:
        """Increment update count."""
        self.update_count += 1
    
    def archive(self) -> None:
        """Archive the edge."""
        self.status = EdgeStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
    
    def activate(self) -> None:
        """Activate the edge."""
        self.status = EdgeStatus.ACTIVE
    
    def deactivate(self) -> None:
        """Deactivate the edge."""
        self.status = EdgeStatus.INACTIVE
    
    def set_temporal_validity(self, valid_from: datetime, valid_to: datetime) -> None:
        """Set temporal validity."""
        self.valid_from = valid_from
        self.valid_to = valid_to
    
    def add_property(self, key: str, value: Any) -> None:
        """Add a property."""
        if not self.properties:
            self.properties = {}
        
        self.properties[key] = value
    
    def remove_property(self, key: str) -> None:
        """Remove a property."""
        if self.properties and key in self.properties:
            del self.properties[key]
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property value."""
        if self.properties:
            return self.properties.get(key, default)
        return default
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata."""
        if not self.metadata:
            self.metadata = {}
        
        self.metadata[key] = value
    
    def remove_metadata(self, key: str) -> None:
        """Remove metadata."""
        if self.metadata and key in self.metadata:
            del self.metadata[key]
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        if self.metadata:
            return self.metadata.get(key, default)
        return default
    
    def reverse_edge(self) -> dict:
        """Get reverse edge representation."""
        return {
            "source_id": str(self.target_id),
            "target_id": str(self.source_id),
            "edge_type": self.edge_type,
            "weight": self.weight,
            "confidence": self.confidence,
            "strength": self.strength,
            "bidirectional": self.bidirectional
        }
    
    def is_hierarchical(self) -> bool:
        """Check if edge represents hierarchical relationship."""
        hierarchical_types = {
            EdgeType.IS_PART_OF,
            EdgeType.DEPENDS_ON,
            EdgeType.PRECEDES,
            EdgeType.FOLLOWS,
            EdgeType.CONTAINS,
            EdgeType.HYPERNYM_OF,
            EdgeType.HYPONYM_OF,
            EdgeType.MERONYM_OF,
            EdgeType.HOLONYM_OF,
            EdgeType.MEMBER_OF,
            EdgeType.INSTANCE_OF,
            EdgeType.PROPERTY_OF
        }
        
        return self.edge_type in hierarchical_types
    
    def is_semantic(self) -> bool:
        """Check if edge represents semantic relationship."""
        semantic_types = {
            EdgeType.RELATES_TO,
            EdgeType.SIMILAR_TO,
            EdgeType.CONTRADICTS,
            EdgeType.SYNONYM_OF,
            EdgeType.ANTONYM_OF
        }
        
        return self.edge_type in semantic_types
    
    def is_functional(self) -> bool:
        """Check if edge represents functional relationship."""
        functional_types = {
            EdgeType.DEFINES,
            EdgeType.IMPLEMENTS,
            EdgeType.REFERENCES,
            EdgeType.SUPPORTS,
            EdgeType.OPPOSES,
            EdgeType.CAUSES,
            EdgeType.ENABLES,
            EdgeType.REQUIRES,
            EdgeType.EXCLUDES
        }
        
        return self.edge_type in functional_types
    
    def is_instance_relationship(self) -> bool:
        """Check if edge represents instance relationship."""
        instance_types = {
            EdgeType.EXAMPLE_OF,
            EdgeType.INSTANCE_OF
        }
        
        return self.edge_type in instance_types
    
    def validate_structure(self) -> List[str]:
        """Validate edge structure and return errors."""
        errors = []
        
        if not self.edge_type:
            errors.append("Edge type is required")
        
        if not self.source_id:
            errors.append("Source node ID is required")
        
        if not self.target_id:
            errors.append("Target node ID is required")
        
        if self.source_id == self.target_id and not self.bidirectional:
            errors.append("Self-loops must be bidirectional")
        
        if self.weight < 0:
            errors.append("Weight cannot be negative")
        
        if self.confidence < 0 or self.confidence > 1:
            errors.append("Confidence must be between 0 and 1")
        
        if self.strength < 0:
            errors.append("Strength cannot be negative")
        
        if self.is_temporal and self.valid_from and self.valid_to:
            if self.valid_from >= self.valid_to:
                errors.append("Valid from must be before valid to")
        
        return errors
    
    def to_graph_dict(self) -> dict:
        """Convert to graph representation."""
        return {
            "id": str(self.id),
            "source": str(self.source_id),
            "target": str(self.target_id),
            "type": self.edge_type,
            "label": self.label,
            "weight": self.weight,
            "confidence": self.confidence,
            "strength": self.strength,
            "bidirectional": self.bidirectional,
            "properties": self.properties or {},
            "metadata": self.metadata or {},
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_cypher_query(self) -> str:
        """Convert to Cypher query fragment."""
        direction = "-" if self.bidirectional else "->"
        return f"({self.source_id}) {direction} ({self.target_id})"
    
    def to_graphviz_edge(self) -> str:
        """Convert to GraphViz edge representation."""
        if self.bidirectional:
            return f'"{self.source_id}" -- "{self.target_id}" [label="{self.label or self.edge_type}"];'
        else:
            return f'"{self.source_id}" -> "{self.target_id}" [label="{self.label or self.edge_type}"];'
    
    def calculate_similarity_score(self, other_edge: 'KnowledgeEdge') -> float:
        """Calculate similarity score with another edge."""
        if self.edge_type != other_edge.edge_type:
            return 0.0
        
        # Simple similarity based on properties
        similarity = 0.0
        
        if self.properties and other_edge.properties:
            common_properties = set(self.properties.keys()) & set(other_edge.properties.keys())
            similarity += len(common_properties) * 0.3
        
        # Weight similarity
        weight_diff = abs(self.weight - other_edge.weight)
        weight_similarity = max(0, 1 - weight_diff / 10.0)
        similarity += weight_similarity * 0.4
        
        # Confidence similarity
        confidence_diff = abs(self.confidence - other_edge.confidence)
        confidence_similarity = max(0, 1 - confidence_diff)
        similarity += confidence_similarity * 0.3
        
        return min(1.0, similarity)
    
    def clone(self, new_source_id: uuid.UUID = None, new_target_id: uuid.UUID = None) -> 'KnowledgeEdge':
        """Create a clone of the edge."""
        return KnowledgeEdge(
            edge_type=self.edge_type,
            source_id=new_source_id or self.source_id,
            target_id=new_target_id or self.target_id,
            weight=self.weight,
            confidence=self.confidence,
            strength=self.strength,
            bidirectional=self.bidirectional,
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            label=self.label,
            description=self.description,
            properties=self.properties.copy() if self.properties else {},
            metadata=self.metadata.copy() if self.metadata else {},
            context=self.context,
            evidence=self.evidence,
            source=self.source,
            created_by=self.created_by
        )
    
    def merge_properties(self, other_properties: dict) -> None:
        """Merge properties from another edge."""
        if not self.properties:
            self.properties = {}
        
        for key, value in other_properties.items():
            if key not in self.properties:
                self.properties[key] = value
    
    def update_edge_strength(self, usage_count: int, feedback_score: float = None) -> None:
        """Update edge strength based on usage and feedback."""
        if feedback_score is not None:
            # Adjust strength based on feedback
            if feedback_score > 0.5:
                self.strength = min(2.0, self.strength * 1.1)
            else:
                self.strength = max(0.1, self.strength * 0.9)
        
        # Adjust based on usage frequency
        if usage_count > 10:
            self.strength = min(2.0, self.strength * 1.05)
        elif usage_count > 100:
            self.strength = min(2.0, self.strength * 1.1)
    
    def get_path_influence(self, path_length: int) -> float:
        """Calculate influence based on path length."""
        if path_length <= 0:
            return self.strength
        
        # Influence decreases with path length
        return self.strength / (2 ** (path_length - 1))
    
    def is_part_of_cycle(self, graph_context: dict) -> bool:
        """Check if edge is part of a cycle."""
        # This would need graph traversal logic
        # Simplified check for self-loops
        return self.source_id == self.target_id
    
    def get_edge_color(self) -> str:
        """Get color for visualization based on edge type."""
        color_mapping = {
            EdgeType.IS_A: "#FF6B6B",
            EdgeType.IS_PART_OF: "#4ECDC4",
            EdgeType.RELATES_TO: "#45B7D1",
            EdgeType.DEPENDS_ON: "#F7DC6F",
            EdgeType.PRECEDES: "#96CEB4",
            EdgeType.FOLLOWS: "#CE93D8",
            EdgeType.CONTAINS: "#FF9F40",
            EdgeType.SIMILAR_TO: "#9C27B0",
            EdgeType.CONTRADICTS: "#E74C3C",
            EdgeType.EXAMPLE_OF: "#3498DB",
            EdgeType.DEFINES: "#2ECC71",
            EdgeType.IMPLEMENTS: "#F39C12",
            EdgeType.REFERENCES: "#1ABC9C",
            EdgeType.SUPPORTS: "#8E44AD",
            EdgeType.OPPOSES: "#E91E63",
            EdgeType.CAUSES: "#F44336",
            EdgeType.ENABLES: "#27AE60",
            EdgeType.REQUIRES: "#F1C40F",
            EdgeType.EXCLUDES: "#9B59B6",
            EdgeType.SYNONYM_OF: "#34495E",
            EdgeType.ANTONYM_OF: "#E91E63",
            EdgeType.HYPERNYM_OF: "#9B59B6",
            EdgeType.HYPONYM_OF: "#3498DB",
            EdgeType.MERONYM_OF: "#F1C40F",
            EdgeType.HOLONYM_OF: "#E67E22",
            EdgeType.MEMBER_OF: "#9C27B0",
            EdgeType.INSTANCE_OF: "#2ECC71",
            EdgeType.PROPERTY_OF: "#F39C12",
            EdgeType.VALUE_OF: "#1ABC9C"
        }
        
        return color_mapping.get(self.edge_type, "#CCCCCC")
    
    def get_edge_style(self) -> str:
        """Get style for visualization based on edge properties."""
        style = "solid"
        
        if self.confidence < 0.5:
            style = "dashed"
        elif self.strength < 0.5:
            style = "dotted"
        
        return style
    
    def get_edge_width(self) -> int:
        """Get width for visualization based on edge weight."""
        return max(1, min(5, int(self.weight * 2)))
    
    def to_networkx_edge(self) -> tuple:
        """Convert to NetworkX edge tuple."""
        return (str(self.source_id), str(self.target_id), {
            "type": self.edge_type,
            "weight": self.weight,
            "confidence": self.confidence,
            "strength": self.strength,
            "label": self.label,
            "color": self.get_edge_color(),
            "style": self.get_edge_style(),
            "width": self.get_edge_width()
        })
