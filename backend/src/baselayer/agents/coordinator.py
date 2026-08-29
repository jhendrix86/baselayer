"""
BaseLayer Task Coordinator

Task distribution, coordination, and load balancing
for the Multi-Agent Orchestration subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.agents import (
    Agent, AgentTask, AgentMetrics,
    AgentType, AgentStatus, TaskStatus
)
from ..models.user import User
from .exceptions import (
    TaskCoordinationError,
    AgentNotFoundError,
    AgentError
)

logger = get_logger(__name__)


class TaskCoordinator:
    """
    Task coordination and distribution system.
    
    Handles task assignment, load balancing, and coordination
    across multiple agents with different strategies.
    """
    
    def __init__(self):
        self.coordination_active: bool = False
        self.coordination_strategies = {
            "round_robin": self._round_robin_strategy,
            "load_balanced": self._load_balanced_strategy,
            "priority_based": self._priority_based_strategy,
            "capability_based": self._capability_based_strategy
        }
        self.default_strategy = "load_balanced"
        self.task_priorities = {
            "critical": 100,
            "high": 75,
            "medium": 50,
            "low": 25
        }
        self.max_task_age: int = 3600  # 1 hour
        self.task_timeout: int = 300  # 5 minutes
        self.retry_attempts: int = 3
        
        # Load balancing state
        self.agent_loads: Dict[str, int] = {}
        self.round_robin_index: int = 0
        self.task_queue: List[AgentTask] = []
        self.active_tasks: Dict[str, AgentTask] = {}
    
    async def start(self) -> None:
        """Start the task coordinator."""
        if self.coordination_active:
            return
        
        self.coordination_active = True
        asyncio.create_task(self._coordination_loop())
        
        logger.info("Task coordinator started")
    
    async def stop(self) -> None:
        """Stop the task coordinator."""
        self.coordination_active = False
        logger.info("Task coordinator stopped")
    
    async def create_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 50,
        required_capabilities: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        retry_attempts: Optional[int] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> AgentTask:
        """
        Create a new task.
        
        Args:
            task_type: Type of task
            task_data: Task data
            priority: Task priority (0-100)
            required_capabilities: Required agent capabilities
            timeout: Task timeout in seconds
            retry_attempts: Number of retry attempts
            created_by: User who created the task
            
        Returns:
            AgentTask: Created task
            
        Raises:
            TaskCoordinationError: If task creation fails
        """
        try:
            async with db_session_context() as session:
                # Create task
                task = AgentTask(
                    task_type=task_type,
                    task_data=task_data,
                    priority=priority,
                    required_capabilities=required_capabilities or [],
                    timeout=timeout or self.task_timeout,
                    retry_attempts=retry_attempts or self.retry_attempts,
                    status=TaskStatus.PENDING,
                    created_by=created_by
                )
                
                session.add(task)
                await session.commit()
                await session.refresh(task)
                
                # Add to task queue
                self.task_queue.append(task)
                self.active_tasks[str(task.id)] = task
                
                logger.info(
                    "Task created",
                    task_id=str(task.id),
                    task_type=task_type,
                    priority=priority
                )
                
                return task
                
        except Exception as e:
            raise TaskCoordinationError(f"Failed to create task: {str(e)}") from e
    
    async def assign_task(
        self,
        task_id: str,
        strategy: Optional[str] = None
    ) -> Optional[Agent]:
        """
        Assign a task to an agent.
        
        Args:
            task_id: Task ID
            strategy: Assignment strategy
            
        Returns:
            Agent: Assigned agent or None
            
        Raises:
            TaskCoordinationError: If assignment fails
        """
        try:
            task = self.active_tasks.get(task_id)
            if not task:
                raise TaskCoordinationError(f"Task not found: {task_id}")
            
            if task.status != TaskStatus.PENDING:
                raise TaskCoordinationError(f"Task not in pending state: {task.status.value}")
            
            # Select strategy
            strategy = strategy or self.default_strategy
            if strategy not in self.coordination_strategies:
                raise TaskCoordinationError(f"Unknown strategy: {strategy}")
            
            # Find suitable agent
            agent = await self.coordination_strategies[strategy](task)
            
            if not agent:
                raise TaskCoordinationError("No suitable agent found for task")
            
            # Assign task to agent
            await self._assign_task_to_agent(agent, task)
            
            logger.info(
                "Task assigned to agent",
                task_id=task_id,
                agent_id=str(agent.id),
                strategy=strategy
            )
            
            return agent
            
        except Exception as e:
            raise TaskCoordinationError(f"Failed to assign task: {str(e)}") from e
    
    async def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Mark a task as completed or failed.
        
        Args:
            task_id: Task ID
            result: Task result
            error: Error message if failed
            
        Returns:
            bool: True if completed successfully
        """
        try:
            task = self.active_tasks.get(task_id)
            if not task:
                raise TaskCoordinationError(f"Task not found: {task_id}")
            
            async with db_session_context() as session:
                if error:
                    # Task failed
                    task.status = TaskStatus.FAILED
                    task.error_message = error
                    task.completed_at = datetime.utcnow()
                    
                    # Check if retry is needed
                    if task.retry_count < task.retry_attempts:
                        task.retry_count += 1
                        task.status = TaskStatus.PENDING
                        task.error_message = None
                        
                        logger.info(
                            "Task retry scheduled",
                            task_id=task_id,
                            retry_attempt=task.retry_count
                        )
                    
                else:
                    # Task completed
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = datetime.utcnow()
                    
                    # Update agent metrics
                    if task.agent_id:
                        await self._update_agent_metrics(task.agent_id, True)
                
                session.add(task)
                await session.commit()
                
                # Update active tasks
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    self.active_tasks.pop(task_id, None)
                    if task in self.task_queue:
                        self.task_queue.remove(task)
                
                logger.info(
                    "Task completed",
                    task_id=task_id,
                    status=task.status.value
                )
                
                return True
                
        except Exception as e:
            raise TaskCoordinationError(f"Failed to complete task: {str(e)}") from e
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and details.
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict[str, Any]: Task status
            
        Raises:
            TaskCoordinationError: If task not found
        """
        try:
            task = self.active_tasks.get(task_id)
            if not task:
                raise TaskCoordinationError(f"Task not found: {task_id}")
            
            status = {
                "task_id": task_id,
                "task_type": task.task_type,
                "status": task.status.value,
                "priority": task.priority,
                "required_capabilities": task.required_capabilities,
                "timeout": task.timeout,
                "retry_attempts": task.retry_attempts,
                "retry_count": task.retry_count,
                "created_at": task.created_at.isoformat(),
                "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "agent_id": str(task.agent_id) if task.agent_id else None,
                "result": task.result,
                "error_message": task.error_message
            }
            
            return status
            
        except Exception as e:
            raise TaskCoordinationError(f"Failed to get task status: {str(e)}") from e
    
    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        agent_id: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AgentTask]:
        """
        List tasks with optional filtering.
        
        Args:
            status: Filter by status
            agent_id: Filter by agent ID
            task_type: Filter by task type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[AgentTask]: List of tasks
        """
        async with db_session_context() as session:
            query = select(AgentTask).where(AgentTask.deleted_at.is_(None))
            
            if status:
                query = query.where(AgentTask.status == status)
            
            if agent_id:
                query = query.where(AgentTask.agent_id == uuid.UUID(agent_id))
            
            if task_type:
                query = query.where(AgentTask.task_type == task_type)
            
            query = query.order_by(AgentTask.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            return list(tasks)
    
    async def get_coordination_stats(self) -> Dict[str, Any]:
        """
        Get coordination statistics.
        
        Returns:
            Dict[str, Any]: Coordination statistics
        """
        try:
            async with db_session_context() as session:
                # Get task counts by status
                result = await session.execute(
                    select(
                        AgentTask.status,
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.deleted_at.is_(None)
                    ).group_by(AgentTask.status)
                )
                task_counts = dict(result.all())
                
                # Get agent load distribution
                result = await session.execute(
                    select(
                        AgentTask.agent_id,
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.status == TaskStatus.ASSIGNED,
                        AgentTask.deleted_at.is_(None)
                    ).group_by(AgentTask.agent_id)
                )
                agent_loads = dict(result.all())
                
                # Get task type distribution
                result = await session.execute(
                    select(
                        AgentTask.task_type,
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.deleted_at.is_(None)
                    ).group_by(AgentTask.task_type)
                )
                task_types = dict(result.all())
                
                stats = {
                    "coordination_active": self.coordination_active,
                    "default_strategy": self.default_strategy,
                    "available_strategies": list(self.coordination_strategies.keys()),
                    "tasks": {
                        "total": sum(task_counts.values()),
                        "by_status": task_counts,
                        "by_type": task_types,
                        "queue_size": len(self.task_queue),
                        "active": len(self.active_tasks)
                    },
                    "agents": {
                        "total_load": sum(agent_loads.values()),
                        "load_distribution": agent_loads,
                        "active_agents": len(self.agent_loads)
                    },
                    "performance": {
                        "average_task_time": await self._calculate_average_task_time(),
                        "success_rate": await self._calculate_success_rate(),
                        "retry_rate": await self._calculate_retry_rate()
                    }
                }
                
                return stats
                
        except Exception as e:
            raise TaskCoordinationError(f"Failed to get coordination stats: {str(e)}") from e
    
    async def _coordination_loop(self) -> None:
        """Main coordination loop."""
        while self.coordination_active:
            try:
                # Process pending tasks
                await self._process_pending_tasks()
                
                # Update agent loads
                await self._update_agent_loads()
                
                # Clean up old tasks
                await self._cleanup_old_tasks()
                
                # Sleep before next iteration
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(
                    "Coordination loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_pending_tasks(self) -> None:
        """Process pending tasks in the queue."""
        pending_tasks = [task for task in self.task_queue if task.status == TaskStatus.PENDING]
        
        # Sort by priority
        pending_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        for task in pending_tasks:
            try:
                # Assign task using default strategy
                await self.assign_task(str(task.id), self.default_strategy)
            except TaskCoordinationError:
                # No suitable agent available, skip for now
                continue
    
    async def _update_agent_loads(self) -> None:
        """Update agent load information."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(
                        Agent.id,
                        func.count(AgentTask.id)
                    ).join(
                        AgentTask, Agent.id == AgentTask.agent_id
                    ).where(
                        Agent.status == AgentStatus.ACTIVE,
                        AgentTask.status == TaskStatus.ASSIGNED,
                        Agent.deleted_at.is_(None),
                        AgentTask.deleted_at.is_(None)
                    ).group_by(Agent.id)
                )
                
                self.agent_loads = {
                    str(agent_id): load for agent_id, load in result.all()
                }
                
        except Exception as e:
            logger.error(
                "Failed to update agent loads",
                error=str(e)
            )
    
    async def _cleanup_old_tasks(self) -> None:
        """Clean up old completed or failed tasks."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(AgentTask).where(
                        AgentTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]),
                        AgentTask.completed_at < cutoff_time,
                        AgentTask.deleted_at.is_(None)
                    )
                )
                old_tasks = result.scalars().all()
                
                for task in old_tasks:
                    task.soft_delete()
                    session.add(task)
                    
                    # Remove from active tasks
                    self.active_tasks.pop(str(task.id), None)
                
                await session.commit()
                
                logger.debug(
                    "Old tasks cleaned up",
                    count=len(old_tasks)
                )
                
        except Exception as e:
            logger.error(
                "Failed to cleanup old tasks",
                error=str(e)
            )
    
    async def _round_robin_strategy(self, task: AgentTask) -> Optional[Agent]:
        """Round-robin task assignment strategy."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    ).order_by(Agent.created_at)
                )
                agents = result.scalars().all()
                
                if not agents:
                    return None
                
                # Check capabilities
                suitable_agents = []
                for agent in agents:
                    if all(cap in agent.capabilities for cap in task.required_capabilities):
                        current_load = self.agent_loads.get(str(agent.id), 0)
                        if current_load < agent.max_concurrent_tasks:
                            suitable_agents.append(agent)
                
                if not suitable_agents:
                    return None
                
                # Round-robin selection
                agent = suitable_agents[self.round_robin_index % len(suitable_agents)]
                self.round_robin_index += 1
                
                return agent
                
        except Exception as e:
            logger.error(
                "Round-robin strategy failed",
                error=str(e)
            )
            return None
    
    async def _load_balanced_strategy(self, task: AgentTask) -> Optional[Agent]:
        """Load-balanced task assignment strategy."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                agents = result.scalars().all()
                
                if not agents:
                    return None
                
                # Find suitable agents with lowest load
                suitable_agents = []
                for agent in agents:
                    if all(cap in agent.capabilities for cap in task.required_capabilities):
                        current_load = self.agent_loads.get(str(agent.id), 0)
                        if current_load < agent.max_concurrent_tasks:
                            suitable_agents.append((agent, current_load))
                
                if not suitable_agents:
                    return None
                
                # Select agent with lowest load
                suitable_agents.sort(key=lambda x: x[1])
                return suitable_agents[0][0]
                
        except Exception as e:
            logger.error(
                "Load-balanced strategy failed",
                error=str(e)
            )
            return None
    
    async def _priority_based_strategy(self, task: AgentTask) -> Optional[Agent]:
        """Priority-based task assignment strategy."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    ).order_by(Agent.total_tasks_completed.desc())
                )
                agents = result.scalars().all()
                
                if not agents:
                    return None
                
                # Find suitable agents with highest performance
                suitable_agents = []
                for agent in agents:
                    if all(cap in agent.capabilities for cap in task.required_capabilities):
                        current_load = self.agent_loads.get(str(agent.id), 0)
                        if current_load < agent.max_concurrent_tasks:
                            suitable_agents.append((agent, agent.total_tasks_completed))
                
                if not suitable_agents:
                    return None
                
                # Select agent with highest performance
                suitable_agents.sort(key=lambda x: x[1], reverse=True)
                return suitable_agents[0][0]
                
        except Exception as e:
            logger.error(
                "Priority-based strategy failed",
                error=str(e)
            )
            return None
    
    async def _capability_based_strategy(self, task: AgentTask) -> Optional[Agent]:
        """Capability-based task assignment strategy."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                agents = result.scalars().all()
                
                if not agents:
                    return None
                
                # Score agents based on capability match and load
                scored_agents = []
                for agent in agents:
                    # Calculate capability match score
                    required_caps = set(task.required_capabilities)
                    agent_caps = set(agent.capabilities)
                    
                    if required_caps.issubset(agent_caps):
                        match_score = len(required_caps) / len(agent_caps) if agent_caps else 0
                        
                        current_load = self.agent_loads.get(str(agent.id), 0)
                        load_score = 1 - (current_load / agent.max_concurrent_tasks)
                        
                        total_score = (match_score * 0.7) + (load_score * 0.3)
                        
                        if current_load < agent.max_concurrent_tasks:
                            scored_agents.append((agent, total_score))
                
                if not scored_agents:
                    return None
                
                # Select agent with highest score
                scored_agents.sort(key=lambda x: x[1], reverse=True)
                return scored_agents[0][0]
                
        except Exception as e:
            logger.error(
                "Capability-based strategy failed",
                error=str(e)
            )
            return None
    
    async def _assign_task_to_agent(self, agent: Agent, task: AgentTask) -> None:
        """Assign a task to an agent."""
        async with db_session_context() as session:
            # Update task
            task.agent_id = agent.id
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.utcnow()
            
            # Update agent
            agent.current_tasks += 1
            agent.last_activity = datetime.utcnow()
            
            session.add(task)
            session.add(agent)
            await session.commit()
            
            # Update agent load
            self.agent_loads[str(agent.id)] = self.agent_loads.get(str(agent.id), 0) + 1
    
    async def _update_agent_metrics(self, agent_id: uuid.UUID, success: bool) -> None:
        """Update agent performance metrics."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(Agent.id == agent_id)
                )
                agent = result.scalar_one_or_none()
                
                if agent:
                    if success:
                        agent.total_tasks_completed += 1
                    else:
                        agent.total_tasks_failed += 1
                    
                    session.add(agent)
                    await session.commit()
                    
        except Exception as e:
            logger.error(
                "Failed to update agent metrics",
                agent_id=str(agent_id),
                error=str(e)
            )
    
    async def _calculate_average_task_time(self) -> float:
        """Calculate average task completion time."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(func.avg(
                        func.extract('epoch', AgentTask.completed_at) - 
                        func.extract('epoch', AgentTask.started_at)
                    )).where(
                        AgentTask.status == TaskStatus.COMPLETED,
                        AgentTask.started_at.is_not(None),
                        AgentTask.completed_at.is_not(None),
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                avg_time = result.scalar()
                return float(avg_time) if avg_time else 0.0
                
        except Exception as e:
            logger.error(
                "Failed to calculate average task time",
                error=str(e)
            )
            return 0.0
    
    async def _calculate_success_rate(self) -> float:
        """Calculate task success rate."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(
                        func.count(func.nullif(AgentTask.status == 'completed', True)),
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]),
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                completed, total = result.first()
                return (completed / total) if total > 0 else 0.0
                
        except Exception as e:
            logger.error(
                "Failed to calculate success rate",
                error=str(e)
            )
            return 0.0
    
    async def _calculate_retry_rate(self) -> float:
        """Calculate task retry rate."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(
                        func.count(func.nullif(AgentTask.retry_count > 0, True)),
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                retried, total = result.first()
                return (retried / total) if total > 0 else 0.0
                
        except Exception as e:
            logger.error(
                "Failed to calculate retry rate",
                error=str(e)
            )
            return 0.0
