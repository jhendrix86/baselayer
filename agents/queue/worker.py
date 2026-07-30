"""
BaseLayer ARQ Worker Configuration

Redis-based task queue worker with health checks,
graceful shutdown, and job timeout handling.
"""

import asyncio
import signal
import uuid
from typing import Any, Dict, List, Optional

import arq
import redis.asyncio as redis
from arq import Worker

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class BaseLayerWorker:
    """
    ARQ worker with health monitoring and graceful shutdown.
    
    Manages task execution, concurrency limits,
    and provides health check endpoints.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_concurrent_jobs: int = 2,
        job_timeout: int = 300,
        health_check_interval: int = 30,
        worker_name: Optional[str] = None
    ) -> None:
        """Initialize worker configuration."""
        self.redis_url: str = redis_url
        self.max_concurrent_jobs: int = max_concurrent_jobs
        self.job_timeout: int = job_timeout
        self.health_check_interval: int = health_check_interval
        self.worker_name: str = worker_name or f"baselayer-worker-{uuid.uuid4().hex[:8]}"
        
        # Worker state
        self.is_running: bool = False
        self.is_shutting_down: bool = False
        self.current_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_stats: Dict[str, int] = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "timeout_jobs": 0
        }
        
        # Redis client for health checks
        self.redis_client: Optional[redis.Redis] = None
        
        # ARQ worker instance
        self.worker: Optional[Worker] = None
        
        # Health check task
        self._health_task: Optional[asyncio.Task] = None
        
        logger.info(
            "Worker initialized",
            worker_name=self.worker_name,
            redis_url=self.redis_url,
            max_concurrent_jobs=self.max_concurrent_jobs,
            job_timeout=self.job_timeout
        )
    
    async def start(self) -> None:
        """Start the worker."""
        try:
            # Initialize Redis client
            self.redis_client = redis.from_url(self.redis_url)
            
            # Register functions
            functions = self._get_registered_functions()
            
            # Create ARQ worker
            self.worker = Worker(
                functions=functions,
                redis_settings=self.redis_url,
                max_jobs=self.max_concurrent_jobs,
                job_timeout=self.job_timeout,
                ctx_defaults={
                    "worker_name": self.worker_name,
                    "started_at": asyncio.get_event_loop().time()
                }
            )
            
            self.is_running = True
            
            # Start health check task
            self._health_task = asyncio.create_task(self._health_check_loop())
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            logger.info(
                "Worker starting",
                worker_name=self.worker_name,
                functions=[func.__name__ for func in functions]
            )
            
            # Start worker (this blocks until shutdown)
            await self.worker.async_run()
            
        except Exception as e:
            logger.error(
                "Worker failed to start",
                worker_name=self.worker_name,
                error=str(e)
            )
            raise BaseLayerError(f"Worker startup failed: {str(e)}") from e
    
    async def stop(self, timeout: int = 30) -> None:
        """
        Stop the worker gracefully.
        
        Args:
            timeout: Maximum time to wait for jobs to complete
        """
        if not self.is_running:
            logger.info("Worker already stopped")
            return
        
        logger.info(
            "Worker stopping gracefully",
            worker_name=self.worker_name,
            timeout=timeout
        )
        
        self.is_shutting_down = True
        
        # Cancel health check task
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        # Wait for current jobs to complete or timeout
        if self.current_jobs:
            logger.info(
                "Waiting for jobs to complete",
                worker_name=self.worker_name,
                active_jobs=len(self.current_jobs)
            )
            
            start_time = asyncio.get_event_loop().time()
            
            while self.current_jobs:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning(
                        "Timeout reached, forcing shutdown",
                        worker_name=self.worker_name,
                        remaining_jobs=len(self.current_jobs)
                    )
                    break
                
                await asyncio.sleep(1)
        
        # Stop ARQ worker
        if self.worker:
            self.worker.close()
        
        # Close Redis client
        if self.redis_client:
            await self.redis_client.close()
        
        self.is_running = False
        
        logger.info(
            "Worker stopped",
            worker_name=self.worker_name,
            final_stats=self.job_stats
        )
    
    def _get_registered_functions(self) -> List[callable]:
        """
        Get list of registered functions.
        
        Override in subclasses to register specific functions.
        
        Returns:
            List of callable functions
        """
        from .tasks import (
            run_agent_task,
            run_pipeline_task,
            schedule_recurring_task
        )
        
        return [
            run_agent_task,
            run_pipeline_task,
            schedule_recurring_task
        ]
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(
                "Received shutdown signal",
                worker_name=self.worker_name,
                signal=signum
            )
            asyncio.create_task(self.stop())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _health_check_loop(self) -> None:
        """Run health check loop."""
        while self.is_running and not self.is_shutting_down:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Health check failed",
                    worker_name=self.worker_name,
                    error=str(e)
                )
                await asyncio.sleep(self.health_check_interval)
    
    async def _perform_health_check(self) -> None:
        """Perform health check and update Redis."""
        try:
            # Check Redis connection
            if self.redis_client:
                await self.redis_client.ping()
            
            # Check worker status
            health_data = {
                "worker_name": self.worker_name,
                "is_running": self.is_running,
                "is_shutting_down": self.is_shutting_down,
                "current_jobs": len(self.current_jobs),
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "job_stats": self.job_stats,
                "timestamp": asyncio.get_event_loop().time(),
                "redis_connected": True
            }
            
            # Store health data in Redis
            health_key = f"worker:health:{self.worker_name}"
            if self.redis_client:
                await self.redis_client.setex(
                    health_key,
                    self.health_check_interval * 2,  # 2x interval
                    value=str(health_data)
                )
            
            logger.debug(
                "Health check completed",
                worker_name=self.worker_name,
                active_jobs=len(self.current_jobs),
                stats=self.job_stats
            )
            
        except Exception as e:
            logger.error(
                "Health check failed",
                worker_name=self.worker_name,
                error=str(e)
            )
            
            # Store error status
            if self.redis_client:
                health_key = f"worker:health:{self.worker_name}"
                error_data = {
                    "worker_name": self.worker_name,
                    "is_running": False,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time(),
                    "redis_connected": False
                }
                
                await self.redis_client.setex(
                    health_key,
                    self.health_check_interval * 2,
                    value=str(error_data)
                )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get current worker health status.
        
        Returns:
            Health status dictionary
        """
        try:
            # Get from Redis if available
            if self.redis_client:
                health_key = f"worker:health:{self.worker_name}"
                health_data = await self.redis_client.get(health_key)
                
                if health_data:
                    import json
                    return json.loads(health_data)
            
            # Fallback to local state
            return {
                "worker_name": self.worker_name,
                "is_running": self.is_running,
                "is_shutting_down": self.is_shutting_down,
                "current_jobs": len(self.current_jobs),
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "job_stats": self.job_stats,
                "timestamp": asyncio.get_event_loop().time(),
                "redis_connected": self.redis_client is not None
            }
            
        except Exception as e:
            logger.error(
                "Failed to get health status",
                worker_name=self.worker_name,
                error=str(e)
            )
            
            return {
                "worker_name": self.worker_name,
                "is_running": False,
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
    
    def update_job_stats(self, job_id: str, status: str) -> None:
        """
        Update job statistics.
        
        Args:
            job_id: Job identifier
            status: Job status (started, completed, failed, timeout)
        """
        self.job_stats["total_jobs"] += 1
        
        if status == "completed":
            self.job_stats["successful_jobs"] += 1
        elif status == "failed":
            self.job_stats["failed_jobs"] += 1
        elif status == "timeout":
            self.job_stats["timeout_jobs"] += 1
        
        logger.debug(
            "Job stats updated",
            worker_name=self.worker_name,
            job_id=job_id,
            status=status,
            total_jobs=self.job_stats["total_jobs"]
        )
    
    def add_job(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """
        Add job to current jobs tracking.
        
        Args:
            job_id: Job identifier
            job_data: Job data
        """
        self.current_jobs[job_id] = {
            "started_at": asyncio.get_event_loop().time(),
            "data": job_data
        }
        
        logger.debug(
            "Job added",
            worker_name=self.worker_name,
            job_id=job_id,
            active_jobs=len(self.current_jobs)
        )
    
    def remove_job(self, job_id: str) -> None:
        """
        Remove job from current jobs tracking.
        
        Args:
            job_id: Job identifier
        """
        if job_id in self.current_jobs:
            job_data = self.current_jobs.pop(job_id)
            
            duration = asyncio.get_event_loop().time() - job_data["started_at"]
            
            logger.debug(
                "Job removed",
                worker_name=self.worker_name,
                job_id=job_id,
                duration=duration,
                active_jobs=len(self.current_jobs)
            )
    
    def get_current_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently running jobs.
        
        Returns:
            Dictionary of current jobs
        """
        return self.current_jobs.copy()
    
    def get_job_stats(self) -> Dict[str, int]:
        """
        Get job statistics.
        
        Returns:
            Job statistics dictionary
        """
        return self.job_stats.copy()


class AgentWorker(BaseLayerWorker):
    """
    Worker specialized for agent tasks.
    
    Registers agent-specific functions and provides
    agent-specific health monitoring.
    """
    
    def _get_registered_functions(self) -> List[callable]:
        """Get agent-specific functions."""
        from .tasks import (
            run_agent_task,
            run_pipeline_task,
            schedule_recurring_task
        )
        
        return [
            run_agent_task,
            run_pipeline_task,
            schedule_recurring_task
        ]


# Worker factory function
def create_worker(
    worker_type: str = "agent",
    **kwargs
) -> BaseLayerWorker:
    """
    Create appropriate worker instance.
    
    Args:
        worker_type: Type of worker to create
        **kwargs: Worker configuration
        
    Returns:
        Configured worker instance
    """
    if worker_type == "agent":
        return AgentWorker(**kwargs)
    else:
        return BaseLayerWorker(**kwargs)


# Global worker instance
worker = create_worker(
    worker_type="agent",
    max_concurrent_jobs=2,  # Optimized for nexus RAM
    job_timeout=300,
    health_check_interval=30
)
