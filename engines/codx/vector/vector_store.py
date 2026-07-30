"""
CODX Vector Store

Vector database interface and operations for CODX
knowledge engine with multiple backends.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
import numpy as np
from abc import ABC, abstractmethod
import json
import pickle

from ..models.vector_embedding import VectorEmbedding, EmbeddingStatus, VectorStoreType
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class VectorStoreBackend(ABC):
    """
    Abstract base class for vector store backends.
    """
    
    @abstractmethod
    async def add_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Add embeddings to store."""
        pass
    
    @abstractmethod
    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings."""
        pass
    
    @abstractmethod
    async def delete_embeddings(self, embedding_ids: List[str]) -> bool:
        """Delete embeddings from store."""
        pass
    
    @abstractmethod
    async def update_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Update embeddings in store."""
        pass
    
    @abstractmethod
    async def get_embedding(self, embedding_id: str) -> Optional[VectorEmbedding]:
        """Get embedding by ID."""
        pass
    
    @abstractmethod
    async def list_embeddings(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorEmbedding]:
        """List embeddings with filters."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        pass


class PostgreSQLVectorStore(VectorStoreBackend):
    """
    PostgreSQL vector store implementation.
    """
    
    def __init__(self, db_session, index_name: str = "codx_vectors"):
        """Initialize PostgreSQL vector store."""
        self.db_session = db_session
        self.index_name = index_name
        self.embedding_dimension = 1536  # Default for text-embedding-ada-002
    
    async def add_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Add embeddings to PostgreSQL."""
        try:
            embedding_ids = []
            
            for embedding in embeddings:
                # Validate embedding
                if not embedding.embedding_vector or len(embedding.embedding_vector) != self.embedding_dimension:
                    logger.warning(
                        "Invalid embedding dimension",
                        embedding_id=str(embedding.id),
                        expected=self.embedding_dimension,
                        actual=len(embedding.embedding_vector) if embedding.embedding_vector else 0
                    )
                    continue
                
                # Add to database
                self.db_session.add(embedding)
                embedding_ids.append(str(embedding.id))
            
            await self.db_session.commit()
            
            logger.info(
                "Embeddings added to PostgreSQL",
                count=len(embedding_ids),
                embedding_ids=embedding_ids
            )
            
            return embedding_ids
            
        except Exception as e:
            logger.error(
                "Failed to add embeddings to PostgreSQL",
                error=str(e),
                embedding_count=len(embeddings)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"PostgreSQL embedding addition failed: {str(e)}") from e
    
    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings in PostgreSQL."""
        try:
            # Validate query vector
            if len(query_vector) != self.embedding_dimension:
                raise BaseLayerError(f"Query vector dimension mismatch: expected {self.embedding_dimension}, got {len(query_vector)}")
            
            # Convert to numpy array for efficient computation
            query_np = np.array(query_vector, dtype=np.float32)
            
            # Get all embeddings
            from sqlalchemy import select, text
            
            # Using pgvector extension for similarity search
            sql_query = text(f"""
                SELECT 
                    e.id,
                    e.text,
                    e.embedding_vector,
                    1 - (e.embedding_vector <=> :query_vector::vector) as distance,
                    e.source_type,
                    e.source_id,
                    e.similarity_threshold,
                    e.retrieval_score,
                    e.status,
                    e.created_at,
                    e.updated_at
                FROM {self.index_name} e
                WHERE e.status = 'active'
                ORDER BY e.embedding_vector <=> :query_vector::vector
                LIMIT :limit
            """)
            
            result = await self.db_session.execute(
                sql_query,
                {"query_vector": query_np.tolist(), "limit": top_k}
            )
            
            rows = result.fetchall()
            
            # Format results
            results = []
            for row in rows:
                # Convert distance to similarity
                similarity = 1.0 - float(row.distance) if row.distance else 0.0
                
                if similarity >= threshold:
                    results.append({
                        "embedding_id": str(row.id),
                        "text": row.text,
                        "similarity": similarity,
                        "distance": float(row.distance) if row.distance else 0.0,
                        "source_type": row.source_type,
                        "source_id": str(row.source_id) if row.source_id else None,
                        "metadata": {
                            "similarity_threshold": float(row.similarity_threshold) if row.similarity_threshold else 0.0,
                            "retrieval_score": float(row.retrieval_score) if row.retrieval_score else 0.0,
                            "status": row.status,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "updated_at": row.updated_at.isoformat() if row.updated_at else None
                        }
                    })
            
            logger.info(
                "PostgreSQL similarity search completed",
                query_dimension=len(query_vector),
                results_count=len(results),
                threshold=threshold,
                top_k=top_k
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "PostgreSQL similarity search failed",
                error=str(e),
                query_dimension=len(query_vector),
                top_k=top_k,
                threshold=threshold
            )
            raise BaseLayerError(f"PostgreSQL search failed: {str(e)}") from e
    
    async def delete_embeddings(self, embedding_ids: List[str]) -> bool:
        """Delete embeddings from PostgreSQL."""
        try:
            from sqlalchemy import delete, text
            
            # Build delete query
            placeholders = ",".join([f"'{eid}'" for eid in embedding_ids])
            sql_query = text(f"""
                UPDATE {self.index_name} 
                SET status = 'archived', archived_at = NOW()
                WHERE id IN ({placeholders})
            """)
            
            result = await self.db_session.execute(sql_query)
            await self.db_session.commit()
            
            deleted_count = result.rowcount
            
            logger.info(
                "Embeddings deleted from PostgreSQL",
                deleted_count=deleted_count,
                embedding_ids=embedding_ids
            )
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error(
                "Failed to delete embeddings from PostgreSQL",
                error=str(e),
                embedding_ids=embedding_ids
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"PostgreSQL deletion failed: {str(e)}") from e
    
    async def update_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Update embeddings in PostgreSQL."""
        try:
            updated_ids = []
            
            for embedding in embeddings:
                # Validate embedding
                if not embedding.embedding_vector or len(embedding.embedding_vector) != self.embedding_dimension:
                    logger.warning(
                        "Invalid embedding dimension for update",
                        embedding_id=str(embedding.id),
                        expected=self.embedding_dimension,
                        actual=len(embedding.embedding_vector) if embedding.embedding_vector else 0
                    )
                    continue
                
                # Update in database
                from sqlalchemy import update, text
                
                sql_query = text(f"""
                    UPDATE {self.index_name} 
                    SET 
                        text = :text,
                        embedding_vector = :embedding_vector,
                        similarity_threshold = :similarity_threshold,
                        retrieval_score = :retrieval_score,
                        updated_at = NOW()
                    WHERE id = :embedding_id
                """)
                
                await self.db_session.execute(sql_query, {
                    "text": embedding.text,
                    "embedding_vector": embedding.embedding_vector,
                    "similarity_threshold": embedding.similarity_threshold,
                    "retrieval_score": embedding.retrieval_score,
                    "embedding_id": str(embedding.id)
                })
                
                updated_ids.append(str(embedding.id))
            
            await self.db_session.commit()
            
            logger.info(
                "Embeddings updated in PostgreSQL",
                count=len(updated_ids),
                embedding_ids=updated_ids
            )
            
            return updated_ids
            
        except Exception as e:
            logger.error(
                "Failed to update embeddings in PostgreSQL",
                error=str(e),
                embedding_count=len(embeddings)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"PostgreSQL update failed: {str(e)}") from e
    
    async def get_embedding(self, embedding_id: str) -> Optional[VectorEmbedding]:
        """Get embedding by ID from PostgreSQL."""
        try:
            from sqlalchemy import select, text
            
            sql_query = text(f"""
                SELECT * FROM {self.index_name} 
                WHERE id = :embedding_id AND status = 'active'
            """)
            
            result = await self.db_session.execute(sql_query, {"embedding_id": embedding_id})
            row = result.fetchone()
            
            if row:
                # Convert to VectorEmbedding object
                embedding = VectorEmbedding(
                    id=row.id,
                    text=row.text,
                    embedding_model=row.embedding_model,
                    embedding_dimension=row.embedding_dimension,
                    embedding_vector=row.embedding_vector,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    similarity_threshold=row.similarity_threshold,
                    retrieval_score=row.retrieval_score,
                    status=row.status,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                
                logger.info(
                    "Embedding retrieved from PostgreSQL",
                    embedding_id=embedding_id
                )
                
                return embedding
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to get embedding from PostgreSQL",
                error=str(e),
                embedding_id=embedding_id
            )
            return None
    
    async def list_embeddings(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorEmbedding]:
        """List embeddings from PostgreSQL."""
        try:
            from sqlalchemy import select, text
            
            # Build base query
            sql_query = text(f"""
                SELECT * FROM {self.index_name} 
                WHERE status = 'active'
            """)
            
            # Add filters
            if filters:
                if "source_type" in filters:
                    sql_query = text(f"""
                        SELECT * FROM {self.index_name} 
                        WHERE status = 'active' AND source_type = :source_type
                    """)
                
                if "embedding_model" in filters:
                    sql_query = text(f"""
                        SELECT * FROM {self.index_name} 
                        WHERE status = 'active' AND embedding_model = :embedding_model
                    """)
            
            # Add ordering and pagination
            sql_query = text(f"""
                {sql_query}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = await self.db_session.execute(sql_query, {
                "limit": limit,
                "offset": offset,
                **{k: v for k, v in (filters or {}).items() if k in ["source_type", "embedding_model"]}
            })
            
            rows = result.fetchall()
            
            # Convert to VectorEmbedding objects
            embeddings = []
            for row in rows:
                embedding = VectorEmbedding(
                    id=row.id,
                    text=row.text,
                    embedding_model=row.embedding_model,
                    embedding_dimension=row.embedding_dimension,
                    embedding_vector=row.embedding_vector,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    similarity_threshold=row.similarity_threshold,
                    retrieval_score=row.retrieval_score,
                    status=row.status,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                embeddings.append(embedding)
            
            logger.info(
                "Embeddings listed from PostgreSQL",
                count=len(embeddings),
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "Failed to list embeddings from PostgreSQL",
                error=str(e),
                limit=limit,
                offset=offset,
                filters=filters
            )
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get PostgreSQL vector store statistics."""
        try:
            from sqlalchemy import select, text, func
            
            # Get basic stats
            sql_query = text(f"""
                SELECT 
                    COUNT(*) as total_embeddings,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_embeddings,
                    COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived_embeddings,
                    AVG(similarity_threshold) as avg_similarity_threshold,
                    AVG(retrieval_score) as avg_retrieval_score
                FROM {self.index_name}
            """)
            
            result = await self.db_session.execute(sql_query)
            row = result.fetchone()
            
            stats = {
                "backend_type": "postgresql",
                "index_name": self.index_name,
                "embedding_dimension": self.embedding_dimension,
                "total_embeddings": row.total_embeddings if row else 0,
                "active_embeddings": row.active_embeddings if row else 0,
                "archived_embeddings": row.archived_embeddings if row else 0,
                "avg_similarity_threshold": float(row.avg_similarity_threshold) if row and row.avg_similarity_threshold else 0.0,
                "avg_retrieval_score": float(row.avg_retrieval_score) if row and row.avg_retrieval_score else 0.0
            }
            
            logger.info(
                "PostgreSQL vector store stats retrieved",
                stats=stats
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "Failed to get PostgreSQL vector store stats",
                error=str(e)
            )
            return {
                "backend_type": "postgresql",
                "index_name": self.index_name,
                "error": str(e)
            }


class PineconeVectorStore(VectorStoreBackend):
    """
    Pinecone vector store implementation.
    """
    
    def __init__(self, api_key: str, index_name: str = "codx-vectors"):
        """Initialize Pinecone vector store."""
        self.api_key = api_key
        self.index_name = index_name
        self.embedding_dimension = 1536
        self.pinecone_client = None
        
        # Import Pinecone lazily
        try:
            import pinecone
            self.pinecone_client = pinecone.Pinecone(api_key=api_key)
        except ImportError:
            logger.warning("Pinecone not available, falling back to mock implementation")
    
    async def add_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Add embeddings to Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return []
        
        try:
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Prepare vectors for upsert
            vectors = []
            embedding_ids = []
            
            for embedding in embeddings:
                if embedding.embedding_vector and len(embedding.embedding_vector) == self.embedding_dimension:
                    vectors.append({
                        "id": str(embedding.id),
                        "values": embedding.embedding_vector,
                        "metadata": {
                            "text": embedding.text,
                            "source_type": embedding.source_type,
                            "source_id": str(embedding.source_id) if embedding.source_id else None,
                            "similarity_threshold": embedding.similarity_threshold,
                            "retrieval_score": embedding.retrieval_score,
                            "status": embedding.status,
                            "created_at": embedding.created_at.isoformat() if embedding.created_at else None,
                            "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None
                        }
                    })
                    embedding_ids.append(str(embedding.id))
            
            # Upsert vectors
            index.upsert(vectors=vectors)
            
            logger.info(
                "Embeddings added to Pinecone",
                count=len(embedding_ids),
                embedding_ids=embedding_ids
            )
            
            return embedding_ids
            
        except Exception as e:
            logger.error(
                "Failed to add embeddings to Pinecone",
                error=str(e),
                embedding_count=len(embeddings)
            )
            raise BaseLayerError(f"Pinecone embedding addition failed: {str(e)}") from e
    
    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings in Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return []
        
        try:
            # Validate query vector
            if len(query_vector) != self.embedding_dimension:
                raise BaseLayerError(f"Query vector dimension mismatch: expected {self.embedding_dimension}, got {len(query_vector)}")
            
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Query Pinecone
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )
            
            # Format results
            formatted_results = []
            for match in results.matches:
                similarity = match.score
                if similarity >= threshold:
                    formatted_results.append({
                        "embedding_id": match.id,
                        "text": match.metadata.get("text", ""),
                        "similarity": similarity,
                        "distance": 1.0 - similarity,
                        "source_type": match.metadata.get("source_type", ""),
                        "source_id": match.metadata.get("source_id"),
                        "metadata": {
                            "similarity_threshold": match.metadata.get("similarity_threshold", 0.0),
                            "retrieval_score": match.metadata.get("retrieval_score", 0.0),
                            "status": match.metadata.get("status", "active"),
                            "created_at": match.metadata.get("created_at"),
                            "updated_at": match.metadata.get("updated_at")
                        }
                    })
            
            logger.info(
                "Pinecone similarity search completed",
                query_dimension=len(query_vector),
                results_count=len(formatted_results),
                threshold=threshold,
                top_k=top_k
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(
                "Pinecone similarity search failed",
                error=str(e),
                query_dimension=len(query_vector),
                top_k=top_k,
                threshold=threshold
            )
            raise BaseLayerError(f"Pinecone search failed: {str(e)}") from e
    
    async def delete_embeddings(self, embedding_ids: List[str]) -> bool:
        """Delete embeddings from Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return False
        
        try:
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Delete vectors
            index.delete(ids=embedding_ids)
            
            logger.info(
                "Embeddings deleted from Pinecone",
                count=len(embedding_ids),
                embedding_ids=embedding_ids
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete embeddings from Pinecone",
                error=str(e),
                embedding_ids=embedding_ids
            )
            raise BaseLayerError(f"Pinecone deletion failed: {str(e)}") from e
    
    async def update_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Update embeddings in Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return []
        
        try:
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Prepare vectors for update
            vectors = []
            updated_ids = []
            
            for embedding in embeddings:
                if embedding.embedding_vector and len(embedding.embedding_vector) == self.embedding_dimension:
                    vectors.append({
                        "id": str(embedding.id),
                        "values": embedding.embedding_vector,
                        "metadata": {
                            "text": embedding.text,
                            "source_type": embedding.source_type,
                            "source_id": str(embedding.source_id) if embedding.source_id else None,
                            "similarity_threshold": embedding.similarity_threshold,
                            "retrieval_score": embedding.retrieval_score,
                            "status": embedding.status,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    })
                    updated_ids.append(str(embedding.id))
            
            # Upsert vectors
            index.upsert(vectors=vectors)
            
            logger.info(
                "Embeddings updated in Pinecone",
                count=len(updated_ids),
                embedding_ids=updated_ids
            )
            
            return updated_ids
            
        except Exception as e:
            logger.error(
                "Failed to update embeddings in Pinecone",
                error=str(e),
                embedding_count=len(embeddings)
            )
            raise BaseLayerError(f"Pinecone update failed: {str(e)}") from e
    
    async def get_embedding(self, embedding_id: str) -> Optional[VectorEmbedding]:
        """Get embedding by ID from Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return None
        
        try:
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Fetch vector by ID
            result = index.fetch(ids=[embedding_id])
            
            if result.vectors:
                vector_data = result.vectors[0]
                
                embedding = VectorEmbedding(
                    id=uuid.UUID(vector_data.id),
                    text=vector_data.metadata.get("text", ""),
                    embedding_model=vector_data.metadata.get("embedding_model", "text-embedding-ada-002"),
                    embedding_dimension=len(vector_data.values),
                    embedding_vector=vector_data.values,
                    source_type=vector_data.metadata.get("source_type", ""),
                    source_id=vector_data.metadata.get("source_id"),
                    similarity_threshold=vector_data.metadata.get("similarity_threshold", 0.0),
                    retrieval_score=vector_data.metadata.get("retrieval_score", 0.0),
                    status=vector_data.metadata.get("status", "active"),
                    created_at=vector_data.metadata.get("created_at"),
                    updated_at=vector_data.metadata.get("updated_at")
                )
                
                logger.info(
                    "Embedding retrieved from Pinecone",
                    embedding_id=embedding_id
                )
                
                return embedding
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to get embedding from Pinecone",
                error=str(e),
                embedding_id=embedding_id
            )
            return None
    
    async def list_embeddings(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorEmbedding]:
        """List embeddings from Pinecone."""
        if not self.pinecone_client:
            logger.warning("Pinecone client not available")
            return []
        
        try:
            # Get index
            index = self.pinecone_client.Index(self.index_name)
            
            # Query all vectors (simplified)
            result = index.query(
                vector=[0.0] * self.embedding_dimension,  # Dummy vector to get all
                top_k=limit + offset,
                include_metadata=True
            )
            
            # Apply filters and pagination
            embeddings = []
            for i, match in enumerate(result.matches):
                if i >= offset:
                    # Apply filters
                    metadata = match.metadata
                    
                    if filters:
                        if "source_type" in filters and metadata.get("source_type") != filters["source_type"]:
                            continue
                        
                        if "embedding_model" in filters and metadata.get("embedding_model") != filters["embedding_model"]:
                            continue
                    
                    embedding = VectorEmbedding(
                        id=uuid.UUID(match.id),
                        text=metadata.get("text", ""),
                        embedding_model=metadata.get("embedding_model", "text-embedding-ada-002"),
                        embedding_dimension=len(match.values),
                        embedding_vector=match.values,
                        source_type=metadata.get("source_type", ""),
                        source_id=metadata.get("source_id"),
                        similarity_threshold=metadata.get("similarity_threshold", 0.0),
                        retrieval_score=metadata.get("retrieval_score", 0.0),
                        status=metadata.get("status", "active"),
                        created_at=metadata.get("created_at"),
                        updated_at=metadata.get("updated_at")
                    )
                    
                    embeddings.append(embedding)
                    
                    if len(embeddings) >= limit:
                        break
            
            logger.info(
                "Embeddings listed from Pinecone",
                count=len(embeddings),
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "Failed to list embeddings from Pinecone",
                error=str(e),
                limit=limit,
                offset=offset,
                filters=filters
            )
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Pinecone vector store statistics."""
        if not self.pinecone_client:
            return {
                "backend_type": "pinecone",
                "index_name": self.index_name,
                "error": "Pinecone client not available"
            }
        
        try:
            # Get index stats
            index = self.pinecone_client.Index(self.index_name)
            stats = index.describe_index_stats()
            
            return {
                "backend_type": "pinecone",
                "index_name": self.index_name,
                "embedding_dimension": self.embedding_dimension,
                "vector_count": stats.dimension,
                "index_fullness": stats.index_fullness,
                "total_vector_count": stats.total_vector_count
            }
            
        except Exception as e:
            logger.error(
                "Failed to get Pinecone vector store stats",
                error=str(e)
            )
            return {
                "backend_type": "pinecone",
                "index_name": self.index_name,
                "error": str(e)
            }


class VectorStore:
    """
    Main vector store interface for CODX knowledge engine.
    
    Provides unified interface for multiple vector store
    backends with automatic backend selection.
    """
    
    def __init__(self, db_session, backend_type: VectorStoreType = VectorStoreType.POSTGRESQL, **backend_config):
        """Initialize vector store."""
        self.db_session = db_session
        self.backend_type = backend_type
        self.backend_config = backend_config
        self.backend = self._create_backend(backend_type, **backend_config)
        
        logger.info(
            "Vector store initialized",
            backend_type=backend_type,
            config=backend_config
        )
    
    def _create_backend(self, backend_type: VectorStoreType, **config) -> VectorStoreBackend:
        """Create vector store backend."""
        if backend_type == VectorStoreType.POSTGRESQL:
            return PostgreSQLVectorStore(self.db_session, **config)
        elif backend_type == VectorStoreType.PINECONE:
            api_key = config.get("api_key")
            index_name = config.get("index_name", "codx-vectors")
            return PineconeVectorStore(api_key=api_key, index_name=index_name)
        else:
            raise BaseLayerError(f"Unsupported vector store backend: {backend_type}")
    
    async def add_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Add embeddings to vector store."""
        return await self.backend.add_embeddings(embeddings)
    
    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings."""
        return await self.backend.search_similar(query_vector, top_k, threshold)
    
    async def delete_embeddings(self, embedding_ids: List[str]) -> bool:
        """Delete embeddings from vector store."""
        return await self.backend.delete_embeddings(embedding_ids)
    
    async def update_embeddings(self, embeddings: List[VectorEmbedding]) -> List[str]:
        """Update embeddings in vector store."""
        return await self.backend.update_embeddings(embeddings)
    
    async def get_embedding(self, embedding_id: str) -> Optional[VectorEmbedding]:
        """Get embedding by ID."""
        return await self.backend.get_embedding(embedding_id)
    
    async def list_embeddings(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorEmbedding]:
        """List embeddings from vector store."""
        return await self.backend.list_embeddings(limit, offset, filters)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return await self.backend.get_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector store."""
        try:
            # Test basic operations
            test_vector = [0.0] * 1536  # Zero vector
            
            # Test search
            search_results = await self.search_similar(test_vector, top_k=1)
            
            # Test stats
            stats = await self.get_stats()
            
            health_status = {
                "backend_type": self.backend_type,
                "status": "healthy",
                "search_working": len(search_results) >= 0,
                "stats_available": "error" not in stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Vector store health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Vector store health check failed",
                error=str(e)
            )
            return {
                "backend_type": self.backend_type,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get backend information."""
        return {
            "backend_type": self.backend_type,
            "config": self.backend_config,
            "available_operations": [
                "add_embeddings",
                "search_similar",
                "delete_embeddings",
                "update_embeddings",
                "get_embedding",
                "list_embeddings",
                "get_stats",
                "health_check"
            ]
        }
