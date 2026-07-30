"""
BaseLayer Output Engine API

REST API endpoints for template management, output generation, and delivery.
"""

from .templates import router as templates_router
from .outputs import router as outputs_router
from .delivery import router as delivery_router
from .analytics import router as analytics_router

__all__ = [
    "templates_router",
    "outputs_router",
    "delivery_router",
    "analytics_router",
]
