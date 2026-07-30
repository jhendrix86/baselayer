"""
BaseLayer Agent Base Tests

Test suite for AgentBase class functionality including
lifecycle management, state transitions, and error handling.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from agents.core.agent_base import AgentBase, AgentState, AgentConfig
from agents.core.context import AgentContext
from agents.core.state import StateMachine
from tests.agents.conftest import (
    TestAgent,
    sample_agent_config,
    sample_agent_context,
    assert_valid_agent_state,
    assert_valid_response_structure,
    LogCapture
)


class TestAgentBase:
    """Test suite for AgentBase functionality."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, sample_agent_config):
        """Test agent initialization with configuration."""
        agent = TestAgent(config=sample_agent_config)
        
        assert agent.agent_id is not None
        assert agent.agent_name == "test_agent"
        assert agent.agent_version == "1.0.0"
        assert agent.state == AgentState.IDLE
        assert agent.config == sample_agent_config
        assert agent.run_count == 0
        assert agent.last_run_at is None
        assert agent.created_at is not None
        assert len(agent.state_history) == 1  # Initial state transition
    
    @pytest.mark.asyncio
    async def test_agent_initialization_default_config(self):
        """Test agent initialization with default configuration."""
        agent = TestAgent()
        
        assert agent.config == AgentConfig()
        assert agent.agent_name == "test_agent"
        assert agent.agent_version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_state_transitions(self, sample_agent_config, sample_agent_context):
        """Test valid state transitions."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run agent to test all transitions
        result = await agent.run(sample_agent_context)
        
        # Should have transitioned through all states
        expected_states = [
            AgentState.PLANNING,
            AgentState.EXECUTING,
            AgentState.VALIDATING,
            AgentState.REPORTING,
            AgentState.COMPLETE
        ]
        
        assert_valid_agent_state(agent.state_history, expected_states)
        assert agent.state == AgentState.COMPLETE
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_invalid_state_transition(self, sample_agent_config, sample_agent_context):
        """Test that invalid state transitions are rejected."""
        agent = TestAgent(config=sample_agent_config)
        
        # Try to transition directly to EXECUTING (should fail)
        with pytest.raises(Exception):
            await agent._transition_state(AgentState.EXECUTING)
        
        # Agent should still be in IDLE
        assert agent.state == AgentState.IDLE
    
    @pytest.mark.asyncio
    async def test_plan_phase_execution(self, sample_agent_config, sample_agent_context):
        """Test plan phase execution."""
        agent = TestAgent(config=sample_agent_config)
        
        # Initialize agent
        await agent.initialize(sample_agent_context)
        
        # Execute plan phase
        plan_result = await agent._execute_lifecycle_phase(
            AgentState.PLANNING,
            agent.plan,
            sample_agent_context.input_data
        )
        
        assert plan_result is not None
        assert "plan" in plan_result
        assert "steps" in plan_result
        assert agent.state == AgentState.PLANNING
    
    @pytest.mark.asyncio
    async def test_execute_phase_execution(self, sample_agent_config, sample_agent_context):
        """Test execute phase execution."""
        agent = TestAgent(config=sample_agent_config)
        
        # Initialize agent
        await agent.initialize(sample_agent_context)
        
        # Execute plan phase first
        plan_result = await agent._execute_lifecycle_phase(
            AgentState.PLANNING,
            agent.plan,
            sample_agent_context.input_data
        )
        
        # Execute execute phase
        execute_result = await agent._execute_lifecycle_phase(
            AgentState.EXECUTING,
            agent.execute,
            plan_result
        )
        
        assert execute_result is not None
        assert "result" in execute_result
        assert "success" in execute_result
        assert agent.state == AgentState.EXECUTING
    
    @pytest.mark.asyncio
    async def test_validate_phase_execution(self, sample_agent_config, sample_agent_context):
        """Test validate phase execution."""
        agent = TestAgent(config=sample_agent_config)
        
        # Initialize agent
        await agent.initialize(sample_agent_context)
        
        # Execute plan and execute phases
        plan_result = await agent._execute_lifecycle_phase(
            AgentState.PLANNING,
            agent.plan,
            sample_agent_context.input_data
        )
        
        execute_result = await agent._execute_lifecycle_phase(
            AgentState.EXECUTING,
            agent.execute,
            plan_result
        )
        
        # Execute validate phase
        validate_result = await agent._execute_lifecycle_phase(
            AgentState.VALIDATING,
            agent.validate,
            execute_result
        )
        
        assert validate_result is not None
        assert "valid" in validate_result
        assert validate_result["valid"] is True
        assert agent.state == AgentState.VALIDATING
    
    @pytest.mark.asyncio
    async def test_report_phase_execution(self, sample_agent_config, sample_agent_context):
        """Test report phase execution."""
        agent = TestAgent(config=sample_agent_config)
        
        # Initialize agent
        await agent.initialize(sample_agent_context)
        
        # Execute all phases up to report
        plan_result = await agent._execute_lifecycle_phase(
            AgentState.PLANNING,
            agent.plan,
            sample_agent_context.input_data
        )
        
        execute_result = await agent._execute_lifecycle_phase(
            AgentState.EXECUTING,
            agent.execute,
            plan_result
        )
        
        validate_result = await agent._execute_lifecycle_phase(
            AgentState.VALIDATING,
            agent.validate,
            execute_result
        )
        
        # Execute report phase
        report_result = await agent._execute_lifecycle_phase(
            AgentState.REPORTING,
            agent.report,
            execute_result
        )
        
        assert report_result is not None
        assert "agent_id" in report_result
        assert "execution_time" in report_result
        assert agent.state == AgentState.REPORTING
    
    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, sample_agent_config, sample_agent_context):
        """Test complete agent lifecycle."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run complete lifecycle
        result = await agent.run(sample_agent_context)
        
        # Validate result structure
        assert_valid_response_structure(result)
        
        # Check final state
        assert agent.state == AgentState.COMPLETE
        
        # Check metrics
        assert result["status"] == "success"
        assert "metrics" in result
        assert result["metrics"]["total_runs"] == 1
        assert result["metrics"]["successful_runs"] == 1
        assert result["metrics"]["failed_runs"] == 0
    
    @pytest.mark.asyncio
    async def test_failed_lifecycle(self, sample_agent_config, sample_agent_context):
        """Test failed agent lifecycle."""
        # Create agent that will fail
        class FailingAgent(TestAgent):
            async def execute(self, plan):
                raise Exception("Test failure")
        
        agent = FailingAgent(config=sample_agent_config)
        
        # Run lifecycle
        result = await agent.run(sample_agent_context)
        
        # Validate failure result
        assert result["status"] == "failed"
        assert "error" in result
        assert "error_type" in result
        assert result["error"] == "Test failure"
        assert result["error_type"] == "Exception"
        
        # Check final state
        assert agent.state == AgentState.FAILED
        
        # Check metrics
        assert result["metrics"]["failed_runs"] == 1
        assert result["metrics"]["successful_runs"] == 0
    
    @pytest.mark.asyncio
    async def test_agent_cancellation(self, sample_agent_config, sample_agent_context):
        """Test agent cancellation."""
        agent = TestAgent(config=sample_agent_config)
        
        # Create slow agent for cancellation test
        class SlowAgent(TestAgent):
            async def execute(self, plan):
                await asyncio.sleep(1.0)  # Slow execution
                return {"result": "slow result"}
        
        slow_agent = SlowAgent(config=sample_agent_config)
        
        # Start execution in background
        execution_task = asyncio.create_task(slow_agent.run(sample_agent_context))
        
        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        await slow_agent.cancel()
        
        # Wait for completion
        result = await execution_task
        
        # Should be cancelled
        assert result["status"] == "failed"
        assert "cancelled" in result.get("error", "").lower()
        assert slow_agent.state == AgentState.CANCELLED
    
    @pytest.mark.asyncio
    async def test_memory_tracking(self, sample_agent_config, sample_agent_context):
        """Test memory usage tracking."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run agent
        await agent.run(sample_agent_context)
        
        # Check that memory was tracked
        assert hasattr(agent, '_memory_usage_mb')
        assert agent._memory_usage_mb >= 0
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, sample_agent_config, sample_agent_context):
        """Test metrics tracking across multiple runs."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run agent multiple times
        for i in range(3):
            context = AgentContext(
                task_id=f"task-{i}",
                task_type="test",
                input_data={"iteration": i},
                memory_interface=AsyncMock(),
                config=sample_agent_config,
                request_id=f"request-{i}"
            )
            
            await agent.run(context)
        
        # Check metrics
        metrics = agent._get_execution_metrics()
        assert metrics["total_runs"] == 3
        assert metrics["successful_runs"] == 3
        assert metrics["failed_runs"] == 0
        assert agent.run_count == 3
    
    @pytest.mark.asyncio
    async def test_state_history_tracking(self, sample_agent_config, sample_agent_context):
        """Test state history tracking."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run agent
        await agent.run(sample_agent_context)
        
        # Check state history
        history = agent.state_history
        assert len(history) >= 5  # At least 5 transitions
        
        # Check transition structure
        for transition in history:
            assert transition.from_state is not None or transition.to_state == AgentState.IDLE
            assert transition.to_state is not None
            assert transition.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_get_state_info(self, sample_agent_config):
        """Test state information retrieval."""
        agent = TestAgent(config=sample_agent_config)
        
        # Get state info
        state_info = agent.get_state_info()
        
        # Validate structure
        required_fields = [
            "agent_id", "agent_name", "agent_version",
            "current_state", "created_at", "run_count",
            "last_run_at", "metrics", "state_history"
        ]
        
        for field in required_fields:
            assert field in state_info
        
        # Validate values
        assert state_info["agent_name"] == "test_agent"
        assert state_info["agent_version"] == "1.0.0"
        assert state_info["current_state"] == AgentState.IDLE.value
    
    @pytest.mark.asyncio
    async def test_cleanup_after_execution(self, sample_agent_config, sample_agent_context):
        """Test cleanup after execution."""
        agent = TestAgent(config=sample_agent_config)
        
        # Run agent
        await agent.run(sample_agent_context)
        
        # Check cleanup
        assert agent.current_context is None
        assert agent.execution_start_time is None
    
    @pytest.mark.asyncio
    async def test_error_handling_in_phase(self, sample_agent_config, sample_agent_context):
        """Test error handling within lifecycle phases."""
        # Create agent with failing plan phase
        class FailingPlanAgent(TestAgent):
            async def plan(self, input_data):
                raise ValueError("Plan phase error")
        
        agent = FailingPlanAgent(config=sample_agent_config)
        
        # Run agent
        result = await agent.run(sample_agent_context)
        
        # Should fail in planning phase
        assert result["status"] == "failed"
        assert "Plan phase error" in result.get("error", "")
        assert agent.state == AgentState.FAILED
    
    @pytest.mark.asyncio
    async def test_retry_configuration(self, sample_agent_config, sample_agent_context):
        """Test retry configuration handling."""
        # Test with different retry configurations
        configs = [
            AgentConfig(max_retries=1),
            AgentConfig(max_retries=5),
            AgentConfig(max_retries=0)
        ]
        
        for config in configs:
            agent = TestAgent(config=config)
            
            # Should not raise during initialization
            assert agent.config.max_retries == config.max_retries
    
    @pytest.mark.asyncio
    async def test_timeout_configuration(self, sample_agent_config, sample_agent_context):
        """Test timeout configuration handling."""
        # Test with different timeout configurations
        configs = [
            AgentConfig(timeout_seconds=30),
            AgentConfig(timeout_seconds=300),
            AgentConfig(timeout_seconds=3600)
        ]
        
        for config in configs:
            agent = TestAgent(config=config)
            
            # Should not raise during initialization
            assert agent.config.timeout_seconds == config.timeout_seconds


class TestAgentConfig:
    """Test suite for AgentConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AgentConfig()
        
        assert config.max_retries == 3
        assert config.timeout_seconds == 300
        assert config.memory_limit_mb == 256
        assert config.log_level == "INFO"
        assert config.enable_metrics is True
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test valid configurations
        valid_configs = [
            {"max_retries": 1, "timeout_seconds": 60},
            {"max_retries": 5, "memory_limit_mb": 512},
            {"log_level": "DEBUG", "enable_metrics": False}
        ]
        
        for config_dict in valid_configs:
            config = AgentConfig(**config_dict)
            
            # Should not raise validation errors
            assert config is not None
    
    def test_config_serialization(self):
        """Test configuration serialization."""
        config = AgentConfig(max_retries=2, timeout_seconds=120)
        
        # Test dict conversion
        config_dict = config.dict()
        
        assert config_dict["max_retries"] == 2
        assert config_dict["timeout_seconds"] == 120
        assert isinstance(config_dict, dict)


class TestAgentContext:
    """Test suite for AgentContext."""
    
    def test_context_creation(self, sample_agent_config):
        """Test context creation and immutability."""
        context = AgentContext(
            task_id="test-task",
            task_type="test",
            input_data={"test": "data"},
            memory_interface=AsyncMock(),
            config=sample_agent_config,
            request_id="test-request"
        )
        
        assert context.task_id == "test-task"
        assert context.task_type == "test"
        assert context.input_data == {"test": "data"}
        assert context.config == sample_agent_config
        assert context.request_id == "test-request"
        
        # Test immutability
        with pytest.raises(Exception):
            # Should be frozen dataclass
            context.task_id = "modified"
    
    def test_context_serialization(self, sample_agent_config):
        """Test context serialization."""
        context = AgentContext(
            task_id="test-task",
            task_type="test",
            input_data={"test": "data"},
            memory_interface=AsyncMock(),
            config=sample_agent_config,
            request_id="test-request"
        )
        
        # Test dict conversion
        context_dict = context.to_dict()
        
        assert context_dict["task_id"] == "test-task"
        assert context_dict["task_type"] == "test"
        assert isinstance(context_dict, dict)
    
    def test_context_from_dict(self, sample_agent_config):
        """Test context creation from dictionary."""
        original_context = AgentContext(
            task_id="test-task",
            task_type="test",
            input_data={"test": "data"},
            memory_interface=AsyncMock(),
            config=sample_agent_config,
            request_id="test-request"
        )
        
        # Convert to dict and back
        context_dict = original_context.to_dict()
        restored_context = AgentContext.from_dict(context_dict)
        
        assert restored_context.task_id == original_context.task_id
        assert restored_context.task_type == original_context.task_type
        assert restored_context.input_data == original_context.input_data
    
    def test_context_with_updates(self, sample_agent_config):
        """Test context with updates."""
        context = AgentContext(
            task_id="test-task",
            task_type="test",
            input_data={"test": "data"},
            memory_interface=AsyncMock(),
            config=sample_agent_config,
            request_id="test-request"
        )
        
        # Create updated context
        updated_context = context.with_updates(
            task_id="updated-task",
            metadata={"updated": True}
        )
        
        assert updated_context.task_id == "updated-task"
        assert updated_context.task_type == "test"  # Unchanged
        assert updated_context.metadata == {"updated": True}
        assert updated_context.input_data == {"test": "data"}  # Unchanged
