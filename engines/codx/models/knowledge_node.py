"""
CODX Knowledge Node Models

SQLAlchemy models for knowledge nodes, entities,
and metadata in the knowledge graph.
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


class NodeType(str, Enum):
    """Knowledge node types."""
    CONCEPT = "concept"
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    ATTRIBUTE = "attribute"
    DOCUMENT = "document"
    QUESTION = "question"
    ANSWER = "answer"
    PROCEDURE = "procedure"
    RULE = "rule"
    METADATA = "metadata"


class NodeStatus(str, Enum):
    """Knowledge node status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class KnowledgeNode(Base):
    """
    Knowledge node model for CODX engine.
    
    Represents entities, concepts, and relationships
    in the knowledge graph with metadata and embeddings.
    """
    __tablename__ = "codx_knowledge_nodes"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    title = Column(String(500), nullable=False)
    description = Column(Text)
    content = Column(Text)
    node_type = Column(String(50), nullable=False, default=NodeType.CONCEPT)
    status = Column(String(20), nullable=False, default=NodeStatus.ACTIVE)
    
    # Content and metadata
    summary = Column(Text)
    keywords = Column(ARRAY(String), default=list)
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    
    # Embedding information
    embedding_id = Column(UUID(as_uuid=True), ForeignKey('codx_vector_embeddings.id'))
    embedding_vector = Column(ARRAY(Float))  # For direct storage
    embedding_model = Column(String(50), default="text-embedding-ada-002")
    embedding_dimension = Column(Integer, default=1536)
    
    # Graph information
    parent_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_nodes.id'))
    root_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_nodes.id'))
    level = Column(Integer, default=0)
    path = Column(String(1000))  # Path from root
    
    # Quality and confidence
    confidence_score = Column(Float, default=1.0)
    quality_score = Column(Float, default=1.0)
    relevance_score = Column(Float, default=1.0)
    
    # Source and provenance
    source = Column(String(200))  # Source system or document
    source_url = Column(String(500))
    author = Column(String(200))
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
    embedding = relationship("VectorEmbedding", back_populates="nodes")
    children = relationship("KnowledgeNode", back_populates="parent", remote_side=[id])
    parent = relationship("KnowledgeNode", back_populates="children", remote_side=[id])
    root_node = relationship("KnowledgeNode", foreign_keys=[root_id])
    outgoing_edges = relationship("KnowledgeEdge", foreign_keys="source_id", back_populates="source_node")
    incoming_edges = relationship("KnowledgeEdge", foreign_keys="target_id", back_populates="target_node")
    
    # Indexes
    __table_args__ = (
        Index('idx_node_type', 'node_type'),
        Index('idx_node_status', 'status'),
        Index('idx_node_created_at', 'created_at'),
        Index('idx_node_embedding_id', 'embedding_id'),
        Index('idx_node_parent_id', 'parent_id'),
        Index('idx_node_root_id', 'root_id'),
        Index('idx_node_level', 'level'),
        Index('idx_node_source', 'source'),
        Index('idx_node_keywords', 'keywords', postgresql_using='gin'),
        Index('idx_node_tags', 'tags', postgresql_using='gin'),
        Index('idx_node_confidence', 'confidence_score'),
        Index('idx_node_quality', 'quality_score'),
        Index('idx_node_relevance', 'relevance_score'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeNode(id={self.id}, title={self.title}, type={self.node_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "node_type": self.node_type,
            "status": self.status,
            "summary": self.summary,
            "keywords": self.keywords or [],
            "tags": self.tags or {},
            "metadata": self.metadata or {},
            "embedding_id": str(self.embedding_id) if self.embedding_id else None,
            "embedding_vector": self.embedding_vector,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "root_id": str(self.root_id) if self.root_id else None,
            "level": self.level,
            "path": self.path,
            "confidence_score": self.confidence_score,
            "quality_score": self.quality_score,
            "relevance_score": self.relevance_score,
            "source": self.source,
            "source_url": self.source_url,
            "author": self.author,
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
        """Check if node is active."""
        return self.status == NodeStatus.ACTIVE
    
    @property
    def is_leaf(self) -> bool:
        """Check if node is a leaf node."""
        return len(self.children) == 0
    
    @property
    def is_root(self) -> bool:
        """Check if node is a root node."""
        return self.parent_id is None
    
    @property
    def depth(self) -> int:
        """Get node depth from root."""
        return self.level
    
    def add_child(self, child_node) -> None:
        """Add a child node."""
        if child_node not in self.children:
            child_node.parent_id = self.id
            child_node.level = self.level + 1
            child_node.path = f"{self.path}/{child_node.id}" if self.path else str(child_node.id)
    
    def remove_child(self, child_node) -> None:
        """Remove a child node."""
        if child_node in self.children:
            child_node.parent_id = None
            child_node.level = 0
            child_node.path = None
    
    def update_access(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
    
    def increment_update_count(self) -> None:
        """Increment update count."""
        self.update_count += 1
    
    def archive(self) -> None:
        """Archive the node."""
        self.status = NodeStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
    
    def activate(self) -> None:
        """Activate the node."""
        self.status = NodeStatus.ACTIVE
    
    def deactivate(self) -> None:
        """Deactivate the node."""
        self.status = NodeStatus.INACTIVE
    
    def update_quality_score(self, score: float) -> None:
        """Update quality score."""
        self.quality_score = max(0.0, min(1.0, score))
    
    def update_confidence_score(self, score: float) -> None:
        """Update confidence score."""
        self.confidence_score = max(0.0, min(1.0, score))
    
    def update_relevance_score(self, score: float) -> None:
        """Update relevance score."""
        self.relevance_score = max(0.0, min(1.0, score))
    
    def add_keyword(self, keyword: str) -> None:
        """Add a keyword."""
        if not self.keywords:
            self.keywords = []
        
        if keyword not in self.keywords:
            self.keywords.append(keyword)
    
    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword."""
        if self.keywords and keyword in self.keywords:
            self.keywords.remove(keyword)
    
    def add_tag(self, key: str, value: Any) -> None:
        """Add a tag."""
        if not self.tags:
            self.tags = {}
        
        self.tags[key] = value
    
    def remove_tag(self, key: str) -> None:
        """Remove a tag."""
        if self.tags and key in self.tags:
            del self.tags[key]
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        if self.metadata:
            return self.metadata.get(key, default)
        return default
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        if not self.metadata:
            self.metadata = {}
        
        self.metadata[key] = value
    
    def get_all_children(self) -> List['KnowledgeNode']:
        """Get all descendant nodes."""
        all_children = []
        
        for child in self.children:
            all_children.append(child)
            all_children.extend(child.get_all_children())
        
        return all_children
    
    def get_path_to_root(self) -> List[str]:
        """Get path from this node to root."""
        if self.is_root:
            return [str(self.id)]
        
        if self.parent:
            parent_path = self.parent.get_path_to_root()
            return parent_path + [str(self.id)]
        
        return [str(self.id)]
    
    def calculate_depth(self) -> int:
        """Calculate depth from root."""
        if self.is_root:
            return 0
        
        return self.parent.calculate_depth() + 1
    
    def get_subtree_size(self) -> int:
        """Get size of subtree including this node."""
        size = 1
        for child in self.children:
            size += child.get_subtree_size()
        
        return size
    
    def is_ancestor_of(self, node: 'KnowledgeNode') -> bool:
        """Check if this node is an ancestor of another node."""
        if self.id == node.id:
            return True
        
        if self.is_root:
            return False
        
        return self.parent.is_ancestor_of(node) if self.parent else False
    
    def is_descendant_of(self, node: 'KnowledgeNode') -> bool:
        """Check if this node is a descendant of another node."""
        return node.is_ancestor_of(self)
    
    def get_common_ancestor(self, node: 'KnowledgeNode') -> Optional['KnowledgeNode']:
        """Get common ancestor with another node."""
        this_path = self.get_path_to_root()
        other_path = node.get_path_to_root()
        
        # Find common prefix
        common_ancestor = None
        for i in range(min(len(this_path), len(other_path))):
            if this_path[i] == other_path[i]:
                # Would need to fetch node by ID
                common_ancestor = this_path[i]
            else:
                break
        
        return common_ancestor
    
    def get_distance_to(self, node: 'KnowledgeNode') -> int:
        """Get distance in edges to another node."""
        if self.id == node.id:
            return 0
        
        if self.is_ancestor_of(node):
            # Calculate depth difference
            return node.calculate_depth() - self.calculate_depth()
        
        if node.is_ancestor_of(self):
            # Calculate depth difference
            return self.calculate_depth() - node.calculate_depth()
        
        # Find common ancestor and calculate distance
        common_ancestor = self.get_common_ancestor(node)
        if common_ancestor:
            return (self.calculate_depth() - 1) + (node.calculate_depth() - 1)
        
        # No common ancestor found
        return -1
    
    def to_tree_dict(self) -> dict:
        """Convert node and children to tree structure."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "node_type": self.node_type,
            "status": self.status,
            "level": self.level,
            "path": self.path,
            "confidence_score": self.confidence_score,
            "quality_score": self.quality_score,
            "relevance_score": self.relevance_score,
            "keywords": self.keywords or [],
            "tags": self.tags or {},
            "metadata": self.metadata or {},
            "access_count": self.access_count,
            "update_count": self.update_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "children": [child.to_tree_dict() for child in self.children]
        }
    
    def validate_structure(self) -> List[str]:
        """Validate node structure and return errors."""
        errors = []
        
        if not self.title or not self.title.strip():
            errors.append("Title is required")
        
        if not self.node_type:
            errors.append("Node type is required")
        
        if self.level < 0:
            errors.append("Level cannot be negative")
        
        if self.confidence_score < 0 or self.confidence_score > 1:
            errors.append("Confidence score must be between 0 and 1")
        
        if self.quality_score < 0 or self.quality_score > 1:
            errors.append("Quality score must be between 0 and 1")
        
        if self.relevance_score < 0 or self.relevance_score > 1:
            errors.append("Relevance score must be between 0 and 1")
        
        if self.embedding_dimension and self.embedding_dimension <= 0:
            errors.append("Embedding dimension must be positive")
        
        return errors
