"""
Tests for CODX Vector Components

Tests for vector store, embedding generation, and similarity search.
"""

import pytest
import uuid
import numpy as np
from unittest.mock import AsyncMock, patch

from engines.codx.vector.vector_store import (
    VectorStore, PostgreSQLVectorStore, PineconeVectorStore,
    VectorStoreBackend
)
from engines.codx.vector.embedding_generator import (
    EmbeddingGenerator, OpenAIEmbeddingProvider, SentenceTransformersProvider,
    create_embedding_generator, calculate_similarity, calculate_euclidean_distance
)
from engines.codx.vector.similarity_search import (
    SimilaritySearch, SearchMode, RankingStrategy, SearchResult, RetrievalResult
)
from engines.codx.models.vector_embedding import VectorEmbedding, EmbeddingStatus, VectorStoreType
from .conftest import (
    mock_db_session, sample_vector_embedding, sample_vector_embedding_create,
    mock_vector_store, mock_llm_client, mock_redis_client
)


class TestVectorStore:
    """Test VectorStore class."""
    
    @pytest.mark.asyncio
    async def test_vector_store_initialization(self, mock_db_session):
        """Test VectorStore initialization."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        
        assert vector_store.db_session == mock_db_session
        assert vector_store.backend_type == VectorStoreType.POSTGRESQL
        assert vector_store.backend is not None
        assert isinstance(vector_store.backend, PostgreSQLVectorStore)
    
    @pytest.mark.asyncio
    async def test_vector_store_pinecone_initialization(self, mock_db_session):
        """Test VectorStore with Pinecone backend."""
        config = {"api_key": "test_key", "index_name": "test-index"}
        vector_store = VectorStore(mock_db_session, VectorStoreType.PINECONE, **config)
        
        assert vector_store.db_session == mock_db_session
        assert vector_store.backend_type == VectorStoreType.PINECONE
        assert vector_store.backend is not None
        assert isinstance(vector_store.backend, PineconeVectorStore)
    
    @pytest.mark.asyncio
    async def test_add_embeddings(self, mock_db_session, sample_vector_embedding):
        """Test adding embeddings to vector store."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        
        # Mock the backend
        vector_store.backend.add_embeddings = AsyncMock(return_value=["embedding_1"])
        
        result = await vector_store.add_embeddings([sample_vector_embedding])
        
        assert result == ["embedding_1"]
        vector_store.backend.add_embeddings.assert_called_once_with([sample_vector_embedding])
    
    @pytest.mark.asyncio
    async def test_search_similar(self, mock_db_session):
        """Test searching for similar embeddings."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        query_vector = [0.1] * 1536
        
        # Mock the backend
        mock_results = [
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "metadata": {}
            }
        ]
        vector_store.backend.search_similar = AsyncMock(return_value=mock_results)
        
        result = await vector_store.search_similar(query_vector, top_k=10, threshold=0.7)
        
        assert len(result) == 1
        assert result[0]["embedding_id"] == "embedding_1"
        assert result[0]["similarity"] == 0.9
        vector_store.backend.search_similar.assert_called_once_with(
            query_vector, top_k=10, threshold=0.7
        )
    
    @pytest.mark.asyncio
    async def test_delete_embeddings(self, mock_db_session):
        """Test deleting embeddings from vector store."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        embedding_ids = ["embedding_1", "embedding_2"]
        
        # Mock the backend
        vector_store.backend.delete_embeddings = AsyncMock(return_value=True)
        
        result = await vector_store.delete_embeddings(embedding_ids)
        
        assert result is True
        vector_store.backend.delete_embeddings.assert_called_once_with(embedding_ids)
    
    @pytest.mark.asyncio
    async def test_get_stats(self, mock_db_session):
        """Test getting vector store statistics."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        
        # Mock the backend
        mock_stats = {
            "backend_type": "postgresql",
            "total_embeddings": 100,
            "active_embeddings": 95
        }
        vector_store.backend.get_stats = AsyncMock(return_value=mock_stats)
        
        result = await vector_store.get_stats()
        
        assert result["backend_type"] == "postgresql"
        assert result["total_embeddings"] == 100
        vector_store.backend.get_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_db_session):
        """Test vector store health check."""
        vector_store = VectorStore(mock_db_session, VectorStoreType.POSTGRESQL)
        
        # Mock the backend
        mock_health = {"status": "healthy", "backend_type": "postgresql"}
        vector_store.backend.health_check = AsyncMock(return_value=mock_health)
        
        result = await vector_store.health_check()
        
        assert result["status"] == "healthy"
        assert result["backend_type"] == "postgresql"
        vector_store.backend.health_check.assert_called_once()


class TestPostgreSQLVectorStore:
    """Test PostgreSQLVectorStore class."""
    
    @pytest.mark.asyncio
    async def test_postgresql_initialization(self, mock_db_session):
        """Test PostgreSQL vector store initialization."""
        store = PostgreSQLVectorStore(mock_db_session, "test_vectors")
        
        assert store.db_session == mock_db_session
        assert store.index_name == "test_vectors"
        assert store.embedding_dimension == 1536
    
    @pytest.mark.asyncio
    async def test_add_embeddings(self, mock_db_session, sample_vector_embedding):
        """Test adding embeddings to PostgreSQL."""
        store = PostgreSQLVectorStore(mock_db_session)
        
        # Mock database operations
        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        result = await store.add_embeddings([sample_vector_embedding])
        
        assert len(result) == 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_similar(self, mock_db_session):
        """Test similarity search in PostgreSQL."""
        store = PostgreSQLVectorStore(mock_db_session)
        query_vector = [0.1] * 1536
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [
            (
                uuid.uuid4(),  # id
                "Machine learning",  # text
                0.9,  # distance
                "node",  # source_type
                uuid.uuid4(),  # source_id
                0.85,  # similarity_threshold
                0.9,  # retrieval_score
                "active",  # status
                datetime.now(),  # created_at
                datetime.now()   # updated_at
            )
        ]
        
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        result = await store.search_similar(query_vector, top_k=10, threshold=0.7)
        
        assert len(result) == 1
        assert result[0]["similarity"] == 0.1  # 1 - distance
        assert result[0]["text"] == "Machine learning"
    
    @pytest.mark.asyncio
    async def test_delete_embeddings(self, mock_db_session):
        """Test deleting embeddings from PostgreSQL."""
        store = PostgreSQLVectorStore(mock_db_session)
        embedding_ids = ["embedding_1", "embedding_2"]
        
        # Mock database operations
        mock_db_session.execute = AsyncMock(return_value=AsyncMock(rowcount=2))
        mock_db_session.commit = AsyncMock()
        
        result = await store.delete_embeddings(embedding_ids)
        
        assert result is True
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_embedding(self, mock_db_session, sample_vector_embedding):
        """Test getting embedding by ID from PostgreSQL."""
        store = PostgreSQLVectorStore(mock_db_session)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_vector_embedding
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        result = await store.get_embedding(str(sample_vector_embedding.id))
        
        assert result == sample_vector_embedding
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_embeddings(self, mock_db_session, sample_vector_embedding):
        """Test listing embeddings from PostgreSQL."""
        store = PostgreSQLVectorStore(mock_db_session)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [sample_vector_embedding]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        result = await store.list_embeddings(limit=10, offset=0)
        
        assert len(result) == 1
        assert result[0] == sample_vector_embedding
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_stats(self, mock_db_session):
        """Test getting PostgreSQL statistics."""
        store = PostgreSQLVectorStore(mock_db_session)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = (
            100,  # total_embeddings
            95,  # active_embeddings
            5,  # archived_embeddings
            0.8,  # avg_similarity_threshold
            0.85,  # avg_retrieval_score
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        result = await store.get_stats()
        
        assert result["backend_type"] == "postgresql"
        assert result["total_embeddings"] == 100
        assert result["active_embeddings"] == 95
        assert result["avg_similarity_threshold"] == 0.8


class TestPineconeVectorStore:
    """Test PineconeVectorStore class."""
    
    @pytest.mark.asyncio
    async def test_pinecone_initialization(self):
        """Test Pinecone vector store initialization."""
        with patch('engines.codx.vector.vector_store.pinecone') as mock_pinecone:
            mock_pinecone.Pinecone.return_value = AsyncMock()
            
            store = PineconeVectorStore(api_key="test_key", index_name="test-index")
            
            assert store.api_key == "test_key"
            assert store.index_name == "test-index"
            assert store.embedding_dimension == 1536
            mock_pinecone.Pinecone.assert_called_once_with(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_add_embeddings(self):
        """Test adding embeddings to Pinecone."""
        with patch('engines.codx.vector.vector_store.pinecone') as mock_pinecone:
            mock_pinecone.Pinecone.return_value = AsyncMock()
            mock_index = AsyncMock()
            mock_pinecone.Pinecone.return_value.Index.return_value = mock_index
            
            store = PineconeVectorStore(api_key="test_key")
            
            embedding = VectorEmbedding(
                text="Test embedding",
                embedding_model="text-embedding-ada-002",
                embedding_dimension=1536,
                embedding_vector=[0.1] * 1536,
                source_type="node",
                source_id=uuid.uuid4()
            )
            
            result = await store.add_embeddings([embedding])
            
            assert len(result) == 1
            mock_index.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_similar(self):
        """Test similarity search in Pinecone."""
        with patch('engines.codx.vector.vector_store.pinecone') as mock_pinecone:
            mock_pinecone.Pinecone.return_value = AsyncMock()
            mock_index = AsyncMock()
            mock_index.query.return_value = AsyncMock(
                matches=[
                    AsyncMock(
                        id="embedding_1",
                        score=0.9,
                        metadata={"text": "Machine learning", "source_type": "node"}
                    )
                ]
            )
            mock_pinecone.Pinecone.return_value.Index.return_value = mock_index
            
            store = PineconeVectorStore(api_key="test_key")
            query_vector = [0.1] * 1536
            
            result = await store.search_similar(query_vector, top_k=10, threshold=0.7)
            
            assert len(result) == 1
            assert result[0]["embedding_id"] == "embedding_1"
            assert result[0]["similarity"] == 0.9
            mock_index.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_embeddings(self):
        """Test deleting embeddings from Pinecone."""
        with patch('engines.codx.vector.vector_store.pinecone') as mock_pinecone:
            mock_pinecone.Pinecone.return_value = AsyncMock()
            mock_index = AsyncMock()
            mock_pinecone.Pinecone.return_value.Index.return_value = mock_index
            
            store = PineconeVectorStore(api_key="test_key")
            embedding_ids = ["embedding_1", "embedding_2"]
            
            result = await store.delete_embeddings(embedding_ids)
            
            assert result is True
            mock_index.delete.assert_called_once_with(ids=embedding_ids)


class TestEmbeddingGenerator:
    """Test EmbeddingGenerator class."""
    
    @pytest.mark.asyncio
    async def test_embedding_generator_initialization(self):
        """Test embedding generator initialization."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider.return_value = AsyncMock()
            
            generator = EmbeddingGenerator(mock_provider.return_value)
            
            assert generator.provider == mock_provider.return_value
            assert generator.embedding_cache == {}
            assert generator.cache_ttl == 3600
    
    @pytest.mark.asyncio
    async def test_generate_embedding(self):
        """Test generating a single embedding."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider_instance = AsyncMock()
            mock_provider.return_value = mock_provider_instance
            mock_provider_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            generator = EmbeddingGenerator(mock_provider_instance)
            
            result = await generator.generate_embedding("Test text")
            
            assert len(result) == 1536
            assert result[0] == 0.1
            mock_provider_instance.generate_embedding.assert_called_once_with("Test text")
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self):
        """Test generating multiple embeddings."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider_instance = AsyncMock()
            mock_provider.return_value = mock_provider_instance
            mock_provider_instance.generate_embeddings_batch = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
            
            generator = EmbeddingGenerator(mock_provider_instance)
            
            texts = ["Text 1", "Text 2"]
            result = await generator.generate_embeddings_batch(texts)
            
            assert len(result) == 2
            assert len(result[0]) == 1536
            assert len(result[1]) == 1536
            mock_provider_instance.generate_embeddings_batch.assert_called_once_with(texts)
    
    @pytest.mark.asyncio
    async def test_generate_embedding_with_cache(self):
        """Test embedding generation with caching."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider_instance = AsyncMock()
            mock_provider.return_value = mock_provider_instance
            mock_provider_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            generator = EmbeddingGenerator(mock_provider_instance)
            
            # First call
            result1 = await generator.generate_embedding("Test text", use_cache=True)
            
            # Second call (should use cache)
            result2 = await generator.generate_embedding("Test text", use_cache=True)
            
            assert result1 == result2
            assert len(generator.embedding_cache) == 1
            # Provider should only be called once due to caching
            mock_provider_instance.generate_embedding.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_generation_stats(self):
        """Test getting generation statistics."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider_instance = AsyncMock()
            mock_provider.return_value = mock_provider_instance
            mock_provider_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            generator = EmbeddingGenerator(mock_provider_instance)
            
            # Generate some embeddings
            await generator.generate_embedding("Test 1")
            await generator.generate_embedding("Test 2")
            
            stats = generator.get_generation_stats()
            
            assert stats["total_embeddings"] == 2
            assert stats["cache_misses"] == 2
            assert stats["cache_size"] == 2
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test embedding generator health check."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider_instance = AsyncMock()
            mock_provider.return_value = mock_provider_instance
            mock_provider_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            generator = EmbeddingGenerator(mock_provider_instance)
            
            health = await generator.health_check()
            
            assert health["status"] == "healthy"
            assert health["test_embedding_generated"] is True


class TestOpenAIEmbeddingProvider:
    """Test OpenAIEmbeddingProvider class."""
    
    @pytest.mark.asyncio
    async def test_openai_initialization(self):
        """Test OpenAI provider initialization."""
        with patch('engines.codx.vector.embedding_generator.openai') as mock_openai:
            mock_openai.OpenAI.return_value = AsyncMock()
            
            provider = OpenAIEmbeddingProvider(api_key="test_key", model="text-embedding-ada-002")
            
            assert provider.api_key == "test_key"
            assert provider.model == "text-embedding-ada-002"
            assert provider.client is not None
            mock_openai.OpenAI.assert_called_once_with(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_generate_embedding(self):
        """Test generating embedding with OpenAI."""
        with patch('engines.codx.vector.embedding_generator.openai') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.embeddings.create.return_value = AsyncMock(
                data=[AsyncMock(embedding=[0.1] * 1536)]
            )
            
            provider = OpenAIEmbeddingProvider(api_key="test_key")
            
            result = await provider.generate_embedding("Test text")
            
            assert len(result) == 1536
            assert result[0] == 0.1
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-ada-002",
                input="Test text"
            )
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self):
        """Test generating multiple embeddings with OpenAI."""
        with patch('engines.codx.vector.embedding_generator.openai') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_client.embeddings.create.return_value = AsyncMock(
                data=[
                    AsyncMock(embedding=[0.1] * 1536),
                    AsyncMock(embedding=[0.2] * 1536)
                ]
            )
            
            provider = OpenAIEmbeddingProvider(api_key="test_key")
            
            texts = ["Text 1", "Text 2"]
            result = await provider.generate_embeddings_batch(texts)
            
            assert len(result) == 2
            assert len(result[0]) == 1536
            assert len(result[1]) == 1536
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-ada-002",
                input=texts
            )
    
    def test_get_model_info(self):
        """Test getting model information."""
        with patch('engines.codx.vector.embedding_generator.openai') as mock_openai:
            mock_openai.OpenAI.return_value = AsyncMock()
            
            provider = OpenAIEmbeddingProvider(api_key="test_key")
            
            info = provider.get_model_info()
            
            assert info["provider"] == "openai"
            assert info["model"] == "text-embedding-ada-002"
            assert info["dimension"] == 1536
            assert info["max_tokens"] == 8191
            assert info["batch_size"] == 100


class TestSentenceTransformersProvider:
    """Test SentenceTransformersProvider class."""
    
    @pytest.mark.asyncio
    async def test_sentence_transformers_initialization(self):
        """Test Sentence Transformers provider initialization."""
        with patch('engines.codx.vector.embedding_generator.SentenceTransformer') as mock_st:
            mock_st.return_value = AsyncMock()
            mock_st.return_value.tokenizer = AsyncMock()
            
            provider = SentenceTransformersProvider(model_name="all-MiniLM-L6-v2")
            
            assert provider.model_name == "all-MiniLM-L6-v2"
            assert provider.model is not None
            mock_st.assert_called_once_with("all-MiniLM-L6-v2")
    
    @pytest.mark.asyncio
    async def test_generate_embedding(self):
        """Test generating embedding with Sentence Transformers."""
        with patch('engines.codx.vector.embedding_generator.SentenceTransformer') as mock_st:
            mock_model = AsyncMock()
            mock_model.encode.return_value = np.array([0.1] * 384)
            mock_model.encode.return_value.tolist.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            provider = SentenceTransformersProvider()
            
            result = await provider.generate_embedding("Test text")
            
            assert len(result) == 384
            assert result[0] == 0.1
            mock_model.encode.assert_called_once_with("Test text")
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self):
        """Test generating multiple embeddings with Sentence Transformers."""
        with patch('engines.codx.vector.embedding_generator.SentenceTransformer') as mock_st:
            mock_model = AsyncMock()
            mock_model.encode.return_value = np.array([
                [0.1] * 384,
                [0.2] * 384
            ])
            mock_model.encode.return_value.tolist.return_value = [
                [0.1] * 384,
                [0.2] * 384
            ]
            mock_st.return_value = mock_model
            
            provider = SentenceTransformersProvider()
            
            texts = ["Text 1", "Text 2"]
            result = await provider.generate_embeddings_batch(texts)
            
            assert len(result) == 2
            assert len(result[0]) == 384
            assert len(result[1]) == 384
            mock_model.encode.assert_called_once_with(texts)
    
    def test_get_model_info(self):
        """Test getting model information."""
        with patch('engines.codx.vector.embedding_generator.SentenceTransformer') as mock_st:
            mock_model = AsyncMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            provider = SentenceTransformersProvider()
            
            info = provider.get_model_info()
            
            assert info["provider"] == "sentence_transformers"
            assert info["model"] == "all-MiniLM-L6-v2"
            assert info["dimension"] == 384
            assert info["batch_size"] == 32


class TestSimilaritySearch:
    """Test SimilaritySearch class."""
    
    @pytest.mark.asyncio
    async def test_similarity_search_initialization(self, mock_vector_store):
        """Test similarity search initialization."""
        search = SimilaritySearch(mock_vector_store)
        
        assert search.vector_store == mock_vector_store
        assert search.default_mode == SearchMode.SEMANTIC
        assert search.default_strategy == RankingStrategy.SIMILARITY
        assert search.search_cache == {}
    
    @pytest.mark.asyncio
    async def test_search(self, mock_vector_store):
        """Test similarity search."""
        # Mock vector store
        mock_results = [
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "metadata": {}
            }
        ]
        mock_vector_store.search_similar = AsyncMock(return_value=mock_results)
        
        search = SimilaritySearch(mock_vector_store)
        
        result = await search.search(
            query="machine learning",
            mode=SearchMode.SEMANTIC,
            top_k=10,
            threshold=0.7
        )
        
        assert len(result) == 1
        assert result[0].embedding_id == "embedding_1"
        assert result[0].similarity == 0.9
        assert result[0].item_type == "embedding"
        mock_vector_store.search_similar.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_similar_embeddings(self, mock_vector_store):
        """Test searching for similar embeddings."""
        # Mock vector store
        mock_results = [
            {
                "embedding_id": "embedding_2",
                "text": "Deep learning",
                "similarity": 0.8,
                "distance": 0.2,
                "source_type": "node",
                "metadata": {}
            }
        ]
        mock_vector_store.search_similar = AsyncMock(return_value=mock_results)
        
        search = SimilaritySearch(mock_vector_store)
        
        result = await search.search_similar(
            embedding_id="embedding_1",
            top_k=10,
            threshold=0.7
        )
        
        assert len(result) == 1
        assert result[0].embedding_id == "embedding_2"
        assert result[0].similarity == 0.8
        mock_vector_store.search_similar.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_by_source(self, mock_vector_store):
        """Test searching by source type."""
        # Mock vector store
        mock_embeddings = [sample_vector_embedding]
        mock_vector_store.list_embeddings = AsyncMock(return_value=mock_embeddings)
        
        search = SimilaritySearch(mock_vector_store)
        
        result = await search.search_by_source(
            source_type="node",
            top_k=10
        )
        
        assert len(result) == 1
        assert result[0].item_id == str(sample_vector_embedding.id)
        assert result[0].source_type == "node"
        mock_vector_store.list_embeddings.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_search_stats(self, mock_vector_store):
        """Test getting search statistics."""
        search = SimilaritySearch(mock_vector_store)
        
        # Simulate some searches
        search.search_stats["total_searches"] = 10
        search.search_stats["successful_searches"] = 8
        search.search_stats["failed_searches"] = 2
        search.search_stats["cache_hits"] = 3
        search.search_stats["cache_misses"] = 7
        
        stats = search.get_search_stats()
        
        assert stats["total_searches"] == 10
        assert stats["successful_searches"] == 8
        assert stats["failed_searches"] == 2
        assert stats["success_rate"] == 0.8
        assert stats["cache_hit_rate"] == 0.3
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_vector_store):
        """Test similarity search health check."""
        # Mock vector store
        mock_vector_store.search_similar = AsyncMock(return_value=[])
        mock_vector_store.health_check = AsyncMock(return_value={"status": "healthy"})
        
        search = SimilaritySearch(mock_vector_store)
        
        health = await search.health_check()
        
        assert health["status"] == "healthy"
        assert health["search_working"] is True
        assert health["test_results_count"] == 0


class TestEmbeddingUtilities:
    """Test embedding utility functions."""
    
    def test_create_embedding_generator_openai(self):
        """Test creating OpenAI embedding generator."""
        with patch('engines.codx.vector.embedding_generator.OpenAIEmbeddingProvider') as mock_provider:
            mock_provider.return_value = AsyncMock()
            
            config = {"api_key": "test_key", "model": "text-embedding-ada-002"}
            generator = create_embedding_generator("openai", **config)
            
            assert generator is not None
            mock_provider.assert_called_once_with(api_key="test_key", model="text-embedding-ada-002")
    
    def test_create_embedding_generator_sentence_transformers(self):
        """Test creating Sentence Transformers embedding generator."""
        with patch('engines.codx.vector.embedding_generator.SentenceTransformersProvider') as mock_provider:
            mock_provider.return_value = AsyncMock()
            
            config = {"model_name": "all-MiniLM-L6-v2"}
            generator = create_embedding_generator("sentence_transformers", **config)
            
            assert generator is not None
            mock_provider.assert_called_once_with(model_name="all-MiniLM-L6-v2")
    
    def test_create_embedding_generator_invalid(self):
        """Test creating embedding generator with invalid provider."""
        with pytest.raises(BaseLayerError):
            create_embedding_generator("invalid_provider")
    
    def test_calculate_similarity(self):
        """Test calculating cosine similarity."""
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]
        
        similarity = calculate_similarity(embedding1, embedding2)
        
        assert similarity == 0.0  # Orthogonal vectors
    
    def test_calculate_similarity_identical(self):
        """Test calculating similarity of identical vectors."""
        embedding1 = [0.5, 0.5, 0.5]
        embedding2 = [0.5, 0.5, 0.5]
        
        similarity = calculate_similarity(embedding1, embedding2)
        
        assert similarity == 1.0  # Identical vectors
    
    def test_calculate_euclidean_distance(self):
        """Test calculating Euclidean distance."""
        embedding1 = [0.0, 0.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]
        
        distance = calculate_euclidean_distance(embedding1, embedding2)
        
        assert distance == 1.0
    
    def test_calculate_euclidean_distance_identical(self):
        """Test calculating distance of identical vectors."""
        embedding1 = [0.5, 0.5, 0.5]
        embedding2 = [0.5, 0.5, 0.5]
        
        distance = calculate_euclidean_distance(embedding1, embedding2)
        
        assert distance == 0.0
    
    def test_calculate_manhattan_distance(self):
        """Test calculating Manhattan distance."""
        embedding1 = [0.0, 0.0, 0.0]
        embedding2 = [1.0, 2.0, 3.0]
        
        distance = calculate_manhattan_distance(embedding1, embedding2)
        
        assert distance == 6.0  # |0-1| + |0-2| + |0-3|
    
    def test_similarity_dimension_mismatch(self):
        """Test similarity calculation with dimension mismatch."""
        embedding1 = [0.1, 0.2]
        embedding2 = [0.1, 0.2, 0.3]
        
        with pytest.raises(BaseLayerError):
            calculate_similarity(embedding1, embedding2)
    
    def test_distance_dimension_mismatch(self):
        """Test distance calculation with dimension mismatch."""
        embedding1 = [0.1, 0.2]
        embedding2 = [0.1, 0.2, 0.3]
        
        with pytest.raises(BaseLayerError):
            calculate_euclidean_distance(embedding1, embedding2)
