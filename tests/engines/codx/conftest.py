"""
CODX Test Configuration

Pytest configuration and fixtures for CODX knowledge engine tests.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from engines.codx.models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from engines.codx.models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from engines.codx.models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from engines.codx.models.vector_embedding import VectorEmbedding, EmbeddingModel, EmbeddingStatus
from engines.codx.models.schemas import (
    KnowledgeNodeCreate, KnowledgeNodeUpdate, KnowledgeNodeResponse,
    KnowledgeEdgeCreate, KnowledgeEdgeUpdate, KnowledgeEdgeResponse,
    KnowledgeGraphCreate, KnowledgeGraphUpdate, KnowledgeGraphResponse,
    VectorEmbeddingCreate, VectorEmbeddingUpdate, VectorEmbeddingResponse
)
from backend.shared.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.scalar_one_or_none = AsyncMock()
    session.scalars = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sample_knowledge_node():
    """Sample knowledge node for testing."""
    return KnowledgeNode(
        id=uuid.uuid4(),
        title="Machine Learning",
        node_type=NodeType.CONCEPT,
        content="Machine learning is a subset of artificial intelligence...",
        description="Overview of machine learning concepts",
        keywords=["AI", "ML", "algorithms", "data"],
        tags={"domain": "computer_science", "difficulty": "intermediate"},
        metadata={"source": "textbook", "chapter": 1},
        source="AI Textbook",
        author="John Doe",
        created_by="test_user",
        confidence_score=0.9,
        quality_score=0.85,
        relevance_score=0.8,
        level=1,
        path="/computer_science/machine_learning",
        access_count=10,
        update_count=2,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_knowledge_edge():
    """Sample knowledge edge for testing."""
    return KnowledgeEdge(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        target_id=uuid.uuid4(),
        edge_type=EdgeType.RELATES_TO,
        weight=0.8,
        confidence=0.9,
        strength=0.7,
        bidirectional=False,
        label="is related to",
        description="Conceptual relationship between nodes",
        properties={"relationship_strength": "strong"},
        metadata={"created_by": "test_user"},
        context="academic context",
        evidence="textbook reference",
        source="AI Textbook",
        created_by="test_user",
        status=EdgeStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        access_count=5,
        update_count=1
    )


@pytest.fixture
def sample_knowledge_graph():
    """Sample knowledge graph for testing."""
    return KnowledgeGraph(
        id=uuid.uuid4(),
        name="Computer Science Knowledge Graph",
        description="A comprehensive graph of computer science concepts",
        graph_type=GraphType.CONCEPT_GRAPH,
        status=GraphStatus.ACTIVE,
        node_count=100,
        edge_count=250,
        max_depth=5,
        average_degree=5.0,
        clustering_coefficient=0.3,
        density=0.025,
        is_connected=True,
        is_cyclic=True,
        is_directed=True,
        root_node_id=uuid.uuid4(),
        parent_graph_id=None,
        metadata={"domain": "computer_science", "created_by": "test_user"},
        configuration={"traversal_algorithm": "bfs", "ranking_strategy": "relevance"},
        tags=["computer_science", "knowledge_graph"],
        access_count=50,
        query_count=200,
        last_accessed=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        traversal_performance={"avg_response_time_ms": 150},
        query_performance={"cache_hit_rate": 0.75},
        index_performance={"index_efficiency": 0.85},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_vector_embedding():
    """Sample vector embedding for testing."""
    return VectorEmbedding(
        id=uuid.uuid4(),
        text="Machine learning is a subset of artificial intelligence",
        embedding_model="text-embedding-ada-002",
        embedding_dimension=1536,
        embedding_vector=[0.1] * 1536,  # Sample vector
        source_type="node",
        source_id=uuid.uuid4(),
        similarity_threshold=0.7,
        retrieval_score=0.85,
        status=EmbeddingStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        indexed_at=datetime.now(timezone.utc),
        metadata={"batch_id": "test_batch_001"},
        quality_metrics={"cosine_similarity": 0.85},
        processing_metadata={"processing_time_ms": 50}
    )


@pytest.fixture
def sample_knowledge_node_create():
    """Sample knowledge node creation request."""
    return KnowledgeNodeCreate(
        title="Deep Learning",
        node_type=NodeType.CONCEPT,
        content="Deep learning is a subset of machine learning...",
        description="Overview of deep learning concepts",
        keywords=["DL", "neural networks", "deep learning"],
        tags={"domain": "computer_science", "difficulty": "advanced"},
        metadata={"source": "research_paper"},
        source="Research Paper",
        author="Jane Smith",
        created_by="test_user",
        confidence_score=0.95,
        quality_score=0.9,
        relevance_score=0.85
    )


@pytest.fixture
def sample_knowledge_edge_create():
    """Sample knowledge edge creation request."""
    return KnowledgeEdgeCreate(
        source_id=str(uuid.uuid4()),
        target_id=str(uuid.uuid4()),
        edge_type=EdgeType.IS_A,
        weight=0.9,
        confidence=0.95,
        strength=0.8,
        bidirectional=False,
        label="is a type of",
        description="Hierarchical relationship",
        properties={"relationship_type": "hierarchical"},
        metadata={"created_by": "test_user"},
        context="academic context",
        evidence="definition from textbook",
        source="Textbook",
        created_by="test_user"
    )


@pytest.fixture
def sample_knowledge_graph_create():
    """Sample knowledge graph creation request."""
    return KnowledgeGraphCreate(
        name="Mathematics Knowledge Graph",
        description="A comprehensive graph of mathematical concepts",
        graph_type=GraphType.CONCEPT_GRAPH,
        root_node_id=str(uuid.uuid4()),
        metadata={"domain": "mathematics"},
        configuration={"traversal_algorithm": "dfs"},
        tags=["mathematics", "concepts"]
    )


@pytest.fixture
def sample_vector_embedding_create():
    """Sample vector embedding creation request."""
    return VectorEmbeddingCreate(
        text="Artificial intelligence is transforming technology",
        embedding_model="text-embedding-ada-002",
        embedding_dimension=1536,
        embedding_vector=[0.2] * 1536,
        source_type="document",
        source_id=str(uuid.uuid4()),
        similarity_threshold=0.75,
        retrieval_score=0.9,
        metadata={"document_id": "doc_001"},
        quality_metrics={"cosine_similarity": 0.9}
    )


@pytest.fixture
def sample_search_request():
    """Sample search request."""
    return {
        "query": "machine learning algorithms",
        "mode": "hybrid",
        "strategy": "relevance",
        "top_k": 10,
        "threshold": 0.7,
        "filters": {"node_type": "concept"},
        "preferences": {"include_metadata": True},
        "context": {"user_expertise": "intermediate"}
    }


@pytest.fixture
def sample_traversal_request():
    """Sample traversal request."""
    return {
        "start_node_id": str(uuid.uuid4()),
        "algorithm": "bfs",
        "max_depth": 3,
        "max_nodes": 50,
        "edge_types": ["relates_to", "is_a"],
        "include_metadata": True
    }


@pytest.fixture
def sample_analytics_request():
    """Sample analytics request."""
    return {
        "graph_id": str(uuid.uuid4()),
        "analysis_type": "structure",
        "include_detailed": True,
        "time_range": {"start": "2024-01-01", "end": "2024-12-31"}
    }


@pytest.fixture
def sample_batch_operation_request():
    """Sample batch operation request."""
    return {
        "operations": [
            {
                "action": "add",
                "target": "node",
                "parameters": sample_knowledge_node_create()
            },
            {
                "action": "search",
                "target": "all",
                "parameters": sample_search_request()
            }
        ],
        "use_cache": True,
        "timeout": 30000
    }


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    store = AsyncMock()
    store.add_embeddings = AsyncMock(return_value=["embedding_1", "embedding_2"])
    store.search_similar = AsyncMock(return_value=[
        {
            "embedding_id": "embedding_1",
            "text": "Machine learning",
            "similarity": 0.9,
            "distance": 0.1,
            "source_type": "node",
            "source_id": "node_1",
            "metadata": {"confidence": 0.85}
        }
    ])
    store.delete_embeddings = AsyncMock(return_value=True)
    store.update_embeddings = AsyncMock(return_value=["embedding_1"])
    store.get_embedding = AsyncMock(return_value=sample_vector_embedding())
    store.list_embeddings = AsyncMock(return_value=[sample_vector_embedding()])
    store.get_stats = AsyncMock(return_value={
        "backend_type": "postgresql",
        "total_embeddings": 100,
        "active_embeddings": 95
    })
    store.health_check = AsyncMock(return_value={
        "status": "healthy",
        "backend_type": "postgresql"
    })
    return store


@pytest.fixture
def mock_graph_traverser():
    """Mock graph traverser for testing."""
    traverser = AsyncMock()
    traverser.breadth_first_search = AsyncMock(return_value={
        "algorithm": "bfs",
        "start_node_id": "node_1",
        "traversal_order": [
            {
                "id": "node_1",
                "title": "Machine Learning",
                "node_type": "concept",
                "depth": 0,
                "metadata": {"confidence": 0.9}
            },
            {
                "id": "node_2",
                "title": "Deep Learning",
                "node_type": "concept",
                "depth": 1,
                "metadata": {"confidence": 0.85}
            }
        ],
        "node_distances": {"node_1": 0, "node_2": 1},
        "execution_time_ms": 50
    })
    traverser.depth_first_search = AsyncMock(return_value={
        "algorithm": "dfs",
        "start_node_id": "node_1",
        "traversal_order": [],
        "execution_time_ms": 45
    })
    traverser.dijkstra_shortest_path = AsyncMock(return_value={
        "algorithm": "dijkstra",
        "start_node_id": "node_1",
        "target_node_id": "node_2",
        "path": ["node_1", "node_2"],
        "distance": 2.5,
        "execution_time_ms": 75
    })
    traverser.health_check = AsyncMock(return_value={
        "status": "healthy"
    })
    return traverser


@pytest.fixture
def mock_graph_analyzer():
    """Mock graph analyzer for testing."""
    analyzer = AsyncMock()
    analyzer.analyze_graph_structure = AsyncMock(return_value={
        "graph_id": "graph_1",
        "basic_metrics": {
            "node_count": 100,
            "edge_count": 250,
            "density": 0.025,
            "is_connected": True,
            "is_cyclic": True,
            "max_depth": 5,
            "average_path_length": 3.2
        },
        "degree_analysis": {
            "average_degree": 5.0,
            "max_degree": 20,
            "min_degree": 1,
            "degree_distribution": {1: 10, 2: 15, 3: 20, 4: 25, 5: 30}
        },
        "clustering_analysis": {
            "clustering_coefficient": 0.3,
            "average_clustering": 0.3,
            "max_clustering": 0.8,
            "min_clustering": 0.1
        }
    })
    analyzer.analyze_graph_performance = AsyncMock(return_value={
        "graph_id": "graph_1",
        "traversal_performance": {"avg_response_time_ms": 150},
        "query_performance": {"cache_hit_rate": 0.75},
        "usage_metrics": {
            "access_count": 50,
            "query_count": 200,
            "last_accessed": datetime.now(timezone.utc).isoformat()
        }
    })
    analyzer.health_check = AsyncMock(return_value={
        "status": "healthy"
    })
    return analyzer


@pytest.fixture
def mock_graph_storage():
    """Mock graph storage for testing."""
    storage = AsyncMock()
    storage.save_graph = AsyncMock(return_value=sample_knowledge_graph())
    storage.save_node = AsyncMock(return_value=sample_knowledge_node())
    storage.save_edge = AsyncMock(return_value=sample_knowledge_edge())
    storage.save_nodes_batch = AsyncMock(return_value=[sample_knowledge_node()])
    storage.save_edges_batch = AsyncMock(return_value=[sample_knowledge_edge()])
    storage.get_graph = AsyncMock(return_value=sample_knowledge_graph())
    storage.get_node = AsyncMock(return_value=sample_knowledge_node())
    storage.get_edge = AsyncMock(return_value=sample_knowledge_edge())
    storage.list_graphs = AsyncMock(return_value=[sample_knowledge_graph()])
    storage.list_nodes = AsyncMock(return_value=[sample_knowledge_node()])
    storage.list_edges = AsyncMock(return_value=[sample_knowledge_edge()])
    storage.delete_graph = AsyncMock(return_value=True)
    storage.delete_node = AsyncMock(return_value=True)
    storage.delete_edge = AsyncMock(return_value=True)
    storage.search_nodes = AsyncMock(return_value=[sample_knowledge_node()])
    storage.search_edges = AsyncMock(return_value=[sample_knowledge_edge()])
    storage.get_storage_stats = AsyncMock(return_value={
        "total_operations": 100,
        "cache_hit_rate": 0.75
    })
    return storage


@pytest.fixture
def mock_query_processor():
    """Mock query processor for testing."""
    processor = AsyncMock()
    processor.process_query = AsyncMock(return_value={
        "original_query": "machine learning algorithms",
        "normalized_query": "machine learning algorithms",
        "query_type": "factual",
        "intent": "search",
        "entities": [
            {
                "text": "machine learning",
                "type": "concept",
                "confidence": 0.9,
                "start_pos": 0,
                "end_pos": 16
            },
            {
                "text": "algorithms",
                "type": "concept",
                "confidence": 0.85,
                "start_pos": 17,
                "end_pos": 26
            }
        ],
        "relationships": [],
        "keywords": ["machine", "learning", "algorithms"],
        "concepts": ["machine learning"],
        "filters": {},
        "constraints": {},
        "context": {},
        "confidence": 0.875,
        "explanation": "Query type: factual | Intent: search | Found 2 entities"
    })
    processor.health_check = AsyncMock(return_value={
        "status": "healthy"
    })
    return processor


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.expire = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value='{"entities": [], "relationships": []}')
    llm.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    return llm


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    ollama = AsyncMock()
    ollama.generate = AsyncMock(return_value={"response": "Generated response"})
    ollama.embed = AsyncMock(return_value={"embedding": [0.1] * 1536})
    return ollama


@pytest.fixture
def log_capture():
    """Capture log messages during tests."""
    import logging
    from io import StringIO
    
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    
    logger = logging.getLogger("engines.codx")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    yield log_stream
    
    logger.removeHandler(handler)


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch("builtins.open", create=True) as mock_open:
        mock_file = MagicMock()
        mock_file.read.return_value = "test content"
        mock_open.return_value.__enter__.return_value = mock_file
        yield mock_open


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external API calls."""
    import httpx
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_response.text = "Success"
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_client.return_value
        mock_client.return_value.get.return_value = mock_response
        mock_client.return_value.post.return_value = mock_response
        yield mock_client


@pytest.fixture
def sample_error_response():
    """Sample error response."""
    return {
        "error": "Test error",
        "message": "This is a test error message",
        "code": "TEST_ERROR",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "component": "test_component",
            "operation": "test_operation"
        }
    }


@pytest.fixture
def sample_success_response():
    """Sample success response."""
    return {
        "success": True,
        "message": "Operation completed successfully",
        "data": {"id": "test_id", "status": "completed"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "operation": "test_operation",
            "execution_time_ms": 100
        }
    }


@pytest.fixture
def sample_validation_response():
    """Sample validation response."""
    return {
        "valid": True,
        "errors": [],
        "warnings": ["Minor warning"],
        "metadata": {
            "validation_rules": ["rule1", "rule2"],
            "validated_at": datetime.now(timezone.utc).isoformat()
        }
    }


@pytest.fixture
def sample_pagination_params():
    """Sample pagination parameters."""
    return {
        "page": 1,
        "page_size": 20,
        "offset": 0,
        "limit": 20,
        "sort_by": "created_at",
        "sort_order": "desc"
    }


@pytest.fixture
def sample_filter_params():
    """Sample filter parameters."""
    return {
        "node_types": ["concept", "entity"],
        "status": "active",
        "created_after": "2024-01-01",
        "created_before": "2024-12-31",
        "confidence_min": 0.7,
        "quality_min": 0.6,
        "keywords": ["machine", "learning"],
        "tags": {"domain": "computer_science"}
    }
