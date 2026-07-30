"""
BaseLayer Pipeline Tests

Test suite for Pipeline class including execution modes,
state persistence, and error handling.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from agents.core.pipeline import Pipeline, PipelineConfig, PipelineStep, PipelineMode, ErrorHandling
from agents.core.state import AgentState
from tests.agents.conftest import (
    TestAgent,
    mock_pipeline_config,
    sample_agent_config,
    assert_valid_response_structure,
    LogCapture
)


class TestPipeline:
    """Test suite for Pipeline functionality."""
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, mock_pipeline_config):
        """Test pipeline initialization with configuration."""
        agents = {"test_agent": TestAgent()}
        
        pipeline = Pipeline(mock_pipeline_config, agents=agents)
        
        assert pipeline.pipeline_id is not None
        assert pipeline.config == mock_pipeline_config
        assert len(pipeline._step_map) == 2
        assert "step1" in pipeline._step_map
        assert "step2" in pipeline._step_map
    
    @pytest.mark.asyncio
    async def test_sequential_execution(self, mock_pipeline_config):
        """Test sequential pipeline execution."""
        agents = {"test_agent": TestAgent()}
        
        # Create sequential pipeline
        config = mock_pipeline_config.copy()
        config.mode = PipelineMode.SEQUENTIAL
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "sequential_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert "step_results" in result
        assert len(result["step_results"]) == 2
        assert "duration_ms" in result
    
    @pytest.mark.asyncio
    async def test_parallel_execution(self, mock_pipeline_config):
        """Test parallel pipeline execution."""
        agents = {"test_agent": TestAgent()}
        
        # Create parallel pipeline
        config = mock_pipeline_config.copy()
        config.mode = PipelineMode.PARALLEL
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "parallel_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert "parallel_results" in result["step_results"]
    
    @pytest.mark.asyncio
    async def test_conditional_execution(self, mock_pipeline_config):
        """Test conditional pipeline execution."""
        agents = {"test_agent": TestAgent()}
        
        # Create conditional pipeline
        config = mock_pipeline_config.copy()
        config.mode = PipelineMode.CONDITIONAL
        
        # Add condition to second step
        config.steps[1].condition = "test_input == 'conditional_test'"
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline with condition met
        input_data = {"test_input": "conditional_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert len(result["step_results"]) == 2
        
        # Execute pipeline with condition not met
        input_data = {"test_input": "other_value"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert len(result["step_results"]) == 1  # Only first step executed
    
    @pytest.mark.asyncio
    async def test_error_handling_stop_on_error(self, mock_pipeline_config):
        """Test stop_on_error error handling."""
        # Create failing agent
        class FailingAgent(TestAgent):
            async def execute(self, plan):
                raise Exception("Step failed")
        
        agents = {"failing_agent": FailingAgent()}
        
        # Create pipeline with stop_on_error
        config = mock_pipeline_config.copy()
        config.steps[0].error_handling = ErrorHandling.STOP_ON_ERROR
        config.steps[0].agent = agents["failing_agent"]
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "error_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "failed"
        assert "error" in result
        assert len(result["step_errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_skip_and_continue(self, mock_pipeline_config):
        """Test skip_and_continue error handling."""
        # Create failing agent
        class FailingAgent(TestAgent):
            async def execute(self, plan):
                raise Exception("Step failed")
        
        agents = {"failing_agent": FailingAgent()}
        
        # Create pipeline with skip_and_continue
        config = mock_pipeline_config.copy()
        config.steps[0].error_handling = ErrorHandling.SKIP_AND_CONTINUE
        config.steps[0].agent = agents["failing_agent"]
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "error_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"  # Should continue despite error
        assert len(result["failed_steps"]) > 0
        assert len(result["completed_steps"]) > 0
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, mock_pipeline_config):
        """Test retry mechanism with exponential backoff."""
        # Create flaky agent
        retry_count = 0
        class FlakyAgent(TestAgent):
            async def execute(self, plan):
                nonlocal retry_count
                retry_count += 1
                if retry_count < 2:  # Fail first 2 times
                    raise Exception(f"Attempt {retry_count} failed")
                return {"result": "success after retries"}
        
        agents = {"flaky_agent": FlakyAgent()}
        
        # Create pipeline with retry
        config = mock_pipeline_config.copy()
        config.steps[0].max_retries = 3
        config.steps[0].retry_backoff = "exponential"
        config.steps[0].agent = agents["flaky_agent"]
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "retry_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert retry_count == 3  # Should have retried 3 times
    
    @pytest.mark.asyncio
    async def test_step_dependencies(self, mock_pipeline_config):
        """Test step dependency handling."""
        agents = {"test_agent": TestAgent()}
        
        # Create pipeline with dependencies
        config = mock_pipeline_config.copy()
        config.steps[1].depends_on = ["step1"]  # step2 depends on step1
        
        pipeline = Pipeline(config, agents=agents)
        
        # Execute pipeline
        input_data = {"test_input": "dependency_test"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "success"
        assert "step1" in result["step_results"]
        assert "step2" in result["step_results"]
        # step2 should execute after step1 completes
    
    @pytest.mark.asyncio
    async def test_pipeline_cancellation(self, mock_pipeline_config):
        """Test pipeline cancellation."""
        # Create slow agent
        class SlowAgent(TestAgent):
            async def execute(self, plan):
                await asyncio.sleep(1.0)  # Slow execution
                return {"result": "slow completion"}
        
        agents = {"slow_agent": SlowAgent()}
        
        pipeline = Pipeline(config=mock_pipeline_config, agents=agents)
        
        # Start execution in background
        execution_task = asyncio.create_task(pipeline.execute({"test": "cancel"}))
        
        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        await pipeline.cancel()
        
        # Wait for completion
        result = await execution_task
        
        assert result["status"] == "failed"
        assert "cancelled" in result.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_pipeline_status_tracking(self, mock_pipeline_config):
        """Test pipeline status tracking."""
        agents = {"test_agent": TestAgent()}
        
        pipeline = Pipeline(config=mock_pipeline_config, agents=agents)
        
        # Get initial status
        status = pipeline.get_status()
        assert status["status"] == "INITIALIZED"
        assert status["current_step"] is None
        
        # Execute pipeline
        await pipeline.execute({"test": "status"})
        
        # Get final status
        status = pipeline.get_status()
        assert status["status"] == "COMPLETED"
        assert status["completed_steps"] == ["step1", "step2"]
        assert status["total_steps"] == 2
        assert "duration_ms" in status
    
    @pytest.mark.asyncio
    async def test_event_emission(self, mock_pipeline_config):
        """Test event emission during pipeline execution."""
        # Create mock Redis client
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = asyncio.Future()
        mock_redis.publish.return_value.set_result(True)
        
        agents = {"test_agent": TestAgent()}
        
        pipeline = Pipeline(
            config=mock_pipeline_config,
            agents=agents,
            redis_client=mock_redis
        )
        
        # Execute pipeline
        await pipeline.execute({"test": "events"})
        
        # Check that publish was called
        assert mock_redis.publish.call_count >= 3  # Started, step events, completed
        assert mock_redis.publish.call_args_list[0][0][0] == "pipeline_events"
    
    @pytest.mark.asyncio
    async def test_state_persistence(self, mock_pipeline_config):
        """Test state persistence during pipeline execution."""
        # Create mock database session
        mock_db = AsyncMock()
        mock_db.begin.return_value.__aenter__.return_value.run_sync.return_value = None
        
        agents = {"test_agent": TestAgent()}
        
        # Create pipeline with persistence enabled
        config = mock_pipeline_config.copy()
        config.enable_persistence = True
        
        pipeline = Pipeline(config=config, agents=agents, db_session=mock_db)
        
        # Execute pipeline
        await pipeline.execute({"test": "persistence"})
        
        # Check that save_state was called
        assert mock_db.begin.called
        # Note: In real implementation, would save to database
    
    @pytest.mark.asyncio
    async def test_pipeline_timeout(self, mock_pipeline_config):
        """Test pipeline timeout handling."""
        # Create slow agent
        class SlowAgent(TestAgent):
            async def execute(self, plan):
                await asyncio.sleep(10.0)  # Longer than timeout
                return {"result": "slow completion"}
        
        agents = {"slow_agent": SlowAgent()}
        
        # Create pipeline with short timeout
        config = mock_pipeline_config.copy()
        config.timeout_seconds = 1
        
        pipeline = Pipeline(config=config, agents=agents)
        
        # Execute pipeline
        input_data = {"test": "timeout"}
        result = await pipeline.execute(input_data)
        
        assert result["status"] == "failed"
        assert "timeout" in result.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_create_pipeline_from_config(self, mock_pipeline_config):
        """Test pipeline creation from configuration dictionary."""
        from agents.core.pipeline import create_pipeline_from_config
        
        # Create agents
        agents = {"test_agent": TestAgent()}
        
        # Create pipeline from config
        pipeline = create_pipeline_from_config(
            mock_pipeline_config,
            agents,
            db_session=None,
            redis_client=None
        )
        
        assert pipeline.config.name == mock_pipeline_config["name"]
        assert pipeline.config.mode == PipelineMode(mock_pipeline_config["mode"])
        assert len(pipeline.config.steps) == 2
        assert pipeline._step_map["step1"].agent == agents["test_agent"]
    
    @pytest.mark.asyncio
    async def test_invalid_pipeline_config(self):
        """Test handling of invalid pipeline configuration."""
        from agents.core.pipeline import create_pipeline_from_config
        from baselayer.agents.exceptions import AgentError as BaseLayerError
        
        # Test with missing agent
        invalid_config = {
            "name": "test_pipeline",
            "mode": "sequential",
            "steps": [
                {
                    "name": "step1",
                    "agent": "nonexistent_agent"
                }
            ]
        }
        
        agents = {"test_agent": TestAgent()}
        
        # Should raise error for missing agent
        with pytest.raises(BaseLayerError):
            create_pipeline_from_config(invalid_config, agents)
    
    @pytest.mark.asyncio
    async def test_pipeline_metrics(self, mock_pipeline_config):
        """Test pipeline execution metrics."""
        agents = {"test_agent": TestAgent()}
        
        pipeline = Pipeline(config=mock_pipeline_config, agents=agents)
        
        # Execute pipeline
        result = await pipeline.execute({"test": "metrics"})
        
        # Check metrics in result
        assert "duration_ms" in result
        assert "metadata" in result
        assert "completed_steps" in result["metadata"]
        assert "total_steps" in result["metadata"]
        
        # Check that duration is reasonable
        duration = result["duration_ms"]
        assert duration > 0
        assert duration < 10000  # Should complete in under 10 seconds


class TestPipelineStep:
    """Test suite for PipelineStep functionality."""
    
    def test_step_creation(self):
        """Test pipeline step creation."""
        agent = TestAgent()
        
        step = PipelineStep(
            name="test_step",
            agent=agent,
            condition="test_condition",
            error_handling=ErrorHandling.RETRY,
            max_retries=3,
            retry_backoff="exponential",
            depends_on=["previous_step"]
        )
        
        assert step.name == "test_step"
        assert step.agent == agent
        assert step.condition == "test_condition"
        assert step.error_handling == ErrorHandling.RETRY
        assert step.max_retries == 3
        assert step.retry_backoff == "exponential"
        assert step.depends_on == ["previous_step"]
    
    def test_step_defaults(self):
        """Test pipeline step default values."""
        agent = TestAgent()
        
        step = PipelineStep(
            name="test_step",
            agent=agent
        )
        
        assert step.condition is None
        assert step.error_handling == ErrorHandling.STOP_ON_ERROR
        assert step.max_retries == 3
        assert step.retry_backoff == "exponential"
        assert step.depends_on == []


class TestPipelineConfig:
    """Test suite for PipelineConfig functionality."""
    
    def test_config_creation(self):
        """Test pipeline configuration creation."""
        agent = TestAgent()
        step1 = PipelineStep(name="step1", agent=agent)
        step2 = PipelineStep(name="step2", agent=agent)
        
        config = PipelineConfig(
            name="test_pipeline",
            description="Test pipeline for unit testing",
            steps=[step1, step2],
            mode=PipelineMode.SEQUENTIAL,
            max_concurrent_pipelines=5,
            timeout_seconds=600,
            enable_persistence=True,
            enable_events=True,
            metadata={"test": True}
        )
        
        assert config.name == "test_pipeline"
        assert config.description == "Test pipeline for unit testing"
        assert len(config.steps) == 2
        assert config.mode == PipelineMode.SEQUENTIAL
        assert config.max_concurrent_pipelines == 5
        assert config.timeout_seconds == 600
        assert config.enable_persistence is True
        assert config.enable_events is True
        assert config.metadata["test"] is True
    
    def test_config_defaults(self):
        """Test pipeline configuration default values."""
        agent = TestAgent()
        step = PipelineStep(name="step1", agent=agent)
        
        config = PipelineConfig(
            name="test_pipeline",
            description="Test pipeline",
            steps=[step],
            mode=PipelineMode.SEQUENTIAL
        )
        
        assert config.max_concurrent_pipelines == 3
        assert config.timeout_seconds == 3600
        assert config.enable_persistence is True
        assert config.enable_events is True
        assert config.metadata == {}


class TestPipelineModes:
    """Test suite for pipeline execution modes."""
    
    def test_mode_values(self):
        """Test pipeline mode enum values."""
        assert PipelineMode.SEQUENTIAL.value == "sequential"
        assert PipelineMode.PARALLEL.value == "parallel"
        assert PipelineMode.CONDITIONAL.value == "conditional"
    
    def test_mode_creation(self):
        """Test mode creation from strings."""
        assert PipelineMode("sequential") == PipelineMode.SEQUENTIAL
        assert PipelineMode("parallel") == PipelineMode.PARALLEL
        assert PipelineMode("conditional") == PipelineMode.CONDITIONAL


class TestErrorHandling:
    """Test suite for error handling strategies."""
    
    def test_error_handling_values(self):
        """Test error handling enum values."""
        assert ErrorHandling.STOP_ON_ERROR.value == "stop_on_error"
        assert ErrorHandling.SKIP_AND_CONTINUE.value == "skip_and_continue"
        assert ErrorHandling.RETRY.value == "retry"
    
    def test_error_handling_creation(self):
        """Test error handling creation from strings."""
        assert ErrorHandling("stop_on_error") == ErrorHandling.STOP_ON_ERROR
        assert ErrorHandling("skip_and_continue") == ErrorHandling.SKIP_AND_CONTINUE
        assert ErrorHandling("retry") == ErrorHandling.RETRY
