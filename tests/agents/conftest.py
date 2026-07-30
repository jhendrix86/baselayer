"""
BaseLayer Agents Test Configuration

Pytest configuration with mocks for Ollama, Redis,
and database sessions.
"""

import asyncio
import json
from typing import Any, Dict, Generator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.llm.ollama_client import OllamaClient, OllamaResponse
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger

logger = get_logger(__name__)


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_db_session():
    """Create test database session."""
    engine = create_async_engine(TEST_DATABASE_URL)
    
    async with engine.begin() as conn:
        # Create all tables
        from agents.models import Base
        await conn.run_sync(Base.metadata.create_all)
    
    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestingSessionLocal() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    client = AsyncMock(spec=OllamaClient)
    
    # Mock health check
    client.health_check.return_value = asyncio.Future()
    client.health_check.return_value.set_result(True)
    
    # Mock model list
    mock_models = [
        MagicMock(
            name="llama2:7b",
            size="7B",
            digest="abc123",
            modified_at="2024-01-01",
            family="llama2",
            parameter_size="7B",
            quantization_level="Q4_0",
            format="gguf"
        )
    ]
    client.list_models.return_value = asyncio.Future()
    client.list_models.return_value.set_result(mock_models)
    
    # Mock generation
    mock_response = OllamaResponse(
        model="llama2:7b",
        created_at=1234567890,
        done=True,
        response="Test response from mock Ollama",
        context=[1, 2, 3],
        token_usage={
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    )
    
    client.generate.return_value = asyncio.Future()
    client.generate.return_value.set_result(mock_response)
    
    client.chat.return_value = asyncio.Future()
    client.chat.return_value.set_result(mock_response)
    
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis = AsyncMock()
    
    # Mock basic Redis operations
    redis.ping.return_value = asyncio.Future()
    redis.ping.return_value.set_result(True)
    
    redis.get.return_value = asyncio.Future()
    redis.get.return_value.set_result(None)
    
    redis.set.return_value = asyncio.Future()
    redis.set.return_value.set_result(True)
    
    redis.setex.return_value = asyncio.Future()
    redis.setex.return_value.set_result(True)
    
    redis.publish.return_value = asyncio.Future()
    redis.publish.return_value.set_result(True)
    
    redis.enqueue_job.return_value = asyncio.Future()
    redis.enqueue_job.return_value.set_result("test-job-id")
    
    return redis


@pytest.fixture
def mock_memory_interface():
    """Mock memory interface for testing."""
    memory = AsyncMock(spec=MemoryInterface)
    
    # Mock basic operations
    memory.store.return_value = asyncio.Future()
    memory.store.return_value.set_result(True)
    
    memory.retrieve.return_value = asyncio.Future()
    memory.retrieve.return_value.set_result({"test": "data"})
    
    memory.search.return_value = asyncio.Future()
    memory.search.return_value.set_result([
        {
            "key": "test-key",
            "value": "test-value",
            "tags": ["test"],
            "confidence": 0.9
        }
    ])
    
    memory.search_semantic.return_value = asyncio.Future()
    memory.search_semantic.return_value.set_result([])
    
    memory.get_context.return_value = asyncio.Future()
    memory.get_context.return_value.set_result("Test context for LLM")
    
    return memory


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration for testing."""
    return AgentConfig(
        max_retries=3,
        timeout_seconds=60,
        memory_limit_mb=128,
        log_level="DEBUG",
        enable_metrics=True
    )


@pytest.fixture
def sample_agent_context():
    """Sample agent context for testing."""
    return AgentContext(
        task_id="test-task-123",
        task_type="test_task",
        input_data={"test_input": "test_value"},
        memory_interface=MagicMock(),
        config=AgentConfig(),
        request_id="test-request-456",
        parent_agent_id=None,
        pipeline_id="test-pipeline-789",
        metadata={"test": "metadata"}
    )


@pytest.fixture
def sample_ollama_response():
    """Sample Ollama response for testing."""
    return OllamaResponse(
        model="llama2:7b",
        created_at=1234567890,
        done=True,
        response="This is a test response from Ollama",
        context=[1001, 1002, 1003],
        token_usage={
            "prompt_tokens": 15,
            "completion_tokens": 20,
            "total_tokens": 35
        }
    )


@pytest.fixture
def mock_pipeline_config():
    """Sample pipeline configuration for testing."""
    return {
        "name": "test_pipeline",
        "description": "Test pipeline for unit testing",
        "mode": "sequential",
        "steps": [
            {
                "name": "step1",
                "agent": "test_agent",
                "error_handling": "stop_on_error",
                "max_retries": 2
            },
            {
                "name": "step2",
                "agent": "test_agent",
                "depends_on": ["step1"],
                "error_handling": "skip_and_continue",
                "max_retries": 1
            }
        ],
        "max_concurrent_pipelines": 2,
        "timeout_seconds": 300,
        "enable_persistence": True,
        "enable_events": True,
        "metadata": {"test": True}
    }


class TestAgent(AgentBase):
    """Test agent implementation for testing."""
    
    agent_name = "test_agent"
    agent_version = "1.0.0"
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple planning implementation."""
        return {
            "plan": f"Plan for {input_data.get('task', 'test task')}",
            "steps": ["step1", "step2"],
            "estimated_duration": 30
        }
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Simple execution implementation."""
        await asyncio.sleep(0.1)  # Simulate work
        return {
            "result": f"Executed plan: {plan.get('plan', 'no plan')}",
            "output": "test output",
            "success": True
        }
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Simple validation implementation."""
        return {
            "valid": result.get("success", False),
            "error": None if result.get("success", False) else "Execution failed"
        }
    
    async def report(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Simple reporting implementation."""
        return {
            "agent_id": self.agent_id,
            "execution_summary": f"Completed with result: {result.get('output', 'no output')}",
            "metrics": self._get_execution_metrics()
        }


@pytest.fixture
def test_agent():
    """Test agent fixture."""
    return TestAgent()


@pytest.fixture
async def http_client():
    """HTTP client for API testing."""
    async with AsyncClient() as client:
        yield client


# Mock data generators
def generate_test_input_data() -> Dict[str, Any]:
    """Generate test input data."""
    return {
        "task": "Generate a business plan",
        "parameters": {
            "industry": "technology",
            "company_size": "startup",
            "timeline": "6 months"
        }
    }


def generate_test_plan() -> Dict[str, Any]:
    """Generate test plan data."""
    return {
        "plan": "Create comprehensive business plan",
        "steps": [
            "Market analysis",
            "Product development",
            "Marketing strategy",
            "Financial projections"
        ],
        "estimated_duration": 180,
        "resources": ["research", "templates", "tools"]
    }


def generate_test_result() -> Dict[str, Any]:
    """Generate test result data."""
    return {
        "result": "Business plan generated successfully",
        "output": "Complete business plan document",
        "success": True,
        "metadata": {
            "word_count": 2500,
            "sections": 8,
            "quality_score": 0.95
        }
    }


# Async test utilities
async def wait_for_condition(
    condition_func: callable,
    timeout: float = 5.0,
    interval: float = 0.1
) -> bool:
    """
    Wait for a condition to become true.
    
    Args:
        condition_func: Function that returns boolean
        timeout: Maximum time to wait
        interval: Check interval
        
    Returns:
        True if condition became true, False if timeout
    """
    start_time = asyncio.get_event_loop().time()
    
    while True:
        if condition_func():
            return True
        
        if asyncio.get_event_loop().time() - start_time > timeout:
            return False
        
        await asyncio.sleep(interval)


async def gather_with_errors(*tasks) -> tuple:
    """
    Gather tasks and return (results, errors).
    
    Args:
        *tasks: Tasks to gather
        
    Returns:
        Tuple of (results, errors)
    """
    results = []
    errors = []
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(result)
            else:
                results.append(result)
                
    except Exception as e:
        errors.append(e)
    
    return results, errors


# Test assertions
def assert_valid_agent_state(state_history: list, expected_states: list) -> None:
    """
    Assert that agent transitioned through expected states.
    
    Args:
        state_history: List of state transitions
        expected_states: Expected state sequence
    """
    actual_states = [transition.to_state.value for transition in state_history]
    
    # Check that all expected states are present in order
    for i, expected_state in enumerate(expected_states):
        assert i < len(actual_states), f"Expected state {expected_state} not found in history"
        assert actual_states[i] == expected_state, f"Expected {expected_state} but got {actual_states[i]}"


def assert_valid_response_structure(response: Dict[str, Any]) -> None:
    """
    Assert that response has valid structure.
    
    Args:
        response: Response dictionary to validate
    """
    required_fields = ["status", "agent_id", "task_id"]
    
    for field in required_fields:
        assert field in response, f"Missing required field: {field}"
    
    if response["status"] == "success":
        assert "result" in response, "Success response missing 'result' field"
    elif response["status"] == "failed":
        assert "error" in response, "Failed response missing 'error' field"


# Logging utilities
class LogCapture:
    """Capture log messages for testing."""
    
    def __init__(self):
        self.messages = []
        self.handler = None
    
    def start(self):
        """Start capturing logs."""
        import logging
        
        self.handler = logging.Handler()
        self.handler.emit = self._capture_log
        
        # Add to root logger
        logging.getLogger().addHandler(self.handler)
    
    def stop(self):
        """Stop capturing logs."""
        if self.handler:
            import logging
            logging.getLogger().removeHandler(self.handler)
    
    def _capture_log(self, record):
        """Capture a log record."""
        self.messages.append({
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "timestamp": record.created
        })
    
    def get_messages(self, level: Optional[str] = None) -> list:
        """Get captured messages."""
        if level:
            return [msg for msg in self.messages if msg["level"] == level]
        return self.messages
    
    def clear(self):
        """Clear captured messages."""
        self.messages = []


@pytest.fixture
def log_capture():
    """Log capture fixture."""
    capture = LogCapture()
    capture.start()
    yield capture
    capture.stop()
