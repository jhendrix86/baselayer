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
