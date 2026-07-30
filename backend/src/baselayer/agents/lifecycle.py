"""
BaseLayer Agent Lifecycle Manager

Agent lifecycle management including creation, activation,
deactivation, and health monitoring.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.agents import (
    Agent, AgentTask, AgentMetrics,
    AgentType, AgentStatus
)
from ..models.user import User
from .exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentLifecycleError,
    AgentConfigurationError
)

logger = get_logger(__name__)


class AgentLifecycleManager:
    """
    Agent lifecycle management system.
    
    Handles agent creation, activation, deactivation,
    configuration, and health monitoring.
    """
    
    def __init__(self):
        self.lifecycle_active: bool = False
        self.agent_configs: Dict[str, Dict[str, Any]] = {}
        self.health_check_interval: int = 30  # seconds
        self.max_agent_age: int = 86400  # 24 hours in seconds
        self.default_agent_config = {
            "max_concurrent_tasks": 5,
            "timeout": 300,
            "retry_attempts": 3,
            "memory_limit": 512,  # MB
            "cpu_limit": 0.5,  # CPU cores
        }
    
    async def start(self) -> None:
        """Start the lifecycle manager."""
        if self.lifecycle_active:
            return
        
        self.lifecycle_active = True
        asyncio.create_task(self._lifecycle_loop())
        
        logger.info("Agent lifecycle manager started")
    
    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        self.lifecycle_active = False
        logger.info("Agent lifecycle manager stopped")
    
    async def create_agent(
        self,
        agent_type: AgentType,
        name: str,
        config: Dict[str, Any],
        capabilities: List[str],
        created_by: Optional[uuid.UUID] = None
    ) -> Agent:
        """
        Create a new agent.
        
        Args:
            agent_type: Type of agent
            name: Agent name
            config: Agent configuration
            capabilities: Agent capabilities
            created_by: User who created the agent
            
        Returns:
            Agent: Created agent
            
        Raises:
            AgentLifecycleError: If creation fails
        """
        try:
            # Validate configuration
            await self._validate_agent_config(agent_type, config, capabilities)
            
            # Merge with default config
            merged_config = {**self.default_agent_config, **config}
            
            async with get_db_session() as session:
                # Create agent
                agent = Agent(
                    name=name,
                    agent_type=agent_type,
                    status=AgentStatus.CREATED,
                    config=merged_config,
                    capabilities=capabilities,
                    max_concurrent_tasks=merged_config["max_concurrent_tasks"],
                    created_by=created_by
                )
                
                session.add(agent)
                await session.commit()
                await session.refresh(agent)
                
                # Store configuration
                self.agent_configs[str(agent.id)] = merged_config
                
                logger.info(
                    "Agent created",
                    agent_id=str(agent.id),
                    name=name,
                    agent_type=agent_type.value
                )
                
                return agent
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to create agent: {str(e)}") from e
    
    async def activate_agent(self, agent_id: str) -> bool:
        """
        Activate an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: True if activated successfully
            
        Raises:
            AgentNotFoundError: If agent not found
            AgentLifecycleError: If activation fails
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.id == uuid.UUID(agent_id),
                        Agent.deleted_at.is_(None)
                    )
                )
                agent = result.scalar_one_or_none()
                
                if not agent:
                    raise AgentNotFoundError(f"Agent not found: {agent_id}")
                
                # Check if agent can be activated
                if agent.status != AgentStatus.CREATED and agent.status != AgentStatus.DEACTIVATED:
                    raise AgentLifecycleError(
                        f"Agent cannot be activated from status: {agent.status.value}"
                    )
                
                # Update agent status
                agent.status = AgentStatus.ACTIVE
                agent.activated_at = datetime.utcnow()
                agent.last_activity = datetime.utcnow()
                
                session.add(agent)
                await session.commit()
                
                logger.info(
                    "Agent activated",
                    agent_id=agent_id,
                    name=agent.name
                )
                
                return True
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to activate agent: {str(e)}") from e
    
    async def deactivate_agent(self, agent_id: str) -> bool:
        """
        Deactivate an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: True if deactivated successfully
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.id == uuid.UUID(agent_id),
                        Agent.deleted_at.is_(None)
                    )
                )
                agent = result.scalar_one_or_none()
                
                if not agent:
                    raise AgentNotFoundError(f"Agent not found: {agent_id}")
                
                # Update agent status
                agent.status = AgentStatus.DEACTIVATED
                agent.deactivated_at = datetime.utcnow()
                
                session.add(agent)
                await session.commit()
                
                logger.info(
                    "Agent deactivated",
                    agent_id=agent_id,
                    name=agent.name
                )
                
                return True
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to deactivate agent: {str(e)}") from e
    
    async def restart_agent(self, agent_id: str) -> bool:
        """
        Restart an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: True if restarted successfully
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        try:
            # Deactivate first
            await self.deactivate_agent(agent_id)
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Activate again
            return await self.activate_agent(agent_id)
            
        except Exception as e:
            raise AgentLifecycleError(f"Failed to restart agent: {str(e)}") from e
    
    async def update_agent_config(
        self,
        agent_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Update agent configuration.
        
        Args:
            agent_id: Agent ID
            config: New configuration
            
        Returns:
            bool: True if updated successfully
            
        Raises:
            AgentNotFoundError: If agent not found
            AgentConfigurationError: If config is invalid
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.id == uuid.UUID(agent_id),
                        Agent.deleted_at.is_(None)
                    )
                )
                agent = result.scalar_one_or_none()
                
                if not agent:
                    raise AgentNotFoundError(f"Agent not found: {agent_id}")
                
                # Validate new configuration
                await self._validate_agent_config(agent.agent_type, config, agent.capabilities)
                
                # Merge with existing config
                merged_config = {**agent.config, **config}
                
                # Update agent
                agent.config = merged_config
                agent.max_concurrent_tasks = merged_config.get("max_concurrent_tasks", 5)
                agent.updated_at = datetime.utcnow()
                
                session.add(agent)
                await session.commit()
                
                # Update stored config
                self.agent_configs[agent_id] = merged_config
                
                logger.info(
                    "Agent configuration updated",
                    agent_id=agent_id,
                    name=agent.name
                )
                
                return True
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to update agent config: {str(e)}") from e
    
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Dict[str, Any]: Agent metrics
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.id == uuid.UUID(agent_id),
                        Agent.deleted_at.is_(None)
                    )
                )
                agent = result.scalar_one_or_none()
                
                if not agent:
                    raise AgentNotFoundError(f"Agent not found: {agent_id}")
                
                # Get task metrics
                result = await session.execute(
                    select(
                        func.count(AgentTask.id),
                        func.count(func.nullif(AgentTask.status == 'completed', True)),
                        func.count(func.nullif(AgentTask.status == 'failed', True))
                    ).where(
                        AgentTask.agent_id == agent.id,
                        AgentTask.deleted_at.is_(None)
                    )
                )
                task_metrics = result.first()
                
                total_tasks = task_metrics[0] or 0
                completed_tasks = task_metrics[1] or 0
                failed_tasks = task_metrics[2] or 0
                
                # Calculate metrics
                success_rate = (completed_tasks / total_tasks) if total_tasks > 0 else 0.0
                failure_rate = (failed_tasks / total_tasks) if total_tasks > 0 else 0.0
                
                metrics = {
                    "agent_id": agent_id,
                    "name": agent.name,
                    "type": agent.agent_type.value,
                    "status": agent.status.value,
                    "created_at": agent.created_at.isoformat(),
                    "activated_at": agent.activated_at.isoformat() if agent.activated_at else None,
                    "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "failed_tasks": failed_tasks,
                    "success_rate": success_rate,
                    "failure_rate": failure_rate,
                    "current_tasks": agent.current_tasks,
                    "max_concurrent_tasks": agent.max_concurrent_tasks,
                    "capabilities": agent.capabilities,
                    "uptime_seconds": self._calculate_uptime(agent),
                    "health_status": await self._check_agent_health_simple(agent)
                }
                
                return metrics
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to get agent metrics: {str(e)}") from e
    
    async def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        agent_type: Optional[AgentType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Agent]:
        """
        List agents with optional filtering.
        
        Args:
            status: Filter by status
            agent_type: Filter by type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[Agent]: List of agents
        """
        async with get_db_session() as session:
            query = select(Agent).where(Agent.deleted_at.is_(None))
            
            if status:
                query = query.where(Agent.status == status)
            
            if agent_type:
                query = query.where(Agent.agent_type == agent_type)
            
            query = query.order_by(Agent.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            agents = result.scalars().all()
            
            return list(agents)
    
    async def cleanup_old_agents(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old inactive agents.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Dict[str, Any]: Cleanup results
        """
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.DEACTIVATED,
                        Agent.deactivated_at < cutoff_date,
                        Agent.deleted_at.is_(None)
                    )
                )
                old_agents = result.scalars().all()
                
                cleaned_count = 0
                for agent in old_agents:
                    agent.soft_delete()
                    session.add(agent)
                    cleaned_count += 1
                
                await session.commit()
                
                logger.info(
                    "Old agents cleaned up",
                    count=cleaned_count,
                    max_age_days=max_age_days
                )
                
                return {
                    "cleaned_count": cleaned_count,
                    "max_age_days": max_age_days,
                    "cutoff_date": cutoff_date.isoformat()
                }
                
        except Exception as e:
            raise AgentLifecycleError(f"Failed to cleanup old agents: {str(e)}") from e
    
    async def _lifecycle_loop(self) -> None:
        """Main lifecycle management loop."""
        while self.lifecycle_active:
            try:
                # Check agent health
                await self._health_check_all_agents()
                
                # Check for stale agents
                await self._check_stale_agents()
                
                # Update agent configurations if needed
                await self._update_agent_configurations()
                
                # Sleep before next iteration
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(
                    "Lifecycle loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _health_check_all_agents(self) -> None:
        """Perform health check on all active agents."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                active_agents = result.scalars().all()
                
                for agent in active_agents:
                    health = await self._check_agent_health_simple(agent)
                    
                    if not health["healthy"]:
                        logger.warning(
                            "Agent health check failed",
                            agent_id=str(agent.id),
                            health_issues=health.get("issues", [])
                        )
                        
                        # Mark as unhealthy
                        if agent.status == AgentStatus.ACTIVE:
                            agent.status = AgentStatus.UNHEALTHY
                            session.add(agent)
                
                await session.commit()
                
        except Exception as e:
            logger.error(
                "Agent health check failed",
                error=str(e)
            )
    
    async def _check_stale_agents(self) -> None:
        """Check for stale agents that need attention."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.last_activity < cutoff_time,
                        Agent.deleted_at.is_(None)
                    )
                )
                stale_agents = result.scalars().all()
                
                for agent in stale_agents:
                    logger.warning(
                        "Stale agent detected",
                        agent_id=str(agent.id),
                        name=agent.name,
                        last_activity=agent.last_activity.isoformat()
                    )
                    
                    # Mark as stale
                    agent.status = AgentStatus.STALE
                    session.add(agent)
                
                await session.commit()
                
        except Exception as e:
            logger.error(
                "Stale agent check failed",
                error=str(e)
            )
    
    async def _update_agent_configurations(self) -> None:
        """Update agent configurations if needed."""
        try:
            # In real implementation, this would check for configuration updates
            # For now, just log the action
            logger.debug("Agent configuration update check completed")
                
        except Exception as e:
            logger.error(
                "Agent configuration update failed",
                error=str(e)
            )
    
    async def _validate_agent_config(
        self,
        agent_type: AgentType,
        config: Dict[str, Any],
        capabilities: List[str]
    ) -> None:
        """
        Validate agent configuration.
        
        Args:
            agent_type: Type of agent
            config: Configuration to validate
            capabilities: Agent capabilities
            
        Raises:
            AgentConfigurationError: If configuration is invalid
        """
        errors = []
        
        # Check required fields
        required_fields = ["max_concurrent_tasks", "timeout"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate max_concurrent_tasks
        max_tasks = config.get("max_concurrent_tasks", 0)
        if max_tasks <= 0 or max_tasks > 20:
            errors.append("max_concurrent_tasks must be between 1 and 20")
        
        # Validate timeout
        timeout = config.get("timeout", 0)
        if timeout <= 0 or timeout > 3600:
            errors.append("timeout must be between 1 and 3600 seconds")
        
        # Validate memory limit
        memory_limit = config.get("memory_limit", 0)
        if memory_limit <= 0 or memory_limit > 4096:
            errors.append("memory_limit must be between 1 and 4096 MB")
        
        # Validate CPU limit
        cpu_limit = config.get("cpu_limit", 0)
        if cpu_limit <= 0 or cpu_limit > 4:
            errors.append("cpu_limit must be between 0.1 and 4")
        
        # Type-specific validation
        if agent_type == AgentType.WORKER:
            if "processing_rate" in config:
                processing_rate = config["processing_rate"]
                if processing_rate <= 0:
                    errors.append("processing_rate must be positive")
        
        elif agent_type == AgentType.ANALYZER:
            if "analysis_models" in config:
                models = config["analysis_models"]
                if not isinstance(models, list):
                    errors.append("analysis_models must be a list")
        
        elif agent_type == AgentType.COORDINATOR:
            if "coordination_strategy" in config:
                strategy = config["coordination_strategy"]
                valid_strategies = ["round_robin", "load_balanced", "priority_based"]
                if strategy not in valid_strategies:
                    errors.append(f"coordination_strategy must be one of: {valid_strategies}")
        
        if errors:
            raise AgentConfigurationError(
                f"Agent configuration validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    async def _check_agent_health_simple(self, agent: Agent) -> Dict[str, Any]:
        """Simple health check for an agent."""
        health = {
            "healthy": True,
            "issues": [],
            "last_check": datetime.utcnow().isoformat()
        }
        
        # Check if agent has recent activity
        if agent.last_activity:
            time_since_activity = datetime.utcnow() - agent.last_activity
            if time_since_activity > timedelta(minutes=5):
                health["healthy"] = False
                health["issues"].append("No recent activity")
        
        # Check task load
        if agent.current_tasks >= agent.max_concurrent_tasks:
            health["issues"].append("Agent at maximum capacity")
        
        # Check uptime
        uptime = self._calculate_uptime(agent)
        if uptime > self.max_agent_age:
            health["issues"].append("Agent uptime exceeds recommended limit")
        
        return health
    
    def _calculate_uptime(self, agent: Agent) -> int:
        """Calculate agent uptime in seconds."""
        if agent.activated_at:
            return int((datetime.utcnow() - agent.activated_at).total_seconds())
        return 0
    
    def get_lifecycle_stats(self) -> Dict[str, Any]:
        """Get lifecycle manager statistics."""
        return {
            "lifecycle_active": self.lifecycle_active,
            "health_check_interval": self.health_check_interval,
            "max_agent_age": self.max_agent_age,
            "stored_configs": len(self.agent_configs),
            "default_config": self.default_agent_config
        }
