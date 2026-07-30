"""
BaseLayer Core Loop API - Executions

REST API endpoints for workflow execution monitoring and management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import get_db_session
from ...models.core_loop import WorkflowExecution, WorkflowStatus
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import WorkflowEngine
from ..monitor import WorkflowMonitor

logger = get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["Executions"])

# Global instances (will be injected in startup)
workflow_engine: WorkflowEngine = None
workflow_monitor: WorkflowMonitor = None


def get_workflow_engine() -> WorkflowEngine:
    """Get workflow engine instance."""
    global workflow_engine
    if not workflow_engine:
        raise HTTPException(status_code=500, detail="Workflow engine not initialized")
    return workflow_engine


def get_workflow_monitor() -> WorkflowMonitor:
    """Get workflow monitor instance."""
    global workflow_monitor
    if not workflow_monitor:
        raise HTTPException(status_code=500, detail="Workflow monitor not initialized")
    return workflow_monitor


@router.get("/", response_model=List[Dict[str, Any]])
async def list_executions(
    status: Optional[WorkflowStatus] = Query(None),
    workflow_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List workflow executions with optional filtering.
    
    Args:
        status: Filter by execution status
        workflow_id: Filter by workflow ID
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of executions
    """
    query = select(WorkflowExecution).where(WorkflowExecution.deleted_at.is_(None))
    
    if status:
        query = query.where(WorkflowExecution.status == status)
    
    if workflow_id:
        try:
            import uuid
            workflow_uuid = uuid.UUID(workflow_id)
            query = query.where(WorkflowExecution.workflow_id == workflow_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    query = query.order_by(WorkflowExecution.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    return [execution.to_dict() for execution in executions]


@router.get("/active", response_model=List[Dict[str, Any]])
async def list_active_executions(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List currently active workflow executions.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of active executions
    """
    engine = get_workflow_engine()
    
    active_executions = await engine.get_active_executions()
    
    return [execution.to_dict() for execution in active_executions]


@router.get("/{execution_id}", response_model=Dict[str, Any])
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific workflow execution.
    
    Args:
        execution_id: Execution ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Execution details
    """
    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.execution_id == execution_id,
            WorkflowExecution.deleted_at.is_(None)
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution.to_dict()


@router.get("/{execution_id}/timeline", response_model=Dict[str, Any])
async def get_execution_timeline(
    execution_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed timeline for a workflow execution.
    
    Args:
        execution_id: Execution ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Execution timeline
    """
    monitor = get_workflow_monitor()
    
    timeline = await monitor.get_execution_timeline(execution_id)
    
    if not timeline:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return timeline


@router.post("/{execution_id}/cancel", response_model=Dict[str, Any])
async def cancel_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel a workflow execution.
    
    Args:
        execution_id: Execution ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Cancellation result
    """
    engine = get_workflow_engine()
    
    success = await engine.cancel_execution(execution_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Execution not found or already completed")
    
    logger.info(
        "Workflow execution cancelled",
        execution_id=execution_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Execution cancelled successfully"}


@router.get("/{execution_id}/logs", response_model=List[Dict[str, Any]])
async def get_execution_logs(
    execution_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get logs for a workflow execution.
    
    Args:
        execution_id: Execution ID
        limit: Maximum number of log entries
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Execution logs
    """
    # Get execution
    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.execution_id == execution_id,
            WorkflowExecution.deleted_at.is_(None)
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Get step executions (logs)
    steps_result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.execution_id == execution_id,
            WorkflowExecution.deleted_at.is_(None)
        ).order_by(WorkflowExecution.created_at)
    )
    step_executions = steps_result.scalars().all()
    
    logs = []
    for step in step_executions:
        log_entry = {
            "timestamp": step.created_at.isoformat(),
            "level": "INFO",
            "message": f"Step {step.step_id} {step.status.value}",
            "step_id": step.step_id,
            "status": step.status.value,
            "duration": step.duration,
            "error": step.error_message
        }
        logs.append(log_entry)
    
    return logs[offset:offset + limit]


@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get workflow execution metrics summary.
    
    Args:
        hours: Number of hours to look back
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Metrics summary
    """
    monitor = get_workflow_monitor()
    
    summary = await monitor.get_performance_summary()
    
    return summary


@router.get("/metrics/workflow/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow_metrics(
    workflow_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get metrics for a specific workflow.
    
    Args:
        workflow_id: Workflow ID
        hours: Number of hours to look back
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Workflow metrics
    """
    monitor = get_workflow_monitor()
    
    metrics = await monitor.get_workflow_metrics(workflow_id, hours)
    
    if not metrics:
        raise HTTPException(status_code=404, detail="Workflow metrics not found")
    
    return metrics


@router.get("/health/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow_health(
    workflow_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get health status for a specific workflow.
    
    Args:
        workflow_id: Workflow ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Workflow health status
    """
    monitor = get_workflow_monitor()
    
    health = await monitor.get_workflow_health(workflow_id)
    
    if not health:
        raise HTTPException(status_code=404, detail="Workflow health not found")
    
    return health


@router.get("/monitor/status", response_model=Dict[str, Any])
async def get_monitor_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get the current status of the workflow monitor.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Monitor status
    """
    monitor = get_workflow_monitor()
    
    status = monitor.get_monitor_status()
    
    return status


@router.get("/monitor/metrics", response_model=List[Dict[str, Any]])
async def get_metrics_history(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get historical metrics data.
    
    Args:
        limit: Maximum number of records to return
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Historical metrics
    """
    monitor = get_workflow_monitor()
    
    history = monitor.get_metrics_history(limit)
    
    return history


@router.post("/retry/{execution_id}", response_model=Dict[str, Any])
async def retry_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retry a failed workflow execution.
    
    Args:
        execution_id: Execution ID to retry
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Retry result
    """
    # Get original execution
    async with get_db_session() as db:
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id,
                WorkflowExecution.deleted_at.is_(None)
            )
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        if execution.status != WorkflowStatus.FAILED:
            raise HTTPException(status_code=400, detail="Only failed executions can be retried")
    
    engine = get_workflow_engine()
    
    # Create new execution with same input data
    new_execution = await engine.start_workflow(
        workflow_id=str(execution.workflow_id),
        input_data=execution.input_data,
        user_id=current_user.id
    )
    
    logger.info(
        "Workflow execution retried",
        original_execution_id=execution_id,
        new_execution_id=new_execution.execution_id,
        user_id=str(current_user.id)
    )
    
    return {
        "execution_id": new_execution.execution_id,
        "status": new_execution.status.value,
        "message": "Execution retried successfully"
    }
