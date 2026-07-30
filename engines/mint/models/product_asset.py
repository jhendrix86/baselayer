"""
MINT Product Asset Models

SQLAlchemy models for product files and assets.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AssetType(str, Enum):
    """Asset file types."""
    PDF = "pdf"
    MARKDOWN = "md"
    ZIP = "zip"
    PNG = "png"
    JPEG = "jpeg"
    JSON = "json"
    TXT = "txt"


class ProductAsset(Base):
    """
    Product asset model for MINT engine.
    
    Represents individual files associated with digital products.
    """
    __tablename__ = "mint_product_assets"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to product
    product_id = Column(UUID(as_uuid=True), ForeignKey('mint_products.id'), nullable=False)
    
    # File information
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False, default=AssetType.PDF)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    
    # Asset metadata
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    product = relationship("Product", back_populates="assets")
    
    # Indexes
    __table_args__ = (
        Index('idx_asset_product_id', 'product_id'),
        Index('idx_asset_file_type', 'file_type'),
        Index('idx_asset_primary', 'is_primary'),
    )
    
    def __repr__(self) -> str:
        return f"<ProductAsset(id={self.id}, file_name={self.file_name}, type={self.file_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "product_id": str(self.product_id),
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "is_primary": self.is_primary,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size_bytes / (1024 * 1024)
    
    @property
    def is_image(self) -> bool:
        """Check if asset is an image."""
        return self.file_type in [AssetType.PNG, AssetType.JPEG]
    
    @property
    def is_document(self) -> bool:
        """Check if asset is a document."""
        return self.file_type in [AssetType.PDF, AssetType.MARKDOWN, AssetType.TXT]
    
    @property
    def is_archive(self) -> bool:
        """Check if asset is an archive."""
        return self.file_type == AssetType.ZIP
    
    @property
    def file_extension(self) -> str:
        """Get file extension."""
        return f".{self.file_type}"
    
    def set_as_primary(self) -> None:
        """Mark this asset as primary."""
        self.is_primary = True
    
    def unset_as_primary(self) -> None:
        """Unmark this asset as primary."""
        self.is_primary = False
    
    def update_sort_order(self, order: int) -> None:
        """Update sort order."""
        self.sort_order = order
