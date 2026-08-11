"""
BaseLayer Core Loop Tasks

Arq task definitions for background workflow processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ..core.database import db_session_context
from ..models.core_loop import Workflow, WorkflowExecution, WorkflowStatus
from .engine import WorkflowEngine
from .scheduler import WorkflowScheduler

logger = get_logger(__name__)


# Global instances (will be initialized in startup)
workflow_engine: WorkflowEngine = None
workflow_scheduler: WorkflowScheduler = None


async def initialize_core_loop():
    """Initialize Core Loop components."""
    global workflow_engine, workflow_scheduler
    
    workflow_engine = WorkflowEngine()
    workflow_scheduler = WorkflowScheduler(workflow_engine)

    # start_execution_worker() is an infinite `while True` loop - awaiting
    # it directly (as this used to) would block this function, and thus
    # this whole coroutine, forever, so workflow_scheduler.start() below
    # would never run. Backgrounded the same way WorkflowScheduler.start()/
    # WorkflowMonitor.start() already background their own loops.
    asyncio.create_task(workflow_engine.start_execution_worker())
    await workflow_scheduler.start()
    
    logger.info("Core Loop components initialized")


async def shutdown_core_loop():
    """Shutdown Core Loop components."""
    global workflow_engine, workflow_scheduler
    
    if workflow_scheduler:
        await workflow_scheduler.stop()
    
    if workflow_engine:
        # Engine doesn't have explicit shutdown, but we can stop the worker
        pass
    
    logger.info("Core Loop components shutdown")


async def execute_workflow_task(ctx: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
    """
    Background task to execute a workflow.
    
    Args:
        ctx: Arq context
        execution_id: ID of the execution to run
        
    Returns:
        Dict[str, Any]: Execution result
    """
    global workflow_engine
    
    if not workflow_engine:
        raise RuntimeError("Workflow engine not initialized")
    
    try:
        # Get execution from database
        async with db_session_context() as session:
            result = await session.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id
                )
            )
            execution = result.scalar_one_or_none()
            
            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")
        
        # Execute the workflow
        await workflow_engine.execute_workflow(execution)
        
        return {
            "status": "completed",
            "execution_id": execution_id,
            "final_status": execution.status.value
        }
        
    except Exception as e:
        logger.error(
            "Workflow execution task failed",
            execution_id=execution_id,
            error=str(e)
        )
        
        # Update execution status to failed
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(WorkflowExecution).where(
                        WorkflowExecution.execution_id == execution_id
                    )
                )
                execution = result.scalar_one_or_none()
                
                if execution:
                    execution.fail(str(e))
                    session.add(execution)
                    await session.commit()
        except Exception as db_error:
            logger.error(
                "Failed to update execution status",
                execution_id=execution_id,
                error=str(db_error)
            )
        
        raise


async def cleanup_old_executions(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old workflow executions.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup result
    """
    retention_days = 30
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        async with db_session_context() as session:
            # Soft delete old executions
            result = await session.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.created_at < cutoff_date,
                    WorkflowExecution.deleted_at.is_(None)
                )
            )
            old_executions = result.scalars().all()
            
            count = 0
            for execution in old_executions:
                execution.soft_delete()
                session.add(execution)
                count += 1
            
            await session.commit()
            
            logger.info(
                "Old executions cleaned up",
                count=count,
                retention_days=retention_days
            )
            
            return {
                "status": "completed",
                "cleaned_executions": count,
                "retention_days": retention_days
            }
            
    except Exception as e:
        logger.error(
            "Cleanup task failed",
            error=str(e)
        )
        raise


async def update_workflow_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update workflow metrics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Metrics update result
    """
    try:
        # This would update metrics tables
        # For now, just log the action
        logger.info("Updating workflow metrics")
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Metrics update task failed",
            error=str(e)
        )
        raise


async def process_scheduled_workflows(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process scheduled workflows.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Processing result
    """
    global workflow_scheduler
    
    if not workflow_scheduler:
        raise RuntimeError("Workflow scheduler not initialized")
    
    try:
        # Get scheduled workflows that need execution
        scheduled_workflows = await workflow_scheduler.get_scheduled_workflows()
        
        current_time = datetime.utcnow()
        executed_count = 0
        
        for workflow_info in scheduled_workflows:
            next_execution = workflow_info["next_execution"]
            
            if next_execution and current_time >= next_execution:
                # Execute the workflow
                workflow_id = workflow_info["workflow_id"]
                input_data = workflow_info["workflow"].config.get("default_input_data", {})
                
                execution = await workflow_engine.start_workflow(
                    workflow_id=workflow_id,
                    input_data=input_data
                )
                
                executed_count += 1
                
                logger.info(
                    "Scheduled workflow executed",
                    workflow_id=workflow_id,
                    execution_id=execution.execution_id
                )
        
        return {
            "status": "completed",
            "executed_workflows": executed_count,
            "total_scheduled": len(scheduled_workflows)
        }
        
    except Exception as e:
        logger.error(
            "Scheduled workflow processing failed",
            error=str(e)
        )
        raise


async def check_workflow_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check workflow system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check result
    """
    try:
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check active executions
        global workflow_engine
        if workflow_engine:
            active_executions = await workflow_engine.get_active_executions()
            health_status["checks"]["active_executions"] = {
                "status": "healthy",
                "count": len(active_executions),
                "max_concurrent": workflow_engine.max_concurrent_executions
            }
            
            if len(active_executions) >= workflow_engine.max_concurrent_executions:
                health_status["checks"]["active_executions"]["status"] = "warning"
                health_status["status"] = "degraded"
        else:
            health_status["checks"]["engine"] = {
                "status": "error",
                "message": "Workflow engine not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check scheduler
        global workflow_scheduler
        if workflow_scheduler:
            scheduler_status = workflow_scheduler.get_scheduler_status()
            health_status["checks"]["scheduler"] = {
                "status": "healthy" if scheduler_status["running"] else "error",
                **scheduler_status
            }
            
            if not scheduler_status["running"]:
                health_status["status"] = "unhealthy"
        else:
            health_status["checks"]["scheduler"] = {
                "status": "error",
                "message": "Workflow scheduler not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check database connectivity
        try:
            async with db_session_context() as session:
                await session.execute("SELECT 1")
                health_status["checks"]["database"] = {
                    "status": "healthy"
                }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        logger.info(
            "Workflow health check completed",
            status=health_status["status"]
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Health check failed",
            error=str(e)
        )
        raise


# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 4,  # Optimized for i5-2400
    "queue_name": "core_loop",
    "job_timeout": 3600,  # 1 hour timeout
}

# Cron jobs
cron_jobs = [
    cron(
        cleanup_old_executions,
        hour=2,  # 2 AM daily
        minute=0,
    ),
    cron(
        update_workflow_metrics,
        hour=0,  # Midnight daily
        minute=5,
    ),
    cron(
        process_scheduled_workflows,
        minute="*",  # Every minute
    ),
    cron(
        check_workflow_health,
        minute="*/5",  # Every 5 minutes
    ),
]
