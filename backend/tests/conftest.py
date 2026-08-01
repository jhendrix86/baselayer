"""
BaseLayer Test Configuration

Pytest configuration and fixtures for the BaseLayer test suite.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from baselayer.core.config import get_settings
from baselayer.core.database import Base, get_db_session
from baselayer.main import app
from baselayer.models.user import User, UserRole

# Test settings
settings = get_settings()

# Override settings for testing
settings.database_url = "sqlite+aiosqlite:///:memory:"
settings.secret_key = "test-secret-key-for-testing-only"
settings.environment = "testing"

# Test database engine
test_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Clean up - drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database dependency override."""
    # Override database dependency
    async def override_get_db_session():
        yield db_session
    
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    # Create test client
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from baselayer.core.auth import password_manager
    
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash=password_manager.hash_password("testpassword123"),
        role=UserRole.OPERATOR,
        is_active=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    from baselayer.core.auth import password_manager
    
    user = User(
        email="admin@example.com",
        name="Admin User",
        password_hash=password_manager.hash_password("adminpassword123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Create authentication headers for test user."""
    from baselayer.core.auth import auth_service
    
    tokens = await auth_service.create_user_tokens(test_user)
    
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Content-Type": "application/json"
    }


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    """Create authentication headers for admin user."""
    from baselayer.core.auth import auth_service
    
    tokens = await auth_service.create_user_tokens(admin_user)
    
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_workflow_data():
    """Mock workflow data for testing."""
    return {
        "name": "Test Workflow",
        "description": "A test workflow for unit testing",
        "steps": [
            {
                "name": "Step 1",
                "type": "task",
                "action": "test_action",
                "parameters": {"test_param": "test_value"}
            }
        ]
    }


@pytest.fixture
def mock_agent_data():
    """Mock agent data for testing."""
    return {
        "name": "Test Agent",
        "type": "test_agent",
        "capabilities": ["test_capability"],
        "config": {"test_config": "test_value"}
    }


@pytest.fixture
def mock_knowledge_entry_data():
    """Mock knowledge entry data for testing."""
    return {
        "title": "Test Knowledge Entry",
        "content": "This is a test knowledge entry for unit testing.",
        "category": "test",
        "tags": ["test", "unit_test"]
    }


@pytest.fixture
def mock_revenue_stream_data():
    """Mock revenue stream data for testing."""
    return {
        "name": "Test Revenue Stream",
        "type": "subscription",
        "amount": 99.99,
        "currency": "USD",
        "frequency": "monthly"
    }


@pytest.fixture
def mock_governance_rule_data():
    """Mock governance rule data for testing."""
    return {
        "name": "Test Governance Rule",
        "description": "A test governance rule for unit testing",
        "rule_type": "compliance",
        "conditions": [{"field": "test_field", "operator": "equals", "value": "test_value"}],
        "actions": [{"type": "log", "message": "Test rule triggered"}]
    }


# Test configuration
def pytest_configure(config):
    """Configure pytest settings."""
    config.addinivalue_line(
        "markers", "unit: Mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: Mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "api: Mark test as API test"
    )
    config.addinivalue_line(
        "markers", "slow: Mark test as slow running"
    )


# Async test configuration
@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"
