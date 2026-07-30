"""
BaseLayer Agent Scaler

Agent scaling and load balancing for the Multi-Agent Orchestration subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.agents import (
    Agent, AgentTask,
    AgentType, AgentStatus, TaskStatus
)
from .lifecycle import AgentLifecycleManager
from .exceptions import (
    AgentScalingError,
    AgentNotFoundError,
    AgentLifecycleError
)

logger = get_logger(__name__)


class AgentScaler:
    """
    Agent scaling and load balancing system.
    
    Handles automatic scaling of agents based on load,
    performance metrics, and resource availability.
    """
    
    def __init__(self):
        self.scaling_active: bool = False
        self.scaling_interval: int = 60  # seconds
        self.max_agents_per_type: Dict[AgentType, int] = {
            AgentType.WORKER: 8,
            AgentType.ANALYZER: 4,
            AgentType.COORDINATOR: 2,
            AgentType.MONITOR: 2
        }
        self.min_agents_per_type: Dict[AgentType, int] = {
            AgentType.WORKER: 1,
            AgentType.ANALYZER: 1,
            AgentType.COORDINATOR: 1,
            AgentType.MONITOR: 1
        }
        self.scale_up_threshold: float = 0.8  # 80% capacity
        self.scale_down_threshold: float = 0.3  # 30% capacity
        self.scale_up_cooldown: int = 300  # 5 minutes
        self.scale_down_cooldown: int = 600  # 10 minutes
        self.last_scale_actions: Dict[str, datetime] = {}
        
        # Scaling metrics
        self.scaling_metrics = {
            "scale_up_actions": 0,
            "scale_down_actions": 0,
            "total_agents_created": 0,
            "total_agents_removed": 0
        }
    
    async def start(self) -> None:
        """Start the scaling system."""
        if self.scaling_active:
            return
        
        self.scaling_active = True
        asyncio.create_task(self._scaling_loop())
        
        logger.info("Agent scaler started")
    
    async def stop(self) -> None:
        """Stop the scaling system."""
        self.scaling_active = False
        logger.info("Agent scaler stopped")
    
    async def scale_up(
        self,
        agent_type: AgentType,
        count: int = 1,
        reason: str = "Manual scaling"
    ) -> List[Agent]:
        """
        Scale up agents of a specific type.
        
        Args:
            agent_type: Type of agent to scale up
            count: Number of agents to create
            reason: Reason for scaling
            
        Returns:
            List[Agent]: Created agents
            
        Raises:
            AgentScalingError: If scaling fails
        """
        try:
            # Check cooldown
            cooldown_key = f"scale_up_{agent_type.value}"
            last_action = self.last_scale_actions.get(cooldown_key)
            
            if last_action and (datetime.utcnow() - last_action) < timedelta(seconds=self.scale_up_cooldown):
                raise AgentScalingError(f"Scale up cooldown active for {agent_type.value}")
            
            # Check maximum limit
            current_count = await self._get_agent_count_by_type(agent_type)
            max_count = self.max_agents_per_type[agent_type]
            
            if current_count + count > max_count:
                raise AgentScalingError(f"Cannot scale up {agent_type.value}: would exceed maximum of {max_count}")
            
            # Create agents
            created_agents = []
            lifecycle_manager = AgentLifecycleManager()
            
            for i in range(count):
                try:
                    agent = await lifecycle_manager.create_agent(
                        agent_type=agent_type,
                        name=f"{agent_type.value}_scaled_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{i}",
                        config=self._get_default_config_for_type(agent_type),
                        capabilities=self._get_default_capabilities_for_type(agent_type)
                    )
                    
                    # Activate the agent
                    await lifecycle_manager.activate_agent(str(agent.id))
                    
                    created_agents.append(agent)
                    
                except Exception as e:
                    logger.error(
                        "Failed to create scaled agent",
                        agent_type=agent_type.value,
                        error=str(e)
                    )
            
            if created_agents:
                # Update metrics
                self.scaling_metrics["scale_up_actions"] += 1
                self.scaling_metrics["total_agents_created"] += len(created_agents)
                
                # Update cooldown
                self.last_scale_actions[cooldown_key] = datetime.utcnow()
                
                logger.info(
                    "Agents scaled up",
                    agent_type=agent_type.value,
                    count=len(created_agents),
                    reason=reason,
                    total_agents=current_count + len(created_agents)
                )
            
            return created_agents
            
        except Exception as e:
            raise AgentScalingError(f"Failed to scale up {agent_type.value}: {str(e)}") from e
    
    async def scale_down(
        self,
        agent_type: AgentType,
        count: int = 1,
        reason: str = "Manual scaling"
    ) -> List[Agent]:
        """
        Scale down agents of a specific type.
        
        Args:
            agent_type: Type of agent to scale down
            count: Number of agents to remove
            reason: Reason for scaling
            
        Returns:
            List[Agent]: Removed agents
            
        Raises:
            AgentScalingError: If scaling fails
        """
        try:
            # Check cooldown
            cooldown_key = f"scale_down_{agent_type.value}"
            last_action = self.last_scale_actions.get(cooldown_key)
            
            if last_action and (datetime.utcnow() - last_action) < timedelta(seconds=self.scale_down_cooldown):
                raise AgentScalingError(f"Scale down cooldown active for {agent_type.value}")
            
            # Check minimum limit
            current_count = await self._get_agent_count_by_type(agent_type)
            min_count = self.min_agents_per_type[agent_type]
            
            if current_count - count < min_count:
                raise AgentScalingError(f"Cannot scale down {agent_type.value}: would go below minimum of {min_count}")
            
            # Get agents to remove (least busy ones)
            agents_to_remove = await self._get_agents_for_removal(agent_type, count)
            
            if not agents_to_remove:
                raise AgentScalingError(f"No suitable agents found for removal: {agent_type.value}")
            
            # Deactivate agents
            removed_agents = []
            lifecycle_manager = AgentLifecycleManager()
            
            for agent in agents_to_remove:
                try:
                    # Ensure agent is not busy
                    if agent.current_tasks > 0:
                        logger.warning(
                            "Agent has active tasks, skipping removal",
                            agent_id=str(agent.id),
                            current_tasks=agent.current_tasks
                        )
                        continue
                    
                    # Deactivate agent
                    await lifecycle_manager.deactivate_agent(str(agent.id))
                    
                    removed_agents.append(agent)
                    
                except Exception as e:
                    logger.error(
                        "Failed to deactivate scaled agent",
                        agent_id=str(agent.id),
                        error=str(e)
                    )
            
            if removed_agents:
                # Update metrics
                self.scaling_metrics["scale_down_actions"] += 1
                self.scaling_metrics["total_agents_removed"] += len(removed_agents)
                
                # Update cooldown
                self.last_scale_actions[cooldown_key] = datetime.utcnow()
                
                logger.info(
                    "Agents scaled down",
                    agent_type=agent_type.value,
                    count=len(removed_agents),
                    reason=reason,
                    total_agents=current_count - len(removed_agents)
                )
            
            return removed_agents
            
        except Exception as e:
            raise AgentScalingError(f"Failed to scale down {agent_type.value}: {str(e)}") from e
    
    async def auto_scale(self) -> Dict[str, Any]:
        """
        Perform automatic scaling based on current load.
        
        Returns:
            Dict[str, Any]: Scaling results
        """
        results = {
            "scale_up_actions": [],
            "scale_down_actions": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Check each agent type
            for agent_type in AgentType:
                try:
                    # Get current metrics
                    metrics = await self._get_type_metrics(agent_type)
                    
                    # Determine if scaling is needed
                    scale_decision = await self._evaluate_scaling_need(agent_type, metrics)
                    
                    if scale_decision["action"] == "scale_up":
                        agents = await self.scale_up(
                            agent_type=agent_type,
                            count=scale_decision["count"],
                            reason="Auto scale up"
                        )
                        results["scale_up_actions"].append({
                            "agent_type": agent_type.value,
                            "count": len(agents),
                            "reason": scale_decision["reason"]
                        })
                    
                    elif scale_decision["action"] == "scale_down":
                        agents = await self.scale_down(
                            agent_type=agent_type,
                            count=scale_decision["count"],
                            reason="Auto scale down"
                        )
                        results["scale_down_actions"].append({
                            "agent_type": agent_type.value,
                            "count": len(agents),
                            "reason": scale_decision["reason"]
                        })
                        
                except Exception as e:
                    logger.error(
                        "Auto scaling failed for agent type",
                        agent_type=agent_type.value,
                        error=str(e)
                    )
            
            return results
            
        except Exception as e:
            raise AgentScalingError(f"Auto scaling failed: {str(e)}") from e
    
    async def get_scaling_stats(self) -> Dict[str, Any]:
        """
        Get scaling statistics.
        
        Returns:
            Dict[str, Any]: Scaling statistics
        """
        try:
            # Get current agent counts by type
            agent_counts = {}
            for agent_type in AgentType:
                count = await self._get_agent_count_by_type(agent_type)
                agent_counts[agent_type.value] = count
            
            stats = {
                "scaling_active": self.scaling_active,
                "scaling_interval": self.scaling_interval,
                "current_agents": agent_counts,
                "limits": {
                    "max": {t.value: c for t, c in self.max_agents_per_type.items()},
                    "min": {t.value: c for t, c in self.min_agents_per_type.items()}
                },
                "thresholds": {
                    "scale_up": self.scale_up_threshold,
                    "scale_down": self.scale_down_threshold
                },
                "cooldowns": {
                    "scale_up": self.scale_up_cooldown,
                    "scale_down": self.scale_down_cooldown
                },
                "metrics": self.scaling_metrics,
                "last_scale_actions": {
                    key: value.isoformat() for key, value in self.last_scale_actions.items()
                }
            }
            
            return stats
            
        except Exception as e:
            raise AgentScalingError(f"Failed to get scaling stats: {str(e)}") from e
    
    async def _scaling_loop(self) -> None:
        """Main scaling loop."""
        while self.scaling_active:
            try:
                # Perform auto scaling
                await self.auto_scale()
                
                # Sleep before next iteration
                await asyncio.sleep(self.scaling_interval)
                
            except Exception as e:
                logger.error(
                    "Scaling loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _get_agent_count_by_type(self, agent_type: AgentType) -> int:
        """Get current count of agents by type."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(func.count(Agent.id)).where(
                        Agent.agent_type == agent_type,
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                return result.scalar() or 0
                
        except Exception as e:
            logger.error(
                "Failed to get agent count",
                agent_type=agent_type.value,
                error=str(e)
            )
            return 0
    
    async def _get_type_metrics(self, agent_type: AgentType) -> Dict[str, Any]:
        """Get metrics for a specific agent type."""
        try:
            async with get_db_session() as session:
                # Get agent count and capacity
                result = await session.execute(
                    select(
                        func.count(Agent.id),
                        func.sum(Agent.max_concurrent_tasks),
                        func.sum(Agent.current_tasks)
                    ).where(
                        Agent.agent_type == agent_type,
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                agent_count, total_capacity, current_load = result.first()
                
                agent_count = agent_count or 0
                total_capacity = total_capacity or 0
                current_load = current_load or 0
                
                # Get task queue size
                result = await session.execute(
                    select(func.count(AgentTask.id)).where(
                        AgentTask.status == TaskStatus.PENDING,
                        AgentTask.deleted_at.is_(None)
                    )
                )
                queue_size = result.scalar() or 0
                
                # Calculate utilization
                utilization = (current_load / total_capacity) if total_capacity > 0 else 0.0
                
                return {
                    "agent_count": agent_count,
                    "total_capacity": total_capacity,
                    "current_load": current_load,
                    "queue_size": queue_size,
                    "utilization": utilization
                }
                
        except Exception as e:
            logger.error(
                "Failed to get type metrics",
                agent_type=agent_type.value,
                error=str(e)
            )
            return {}
    
    async def _evaluate_scaling_need(self, agent_type: AgentType, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if scaling is needed for an agent type."""
        utilization = metrics.get("utilization", 0.0)
        queue_size = metrics.get("queue_size", 0)
        agent_count = metrics.get("agent_count", 0)
        
        # Scale up conditions
        if utilization >= self.scale_up_threshold or queue_size > 5:
            # Calculate how many agents to add
            if utilization >= 0.95:  # Near capacity
                count = min(2, self.max_agents_per_type[agent_type] - agent_count)
            else:
                count = 1
            
            return {
                "action": "scale_up",
                "count": count,
                "reason": f"High utilization ({utilization:.1%}) or queue size ({queue_size})"
            }
        
        # Scale down conditions
        elif utilization <= self.scale_down_threshold and queue_size == 0:
            # Only scale down if we have more than minimum
            min_count = self.min_agents_per_type[agent_type]
            if agent_count > min_count:
                count = min(1, agent_count - min_count)
                
                return {
                    "action": "scale_down",
                    "count": count,
                    "reason": f"Low utilization ({utilization:.1%}) and no queue"
                }
        
        # No scaling needed
        return {
            "action": "none",
            "count": 0,
            "reason": f"Utilization ({utilization:.1%}) within thresholds"
        }
    
    async def _get_agents_for_removal(self, agent_type: AgentType, count: int) -> List[Agent]:
        """Get agents suitable for removal."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.agent_type == agent_type,
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    ).order_by(
                        Agent.current_tasks.asc(),
                        Agent.total_tasks_completed.asc(),
                        Agent.last_activity.asc()
                    ).limit(count)
                )
                return result.scalars().all()
                
        except Exception as e:
            logger.error(
                "Failed to get agents for removal",
                agent_type=agent_type.value,
                error=str(e)
            )
            return []
    
    def _get_default_config_for_type(self, agent_type: AgentType) -> Dict[str, Any]:
        """Get default configuration for an agent type."""
        base_config = {
            "max_concurrent_tasks": 5,
            "timeout": 300,
            "retry_attempts": 3,
            "memory_limit": 512,
            "cpu_limit": 0.5
        }
        
        if agent_type == AgentType.WORKER:
            base_config.update({
                "processing_rate": 10,
                "batch_size": 100
            })
        elif agent_type == AgentType.ANALYZER:
            base_config.update({
                "analysis_models": ["sentiment", "topics"],
                "analysis_timeout": 60
            })
        elif agent_type == AgentType.COORDINATOR:
            base_config.update({
                "coordination_strategy": "load_balanced",
                "max_coordinated_agents": 20
            })
        elif agent_type == AgentType.MONITOR:
            base_config.update({
                "monitoring_interval": 30,
                "alert_thresholds": {
                    "cpu": 80,
                    "memory": 85
                }
            })
        
        return base_config
    
    def _get_default_capabilities_for_type(self, agent_type: AgentType) -> List[str]:
        """Get default capabilities for an agent type."""
        if agent_type == AgentType.WORKER:
            return ["task_execution", "data_processing", "batch_processing"]
        elif agent_type == AgentType.ANALYZER:
            return ["analysis", "sentiment_analysis", "topic_modeling", "entity_extraction"]
        elif agent_type == AgentType.COORDINATOR:
            return ["coordination", "task_distribution", "load_balancing"]
        elif agent_type == AgentType.MONITOR:
            return ["monitoring", "health_check", "metrics_collection", "alerting"]
        
        return []
