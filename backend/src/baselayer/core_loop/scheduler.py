"""
BaseLayer Workflow Scheduler

Schedules and manages recurring workflow executions with cron support.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ..core.database import db_session_context
from ..models.core_loop import Workflow, WorkflowExecution, WorkflowStatus, ScheduleType
from .engine import WorkflowEngine

logger = get_logger(__name__)


class WorkflowScheduler:
    """
    Workflow scheduler for recurring executions.
    
    Manages cron-based scheduling and automatic workflow execution
    with optimized performance for i5-2400 hardware.
    """
    
    def __init__(self, workflow_engine: WorkflowEngine):
        self.workflow_engine = workflow_engine
        self.scheduled_workflows: Dict[str, Dict[str, Any]] = {}
        self.scheduler_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.check_interval = 60  # Check every minute
    
    async def start(self) -> None:
        """Start the workflow scheduler."""
        if self.scheduler_running:
            return
        
        self.scheduler_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("Workflow scheduler started")
    
    async def stop(self) -> None:
        """Stop the workflow scheduler."""
        self.scheduler_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Workflow scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self.scheduler_running:
            try:
                await self._check_and_execute_scheduled_workflows()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Scheduler loop error",
                    error=str(e)
                )
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute_scheduled_workflows(self) -> None:
        """Check for and execute scheduled workflows."""
        async with db_session_context() as session:
            # Get all active scheduled workflows
            result = await session.execute(
                select(Workflow).where(
                    Workflow.status == WorkflowStatus.ACTIVE,
                    Workflow.schedule_type.is_not(None),
                    Workflow.schedule_expression.is_not(None),
                    Workflow.deleted_at.is_(None)
                )
            )
            workflows = result.scalars().all()
            
            current_time = datetime.utcnow()
            
            for workflow in workflows:
                try:
                    if await self._should_execute_workflow(workflow, current_time):
                        await self._execute_scheduled_workflow(workflow)
                except Exception as e:
                    logger.error(
                        "Error checking scheduled workflow",
                        workflow_id=str(workflow.id),
                        workflow_name=workflow.name,
                        error=str(e)
                    )
    
    async def _should_execute_workflow(
        self,
        workflow: Workflow,
        current_time: datetime
    ) -> bool:
        """
        Check if a workflow should be executed now.
        
        Args:
            workflow: Workflow definition
            current_time: Current time
            
        Returns:
            bool: True if workflow should be executed
        """
        workflow_id = str(workflow.id)
        
        # Check if we have scheduling info for this workflow
        if workflow_id not in self.scheduled_workflows:
            # Initialize scheduling info
            self.scheduled_workflows[workflow_id] = {
                "last_execution": None,
                "next_execution": self._calculate_next_execution(workflow, current_time),
                "workflow": workflow
            }
        
        scheduling_info = self.scheduled_workflows[workflow_id]
        next_execution = scheduling_info["next_execution"]
        
        # Check if it's time to execute
        if next_execution and current_time >= next_execution:
            return True
        
        return False
    
    def _calculate_next_execution(
        self,
        workflow: Workflow,
        from_time: datetime
    ) -> Optional[datetime]:
        """
        Calculate the next execution time for a workflow.
        
        Args:
            workflow: Workflow definition
            from_time: Time to calculate from
            
        Returns:
            datetime: Next execution time or None
        """
        if not workflow.schedule_expression:
            return None
        
        try:
            if workflow.schedule_type == ScheduleType.CRON:
                # Use croniter for cron expressions
                cron = croniter(workflow.schedule_expression, from_time)
                return cron.get_next(datetime)
            
            elif workflow.schedule_type == ScheduleType.RECURRING:
                # Handle simple recurring expressions
                expression = workflow.schedule_expression.lower()
                
                if expression.startswith("every "):
                    # Parse "every X minutes/hours/days"
                    parts = expression.split()
                    if len(parts) >= 3:
                        interval = int(parts[1])
                        unit = parts[2]
                        
                        if unit.startswith("minute"):
                            return from_time + timedelta(minutes=interval)
                        elif unit.startswith("hour"):
                            return from_time + timedelta(hours=interval)
                        elif unit.startswith("day"):
                            return from_time + timedelta(days=interval)
            
            elif workflow.schedule_type == ScheduleType.ONCE:
                # One-time execution
                if workflow.schedule_expression:
                    try:
                        return datetime.fromisoformat(workflow.schedule_expression)
                    except ValueError:
                        pass
            
        except Exception as e:
            logger.error(
                "Error calculating next execution",
                workflow_id=str(workflow.id),
                schedule_expression=workflow.schedule_expression,
                error=str(e)
            )
        
        return None
    
    async def _execute_scheduled_workflow(self, workflow: Workflow) -> None:
        """
        Execute a scheduled workflow.
        
        Args:
            workflow: Workflow definition
        """
        workflow_id = str(workflow.id)
        current_time = datetime.utcnow()
        
        try:
            # Check for existing recent executions to avoid duplicates
            async with db_session_context() as session:
                result = await session.execute(
                    select(WorkflowExecution).where(
                        WorkflowExecution.workflow_id == workflow.id,
                        WorkflowExecution.created_at >= current_time - timedelta(minutes=5),
                        WorkflowExecution.deleted_at.is_(None)
                    ).order_by(WorkflowExecution.created_at.desc())
                )
                recent_execution = result.scalar_one_or_none()
                
                if recent_execution:
                    logger.info(
                        "Skipping duplicate scheduled execution",
                        workflow_id=workflow_id,
                        recent_execution_id=recent_execution.execution_id
                    )
                    # Update next execution time
                    scheduling_info = self.scheduled_workflows[workflow_id]
                    scheduling_info["next_execution"] = self._calculate_next_execution(
                        workflow, current_time
                    )
                    return
            
            # Execute workflow
            logger.info(
                "Executing scheduled workflow",
                workflow_id=workflow_id,
                workflow_name=workflow.name,
                schedule_expression=workflow.schedule_expression
            )
            
            # Use default input data or empty dict
            input_data = workflow.config.get("default_input_data", {})
            
            execution = await self.workflow_engine.start_workflow(
                workflow_id=workflow_id,
                input_data=input_data
            )
            
            # Update scheduling info
            scheduling_info = self.scheduled_workflows[workflow_id]
            scheduling_info["last_execution"] = current_time
            scheduling_info["next_execution"] = self._calculate_next_execution(
                workflow, current_time
            )
            
            logger.info(
                "Scheduled workflow executed",
                workflow_id=workflow_id,
                execution_id=execution.execution_id
            )
            
        except Exception as e:
            logger.error(
                "Error executing scheduled workflow",
                workflow_id=workflow_id,
                error=str(e)
            )
            
            # Update next execution time even on error to prevent infinite loops
            if workflow_id in self.scheduled_workflows:
                scheduling_info = self.scheduled_workflows[workflow_id]
                scheduling_info["next_execution"] = self._calculate_next_execution(
                    workflow, current_time + timedelta(minutes=5)  # Delay retry by 5 minutes
                )
    
    async def schedule_workflow(
        self,
        workflow_id: str,
        schedule_expression: str,
        schedule_type: ScheduleType = ScheduleType.CRON
    ) -> bool:
        """
        Schedule a workflow for recurring execution.
        
        Args:
            workflow_id: ID of the workflow to schedule
            schedule_expression: Schedule expression (cron or recurring)
            schedule_type: Type of schedule
            
        Returns:
            bool: True if scheduled successfully
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
                return False
            
            # Update workflow scheduling
            workflow.schedule_type = schedule_type
            workflow.schedule_expression = schedule_expression
            workflow.status = WorkflowStatus.ACTIVE
            
            session.add(workflow)
            await session.commit()
            
            # Update scheduler cache
            self.scheduled_workflows[workflow_id] = {
                "last_execution": None,
                "next_execution": self._calculate_next_execution(
                    workflow, datetime.utcnow()
                ),
                "workflow": workflow
            }
            
            logger.info(
                "Workflow scheduled",
                workflow_id=workflow_id,
                schedule_type=schedule_type.value,
                schedule_expression=schedule_expression
            )
            
            return True
    
    async def unschedule_workflow(self, workflow_id: str) -> bool:
        """
        Unschedule a workflow from recurring execution.
        
        Args:
            workflow_id: ID of the workflow to unschedule
            
        Returns:
            bool: True if unscheduled successfully
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
                return False
            
            # Remove scheduling
            workflow.schedule_type = None
            workflow.schedule_expression = None
            
            session.add(workflow)
            await session.commit()
            
            # Remove from scheduler cache
            self.scheduled_workflows.pop(workflow_id, None)
            
            logger.info(
                "Workflow unscheduled",
                workflow_id=workflow_id
            )
            
            return True
    
    async def get_scheduled_workflows(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled workflows with their next execution times.
        
        Returns:
            List[Dict[str, Any]]: List of scheduled workflows
        """
        scheduled_workflows = []
        
        for workflow_id, scheduling_info in self.scheduled_workflows.items():
            workflow = scheduling_info["workflow"]
            
            scheduled_workflows.append({
                "workflow_id": workflow_id,
                "workflow_name": workflow.name,
                "schedule_type": workflow.schedule_type.value if workflow.schedule_type else None,
                "schedule_expression": workflow.schedule_expression,
                "last_execution": scheduling_info["last_execution"],
                "next_execution": scheduling_info["next_execution"],
                "status": workflow.status.value,
            })
        
        return scheduled_workflows
    
    async def get_next_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the next scheduled executions.
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List[Dict[str, Any]]: List of next executions
        """
        current_time = datetime.utcnow()
        next_executions = []
        
        for workflow_id, scheduling_info in self.scheduled_workflows.items():
            next_execution = scheduling_info["next_execution"]
            
            if next_execution and next_execution > current_time:
                workflow = scheduling_info["workflow"]
                
                next_executions.append({
                    "workflow_id": workflow_id,
                    "workflow_name": workflow.name,
                    "next_execution": next_execution,
                    "schedule_expression": workflow.schedule_expression,
                    "time_until_execution": next_execution - current_time,
                })
        
        # Sort by next execution time
        next_executions.sort(key=lambda x: x["next_execution"])
        
        return next_executions[:limit]
    
    async def update_schedule(
        self,
        workflow_id: str,
        schedule_expression: str,
        schedule_type: ScheduleType = ScheduleType.CRON
    ) -> bool:
        """
        Update the schedule for a workflow.
        
        Args:
            workflow_id: ID of the workflow
            schedule_expression: New schedule expression
            schedule_type: New schedule type
            
        Returns:
            bool: True if updated successfully
        """
        return await self.schedule_workflow(workflow_id, schedule_expression, schedule_type)
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get the current status of the scheduler.
        
        Returns:
            Dict[str, Any]: Scheduler status information
        """
        return {
            "running": self.scheduler_running,
            "scheduled_workflows_count": len(self.scheduled_workflows),
            "check_interval": self.check_interval,
            "next_executions_count": len([
                info for info in self.scheduled_workflows.values()
                if info["next_execution"] and info["next_execution"] > datetime.utcnow()
            ])
        }
