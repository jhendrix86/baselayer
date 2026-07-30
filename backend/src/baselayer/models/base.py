"""
BaseLayer Base Model

Common base class for all SQLAlchemy models with shared functionality
including timestamps, soft delete, and audit fields.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, VARCHAR

import uuid


# Custom UUID type for better compatibility
class UUIDType(TypeDecorator):
    """Custom UUID type for SQLAlchemy."""
    impl = VARCHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(value)


# Base class for all models
Base = declarative_base()


class BaseModel(Base):
    """
    Base model class with common fields and functionality.
    
    All models should inherit from this base class to ensure
    consistent behavior across the application.
    """
    
    __abstract__ = True
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Unique identifier for the record"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        comment="Timestamp when the record was last updated"
    )
    
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp when the record was soft deleted"
    )
    
    # Audit fields
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the user who created the record"
    )
    
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the user who last updated the record"
    )
    
    # Version for optimistic locking
    version: Mapped[int] = mapped_column(
        String(50),
        nullable=True,
        default="1.0.0",
        comment="Version of the record for optimistic locking"
    )
    
    # Metadata (JSON field for flexible additional data)
    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional metadata in JSON format"
    )
    
    def to_dict(self, exclude_fields: list[str] | None = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude_fields: List of field names to exclude from the output
            
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        exclude_fields = exclude_fields or []
        result = {}
        
        for column in self.__table__.columns:
            field_name = column.name
            if field_name in exclude_fields:
                continue
                
            value = getattr(self, field_name)
            
            # Handle UUID serialization
            if isinstance(value, uuid.UUID):
                value = str(value)
            # Handle datetime serialization
            elif isinstance(value, datetime):
                value = value.isoformat()
            # Handle metadata field
            elif field_name == "metadata_" and value:
                # Parse JSON if it's a string
                if isinstance(value, str):
                    import json
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        value = {"raw": value}
            
            result[field_name] = value
        
        return result
    
    def update_from_dict(self, data: Dict[str, Any], exclude_fields: list[str] | None = None) -> None:
        """
        Update model instance from dictionary.
        
        Args:
            data: Dictionary of field values to update
            exclude_fields: List of field names to exclude from updating
        """
        exclude_fields = exclude_fields or ["id", "created_at", "created_by"]
        
        for field_name, value in data.items():
            if field_name in exclude_fields:
                continue
                
            if hasattr(self, field_name):
                # Handle UUID parsing
                if field_name in ["created_by", "updated_by"] and isinstance(value, str):
                    try:
                        value = uuid.UUID(value)
                    except ValueError:
                        continue
                
                # Handle datetime parsing
                if field_name.endswith("_at") and isinstance(value, str):
                    try:
                        from datetime import datetime
                        # Try ISO format first
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        continue
                
                # Handle metadata field
                if field_name == "metadata_":
                    if isinstance(value, str):
                        import json
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            value = {"raw": value}
                
                setattr(self, field_name, value)
    
    def soft_delete(self, deleted_by: uuid.UUID | None = None) -> None:
        """
        Soft delete the record.
        
        Args:
            deleted_by: ID of the user performing the deletion
        """
        self.deleted_at = datetime.utcnow()
        self.updated_by = deleted_by
    
    def restore(self, restored_by: uuid.UUID | None = None) -> None:
        """
        Restore a soft-deleted record.
        
        Args:
            restored_by: ID of the user performing the restoration
        """
        self.deleted_at = None
        self.updated_by = restored_by
    
    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None
    
    def increment_version(self) -> None:
        """Increment the version number."""
        if self.version:
            try:
                parts = self.version.split('.')
                patch = int(parts[-1]) + 1
                self.version = f"{'.'.join(parts[:-1])}.{patch}"
            except (IndexError, ValueError):
                self.version = "1.0.0"
        else:
            self.version = "1.0.0"
    
    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id}, created_at={self.created_at})>"
