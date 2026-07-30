"""
MINT Product Analytics Models

SQLAlchemy models for product analytics and sales tracking.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ProductAnalytics(Base):
    """
    Product analytics model for MINT engine.
    
    Tracks daily analytics including views, sales, revenue,
    and conversion rates for each product.
    """
    __tablename__ = "mint_product_analytics"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to product
    product_id = Column(UUID(as_uuid=True), ForeignKey('mint_products.id'), nullable=False)
    
    # Date tracking
    date = Column(DateTime(timezone=True), nullable=False)
    
    # Analytics metrics
    views = Column(Integer, default=0)
    sales = Column(Integer, default=0)
    revenue_cents = Column(Integer, default=0)
    refunds = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    
    # Source tracking
    source = Column(String(50), default="gumroad")  # gumroad, direct, affiliate, etc.
    
    # Additional metrics
    unique_visitors = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    add_to_cart = Column(Integer, default=0)
    checkout_started = Column(Integer, default=0)
    
    # Revenue breakdown
    gross_revenue_cents = Column(Integer, default=0)
    net_revenue_cents = Column(Integer, default=0)  # After refunds
    fees_cents = Column(Integer, default=0)  # Platform fees
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    product = relationship("Product", back_populates="analytics")
    
    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='uq_product_date'),
        Index('idx_analytics_product_id', 'product_id'),
        Index('idx_analytics_date', 'date'),
        Index('idx_analytics_source', 'source'),
        Index('idx_analytics_created_at', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<ProductAnalytics(id={self.id}, product_id={self.product_id}, date={self.date})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "product_id": str(self.product_id),
            "date": self.date.isoformat() if self.date else None,
            "views": self.views,
            "sales": self.sales,
            "revenue_cents": self.revenue_cents,
            "revenue_dollars": self.revenue_dollars,
            "refunds": self.refunds,
            "conversion_rate": self.conversion_rate,
            "source": self.source,
            "unique_visitors": self.unique_visitors,
            "page_views": self.page_views,
            "add_to_cart": self.add_to_cart,
            "checkout_started": self.checkout_started,
            "gross_revenue_cents": self.gross_revenue_cents,
            "net_revenue_cents": self.net_revenue_cents,
            "fees_cents": self.fees_cents,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def revenue_dollars(self) -> float:
        """Get revenue in dollars."""
        return self.revenue_cents / 100.0
    
    @property
    def gross_revenue_dollars(self) -> float:
        """Get gross revenue in dollars."""
        return self.gross_revenue_cents / 100.0
    
    @property
    def net_revenue_dollars(self) -> float:
        """Get net revenue in dollars."""
        return self.net_revenue_cents / 100.0
    
    @property
    def fees_dollars(self) -> float:
        """Get fees in dollars."""
        return self.fees_cents / 100.0
    
    def increment_views(self, count: int = 1) -> None:
        """Increment view count."""
        self.views += count
    
    def increment_sales(self, count: int = 1) -> None:
        """Increment sales count."""
        self.sales += count
    
    def add_revenue(self, cents: int) -> None:
        """Add revenue in cents."""
        self.revenue_cents += cents
        self.gross_revenue_cents += cents
        self.net_revenue_cents += cents
    
    def add_refund(self, cents: int) -> None:
        """Add refund in cents."""
        self.refunds += 1
        self.net_revenue_cents -= cents
    
    def add_fees(self, cents: int) -> None:
        """Add platform fees in cents."""
        self.fees_cents += cents
        self.net_revenue_cents -= cents
    
    def calculate_conversion_rate(self) -> None:
        """Calculate conversion rate from views and sales."""
        if self.views > 0:
            self.conversion_rate = (self.sales / self.views) * 100
        else:
            self.conversion_rate = 0.0
    
    def update_from_gumroad_data(self, gumroad_data: dict) -> None:
        """Update analytics from Gumroad API data."""
        # Update basic metrics
        if "sales" in gumroad_data:
            self.sales = gumroad_data["sales"]
        
        if "revenue" in gumroad_data:
            self.revenue_cents = int(gumroad_data["revenue"] * 100)
        
        if "views" in gumroad_data:
            self.views = gumroad_data["views"]
        
        if "refunds" in gumroad_data:
            self.refunds = gumroad_data["refunds"]
        
        # Calculate conversion rate
        self.calculate_conversion_rate()
    
    def get_daily_summary(self) -> dict:
        """Get daily summary for reporting."""
        return {
            "date": self.date.isoformat() if self.date else None,
            "views": self.views,
            "sales": self.sales,
            "revenue_dollars": self.revenue_dollars,
            "refunds": self.refunds,
            "conversion_rate": self.conversion_rate,
            "source": self.source
        }
    
    def get_performance_metrics(self) -> dict:
        """Get performance metrics for analysis."""
        return {
            "total_views": self.views,
            "total_sales": self.sales,
            "total_revenue": self.revenue_dollars,
            "conversion_rate": self.conversion_rate,
            "refund_rate": (self.refunds / self.sales * 100) if self.sales > 0 else 0,
            "average_order_value": self.revenue_dollars / self.sales if self.sales > 0 else 0,
            "revenue_per_view": self.revenue_dollars / self.views if self.views > 0 else 0
        }


class ProductAnalyticsSummary(Base):
    """
    Product analytics summary model.
    
    Aggregated analytics for reporting and dashboards.
    """
    __tablename__ = "mint_product_analytics_summary"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to product
    product_id = Column(UUID(as_uuid=True), ForeignKey('mint_products.id'), nullable=False)
    
    # Summary period
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly, yearly
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Aggregated metrics
    total_views = Column(Integer, default=0)
    total_sales = Column(Integer, default=0)
    total_revenue_cents = Column(Integer, default=0)
    total_refunds = Column(Integer, default=0)
    average_conversion_rate = Column(Float, default=0.0)
    
    # Performance metrics
    best_day_sales = Column(Integer, default=0)
    best_day_revenue_cents = Column(Integer, default=0)
    worst_day_sales = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    product = relationship("Product")
    
    # Indexes
    __table_args__ = (
        Index('idx_summary_product_id', 'product_id'),
        Index('idx_summary_period_type', 'period_type'),
        Index('idx_summary_period_start', 'period_start'),
        Index('idx_summary_created_at', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<ProductAnalyticsSummary(id={self.id}, product_id={self.product_id}, period={self.period_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "product_id": str(self.product_id),
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "total_views": self.total_views,
            "total_sales": self.total_sales,
            "total_revenue_cents": self.total_revenue_cents,
            "total_revenue_dollars": self.total_revenue_dollars,
            "total_refunds": self.total_refunds,
            "average_conversion_rate": self.average_conversion_rate,
            "best_day_sales": self.best_day_sales,
            "best_day_revenue_cents": self.best_day_revenue_cents,
            "worst_day_sales": self.worst_day_sales,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def total_revenue_dollars(self) -> float:
        """Get total revenue in dollars."""
        return self.total_revenue_cents / 100.0
    
    @property
    def best_day_revenue_dollars(self) -> float:
        """Get best day revenue in dollars."""
        return self.best_day_revenue_cents / 100.0
    
    def calculate_average_conversion_rate(self, daily_analytics: list) -> None:
        """Calculate average conversion rate from daily analytics."""
        if daily_analytics:
            total_conversion = sum(day.conversion_rate for day in daily_analytics)
            self.average_conversion_rate = total_conversion / len(daily_analytics)
        else:
            self.average_conversion_rate = 0.0
    
    def update_from_daily_analytics(self, daily_analytics: list) -> None:
        """Update summary from daily analytics data."""
        if not daily_analytics:
            return
        
        # Calculate totals
        self.total_views = sum(day.views for day in daily_analytics)
        self.total_sales = sum(day.sales for day in daily_analytics)
        self.total_revenue_cents = sum(day.revenue_cents for day in daily_analytics)
        self.total_refunds = sum(day.refunds for day in daily_analytics)
        
        # Find best and worst days
        best_day = max(daily_analytics, key=lambda x: x.sales)
        worst_day = min(daily_analytics, key=lambda x: x.sales)
        
        self.best_day_sales = best_day.sales
        self.best_day_revenue_cents = best_day.revenue_cents
        self.worst_day_sales = worst_day.sales
        
        # Calculate average conversion rate
        self.calculate_average_conversion_rate(daily_analytics)
