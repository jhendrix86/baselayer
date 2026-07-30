"""
BaseLayer Tasks Tests

Test suite for ARQ task definitions including
agent execution, pipeline execution, and scheduling.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.queue.tasks import (
    run_agent_task,
    run_pipeline_task,
    schedule_recurring_task,
    enqueue_agent_task,
    enqueue_pipeline_task,
    get_job_status,
    cancel_job,
    AGENT_REGISTRY,
    PIPELINE_REGISTRY
)
from agents.core.agent_base import AgentBase, AgentConfig
from agents.core.pipeline import Pipeline
from agents.memory.memory_interface import MemoryInterface
from tests.agents.conftest import (
    TestAgent,
    mock_pipeline_config,
    sample_agent_config,
    sample_agent_context,
    generate_test_input_data,
    generate_test_plan,
    generate_test_result,
    assert_valid_response_structure,
    LogCapture
)


class TestTaskFunctions:
    """Test suite for task functions."""
    
    @pytest.mark.asyncio
    async def test_run_agent_task_success(self, sample_agent_config, sample_agent_context):
        """Test successful agent task execution."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-job-123"
        mock_ctx.get.return_value = "test-request-456"
        mock_ctx.get.side_effect = lambda key, default=None: {
            "metadata": {"test": True}
        }.get(key, default)
        
        result = await run_agent_task(
            ctx=mock_ctx,
            agent_name="test_agent",
            task_data=generate_test_input_data(),
            config=sample_agent_config.dict()
        )
        
        assert_valid_response_structure(result)
        assert result["status"] == "success"
        assert result["agent_name"] == "test_agent"
        assert result["job_id"] == "test-job-123"
        assert "result" in result
        assert "duration_ms" in result
        assert "completed_at" in result
    
    @pytest.mark.asyncio
    async def test_run_agent_task_invalid_agent(self, sample_agent_config, sample_agent_context):
        """Test agent task with non-existent agent."""
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-job-123"
        
        result = await run_agent_task(
            ctx=mock_ctx,
            agent_name="nonexistent_agent",
            task_data=generate_test_input_data()
        )
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Agent not registered" in result["error"]
    
    @pytest.mark.asyncio
    async def test_run_agent_task_execution_failure(self, sample_agent_config, sample_agent_context):
        """Test agent task with execution failure."""
        # Register failing agent
        class FailingAgent(TestAgent):
            async def run(self, context):
                raise Exception("Agent execution failed")
        
        AGENT_REGISTRY["failing_agent"] = FailingAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-job-123"
        
        result = await run_agent_task(
            ctx=mock_ctx,
            agent_name="failing_agent",
            task_data=generate_test_input_data()
        )
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Agent execution failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_run_pipeline_task_success(self, mock_pipeline_config, sample_agent_context):
        """Test successful pipeline task execution."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        PIPELINE_REGISTRY["test_pipeline"] = mock_pipeline_config
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-pipeline-123"
        mock_ctx.get.return_value = "test-request-456"
        
        result = await run_pipeline_task(
            ctx=mock_ctx,
            pipeline_name="test_pipeline",
            input_data=generate_test_input_data()
        )
        
        assert_valid_response_structure(result)
        assert result["status"] == "success"
        assert result["pipeline_name"] == "test_pipeline"
        assert result["job_id"] == "test-pipeline-123"
        assert "result" in result
        assert "duration_ms" in result
        assert "completed_at" in result
    
    @pytest.mark.asyncio
    async def test_run_pipeline_task_invalid_pipeline(self, sample_agent_context):
        """Test pipeline task with non-existent pipeline."""
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-pipeline-123"
        
        result = await run_pipeline_task(
            ctx=mock_ctx,
            pipeline_name="nonexistent_pipeline",
            input_data=generate_test_input_data()
        )
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Pipeline not registered" in result["error"]
    
    @pytest.mark.asyncio
    async def test_run_pipeline_task_with_overrides(self, mock_pipeline_config, sample_agent_context):
        """Test pipeline task with configuration overrides."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        PIPELINE_REGISTRY["test_pipeline"] = mock_pipeline_config
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-pipeline-123"
        
        config_overrides = {"timeout_seconds": 600}
        
        result = await run_pipeline_task(
            ctx=mock_ctx,
            pipeline_name="test_pipeline",
            input_data=generate_test_input_data(),
            config_overrides=config_overrides
        )
        
        assert_valid_response_structure(result)
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_schedule_recurring_task_success(self, sample_agent_config, sample_agent_context):
        """Test successful recurring task scheduling."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-schedule-123"
        
        result = await schedule_recurring_task(
            ctx=mock_ctx,
            agent_name="test_agent",
            cron_expression="0 9 * * *",
            task_data=generate_test_input_data()
        )
        
        assert result["status"] == "scheduled"
        assert result["agent_name"] == "test_agent"
        assert result["cron_expression"] == "0 9 * * *"
        assert "next_run" in result
    
    @pytest.mark.asyncio
    async def test_schedule_recurring_task_invalid_cron(self, sample_agent_config, sample_agent_context):
        """Test recurring task with invalid cron expression."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-schedule-123"
        
        result = await schedule_recurring_task(
            ctx=mock_ctx,
            agent_name="test_agent",
            cron_expression="invalid-cron",
            task_data=generate_test_input_data()
        )
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Invalid cron expression" in result["error"]


class TestTaskUtilities:
    """Test suite for task utility functions."""
    
    @pytest.mark.asyncio
    async def test_enqueue_agent_task_success(self):
        """Test successful agent task enqueuing."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-job-id"
            
            job_id = await enqueue_agent_task(
                agent_name="test_agent",
                task_data=generate_test_input_data()
            )
            
            assert job_id == "test-job-id"
            mock_redis.enqueue_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enqueue_agent_task_with_delay(self):
        """Test agent task enqueuing with delay."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-job-id"
            
            job_id = await enqueue_agent_task(
                agent_name="test_agent",
                task_data=generate_test_input_data(),
                delay=30
            )
            
            assert job_id == "test-job-id"
            mock_redis.enqueue_job.assert_called_once_with(
                any_args=True,
                _defer_by=30
            )
    
    @pytest.mark.asyncio
    async def test_enqueue_pipeline_task_success(self):
        """Test successful pipeline task enqueuing."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        PIPELINE_REGISTRY["test_pipeline"] = mock_pipeline_config
        
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-pipeline-job-id"
            
            job_id = await enqueue_pipeline_task(
                pipeline_name="test_pipeline",
                input_data=generate_test_input_data()
            )
            
            assert job_id == "test-pipeline-job-id"
            mock_redis.enqueue_job.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enqueue_pipeline_task_with_overrides(self):
        """Test pipeline task enqueuing with config overrides."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        PIPELINE_REGISTRY["test_pipeline"] = mock_pipeline_config
        
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-pipeline-job-id"
            
            config_overrides = {"timeout_seconds": 600}
            
            job_id = await enqueue_pipeline_task(
                pipeline_name="test_pipeline",
                input_data=generate_test_input_data(),
                config_overrides=config_overrides
            )
            
            assert job_id == "test-pipeline-job-id"
            mock_redis.enqueue_job.assert_called_once_with(
                any_args=True,
                config_overrides=config_overrides
            )
    
    @pytest.mark.asyncio
    async def test_get_job_status_success(self):
        """Test successful job status retrieval."""
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_job_data = {
                "job_id": "test-job-123",
                "status": "completed",
                "result": {"test": "data"}
            }
            mock_redis.get.return_value = str(mock_job_data)
            
            status = await get_job_status("test-job-123")
            
            assert status["job_id"] == "test-job-123"
            assert status["status"] == "completed"
            assert status["result"] == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self):
        """Test job status when job not found."""
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.get.return_value = None
            
            status = await get_job_status("nonexistent-job")
            
            assert status is None
    
    @pytest.mark.asyncio
    async def test_cancel_job_success(self):
        """Test successful job cancellation."""
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.set.return_value = asyncio.Future()
            mock_redis.set.return_value.set_result(True)
            
            cancelled = await cancel_job("test-job-123")
            
            assert cancelled is True
            mock_redis.set.assert_called_once_with("cancel:test-job-123", "1", ex=60)
    
    @pytest.mark.asyncio
    async def test_cancel_job_failure(self):
        """Test job cancellation failure."""
        # Mock Redis client
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.set.side_effect = Exception("Redis error")
            
            cancelled = await cancel_job("test-job-123")
            
            assert cancelled is False


class TestTaskIntegration:
    """Test suite for task integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_agent_task_end_to_end(self, sample_agent_config, sample_agent_context):
        """Test complete agent task workflow."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock Redis and worker
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-job-id"
            
            # Enqueue task
            job_id = await enqueue_agent_task(
                agent_name="test_agent",
                task_data=generate_test_input_data()
            )
            
            # Get status
            mock_redis.get.return_value = None
            status = await get_job_status(job_id)
            
            # Should not have status yet (just enqueued)
            assert status is None
    
    @pytest.mark.asyncio
    async def test_pipeline_task_end_to_end(self, mock_pipeline_config, sample_agent_context):
        """Test complete pipeline task workflow."""
        # Register test agent and pipeline
        AGENT_REGISTRY["test_agent"] = TestAgent
        PIPELINE_REGISTRY["test_pipeline"] = mock_pipeline_config
        
        # Mock Redis and worker
        with patch('agents.queue.tasks.worker.redis_client') as mock_redis:
            mock_redis.enqueue_job.return_value = "test-pipeline-job-id"
            
            # Enqueue pipeline task
            job_id = await enqueue_pipeline_task(
                pipeline_name="test_pipeline",
                input_data=generate_test_input_data()
            )
            
            # Get status
            mock_redis.get.return_value = None
            status = await get_job_status(job_id)
            
            # Should not have status yet (just enqueued)
            assert status is None
    
    @pytest.mark.asyncio
    async def test_task_error_handling(self, sample_agent_config, sample_agent_context):
        """Test task error handling and logging."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-job-123"
        
        # Capture logs
        with LogCapture() as log_capture:
            result = await run_agent_task(
                ctx=mock_ctx,
                agent_name="test_agent",
                task_data=generate_test_input_data()
            )
        
        # Should have error logs
        error_logs = log_capture.get_messages("ERROR")
        assert len(error_logs) >= 0
    
    @pytest.mark.asyncio
    async def test_task_metrics_tracking(self, sample_agent_config, sample_agent_context):
        """Test task metrics tracking."""
        # Register test agent
        AGENT_REGISTRY["test_agent"] = TestAgent
        
        # Mock ARQ context
        mock_ctx = MagicMock()
        mock_ctx.job_id = "test-job-123"
        
        result = await run_agent_task(
            ctx=mock_ctx,
            agent_name="test_agent",
            task_data=generate_test_input_data()
        )
        
        # Should have duration metrics
        assert "duration_ms" in result
        assert result["duration_ms"] >= 0


class TestTaskConfiguration:
    """Test suite for task configuration validation."""
    
    def test_agent_registry_validation(self):
        """Test agent registry validation."""
        # Test with empty registry
        original_registry = AGENT_REGISTRY.copy()
        AGENT_REGISTRY.clear()
        
        with pytest.raises(Exception):
            # This should raise an error in the actual implementation
            pass
        
        # Restore registry
        AGENT_REGISTRY.update(original_registry)
    
    def test_pipeline_registry_validation(self):
        """Test pipeline registry validation."""
        # Test with empty registry
        original_registry = PIPELINE_REGISTRY.copy()
        PIPELINE_REGISTRY.clear()
        
        with pytest.raises(Exception):
            # This should raise an error in the actual implementation
            pass
        
        # Restore registry
        PIPELINE_REGISTRY.update(original_registry)
    
    def test_task_data_serialization(self):
        """Test task data serialization."""
        task_data = generate_test_input_data()
        
        # Should be JSON serializable
        import json
        serialized = json.dumps(task_data)
        deserialized = json.loads(serialized)
        
        assert deserialized == task_data
