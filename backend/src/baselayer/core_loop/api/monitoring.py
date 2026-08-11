"""
BaseLayer Core Loop API - Monitoring

REST API endpoints for workflow monitoring and real-time metrics.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import db_session_context
from ...models.core_loop import Workflow, WorkflowExecution, WorkflowStatus
from ...models.user import User
from ...core.auth import get_current_user
from ..monitor import WorkflowMonitor
from ..scheduler import WorkflowScheduler

logger = get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

# Global instances (will be injected in startup)
workflow_monitor: WorkflowMonitor = None
workflow_scheduler: WorkflowScheduler = None


def get_workflow_monitor() -> WorkflowMonitor:
    """Get workflow monitor instance."""
    global workflow_monitor
    if not workflow_monitor:
        raise HTTPException(status_code=500, detail="Workflow monitor not initialized")
    return workflow_monitor


def get_workflow_scheduler() -> WorkflowScheduler:
    """Get workflow scheduler instance."""
    global workflow_scheduler
    if not workflow_scheduler:
        raise HTTPException(status_code=500, detail="Workflow scheduler not initialized")
    return workflow_scheduler


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard_data(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for workflow monitoring.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Dashboard data
    """
    monitor = get_workflow_monitor()
    scheduler = get_workflow_scheduler()
    
    # Get performance summary
    performance = await monitor.get_performance_summary()
    
    # Get scheduled workflows
    scheduled = await scheduler.get_scheduled_workflows()
    
    # Get next executions
    next_executions = await scheduler.get_next_executions(5)
    
    # Get active executions
    active_executions = await monitor._collect_engine_metrics()
    
    dashboard_data = {
        "performance": performance,
        "scheduled_workflows": {
            "total": len(scheduled),
            "active": len([w for w in scheduled if w["status"] == "active"]),
            "next_executions": next_executions
        },
        "active_executions": active_executions,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return dashboard_data


@router.get("/metrics/realtime", response_model=Dict[str, Any])
async def get_realtime_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get real-time workflow metrics.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Real-time metrics
    """
    monitor = get_workflow_monitor()
    
    # Get latest metrics
    if not monitor.metrics_history:
        return {"message": "No metrics available yet"}
    
    latest_metrics = monitor.metrics_history[-1]
    
    return latest_metrics


@router.get("/metrics/history", response_model=List[Dict[str, Any]])
async def get_metrics_history(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get historical metrics data.
    
    Args:
        hours: Number of hours to look back
        limit: Maximum number of records
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Historical metrics
    """
    monitor = get_workflow_monitor()
    
    history = monitor.get_metrics_history(limit)
    
    # Filter by time if needed
    if hours > 0:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_history = [
            m for m in history
            if datetime.fromisoformat(m["timestamp"]) >= cutoff_time
        ]
        return filtered_history
    
    return history


@router.get("/health/system", response_model=Dict[str, Any])
async def get_system_health(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get overall system health status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: System health status
    """
    monitor = get_workflow_monitor()
    scheduler = get_workflow_scheduler()
    
    health_status = {
        "status": "healthy",
        "components": {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Check monitor health
    monitor_status = monitor.get_monitor_status()
    health_status["components"]["monitor"] = {
        "status": "healthy" if monitor_status["active"] else "unhealthy",
        "details": monitor_status
    }
    
    # Check scheduler health
    scheduler_status = scheduler.get_scheduler_status()
    health_status["components"]["scheduler"] = {
        "status": "healthy" if scheduler_status["running"] else "unhealthy",
        "details": scheduler_status
    }
    
    # Check database connectivity
    try:
        async with db_session_context() as db:
            await db.execute("SELECT 1")
            health_status["components"]["database"] = {
                "status": "healthy"
            }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Determine overall status
    component_statuses = [
        comp["status"] for comp in health_status["components"].values()
    ]
    
    if any(status == "unhealthy" for status in component_statuses):
        health_status["status"] = "unhealthy"
    elif any(status == "degraded" for status in component_statuses):
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/workflows/overview", response_model=Dict[str, Any])
async def get_workflows_overview(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get overview of all workflows and their status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Workflows overview
    """
    async with db_session_context() as db:
        # Get workflow counts by status
        result = await db.execute(
            select(
                Workflow.status,
                func.count(Workflow.id)
            ).where(
                Workflow.deleted_at.is_(None)
            ).group_by(Workflow.status)
        )
        workflow_counts = dict(result.all())
        
        # Get execution counts by status
        result = await db.execute(
            select(
                WorkflowExecution.status,
                func.count(WorkflowExecution.id)
            ).where(
                WorkflowExecution.deleted_at.is_(None),
                WorkflowExecution.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).group_by(WorkflowExecution.status)
        )
        execution_counts = dict(result.all())
        
        # Get total counts
        total_workflows = sum(workflow_counts.values())
        total_executions = sum(execution_counts.values())
        
        overview = {
            "workflows": {
                "total": total_workflows,
                "by_status": workflow_counts
            },
            "executions": {
                "total_24h": total_executions,
                "by_status": execution_counts
            },
            "success_rate_24h": (
                execution_counts.get(WorkflowStatus.COMPLETED.value, 0) / total_executions
                if total_executions > 0 else 0
            )
        }
        
        return overview


@router.get("/workflows/performance", response_model=List[Dict[str, Any]])
async def get_workflows_performance(
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get performance metrics for top workflows.
    
    Args:
        limit: Maximum number of workflows
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Workflow performance metrics
    """
    async with db_session_context() as db:
        # Get workflows with execution counts and average duration
        result = await db.execute(
            select(
                Workflow.id,
                Workflow.name,
                Workflow.status,
                func.count(WorkflowExecution.id).label("execution_count"),
                func.avg(WorkflowExecution.duration_seconds).label("avg_duration")
            ).join(
                WorkflowExecution, Workflow.id == WorkflowExecution.workflow_id
            ).where(
                Workflow.deleted_at.is_(None),
                WorkflowExecution.deleted_at.is_(None),
                WorkflowExecution.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).group_by(
                Workflow.id, Workflow.name, Workflow.status
            ).order_by(
                func.count(WorkflowExecution.id).desc()
            ).limit(limit)
        )
        
        workflows = result.all()
        
        performance_data = []
        for workflow in workflows:
            performance_data.append({
                "workflow_id": str(workflow.id),
                "workflow_name": workflow.name,
                "status": workflow.status.value,
                "execution_count": workflow.execution_count,
                "avg_duration_seconds": float(workflow.avg_duration) if workflow.avg_duration else 0
            })
        
        return performance_data


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_alerts(
    severity: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get system alerts based on monitoring data.
    
    Args:
        severity: Filter by alert severity
        limit: Maximum number of alerts
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of alerts
    """
    monitor = get_workflow_monitor()
    
    alerts = []
    
    # Get latest metrics
    if monitor.metrics_history:
        latest_metrics = monitor.metrics_history[-1]
        
        # Check for performance issues
        success_rate = latest_metrics["database"].get("success_rate", 0)
        if success_rate < 0.8:
            alerts.append({
                "id": f"low_success_rate_{datetime.utcnow().timestamp()}",
                "type": "performance",
                "severity": "warning" if success_rate >= 0.6 else "critical",
                "title": "Low Success Rate",
                "message": f"Workflow success rate is {success_rate:.1%}",
                "timestamp": latest_metrics["timestamp"],
                "metadata": {
                    "success_rate": success_rate,
                    "threshold": 0.8
                }
            })
        
        # Check for high queue size
        queue_size = latest_metrics["engine"].get("queue_size", 0)
        if queue_size > 10:
            alerts.append({
                "id": f"high_queue_size_{datetime.utcnow().timestamp()}",
                "type": "capacity",
                "severity": "warning" if queue_size <= 20 else "critical",
                "title": "High Queue Backlog",
                "message": f"Execution queue has {queue_size} items",
                "timestamp": latest_metrics["timestamp"],
                "metadata": {
                    "queue_size": queue_size,
                    "threshold": 10
                }
            })
        
        # Check for system resource issues
        system_metrics = latest_metrics.get("system", {})
        cpu_percent = system_metrics.get("cpu_percent", 0)
        memory_percent = system_metrics.get("memory_percent", 0)
        disk_percent = system_metrics.get("disk_percent", 0)
        
        if cpu_percent > 90:
            alerts.append({
                "id": f"high_cpu_{datetime.utcnow().timestamp()}",
                "type": "resource",
                "severity": "critical",
                "title": "High CPU Usage",
                "message": f"CPU usage is {cpu_percent:.1f}%",
                "timestamp": latest_metrics["timestamp"],
                "metadata": {
                    "cpu_percent": cpu_percent,
                    "threshold": 90
                }
            })
        
        if memory_percent > 90:
            alerts.append({
                "id": f"high_memory_{datetime.utcnow().timestamp()}",
                "type": "resource",
                "severity": "critical",
                "title": "High Memory Usage",
                "message": f"Memory usage is {memory_percent:.1f}%",
                "timestamp": latest_metrics["timestamp"],
                "metadata": {
                    "memory_percent": memory_percent,
                    "threshold": 90
                }
            })
        
        if disk_percent > 90:
            alerts.append({
                "id": f"low_disk_{datetime.utcnow().timestamp()}",
                "type": "resource",
                "severity": "critical",
                "title": "Low Disk Space",
                "message": f"Disk usage is {disk_percent:.1f}%",
                "timestamp": latest_metrics["timestamp"],
                "metadata": {
                    "disk_percent": disk_percent,
                    "threshold": 90
                }
            })
    
    # Filter by severity if specified
    if severity:
        alerts = [alert for alert in alerts if alert["severity"] == severity]
    
    # Sort by timestamp (most recent first) and limit
    alerts.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return alerts[:limit]


@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed scheduler status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Scheduler status
    """
    scheduler = get_workflow_scheduler()
    
    status = scheduler.get_scheduler_status()
    
    # Add additional details
    scheduled_workflows = await scheduler.get_scheduled_workflows()
    next_executions = await scheduler.get_next_executions(10)
    
    status.update({
        "scheduled_workflows": {
            "total": len(scheduled_workflows),
            "active": len([w for w in scheduled_workflows if w["status"] == "active"]),
            "details": scheduled_workflows[:5]  # Show first 5
        },
        "next_executions": next_executions
    })
    
    return status


@router.get("/performance/trends", response_model=Dict[str, Any])
async def get_performance_trends(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get performance trends over time.
    
    Args:
        hours: Number of hours to analyze
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Performance trends
    """
    monitor = get_workflow_monitor()
    
    # Get metrics history
    history = monitor.get_metrics_history(200)  # Get more data for trend analysis
    
    if not history:
        return {"message": "Insufficient data for trend analysis"}
    
    # Filter by time range
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    filtered_history = [
        m for m in history
        if datetime.fromisoformat(m["timestamp"]) >= cutoff_time
    ]
    
    if len(filtered_history) < 2:
        return {"message": "Insufficient data for trend analysis"}
    
    # Calculate trends
    trends = {
        "period_hours": hours,
        "data_points": len(filtered_history),
        "metrics": {}
    }
    
    # Success rate trend
    success_rates = [
        m["database"].get("success_rate", 0) for m in filtered_history
        if "database" in m
    ]
    
    if success_rates:
        avg_success_rate = sum(success_rates) / len(success_rates)
        recent_success_rate = success_rates[-1]
        trend = "stable"
        
        if len(success_rates) >= 2:
            change = recent_success_rate - success_rates[0]
            if abs(change) > 0.1:
                trend = "increasing" if change > 0 else "decreasing"
        
        trends["metrics"]["success_rate"] = {
            "average": avg_success_rate,
            "current": recent_success_rate,
            "trend": trend
        }
    
    # Execution count trend
    execution_counts = [
        m["database"].get("recent_executions", 0) for m in filtered_history
        if "database" in m
    ]
    
    if execution_counts:
        avg_executions = sum(execution_counts) / len(execution_counts)
        recent_executions = execution_counts[-1]
        trend = "stable"
        
        if len(execution_counts) >= 2:
            change = recent_executions - execution_counts[0]
            if abs(change) > avg_executions * 0.2:  # 20% change threshold
                trend = "increasing" if change > 0 else "decreasing"
        
        trends["metrics"]["executions"] = {
            "average": avg_executions,
            "current": recent_executions,
            "trend": trend
        }
    
    return trends
