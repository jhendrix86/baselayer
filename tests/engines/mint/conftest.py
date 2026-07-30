"""
MINT Engine Test Configuration

Pytest configuration with mocks for Gumroad,
database sessions, and agent testing.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from agents.core.agent_base import AgentConfig
from agents.core.context import AgentContext
from agents.llm.ollama_client import OllamaClient, OllamaResponse
from agents.llm.prompt_engine import PromptEngine
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_db_session():
    """Create test database session."""
    # Mock database session
    session = AsyncMock()
    
    # Mock query execution
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalars.return_value.all.return_value = []
    
    session.add.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.delete.return_value = None
    
    yield session


@pytest_asyncio.fixture(scope="session")
async def mock_redis_client():
    """Create mock Redis client."""
    redis = AsyncMock()
    
    # Mock Redis operations
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
    
    yield redis


@pytest.fixture(scope="session")
def mock_ollama_client():
    """Create mock Ollama client."""
    client = AsyncMock(spec=OllamaClient)
    
    # Mock health check
    client.health_check.return_value = True
    
    # Mock model listing
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
    client.list_models.return_value = mock_models
    
    # Mock generation
    mock_response = OllamaResponse(
        model="llama2:7b",
        created_at=1234567890,
        done=True,
        response="Test response from mock Ollama",
        context=[1001, 1002, 1003],
        token_usage={
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    )
    
    client._select_model.return_value = "llama2:7b"
    client._execute_with_retry.return_value = mock_response
    client.generate.return_value = mock_response
    client.chat.return_value = mock_response
    
    # Mock streaming
    async def mock_stream(*args, **kwargs):
        for i in range(3):
            yield OllamaResponse(
                model="llama2:7b",
                response=f"chunk_{i}",
                done=(i == 2),
                token_usage={"total_tokens": 5}
            )
    
    client._stream_with_retry.side_effect = mock_stream
    
    return client


@pytest.fixture(scope="session")
def mock_prompt_engine():
    """Create mock prompt engine."""
    engine = AsyncMock(spec=PromptEngine)
    
    # Mock template rendering
    engine.render.return_value = "Rendered template content"
    engine.render_with_pattern.return_value = "Rendered template with pattern"
    engine.create_system_message.return_value = "System message content"
    engine.create_few_shot.return_value = "Few-shot content"
    engine.create_chain_of_thought.return_value = "Chain of thought content"
    engine.create_json_output.return_value = "JSON output content"
    engine.create_error_correction.return_value = "Error correction content"
    engine.validate_template.return_value = {
        "valid": True,
        "score": 1.0,
        "syntax_valid": True
    }
    engine.list_templates.return_value = []
    engine.get_template_info.return_value = None
    engine.clear_cache.return_value = None
    engine.reload_templates.return_value = None
    
    return engine


@pytest.fixture(scope="session")
def mock_memory_interface():
    """Create mock memory interface."""
    memory = AsyncMock(spec=MemoryInterface)
    
    # Mock memory operations
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
    
    memory.update.return_value = asyncio.Future()
    memory.update.return_value.set_result(True)
    
    memory.delete.return_value = asyncio.Future()
    memory.delete.return_value.set_result(True)
    
    memory.get_context.return_value = asyncio.Future()
    memory.get_context.return_value.set_result("Test context for LLM")
    
    memory.link.return_value = asyncio.Future()
    memory.link.return_value.set_result(True)
    
    memory.get_related.return_value = asyncio.Future()
    memory.get_related.return_value.set_result([])
    
    memory.get_stats.return_value = asyncio.Future()
    memory.get_stats.return_value.set_result({
        "total_entries": 100,
        "total_links": 50
    })
    
    memory.health_check.return_value = asyncio.Future()
    memory.health_check.return_value.set_result(True)
    
    return memory


@pytest.fixture(scope="session")
def sample_product_data():
    """Sample product data for testing."""
    return {
        "title": "Test Digital Product",
        "subtitle": "A comprehensive guide for testing",
        "description": "This is a test product created for unit testing purposes. It includes comprehensive coverage of the topic with practical examples and actionable insights.",
        "product_type": "pdf_guide",
        "price_cents": 999,  # $9.99
        "tags": ["test", "guide", "digital"],
        "target_audience": "developers",
        "word_count_target": 2000,
        "brief": "Create a comprehensive guide about testing digital products",
        "metadata": {
            "test": True,
            "version": "1.0.0"
        }
    }


@pytest.fixture(scope="session")
def sample_generation_request():
    """Sample generation request for testing."""
    return {
        "product_type": "pdf_guide",
        "brief": "Create a comprehensive guide about digital product creation",
        "target_audience": "entrepreneurs",
        "price_range": "medium",
        "word_count_target": 1500,
        "template_id": None,
        "skip_review": False,
        "metadata": {
            "test": True
        }
    }


@pytest.fixture(scope="session")
def sample_publish_request():
    """Sample publish request for testing."""
    return {
        "product_id": "test-product-123",
        "skip_review": False,
        "publish_immediately": False,
        "price_override_cents": None
    }


@pytest.fixture(scope="session")
def sample_regenerate_request():
    """Sample regenerate request for testing."""
    return {
        "product_id": "test-product-123",
        "sections": ["introduction", "implementation"],
        "template_id": None,
        "force_regenerate": False
    }


@pytest.fixture(scope="session")
def sample_gumroad_product():
    """Sample Gumroad product for testing."""
    return {
        "name": "Test Digital Product",
        "description": "A comprehensive test product",
        "price_cents": 999,
        "visible": True,
        "require_shipping": False,
        "tags": ["test", "digital"],
        "max_purchase_count": None,
        "support_email": None,
        "published": False
    }


@pytest.fixture(scope="session")
def sample_gumroad_response():
    """Sample Gumroad API response for testing."""
    return {
        "id": "gumroad-product-123",
        "name": "Test Digital Product",
        "description": "A comprehensive test product",
        "price_cents": 999,
        "url": "https://gumroad.com/l/test-product",
        "visible": True,
        "require_shipping": False,
        "tags": ["test", "digital"],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture(scope="session")
def sample_pipeline_result():
    """Sample pipeline execution result for testing."""
    return {
        "status": "success",
        "step_results": {
            "generate_content": {
                "success": True,
                "result": {
                    "generation_id": "test-gen-123",
                    "content": "Generated content for testing",
                    "sections": {
                        "introduction": "Test introduction",
                        "main_content": "Test main content",
                        "conclusion": "Test conclusion"
                    },
                    "metadata": {
                        "quality_score": 0.9,
                        "word_count": 1500
                    }
                }
            },
            "package_product": {
                "success": True,
                "result": {
                    "assets": {
                        "pdf": {
                            "file_name": "test-product.pdf",
                            "file_path": "/path/to/test-product.pdf",
                            "file_size_bytes": 1024000
                        }
                    },
                    "primary_asset": "pdf"
                }
            },
            "optimize_listing": {
                "success": True,
                "result": {
                    "full_listing": "Optimized listing copy for testing",
                    "character_counts": {
                        "total": 500,
                        "title": 50,
                        "description": 300
                    }
                }
            },
            "publish_to_gumroad": {
                "success": True,
                "result": {
                    "gumroad_product_id": "gumroad-123",
                    "gumroad_url": "https://gumroad.com/l/test-product"
                }
            }
        },
        "duration_ms": 30000,
        "metadata": {
            "pipeline_type": "product_creation",
            "total_steps": 4,
            "completed_steps": 4
        }
    }


@pytest.fixture(scope="session")
def mock_agent_config():
    """Sample agent configuration for testing."""
    return AgentConfig(
        max_retries=3,
        timeout_seconds=60,
        memory_limit_mb=128,
        log_level="DEBUG",
        enable_metrics=True
    )


@pytest.fixture(scope="session")
def mock_agent_context():
    """Sample agent context for testing."""
    return AgentContext(
        task_id="test-task-123",
        task_type="test_task",
        input_data={"test": "data"},
        memory_interface=AsyncMock(spec=MemoryInterface),
        config=AgentConfig(),
        request_id="test-request-456",
        parent_agent_id=None,
        pipeline_id="test-pipeline-789",
        metadata={"test": True}
    )


@pytest.fixture(scope="session")
def log_capture():
    """Log capture fixture for testing."""
    class LogCapture:
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
            import logging
            
            if self.handler:
                logging.getLogger().removeHandler(self.handler)
        
        def _capture_log(self, record):
            """Capture a log record."""
            self.messages.append({
                "level": record.levelname,
                "message": record.getMessage(),
                "name": record.name,
                "timestamp": record.created
            })
        
        def get_messages(self, level=None):
            """Get captured messages."""
            if level:
                return [msg for msg in self.messages if msg["level"] == level]
            return self.messages
        
        def clear(self):
            """Clear captured messages."""
            self.messages = []
    
    return LogCapture()


@pytest.fixture(scope="session")
def sample_template_data():
    """Sample template data for testing."""
    return {
        "name": "test_template",
        "description": "Test template for unit testing",
        "product_type": "pdf_guide",
        "prompt_template_name": "product_outline_v1",
        "structure": {
            "sections": {
                "introduction": {
                    "title": "Introduction",
                    "word_count": 300,
                    "description": "Hook the reader and state the problem"
                },
                "main_content": {
                    "title": "Main Content",
                    "word_count": 1000,
                    "description": "Provide detailed information and examples"
                },
                "conclusion": {
                    "title": "Conclusion",
                    "word_count": 200,
                    "description": "Summarize key takeaways"
                }
            }
        },
        "default_price_cents": 999,
        "tags": ["test", "template"],
        "min_word_count": 500,
        "max_word_count": 5000,
        "required_sections": ["introduction", "main_content"],
        "optional_sections": ["conclusion"],
        "temperature": 0.7,
        "max_tokens": 2000,
        "model_preference": "llama2:7b",
        "category": "testing",
        "target_audience": "testers",
        "difficulty_level": "beginner",
        "min_quality_score": 0.7,
        "require_human_review": True,
        "auto_approval_threshold": 0.9,
        "metadata": {
            "test": True,
            "version": "1.0.0"
        }
    }


@pytest.fixture(scope="session")
def sample_analytics_data():
    """Sample analytics data for testing."""
    return {
        "product_id": "test-product-123",
        "date": "2024-01-01",
        "views": 1000,
        "sales": 50,
        "revenue_cents": 49950,  # $499.50
        "refunds": 2,
        "conversion_rate": 5.0,
        "source": "gumroad",
        "unique_visitors": 800,
        "page_views": 1200,
        "add_to_cart": 75,
        "checkout_started": 60,
        "gross_revenue_cents": 54950,  # $549.50
        "net_revenue_cents": 52950,  # $529.50
        "fees_cents": 2000  # $20.00
    }


@pytest.fixture(scope="session")
def mock_file_system():
    """Mock file system operations for testing."""
    import os
    from pathlib import Path
    
    mock_files = {}
    
    def mock_open(file_path, mode='r', encoding='utf-8'):
        """Mock file open operation."""
        path = Path(file_path)
        
        if str(path) in mock_files:
            content = mock_files[str(path)]
        else:
            content = f"Mock content for {file_path}"
        
        from io import StringIO
        return StringIO(content)
    
    def mock_exists(file_path):
        """Mock file existence check."""
        return str(Path(file_path)) in mock_files or Path(file_path).exists()
    
    def mock_stat(file_path):
        """Mock file stat operation."""
        path = Path(file_path)
        
        class MockStat:
            def __init__(self):
                self.st_size = len(mock_files.get(str(path), "Mock content"))
        
        return MockStat()
    
    def mock_makedirs(file_path, exist_ok=False):
        """Mock directory creation."""
        pass
    
    # Store mock files
    mock_files.update({
        "/path/to/test-product.pdf": "Mock PDF content",
        "/path/to/test-product.md": "Mock Markdown content",
        "/path/to/test-product.txt": "Mock text content",
        "/path/to/test-product.zip": "Mock ZIP content"
    })
    
    return {
        "open": mock_open,
        "exists": mock_exists,
        "stat": mock_stat,
        "makedirs": mock_makedirs
    }


@pytest.fixture(scope="session")
def mock_http_client():
    """Mock HTTP client for testing."""
    import httpx
    
    client = AsyncMock(spec=httpx.AsyncClient)
    
    # Mock HTTP responses
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    
    client.request.return_value = mock_response
    client.get.return_value = mock_response
    client.post.return_value = mock_response
    client.put.return_value = mock_response
    client.delete.return_value = mock_response
    
    return client


@pytest.fixture(scope="session")
def sample_error_response():
    """Sample error response for testing."""
    return {
        "error": "Test error message",
        "message": "Test error occurred",
        "details": {
            "error_code": "TEST_ERROR",
            "context": "Unit testing"
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }


@pytest.fixture(scope="session")
def sample_success_response():
    """Sample success response for testing."""
    return {
        "success": True,
        "message": "Operation completed successfully",
        "data": {
            "test": True,
            "operation": "unit_test"
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }


@pytest.fixture(scope="session")
def sample_validation_result():
    """Sample validation result for testing."""
    return {
        "valid": True,
        "score": 0.9,
        "validation_results": {
            "word_count_validation": {
                "valid": True,
                "score": 1.0,
                "word_count": 1500,
                "target_count": 1500
            },
            "content_completeness": {
                "valid": True,
                "score": 1.0,
                "total_sections": 5,
                "completed_sections": 5
            },
            "kade_persona_compliance": {
                "valid": True,
                "score": 1.0,
                "violations": []
            },
            "placeholder_removal": {
                "valid": True,
                "score": 1.0,
                "violations": []
            },
            "ai_self_reference_check": {
                "valid": True,
                "score": 1.0,
                "violations": []
            },
            "cta_presence": {
                "valid": True,
                "score": 1.0,
                "violations": []
            }
        },
        "errors": []
    }


@pytest.fixture(scope="session")
def sample_quality_metrics():
    """Sample quality metrics for testing."""
    return {
        "total_runs": 10,
        "successful_runs": 9,
        "failed_runs": 1,
        "average_duration_ms": 25000,
        "quality_scores": [0.8, 0.9, 0.85, 0.95],
        "error_rates": {
            "generation": 0.1,
            "packaging": 0.0,
            "listing": 0.05,
            "publishing": 0.0
        }
    }


@pytest.fixture(scope="session")
def sample_pipeline_config():
    """Sample pipeline configuration for testing."""
    return {
        "name": "test_pipeline",
        "description": "Test pipeline for unit testing",
        "mode": "sequential",
        "steps": [
            {
                "name": "test_step_1",
                "agent": "TestAgent",
                "error_handling": "retry",
                "max_retries": 2
            },
            {
                "name": "test_step_2",
                "agent": "TestAgent",
                "depends_on": ["test_step_1"],
                "error_handling": "skip_and_continue",
                "max_retries": 1
            }
        ],
        "timeout_seconds": 300,
        "enable_persistence": True,
        "enable_events": True,
        "metadata": {
            "test": True,
            "version": "1.0.0"
        }
    }


@pytest.fixture(scope="session")
def sample_environment_variables():
    """Sample environment variables for testing."""
    return {
        "GUMROAD_ACCESS_TOKEN": "test-token-123",
        "DATABASE_URL": "sqlite:///test.db",
        "REDIS_URL": "redis://localhost:6379/0",
        "LOG_LEVEL": "DEBUG"
    }


@pytest.fixture(scope="session")
def mock_settings():
    """Mock application settings for testing."""
    from pydantic import BaseSettings
    
    class MockSettings(BaseSettings):
        app_name: str = "Test MINT Engine"
        environment: str = "test"
        debug: bool = True
        secret_key: str = "test-secret-key"
        database_url: str = "sqlite:///test.db"
        redis_url: str = "redis://localhost:6379/0"
        
        class Config:
            env_file = ".env.test"
    
    return MockSettings()
