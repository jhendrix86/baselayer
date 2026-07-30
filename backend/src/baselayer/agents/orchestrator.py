"""
BaseLayer Agent Orchestrator

Central orchestration for multi-agent system management,
task distribution, and coordination.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.agents import (
    Agent, AgentTask, AgentMetrics,
    AgentType, AgentStatus, TaskStatus
)
from ..models.user import User
from .lifecycle import AgentLifecycleManager
from .coordinator import TaskCoordinator
from .communicator import AgentCommunicator
from .monitor import AgentMonitor
from .scaler import AgentScaler
from .exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentLifecycleError,
    TaskCoordinationError
)

logger = get_logger(__name__)


class AgentOrchestrator:
    """
    Central agent orchestration system.
    
    Manages agent lifecycle, task distribution, communication,
    and performance monitoring with scaling capabilities.
    """
    
    def __init__(self):
        self.active_agents: Dict[str, Agent] = {}
        self.agent_tasks: Dict[str, List[AgentTask]] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.communication_bus: Dict[str, asyncio.Queue] = {}
        
        # Component managers
        self.lifecycle_manager = AgentLifecycleManager()
        self.task_coordinator = TaskCoordinator()
        self.agent_communicator = AgentCommunicator()
        self.agent_monitor = AgentMonitor()
        self.agent_scaler = AgentScaler()
        
        # Configuration
        self.max_concurrent_tasks: int = 10  # Optimized for i5-2400
        self.task_timeout: int = 300  # 5 minutes
        self.health_check_interval: int = 30  # seconds
        self.auto_scaling_enabled: bool = True
        
        # State
        self.orchestration_active: bool = False
        self.performance_metrics: Dict[str, Any] = {}
    
    async def start_orchestration(self) -> None:
        """Start the orchestration system."""
        if self.orchestration_active:
            return
        
        self.orchestration_active = True
        
        # Start component managers
        await self.lifecycle_manager.start()
        await self.task_coordinator.start()
        await self.agent_communicator.start()
        await self.agent_monitor.start()
        await self.agent_scaler.start()
        
        # Load active agents from database
        await self._load_active_agents()
        
        # Start orchestration loops
        asyncio.create_task(self._orchestration_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._task_processing_loop())
        
        logger.info("Agent orchestration started")
    
    async def stop_orchestration(self) -> None:
        """Stop the orchestration system."""
        self.orchestration_active = False
        
        # Stop component managers
        await self.lifecycle_manager.stop()
        await self.task_coordinator.stop()
        await self.agent_communicator.stop()
        await self.agent_monitor.stop()
        await self.agent_scaler.stop()
        
        logger.info("Agent orchestration stopped")
    
    async def register_agent(
        self,
        agent_type: AgentType,
        name: str,
        config: Dict[str, Any],
        capabilities: List[str],
        created_by: Optional[uuid.UUID] = None
    ) -> Agent:
        """
        Register a new agent in the orchestration system.
        
        Args:
            agent_type: Type of agent
            name: Agent name
            config: Agent configuration
            capabilities: Agent capabilities
            created_by: User who created the agent
            
        Returns:
            Agent: Registered agent
            
        Raises:
            AgentLifecycleError: If registration fails
        """
        try:
            # Create agent through lifecycle manager
            agent = await self.lifecycle_manager.create_agent(
                agent_type=agent_type,
                name=name,
                config=config,
                capabilities=capabilities,
                created_by=created_by
            )
            
            # Initialize communication channel
            self.communication_bus[str(agent.id)] = asyncio.Queue()
            
            # Add to active agents
            self.active_agents[str(agent.id)] = agent
            self.agent_tasks[str(agent.id)] = []
            
            # Start agent monitoring
            await self.agent_monitor.start_monitoring(agent)
            
            logger.info(
                "Agent registered in orchestration",
                agent_id=str(agent.id),
                name=name,
                agent_type=agent_type.value
            )
            
            return agent
            
        except Exception as e:
            raise AgentLifecycleError(f"Failed to register agent: {str(e)}") from e
    
    async def unregister_agent(
        self,
        agent_id: str,
        graceful_shutdown: bool = True
    ) -> bool:
        """
        Unregister an agent from the orchestration system.
        
        Args:
            agent_id: Agent ID
            graceful_shutdown: Whether to perform graceful shutdown
            
        Returns:
            bool: True if unregistered successfully
        """
        try:
            agent = self.active_agents.get(agent_id)
            if not agent:
                raise AgentNotFoundError(f"Agent not found: {agent_id}")
            
            # Stop monitoring
            await self.agent_monitor.stop_monitoring(agent_id)
            
            # Handle graceful shutdown
            if graceful_shutdown:
                await self._graceful_shutdown_agent(agent)
            
            # Remove from active agents
            del self.active_agents[agent_id]
            del self.agent_tasks[agent_id]
            
            # Remove communication channel
            self.communication_bus.pop(agent_id, None)
            
            # Deactivate through lifecycle manager
            await self.lifecycle_manager.deactivate_agent(agent_id)
            
            logger.info(
                "Agent unregistered from orchestration",
                agent_id=agent_id,
                graceful_shutdown=graceful_shutdown
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to unregister agent",
                agent_id=agent_id,
                error=str(e)
            )
            return False
    
    async def submit_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 0,
        required_capabilities: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> AgentTask:
        """
        Submit a task to the orchestration system.
        
        Args:
            task_type: Type of task
            task_data: Task data
            priority: Task priority (higher = more important)
            required_capabilities: Required agent capabilities
            timeout: Task timeout in seconds
            created_by: User who created the task
            
        Returns:
            AgentTask: Created task
            
        Raises:
            TaskCoordinationError: If task submission fails
        """
        try:
            # Create task through coordinator
            task = await self.task_coordinator.create_task(
                task_type=task_type,
                task_data=task_data,
                priority=priority,
                required_capabilities=required_capabilities,
                timeout=timeout or self.task_timeout,
                created_by=created_by
            )
            
            # Add to task queue
            await self.task_queue.put(task)
            
            logger.info(
                "Task submitted to orchestration",
                task_id=str(task.id),
                task_type=task_type,
                priority=priority
            )
            
            return task
            
        except Exception as e:
            raise TaskCoordinationError(f"Failed to submit task: {str(e)}") from e
    
    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get status of a specific agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Dict[str, Any]: Agent status
        """
        agent = self.active_agents.get(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")
        
        # Get basic agent info
        status = {
            "agent_id": agent_id,
            "name": agent.name,
            "type": agent.agent_type.value,
            "status": agent.status.value,
            "capabilities": agent.capabilities,
            "created_at": agent.created_at.isoformat(),
            "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
            "active_tasks": len(self.agent_tasks.get(agent_id, [])),
            "total_tasks": agent.total_tasks_completed,
            "performance_metrics": await self.agent_monitor.get_agent_metrics(agent_id)
        }
        
        return status
    
    async def get_orchestration_status(self) -> Dict[str, Any]:
        """
        Get overall orchestration system status.
        
        Returns:
            Dict[str, Any]: Orchestration status
        """
        # Count agents by status
        status_counts = {}
        for agent in self.active_agents.values():
            status = agent.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get task statistics
        total_tasks = sum(len(tasks) for tasks in self.agent_tasks.values())
        queue_size = self.task_queue.qsize()
        
        # Get system metrics
        system_metrics = await self.agent_monitor.get_system_metrics()
        
        status = {
            "orchestration_active": self.orchestration_active,
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {
                "total": len(self.active_agents),
                "by_status": status_counts,
                "by_type": self._get_agent_type_counts()
            },
            "tasks": {
                "total_active": total_tasks,
                "queue_size": queue_size,
                "completed_today": await self._get_completed_tasks_today()
            },
            "performance": system_metrics,
            "auto_scaling": {
                "enabled": self.auto_scaling_enabled,
                "current_scale": len(self.active_agents)
            }
        }
        
        return status
    
    async def _orchestration_loop(self) -> None:
        """Main orchestration loop."""
        while self.orchestration_active:
            try:
                # Check for auto-scaling needs
                if self.auto_scaling_enabled:
                    await self._check_scaling_needs()
                
                # Update performance metrics
                await self._update_performance_metrics()
                
                # Process agent communications
                await self._process_agent_communications()
                
                # Sleep before next iteration
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(
                    "Orchestration loop error",
                    error=str(e)
                )
                await asyncio.sleep(30)
    
    async def _health_check_loop(self) -> None:
        """Health check loop for agents."""
        while self.orchestration_active:
            try:
                # Check health of all active agents
                for agent_id, agent in list(self.active_agents.items()):
                    health = await self.agent_monitor.check_agent_health(agent)
                    
                    if not health["healthy"]:
                        logger.warning(
                            "Agent health check failed",
                            agent_id=agent_id,
                            health_issues=health.get("issues", [])
                        )
                        
                        # Attempt recovery
                        await self._attempt_agent_recovery(agent)
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(
                    "Health check loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _task_processing_loop(self) -> None:
        """Task processing loop."""
        while self.orchestration_active:
            try:
                # Get next task from queue
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=60.0
                )
                
                # Process task
                await self._process_task(task)
                
            except asyncio.TimeoutError:
                # No tasks in queue
                continue
            except Exception as e:
                logger.error(
                    "Task processing loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_task(self, task: AgentTask) -> None:
        """Process a single task."""
        try:
            # Find suitable agent
            suitable_agent = await self._find_suitable_agent(task)
            
            if not suitable_agent:
                # No suitable agent, requeue with lower priority
                await asyncio.sleep(5)
                await self.task_queue.put(task)
                return
            
            # Assign task to agent
            await self._assign_task_to_agent(suitable_agent, task)
            
            # Execute task
            await self._execute_task(suitable_agent, task)
            
        except Exception as e:
            logger.error(
                "Task processing failed",
                task_id=str(task.id),
                error=str(e)
            )
            
            # Mark task as failed
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            
            async with get_db_session() as session:
                session.add(task)
                await session.commit()
    
    async def _find_suitable_agent(self, task: AgentTask) -> Optional[Agent]:
        """Find a suitable agent for a task."""
        required_capabilities = task.required_capabilities or []
        
        # Find agents with required capabilities
        suitable_agents = []
        
        for agent in self.active_agents.values():
            if agent.status != AgentStatus.ACTIVE:
                continue
            
            # Check capabilities
            if required_capabilities:
                if not all(cap in agent.capabilities for cap in required_capabilities):
                    continue
            
            # Check task load
            current_tasks = len(self.agent_tasks.get(str(agent.id), []))
            if current_tasks >= agent.max_concurrent_tasks:
                continue
            
            suitable_agents.append(agent)
        
        if not suitable_agents:
            return None
        
        # Select best agent (least loaded)
        best_agent = min(
            suitable_agents,
            key=lambda a: len(self.agent_tasks.get(str(a.id), []))
        )
        
        return best_agent
    
    async def _assign_task_to_agent(self, agent: Agent, task: AgentTask) -> None:
        """Assign a task to an agent."""
        # Update task
        task.agent_id = agent.id
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.utcnow()
        
        # Add to agent's task list
        agent_id = str(agent.id)
        if agent_id not in self.agent_tasks:
            self.agent_tasks[agent_id] = []
        self.agent_tasks[agent_id].append(task)
        
        # Update agent
        agent.last_activity = datetime.utcnow()
        agent.current_tasks += 1
        
        # Save to database
        async with get_db_session() as session:
            session.add(task)
            session.add(agent)
            await session.commit()
        
        logger.info(
            "Task assigned to agent",
            task_id=str(task.id),
            agent_id=agent_id,
            task_type=task.task_type
        )
    
    async def _execute_task(self, agent: Agent, task: AgentTask) -> None:
        """Execute a task on an agent."""
        try:
            # Send task to agent
            await self.agent_communicator.send_message(
                target_agent_id=str(agent.id),
                message_type="task_execution",
                message_data={
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "task_data": task.task_data,
                    "timeout": task.timeout
                }
            )
            
            # Wait for task completion (with timeout)
            timeout = task.timeout or self.task_timeout
            
            try:
                result = await asyncio.wait_for(
                    self._wait_for_task_completion(task),
                    timeout=timeout
                )
                
                # Task completed successfully
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.utcnow()
                
                # Update agent metrics
                agent.total_tasks_completed += 1
                agent.current_tasks -= 1
                
                logger.info(
                    "Task completed successfully",
                    task_id=str(task.id),
                    agent_id=str(agent.id)
                )
                
            except asyncio.TimeoutError:
                # Task timed out
                task.status = TaskStatus.FAILED
                task.error_message = "Task execution timed out"
                task.completed_at = datetime.utcnow()
                agent.current_tasks -= 1
                
                logger.warning(
                    "Task execution timed out",
                    task_id=str(task.id),
                    agent_id=str(agent.id),
                    timeout=timeout
                )
            
            # Remove from agent's task list
            agent_id = str(agent.id)
            if agent_id in self.agent_tasks:
                self.agent_tasks[agent_id] = [
                    t for t in self.agent_tasks[agent_id]
                    if t.id != task.id
                ]
            
            # Save to database
            async with get_db_session() as session:
                session.add(task)
                session.add(agent)
                await session.commit()
            
        except Exception as e:
            # Task failed
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            agent.current_tasks -= 1
            
            logger.error(
                "Task execution failed",
                task_id=str(task.id),
                agent_id=str(agent.id),
                error=str(e)
            )
            
            # Save to database
            async with get_db_session() as session:
                session.add(task)
                session.add(agent)
                await session.commit()
    
    async def _wait_for_task_completion(self, task: AgentTask) -> Any:
        """Wait for task completion notification."""
        # In real implementation, this would wait for agent response
        # For now, simulate task execution
        await asyncio.sleep(1)
        
        # Simulate successful result
        return {
            "status": "completed",
            "result": f"Task {task.task_type} completed successfully",
            "execution_time": 1.0
        }
    
    async def _load_active_agents(self) -> None:
        """Load active agents from database."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.deleted_at.is_(None)
                )
            )
            agents = result.scalars().all()
            
            for agent in agents:
                self.active_agents[str(agent.id)] = agent
                self.agent_tasks[str(agent.id)] = []
                self.communication_bus[str(agent.id)] = asyncio.Queue()
                
                # Start monitoring
                await self.agent_monitor.start_monitoring(agent)
    
    async def _graceful_shutdown_agent(self, agent: Agent) -> None:
        """Perform graceful shutdown of an agent."""
        try:
            # Wait for current tasks to complete
            agent_id = str(agent.id)
            current_tasks = self.agent_tasks.get(agent_id, [])
            
            if current_tasks:
                logger.info(
                    "Waiting for agent tasks to complete",
                    agent_id=agent_id,
                    task_count=len(current_tasks)
                )
                
                # Wait up to 30 seconds for tasks to complete
                for _ in range(30):
                    if not self.agent_tasks.get(agent_id):
                        break
                    await asyncio.sleep(1)
            
            # Send shutdown signal
            await self.agent_communicator.send_message(
                target_agent_id=agent_id,
                message_type="shutdown",
                message_data={"graceful": True}
            )
            
        except Exception as e:
            logger.error(
                "Graceful shutdown failed",
                agent_id=str(agent.id),
                error=str(e)
            )
    
    async def _check_scaling_needs(self) -> None:
        """Check if auto-scaling is needed."""
        try:
            # Get current load metrics
            queue_size = self.task_queue.qsize()
            total_active_tasks = sum(len(tasks) for tasks in self.agent_tasks.values())
            active_agents = len(self.active_agents)
            
            # Scaling logic
            if queue_size > 10 and active_agents < 8:  # Scale up
                await self.agent_scaler.scale_up(1)
            elif queue_size < 2 and active_agents > 2:  # Scale down
                await self.agent_scaler.scale_down(1)
                
        except Exception as e:
            logger.error(
                "Scaling check failed",
                error=str(e)
            )
    
    async def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        try:
            self.performance_metrics = await self.agent_monitor.get_system_metrics()
        except Exception as e:
            logger.error(
                "Performance metrics update failed",
                error=str(e)
            )
    
    async def _process_agent_communications(self) -> None:
        """Process inter-agent communications."""
        try:
            # Process messages in communication bus
            for agent_id, queue in self.communication_bus.items():
                while not queue.empty():
                    try:
                        message = queue.get_nowait()
                        await self.agent_communicator.process_message(agent_id, message)
                    except asyncio.QueueEmpty:
                        break
        except Exception as e:
            logger.error(
                "Agent communication processing failed",
                error=str(e)
            )
    
    async def _attempt_agent_recovery(self, agent: Agent) -> None:
        """Attempt to recover an unhealthy agent."""
        try:
            # Simple recovery attempt - restart agent
            await self.lifecycle_manager.restart_agent(str(agent.id))
            
            logger.info(
                "Agent recovery attempted",
                agent_id=str(agent.id)
            )
            
        except Exception as e:
            logger.error(
                "Agent recovery failed",
                agent_id=str(agent.id),
                error=str(e)
            )
    
    def _get_agent_type_counts(self) -> Dict[str, int]:
        """Get agent counts by type."""
        type_counts = {}
        
        for agent in self.active_agents.values():
            agent_type = agent.agent_type.value
            type_counts[agent_type] = type_counts.get(agent_type, 0) + 1
        
        return type_counts
    
    async def _get_completed_tasks_today(self) -> int:
        """Get number of tasks completed today."""
        async with get_db_session() as session:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = await session.execute(
                select(func.count(AgentTask.id)).where(
                    AgentTask.status == TaskStatus.COMPLETED,
                    AgentTask.completed_at >= today
                )
            )
            
            return result.scalar() or 0
