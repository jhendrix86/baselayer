"""
BaseLayer Monitoring and Metrics System

Comprehensive monitoring, metrics collection, and health checks
for the BaseLayer multi-agent system.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from .config import get_settings
from .database import get_db_session
from ..models.user import User
from ..models.core_loop import Workflow, WorkflowExecution
from ..models.governance import AuditLog

logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Prometheus Metrics
REQUEST_COUNT = Counter(
    'baselayer_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'baselayer_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_USERS = Gauge(
    'baselayer_active_users',
    'Number of active users'
)

WORKFLOW_EXECUTIONS = Counter(
    'baselayer_workflow_executions_total',
    'Total workflow executions',
    ['status', 'workflow_type']
)

SYSTEM_HEALTH = Gauge(
    'baselayer_system_health',
    'System health score (0-100)'
)

DATABASE_CONNECTIONS = Gauge(
    'baselayer_database_connections',
    'Number of active database connections'
)

CACHE_HIT_RATE = Gauge(
    'baselayer_cache_hit_rate',
    'Cache hit rate percentage'
)

ERROR_RATE = Gauge(
    'baselayer_error_rate',
    'Error rate percentage'
)

TASK_QUEUE_SIZE = Gauge(
    'baselayer_task_queue_size',
    'Size of task queue',
    ['queue_name']
)


class MonitoringSystem:
    """
    Comprehensive monitoring system for BaseLayer.
    
    Tracks system health, performance metrics, and operational insights.
    """
    
    def __init__(self):
        self.monitoring_active: bool = False
        self.metrics_interval: int = 60  # seconds
        self.health_check_interval: int = 30  # seconds
        self.alert_thresholds = {
            "error_rate": 5.0,  # 5%
            "response_time": 2.0,  # 2 seconds
            "cpu_usage": 80.0,  # 80%
            "memory_usage": 85.0,  # 85%
            "disk_usage": 90.0,  # 90%
        }
        
        # System metrics cache
        self.metrics_cache: Dict[str, Any] = {}
        self.cache_ttl: int = 300  # 5 minutes
        
        # Alert system
        self.alerts: List[Dict[str, Any]] = []
        self.alert_handlers: List[callable] = []
    
    async def start(self) -> None:
        """Start the monitoring system."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._health_check_loop())
        
        logger.info("Monitoring system started")
    
    async def stop(self) -> None:
        """Stop the monitoring system."""
        self.monitoring_active = False
        logger.info("Monitoring system stopped")
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive system metrics.
        
        Returns:
            Dict[str, Any]: System metrics
        """
        try:
            # Check cache first
            cache_key = "system_metrics"
            if cache_key in self.metrics_cache:
                cached_data = self.metrics_cache[cache_key]
                cache_age = datetime.utcnow() - cached_data["timestamp"]
                
                if cache_age.total_seconds() < self.cache_ttl:
                    return cached_data["data"]
            
            # Collect metrics
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "system": await self._get_system_metrics(),
                "database": await self._get_database_metrics(),
                "application": await self._get_application_metrics(),
                "performance": await self._get_performance_metrics(),
                "alerts": self.alerts[-10:] if self.alerts else []  # Last 10 alerts
            }
            
            # Update cache
            self.metrics_cache[cache_key] = {
                "data": metrics,
                "timestamp": datetime.utcnow()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(
                "Failed to get system metrics",
                error=str(e)
            )
            return {"error": str(e)}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get system health status.
        
        Returns:
            Dict[str, Any]: Health status
        """
        try:
            health_checks = {
                "database": await self._check_database_health(),
                "redis": await self._check_redis_health(),
                "application": await self._check_application_health(),
                "system": await self._check_system_health()
            }
            
            # Calculate overall health
            healthy_checks = sum(1 for check in health_checks.values() if check["healthy"])
            total_checks = len(health_checks)
            health_score = (healthy_checks / total_checks) * 100
            
            overall_status = "healthy"
            if health_score < 50:
                overall_status = "unhealthy"
            elif health_score < 80:
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "score": health_score,
                "checks": health_checks,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Failed to get health status",
                error=str(e)
            )
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def record_metric(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a custom metric.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
        """
        try:
            # Update Prometheus metrics
            if name == "request_count":
                REQUEST_COUNT.labels(**labels or {}).inc()
            elif name == "request_duration":
                REQUEST_DURATION.labels(**labels or {}).observe(value)
            elif name == "active_users":
                ACTIVE_USERS.set(value)
            elif name == "workflow_execution":
                WORKFLOW_EXECUTIONS.labels(**labels or {}).inc()
            elif name == "system_health":
                SYSTEM_HEALTH.set(value)
            elif name == "error_rate":
                ERROR_RATE.set(value)
            elif name == "task_queue_size":
                TASK_QUEUE_SIZE.labels(**labels or {}).set(value)
            
            logger.debug(
                "Metric recorded",
                name=name,
                value=value,
                labels=labels
            )
            
        except Exception as e:
            logger.error(
                "Failed to record metric",
                name=name,
                error=str(e)
            )
    
    async def create_alert(
        self,
        severity: str,
        title: str,
        description: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create an alert.
        
        Args:
            severity: Alert severity (critical, warning, info)
            title: Alert title
            description: Alert description
            source: Alert source
            metadata: Additional metadata
        """
        alert = {
            "id": str(int(time.time() * 1000)),  # Simple ID
            "severity": severity,
            "title": title,
            "description": description,
            "source": source,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "resolved": False
        }
        
        self.alerts.append(alert)
        
        # Keep only last 1000 alerts
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
        
        # Trigger alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(
                    "Alert handler failed",
                    error=str(e)
                )
        
        logger.warning(
            "Alert created",
            severity=severity,
            title=title,
            source=source
        )
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Update Prometheus metrics
                await self._update_prometheus_metrics()
                
                # Check alert thresholds
                await self._check_alert_thresholds()
                
                # Clean up old metrics cache
                await self._cleanup_metrics_cache()
                
                # Sleep until next iteration
                await asyncio.sleep(self.metrics_interval)
                
            except Exception as e:
                logger.error(
                    "Monitoring loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        while self.monitoring_active:
            try:
                # Get health status
                health_status = await self.get_health_status()
                
                # Update system health metric
                await self.record_metric("system_health", health_status["score"])
                
                # Create alerts for unhealthy components
                for component, check in health_status["checks"].items():
                    if not check["healthy"]:
                        await self.create_alert(
                            severity="critical" if health_status["status"] == "unhealthy" else "warning",
                            title=f"{component.title()} Health Issue",
                            description=check.get("error", f"{component} is unhealthy"),
                            source="health_check",
                            metadata={"component": component, "check": check}
                        )
                
                # Sleep until next iteration
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(
                    "Health check loop error",
                    error=str(e)
                )
                await asyncio.sleep(30)
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics."""
        try:
            import psutil
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": cpu_freq.current if cpu_freq else None
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "usage_percent:": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "uptime": time.time() - psutil.boot_time()
            }
            
        except ImportError:
            # psutil not available, return basic metrics
            return {
                "cpu": {"usage_percent": 0, "count": 0},
                "memory": {"total": 0, "available": 0, "used": 0, "usage_percent": 0},
                "disk": {"total": 0, "used": 0, "free": 0, "usage_percent": 0},
                "network": {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0},
                "uptime": 0
            }
        except Exception as e:
            logger.error(
                "Failed to get system metrics",
                error=str(e)
            )
            return {"error": str(e)}
    
    async def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database metrics."""
        try:
            async with get_db_session() as session:
                # Connection pool metrics
                pool = session.bind.pool
                connections = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow()
                }
                
                # Table row counts
                tables = {}
                
                # Users
                result = await session.execute(select(func.count(User.id)))
                tables["users"] = result.scalar()
                
                # Workflows
                result = await session.execute(select(func.count(Workflow.id)))
                tables["workflows"] = result.scalar()
                
                # Workflow Executions
                result = await session.execute(select(func.count(WorkflowExecution.id)))
                tables["workflow_executions"] = result.scalar()
                
                # Audit Logs
                result = await session.execute(select(func.count(AuditLog.id)))
                tables["audit_logs"] = result.scalar()
                
                return {
                    "connections": connections,
                    "tables": tables,
                    "pool_size": pool.size(),
                    "max_overflow": pool.max_overflow
                }
                
        except Exception as e:
            logger.error(
                "Failed to get database metrics",
                error=str(e)
            )
            return {"error": str(e)}
    
    async def _get_application_metrics(self) -> Dict[str, Any]:
        """Get application-level metrics."""
        try:
            async with get_db_session() as session:
                # User metrics
                result = await session.execute(
                    select(func.count(User.id)).where(User.is_active == True)
                )
                active_users = result.scalar()
                
                result = await session.execute(
                    select(func.count(User.id))
                )
                total_users = result.scalar()
                
                # Recent activity (last 24 hours)
                cutoff = datetime.utcnow() - timedelta(hours=24)
                result = await session.execute(
                    select(func.count(WorkflowExecution.id)).where(
                        WorkflowExecution.created_at >= cutoff
                    )
                )
                recent_executions = result.scalar()
                
                return {
                    "users": {
                        "active": active_users,
                        "total": total_users,
                        "active_percentage": (active_users / total_users * 100) if total_users > 0 else 0
                    },
                    "workflows": {
                        "recent_executions": recent_executions
                    },
                    "version": "0.1.0",
                    "environment": settings.environment
                }
                
        except Exception as e:
            logger.error(
                "Failed to get application metrics",
                error=str(e)
            )
            return {"error": str(e)}
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # In a real implementation, would collect from various sources
            return {
                "response_time": {
                    "avg": 0.5,  # seconds
                    "p95": 1.2,
                    "p99": 2.1
                },
                "throughput": {
                    "requests_per_second": 45.5,
                    "executions_per_minute": 12.3
                },
                "error_rate": 2.1,  # percentage
                "cache_hit_rate": 85.7  # percentage
            }
            
        except Exception as e:
            logger.error(
                "Failed to get performance metrics",
                error=str(e)
            )
            return {"error": str(e)}
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            start_time = time.time()
            
            async with get_db_session() as session:
                # Simple connectivity test
                await session.execute("SELECT 1")
                
                response_time = time.time() - start_time
                
                return {
                    "healthy": True,
                    "response_time": response_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            # In a real implementation, would check Redis connection
            return {
                "healthy": True,
                "response_time": 0.001,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_application_health(self) -> Dict[str, Any]:
        """Check application health."""
        try:
            # Check if application is responsive
            return {
                "healthy": True,
                "uptime": time.time(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """Check system health."""
        try:
            import psutil
            
            # Check CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_healthy = cpu_usage < self.alert_thresholds["cpu_usage"]
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_healthy = memory.percent < self.alert_thresholds["memory_usage"]
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
            disk_healthy = disk_usage < self.alert_thresholds["disk_usage"]
            
            overall_healthy = cpu_healthy and memory_healthy and disk_healthy
            
            return {
                "healthy": overall_healthy,
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "disk_usage": disk_usage,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _update_prometheus_metrics(self) -> None:
        """Update Prometheus metrics."""
        try:
            # Update database connections
            db_metrics = await self._get_database_metrics()
            if "connections" in db_metrics:
                connections = db_metrics["connections"]
                DATABASE_CONNECTIONS.set(connections["checked_out"])
            
            # Update active users
            app_metrics = await self._get_application_metrics()
            if "users" in app_metrics:
                ACTIVE_USERS.set(app_metrics["users"]["active"])
            
            # Update error rate
            perf_metrics = await self._get_performance_metrics()
            if "error_rate" in perf_metrics:
                ERROR_RATE.set(perf_metrics["error_rate"])
            
            # Update cache hit rate
            if "cache_hit_rate" in perf_metrics:
                CACHE_HIT_RATE.set(perf_metrics["cache_hit_rate"])
            
        except Exception as e:
            logger.error(
                "Failed to update Prometheus metrics",
                error=str(e)
            )
    
    async def _check_alert_thresholds(self) -> None:
        """Check alert thresholds and create alerts."""
        try:
            # Get performance metrics
            perf_metrics = await self._get_performance_metrics()
            
            # Check error rate
            if "error_rate" in perf_metrics:
                error_rate = perf_metrics["error_rate"]
                if error_rate > self.alert_thresholds["error_rate"]:
                    await self.create_alert(
                        severity="warning",
                        title="High Error Rate",
                        description=f"Error rate is {error_rate}%, threshold is {self.alert_thresholds['error_rate']}%",
                        source="monitoring",
                        metadata={"error_rate": error_rate, "threshold": self.alert_thresholds["error_rate"]}
                    )
            
            # Check response time
            if "response_time" in perf_metrics:
                response_time = perf_metrics["response_time"]["avg"]
                if response_time > self.alert_thresholds["response_time"]:
                    await self.create_alert(
                        severity="warning",
                        title="High Response Time",
                        description=f"Average response time is {response_time}s, threshold is {self.alert_thresholds['response_time']}s",
                        source="monitoring",
                        metadata={"response_time": response_time, "threshold": self.alert_thresholds["response_time"]}
                    )
            
        except Exception as e:
            logger.error(
                "Failed to check alert thresholds",
                error=str(e)
            )
    
    async def _cleanup_metrics_cache(self) -> None:
        """Clean up old metrics cache entries."""
        current_time = datetime.utcnow()
        
        for key, (timestamp, _) in list(self.metrics_cache.items()):
            if current_time - timestamp > timedelta(seconds=self.cache_ttl):
                del self.metrics_cache[key]
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest()


# Global monitoring system instance
monitoring_system = MonitoringSystem()
