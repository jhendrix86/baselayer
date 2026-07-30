"""
CODX Knowledge Graph Models

SQLAlchemy models for graph structure, traversal,
and analytics in the knowledge graph.
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


class GraphType(str, Enum):
    """Knowledge graph types."""
    CONCEPT_GRAPH = "concept_graph"
    ENTITY_RELATIONSHIP_GRAPH = "entity_relationship_graph"
    PROCEDURE_GRAPH = "procedure_graph"
    ONTOLOGY_GRAPH = "ontology_graph"
    TEMPORAL_GRAPH = "temporal_graph"
    SEMANTIC_GRAPH = "semantic_graph"
    CAUSAL_GRAPH = "causal_graph"
    KNOWLEDGE_MAP = "knowledge_map"


class GraphStatus(str, Enum):
    """Knowledge graph status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUILDING = "building"
    UPDATING = "updating"
    ERROR = "error"
    LOCKED = "locked"


class TraversalAlgorithm(str, Enum):
    """Graph traversal algorithms."""
    BFS = "bfs"  # Breadth-First Search
    DFS = "dfs"  # Depth-First Search
    Dijkstra = "dijkstra"  # Shortest path
    A_STAR = "a_star"  # A* pathfinding
    FLOYD_WARSHALL = "floyd_warshall"  # All-pairs shortest paths
    TOPOLOGICAL_SORT = "topological_sort"  # Topological ordering
    STRONGLY_CONNECTED = "strongly_connected"  # Strongly connected components
    BIPARTITE_MATCHING = "bipartite_matching"  # Bipartite matching


class KnowledgeGraph(Base):
    """
    Knowledge graph model for CODX engine.
    
    Represents graph structures, metadata, and
    traversal algorithms for knowledge navigation.
    """
    __tablename__ = "codx_knowledge_graphs"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    graph_type = Column(String(50), nullable=False, default=GraphType.CONCEPT_GRAPH)
    status = Column(String(20), nullable=False, default=GraphStatus.ACTIVE)
    
    # Graph structure
    node_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)
    max_depth = Column(Integer, default=0)
    average_degree = Column(Float, default=0.0)
    clustering_coefficient = Column(Float, default=0.0)
    
    # Graph properties
    is_directed = Column(Boolean, default=False)
    is_weighted = Column(Boolean, default=True)
    is_cyclic = Column(Boolean, default=False)
    is_connected = Column(Boolean, default=False)
    density = Column(Float, default=0.0)
    
    # Metadata and configuration
    metadata = Column(JSON, default=dict)
    configuration = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    
    # Root and hierarchy
    root_node_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_nodes.id'))
    parent_graph_id = Column(UUID(as_uuid=True), ForeignKey('codx_knowledge_graphs.id'))
    graph_hierarchy = Column(String(100))  # Path in graph hierarchy
    
    # Performance metrics
    traversal_performance = Column(JSON, default=dict)
    query_performance = Column(JSON, default=dict)
    index_performance = Column(JSON, default=dict)
    
    # Usage statistics
    access_count = Column(Integer, default=0)
    query_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    root_node = relationship("KnowledgeNode", foreign_keys=[root_node_id])
    parent_graph = relationship("KnowledgeGraph", foreign_keys=[parent_graph_id])
    child_graphs = relationship("KnowledgeGraph", foreign_keys=[parent_graph_id])
    nodes = relationship("KnowledgeNode", secondary="graph_nodes", back_populates="graphs")
    edges = relationship("KnowledgeEdge", secondary="graph_edges", back_populates="graphs")
    traversals = relationship("GraphTraversal", back_populates="graph")
    analytics = relationship("GraphAnalytics", back_populates="graph")
    
    # Indexes
    __table_args__ = (
        Index('idx_graph_type', 'graph_type'),
        Index('idx_graph_status', 'status'),
        Index('idx_graph_root_node', 'root_node_id'),
        Index('idx_graph_parent_graph', 'parent_graph_id'),
        Index('idx_graph_created_at', 'created_at'),
        Index('idx_graph_updated_at', 'updated_at'),
        Index('idx_graph_tags', 'tags', postgresql_using='gin'),
        Index('idx_graph_metadata', 'metadata', postgresql_using='gin'),
        Index('idx_graph_is_directed', 'is_directed'),
        Index('idx_graph_is_connected', 'is_connected'),
        Index('idx_graph_density', 'density'),
        Index('idx_graph_clustering', 'clustering_coefficient'),
        Index('idx_graph_node_count', 'node_count'),
        Index('idx_graph_edge_count', 'edge_count'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeGraph(id={self.id}, name={self.name}, type={self.graph_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "graph_type": self.graph_type,
            "status": self.status,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "max_depth": self.max_depth,
            "average_degree": self.average_degree,
            "clustering_coefficient": self.clustering_coefficient,
            "is_directed": self.is_directed,
            "is_weighted": self.is_weighted,
            "is_cyclic": self.is_cyclic,
            "is_connected": self.is_connected,
            "density": self.density,
            "metadata": self.metadata or {},
            "configuration": self.configuration or {},
            "tags": self.tags or [],
            "root_node_id": str(self.root_node_id) if self.root_node_id else None,
            "parent_graph_id": str(self.parent_graph_id) if self.parent_graph_id else None,
            "graph_hierarchy": self.graph_hierarchy,
            "traversal_performance": self.traversal_performance or {},
            "query_performance": self.query_performance or {},
            "index_performance": self.index_performance or {},
            "access_count": self.access_count,
            "query_count": self.query_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if graph is active."""
        return self.status == GraphStatus.ACTIVE
    
    @property
    def is_root(self) -> bool:
        """Check if graph is a root graph."""
        return self.parent_graph_id is None
    
    @property
    def depth(self) -> int:
        """Get graph depth."""
        return self.max_depth
    
    @property
    def average_path_length(self) -> float:
        """Calculate average path length."""
        if self.node_count <= 1:
            return 0.0
        
        # Approximation for connected graphs
        if self.is_connected:
            return self.node_count / (2.0 * self.density)
        
        return float('inf')
    
    def add_node(self, node_id: uuid.UUID) -> None:
        """Add a node to the graph."""
        self.node_count += 1
        self.last_updated = datetime.now(timezone.utc)
    
    def remove_node(self, node_id: uuid.UUID) -> None:
        """Remove a node from the graph."""
        if self.node_count > 0:
            self.node_count -= 1
        self.last_updated = datetime.now(timezone.utc)
    
    def add_edge(self, edge_id: uuid.UUID) -> None:
        """Add an edge to the graph."""
        self.edge_count += 1
        self.last_updated = datetime.now(timezone.utc)
    
    def remove_edge(self, edge_id: uuid.UUID) -> None:
        """Remove an edge from the graph."""
        if self.edge_count > 0:
            self.edge_count -= 1
        self.last_updated = datetime.now(timezone.utc)
    
    def update_statistics(self) -> None:
        """Update graph statistics."""
        # This would be calculated based on actual graph structure
        # Placeholder for now
        self.last_updated = datetime.now(timezone.utc)
    
    def calculate_density(self) -> float:
        """Calculate graph density."""
        if self.node_count <= 1:
            return 0.0
        
        max_edges = self.node_count * (self.node_count - 1)
        if self.is_directed:
            max_edges = self.node_count * (self.node_count - 1)
        
        return self.edge_count / max_edges if max_edges > 0 else 0.0
    
    def calculate_clustering_coefficient(self) -> float:
        """Calculate clustering coefficient."""
        # Placeholder - would need actual graph structure
        return 0.0
    
    def update_access(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
    
    def increment_query_count(self) -> None:
        """Increment query count."""
        self.query_count += 1
    
    def archive(self) -> None:
        """Archive the graph."""
        self.status = GraphStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
    
    def activate(self) -> None:
        """Activate the graph."""
        self.status = GraphStatus.ACTIVE
    
    def deactivate(self) -> None:
        """Deactivate the graph."""
        self.status = GraphStatus.INACTIVE
    
    def lock(self) -> None:
        """Lock the graph for updates."""
        self.status = GraphStatus.LOCKED
    
    def unlock(self) -> None:
        """Unlock the graph."""
        if self.status == GraphStatus.LOCKED:
            self.status = GraphStatus.ACTIVE
    
    def set_root(self, node_id: uuid.UUID) -> None:
        """Set root node."""
        self.root_node_id = node_id
    
    def set_parent(self, parent_graph_id: uuid.UUID) -> None:
        """Set parent graph."""
        self.parent_graph_id = parent_graph_id
    
    def add_tag(self, tag: str) -> None:
        """Add a tag."""
        if not self.tags:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
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
    
    def get_configuration(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        if self.configuration:
            return self.configuration.get(key, default)
        return default
    
    def set_configuration(self, key: str, value: Any) -> None:
        """Set configuration value."""
        if not self.configuration:
            self.configuration = {}
        
        self.configuration[key] = value
    
    def update_traversal_performance(self, algorithm: str, metrics: dict) -> None:
        """Update traversal performance metrics."""
        if not self.traversal_performance:
            self.traversal_performance = {}
        
        self.traversal_performance[algorithm] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics
        }
    
    def update_query_performance(self, query_type: str, metrics: dict) -> None:
        """Update query performance metrics."""
        if not self.query_performance:
            self.query_performance = {}
        
        self.query_performance[query_type] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics
        }
    
    def get_graph_summary(self) -> dict:
        """Get graph summary for display."""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.graph_type,
            "status": self.status,
            "nodes": self.node_count,
            "edges": self.edge_count,
            "depth": self.max_depth,
            "density": self.density,
            "clustering_coefficient": self.clustering_coefficient,
            "is_directed": self.is_directed,
            "is_connected": self.is_connected,
            "is_cyclic": self.is_cyclic,
            "average_degree": self.average_degree,
            "access_count": self.access_count,
            "query_count": self.query_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
    
    def validate_structure(self) -> List[str]:
        """Validate graph structure and return errors."""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Graph name is required")
        
        if not self.graph_type:
            errors.append("Graph type is required")
        
        if self.node_count < 0:
            errors.append("Node count cannot be negative")
        
        if self.edge_count < 0:
            errors.append("Edge count cannot be negative")
        
        if self.max_depth < 0:
            errors.append("Max depth cannot be negative")
        
        if self.density < 0 or self.density > 1:
            errors.append("Density must be between 0 and 1")
        
        if self.clustering_coefficient < 0 or self.clustering_coefficient > 1:
            errors.append("Clustering coefficient must be between 0 and 1")
        
        if self.average_degree < 0:
            errors.append("Average degree cannot be negative")
        
        return errors
    
    def to_networkx_dict(self) -> dict:
        """Convert to NetworkX-compatible dictionary."""
        return {
            "directed": self.is_directed,
            "multigraph": False,
            "nodes": [],  # Would need to fetch actual nodes
            "edges": [],  # Would need to fetch actual edges
            "graph": {
                "name": self.name,
                "type": self.graph_type
            },
            "metadata": self.metadata or {}
        }
    
    def to_cypher_schema(self) -> str:
        """Convert to Cypher schema definition."""
        return f"""
        CREATE (:{self.graph_type}) {{
            id: ID,
            title: String,
            description: String,
            created_at: DateTime
        }}
        
        CREATE (:{self.graph_type}_rel) {{
            source: ID,
            target: ID,
            type: String,
            weight: Float
        }}
        """
    
    def get_statistics(self) -> dict:
        """Get detailed graph statistics."""
        return {
            "basic": {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "density": self.density,
                "is_directed": self.is_directed,
                "is_connected": self.is_connected,
                "is_cyclic": self.is_cyclic
            },
            "degrees": {
                "average_degree": self.average_degree,
                "max_degree": 0,  # Would need calculation
                "min_degree": 0,  # Would need calculation
                "degree_distribution": {}  # Would need calculation
            },
            "paths": {
                "average_path_length": self.average_path_length,
                "diameter": 0,  # Would need calculation
                "radius": 0,  # Would need calculation
                "eccentricity": {}  # Would need calculation
            },
            "clustering": {
                "clustering_coefficient": self.clustering_coefficient,
                "connected_components": 0,  # Would need calculation
                "strongly_connected_components": 0  # Would need calculation
            },
            "performance": {
                "traversal_performance": self.traversal_performance or {},
                "query_performance": self.query_performance or {},
                "index_performance": self.index_performance or {}
            }
        }
