"""
BaseLayer Agent Base Class

Abstract base class for all agents with lifecycle management,
state machine, and built-in logging.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Import BaseLayer utilities
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)

T = TypeVar('T', bound='AgentBase')


class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Import AgentConfig and AgentContext from context to avoid duplication
from .context import AgentConfig, AgentContext


@dataclass
class StateTransition:
    """Record of state transition with timing."""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    duration_ms: Optional[float] = None
    error: Optional[Exception] = None


class AgentBase(ABC):
    """
    Abstract base class for all agents.
    
    Provides lifecycle management, state machine, logging,
    and common functionality for all agent implementations.
    """
    
    # Class-level configuration
    agent_name: str
    agent_version: str = "1.0.0"
    
    # Valid state transitions
    _valid_transitions: Dict[AgentState, List[AgentState]] = {
        AgentState.IDLE: [AgentState.PLANNING, AgentState.CANCELLED],
        AgentState.PLANNING: [AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.EXECUTING: [AgentState.VALIDATING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.VALIDATING: [AgentState.REPORTING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.REPORTING: [AgentState.COMPLETE, AgentState.FAILED],
        AgentState.COMPLETE: [AgentState.IDLE, AgentState.PLANNING],
        AgentState.FAILED: [AgentState.IDLE, AgentState.PLANNING],
        AgentState.CANCELLED: [AgentState.IDLE],
    }
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        """Initialize agent with configuration."""
        self.agent_id: str = str(uuid.uuid4())
        self.config: AgentConfig = config or AgentConfig()
        self.state: AgentState = AgentState.IDLE
        self.created_at: datetime = datetime.now(timezone.utc)
        self.run_count: int = 0
        self.last_run_at: Optional[datetime] = None
        
        # State tracking
        self.state_history: List[StateTransition] = []
        self.current_context: Optional[AgentContext] = None
        self.execution_start_time: Optional[float] = None
        
        # Metrics
        self.metrics: Dict[str, Any] = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "average_runtime_ms": 0.0,
            "last_error": None,
        }
        
        self.logger = get_logger(f"agent.{self.agent_name}")
        
        # Memory tracking
        self._memory_usage_mb: float = 0.0
        
        self.logger.info(
            "Agent initialized",
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            version=self.agent_version,
            config=self.config.dict()
        )
    
    async def initialize(self, context: AgentContext) -> None:
        """
        Initialize agent with execution context.
        
        Args:
            context: Execution context containing task and configuration
        """
        self.current_context = context
        self.execution_start_time = time.time()
        
        await self._track_memory_usage()
        
        self.logger.info(
            "Agent execution started",
            agent_id=self.agent_id,
            task_id=context.task_id,
            task_type=context.task_type,
            request_id=context.request_id
        )
    
    async def run(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute the full agent lifecycle.
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing execution results and metadata
        """
        try:
            await self.initialize(context)
            
            # Execute lifecycle phases
            plan_result = await self._execute_lifecycle_phase(
                AgentState.PLANNING,
                self.plan,
                context.input_data
            )
            
            if plan_result is None:
                raise BaseLayerError("Plan phase returned None")
            
            execute_result = await self._execute_lifecycle_phase(
                AgentState.EXECUTING,
                self.execute,
                plan_result
            )
            
            if execute_result is None:
                raise BaseLayerError("Execute phase returned None")
            
            validate_result = await self._execute_lifecycle_phase(
                AgentState.VALIDATING,
                self.validate,
                execute_result
            )
            
            if not validate_result.get("valid", False):
                raise BaseLayerError(f"Validation failed: {validate_result.get('error', 'Unknown error')}")
            
            report_result = await self._execute_lifecycle_phase(
                AgentState.REPORTING,
                self.report,
                execute_result
            )
            
            # Mark as complete
            await self._transition_state(AgentState.COMPLETE)
            
            # Update metrics
            self._update_metrics(success=True)
            
            return {
                "status": "success",
                "agent_id": self.agent_id,
                "task_id": context.task_id,
                "result": execute_result,
                "report": report_result,
                "metrics": self._get_execution_metrics(),
                "state_history": [
                    {
                        "from_state": t.from_state.value,
                        "to_state": t.to_state.value,
                        "timestamp": t.timestamp.isoformat(),
                        "duration_ms": t.duration_ms
                    }
                    for t in self.state_history
                ]
            }
            
        except Exception as e:
            self.logger.error(
                "Agent execution failed",
                agent_id=self.agent_id,
                task_id=context.task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            await self._transition_state(AgentState.FAILED, error=e)
            self._update_metrics(success=False, error=e)
            
            return {
                "status": "failed",
                "agent_id": self.agent_id,
                "task_id": context.task_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "metrics": self._get_execution_metrics()
            }
        
        finally:
            await self.cleanup()
    
    async def _execute_lifecycle_phase(
        self,
        target_state: AgentState,
        phase_func: callable,
        input_data: Any
    ) -> Any:
        """
        Execute a lifecycle phase with timing and error handling.
        
        Args:
            target_state: State to transition to
            phase_func: Phase function to execute
            input_data: Data to pass to phase function
            
        Returns:
            Result from phase function
        """
        await self._transition_state(target_state)
        
        start_time = time.time()
        
        try:
            # Check memory usage
            await self._track_memory_usage()
            if self._memory_usage_mb > self.config.memory_limit_mb:
                self.logger.warning(
                    "Memory usage exceeds limit",
                    agent_id=self.agent_id,
                    usage_mb=self._memory_usage_mb,
                    limit_mb=self.config.memory_limit_mb
                )
            
            # Execute phase
            if asyncio.iscoroutinefunction(phase_func):
                result = await phase_func(input_data)
            else:
                result = phase_func(input_data)
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{target_state.value.title()} phase completed",
                agent_id=self.agent_id,
                duration_ms=duration_ms,
                memory_usage_mb=self._memory_usage_mb
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.error(
                f"{target_state.value.title()} phase failed",
                agent_id=self.agent_id,
                duration_ms=duration_ms,
                error=str(e),
                error_type=type(e).__name__
            )
            
            raise
    
    async def _transition_state(
        self,
        new_state: AgentState,
        error: Optional[Exception] = None
    ) -> None:
        """
        Transition to a new state with validation and logging.
        
        Args:
            new_state: State to transition to
            error: Optional error that caused the transition
        """
        if new_state not in self._valid_transitions.get(self.state, []):
            self.logger.error(
                "Invalid state transition",
                agent_id=self.agent_id,
                from_state=self.state.value,
                to_state=new_state.value
            )
            raise BaseLayerError(
                f"Invalid state transition: {self.state.value} -> {new_state.value}"
            )
        
        old_state = self.state
        self.state = new_state
        
        # Calculate duration
        duration_ms = None
        if self.execution_start_time and old_state != AgentState.IDLE:
            duration_ms = (time.time() - self.execution_start_time) * 1000
        
        # Record transition
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error=error
        )
        
        self.state_history.append(transition)
        
        self.logger.info(
            "State transition",
            agent_id=self.agent_id,
            from_state=old_state.value,
            to_state=new_state.value,
            error=str(error) if error else None
        )
    
    async def _track_memory_usage(self) -> None:
        """Track current memory usage."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            self._memory_usage_mb = memory_info.rss / 1024 / 1024
        except ImportError:
            # psutil not available, skip memory tracking
            pass
        except Exception as e:
            self.logger.warning(
                "Failed to track memory usage",
                agent_id=self.agent_id,
                error=str(e)
            )
    
    def _update_metrics(self, success: bool, error: Optional[Exception] = None) -> None:
        """Update agent execution metrics."""
        self.run_count += 1
        self.last_run_at = datetime.now(timezone.utc)
        
        self.metrics["total_runs"] = self.run_count
        
        if success:
            self.metrics["successful_runs"] += 1
        else:
            self.metrics["failed_runs"] += 1
            self.metrics["last_error"] = str(error) if error else None
        
        # Calculate average runtime
        if self.state_history:
            runtimes = [
                t.duration_ms for t in self.state_history
                if t.duration_ms is not None and t.to_state == AgentState.COMPLETE
            ]
            if runtimes:
                self.metrics["average_runtime_ms"] = sum(runtimes) / len(runtimes)
    
    def _get_execution_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics."""
        return {
            **self.metrics,
            "current_state": self.state.value,
            "memory_usage_mb": self._memory_usage_mb,
            "run_count": self.run_count,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None
        }
    
    # Abstract methods that subclasses MUST implement
    
    @abstractmethod
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan the execution approach.
        
        Args:
            input_data: Input data for planning
            
        Returns:
            Dict containing execution plan
        """
        pass
    
    @abstractmethod
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the planned approach.
        
        Args:
            plan: Execution plan from plan() phase
            
        Returns:
            Dict containing execution results
        """
        pass
    
    # Default implementations (can be overridden)
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate execution results.
        
        Args:
            result: Results from execute() phase
            
        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        return {
            "valid": True,
            "error": None
        }
    
    async def report(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report execution results.
        
        Args:
            result: Results from execute() phase
            
        Returns:
            Dict containing report data
        """
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "result_summary": result.get("summary", "Execution completed"),
            "metrics": self._get_execution_metrics()
        }
    
    async def cleanup(self) -> None:
        """Clean up resources after execution."""
        self.current_context = None
        self.execution_start_time = None
        
        self.logger.info(
            "Agent cleanup completed",
            agent_id=self.agent_id
        )
    
    async def cancel(self) -> None:
        """Cancel current execution."""
        if self.state in [AgentState.IDLE, AgentState.COMPLETE, AgentState.FAILED, AgentState.CANCELLED]:
            return
        
        await self._transition_state(AgentState.CANCELLED)
        
        self.logger.info(
            "Agent execution cancelled",
            agent_id=self.agent_id
        )
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "current_state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "run_count": self.run_count,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "metrics": self._get_execution_metrics(),
            "state_history": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "duration_ms": t.duration_ms
                }
                for t in self.state_history[-10:]  # Last 10 transitions
            ]
        }
