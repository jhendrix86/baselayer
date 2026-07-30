"""
CODX Pydantic Schemas

Request and response schemas for CODX knowledge engine
including validation, search, and graph operations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, validator
from sqlalchemy.dialects.postgresql import UUID


class NodeType(str, Enum):
    """Node types for knowledge graph."""
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


class EdgeType(str, Enum):
    """Edge types for knowledge graph."""
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
    HOLONYM_OF = "holonym_of"
    MERONYM_OF = "meronym_of"
    MEMBER_OF = "member_of"
    INSTANCE_OF = "instance_of"
    PROPERTY_OF = "property_of"
    VALUE_OF = "value_of"


class NodeStatus(str, Enum):
    """Node status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class EdgeStatus(str, Enum):
    """Edge status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class GraphType(str, Enum):
    """Graph type values."""
    CONCEPT_GRAPH = "concept_graph"
    ENTITY_RELATIONSHIP_GRAPH = "entity_relationship_graph"
    PROCEDURE_GRAPH = "procedure_graph"
    ONTOLOGY_GRAPH = "ontology_graph"
    TEMPORAL_GRAPH = "temporal_graph"
    SEMANTIC_GRAPH = "semantic_graph"
    CAUSAL_GRAPH = "causal_graph"
    KNOWLEDGE_MAP = "knowledge_map"


class GraphStatus(str, Enum):
    """Graph status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUILDING = "building"
    UPDATING = "updating"
    ERROR = "error"
    LOCKED = "locked"


class TraversalAlgorithm(str, Enum):
    """Traversal algorithm values."""
    BFS = "bfs"
    DFS = "dfs"
    DIJKSTRA = "dijkstra"
    A_STAR = "a_star"
    FLOYD_WARSHALL = "floyd_warshall"
    TOPOLOGICAL_SORT = "topological_sort"
    STRONGLY_CONNECTED = "strongly_connected"
    BIPARTITE_MATCHING = "bipartite_matching"


class EmbeddingModel(str, Enum):
    """Embedding model values."""
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    WORD2VEC = "word2vec"
    GLOVE = "glove"
    FASTTEXT = "fasttext"
    CUSTOM = "custom"


class EmbeddingStatus(str, Enum):
    """Embedding status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class VectorStoreType(str, Enum):
    """Vector store type values."""
    POSTGRESQL = "postgresql"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    MILVUS = "milvus"
    CHROMA = "chroma"
    FAISS = "faiss"
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"


# Request Schemas

class NodeCreate(BaseModel):
    """Node creation request."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    content: Optional[str] = Field(None, max_length=10000)
    node_type: NodeType = Field(..., description="Type of node")
    parent_id: Optional[str] = Field(None, description="Parent node ID")
    root_id: Optional[str] = Field(None, description="Root node ID")
    keywords: List[str] = Field(default_factory=list, max_items=50)
    tags: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = Field(None, description="Embedding ID")
    source: Optional[str] = Field(None, max_length=200)
    source_url: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title is required')
        return v.strip()
    
    @validator('keywords')
    def validate_keywords(cls, v):
        if len(v) > 50:
            raise ValueError('Maximum 50 keywords allowed')
        return [k.strip() for k in v if k.strip()]
    
    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError('Confidence score must be between 0.0 and 1.0')
        return v
    
    @validator('quality_score')
    def validate_quality_score(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError('Quality score must be between 0.0 and 1.0')
        return v


class NodeUpdate(BaseModel):
    """Node update request."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    content: Optional[str] = Field(None, max_length=10000)
    status: Optional[NodeStatus] = Field(None)
    keywords: Optional[List[str]] = Field(None, max_items=50)
    tags: Optional[Dict[str, Any]] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)
    embedding_id: Optional[str] = Field(None)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Confidence score must be between 0.0 and 1.0')
        return v
    
    @validator('quality_score')
    def validate_quality_score(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Quality score must be between 0.0 and 1.0')
        return v


class EdgeCreate(BaseModel):
    """Edge creation request."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    edge_type: EdgeType = Field(..., description="Type of edge")
    weight: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    strength: float = Field(default=1.0, ge=0.0)
    bidirectional: bool = Field(default=False)
    valid_from: Optional[datetime] = Field(None)
    valid_to: Optional[datetime] = Field(None)
    label: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    properties: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[str] = Field(None, max_length=1000)
    evidence: Optional[str] = Field(None, max_length=2000)
    source: Optional[str] = Field(None, max_length=200)
    created_by: Optional[str] = Field(None, max_length=200)
    
    @validator('source_id', 'target_id')
    def validate_ids(cls, v):
        if not v or not v.strip():
            raise ValueError('Node ID is required')
        return v.strip()
    
    @validator('weight')
    def validate_weight(cls, v):
        if v < 0.0:
            raise ValueError('Weight must be non-negative')
        return v
    
    @validator('confidence')
    def validate_confidence(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return v
    
    @validator('strength')
    def validate_strength(cls, v):
        if v < 0.0:
            raise ValueError('Strength must be non-negative')
        return v


class EdgeUpdate(BaseModel):
    """Edge update request."""
    edge_type: Optional[EdgeType] = Field(None)
    status: Optional[EdgeStatus] = Field(None)
    weight: Optional[float] = Field(None, ge=0.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    strength: Optional[float] = Field(None, ge=0.0)
    valid_from: Optional[datetime] = Field(None)
    valid_to: Optional[datetime] = Field(None)
    label: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    properties: Optional[Dict[str, Any]] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)
    context: Optional[str] = Field(None, max_length=1000)
    evidence: Optional[str] = Field(None, max_length=2000)
    
    @validator('weight')
    def validate_weight(cls, v):
        if v is not None and v < 0.0:
            raise ValueError('Weight must be non-negative')
        return v
    
    @validator('confidence')
    def validate_confidence(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return v
    
    @validator('strength')
    def validate_strength(cls, v):
        if v is not None and v < 0.0:
            raise ValueError('Strength must be non-negative')
        return v


class GraphCreate(BaseModel):
    """Graph creation request."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    graph_type: GraphType = Field(..., description="Type of graph")
    root_node_id: Optional[str] = Field(None, description="Root node ID")
    parent_graph_id: Optional[str] = Field(None, description="Parent graph ID")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, max_items=50)
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Graph name is required')
        return v.strip()


class GraphUpdate(BaseModel):
    """Graph update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[GraphStatus] = Field(None)
    root_node_id: Optional[str] = Field(None)
    parent_graph_id: Optional[str] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)
    configuration: Optional[Dict[str, Any]] = Field(None)
    tags: Optional[List[str]] = Field(None)
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v.strip() or len(v.strip()) < 1):
            raise ValueError('Name must be non-empty string')
        return v.strip()


class EmbeddingCreate(BaseModel):
    """Embedding creation request."""
    text: str = Field(..., min_length=1, max_length=10000)
    embedding_model: EmbeddingModel = Field(..., description="Embedding model to use")
    source_type: str = Field(..., description="Type of source text")
    source_id: Optional[str] = Field(None, description="Source node ID")
    context_window: Optional[int] = Field(None, ge=0, le=8192)
    chunk_index: Optional[int] = Field(None, ge=0)
    chunk_total: Optional[int] = Field(None, ge=1)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    vector_store: VectorStoreType = Field(..., description="Vector store type")
    store_index: Optional[str] = Field(None, max_length=100)
    store_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError('Text is required for embedding')
        return v.strip()
    
    @validator('similarity_threshold')
    def validate_similarity_threshold(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError('Similarity threshold must be between 0.0 and 1.0')
        return v


class EmbeddingUpdate(BaseModel):
    """Embedding update request."""
    status: Optional[EmbeddingStatus] = Field(None)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    compression_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    store_metadata: Optional[Dict[str, Any]] = Field(None)


# Response Schemas

class NodeResponse(BaseModel):
    """Node response."""
    id: str
    title: str
    description: Optional[str]
    content: Optional[str]
    node_type: NodeType
    status: NodeStatus
    summary: Optional[str]
    keywords: List[str]
    tags: Dict[str, Any]
    metadata: Dict[str, Any]
    embedding_id: Optional[str]
    embedding_vector: Optional[List[float]]
    embedding_model: Optional[str]
    embedding_dimension: Optional[int]
    parent_id: Optional[str]
    root_id: Optional[str]
    level: int
    path: Optional[str]
    confidence_score: float
    quality_score: float
    relevance_score: float
    source: Optional[str]
    source_url: Optional[str]
    author: Optional[str]
    created_by: Optional[str]
    access_count: int
    update_count: int
    last_accessed: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    children: List['NodeResponse'] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EdgeResponse(BaseModel):
    """Edge response."""
    id: str
    edge_type: EdgeType
    status: EdgeStatus
    source_id: str
    target_id: str
    weight: float
    confidence: float
    strength: float
    bidirectional: bool
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    label: Optional[str]
    description: Optional[str]
    properties: Dict[str, Any]
    metadata: Dict[str, Any]
    context: Optional[str]
    evidence: Optional[str]
    source: Optional[str]
    created_by: Optional[str]
    access_count: int
    update_count: int
    last_accessed: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class GraphResponse(BaseModel):
    """Graph response."""
    id: str
    name: str
    description: Optional[str]
    graph_type: GraphType
    status: GraphStatus
    node_count: int
    edge_count: int
    max_depth: int
    average_degree: float
    clustering_coefficient: float
    is_directed: bool
    is_weighted: bool
    is_cyclic: bool
    is_connected: bool
    density: float
    metadata: Dict[str, Any]
    configuration: Dict[str, Any]
    tags: List[str]
    root_node_id: Optional[str]
    parent_graph_id: Optional[str]
    graph_hierarchy: Optional[str]
    traversal_performance: Dict[str, Any]
    query_performance: Dict[str, Any]
    index_performance: Dict[str, Any]
    access_count: int
    query_count: int
    last_accessed: Optional[datetime]
    last_updated: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EmbeddingResponse(BaseModel):
    """Embedding response."""
    id: str
    text: str
    embedding_model: EmbeddingModel
    embedding_dimension: int
    embedding_vector: List[float]
    normalized: bool
    processed_tokens: int
    max_tokens: int
    source_type: str
    source_id: Optional[str]
    context_window: Optional[int]
    chunk_index: Optional[int]
    chunk_total: int
    similarity_threshold: float
    retrieval_score: float
    compression_ratio: float
    vector_store: VectorStoreType
    store_index: Optional[str]
    store_metadata: Dict[str, Any]
    status: EmbeddingStatus
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Search and Query Schemas

class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., min_length=1, max_length=500)
    node_types: Optional[List[NodeType]] = Field(None)
    edge_types: Optional[List[EdgeType]] = Field(None)
    graph_ids: Optional[List[str]] = Field(None)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_embeddings: bool = Field(default=False)
    include_metadata: bool = Field(default=True)
    sort_by: Optional[str] = Field(None)
    sort_order: str = Field(default="relevance", regex="^(relevance|created_at|updated_at|title|access_count)$")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query is required')
        return v.strip()
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ["relevance", "created_at", "updated_at", "title", "access_count"]:
            raise ValueError('Invalid sort order')
        return v


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    total: int
    limit: int
    offset: int
    results: List[Dict[str, Any]]
    facets: Dict[str, Any]
    suggestions: List[str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TraversalRequest(BaseModel):
    """Traversal request."""
    start_node_id: str = Field(..., description="Starting node ID")
    algorithm: TraversalAlgorithm = Field(..., description="Traversal algorithm")
    target_node_id: Optional[str] = Field(None, description="Target node ID for pathfinding")
    max_depth: Optional[int] = Field(None, ge=0, le=10)
    max_nodes: Optional[int] = Field(None, ge=0, le=1000)
    edge_types: Optional[List[EdgeType]] = Field(None)
    include_metadata: bool = Field(default=True)
    return_paths: bool = Field(default=False)
    
    @validator('start_node_id')
    def validate_start_node_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Start node ID is required')
        return v.strip()
    
    @validator('max_depth')
    def validate_max_depth(cls, v):
        if v is not None and (v < 0 or v > 10):
            raise ValueError('Max depth must be between 0 and 10')
        return v
    
    @validator('max_nodes')
    def validate_max_nodes(cls, v):
        if v is not None and (v < 0 or v > 1000):
            raise ValueError('Max nodes must be between 0 and 1000')
        return v


class TraversalResponse(BaseModel):
    """Traversal response."""
    algorithm: TraversalAlgorithm
    start_node_id: str
    target_node_id: Optional[str]
    path: List[str]
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    distance: Optional[float]
    total_nodes_visited: int
    total_edges_traversed: int
    execution_time_ms: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Analytics Schemas

class GraphAnalyticsRequest(BaseModel):
    """Graph analytics request."""
    graph_id: Optional[str] = Field(None)
    include_performance: bool = Field(default=True)
    include_structure: bool = Field(default=True)
    include_usage: bool = Field(default=True)
    date_range: Optional[Dict[str, str]] = Field(None)
    
    @validator('date_range')
    def validate_date_range(cls, v):
        if v is not None:
            start = v.get('start')
            end = v.get('end')
            
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    if start_dt > end_dt:
                        raise ValueError('Start date must be before end date')
                except ValueError:
                    raise ValueError('Invalid date format')
        
        return v


class GraphAnalyticsResponse(BaseModel):
    """Graph analytics response."""
    graph_id: Optional[str]
    basic_metrics: Dict[str, Any]
    structure_analysis: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    usage_statistics: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Pagination Schemas

class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = Field(None)
    sort_order: str = Field(default="desc", regex="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Paginated response."""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool
    
    @classmethod
    def create(cls, items: List[Any], total: int, page: int, size: int) -> "PaginatedResponse":
        """Create paginated response."""
        pages = (total + size - 1) // size + 1
        
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


# Error Schemas

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Filter Schemas

class NodeFilter(BaseModel):
    """Node filter parameters."""
    status: Optional[List[NodeStatus]] = None
    node_types: Optional[List[NodeType]] = None
    keywords: Optional[List[str]] = None
    tags: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    author: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    min_quality: Optional[float] = None
    max_quality: Optional[float] = None
    has_embedding: Optional[bool] = None
    is_root: Optional[bool] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None


class EdgeFilter(BaseModel):
    """Edge filter parameters."""
    status: Optional[List[EdgeStatus]] = None
    edge_types: Optional[List[EdgeType]] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    min_strength: Optional[float] = None
    max_strength: Optional[float] = None
    is_bidirectional: Optional[bool] = None
    is_temporal: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None


class GraphFilter(BaseModel):
    """Graph filter parameters."""
    status: Optional[List[GraphStatus]] = None
    graph_types: Optional[List[GraphType]] = None
    root_node_id: Optional[str] = None
    parent_graph_id: Optional[str] = None
    tags: Optional[List[str]] = None
    is_directed: Optional[bool] = None
    is_weighted: Optional[bool] = None
    is_cyclic: Optional[bool] = None
    is_connected: Optional[bool] = None
    min_node_count: Optional[int] = None
    max_node_count: Optional[int] = None
    min_edge_count: Optional[int] = None
    max_edge_count: Optional[int] None
    min_depth: Optional[int] = None
    max_depth: Optional[int] None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] None


class EmbeddingFilter(BaseModel):
    """Embedding filter parameters."""
    status: Optional[List[EmbeddingStatus]] = None
    embedding_model: Optional[EmbeddingModel] = None
    source_type: Optional[str] = None
    vector_store: Optional[VectorStoreType] = None
    similarity_threshold_min: Optional[float] = None
    similarity_threshold_max: Optional[float] = None
    retrieval_score_min: Optional[float] = None
    retrieval_score_max: Optional[float] = None
    compression_ratio_min: Optional[float] = None
    compression_ratio_max: Optional[float] = None
    is_normalized: Optional[bool] = None
    is_chunked: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None


# Query Schemas

class QueryRequest(BaseModel):
    """Knowledge query request."""
    query: str = Field(..., min_length=1, max_length=500)
    query_type: str = Field(default="semantic", regex="^(semantic|keyword|hybrid|graph)$")
    context: Optional[str] = Field(None, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    include_explanations: bool = Field(default=False)
    include_sources: bool = Field(default=True)
    include_confidence: bool = Field(default=True)
    include_metadata: bool = Field(default=True)
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query is required')
        return v.strip()
    
    @validator('query_type')
    def validate_query_type(cls, v):
        if v not in ["semantic", "keyword", "hybrid", "graph"]:
            raise ValueError('Invalid query type')
        return v
    
    @validator('similarity_threshold')
    def validate_similarity_threshold(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Similarity threshold must be between 0.0 and 1.0')
        return v


class QueryResponse(BaseModel):
    """Knowledge query response."""
    query: str
    query_type: str
    results: List[Dict[str, Any]]
    total_found: int
    execution_time_ms: int
    explanations: List[str]
    sources: List[str]
    confidence_scores: List[float]
    metadata: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Batch Operations Schemas

class BatchNodeCreate(BaseModel):
    """Batch node creation request."""
    nodes: List[NodeCreate] = Field(..., min_items=1, max_items=100)
    
    @validator('nodes')
    def validate_nodes(cls, v):
        if not v:
            raise ValueError('At least one node is required')
        return v


class BatchEdgeCreate(BaseModel):
    """Batch edge creation request."""
    edges: List[EdgeCreate] = Field(..., min_items=1, max_items=100)
    
    @validator('edges')
    def validate_edges(cls, v):
        if not v:
            raise ValueError('At least one edge is required')
        return v


class BatchEmbeddingCreate(BaseModel):
    """Batch embedding creation request."""
    embeddings: List[EmbeddingCreate] = Field(..., min_items=1, max_items=100)
    
    @validator('embeddings')
    def validate_embeddings(cls, v):
        if not v:
            raise ValueError('At least one embedding is required')
        return v


# Import/Export Schemas

class ImportRequest(BaseModel):
    """Knowledge import request."""
    format: str = Field(default="json", regex="^(json|csv|neo4j|graphml)$")
    source: Optional[str] = Field(None)
    validation_strict: bool = Field(default=True)
    merge_strategy: str = Field(default="skip", regex="^(skip|merge|replace|update)$")
    create_missing_nodes: bool = Field(default=True)
    create_missing_edges: bool = Field(default=True)
    
    @validator('format')
    def validate_format(cls, v):
        if v not in ["json", "csv", "neo4j", "graphml"]:
            raise ValueError('Invalid import format')
        return v
    
    @validator('merge_strategy')
    def validate_merge_strategy(cls, v):
        if v not in ["skip", "merge", "replace", "update"]:
            raise ValueError('Invalid merge strategy')
        return v


class ImportResponse(BaseModel):
    """Knowledge import response."""
    format: str
    source: Optional[str]
    nodes_imported: int
    edges_imported: int
    nodes_updated: int
    edges_updated: int
    nodes_failed: int
    edges_failed: int
    errors: List[str]
    warnings: List[str]
    execution_time_ms: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ExportRequest:
    """Knowledge export request."""
    format: str = Field(default="json", regex="^(json|csv|neo4j|graphml|cypher)$")
    graph_id: Optional[str] = Field(None)
    include_embeddings: bool = Field(default=False)
    include_metadata: bool = Field(default=True)
    node_types: Optional[List[NodeType]] = Field(None)
    edge_types: Optional[List[EdgeType]] = Field(None)
    max_depth: Optional[int] = Field(None, ge=0, le=10)
    max_nodes: Optional[int] = Field(None, ge=0, le=1000)
    
    @validator('format')
    def validate_format(cls, v):
        if v not in ["json", "csv", "neo4j", "graphml", "cypher"]:
            raise ValueError('Invalid export format')
        return v


class ExportResponse:
    """Knowledge export response."""
    format: str
    graph_id: Optional[str]
    nodes_exported: int
    edges_exported: int
    file_path: Optional[str]
    download_url: Optional[str]
    file_size_bytes: int
    execution_time_ms: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
