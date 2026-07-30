"""
BaseLayer Core Loop API - Workflows

REST API endpoints for workflow management, execution, and scheduling.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import get_db_session
from ...models.core_loop import (
    Workflow, WorkflowExecution, WorkflowStatus, WorkflowPriority,
    ScheduleType
)
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import WorkflowEngine
from ..scheduler import WorkflowScheduler
from ..exceptions import (
    WorkflowEngineError,
    WorkflowValidationError,
    WorkflowGovernanceError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/workflows", tags=["Workflows"])

# Global instances (will be injected in startup)
workflow_engine: WorkflowEngine = None
workflow_scheduler: WorkflowScheduler = None


def get_workflow_engine() -> WorkflowEngine:
    """Get workflow engine instance."""
    global workflow_engine
    if not workflow_engine:
        raise HTTPException(status_code=500, detail="Workflow engine not initialized")
    return workflow_engine


def get_workflow_scheduler() -> WorkflowScheduler:
    """Get workflow scheduler instance."""
    global workflow_scheduler
    if not workflow_scheduler:
        raise HTTPException(status_code=500, detail="Workflow scheduler not initialized")
    return workflow_scheduler


@router.get("/", response_model=List[Dict[str, Any]])
async def list_workflows(
    status: Optional[WorkflowStatus] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List workflows with optional filtering.
    
    Args:
        status: Filter by workflow status
        category: Filter by workflow category
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of workflows
    """
    query = select(Workflow).where(Workflow.deleted_at.is_(None))
    
    if status:
        query = query.where(Workflow.status == status)
    
    if category:
        query = query.where(Workflow.category == category)
    
    query = query.order_by(Workflow.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    workflows = result.scalars().all()
    
    return [workflow.to_dict() for workflow in workflows]


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific workflow by ID.
    
    Args:
        workflow_id: Workflow ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Workflow details
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_uuid,
            Workflow.deleted_at.is_(None)
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflow.to_dict()


@router.post("/", response_model=Dict[str, Any])
async def create_workflow(
    workflow_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new workflow.
    
    Args:
        workflow_data: Workflow data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created workflow
    """
    try:
        # Validate workflow data
        await _validate_workflow_data(workflow_data)
        
        # Create workflow
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description"),
            status=WorkflowStatus.DRAFT,
            priority=WorkflowPriority(workflow_data.get("priority", "medium")),
            config=workflow_data.get("config", {}),
            category=workflow_data.get("category"),
            tags=workflow_data.get("tags", []),
            governance_required=workflow_data.get("governance_required", False),
            created_by=current_user.id
        )
        
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(
            "Workflow created",
            workflow_id=str(workflow.id),
            workflow_name=workflow.name,
            user_id=str(current_user.id)
        )
        
        return workflow.to_dict()
        
    except (WorkflowValidationError, WorkflowGovernanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Error creating workflow",
            error=str(e),
            user_id=str(current_user.id)
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{workflow_id}", response_model=Dict[str, Any])
async def update_workflow(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update a workflow.
    
    Args:
        workflow_id: Workflow ID
        workflow_data: Updated workflow data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Updated workflow
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_uuid,
            Workflow.deleted_at.is_(None)
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if user can update workflow
    if not current_user.is_admin and workflow.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this workflow")
    
    # Update workflow
    if "name" in workflow_data:
        workflow.name = workflow_data["name"]
    
    if "description" in workflow_data:
        workflow.description = workflow_data["description"]
    
    if "config" in workflow_data:
        workflow.config = workflow_data["config"]
    
    if "category" in workflow_data:
        workflow.category = workflow_data["category"]
    
    if "tags" in workflow_data:
        workflow.tags = workflow_data["tags"]
    
    if "priority" in workflow_data:
        workflow.priority = WorkflowPriority(workflow_data["priority"])
    
    if "governance_required" in workflow_data:
        workflow.governance_required = workflow_data["governance_required"]
    
    workflow.updated_by = current_user.id
    workflow.increment_version()
    
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    
    logger.info(
        "Workflow updated",
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        user_id=str(current_user.id)
    )
    
    return workflow.to_dict()


@router.delete("/{workflow_id}", response_model=Dict[str, Any])
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a workflow (soft delete).
    
    Args:
        workflow_id: Workflow ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_uuid,
            Workflow.deleted_at.is_(None)
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if user can delete workflow
    if not current_user.is_admin and workflow.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this workflow")
    
    # Soft delete workflow
    workflow.soft_delete(current_user.id)
    
    db.add(workflow)
    await db.commit()
    
    logger.info(
        "Workflow deleted",
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        user_id=str(current_user.id)
    )
    
    return {"message": "Workflow deleted successfully"}


@router.post("/{workflow_id}/execute", response_model=Dict[str, Any])
async def execute_workflow(
    workflow_id: str,
    input_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Execute a workflow.
    
    Args:
        workflow_id: Workflow ID
        input_data: Input data for the workflow
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Execution result
    """
    engine = get_workflow_engine()
    
    try:
        execution = await engine.start_workflow(
            workflow_id=workflow_id,
            input_data=input_data,
            user_id=current_user.id
        )
        
        logger.info(
            "Workflow execution started",
            workflow_id=workflow_id,
            execution_id=execution.execution_id,
            user_id=str(current_user.id)
        )
        
        return {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "input_data": execution.input_data
        }
        
    except (WorkflowValidationError, WorkflowGovernanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except WorkflowEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/executions", response_model=List[Dict[str, Any]])
async def list_workflow_executions(
    workflow_id: str,
    status: Optional[WorkflowStatus] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List executions for a specific workflow.
    
    Args:
        workflow_id: Workflow ID
        status: Filter by execution status
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of executions
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID")
    
    query = select(WorkflowExecution).where(
        WorkflowExecution.workflow_id == workflow_uuid,
        WorkflowExecution.deleted_at.is_(None)
    )
    
    if status:
        query = query.where(WorkflowExecution.status == status)
    
    query = query.order_by(WorkflowExecution.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    return [execution.to_dict() for execution in executions]


@router.get("/executions/{execution_id}", response_model=Dict[str, Any])
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


@router.post("/executions/{execution_id}/cancel", response_model=Dict[str, Any])
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel a workflow execution.
    
    Args:
        execution_id: Execution ID
        db: Database session
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


@router.post("/{workflow_id}/schedule", response_model=Dict[str, Any])
async def schedule_workflow(
    workflow_id: str,
    schedule_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Schedule a workflow for recurring execution.
    
    Args:
        workflow_id: Workflow ID
        schedule_data: Schedule configuration
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Schedule result
    """
    scheduler = get_workflow_scheduler()
    
    schedule_expression = schedule_data.get("schedule_expression")
    schedule_type = ScheduleType(schedule_data.get("schedule_type", "cron"))
    
    if not schedule_expression:
        raise HTTPException(status_code=400, detail="Schedule expression is required")
    
    success = await scheduler.schedule_workflow(
        workflow_id=workflow_id,
        schedule_expression=schedule_expression,
        schedule_type=schedule_type
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    logger.info(
        "Workflow scheduled",
        workflow_id=workflow_id,
        schedule_expression=schedule_expression,
        schedule_type=schedule_type.value,
        user_id=str(current_user.id)
    )
    
    return {
        "message": "Workflow scheduled successfully",
        "schedule_expression": schedule_expression,
        "schedule_type": schedule_type.value
    }


@router.delete("/{workflow_id}/schedule", response_model=Dict[str, Any])
async def unschedule_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Unschedule a workflow from recurring execution.
    
    Args:
        workflow_id: Workflow ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Unschedule result
    """
    scheduler = get_workflow_scheduler()
    
    success = await scheduler.unschedule_workflow(workflow_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    logger.info(
        "Workflow unscheduled",
        workflow_id=workflow_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Workflow unscheduled successfully"}


@router.get("/scheduled", response_model=List[Dict[str, Any]])
async def list_scheduled_workflows(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List all scheduled workflows.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of scheduled workflows
    """
    scheduler = get_workflow_scheduler()
    
    scheduled_workflows = await scheduler.get_scheduled_workflows()
    
    return scheduled_workflows


async def _validate_workflow_data(workflow_data: Dict[str, Any]) -> None:
    """
    Validate workflow data.
    
    Args:
        workflow_data: Workflow data to validate
        
    Raises:
        WorkflowValidationError: If validation fails
    """
    errors = []
    
    # Required fields
    if "name" not in workflow_data:
        errors.append("Workflow name is required")
    
    # Validate config
    config = workflow_data.get("config", {})
    if not isinstance(config, dict):
        errors.append("Config must be a dictionary")
    
    # Validate priority
    priority = workflow_data.get("priority", "medium")
    try:
        WorkflowPriority(priority)
    except ValueError:
        errors.append(f"Invalid priority: {priority}")
    
    # Validate schedule if provided
    if "schedule_expression" in workflow_data:
        schedule_expr = workflow_data["schedule_expression"]
        if not isinstance(schedule_expr, str):
            errors.append("Schedule expression must be a string")
    
    if errors:
        raise WorkflowValidationError(
            f"Workflow validation failed: {'; '.join(errors)}",
            validation_errors=errors
        )
