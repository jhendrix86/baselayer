"""
EMAIL_CORE Test Configuration

Pytest configuration and fixtures for email core tests.
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

from ..models.subscriber import Subscriber, SubscriberStatus, SubscriberSource
from ..models.email_log import EmailLog, EmailType, EmailStatus
from ..template_engine import EmailTemplateEngine
from ..brevo_client import BrevoClient
from ..subscriber_manager import SubscriberManager

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
            # Mock expiration - would need timer in real implementation
            return True
    
    return MockRedis()


@pytest.fixture
def mock_brevo_client():
    """Mock Brevo client for testing."""
    class MockBrevoClient:
        def __init__(self):
            self.api_key = "test_key"
            self.daily_limit = 300
        
        async def send_transactional_email(self, email_data, redis_client=None):
            return {
                "messageId": f"test_msg_{uuid.uuid4()}",
                "status": "sent"
            }
        
        async def create_contact(self, contact_data):
            return {
                "id": str(uuid.uuid4()),
                "email": contact_data["email"]
            }
        
        async def update_contact(self, contact_id, contact_data):
            return {
                "id": contact_id,
                "email": contact_data.get("email")
            }
        
        async def delete_contact(self, contact_id):
            return {"id": contact_id}
        
        async def get_contacts(self, limit=50, offset=0):
            return {
                "contacts": [],
                "count": 0
            }
        
        def parse_webhook(self, webhook_data):
            class MockWebhook:
                def __init__(self, data):
                    self.event = data.get("event")
                    self.messageId = data.get("messageId")
                    self.reason = data.get("reason")
                    self.details = data.get("details", {})
            
            return MockWebhook(webhook_data)
    
    return MockBrevoClient()


@pytest.fixture
def template_engine():
    """Create template engine for testing."""
    return EmailTemplateEngine(base_url="https://test.example.com")


@pytest.fixture
def brevo_client(mock_brevo_client):
    """Create Brevo client for testing."""
    return BrevoClient(api_key="test_key")


@pytest.fixture
def subscriber_manager(db_session, mock_redis_client):
    """Create subscriber manager for testing."""
    return SubscriberManager(db_session, redis_client=mock_redis_client)


@pytest.fixture
async def sample_subscriber(db_session) -> Subscriber:
    """Create sample subscriber for testing."""
    subscriber = Subscriber(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        status=SubscriberStatus.ACTIVE,
        source=SubscriberSource.WEBFORM,
        tags=["test", "sample"]
    )
    
    db_session.add(subscriber)
    await db_session.commit()
    await db_session.refresh(subscriber)
    
    return subscriber


@pytest.fixture
async def sample_email_log(db_session, sample_subscriber) -> EmailLog:
    """Create sample email log for testing."""
    email_log = EmailLog(
        subscriber_id=sample_subscriber.id,
        email_type=EmailType.NEWSLETTER,
        subject="Test Email",
        template_name="newsletter",
        content_html="<html><body>Test content</body></html>",
        content_text="Test content",
        status=EmailStatus.SENT
    )
    
    db_session.add(email_log)
    await db_session.commit()
    await db_session.refresh(email_log)
    
    return email_log


@pytest.fixture
def sample_sequence_data():
    """Sample sequence data for testing."""
    return {
        "name": "Test Sequence",
        "description": "A test sequence for testing purposes",
        "slug": "test-sequence",
        "trigger": "subscription",
        "steps": [
            {
                "step_number": 1,
                "subject": "Welcome to Test Sequence",
                "delay": {"value": 0, "unit": "days"},
                "content": "Welcome to our test sequence!"
            },
            {
                "step_number": 2,
                "subject": "Second Step",
                "delay": {"value": 1, "unit": "days"},
                "content": "This is the second step."
            }
        ]
    }


@pytest.fixture
def sample_broadcast_data():
    """Sample broadcast data for testing."""
    return {
        "name": "Test Newsletter",
        "subject": "Test Newsletter Subject",
        "content_md": "# Test Newsletter\n\nThis is a test newsletter.",
        "content_html": "<h1>Test Newsletter</h1><p>This is a test newsletter.</p>",
        "broadcast_type": "newsletter",
        "segment_filters": {
            "status": [SubscriberStatus.ACTIVE]
        }
    }


@pytest.fixture
def sample_template_context():
    """Sample template context for testing."""
    return {
        "subscriber": {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User"
        },
        "company_name": "Test Company",
        "company_address": "123 Test St, Test City, TS 12345",
        "support_email": "support@test.com",
        "unsubscribe_url": "https://test.com/unsubscribe",
        "base_url": "https://test.com",
        "current_date": datetime.now(timezone.utc)
    }


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
Base = declarative_base()
