"""
BaseLayer Workflow Engine

Core workflow orchestration engine with dependency resolution,
execution management, and state tracking.
"""

import asyncio
import uuid
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ..core.database import db_session_context
from ..models.core_loop import (
    Workflow, WorkflowExecution, WorkflowStep, WorkflowStepExecution,
    WorkflowStatus, WorkflowPriority, StepType
)
from ..models.user import User
from .exceptions import (
    WorkflowEngineError,
    WorkflowExecutionError,
    WorkflowValidationError,
    WorkflowDependencyError,
    WorkflowTimeoutError,
    WorkflowGovernanceError
)
from .failure_emitter import FailureEventEmitter, FailureSeverity, FailureType

logger = get_logger(__name__)


class WorkflowEngine:
    """
    Core workflow orchestration engine.
    
    Manages workflow execution, dependency resolution, and state tracking
    with optimized performance for i5-2400 hardware.
    """
    
    def __init__(self):
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_queue: asyncio.Queue = asyncio.Queue()
        self.max_concurrent_executions: int = 4  # Optimized for i5-2400
        self.execution_semaphore = asyncio.Semaphore(self.max_concurrent_executions)

        # Initialize failure event emitter
        rabbitmq_url = os.getenv("RABBITMQ_URL")
        self.failure_emitter = FailureEventEmitter(rabbitmq_url)

    async def connect(self):
        """Connect to external services"""
        await self.failure_emitter.connect()
        logger.info("workflow_engine_connected")

    async def disconnect(self):
        """Disconnect from external services"""
        await self.failure_emitter.disconnect()
        logger.info("workflow_engine_disconnected")
    
    async def start_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None
    ) -> WorkflowExecution:
        """
        Start a new workflow execution.
        
        Args:
            workflow_id: ID of the workflow to execute
            input_data: Input data for the workflow
            user_id: ID of the user starting the workflow
            
        Returns:
            WorkflowExecution: The created execution record
            
        Raises:
            WorkflowValidationError: If workflow validation fails
            WorkflowGovernanceError: If governance checks fail
        """
        async with db_session_context() as session:
            # Get workflow
            result = await session.execute(
                select(Workflow).where(
                    Workflow.id == uuid.UUID(workflow_id),
                    Workflow.deleted_at.is_(None)
                )
            )
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise WorkflowValidationError(f"Workflow not found: {workflow_id}")
            
            if not workflow.can_execute:
                raise WorkflowValidationError(
                    f"Workflow cannot be executed in status: {workflow.status}"
                )
            
            # Validate input data
            await self._validate_workflow_input(workflow, input_data)
            
            # Check governance requirements
            await self._check_governance_requirements(workflow, user_id)
            
            # Create execution record
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                execution_id=str(uuid.uuid4()),
                input_data=input_data,
                status=WorkflowStatus.ACTIVE,
                created_by=user_id
            )
            
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            
            # Start execution
            execution.start(input_data)
            session.add(execution)
            await session.commit()
            
            # Add to active executions
            self.active_executions[execution.execution_id] = execution
            
            # Queue for execution
            await self.execution_queue.put(execution)
            
            logger.info(
                "Workflow started",
                workflow_id=workflow_id,
                execution_id=execution.execution_id,
                user_id=str(user_id) if user_id else None
            )
            
            return execution
    
    async def _validate_workflow_input(
        self,
        workflow: Workflow,
        input_data: Dict[str, Any]
    ) -> None:
        """
        Validate workflow input data.
        
        Args:
            workflow: Workflow definition
            input_data: Input data to validate
            
        Raises:
            WorkflowValidationError: If validation fails
        """
        validation_errors = []
        
        # Check required variables
        workflow_config = workflow.config or {}
        variables = workflow_config.get("variables", {})
        
        for var_name, var_config in variables.items():
            if var_config.get("required", False) and var_name not in input_data:
                validation_errors.append(f"Required variable '{var_name}' is missing")
        
        # Type validation
        for var_name, var_config in variables.items():
            if var_name in input_data:
                expected_type = var_config.get("type")
                value = input_data[var_name]
                
                if expected_type == "string" and not isinstance(value, str):
                    validation_errors.append(f"Variable '{var_name}' must be a string")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    validation_errors.append(f"Variable '{var_name}' must be a number")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    validation_errors.append(f"Variable '{var_name}' must be a boolean")
                elif expected_type == "array" and not isinstance(value, list):
                    validation_errors.append(f"Variable '{var_name}' must be an array")
                elif expected_type == "object" and not isinstance(value, dict):
                    validation_errors.append(f"Variable '{var_name}' must be an object")
        
        if validation_errors:
            raise WorkflowValidationError(
                f"Workflow input validation failed: {'; '.join(validation_errors)}",
                validation_errors=validation_errors
            )
    
    async def _check_governance_requirements(
        self,
        workflow: Workflow,
        user_id: Optional[uuid.UUID] = None
    ) -> None:
        """
        Check governance requirements for workflow execution.
        
        Args:
            workflow: Workflow definition
            user_id: ID of the user executing the workflow
            
        Raises:
            WorkflowGovernanceError: If governance checks fail
        """
        if not workflow.governance_required:
            return
        
        async with db_session_context() as session:
            # Check user permissions
            if user_id:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    raise WorkflowGovernanceError(
                        "User not found for governance check",
                        governance_rules=["user_authentication"]
                    )
                
                # Check if user can execute workflows
                if not user.can_create_workflows:
                    raise WorkflowGovernanceError(
                        "User lacks permission to execute workflows",
                        governance_rules=["workflow_execution_permission"],
                        compliance_level=user.compliance_level
                    )
            
            # TODO: Check additional governance rules
            # This would involve checking specific governance rules
            # based on the workflow category and compliance level
    
    async def execute_workflow(self, execution: WorkflowExecution) -> None:
        """
        Execute a workflow with dependency resolution.

        Args:
            execution: Workflow execution record
        """
        async with self.execution_semaphore:
            try:
                await self._execute_workflow_steps(execution)
            except Exception as e:
                logger.error(
                    "Workflow execution failed",
                    execution_id=execution.execution_id,
                    error=str(e)
                )

                # Emit failure event
                failure_type, severity = FailureEventEmitter.classify_exception(e)
                import traceback
                stack_trace = traceback.format_exc()

                await self.failure_emitter.emit_failure_detected(
                    failure_id=execution.execution_id,
                    failure_type=failure_type,
                    severity=severity,
                    component="workflow-engine",
                    error_message=str(e),
                    stack_trace=stack_trace,
                    context={
                        "workflow_id": str(execution.workflow_id),
                        "execution_id": execution.execution_id,
                    },
                    affected_operations=[
                        "workflow.execute",
                        f"workflow.{execution.workflow_id}",
                    ],
                    is_retriable=failure_type != FailureType.VALIDATION,
                )

                execution.fail(str(e))

                # Remove from active executions
                self.active_executions.pop(execution.execution_id, None)
    
    async def _execute_workflow_steps(self, execution: WorkflowExecution) -> None:
        """
        Execute workflow steps with dependency resolution.
        
        Args:
            execution: Workflow execution record
        """
        async with db_session_context() as session:
            # Get workflow and steps
            result = await session.execute(
                select(Workflow).where(Workflow.id == execution.workflow_id)
            )
            workflow = result.scalar_one()
            
            workflow_config = workflow.config or {}
            steps = workflow_config.get("steps", [])
            
            if not steps:
                execution.complete({})
                return
            
            # Build dependency graph
            dependency_graph = self._build_dependency_graph(steps)
            
            # Execute steps in dependency order
            completed_steps: Set[str] = set()
            failed_steps: Set[str] = set()
            step_results: Dict[str, Any] = {}
            
            while len(completed_steps) + len(failed_steps) < len(steps):
                # Find steps ready for execution
                ready_steps = [
                    step for step in steps
                    if step["id"] not in completed_steps
                    and step["id"] not in failed_steps
                    and all(
                        dep in completed_steps
                        for dep in step.get("dependencies", [])
                    )
                ]
                
                if not ready_steps:
                    # Check for circular dependencies
                    remaining_steps = [
                        step["id"] for step in steps
                        if step["id"] not in completed_steps
                        and step["id"] not in failed_steps
                    ]
                    
                    if remaining_steps:
                        raise WorkflowDependencyError(
                            "Circular dependency detected in workflow",
                            dependency_graph=dependency_graph
                        )
                    break
                
                # Execute ready steps (can be parallelized)
                tasks = []
                for step in ready_steps:
                    task = self._execute_step(
                        execution,
                        step,
                        step_results,
                        completed_steps,
                        failed_steps
                    )
                    tasks.append(task)
                
                # Wait for all steps to complete
                step_results_batch = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(step_results_batch):
                    step_id = ready_steps[i]["id"]
                    
                    if isinstance(result, Exception):
                        failed_steps.add(step_id)
                        logger.error(
                            "Step execution failed",
                            execution_id=execution.execution_id,
                            step_id=step_id,
                            error=str(result)
                        )
                    else:
                        completed_steps.add(step_id)
                        step_results[step_id] = result
                
                # Update progress
                progress = int((len(completed_steps) / len(steps)) * 100)
                execution.update_progress("", progress)
                
                # Check for timeout
                if execution.started_at:
                    elapsed = datetime.utcnow() - execution.started_at
                    timeout_seconds = int(workflow.timeout_seconds or 3600)
                    
                    if elapsed.total_seconds() > timeout_seconds:
                        raise WorkflowTimeoutError(
                            f"Workflow execution timed out after {timeout_seconds} seconds",
                            timeout_seconds=timeout_seconds
                        )
            
            # Determine final status
            if failed_steps:
                execution.fail(
                    f"Workflow failed: {len(failed_steps)} steps failed",
                    {"failed_steps": list(failed_steps)}
                )
            else:
                execution.complete(step_results)
            
            # Remove from active executions
            self.active_executions.pop(execution.execution_id, None)
    
    def _build_dependency_graph(self, steps: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Build dependency graph from workflow steps.
        
        Args:
            steps: List of workflow steps
            
        Returns:
            Dict[str, List[str]]: Dependency graph
        """
        dependency_graph = {}
        
        for step in steps:
            step_id = step["id"]
            dependencies = step.get("dependencies", [])
            dependency_graph[step_id] = dependencies
        
        return dependency_graph
    
    async def _execute_step(
        self,
        execution: WorkflowExecution,
        step: Dict[str, Any],
        step_results: Dict[str, Any],
        completed_steps: Set[str],
        failed_steps: Set[str]
    ) -> Any:
        """
        Execute a single workflow step.
        
        Args:
            execution: Workflow execution record
            step: Step definition
            step_results: Results from previous steps
            completed_steps: Set of completed step IDs
            failed_steps: Set of failed step IDs
            
        Returns:
            Any: Step execution result
        """
        step_id = step["id"]
        step_type = step.get("type", "task")
        step_config = step.get("config", {})
        timeout = step.get("timeout", 300)
        
        logger.info(
            "Executing step",
            execution_id=execution.execution_id,
            step_id=step_id,
            step_type=step_type
        )
        
        try:
            # Execute based on step type
            if step_type == "task":
                result = await self._execute_task_step(
                    execution, step_id, step_config, step_results
                )
            elif step_type == "decision":
                result = await self._execute_decision_step(
                    execution, step_id, step_config, step_results
                )
            elif step_type == "delay":
                result = await self._execute_delay_step(
                    execution, step_id, step_config
                )
            elif step_type == "webhook":
                result = await self._execute_webhook_step(
                    execution, step_id, step_config, step_results
                )
            elif step_type == "agent":
                result = await self._execute_agent_step(
                    execution, step_id, step_config, step_results
                )
            else:
                raise WorkflowExecutionError(
                    f"Unknown step type: {step_type}",
                    step_id=step_id
                )
            
            logger.info(
                "Step completed successfully",
                execution_id=execution.execution_id,
                step_id=step_id
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Step execution failed",
                execution_id=execution.execution_id,
                step_id=step_id,
                error=str(e)
            )
            raise WorkflowExecutionError(
                f"Step execution failed: {str(e)}",
                step_id=step_id
            ) from e
    
    async def _execute_task_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
        config: Dict[str, Any],
        step_results: Dict[str, Any]
    ) -> Any:
        """Execute a task step."""
        # TODO: Implement actual task execution logic
        # This would involve calling specific task handlers
        await asyncio.sleep(0.1)  # Simulate work
        return {"status": "completed", "output": f"Task {step_id} completed"}
    
    async def _execute_decision_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
        config: Dict[str, Any],
        step_results: Dict[str, Any]
    ) -> Any:
        """Execute a decision step."""
        # TODO: Implement decision logic
        condition = config.get("condition", "true")
        return {"decision": condition == "true", "condition": condition}
    
    async def _execute_delay_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
        config: Dict[str, Any]
    ) -> Any:
        """Execute a delay step."""
        delay_seconds = config.get("seconds", 1)
        await asyncio.sleep(delay_seconds)
        return {"status": "completed", "delayed": delay_seconds}
    
    async def _execute_webhook_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
        config: Dict[str, Any],
        step_results: Dict[str, Any]
    ) -> Any:
        """Execute a webhook step."""
        # TODO: Implement webhook call
        url = config.get("url", "https://example.com/webhook")
        return {"status": "completed", "webhook_url": url}
    
    async def _execute_agent_step(
        self,
        execution: WorkflowExecution,
        step_id: str,
        config: Dict[str, Any],
        step_results: Dict[str, Any]
    ) -> Any:
        """Execute an agent step."""
        # TODO: Implement agent execution
        agent_type = config.get("agent_type", "worker")
        return {"status": "completed", "agent_type": agent_type}
    
    async def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """
        Get the status of a workflow execution.
        
        Args:
            execution_id: ID of the execution
            
        Returns:
            WorkflowExecution: Execution record or None if not found
        """
        # Check active executions first
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]
        
        # Check database
        async with db_session_context() as session:
            result = await session.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id
                )
            )
            return result.scalar_one_or_none()
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a workflow execution.
        
        Args:
            execution_id: ID of the execution to cancel
            
        Returns:
            bool: True if cancelled successfully
        """
        execution = await self.get_execution_status(execution_id)
        
        if not execution:
            return False
        
        if execution.is_completed:
            return False
        
        execution.cancel()
        
        # Remove from active executions
        self.active_executions.pop(execution_id, None)
        
        logger.info(
            "Workflow execution cancelled",
            execution_id=execution_id
        )
        
        return True
    
    async def get_active_executions(self) -> List[WorkflowExecution]:
        """
        Get all active workflow executions.
        
        Returns:
            List[WorkflowExecution]: List of active executions
        """
        return list(self.active_executions.values())
    
    async def start_execution_worker(self) -> None:
        """Start the background execution worker."""
        logger.info("Starting workflow execution worker")
        
        while True:
            try:
                # Get next execution from queue
                execution = await self.execution_queue.get()
                
                # Execute workflow
                await self.execute_workflow(execution)
                
            except Exception as e:
                logger.error(
                    "Execution worker error",
                    error=str(e)
                )
                await asyncio.sleep(5)  # Brief pause before continuing
