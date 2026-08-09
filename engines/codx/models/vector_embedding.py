"""
CODX Vector Embedding Models

SQLAlchemy models for vector embeddings,
embedding models, and similarity search.
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


class EmbeddingModel(str, Enum):
    """Vector embedding model types."""
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    WORD2VEC = "word2vec"
    GLOVE = "glove"
    FASTTEXT = "fasttext"
    CUSTOM = "custom"


class EmbeddingStatus(str, Enum):
    """Embedding status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class VectorStoreType(str, Enum):
    """Vector store types."""
    POSTGRESQL = "postgresql"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    MILVUS = "milvus"
    CHROMA = "chroma"
    FAISS = "faiss"
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"


class VectorEmbedding(Base):
    """
    Vector embedding model for CODX engine.
    
    Stores text embeddings and metadata for
    semantic similarity search and retrieval.
    """
    __tablename__ = "codx_vector_embeddings"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Embedding information
    text = Column(Text, nullable=False)
    embedding_model = Column(String(50), nullable=False, default=EmbeddingModel.TEXT_EMBEDDING_ADA_002)
    embedding_dimension = Column(Integer, nullable=False, default=1536)
    embedding_vector = Column(ARRAY(Float), nullable=False)
    
    # Normalization and processing
    normalized = Column(Boolean, default=False)
    processed_tokens = Column(Integer, default=0)
    max_tokens = Column(Integer, default=8192)
    
    # Metadata and context
    source_type = Column(String(50))  # document, query, etc.
    source_id = Column(UUID(as_uuid=True))  # Reference to source
    context_window = Column(Integer, default=0)
    chunk_index = Column(Integer, default=0)
    chunk_total = Column(Integer, default=1)
    
    # Quality and performance metrics
    similarity_threshold = Column(Float, default=0.7)
    retrieval_score = Column(Float, default=1.0)
    compression_ratio = Column(Float, default=1.0)
    
    # Store information
    vector_store = Column(String(50), nullable=False, default=VectorStoreType.POSTGRESQL)
    store_index = Column(String(100))  # Index name in vector store
    store_metadata = Column(JSON, default=dict)
    
    # Status and lifecycle
    status = Column(String(20), nullable=False, default=EmbeddingStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    nodes = relationship("KnowledgeNode", secondary="node_embeddings", back_populates="embeddings")
    
    # Indexes
    __table_args__ = (
        Index('idx_embedding_model', 'embedding_model'),
        Index('idx_embedding_status', 'status'),
        Index('idx_embedding_source_type', 'source_type'),
        Index('idx_embedding_source_id', 'source_id'),
        Index('idx_embedding_vector_store', 'vector_store'),
        Index('idx_embedding_created_at', 'created_at'),
        Index('idx_embedding_store_index', 'store_index'),
        Index('idx_embedding_similarity_threshold', 'similarity_threshold'),
        Index('idx_embedding_retrieval_score', 'retrieval_score'),
    )
    
    def __repr__(self) -> str:
        return f"<VectorEmbedding(id={self.id}, model={self.embedding_model}, dimension={self.embedding_dimension})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "text": self.text,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "embedding_vector": self.embedding_vector,
            "normalized": self.normalized,
            "processed_tokens": self.processed_tokens,
            "max_tokens": self.max_tokens,
            "source_type": self.source_type,
            "source_id": str(self.source_id) if self.source_id else None,
            "context_window": self.context_window,
            "chunk_index": self.chunk_index,
            "chunk_total": self.chunk_total,
            "similarity_threshold": self.similarity_threshold,
            "retrieval_score": self.retrieval_score,
            "compression_ratio": self.compression_ratio,
            "vector_store": self.vector_store,
            "store_index": self.store_index,
            "store_metadata": self.store_metadata or {},
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if embedding is active."""
        return self.status == EmbeddingStatus.ACTIVE
    
    @property
    def is_normalized(self) -> bool:
        """Check if embedding is normalized."""
        return self.normalized
    
    @property
    def vector_length(self) -> float:
        """Calculate vector length."""
        return sum(x * x for x in self.embedding_vector) ** 0.5
    
    @property
    def token_utilization(self) -> float:
        """Calculate token utilization."""
        return self.processed_tokens / self.max_tokens if self.max_tokens > 0 else 0.0
    
    @property
    def is_chunked(self) -> bool:
        """Check if this is a chunk of a larger text."""
        return self.chunk_total > 1
    
    @property
    def chunk_position(self) -> str:
        """Get chunk position string."""
        if self.chunk_total <= 1:
            return "complete"
        return f"{self.chunk_index + 1}/{self.chunk_total}"
    
    def normalize(self) -> None:
        """Normalize the embedding vector."""
        import math
        
        # Calculate L2 norm
        norm = math.sqrt(sum(x * x for x in self.embedding_vector))
        
        if norm > 0:
            self.embedding_vector = [x / norm for x in self.embedding_vector]
            self.normalized = True
            self.updated_at = datetime.now(timezone.utc)
    
    def calculate_similarity(self, other_vector: list) -> float:
        """Calculate cosine similarity with another vector."""
        import math
        
        if len(self.embedding_vector) != len(other_vector):
            return 0.0
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(self.embedding_vector, other_vector))
        
        # Calculate magnitudes
        magnitude_a = math.sqrt(sum(a * a for a in self.embedding_vector))
        magnitude_b = math.sqrt(sum(b * b for b in other_vector))
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        # Calculate cosine similarity
        return dot_product / (magnitude_a * magnitude_b)
    
    def euclidean_distance(self, other_vector: list) -> float:
        """Calculate Euclidean distance to another vector."""
        import math
        
        if len(self.embedding_vector) != len(other_vector):
            return float('inf')
        
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.embedding_vector, other_vector)))
    
    def manhattan_distance(self, other_vector: list) -> float:
        """Calculate Manhattan distance to another vector."""
        if len(self.embedding_vector) != len(other_vector):
            return float('inf')
        
        return sum(abs(a - b) for a, b in zip(self.embedding_vector, other_vector))
    
    def update_retrieval_score(self, score: float) -> None:
        """Update retrieval score based on usage."""
        # Weighted average with existing score
        if self.retrieval_score == 0:
            self.retrieval_score = score
        else:
            # Exponential moving average
            alpha = 0.1
            self.retrieval_score = alpha * score + (1 - alpha) * self.retrieval_score
        
        self.updated_at = datetime.now(timezone.utc)
    
    def update_similarity_threshold(self, threshold: float) -> None:
        """Update similarity threshold based on performance."""
        self.similarity_threshold = max(0.0, min(1.0, threshold))
        self.updated_at = datetime.now(timezone.utc)
    
    def update_compression_ratio(self, ratio: float) -> None:
        """Update compression ratio."""
        self.compression_ratio = max(0.0, min(1.0, ratio))
        self.updated_at = datetime.now(timezone.utc)
    
    def archive(self) -> None:
        """Archive the embedding."""
        self.status = EmbeddingStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
    
    def activate(self) -> None:
        """Activate the embedding."""
        self.status = EmbeddingStatus.ACTIVE
    
    def deactivate(self) -> None:
        """Deactivate the embedding."""
        self.status = EmbeddingStatus.INACTIVE
    
    def set_store_metadata(self, key: str, value: Any) -> None:
        """Set store metadata."""
        if not self.store_metadata:
            self.store_metadata = {}
        
        self.store_metadata[key] = value
    
    def get_store_metadata(self, key: str, default: Any = None) -> Any:
        """Get store metadata value."""
        if self.store_metadata:
            return self.store_metadata.get(key, default)
        return default
    
    def validate_structure(self) -> List[str]:
        """Validate embedding structure and return errors."""
        errors = []
        
        if not self.text or not self.text.strip():
            errors.append("Text is required")
        
        if not self.embedding_model:
            errors.append("Embedding model is required")
        
        if self.embedding_dimension <= 0:
            errors.append("Embedding dimension must be positive")
        
        if not self.embedding_vector or len(self.embedding_vector) != self.embedding_dimension:
            errors.append("Embedding vector dimension mismatch")
        
        if self.processed_tokens < 0:
            errors.append("Processed tokens cannot be negative")
        
        if self.max_tokens <= 0:
            errors.append("Max tokens cannot be negative")
        
        if self.processed_tokens > self.max_tokens:
            errors.append("Processed tokens cannot exceed max tokens")
        
        if self.similarity_threshold < 0 or self.similarity_threshold > 1:
            errors.append("Similarity threshold must be between 0 and 1")
        
        if self.retrieval_score < 0 or self.retrieval_score > 1:
            errors.append("Retrieval score must be between 0 and 1")
        
        if self.compression_ratio < 0 or self.compression_ratio > 1:
            errors.append("Compression ratio must be between 0 and 1")
        
        return errors
    
    def to_vector_dict(self) -> dict:
        """Convert to vector representation."""
        return {
            "id": str(self.id),
            "vector": self.embedding_vector,
            "dimension": self.embedding_dimension,
            "model": self.embedding_model,
            "normalized": self.normalized,
            "length": self.vector_length,
            "token_utilization": self.token_utilization,
            "is_chunked": self.is_chunked,
            "chunk_position": self.chunk_position,
            "similarity_threshold": self.similarity_threshold,
            "retrieval_score": self.retrieval_score,
            "compression_ratio": self.compression_ratio
        }
    
    def to_search_dict(self) -> dict:
        """Convert to search representation."""
        return {
            "id": str(self.id),
            "text": self.text,
            "vector": self.embedding_vector,
            "metadata": {
                "model": self.embedding_model,
                "dimension": self.embedding_dimension,
                "source_type": self.source_type,
                "source_id": str(self.source_id) if self.source_id else None,
                "context_window": self.context_window,
                "chunk_index": self.chunk_index,
                "chunk_total": self.chunk_total,
                "is_chunked": self.is_chunked,
                "chunk_position": self.chunk_position
            },
            "scores": {
                "retrieval": self.retrieval_score,
                "similarity_threshold": self.similarity_threshold
            },
            "store": {
                "type": self.vector_store,
                "index": self.store_index,
                "metadata": self.store_metadata or {}
            },
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_nearest_neighbors(self, embeddings: list, k: int = 5) -> list:
        """Get k nearest neighbors from a list of embeddings."""
        # Calculate similarities
        similarities = []
        for embedding in embeddings:
            if embedding.id != self.id:
                similarity = self.calculate_similarity(embedding.embedding_vector)
                similarities.append({
                    "id": embedding.id,
                    "similarity": similarity
                })
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top k
        return similarities[:k]
    
    def get_similarity_range(self, min_similarity: float, max_similarity: float) -> int:
        """Get count of embeddings within similarity range."""
        # This would need to query the database
        # Placeholder for now
        return 0
    
    def calculate_precision_at_k(self, relevant_embeddings: list, k: int) -> float:
        """Calculate precision@k metric."""
        if not relevant_embeddings:
            return 0.0
        
        # Get top k nearest neighbors
        neighbors = self.get_nearest_neighbors([], k)
        top_k_ids = [n["id"] for n in neighbors]
        
        # Count how many are relevant
        relevant_count = sum(1 for neighbor_id in top_k_ids if neighbor_id in relevant_embeddings)
        
        return relevant_count / k
    
    def calculate_recall_at_k(self, relevant_embeddings: list, k: int) -> float:
        """Calculate recall@k metric."""
        if not relevant_embeddings:
            return 0.0
        
        # Get top k nearest neighbors
        neighbors = self.get_nearest_neighbors([], k)
        top_k_ids = [n["id"] for n in neighbors]
        
        # Count how many relevant items were found
        found_count = sum(1 for embedding_id in relevant_embeddings if embedding_id in top_k_ids)
        
        return found_count / len(relevant_embeddings) if relevant_embeddings else 0.0
    
    def calculate_f1_score(self, relevant_embeddings: list, k: int) -> float:
        """Calculate F1 score."""
        precision = self.calculate_precision_at_k(relevant_embeddings, k)
        recall = self.calculate_recall_at_k(relevant_embeddings, k)
        
        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)
    
    def get_embedding_stats(self) -> dict:
        """Get embedding statistics."""
        return {
            "dimension": self.embedding_dimension,
            "vector_length": self.vector_length,
            "normalized": self.normalized,
            "token_utilization": self.token_utilization,
            "similarity_threshold": self.similarity_threshold,
            "retrieval_score": self.retrieval_score,
            "compression_ratio": self.compression_ratio,
            "is_chunked": self.is_chunked,
            "chunk_position": self.chunk_position
        }
