"""
BaseLayer Multi-Agent Orchestration API

REST API endpoints for agent management, coordination, and monitoring.
"""

from .agents import router as agents_router
from .tasks import router as tasks_router
from .orchestration import router as orchestration_router
from .monitoring import router as monitoring_router
from .scaling import router as scaling_router

__all__ = [
    "agents_router",
    "tasks_router",
    "orchestration_router",
    "monitoring_router",
    "scaling_router",
]
