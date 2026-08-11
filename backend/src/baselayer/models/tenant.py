"""
Tenant model for multi-tenancy support in BaseLayer
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from baselayer.models.base import BaseModel, UUIDType


class Tenant(BaseModel):
    """
    Tenant model for multi-tenancy support.
    
    Each tenant represents an isolated environment with its own data,
    users, and configuration. This enables the same BaseLayer instance
    to serve multiple organizations or business units.
    """
    
    __tablename__ = "tenants"
    
    # Tenant identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Human-readable name of the tenant"
    )
    
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-friendly identifier for the tenant"
    )
    
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Description of the tenant"
    )
    
    # Tenant status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
        comment="Whether the tenant is active"
    )
    
    # Configuration
    config: Mapped[Dict[str, Any] | None] = mapped_column(
        String,
        nullable=True,
        comment="Tenant-specific configuration in JSON format"
    )
    
    # Metadata
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email for the tenant"
    )
    
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact name for the tenant"
    )
    
    def to_dict(self, exclude_fields: list[str] | None = None) -> Dict[str, Any]:
        """
        Convert tenant instance to dictionary.
        
        Args:
            exclude_fields: List of field names to exclude from the output
            
        Returns:
            Dict[str, Any]: Dictionary representation of the tenant
        """
        exclude_fields = exclude_fields or []
        result = super().to_dict(exclude_fields=exclude_fields)
        
        # Parse config if it's a string
        if result.get("config") and isinstance(result["config"], str):
            import json
            try:
                result["config"] = json.loads(result["config"])
            except json.JSONDecodeError:
                result["config"] = {"raw": result["config"]}
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the tenant."""
        return f"<Tenant(id={self.id}, name={self.name}, slug={self.slug}, is_active={self.is_active})>"
