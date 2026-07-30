"""
MINT Product Models

SQLAlchemy models for digital products, assets, and analytics.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    JSON, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ProductType(str, Enum):
    """Product types for digital products."""
    PDF_GUIDE = "pdf_guide"
    TEMPLATE_PACK = "template_pack"
    CHECKLIST = "checklist"
    CHEAT_SHEET = "cheat_sheet"
    PROMPT_LIBRARY = "prompt_library"
    CODE_SNIPPETS = "code_snippets"
    NOTION_TEMPLATE = "notion_template"


class ProductStatus(str, Enum):
    """Product lifecycle status."""
    DRAFT = "draft"
    GENERATING = "generating"
    REVIEW = "review"
    LISTED = "listed"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Product(Base):
    """
    Digital product model for MINT engine.
    
    Represents AI-generated digital products sold via Gumroad.
    """
    __tablename__ = "mint_products"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    title = Column(String(200), nullable=False)
    subtitle = Column(String(300))
    description = Column(Text, nullable=False)
    product_type = Column(String(50), nullable=False, default=ProductType.PDF_GUIDE)
    status = Column(String(20), nullable=False, default=ProductStatus.DRAFT)
    
    # Pricing
    price_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    
    # SEO and identification
    slug = Column(String(200), nullable=False, unique=True)
    tags = Column(JSON, default=list)
    
    # Gumroad integration
    gumroad_product_id = Column(String(100), unique=True)
    gumroad_url = Column(String(500))
    
    # File management
    file_paths = Column(JSON, default=list)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    # Analytics
    download_count = Column(Integer, default=0)
    revenue_cents = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    listed_at = Column(DateTime(timezone=True))
    
    # Version control
    version = Column(String(20), default="1.0.0")
    
    # Relationships
    assets = relationship("ProductAsset", back_populates="product", cascade="all, delete-orphan")
    analytics = relationship("ProductAnalytics", back_populates="product", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_product_status', 'status'),
        Index('idx_product_type', 'product_type'),
        Index('idx_product_created_at', 'created_at'),
        Index('idx_product_gumroad_id', 'gumroad_product_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title={self.title}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "product_type": self.product_type,
            "status": self.status,
            "price_cents": self.price_cents,
            "currency": self.currency,
            "slug": self.slug,
            "tags": self.tags,
            "gumroad_product_id": self.gumroad_product_id,
            "gumroad_url": self.gumroad_url,
            "file_paths": self.file_paths,
            "metadata": self.metadata,
            "download_count": self.download_count,
            "revenue_cents": self.revenue_cents,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "listed_at": self.listed_at.isoformat() if self.listed_at else None,
            "version": self.version
        }
    
    @property
    def is_listed(self) -> bool:
        """Check if product is listed on Gumroad."""
        return self.status == ProductStatus.LISTED
    
    @property
    def is_active(self) -> bool:
        """Check if product is active (not paused or archived)."""
        return self.status not in [ProductStatus.PAUSED, ProductStatus.ARCHIVED]
    
    @property
    def price_dollars(self) -> float:
        """Get price in dollars."""
        return self.price_cents / 100.0
    
    def generate_slug(self) -> str:
        """Generate URL-friendly slug from title."""
        import re
        # Convert to lowercase and replace spaces with hyphens
        slug = re.sub(r'[^a-z0-9\s-]', '', self.title.lower())
        slug = re.sub(r'\s+', '-', slug)
        slug = slug.strip('-')
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        return slug
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the product."""
        if not self.tags:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the product."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def increment_downloads(self) -> None:
        """Increment download count."""
        self.download_count += 1
    
    def add_revenue(self, cents: int) -> None:
        """Add revenue in cents."""
        self.revenue_cents += cents
