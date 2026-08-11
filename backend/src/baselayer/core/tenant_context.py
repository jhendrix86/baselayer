"""
Tenant context management for multi-tenancy support in BaseLayer

This module provides utilities for managing tenant context throughout
the request lifecycle, including extraction from JWT and database session filtering.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# Context variable to store the current tenant ID
tenant_context: ContextVar[Optional[UUID]] = ContextVar("tenant_context", default=None)


def set_tenant_context(tenant_id: UUID) -> None:
    """
    Set the tenant context for the current request.
    
    Args:
        tenant_id: The UUID of the tenant for the current request
    """
    tenant_context.set(tenant_id)
    logger.debug("Set tenant context", tenant_id=str(tenant_id))


def get_tenant_context() -> Optional[UUID]:
    """
    Get the current tenant context.
    
    Returns:
        The UUID of the current tenant, or None if not set
    """
    return tenant_context.get()


def clear_tenant_context() -> None:
    """Clear the tenant context."""
    tenant_context.set(None)
    logger.debug("Cleared tenant context")


def apply_tenant_context(model_instance) -> None:
    """
    Apply the current tenant context to a model instance if not already set.

    Args:
        model_instance: Model instance (any BaseModel subclass with a tenant_id
            column) to apply tenant context to
    """
    tenant_id = get_tenant_context()

    if tenant_id is None:
        logger.debug("No tenant context available, skipping tenant assignment")
        return

    if hasattr(model_instance, "tenant_id") and model_instance.tenant_id is None:
        model_instance.tenant_id = tenant_id
        logger.debug("Applied tenant context to model", tenant_id=str(tenant_id))
