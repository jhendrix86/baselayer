"""
BaseLayer Workflow Monitor

Real-time monitoring and metrics collection for workflow executions.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.core_loop import (
    Workflow, WorkflowExecution, WorkflowStatus, WorkflowPriority
)
from .engine import WorkflowEngine

logger = get_logger(__name__)


class WorkflowMonitor:
    """
    Workflow execution monitor with real-time metrics.
    
    Tracks workflow performance, health, and resource usage
    with optimized performance for i5-2400 hardware.
    """
    
    def __init__(self, workflow_engine: WorkflowEngine):
        self.workflow_engine = workflow_engine
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.metrics_interval = 30  # Collect metrics every 30 seconds
        self.metrics_history: List[Dict[str, Any]] = []
        self.max_history_size = 100  # Keep last 100 metric samples
        
        # Performance metrics
        self.execution_counts: Dict[str, int] = {}
        self.execution_times: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        self.active_executions: Dict[str, Dict[str, Any]] = {}
    
    async def start(self) -> None:
        """Start the workflow monitor."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Workflow monitor started")
    
    async def stop(self) -> None:
        """Stop the workflow monitor."""
        self.monitoring_active = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Workflow monitor stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.metrics_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Monitoring loop error",
                    error=str(e)
                )
                await asyncio.sleep(self.metrics_interval)
    
    async def _collect_metrics(self) -> None:
        """Collect workflow execution metrics."""
        current_time = datetime.utcnow()
        
        try:
            # Collect database metrics
            db_metrics = await self._collect_database_metrics()
            
            # Collect engine metrics
            engine_metrics = await self._collect_engine_metrics()
            
            # Combine metrics
            metrics = {
                "timestamp": current_time.isoformat(),
                "database": db_metrics,
                "engine": engine_metrics,
                "system": await self._collect_system_metrics()
            }
            
            # Store in history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            # Log summary metrics
            logger.info(
                "Workflow metrics collected",
                total_executions=db_metrics.get("total_executions", 0),
                active_executions=engine_metrics.get("active_executions", 0),
                success_rate=db_metrics.get("success_rate", 0)
            )
            
        except Exception as e:
            logger.error(
                "Error collecting metrics",
                error=str(e)
            )
    
    async def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect metrics from the database."""
        async with get_db_session() as session:
            # Total executions
            total_result = await session.execute(
                select(func.count(WorkflowExecution.id)).where(
                    WorkflowExecution.deleted_at.is_(None)
                )
            )
            total_executions = total_result.scalar() or 0
            
            # Executions by status
            status_result = await session.execute(
                select(
                    WorkflowExecution.status,
                    func.count(WorkflowExecution.id)
                ).where(
                    WorkflowExecution.deleted_at.is_(None)
                ).group_by(WorkflowExecution.status)
            )
            executions_by_status = dict(status_result.all())
            
            # Executions in last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_result = await session.execute(
                select(func.count(WorkflowExecution.id)).where(
                    WorkflowExecution.created_at >= hour_ago,
                    WorkflowExecution.deleted_at.is_(None)
                )
            )
            recent_executions = recent_result.scalar() or 0
            
            # Success rate (last 24 hours)
            day_ago = datetime.utcnow() - timedelta(days=1)
            success_result = await session.execute(
                select(
                    WorkflowExecution.status,
                    func.count(WorkflowExecution.id)
                ).where(
                    WorkflowExecution.created_at >= day_ago,
                    WorkflowExecution.deleted_at.is_(None)
                ).group_by(WorkflowExecution.status)
            )
            daily_status_counts = dict(success_result.all())
            
            total_daily = sum(daily_status_counts.values())
            successful_daily = daily_status_counts.get(WorkflowStatus.COMPLETED.value, 0)
            success_rate = (successful_daily / total_daily) if total_daily > 0 else 0
            
            # Average execution time (last 24 hours)
            avg_time_result = await session.execute(
                select(func.avg(WorkflowExecution.duration_seconds)).where(
                    WorkflowExecution.created_at >= day_ago,
                    WorkflowExecution.duration_seconds.is_not(None),
                    WorkflowExecution.deleted_at.is_(None)
                )
            )
            avg_execution_time = avg_time_result.scalar() or 0
            
            return {
                "total_executions": total_executions,
                "executions_by_status": executions_by_status,
                "recent_executions": recent_executions,
                "success_rate": success_rate,
                "avg_execution_time_seconds": avg_execution_time,
            }
    
    async def _collect_engine_metrics(self) -> Dict[str, Any]:
        """Collect metrics from the workflow engine."""
        active_executions = await self.workflow_engine.get_active_executions()
        
        return {
            "active_executions": len(active_executions),
            "max_concurrent_executions": self.workflow_engine.max_concurrent_executions,
            "queue_size": self.workflow_engine.execution_queue.qsize(),
            "execution_semaphore_value": self.workflow_engine.execution_semaphore._value,
        }
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level metrics."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_free_gb": disk.free / (1024 * 1024 * 1024),
            }
            
        except ImportError:
            # psutil not available, return placeholder metrics
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0,
                "memory_available_mb": 0,
                "disk_free_gb": 0,
            }
    
    async def get_workflow_metrics(
        self,
        workflow_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get metrics for specific workflow or all workflows.
        
        Args:
            workflow_id: Specific workflow ID (optional)
            hours: Number of hours to look back
            
        Returns:
            Dict[str, Any]: Workflow metrics
        """
        async with get_db_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            # Build query
            query = select(
                WorkflowExecution.status,
                func.count(WorkflowExecution.id),
                func.avg(WorkflowExecution.duration_seconds)
            ).where(
                WorkflowExecution.created_at >= since,
                WorkflowExecution.deleted_at.is_(None)
            )
            
            if workflow_id:
                query = query.where(WorkflowExecution.workflow_id == uuid.UUID(workflow_id))
            
            query = query.group_by(WorkflowExecution.status)
            
            result = await session.execute(query)
            status_metrics = result.all()
            
            # Process results
            total_executions = sum(row[1] for row in status_metrics)
            avg_times = {row[0]: row[2] for row in status_metrics if row[2] is not None}
            
            metrics = {
                "total_executions": total_executions,
                "executions_by_status": {row[0]: row[1] for row in status_metrics},
                "avg_execution_times": avg_times,
                "period_hours": hours,
            }
            
            # Calculate success rate
            completed = metrics["executions_by_status"].get(WorkflowStatus.COMPLETED.value, 0)
            metrics["success_rate"] = (completed / total_executions) if total_executions > 0 else 0
            
            return metrics
    
    async def get_execution_timeline(
        self,
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed timeline for a specific execution.
        
        Args:
            execution_id: ID of the execution
            
        Returns:
            Dict[str, Any]: Execution timeline
        """
        async with get_db_session() as session:
            # Get execution
            result = await session.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id,
                    WorkflowExecution.deleted_at.is_(None)
                )
            )
            execution = result.scalar_one_or_none()
            
            if not execution:
                return {}
            
            # Get step executions
            steps_result = await session.execute(
                select(WorkflowStepExecution).where(
                    WorkflowStepExecution.execution_id == execution.id,
                    WorkflowStepExecution.deleted_at.is_(None)
                ).order_by(WorkflowStepExecution.started_at)
            )
            step_executions = steps_result.scalars().all()
            
            # Build timeline
            timeline = {
                "execution_id": execution_id,
                "workflow_id": str(execution.workflow_id),
                "status": execution.status.value,
                "created_at": execution.created_at.isoformat(),
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration_seconds": execution.duration,
                "progress_percent": execution.progress_percent,
                "current_step": execution.current_step,
                "input_data": execution.input_data,
                "output_data": execution.output_data,
                "error_message": execution.error_message,
                "steps": []
            }
            
            for step in step_executions:
                step_data = {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": step.duration,
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "error_message": step.error_message,
                    "retry_count": step.retry_count,
                }
                timeline["steps"].append(step_data)
            
            return timeline
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.
        
        Returns:
            Dict[str, Any]: Performance summary
        """
        if not self.metrics_history:
            return {}
        
        # Get latest metrics
        latest_metrics = self.metrics_history[-1]
        
        # Calculate trends (compare with previous metrics)
        if len(self.metrics_history) >= 2:
            previous_metrics = self.metrics_history[-2]
            
            # Calculate trends
            db_trend = self._calculate_trend(
                previous_metrics["database"]["total_executions"],
                latest_metrics["database"]["total_executions"]
            )
            
            success_trend = self._calculate_trend(
                previous_metrics["database"]["success_rate"],
                latest_metrics["database"]["success_rate"]
            )
        else:
            db_trend = 0
            success_trend = 0
        
        return {
            "current": latest_metrics,
            "trends": {
                "executions_trend": db_trend,
                "success_rate_trend": success_trend,
            },
            "health": {
                "status": "healthy" if latest_metrics["database"]["success_rate"] > 0.8 else "degraded",
                "issues": self._identify_health_issues(latest_metrics),
            },
            "period": {
                "metrics_count": len(self.metrics_history),
                "collection_interval": self.metrics_interval,
            }
        }
    
    def _calculate_trend(self, previous: float, current: float) -> str:
        """Calculate trend between two values."""
        if previous == 0:
            return "stable"
        
        change = (current - previous) / previous
        
        if change > 0.1:
            return "increasing"
        elif change < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _identify_health_issues(self, metrics: Dict[str, Any]) -> List[str]:
        """Identify potential health issues from metrics."""
        issues = []
        
        # Check success rate
        if metrics["database"]["success_rate"] < 0.8:
            issues.append("Low success rate")
        
        # Check active executions
        if metrics["engine"]["active_executions"] >= metrics["engine"]["max_concurrent_executions"]:
            issues.append("Maximum concurrent executions reached")
        
        # Check queue size
        if metrics["engine"]["queue_size"] > 10:
            issues.append("High queue backlog")
        
        # Check system resources
        if metrics["system"]["cpu_percent"] > 90:
            issues.append("High CPU usage")
        
        if metrics["system"]["memory_percent"] > 90:
            issues.append("High memory usage")
        
        if metrics["system"]["disk_percent"] > 90:
            issues.append("Low disk space")
        
        return issues
    
    async def get_workflow_health(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get health status for a specific workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Dict[str, Any]: Workflow health information
        """
        metrics = await self.get_workflow_metrics(workflow_id, hours=24)
        
        # Determine health status
        if metrics["total_executions"] == 0:
            status = "unknown"
        elif metrics["success_rate"] >= 0.9:
            status = "healthy"
        elif metrics["success_rate"] >= 0.7:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "workflow_id": workflow_id,
            "status": status,
            "success_rate": metrics["success_rate"],
            "total_executions": metrics["total_executions"],
            "avg_execution_time": metrics["avg_execution_times"].get("completed", 0),
            "recent_executions": metrics["executions_by_status"],
            "issues": self._identify_workflow_issues(metrics),
        }
    
    def _identify_workflow_issues(self, metrics: Dict[str, Any]) -> List[str]:
        """Identify issues specific to a workflow."""
        issues = []
        
        if metrics["success_rate"] < 0.7:
            issues.append("Low success rate")
        
        if metrics["total_executions"] == 0:
            issues.append("No recent executions")
        
        avg_time = metrics["avg_execution_times"].get("completed")
        if avg_time and avg_time > 300:  # 5 minutes
            issues.append("Slow execution time")
        
        return issues
    
    def get_metrics_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get historical metrics data.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List[Dict[str, Any]]: Historical metrics
        """
        return self.metrics_history[-limit:] if self.metrics_history else []
    
    def get_monitor_status(self) -> Dict[str, Any]:
        """
        Get the current status of the monitor.
        
        Returns:
            Dict[str, Any]: Monitor status information
        """
        return {
            "active": self.monitoring_active,
            "metrics_interval": self.metrics_interval,
            "history_size": len(self.metrics_history),
            "max_history_size": self.max_history_size,
            "last_collection": self.metrics_history[-1]["timestamp"] if self.metrics_history else None,
        }
