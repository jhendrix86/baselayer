"""
BaseLayer Pipeline Runner

Orchestrates multiple agents with different execution modes,
state persistence, and event emission.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .agent_base import AgentBase, AgentState
from .context import AgentContext
from .state import AgentState
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class PipelineMode(Enum):
    """Pipeline execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class ErrorHandling(Enum):
    """Error handling strategies."""
    STOP_ON_ERROR = "stop_on_error"
    SKIP_AND_CONTINUE = "skip_and_continue"
    RETRY = "retry"


@dataclass
class PipelineStep:
    """Single step in a pipeline."""
    name: str
    agent: AgentBase
    condition: Optional[str] = None  # Conditional expression
    error_handling: ErrorHandling = ErrorHandling.STOP_ON_ERROR
    max_retries: int = 3
    retry_backoff: str = "exponential"
    depends_on: List[str] = field(default_factory=list)  # Step dependencies


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    name: str
    description: str
    steps: List[PipelineStep]
    mode: PipelineMode
    max_concurrent_pipelines: int = 3
    timeout_seconds: int = 3600  # 1 hour default
    enable_persistence: bool = True
    enable_events: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineState:
    """Pipeline execution state."""
    pipeline_id: str
    config: PipelineConfig
    status: str  # RUNNING, COMPLETED, FAILED, CANCELLED
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    step_errors: Dict[str, Exception] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """
    Pipeline runner for orchestrating multiple agents.
    
    Supports sequential, parallel, and conditional execution
    with state persistence and event emission.
    """
    
    def __init__(
        self,
        config: PipelineConfig,
        db_session: Optional[AsyncSession] = None,
        redis_client: Optional[Any] = None
    ) -> None:
        """Initialize pipeline with configuration."""
        self.config = config
        self.db_session = db_session
        self.redis_client = redis_client
        self.pipeline_id: str = str(uuid.uuid4())
        
        # Execution state
        self.state: PipelineState = PipelineState(
            pipeline_id=self.pipeline_id,
            config=config,
            status="INITIALIZED"
        )
        
        # Event tracking
        self.events: List[Dict[str, Any]] = []
        
        # Cancellation handling
        self._cancel_event = asyncio.Event()
        self._execution_task: Optional[asyncio.Task] = None
        
        # Step lookup
        self._step_map: Dict[str, PipelineStep] = {
            step.name: step for step in config.steps
        }
        
        logger.info(
            "Pipeline initialized",
            pipeline_id=self.pipeline_id,
            name=config.name,
            mode=config.mode.value,
            steps=len(config.steps)
        )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """
        Execute the pipeline with input data.
        
        Args:
            input_data: Input data for the pipeline
            context: Optional execution context
            
        Returns:
            Dict containing execution results and metadata
        """
        try:
            # Initialize execution
            self.state.status = "RUNNING"
            self.state.started_at = datetime.now(timezone.utc)
            
            await self._emit_event("pipeline_started", {
                "pipeline_id": self.pipeline_id,
                "config": self.config.name,
                "input_data": input_data
            })
            
            # Save initial state if persistence enabled
            if self.config.enable_persistence and self.db_session:
                await self._save_state()
            
            # Execute based on mode
            if self.config.mode == PipelineMode.SEQUENTIAL:
                result = await self._execute_sequential(input_data, context)
            elif self.config.mode == PipelineMode.PARALLEL:
                result = await self._execute_parallel(input_data, context)
            elif self.config.mode == PipelineMode.CONDITIONAL:
                result = await self._execute_conditional(input_data, context)
            else:
                raise BaseLayerError(f"Unsupported pipeline mode: {self.config.mode}")
            
            # Mark completion
            self.state.status = "COMPLETED"
            self.state.completed_at = datetime.now(timezone.utc)
            
            await self._emit_event("pipeline_completed", {
                "pipeline_id": self.pipeline_id,
                "result": result,
                "duration_ms": self._get_duration_ms()
            })
            
            # Save final state
            if self.config.enable_persistence and self.db_session:
                await self._save_state()
            
            return {
                "status": "success",
                "pipeline_id": self.pipeline_id,
                "config": self.config.name,
                "result": result,
                "step_results": self.state.step_results,
                "duration_ms": self._get_duration_ms(),
                "metadata": {
                    "completed_steps": self.state.completed_steps,
                    "failed_steps": self.state.failed_steps,
                    "total_steps": len(self.config.steps)
                }
            }
            
        except Exception as e:
            self.state.status = "FAILED"
            self.state.completed_at = datetime.now(timezone.utc)
            
            logger.error(
                "Pipeline execution failed",
                pipeline_id=self.pipeline_id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            await self._emit_event("pipeline_failed", {
                "pipeline_id": self.pipeline_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": self._get_duration_ms()
            })
            
            # Save error state
            if self.config.enable_persistence and self.db_session:
                await self._save_state()
            
            return {
                "status": "failed",
                "pipeline_id": self.pipeline_id,
                "config": self.config.name,
                "error": str(e),
                "error_type": type(e).__name__,
                "step_results": self.state.step_results,
                "step_errors": {
                    step: str(error) for step, error in self.state.step_errors.items()
                },
                "duration_ms": self._get_duration_ms()
            }
    
    async def _execute_sequential(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """Execute steps sequentially."""
        current_data = input_data
        
        for step in self.config.steps:
            if self._cancel_event.is_set():
                raise BaseLayerError("Pipeline cancelled")
            
            # Check dependencies
            if not self._check_dependencies(step):
                logger.warning(
                    "Skipping step due to unmet dependencies",
                    pipeline_id=self.pipeline_id,
                    step=step.name,
                    dependencies=step.depends_on
                )
                continue
            
            # Check condition
            if step.condition and not self._evaluate_condition(step.condition, current_data):
                logger.info(
                    "Skipping step due to failed condition",
                    pipeline_id=self.pipeline_id,
                    step=step.name,
                    condition=step.condition
                )
                continue
            
            # Execute step
            result = await self._execute_step(step, current_data, context)
            current_data = result
            
            # Update pipeline state
            self.state.step_results[step.name] = result
            self.state.completed_steps.append(step.name)
            self.state.current_step = None
            
            # Save state after each step
            if self.config.enable_persistence and self.db_session:
                await self._save_state()
        
        return current_data
    
    async def _execute_parallel(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """Execute steps in parallel."""
        # Group steps by dependencies
        independent_steps = [
            step for step in self.config.steps
            if not step.depends_on
        ]
        
        # Execute independent steps in parallel
        tasks = []
        for step in independent_steps:
            if self._cancel_event.is_set():
                raise BaseLayerError("Pipeline cancelled")
            
            task = asyncio.create_task(
                self._execute_step(step, input_data, context)
            )
            tasks.append((step.name, task))
        
        # Wait for all tasks
        results = {}
        for step_name, task in tasks:
            try:
                result = await task
                results[step_name] = result
                self.state.completed_steps.append(step_name)
            except Exception as e:
                self.state.failed_steps.append(step_name)
                self.state.step_errors[step_name] = e
                logger.error(
                    "Parallel step failed",
                    pipeline_id=self.pipeline_id,
                    step=step_name,
                    error=str(e)
                )
        
        # Merge results
        self.state.step_results.update(results)
        
        return {
            "parallel_results": results,
            "input_data": input_data
        }
    
    async def _execute_conditional(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """Execute steps with conditional logic."""
        current_data = input_data
        
        for step in self.config.steps:
            if self._cancel_event.is_set():
                raise BaseLayerError("Pipeline cancelled")
            
            # Check dependencies
            if not self._check_dependencies(step):
                continue
            
            # Evaluate condition
            if step.condition:
                if not self._evaluate_condition(step.condition, current_data):
                    logger.info(
                        "Conditional step skipped",
                        pipeline_id=self.pipeline_id,
                        step=step.name,
                        condition=step.condition
                    )
                    continue
            
            # Execute step
            result = await self._execute_step(step, current_data, context)
            current_data = result
            
            # Update state
            self.state.step_results[step.name] = result
            self.state.completed_steps.append(step.name)
            self.state.current_step = None
        
        return current_data
    
    async def _execute_step(
        self,
        step: PipelineStep,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """
        Execute a single pipeline step.
        
        Args:
            step: Pipeline step to execute
            input_data: Input data for the step
            context: Execution context
            
        Returns:
            Step execution result
        """
        self.state.current_step = step.name
        
        await self._emit_event("step_started", {
            "pipeline_id": self.pipeline_id,
            "step": step.name,
            "agent": step.agent.agent_name
        })
        
        # Create step context
        step_context = AgentContext(
            task_id=f"{self.pipeline_id}_{step.name}",
            task_type=f"pipeline_step_{step.name}",
            input_data=input_data,
            memory_interface=context.memory_interface if context else None,
            config=step.agent.config,
            request_id=context.request_id if context else str(uuid.uuid4()),
            parent_agent_id=None,
            pipeline_id=self.pipeline_id,
            metadata={
                "pipeline_name": self.config.name,
                "step_name": step.name,
                "step_config": {
                    "error_handling": step.error_handling.value,
                    "max_retries": step.max_retries
                }
            }
        )
        
        # Execute with retry logic
        last_error = None
        for attempt in range(step.max_retries + 1):
            try:
                result = await step.agent.run(step_context)
                
                await self._emit_event("step_completed", {
                    "pipeline_id": self.pipeline_id,
                    "step": step.name,
                    "attempt": attempt + 1,
                    "result": result
                })
                
                return result.get("result", {})
                
            except Exception as e:
                last_error = e
                
                if attempt < step.max_retries:
                    wait_time = self._calculate_backoff(attempt, step.retry_backoff)
                    
                    logger.warning(
                        "Step failed, retrying",
                        pipeline_id=self.pipeline_id,
                        step=step.name,
                        attempt=attempt + 1,
                        max_retries=step.max_retries,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(wait_time)
                else:
                    self.state.failed_steps.append(step.name)
                    self.state.step_errors[step.name] = e
                    
                    await self._emit_event("step_failed", {
                        "pipeline_id": self.pipeline_id,
                        "step": step.name,
                        "attempts": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                    
                    # Handle error based on strategy
                    if step.error_handling == ErrorHandling.STOP_ON_ERROR:
                        raise BaseLayerError(
                            f"Step {step.name} failed: {str(e)}"
                        ) from e
                    elif step.error_handling == ErrorHandling.SKIP_AND_CONTINUE:
                        logger.warning(
                            "Step failed, skipping",
                            pipeline_id=self.pipeline_id,
                            step=step.name,
                            error=str(e)
                        )
                        return input_data
        
        # Should not reach here
        raise BaseLayerError(
            f"Step {step.name} failed after {step.max_retries + 1} attempts: {str(last_error)}"
        )
    
    def _check_dependencies(self, step: PipelineStep) -> bool:
        """Check if step dependencies are satisfied."""
        for dep in step.depends_on:
            if dep not in self.state.completed_steps:
                return False
        return True
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """
        Evaluate a conditional expression.
        
        Args:
            condition: Conditional expression string
            data: Data to evaluate against
            
        Returns:
            Boolean result of condition evaluation
        """
        try:
            # Simple evaluation - in production, use a safer expression evaluator
            # For now, support basic key existence and value checks
            if "==" in condition:
                key, value = condition.split("==", 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                
                # Get nested value
                current = data
                for part in key.split('.'):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False
                
                return str(current) == value
            
            elif "exists" in condition:
                key = condition.replace("exists", "").strip()
                current = data
                for part in key.split('.'):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False
                return True
            
            return True
            
        except Exception as e:
            logger.warning(
                "Condition evaluation failed",
                pipeline_id=self.pipeline_id,
                condition=condition,
                error=str(e)
            )
            return False
    
    def _calculate_backoff(self, attempt: int, strategy: str) -> float:
        """Calculate retry backoff time."""
        if strategy == "exponential":
            return 2 ** attempt  # 1, 2, 4, 8...
        elif strategy == "linear":
            return attempt + 1  # 1, 2, 3, 4...
        else:
            return 1.0  # Default
    
    def _get_duration_ms(self) -> Optional[float]:
        """Get pipeline execution duration in milliseconds."""
        if self.state.started_at:
            end = self.state.completed_at or datetime.now(timezone.utc)
            return (end - self.state.started_at).total_seconds() * 1000
        return None
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit pipeline event via Redis pub/sub."""
        if not self.config.enable_events or not self.redis_client:
            return
        
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline_id": self.pipeline_id,
            **data
        }
        
        try:
            await self.redis_client.publish("pipeline_events", json.dumps(event))
            self.events.append(event)
        except Exception as e:
            logger.warning(
                "Failed to emit pipeline event",
                pipeline_id=self.pipeline_id,
                event_type=event_type,
                error=str(e)
            )
    
    async def _save_state(self) -> None:
        """Save pipeline state to database."""
        if not self.db_session:
            return
        
        try:
            # In a real implementation, would save to a pipeline_state table
            # For now, just log the state
            logger.debug(
                "Pipeline state saved",
                pipeline_id=self.pipeline_id,
                status=self.state.status,
                completed_steps=len(self.state.completed_steps),
                failed_steps=len(self.state.failed_steps)
            )
        except Exception as e:
            logger.error(
                "Failed to save pipeline state",
                pipeline_id=self.pipeline_id,
                error=str(e)
            )
    
    async def cancel(self) -> None:
        """Cancel pipeline execution."""
        self._cancel_event.set()
        
        # Cancel all running agents
        for step in self.config.steps:
            await step.agent.cancel()
        
        self.state.status = "CANCELLED"
        
        await self._emit_event("pipeline_cancelled", {
            "pipeline_id": self.pipeline_id
        })
        
        logger.info(
            "Pipeline cancelled",
            pipeline_id=self.pipeline_id
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status."""
        return {
            "pipeline_id": self.pipeline_id,
            "config": {
                "name": self.config.name,
                "description": self.config.description,
                "mode": self.config.mode.value
            },
            "status": self.state.status,
            "current_step": self.state.current_step,
            "completed_steps": self.state.completed_steps,
            "failed_steps": self.state.failed_steps,
            "total_steps": len(self.config.steps),
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "completed_at": self.state.completed_at.isoformat() if self.state.completed_at else None,
            "duration_ms": self._get_duration_ms(),
            "metadata": self.state.metadata
        }


# Factory function for creating pipelines from config
def create_pipeline_from_config(
    config_dict: Dict[str, Any],
    agents: Dict[str, AgentBase],
    db_session: Optional[AsyncSession] = None,
    redis_client: Optional[Any] = None
) -> Pipeline:
    """
    Create a pipeline from configuration dictionary.
    
    Args:
        config_dict: Pipeline configuration
        agents: Dictionary of available agents
        db_session: Database session
        redis_client: Redis client
        
    Returns:
        Configured Pipeline instance
    """
    steps = []
    for step_config in config_dict.get("steps", []):
        agent_name = step_config.get("agent")
        if agent_name not in agents:
            raise BaseLayerError(f"Agent not found: {agent_name}")
        
        step = PipelineStep(
            name=step_config["name"],
            agent=agents[agent_name],
            condition=step_config.get("condition"),
            error_handling=ErrorHandling(
                step_config.get("error_handling", "stop_on_error")
            ),
            max_retries=step_config.get("max_retries", 3),
            retry_backoff=step_config.get("retry_backoff", "exponential"),
            depends_on=step_config.get("depends_on", [])
        )
        steps.append(step)
    
    config = PipelineConfig(
        name=config_dict["name"],
        description=config_dict["description"],
        steps=steps,
        mode=PipelineMode(config_dict["mode"]),
        max_concurrent_pipelines=config_dict.get("max_concurrent_pipelines", 3),
        timeout_seconds=config_dict.get("timeout_seconds", 3600),
        enable_persistence=config_dict.get("enable_persistence", True),
        enable_events=config_dict.get("enable_events", True),
        metadata=config_dict.get("metadata", {})
    )
    
    return Pipeline(config, db_session, redis_client)
