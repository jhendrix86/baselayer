"""
BaseLayer Multi-Agent Orchestration Tasks

Arq task definitions for background agent processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.agents import (
    Agent, AgentTask, AgentMetrics,
    AgentType, AgentStatus, TaskStatus
)
from .orchestrator import AgentOrchestrator
from .lifecycle import AgentLifecycleManager
from .coordinator import TaskCoordinator
from .communicator import AgentCommunicator
from .monitor import AgentMonitor
from .scaler import AgentScaler

logger = get_logger(__name__)

# Global instances (will be initialized in startup)
agent_orchestrator: AgentOrchestrator = None
lifecycle_manager: AgentLifecycleManager = None
task_coordinator: TaskCoordinator = None
agent_communicator: AgentCommunicator = None
agent_monitor: AgentMonitor = None
agent_scaler: AgentScaler = None


async def initialize_agents():
    """Initialize Multi-Agent Orchestration components."""
    global agent_orchestrator, lifecycle_manager, task_coordinator
    global agent_communicator, agent_monitor, agent_scaler
    
    agent_orchestrator = AgentOrchestrator()
    lifecycle_manager = AgentLifecycleManager()
    task_coordinator = TaskCoordinator()
    agent_communicator = AgentCommunicator()
    agent_monitor = AgentMonitor()
    agent_scaler = AgentScaler()
    
    await agent_orchestrator.start_orchestration()
    
    logger.info("Multi-Agent Orchestration components initialized")


async def shutdown_agents():
    """Shutdown Multi-Agent Orchestration components."""
    global agent_orchestrator
    
    if agent_orchestrator:
        await agent_orchestrator.stop_orchestration()
    
    logger.info("Multi-Agent Orchestration components shutdown")


async def process_agent_health_checks(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process agent health checks.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check results
    """
    global agent_monitor
    
    if not agent_monitor:
        raise RuntimeError("Agent monitor not initialized")
    
    try:
        # Get all active agents
        async with db_session_context() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.deleted_at.is_(None)
                )
            )
            agents = result.scalars().all()
        
        health_results = {
            "total_agents": len(agents),
            "healthy_agents": 0,
            "unhealthy_agents": 0,
            "health_issues": []
        }
        
        for agent in agents:
            try:
                health = await agent_monitor.check_agent_health(agent)
                
                if health["healthy"]:
                    health_results["healthy_agents"] += 1
                else:
                    health_results["unhealthy_agents"] += 1
                    health_results["health_issues"].append({
                        "agent_id": str(agent.id),
                        "name": agent.name,
                        "issues": health["issues"]
                    })
                
            except Exception as e:
                health_results["unhealthy_agents"] += 1
                health_results["health_issues"].append({
                    "agent_id": str(agent.id),
                    "name": agent.name,
                    "error": str(e)
                })
        
        logger.info(
            "Agent health checks completed",
            total=health_results["total_agents"],
            healthy=health_results["healthy_agents"],
            unhealthy=health_results["unhealthy_agents"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            **health_results
        }
        
    except Exception as e:
        logger.error(
            "Agent health check task failed",
            error=str(e)
        )
        raise


async def process_agent_scaling(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process automatic agent scaling.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Scaling results
    """
    global agent_scaler
    
    if not agent_scaler:
        raise RuntimeError("Agent scaler not initialized")
    
    try:
        scaling_results = await agent_scaler.auto_scale()
        
        logger.info(
            "Agent scaling completed",
            scale_up_count=len(scaling_results["scale_up_actions"]),
            scale_down_count=len(scaling_results["scale_down_actions"])
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            **scaling_results
        }
        
    except Exception as e:
        logger.error(
            "Agent scaling task failed",
            error=str(e)
        )
        raise


async def process_task_cleanup(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old tasks.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup results
    """
    retention_days = 7
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        async with db_session_context() as session:
            # Soft delete old tasks
            result = await session.execute(
                select(AgentTask).where(
                    AgentTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]),
                    AgentTask.completed_at < cutoff_date,
                    AgentTask.deleted_at.is_(None)
                )
            )
            old_tasks = result.scalars().all()
            
            count = 0
            for task in old_tasks:
                task.soft_delete()
                session.add(task)
                count += 1
            
            await session.commit()
            
            logger.info(
                "Old tasks cleaned up",
                count=count,
                retention_days=retention_days
            )
            
            return {
                "status": "completed",
                "cleaned_tasks": count,
                "retention_days": retention_days,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(
            "Task cleanup task failed",
            error=str(e)
        )
        raise


async def process_agent_metrics_collection(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to collect agent metrics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Metrics collection results
    """
    global agent_monitor
    
    if not agent_monitor:
        raise RuntimeError("Agent monitor not initialized")
    
    try:
        # Get system metrics
        system_metrics = await agent_monitor.get_system_metrics()
        
        # Get individual agent metrics
        async with db_session_context() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.deleted_at.is_(None)
                )
            )
            agents = result.scalars().all()
        
        agent_metrics = {}
        for agent in agents:
            try:
                metrics = await agent_monitor.get_agent_metrics(str(agent.id))
                agent_metrics[str(agent.id)] = metrics
            except Exception as e:
                logger.error(
                    "Failed to collect agent metrics",
                    agent_id=str(agent.id),
                    error=str(e)
                )
        
        logger.info(
            "Agent metrics collection completed",
            total_agents=len(agents),
            system_cpu=system_metrics.get("system", {}).get("cpu_usage", 0),
            system_memory=system_metrics.get("system", {}).get("memory_usage", 0)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "system_metrics": system_metrics,
            "agent_metrics_count": len(agent_metrics)
        }
        
    except Exception as e:
        logger.error(
            "Agent metrics collection task failed",
            error=str(e)
        )
        raise


async def process_agent_lifecycle_maintenance(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to maintain agent lifecycle.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Maintenance results
    """
    global lifecycle_manager
    
    if not lifecycle_manager:
        raise RuntimeError("Lifecycle manager not initialized")
    
    try:
        # Clean up old agents
        cleanup_results = await lifecycle_manager.cleanup_old_agents(max_age_days=30)
        
        # Update agent configurations if needed
        # This would check for configuration updates in a real implementation
        
        logger.info(
            "Agent lifecycle maintenance completed",
            cleaned_agents=cleanup_results.get("cleaned_count", 0)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "cleanup_results": cleanup_results
        }
        
    except Exception as e:
        logger.error(
            "Agent lifecycle maintenance task failed",
            error=str(e)
        )
        raise


async def process_task_coordination_optimization(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to optimize task coordination.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Optimization results
    """
    global task_coordinator
    
    if not task_coordinator:
        raise RuntimeError("Task coordinator not initialized")
    
    try:
        # Get coordination statistics
        coordination_stats = await task_coordinator.get_coordination_stats()
        
        # Analyze and optimize coordination strategy
        # This would implement optimization logic in a real implementation
        
        logger.info(
            "Task coordination optimization completed",
            total_tasks=coordination_stats.get("tasks", {}).get("total", 0),
            success_rate=coordination_stats.get("performance", {}).get("success_rate", 0)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "coordination_stats": coordination_stats
        }
        
    except Exception as e:
        logger.error(
            "Task coordination optimization task failed",
            error=str(e)
        )
        raise


async def process_communication_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check communication system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Communication health results
    """
    global agent_communicator
    
    if not agent_communicator:
        raise RuntimeError("Agent communicator not initialized")
    
    try:
        # Get communication statistics
        comm_stats = await agent_communicator.get_communication_stats()
        
        # Check for communication issues
        issues = []
        
        # Check message queue sizes
        queue_sizes = comm_stats.get("message_queues", 0)
        if queue_sizes > 100:
            issues.append(f"Large message queue size: {queue_sizes}")
        
        # Check average response time
        avg_response_time = comm_stats.get("metrics", {}).get("average_response_time", 0)
        if avg_response_time > 5.0:
            issues.append(f"High average response time: {avg_response_time:.2f}s")
        
        # Check failure rate
        messages_failed = comm_stats.get("metrics", {}).get("messages_failed", 0)
        messages_sent = comm_stats.get("metrics", {}).get("messages_sent", 0)
        failure_rate = (messages_failed / messages_sent * 100) if messages_sent > 0 else 0
        
        if failure_rate > 10:
            issues.append(f"High message failure rate: {failure_rate:.1f}%")
        
        logger.info(
            "Communication health check completed",
            queue_sizes=queue_sizes,
            avg_response_time=avg_response_time,
            failure_rate=failure_rate,
            issues_count=len(issues)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "communication_stats": comm_stats,
            "health_issues": issues,
            "healthy": len(issues) == 0
        }
        
    except Exception as e:
        logger.error(
            "Communication health check task failed",
            error=str(e)
        )
        raise


async def process_orchestration_system_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check overall orchestration system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: System health results
    """
    global agent_orchestrator
    
    if not agent_orchestrator:
        raise RuntimeError("Agent orchestrator not initialized")
    
    try:
        # Get orchestration status
        orchestration_status = await agent_orchestrator.get_orchestration_status()
        
        # Evaluate system health
        health_status = {
            "healthy": True,
            "issues": [],
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check orchestration active status
        if not orchestration_status.get("orchestration_active"):
            health_status["healthy"] = False
            health_status["issues"].append("Orchestration system not active")
        
        # Check agent counts
        total_agents = orchestration_status.get("agents", {}).get("total", 0)
        if total_agents == 0:
            health_status["healthy"] = False
            health_status["issues"].append("No active agents")
        
        # Check task queue size
        queue_size = orchestration_status.get("tasks", {}).get("queue_size", 0)
        if queue_size > 50:
            health_status["warnings"].append(f"Large task queue: {queue_size}")
        
        # Check system performance
        system_metrics = orchestration_status.get("performance", {})
        cpu_usage = system_metrics.get("cpu_usage", 0)
        memory_usage = system_metrics.get("memory_usage", 0)
        
        if cpu_usage > 90:
            health_status["warnings"].append(f"High CPU usage: {cpu_usage:.1f}%")
        
        if memory_usage > 90:
            health_status["warnings"].append(f"High memory usage: {memory_usage:.1f}%")
        
        logger.info(
            "Orchestration system health check completed",
            healthy=health_status["healthy"],
            issues_count=len(health_status["issues"]),
            warnings_count=len(health_status["warnings"])
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "orchestration_status": orchestration_status,
            "health_status": health_status
        }
        
    except Exception as e:
        logger.error(
            "Orchestration system health check failed",
            error=str(e)
        )
        raise


# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 3,  # Optimized for i5-2400
    "queue_name": "agents",
    "job_timeout": 1800,  # 30 minutes timeout
}

# Cron jobs
cron_jobs = [
    cron(
        process_agent_health_checks,
        minute="*/5",  # Every 5 minutes
    ),
    cron(
        process_agent_scaling,
        minute="*/10",  # Every 10 minutes
    ),
    cron(
        process_task_cleanup,
        hour=2,  # 2 AM daily
        minute=0,
    ),
    cron(
        process_agent_metrics_collection,
        minute="*/2",  # Every 2 minutes
    ),
    cron(
        process_agent_lifecycle_maintenance,
        hour=3,  # 3 AM daily
        minute=0,
    ),
    cron(
        process_task_coordination_optimization,
        hour=4,  # 4 AM daily
        minute=0,
    ),
    cron(
        process_communication_health,
        minute="*/15",  # Every 15 minutes
    ),
    cron(
        process_orchestration_system_health,
        minute="*/30",  # Every 30 minutes
    ),
]
