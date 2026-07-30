"""
CODEX Test Configuration

Pytest configuration and fixtures for CODEX knowledge system tests.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ...models.knowledge_entry import KnowledgeEntry, KnowledgeEntryType, SourceEngine
from ...models.knowledge_link import KnowledgeLink, KnowledgeLinkType
from ...models.knowledge_snapshot import KnowledgeSnapshot
from ...api.knowledge_manager import KnowledgeManager
from ...vector.embedding_engine import EmbeddingEngine
from ...vector.vector_store import VectorStore
from ...vector.semantic_search import SemanticSearch

logger = get_logger(__name__)

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        async def get(self, key: str):
            return self.data.get(key)
        
        async def set(self, key: str, value: str, ex: int = None):
            self.data[key] = value
            return True
        
        async def incr(self, key: str):
            if key not in self.data:
                self.data[key] = 0
            self.data[key] += 1
            return self.data[key]
        
        async def lpush(self, key: str, *values):
            if key not in self.data:
                self.data[key] = []
            self.data[key].extend(values)
            return len(self.data[key])
        
        async def expire(self, key: str, seconds: int):
            return True
        
        async def keys(self, pattern: str):
            return list(self.data.keys())
        
        async def delete(self, key: str):
            if key in self.data:
                del self.data[key]
                return True
            return False
        
        async def ttl(self, key: str):
            return 3600  # Mock TTL
        
        async def pipeline(self):
            return MockPipeline(self.data)
    
    class MockPipeline:
        def __init__(self, data):
            self.data = data
            self.operations = []
        
        def get(self, key):
            self.operations.append(('get', key))
            return self
        
        def setex(self, key, ttl, value):
            self.operations.append(('setex', key, ttl, value))
            return self
        
        def execute(self):
            results = []
            for op in self.operations:
                if op[0] == 'get':
                    results.append(self.data.get(op[1]))
                elif op[0] == 'setex':
                    self.data[op[1]] = op[3]
                    results.append(True)
            self.operations = []
            return results
    
    return MockRedis()


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    class MockOllamaClient:
        def __init__(self):
            self.model = "nomic-embed-text"
        
        async def embed(self, model: str, prompt: str):
            # Mock embedding generation
            import random
            embedding = [random.uniform(-1, 1) for _ in range(768)]
            
            class MockResponse:
                def __init__(self, embedding):
                    self.embedding = embedding
            
            return MockResponse(embedding)
    
    return MockOllamaClient()


@pytest.fixture
def embedding_engine(mock_redis_client, mock_ollama_client):
    """Create embedding engine for testing."""
    return EmbeddingEngine(
        redis_client=mock_redis_client,
        model="nomic-embed-text"
    )


@pytest.fixture
def vector_store(db_session):
    """Create vector store for testing."""
    return VectorStore(db_session)


@pytest.fixture
def semantic_search(embedding_engine, vector_store):
    """Create semantic search for testing."""
    return SemanticSearch(
        embedding_engine=embedding_engine,
        vector_store=vector_store
    )


@pytest.fixture
def knowledge_manager(db_session, mock_redis_client):
    """Create knowledge manager for testing."""
    return KnowledgeManager(db_session, mock_redis_client)


@pytest.fixture
async def sample_knowledge_entry(db_session) -> KnowledgeEntry:
    """Create sample knowledge entry for testing."""
    entry = KnowledgeEntry(
        key="test:sample_fact",
        value="This is a sample fact for testing purposes",
        entry_type=KnowledgeEntryType.FACT,
        source_engine=SourceEngine.MANUAL,
        source_agent="test_agent",
        tags=["test", "sample"],
        confidence=0.9
    )
    
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    
    return entry


@pytest.fixture
async def sample_knowledge_link(db_session, sample_knowledge_entry) -> KnowledgeLink:
    """Create sample knowledge link for testing."""
    # Create another entry to link to
    target_entry = KnowledgeEntry(
        key="test:related_fact",
        value="This is a related fact",
        entry_type=KnowledgeEntryType.FACT,
        source_engine=SourceEngine.MANUAL,
        source_agent="test_agent",
        tags=["test", "related"],
        confidence=0.8
    )
    
    db_session.add(target_entry)
    await db_session.commit()
    await db_session.refresh(target_entry)
    
    # Create link
    link = KnowledgeLink(
        source_entry_id=sample_knowledge_entry.id,
        target_entry_id=target_entry.id,
        link_type=KnowledgeLinkType.RELATED,
        strength=0.7
    )
    
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)
    
    return link


@pytest.fixture
async def sample_knowledge_snapshot(db_session) -> KnowledgeSnapshot:
    """Create sample knowledge snapshot for testing."""
    snapshot = KnowledgeSnapshot(
        snapshot_date=datetime.now(timezone.utc),
        total_entries=100,
        entries_by_type={
            "fact": 50,
            "decision": 20,
            "pattern": 15,
            "outcome": 10,
            "preference": 5
        },
        entries_by_engine={
            "manual": 40,
            "mint": 30,
            "wire": 20,
            "pulse": 10
        },
        entries_by_confidence={
            "0.0-0.1": 5,
            "0.1-0.2": 5,
            "0.2-0.3": 10,
            "0.3-0.4": 15,
            "0.4-0.5": 20,
            "0.5-0.6": 20,
            "0.6-0.7": 15,
            "0.7-0.8": 5,
            "0.8-0.9": 3,
            "0.9-1.0": 2
        },
        avg_confidence=0.55,
        avg_access_frequency=0.1,
        archived_count=5,
        expired_count=0,
        new_entries_today=3,
        entries_with_embeddings=80,
        total_links=25
    )
    
    db_session.add(snapshot)
    await db_session.commit()
    await db_session.refresh(snapshot)
    
    return snapshot


@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""
    import random
    random.seed(42)  # For reproducible tests
    return [random.uniform(-1, 1) for _ in range(768)]


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return [
        {
            "id": str(uuid.uuid4()),
            "similarity": 0.95,
            "key": "test:result_1",
            "value": "First search result",
            "entry_type": "fact",
            "source_engine": "manual",
            "source_agent": "test_agent",
            "confidence": 0.9,
            "tags": ["test", "result"],
            "access_count": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "search_weight": 0.9
        },
        {
            "id": str(uuid.uuid4()),
            "similarity": 0.85,
            "key": "test:result_2",
            "value": "Second search result",
            "entry_type": "decision",
            "source_engine": "mint",
            "source_agent": "test_agent",
            "confidence": 0.8,
            "tags": ["test", "result"],
            "access_count": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "search_weight": 0.8
        }
    ]


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Import Base for table creation
from sqlalchemy.ext.declarative import declarative_base
Base = declarativeBase()
