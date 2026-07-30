"""
BaseLayer Task Queue Tasks

ARQ task definitions for agent and pipeline execution
with job correlation, error handling, and scheduling.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import arq
from croniter import croniter

from ..core.agent_base import AgentBase
from ..core.context import AgentContext
from ..core.pipeline import Pipeline, create_pipeline_from_config
from ..core.state import AgentState
from ..llm.ollama_client import ollama_client
from ..memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


# In-memory agent registry (will be populated by engine implementations)
AGENT_REGISTRY: Dict[str, type] = {}
PIPELINE_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_agent(agent_class: type) -> None:
    """Register an agent class."""
    AGENT_REGISTRY[agent_class.agent_name] = agent_class
    logger.debug(f"Agent registered: {agent_class.agent_name}")


def register_pipeline(name: str, config: Dict[str, Any]) -> None:
    """Register a pipeline configuration."""
    PIPELINE_REGISTRY[name] = config
    logger.debug(f"Pipeline registered: {name}")


@arq.job()
async def run_agent_task(
    ctx: arq.Context,
    agent_name: str,
    task_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a single agent task.
    
    Args:
        ctx: ARQ job context
        agent_name: Name of agent to run
        task_data: Input data for the agent
        config: Optional agent configuration
        
    Returns:
        Task execution result
    """
    job_id = ctx.job_id
    start_time = datetime.now(timezone.utc)
    
    logger.info(
        "Agent task started",
        job_id=job_id,
        agent_name=agent_name
    )
    
    try:
        # Get agent class
        if agent_name not in AGENT_REGISTRY:
            raise BaseLayerError(f"Agent not registered: {agent_name}")
        
        agent_class = AGENT_REGISTRY[agent_name]
        
        # Create agent configuration
        from ..core.agent_base import AgentConfig
        agent_config = AgentConfig(**config) if config else AgentConfig()
        
        # Instantiate agent
        agent = agent_class(config=agent_config)
        
        # Create memory interface (mock for now)
        memory_interface = MockMemoryInterface()
        
        # Create execution context
        context = AgentContext(
            task_id=job_id,
            task_type="agent_execution",
            input_data=task_data,
            memory_interface=memory_interface,
            config=agent_config,
            request_id=ctx.get("request_id", str(uuid.uuid4())),
            metadata=ctx.get("metadata", {})
        )
        
        # Execute agent
        result = await Agent.run(context)
        
        # Calculate duration
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        logger.info(
            "Agent task completed",
            job_id=job_id,
            agent_name=agent_name,
            duration_ms=duration_ms,
            status=result.get("status")
        )
        
        return {
            "job_id": job_id,
            "agent_name": agent_name,
            "status": "success",
            "result": result,
            "duration_ms": duration_ms,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        logger.error(
            "Agent task failed",
            job_id=job_id,
            agent_name=agent_name,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms
        )
        
        return {
            "job_id": job_id,
            "agent_name": agent_name,
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": duration_ms,
            "failed_at": datetime.now(timezone.utc).isoformat()
        }


@arq.job()
async def run_pipeline_task(
    ctx: arq.Context,
    pipeline_name: str,
    input_data: Dict[str, Any],
    config_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a pipeline task.
    
    Args:
        ctx: ARQ job context
        pipeline_name: Name of pipeline to run
        input_data: Input data for the pipeline
        config_overrides: Optional pipeline configuration overrides
        
    Returns:
        Pipeline execution result
    """
    job_id = ctx.job_id
    start_time = datetime.now(timezone.utc)
    
    logger.info(
        "Pipeline task started",
        job_id=job_id,
        pipeline_name=pipeline_name
    )
    
    try:
        # Get pipeline configuration
        if pipeline_name not in PIPELINE_REGISTRY:
            raise BaseLayerError(f"Pipeline not registered: {pipeline_name}")
        
        pipeline_config = PIPELINE_REGISTRY[pipeline_name]
        
        # Apply overrides
        if config_overrides:
            pipeline_config.update(config_overrides)
        
        # Create agents for pipeline
        agents = {}
        for step_config in pipeline_config.get("steps", []):
            agent_name = step_config.get("agent")
            if agent_name not in AGENT_REGISTRY:
                raise BaseLayerError(f"Agent not registered: {agent_name}")
            
            agent_class = AGENT_REGISTRY[agent_name]
            from ..core.agent_base import AgentConfig
            agent_config = AgentConfig()
            
            agents[agent_name] = agent_class(config=agent_config)
        
        # Create pipeline
        pipeline = create_pipeline_from_config(
            pipeline_config,
            agents,
            db_session=None,  # TODO: Get from context
            redis_client=None  # TODO: Get from context
        )
        
        # Create execution context
        memory_interface = MockMemoryInterface()
        context = AgentContext(
            task_id=job_id,
            task_type="pipeline_execution",
            input_data=input_data,
            memory_interface=memory_interface,
            config=AgentConfig(),
            request_id=ctx.get("request_id", str(uuid.uuid4())),
            pipeline_id=pipeline_name,
            metadata=ctx.get("metadata", {})
        )
        
        # Execute pipeline
        result = await pipeline.execute(input_data, context)
        
        # Calculate duration
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        logger.info(
            "Pipeline task completed",
            job_id=job_id,
            pipeline_name=pipeline_name,
            duration_ms=duration_ms,
            status=result.get("status")
        )
        
        return {
            "job_id": job_id,
            "pipeline_name": pipeline_name,
            "status": "success",
            "result": result,
            "duration_ms": duration_ms,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        logger.error(
            "Pipeline task failed",
            job_id=job_id,
            pipeline_name=pipeline_name,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms
        )
        
        return {
            "job_id": job_id,
            "pipeline_name": pipeline_name,
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": duration_ms,
            "failed_at": datetime.now(timezone.utc).isoformat()
        }


@arq.job(cron="0 9 * * *")  # Daily at 9 AM
async def schedule_recurring_task(
    ctx: arq.Context,
    agent_name: str,
    cron_expression: str,
    task_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Schedule a recurring task using cron expression.
    
    Args:
        ctx: ARQ job context
        agent_name: Name of agent to run
        cron_expression: Cron expression for scheduling
        task_data: Input data for the agent
        config: Optional agent configuration
        
    Returns:
        Scheduling result
    """
    job_id = ctx.job_id
    
    logger.info(
        "Recurring task scheduled",
        job_id=job_id,
        agent_name=agent_name,
        cron_expression=cron_expression
    )
    
    try:
        # Validate cron expression
        try:
            croniter(cron_expression)
        except Exception as e:
            raise BaseLayerError(f"Invalid cron expression: {cron_expression}") from e
        
        # Calculate next run time
        cron = croniter(cron_expression)
        next_run = cron.get_next(datetime.now(timezone.utc))
        
        # Schedule next run
        from .worker import worker
        
        await ctx["redis"].enqueue_job(
            "run_agent_task",
            agent_name=agent_name,
            task_data=task_data,
            config=config,
            _job_id=str(uuid.uuid4()),
            _defer_until=next_run
        )
        
        logger.info(
            "Next run scheduled",
            job_id=job_id,
            agent_name=agent_name,
            next_run=next_run.isoformat()
        )
        
        return {
            "job_id": job_id,
            "agent_name": agent_name,
            "cron_expression": cron_expression,
            "next_run": next_run.isoformat(),
            "status": "scheduled"
        }
        
    except Exception as e:
        logger.error(
            "Failed to schedule recurring task",
            job_id=job_id,
            agent_name=agent_name,
            cron_expression=cron_expression,
            error=str(e)
        )
        
        return {
            "job_id": job_id,
            "agent_name": agent_name,
            "cron_expression": cron_expression,
            "status": "failed",
            "error": str(e)
        }


class MockMemoryInterface:
    """
    Mock memory interface for development.
    
    Implements MemoryInterface with in-memory storage
    until Codex (Engine 5) is built.
    """
    
    def __init__(self) -> None:
        """Initialize mock memory."""
        self.storage: Dict[str, Any] = {}
        self.tags: Dict[str, List[str]] = {}
        self.confidence: Dict[str, float] = {}
        
        logger.debug("Mock memory interface initialized")
    
    async def store(
        self,
        key: str,
        value: Any,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        source: Optional[str] = None
    ) -> bool:
        """Store a value in memory."""
        try:
            self.storage[key] = value
            self.tags[key] = tags or []
            self.confidence[key] = confidence
            
            logger.debug(
                "Memory stored",
                key=key,
                tags=tags,
                confidence=confidence
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to store in memory",
                key=key,
                error=str(e)
            )
            return False
    
    async def retrieve(
        self,
        key: str
    ) -> Optional[Any]:
        """Retrieve a value from memory."""
        try:
            value = self.storage.get(key)
            
            logger.debug(
                "Memory retrieved",
                key=key,
                found=value is not None
            )
            
            return value
            
        except Exception as e:
            logger.error(
                "Failed to retrieve from memory",
                key=key,
                error=str(e)
            )
            return None
    
    async def search(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memory by query and tags."""
        try:
            results = []
            
            for key, value in self.storage.items():
                # Simple text search
                if query.lower() in str(value).lower():
                    # Check tags if specified
                    if tags:
                        item_tags = self.tags.get(key, [])
                        if not any(tag in item_tags for tag in tags):
                            continue
                    
                    results.append({
                        "key": key,
                        "value": value,
                        "tags": self.tags.get(key, []),
                        "confidence": self.confidence.get(key, 1.0)
                    })
                
                    if len(results) >= limit:
                        break
            
            logger.debug(
                "Memory search completed",
                query=query,
                tags=tags,
                results=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Failed to search memory",
                query=query,
                error=str(e)
            )
            return []
    
    async def update(
        self,
        key: str,
        value: Any,
        confidence: Optional[float] = None
    ) -> bool:
        """Update a value in memory."""
        try:
            if key in self.storage:
                self.storage[key] = value
                if confidence is not None:
                    self.confidence[key] = confidence
                
                logger.debug(
                    "Memory updated",
                    key=key,
                    confidence=confidence
                )
                
                return True
            else:
                logger.warning(
                    "Memory update failed - key not found",
                    key=key
                )
                return False
                
        except Exception as e:
            logger.error(
                "Failed to update memory",
                key=key,
                error=str(e)
            )
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from memory."""
        try:
            if key in self.storage:
                del self.storage[key]
                if key in self.tags:
                    del self.tags[key]
                if key in self.confidence:
                    del self.confidence[key]
                
                logger.debug(
                    "Memory deleted",
                    key=key
                )
                
                return True
            else:
                logger.warning(
                    "Memory delete failed - key not found",
                    key=key
                )
                return False
                
        except Exception as e:
            logger.error(
                "Failed to delete from memory",
                key=key,
                error=str(e)
            )
            return False
    
    async def search_semantic(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Semantic search (mock implementation)."""
        # For now, just do text search
        return await self.search(query, limit=limit)


# Task utility functions
async def enqueue_agent_task(
    agent_name: str,
    task_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    delay: Optional[int] = None
) -> str:
    """
    Enqueue an agent task.
    
    Args:
        agent_name: Name of agent to run
        task_data: Input data for the agent
        config: Optional agent configuration
        delay: Optional delay in seconds
        
    Returns:
        Job ID
    """
    try:
        from .worker import worker
        
        job_id = await worker.redis_client.enqueue_job(
            "run_agent_task",
            agent_name=agent_name,
            task_data=task_data,
            config=config,
            _job_id=str(uuid.uuid4()),
            _defer_by=delay
        )
        
        logger.info(
            "Agent task enqueued",
            agent_name=agent_name,
            job_id=job_id,
            delay=delay
        )
        
        return job_id
        
    except Exception as e:
        logger.error(
            "Failed to enqueue agent task",
            agent_name=agent_name,
            error=str(e)
        )
        raise BaseLayerError(f"Failed to enqueue task: {str(e)}") from e


async def enqueue_pipeline_task(
    pipeline_name: str,
    input_data: Dict[str, Any],
    config_overrides: Optional[Dict[str, Any]] = None,
    delay: Optional[int] = None
) -> str:
    """
    Enqueue a pipeline task.
    
    Args:
        pipeline_name: Name of pipeline to run
        input_data: Input data for the pipeline
        config_overrides: Optional pipeline configuration overrides
        delay: Optional delay in seconds
        
    Returns:
        Job ID
    """
    try:
        from .worker import worker
        
        job_id = await worker.redis_client.enqueue_job(
            "run_pipeline_task",
            pipeline_name=pipeline_name,
            input_data=input_data,
            config_overrides=config_overrides,
            _job_id=str(uuid.uuid4()),
            _defer_by=delay
        )
        
        logger.info(
            "Pipeline task enqueued",
            pipeline_name=pipeline_name,
            job_id=job_id,
            delay=delay
        )
        
        return job_id
        
    except Exception as e:
        logger.error(
            "Failed to enqueue pipeline task",
            pipeline_name=pipeline_name,
            error=str(e)
        )
        raise BaseLayerError(f"Failed to enqueue task: {str(e)}") from e


async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of a specific job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status or None if not found
    """
    try:
        from .worker import worker
        
        # Get job info from ARQ
        job_info = await worker.redis_client.get(f"arq:job:{job_id}")
        
        if job_info:
            return json.loads(job_info)
        
        return None
        
    except Exception as e:
        logger.error(
            "Failed to get job status",
            job_id=job_id,
            error=str(e)
        )
        return None


async def cancel_job(job_id: str) -> bool:
    """
    Cancel a running job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if cancelled, False otherwise
    """
    try:
        from .worker import worker
        
        # This is a simplified implementation
        # In a real system, would need to track running jobs and send cancel signals
        cancelled = await worker.redis_client.set(f"cancel:{job_id}", "1", ex=60)
        
        logger.info(
            "Job cancellation requested",
            job_id=job_id,
            success=cancelled
        )
        
        return cancelled
        
    except Exception as e:
        logger.error(
            "Failed to cancel job",
            job_id=job_id,
            error=str(e)
        )
        return False


# ARQ worker settings
WorkerSettings = arq.worker.WorkerSettings(
    cron_jobs=[schedule_recurring_task],
    max_tries=3,
    retry_delay=5,
    retry_jitter=True,
    timeout_seconds=300,
    keep_result=3600,  # 1 hour
    health_check_interval=30,
    health_check_key="worker:health"
)
