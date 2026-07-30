"""
BaseLayer Agent Monitor

Agent performance monitoring, health checks, and metrics collection
for the Multi-Agent Orchestration subsystem.
"""

import asyncio
import psutil
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.agents import (
    Agent, AgentTask, AgentMetrics,
    AgentType, AgentStatus, TaskStatus
)
from .exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentPerformanceError
)

logger = get_logger(__name__)


class AgentMonitor:
    """
    Agent monitoring and metrics collection system.
    
    Monitors agent performance, health, and resource usage
    with real-time metrics and alerting.
    """
    
    def __init__(self):
        self.monitoring_active: bool = False
        self.monitored_agents: Dict[str, Dict[str, Any]] = {}
        self.health_check_interval: int = 30  # seconds
        self.metrics_collection_interval: int = 60  # seconds
        self.performance_thresholds = {
            "cpu_usage": 80.0,  # percentage
            "memory_usage": 85.0,  # percentage
            "task_failure_rate": 20.0,  # percentage
            "response_time": 5.0,  # seconds
            "task_completion_rate": 70.0  # percentage
        }
        self.alert_cooldown: int = 300  # 5 minutes
        self.last_alerts: Dict[str, datetime] = {}
        
        # Monitoring metrics
        self.system_metrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "network_io": {"bytes_sent": 0, "bytes_recv": 0}
        }
    
    async def start(self) -> None:
        """Start the monitoring system."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._metrics_collection_loop())
        
        logger.info("Agent monitor started")
    
    async def stop(self) -> None:
        """Stop the monitoring system."""
        self.monitoring_active = False
        logger.info("Agent monitor stopped")
    
    async def start_monitoring(self, agent: Agent) -> None:
        """
        Start monitoring a specific agent.
        
        Args:
            agent: Agent to monitor
        """
        agent_id = str(agent.id)
        
        self.monitored_agents[agent_id] = {
            "agent": agent,
            "start_time": datetime.utcnow(),
            "last_health_check": None,
            "last_metrics_collection": None,
            "health_status": "unknown",
            "performance_metrics": {},
            "alert_count": 0
        }
        
        logger.info(
            "Started monitoring agent",
            agent_id=agent_id,
            name=agent.name
        )
    
    async def stop_monitoring(self, agent_id: str) -> None:
        """
        Stop monitoring a specific agent.
        
        Args:
            agent_id: Agent ID to stop monitoring
        """
        self.monitored_agents.pop(agent_id, None)
        
        logger.info(
            "Stopped monitoring agent",
            agent_id=agent_id
        )
    
    async def check_agent_health(self, agent: Agent) -> Dict[str, Any]:
        """
        Perform health check on an agent.
        
        Args:
            agent: Agent to check
            
        Returns:
            Dict[str, Any]: Health check results
        """
        agent_id = str(agent.id)
        health_check = {
            "agent_id": agent_id,
            "healthy": True,
            "issues": [],
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Check agent status
            if agent.status != AgentStatus.ACTIVE:
                health_check["healthy"] = False
                health_check["issues"].append(f"Agent not active: {agent.status.value}")
            
            # Check last activity
            if agent.last_activity:
                time_since_activity = datetime.utcnow() - agent.last_activity
                if time_since_activity > timedelta(minutes=5):
                    health_check["warnings"].append(f"No recent activity: {time_since_activity}")
                elif time_since_activity > timedelta(minutes=15):
                    health_check["healthy"] = False
                    health_check["issues"].append(f"No activity for {time_since_activity}")
            
            # Check task load
            if agent.current_tasks >= agent.max_concurrent_tasks:
                health_check["warnings"].append("Agent at maximum capacity")
            
            # Check failure rate
            failure_rate = await self._calculate_agent_failure_rate(agent_id)
            if failure_rate > self.performance_thresholds["task_failure_rate"]:
                health_check["healthy"] = False
                health_check["issues"].append(f"High failure rate: {failure_rate:.1f}%")
            
            # Check response time
            avg_response_time = await self._calculate_agent_response_time(agent_id)
            if avg_response_time > self.performance_thresholds["response_time"]:
                health_check["warnings"].append(f"High response time: {avg_response_time:.1f}s")
            
            # Update monitoring data
            if agent_id in self.monitored_agents:
                self.monitored_agents[agent_id]["last_health_check"] = datetime.utcnow()
                self.monitored_agents[agent_id]["health_status"] = "healthy" if health_check["healthy"] else "unhealthy"
            
            return health_check
            
        except Exception as e:
            health_check["healthy"] = False
            health_check["issues"].append(f"Health check failed: {str(e)}")
            
            logger.error(
                "Agent health check failed",
                agent_id=agent_id,
                error=str(e)
            )
            
            return health_check
    
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Dict[str, Any]: Agent metrics
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
                task_metrics = await self._get_agent_task_metrics(agent_id)
                
                # Get performance metrics
                performance_metrics = await self._get_agent_performance_metrics(agent_id)
                
                # Get resource metrics
                resource_metrics = await self._get_agent_resource_metrics(agent_id)
                
                metrics = {
                    "agent_id": agent_id,
                    "name": agent.name,
                    "type": agent.agent_type.value,
                    "status": agent.status.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "tasks": task_metrics,
                    "performance": performance_metrics,
                    "resources": resource_metrics,
                    "uptime": self._calculate_uptime(agent)
                }
                
                # Update monitoring data
                if agent_id in self.monitored_agents:
                    self.monitored_agents[agent_id]["last_metrics_collection"] = datetime.utcnow()
                    self.monitored_agents[agent_id]["performance_metrics"] = metrics
                
                return metrics
                
        except Exception as e:
            raise AgentPerformanceError(f"Failed to get agent metrics: {str(e)}") from e
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-wide metrics.
        
        Returns:
            Dict[str, Any]: System metrics
        """
        try:
            # Update system metrics
            await self._update_system_metrics()
            
            # Get agent statistics
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        Agent.status,
                        func.count(Agent.id)
                    ).where(
                        Agent.deleted_at.is_(None)
                    ).group_by(Agent.status)
                )
                agent_counts = dict(result.all())
                
                result = await session.execute(
                    select(
                        Agent.agent_type,
                        func.count(Agent.id)
                    ).where(
                        Agent.deleted_at.is_(None)
                    ).group_by(Agent.agent_type)
                )
                type_counts = dict(result.all())
                
                # Get task statistics
                result = await session.execute(
                    select(
                        AgentTask.status,
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.deleted_at.is_(None)
                    ).group_by(AgentTask.status)
                )
                task_counts = dict(result.all())
            
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "agents": {
                    "total": sum(agent_counts.values()),
                    "by_status": agent_counts,
                    "by_type": type_counts,
                    "monitored": len(self.monitored_agents)
                },
                "tasks": {
                    "total": sum(task_counts.values()),
                    "by_status": task_counts
                },
                "system": self.system_metrics,
                "monitoring": {
                    "active": self.monitoring_active,
                    "health_check_interval": self.health_check_interval,
                    "metrics_collection_interval": self.metrics_collection_interval
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(
                "Failed to get system metrics",
                error=str(e)
            )
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Get monitoring system statistics.
        
        Returns:
            Dict[str, Any]: Monitoring statistics
        """
        stats = {
            "monitoring_active": self.monitoring_active,
            "monitored_agents": len(self.monitored_agents),
            "health_check_interval": self.health_check_interval,
            "metrics_collection_interval": self.metrics_collection_interval,
            "performance_thresholds": self.performance_thresholds,
            "alert_cooldown": self.alert_cooldown,
            "system_metrics": self.system_metrics
        }
        
        # Agent health distribution
        health_distribution = {}
        for agent_id, data in self.monitored_agents.items():
            health = data.get("health_status", "unknown")
            health_distribution[health] = health_distribution.get(health, 0) + 1
        
        stats["agent_health_distribution"] = health_distribution
        
        return stats
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for health checks."""
        while self.monitoring_active:
            try:
                # Perform health checks on all monitored agents
                for agent_id, data in list(self.monitored_agents.items()):
                    try:
                        agent = data["agent"]
                        health = await self.check_agent_health(agent)
                        
                        # Check for alerts
                        if not health["healthy"]:
                            await self._check_alert_conditions(agent_id, health)
                            
                    except Exception as e:
                        logger.error(
                            "Health check failed",
                            agent_id=agent_id,
                            error=str(e)
                        )
                
                # Sleep before next iteration
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(
                    "Monitoring loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _metrics_collection_loop(self) -> None:
        """Main metrics collection loop."""
        while self.monitoring_active:
            try:
                # Update system metrics
                await self._update_system_metrics()
                
                # Collect metrics for all monitored agents
                for agent_id in list(self.monitored_agents.keys()):
                    try:
                        await self.get_agent_metrics(agent_id)
                    except Exception as e:
                        logger.error(
                            "Metrics collection failed",
                            agent_id=agent_id,
                            error=str(e)
                        )
                
                # Sleep before next iteration
                await asyncio.sleep(self.metrics_collection_interval)
                
            except Exception as e:
                logger.error(
                    "Metrics collection loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            # CPU usage
            self.system_metrics["cpu_usage"] = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_metrics["memory_usage"] = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.system_metrics["disk_usage"] = disk.percent
            
            # Network I/O
            network = psutil.net_io_counters()
            self.system_metrics["network_io"] = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv
            }
            
        except Exception as e:
            logger.error(
                "Failed to update system metrics",
                error=str(e)
            )
    
    async def _calculate_agent_failure_rate(self, agent_id: str) -> float:
        """Calculate agent task failure rate."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        func.count(func.nullif(AgentTask.status == 'failed', True)),
                        func.count(AgentTask.id)
                    ).where(
                        AgentTask.agent_id == uuid.UUID(agent_id),
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                failed, total = result.first()
                return (failed / total * 100) if total > 0 else 0.0
                
        except Exception as e:
            logger.error(
                "Failed to calculate failure rate",
                agent_id=agent_id,
                error=str(e)
            )
            return 0.0
    
    async def _calculate_agent_response_time(self, agent_id: str) -> float:
        """Calculate average agent response time."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        func.avg(
                            func.extract('epoch', AgentTask.completed_at) - 
                            func.extract('epoch', AgentTask.started_at)
                        )
                    ).where(
                        AgentTask.agent_id == uuid.UUID(agent_id),
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
                "Failed to calculate response time",
                agent_id=agent_id,
                error=str(e)
            )
            return 0.0
    
    async def _get_agent_task_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get task-related metrics for an agent."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        func.count(AgentTask.id),
                        func.count(func.nullif(AgentTask.status == 'completed', True)),
                        func.count(func.nullif(AgentTask.status == 'failed', True)),
                        func.count(func.nullif(AgentTask.status == 'assigned', True))
                    ).where(
                        AgentTask.agent_id == uuid.UUID(agent_id),
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                total, completed, failed, assigned = result.first()
                
                return {
                    "total": total or 0,
                    "completed": completed or 0,
                    "failed": failed or 0,
                    "assigned": assigned or 0,
                    "success_rate": (completed / total * 100) if total > 0 else 0.0,
                    "failure_rate": (failed / total * 100) if total > 0 else 0.0
                }
                
        except Exception as e:
            logger.error(
                "Failed to get task metrics",
                agent_id=agent_id,
                error=str(e)
            )
            return {}
    
    async def _get_agent_performance_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get performance metrics for an agent."""
        try:
            # Calculate various performance metrics
            failure_rate = await self._calculate_agent_failure_rate(agent_id)
            response_time = await self._calculate_agent_response_time(agent_id)
            
            # Get recent task completion rate
            recent_time = datetime.utcnow() - timedelta(hours=1)
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(
                        func.count(AgentTask.id),
                        func.count(func.nullif(AgentTask.status == 'completed', True))
                    ).where(
                        AgentTask.agent_id == uuid.UUID(agent_id),
                        AgentTask.completed_at >= recent_time,
                        AgentTask.deleted_at.is_(None)
                    )
                )
                
                total_recent, completed_recent = result.first()
                recent_completion_rate = (completed_recent / total_recent * 100) if total_recent > 0 else 0.0
            
            return {
                "failure_rate": failure_rate,
                "average_response_time": response_time,
                "recent_completion_rate": recent_completion_rate,
                "performance_score": self._calculate_performance_score(failure_rate, response_time, recent_completion_rate)
            }
            
        except Exception as e:
            logger.error(
                "Failed to get performance metrics",
                agent_id=agent_id,
                error=str(e)
            )
            return {}
    
    async def _get_agent_resource_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get resource usage metrics for an agent."""
        try:
            # In a real implementation, this would get actual resource usage
            # For now, return simulated metrics
            return {
                "cpu_usage": 25.0,  # Simulated
                "memory_usage": 150.0,  # MB
                "network_io": {
                    "bytes_sent": 1024,
                    "bytes_recv": 2048
                },
                "disk_io": {
                    "bytes_read": 4096,
                    "bytes_written": 2048
                }
            }
            
        except Exception as e:
            logger.error(
                "Failed to get resource metrics",
                agent_id=agent_id,
                error=str(e)
            )
            return {}
    
    def _calculate_uptime(self, agent: Agent) -> int:
        """Calculate agent uptime in seconds."""
        if agent.activated_at:
            return int((datetime.utcnow() - agent.activated_at).total_seconds())
        return 0
    
    def _calculate_performance_score(
        self,
        failure_rate: float,
        response_time: float,
        completion_rate: float
    ) -> float:
        """Calculate overall performance score (0-100)."""
        # Weight different factors
        failure_score = max(0, 100 - failure_rate)
        response_score = max(0, 100 - (response_time * 10))  # 10 points per second
        completion_score = completion_rate
        
        # Weighted average
        score = (failure_score * 0.4) + (response_score * 0.3) + (completion_score * 0.3)
        
        return min(100, max(0, score))
    
    async def _check_alert_conditions(self, agent_id: str, health: Dict[str, Any]) -> None:
        """Check if alert conditions are met and send alerts."""
        try:
            # Check alert cooldown
            last_alert = self.last_alerts.get(agent_id)
            if last_alert and (datetime.utcnow() - last_alert) < timedelta(seconds=self.alert_cooldown):
                return
            
            # Check for critical issues
            if health["issues"]:
                await self._send_alert(agent_id, "critical", health["issues"])
            
            # Check for warnings
            elif health["warnings"]:
                await self._send_alert(agent_id, "warning", health["warnings"])
            
        except Exception as e:
            logger.error(
                "Alert check failed",
                agent_id=agent_id,
                error=str(e)
            )
    
    async def _send_alert(self, agent_id: str, severity: str, messages: List[str]) -> None:
        """Send an alert for an agent."""
        try:
            # Update alert tracking
            self.last_alerts[agent_id] = datetime.utcnow()
            
            if agent_id in self.monitored_agents:
                self.monitored_agents[agent_id]["alert_count"] += 1
            
            # Log alert
            logger.warning(
                "Agent alert",
                agent_id=agent_id,
                severity=severity,
                messages=messages
            )
            
            # In a real implementation, this would send notifications
            # via email, Slack, or other alerting systems
            
        except Exception as e:
            logger.error(
                "Failed to send alert",
                agent_id=agent_id,
                error=str(e)
            )
