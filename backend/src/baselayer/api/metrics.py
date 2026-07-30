"""
BaseLayer Metrics Endpoints

Provides Prometheus-compatible metrics for Netdata integration.
"""

import time
from typing import Dict, Any

from fastapi import APIRouter, Request
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from baselayer.core.logging import get_logger

logger = get_logger(__name__)
metrics_router = APIRouter()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "baselayer_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "baselayer_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0]
)

ACTIVE_CONNECTIONS = Gauge(
    "baselayer_active_connections",
    "Number of active connections"
)

DATABASE_CONNECTIONS = Gauge(
    "baselayer_database_connections",
    "Number of active database connections"
)

REDIS_CONNECTIONS = Gauge(
    "baselayer_redis_connections",
    "Number of active Redis connections"
)

OLLAMA_REQUESTS = Counter(
    "baselayer_ollama_requests_total",
    "Total number of Ollama requests",
    ["model", "status"]
)

OLLAMA_REQUEST_DURATION = Histogram(
    "baselayer_ollama_request_duration_seconds",
    "Ollama request duration in seconds",
    ["model"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

GOVERNANCE_AUDITS = Counter(
    "baselayer_governance_audits_total",
    "Total number of governance audits",
    ["action", "status"]
)

WORKFLOW_EXECUTIONS = Counter(
    "baselayer_workflow_executions_total",
    "Total number of workflow executions",
    ["workflow_type", "status"]
)

WORKFLOW_DURATION = Histogram(
    "baselayer_workflow_duration_seconds",
    "Workflow execution duration in seconds",
    ["workflow_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0]
)

AGENT_TASKS = Counter(
    "baselayer_agent_tasks_total",
    "Total number of agent tasks",
    ["agent_type", "task_type", "status"]
)

SYSTEM_MEMORY_USAGE = Gauge(
    "baselayer_system_memory_usage_bytes",
    "System memory usage in bytes"
)

SYSTEM_CPU_USAGE = Gauge(
    "baselayer_system_cpu_usage_percent",
    "System CPU usage percentage"
)

SYSTEM_DISK_USAGE = Gauge(
    "baselayer_system_disk_usage_bytes",
    "System disk usage in bytes"
)


@metrics_router.get("/")
async def metrics_index() -> Dict[str, Any]:
    """
    Metrics endpoint index.
    
    Returns information about available metrics.
    
    Returns:
        Dict[str, Any]: Metrics information
    """
    return {
        "service": "BaseLayer Metrics",
        "version": "0.1.0",
        "format": "Prometheus",
        "endpoints": {
            "prometheus": "/metrics/prometheus",
            "health": "/health",
        },
        "metrics": {
            "requests": "HTTP request metrics",
            "database": "Database connection metrics",
            "redis": "Redis connection metrics",
            "ollama": "Ollama AI service metrics",
            "governance": "Governance and audit metrics",
            "workflows": "Workflow execution metrics",
            "agents": "Multi-agent orchestration metrics",
            "system": "System resource metrics",
        },
    }


@metrics_router.get("/prometheus")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for Netdata integration.
    
    Returns:
        Response: Prometheus-formatted metrics
    """
    # Update system metrics
    try:
        import psutil
        
        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.used)
        
        # CPU usage
        SYSTEM_CPU_USAGE.set(psutil.cpu_percent())
        
        # Disk usage
        disk = psutil.disk_usage("/")
        SYSTEM_DISK_USAGE.set(disk.used)
        
    except Exception as e:
        logger.error("failed_to_update_system_metrics", error=str(e))
    
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@metrics_router.get("/health")
async def metrics_health() -> Dict[str, Any]:
    """
    Metrics service health check.
    
    Returns:
        Dict[str, Any]: Metrics service health
    """
    return {
        "status": "healthy",
        "service": "BaseLayer Metrics",
        "timestamp": time.time(),
    }


# Middleware for automatic metrics collection
class MetricsMiddleware:
    """
    Middleware to automatically collect request metrics.
    
    This should be added to the FastAPI middleware stack to automatically
    track request counts and durations.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            
            # Track active connections
            ACTIVE_CONNECTIONS.inc()
            
            try:
                await self.app(scope, receive, send)
            finally:
                # Record metrics
                request_time = time.time() - start_time
                
                method = scope["method"]
                # Extract endpoint from path
                path = scope["path"]
                status_code = "200"  # This would need to be extracted from response
                
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=path,
                    status_code=status_code
                ).inc()
                
                REQUEST_DURATION.labels(
                    method=method,
                    endpoint=path
                ).observe(request_time)
                
                # Decrement active connections
                ACTIVE_CONNECTIONS.dec()
        else:
            await self.app(scope, receive, send)


def increment_ollama_request(model: str, status: str, duration: float) -> None:
    """
    Increment Ollama request metrics.
    
    Args:
        model: Ollama model name
        status: Request status (success/error)
        duration: Request duration in seconds
    """
    OLLAMA_REQUESTS.labels(model=model, status=status).inc()
    OLLAMA_REQUEST_DURATION.labels(model=model).observe(duration)


def increment_governance_audit(action: str, status: str) -> None:
    """
    Increment governance audit metrics.
    
    Args:
        action: Governance action
        status: Audit status
    """
    GOVERNANCE_AUDITS.labels(action=action, status=status).inc()


def increment_workflow_execution(workflow_type: str, status: str, duration: float) -> None:
    """
    Increment workflow execution metrics.
    
    Args:
        workflow_type: Type of workflow
        status: Execution status
        duration: Execution duration in seconds
    """
    WORKFLOW_EXECUTIONS.labels(workflow_type=workflow_type, status=status).inc()
    WORKFLOW_DURATION.labels(workflow_type=workflow_type).observe(duration)


def increment_agent_task(agent_type: str, task_type: str, status: str) -> None:
    """
    Increment agent task metrics.
    
    Args:
        agent_type: Type of agent
        task_type: Type of task
        status: Task status
    """
    AGENT_TASKS.labels(agent_type=agent_type, task_type=task_type, status=status).inc()


def update_database_connections(count: int) -> None:
    """
    Update database connection gauge.
    
    Args:
        count: Number of active connections
    """
    DATABASE_CONNECTIONS.set(count)


def update_redis_connections(count: int) -> None:
    """
    Update Redis connection gauge.
    
    Args:
        count: Number of active connections
    """
    REDIS_CONNECTIONS.set(count)
