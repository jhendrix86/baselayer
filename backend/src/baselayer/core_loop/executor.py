"""
BaseLayer Workflow Executor

Handles individual workflow step execution with retry logic
and error handling optimized for i5-2400 hardware.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable

from structlog import get_logger

from ..models.core_loop import WorkflowStepExecution, TaskStatus, StepType
from .exceptions import WorkflowExecutionError, WorkflowTimeoutError

logger = get_logger(__name__)


class WorkflowExecutor:
    """
    Individual workflow step executor.
    
    Handles step execution, retry logic, and error handling
    with resource optimization for i5-2400 hardware.
    """
    
    def __init__(self):
        self.step_handlers: Dict[str, Callable] = {}
        self.register_default_handlers()
    
    def register_handler(
        self,
        step_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ) -> None:
        """
        Register a custom step handler.
        
        Args:
            step_type: Type of step
            handler: Async handler function
        """
        self.step_handlers[step_type] = handler
        logger.info("Step handler registered", step_type=step_type)
    
    def register_default_handlers(self) -> None:
        """Register default step handlers."""
        self.step_handlers.update({
            "task": self._handle_task_step,
            "decision": self._handle_decision_step,
            "delay": self._handle_delay_step,
            "webhook": self._handle_webhook_step,
            "agent": self._handle_agent_step,
            "parallel": self._handle_parallel_step,
        })
    
    async def execute_step(
        self,
        step_execution: WorkflowStepExecution,
        step_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """
        Execute a workflow step with retry logic.
        
        Args:
            step_execution: Step execution record
            step_config: Step configuration
            context: Execution context
            
        Returns:
            Any: Step execution result
            
        Raises:
            WorkflowExecutionError: If step execution fails
        """
        step_type = step_config.get("type", "task")
        handler = self.step_handlers.get(step_type)
        
        if not handler:
            raise WorkflowExecutionError(
                f"No handler registered for step type: {step_type}",
                step_id=step_execution.step_id
            )
        
        # Get retry policy
        retry_policy = step_config.get("retry_policy", {})
        max_retries = retry_policy.get("max_attempts", 3)
        backoff_type = retry_policy.get("backoff_type", "exponential")
        base_delay = retry_policy.get("base_delay", 5)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Update retry count
                step_execution.retry_count = str(attempt)
                
                # Execute step
                start_time = time.time()
                result = await handler(step_config, context)
                execution_time = time.time() - start_time
                
                logger.info(
                    "Step executed successfully",
                    step_id=step_execution.step_id,
                    attempt=attempt + 1,
                    execution_time=execution_time
                )
                
                return result
                
            except Exception as e:
                last_error = e
                
                logger.warning(
                    "Step execution attempt failed",
                    step_id=step_execution.step_id,
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
                    error=str(e)
                )
                
                # If this is the last attempt, don't wait
                if attempt >= max_retries:
                    break
                
                # Calculate delay for next attempt
                if backoff_type == "exponential":
                    delay = base_delay * (2 ** attempt)
                elif backoff_type == "linear":
                    delay = base_delay * (attempt + 1)
                else:  # fixed
                    delay = base_delay
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # All attempts failed
        error_message = f"Step execution failed after {max_retries + 1} attempts: {str(last_error)}"
        raise WorkflowExecutionError(
            error_message,
            step_id=step_execution.step_id,
            error_code="STEP_EXECUTION_FAILED"
        ) from last_error
    
    async def _handle_task_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle task step execution."""
        task_name = config.get("task_name", "unnamed_task")
        task_params = config.get("parameters", {})
        
        logger.info("Executing task step", task_name=task_name)
        
        # Simulate task execution
        # In real implementation, this would call actual task handlers
        await asyncio.sleep(0.1)  # Simulate work
        
        return {
            "status": "completed",
            "task_name": task_name,
            "output": f"Task {task_name} completed successfully",
            "parameters": task_params
        }
    
    async def _handle_decision_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle decision step execution."""
        condition = config.get("condition", "true")
        options = config.get("options", {})
        
        logger.info("Executing decision step", condition=condition)
        
        # Simple condition evaluation
        # In real implementation, this would use a proper expression evaluator
        result = self._evaluate_condition(condition, context)
        
        return {
            "decision": result,
            "condition": condition,
            "selected_branch": options.get(str(result).lower(), "default")
        }
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition string against context."""
        # Simple evaluation - in real implementation, use a proper expression parser
        if condition.lower() == "true":
            return True
        elif condition.lower() == "false":
            return False
        elif condition.startswith("context."):
            # Extract context variable
            var_path = condition[8:]  # Remove "context."
            parts = var_path.split(".")
            value = context
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return False
            
            return bool(value)
        
        return True
    
    async def _handle_delay_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle delay step execution."""
        delay_seconds = config.get("seconds", 1)
        
        logger.info("Executing delay step", delay_seconds=delay_seconds)
        
        await asyncio.sleep(delay_seconds)
        
        return {
            "status": "completed",
            "delayed": delay_seconds
        }
    
    async def _handle_webhook_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle webhook step execution."""
        url = config.get("url", "https://example.com/webhook")
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        payload = config.get("payload", context)
        
        logger.info("Executing webhook step", url=url, method=method)
        
        # Simulate webhook call
        # In real implementation, this would use httpx or aiohttp
        await asyncio.sleep(0.2)  # Simulate network latency
        
        return {
            "status": "completed",
            "webhook_url": url,
            "method": method,
            "response_code": 200,
            "response_body": {"status": "success"}
        }
    
    async def _handle_agent_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle agent step execution."""
        agent_type = config.get("agent_type", "worker")
        agent_config = config.get("agent_config", {})
        prompt = config.get("prompt", "")
        
        logger.info("Executing agent step", agent_type=agent_type)
        
        # Simulate agent execution
        # In real implementation, this would call the agent orchestration system
        await asyncio.sleep(0.5)  # Simulate agent processing time
        
        return {
            "status": "completed",
            "agent_type": agent_type,
            "agent_response": f"Agent {agent_type} processed the request",
            "confidence": 0.95,
            "processing_time": 0.5
        }
    
    async def _handle_parallel_step(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Handle parallel step execution."""
        parallel_steps = config.get("steps", [])
        max_concurrency = config.get("max_concurrency", 4)
        
        logger.info("Executing parallel step", steps_count=len(parallel_steps))
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def execute_parallel_step(step_config: Dict[str, Any]) -> Any:
            async with semaphore:
                return await self.execute_step(
                    step_config.get("execution", WorkflowStepExecution()),
                    step_config,
                    context
                )
        
        # Execute steps in parallel
        tasks = [execute_parallel_step(step) for step in parallel_steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_results = []
        failed_results = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_results.append({
                    "step_index": i,
                    "error": str(result)
                })
            else:
                successful_results.append({
                    "step_index": i,
                    "result": result
                })
        
        return {
            "status": "completed",
            "successful_steps": successful_results,
            "failed_steps": failed_results,
            "total_steps": len(parallel_steps)
        }
    
    async def execute_with_timeout(
        self,
        step_execution: WorkflowStepExecution,
        step_config: Dict[str, Any],
        context: Dict[str, Any],
        timeout_seconds: Optional[int] = None
    ) -> Any:
        """
        Execute a step with timeout.
        
        Args:
            step_execution: Step execution record
            step_config: Step configuration
            context: Execution context
            timeout_seconds: Timeout in seconds
            
        Returns:
            Any: Step execution result
            
        Raises:
            WorkflowTimeoutError: If step execution times out
        """
        timeout = timeout_seconds or step_config.get("timeout", 300)
        
        try:
            return await asyncio.wait_for(
                self.execute_step(step_execution, step_config, context),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise WorkflowTimeoutError(
                f"Step execution timed out after {timeout} seconds",
                timeout_seconds=timeout,
                step_id=step_execution.step_id
            )
    
    async def validate_step_config(
        self,
        step_config: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Validate step configuration.
        
        Args:
            step_config: Step configuration to validate
            
        Returns:
            tuple[bool, list[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        step_type = step_config.get("type")
        if not step_type:
            errors.append("Step type is required")
        
        step_id = step_config.get("id")
        if not step_id:
            errors.append("Step ID is required")
        
        # Check if handler exists
        if step_type and step_type not in self.step_handlers:
            errors.append(f"No handler registered for step type: {step_type}")
        
        # Validate step type specific configuration
        if step_type == "webhook":
            url = step_config.get("url")
            if not url:
                errors.append("Webhook URL is required")
            elif not self._is_valid_url(url):
                errors.append("Invalid webhook URL")
        
        elif step_type == "delay":
            seconds = step_config.get("seconds")
            if seconds is None or seconds < 0:
                errors.append("Delay seconds must be a non-negative number")
        
        elif step_type == "parallel":
            steps = step_config.get("steps", [])
            if not steps:
                errors.append("Parallel steps cannot be empty")
            else:
                for i, sub_step in enumerate(steps):
                    sub_valid, sub_errors = await self.validate_step_config(sub_step)
                    if not sub_valid:
                        errors.extend([f"Step {i}: {error}" for error in sub_errors])
        
        return len(errors) == 0, errors
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid."""
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def get_registered_handlers(self) -> list[str]:
        """Get list of registered step handlers."""
        return list(self.step_handlers.keys())
    
    def remove_handler(self, step_type: str) -> bool:
        """
        Remove a step handler.
        
        Args:
            step_type: Type of step to remove
            
        Returns:
            bool: True if handler was removed
        """
        if step_type in self.step_handlers:
            del self.step_handlers[step_type]
            logger.info("Step handler removed", step_type=step_type)
            return True
        return False
