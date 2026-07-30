"""
BaseLayer Income Engine Models

Revenue stream management, transaction tracking, and financial metrics
for the Income Engine subsystem.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, Numeric, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class RevenueType(str, Enum):
    """Revenue stream types."""
    SUBSCRIPTION = "subscription"
    ONE_TIME = "one_time"
    USAGE_BASED = "usage_based"
    COMMISSION = "commission"
    LICENSING = "licensing"


class RevenueStatus(str, Enum):
    """Revenue stream status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"


class PricingModel(str, Enum):
    """Pricing models for revenue streams."""
    FIXED = "fixed"
    TIERED = "tiered"
    USAGE_BASED = "usage_based"
    DYNAMIC = "dynamic"


class BillingCycle(str, Enum):
    """Billing cycles for recurring revenue."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class TransactionStatus(str, Enum):
    """Transaction status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class RevenueStream(BaseModel):
    """
    Revenue stream model for Income Engine.
    
    Defines automated revenue pipelines with pricing, billing, and tracking.
    """
    
    __tablename__ = "revenue_streams"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Revenue stream name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Revenue stream description"
    )
    
    # Type and status
    revenue_type: Mapped[RevenueType] = mapped_column(
        ENUM(RevenueType, name="revenue_type"),
        nullable=False,
        index=True,
        comment="Type of revenue stream"
    )
    
    status: Mapped[RevenueStatus] = mapped_column(
        ENUM(RevenueStatus, name="revenue_status"),
        nullable=False,
        default=RevenueStatus.PENDING,
        index=True,
        comment="Current revenue stream status"
    )
    
    # Pricing configuration
    pricing_model: Mapped[PricingModel] = mapped_column(
        ENUM(PricingModel, name="pricing_model"),
        nullable=False,
        default=PricingModel.FIXED,
        comment="Pricing model for the revenue stream"
    )
    
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Base amount for fixed pricing"
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="Currency code (ISO 4217)"
    )
    
    # Billing configuration
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        ENUM(BillingCycle, name="billing_cycle"),
        nullable=True,
        comment="Billing cycle for recurring revenue"
    )
    
    billing_day: Mapped[int] = mapped_column(
        String(2),
        nullable=True,
        comment="Day of month for billing (1-31)"
    )
    
    trial_days: Mapped[int] = mapped_column(
        String(3),
        nullable=True,
        default="0",
        comment="Number of trial days"
    )
    
    # Usage limits and tiers
    usage_limits: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Usage limits and tier configurations"
    )
    
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Commission rate (0.0000 - 1.0000)"
    )
    
    # Integration settings
    payment_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment provider (stripe, paypal, etc.)"
    )
    
    provider_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific configuration"
    )
    
    webhook_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Webhook URL for payment notifications"
    )
    
    # Automation settings
    auto_bill: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to automatically bill customers"
    )
    
    retry_failed_payments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to retry failed payments"
    )
    
    max_retry_attempts: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="3",
        comment="Maximum number of payment retry attempts"
    )
    
    # Metadata
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Revenue stream category"
    )
    
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tags for categorization"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="revenue_streams",
        foreign_keys=[BaseModel.created_by],
        lazy="select"
    )
    
    transactions = relationship(
        "RevenueTransaction",
        back_populates="revenue_stream",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    metrics = relationship(
        "RevenueMetrics",
        back_populates="revenue_stream",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_revenue_stream_name_deleted"),
        Index("idx_revenue_type_status", "revenue_type", "status"),
        Index("idx_revenue_category", "category"),
        Index("idx_revenue_created_at", "created_at"),
        {"comment": "Revenue streams for automated income generation"}
    )
    
    def __repr__(self) -> str:
        """String representation of the revenue stream."""
        return f"<RevenueStream(name='{self.name}', type='{self.revenue_type}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if revenue stream is active."""
        return self.status == RevenueStatus.ACTIVE
    
    @property
    def is_subscription(self) -> bool:
        """Check if this is a subscription revenue stream."""
        return self.revenue_type == RevenueType.SUBSCRIPTION
    
    @property
    def is_usage_based(self) -> bool:
        """Check if this is a usage-based revenue stream."""
        return self.revenue_type == RevenueType.USAGE_BASED
    
    def activate(self) -> None:
        """Activate the revenue stream."""
        self.status = RevenueStatus.ACTIVE
        self.increment_version()
    
    def deactivate(self) -> None:
        """Deactivate the revenue stream."""
        self.status = RevenueStatus.INACTIVE
        self.increment_version()
    
    def suspend(self) -> None:
        """Suspend the revenue stream."""
        self.status = RevenueStatus.SUSPENDED
        self.increment_version()
    
    def calculate_price(self, usage_data: Dict[str, Any] | None = None) -> Decimal:
        """
        Calculate price based on pricing model and usage.
        
        Args:
            usage_data: Usage data for usage-based pricing
            
        Returns:
            Decimal: Calculated price
        """
        if self.pricing_model == PricingModel.FIXED:
            return self.base_amount or Decimal('0.00')
        
        elif self.pricing_model == PricingModel.USAGE_BASED:
            # TODO: Implement usage-based pricing logic
            return self.base_amount or Decimal('0.00')
        
        elif self.pricing_model == PricingModel.TIERED:
            # TODO: Implement tiered pricing logic
            return self.base_amount or Decimal('0.00')
        
        elif self.pricing_model == PricingModel.DYNAMIC:
            # TODO: Implement dynamic pricing logic
            return self.base_amount or Decimal('0.00')
        
        return Decimal('0.00')
    
    def get_next_billing_date(self, from_date: datetime | None = None) -> datetime | None:
        """
        Calculate next billing date.
        
        Args:
            from_date: Date to calculate from (defaults to current date)
            
        Returns:
            datetime | None: Next billing date
        """
        if not self.billing_cycle or not self.billing_day:
            return None
        
        from_date = from_date or datetime.utcnow()
        
        if self.billing_cycle == BillingCycle.MONTHLY:
            # Calculate next month with the specified day
            if from_date.day > int(self.billing_day):
                # Next month
                next_month = from_date.replace(day=1).replace(month=(from_date.month % 12) + 1)
                if from_date.month == 12:
                    next_month = next_month.replace(year=next_month.year + 1)
                return next_month.replace(day=int(self.billing_day))
            else:
                # This month
                return from_date.replace(day=int(self.billing_day))
        
        elif self.billing_cycle == BillingCycle.QUARTERLY:
            # TODO: Implement quarterly billing logic
            pass
        
        elif self.billing_cycle == BillingCycle.YEARLY:
            # TODO: Implement yearly billing logic
            pass
        
        return None


class RevenueTransaction(BaseModel):
    """
    Revenue transaction model.
    
    Tracks individual revenue transactions with payment processing and status.
    """
    
    __tablename__ = "revenue_transactions"
    
    # References
    revenue_stream_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("revenue_streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the revenue stream"
    )
    
    # Transaction details
    transaction_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique transaction identifier"
    )
    
    external_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="External payment provider transaction ID"
    )
    
    # Customer information
    customer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Customer identifier"
    )
    
    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer email"
    )
    
    # Financial details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Transaction amount"
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="Currency code (ISO 4217)"
    )
    
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        default=Decimal('0.00'),
        comment="Payment processing fee"
    )
    
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Net amount after fees"
    )
    
    # Status and timing
    status: Mapped[TransactionStatus] = mapped_column(
        ENUM(TransactionStatus, name="transaction_status"),
        nullable=False,
        default=TransactionStatus.PENDING,
        index=True,
        comment="Current transaction status"
    )
    
    initiated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Transaction initiation time"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Transaction completion time"
    )
    
    failed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Transaction failure time"
    )
    
    # Payment details
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment method (card, bank_transfer, etc.)"
    )
    
    payment_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment provider"
    )
    
    # Billing period
    billing_period_start: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Start of billing period"
    )
    
    billing_period_end: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="End of billing period"
    )
    
    # Usage data
    usage_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Usage data for usage-based billing"
    )
    
    # Error handling
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if transaction failed"
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if transaction failed"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    # Metadata
    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional transaction metadata"
    )
    
    # Relationships
    revenue_stream = relationship(
        "RevenueStream",
        back_populates="transactions",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_transaction_stream_status", "revenue_stream_id", "status"),
        Index("idx_transaction_customer", "customer_id"),
        Index("idx_transaction_initiated", "initiated_at"),
        Index("idx_transaction_amount", "amount"),
        {"comment": "Individual revenue transactions tracking"}
    )
    
    def __repr__(self) -> str:
        """String representation of the transaction."""
        return f"<RevenueTransaction(transaction_id='{self.transaction_id}', amount={self.amount}, status='{self.status}')>"
    
    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == TransactionStatus.COMPLETED
    
    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status == TransactionStatus.PENDING
    
    @property
    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.status == TransactionStatus.FAILED
    
    def complete(self, external_id: str | None = None) -> None:
        """
        Mark transaction as completed.
        
        Args:
            external_id: External transaction ID from payment provider
        """
        self.status = TransactionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        
        if external_id:
            self.external_id = external_id
        
        # Calculate net amount
        if self.fee_amount:
            self.net_amount = self.amount - self.fee_amount
        else:
            self.net_amount = self.amount
    
    def fail(self, error_code: str, error_message: str) -> None:
        """
        Mark transaction as failed.
        
        Args:
            error_code: Error code from payment provider
            error_message: Error message
        """
        self.status = TransactionStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_code = error_code
        self.error_message = error_message
    
    def refund(self, amount: Decimal | None = None) -> None:
        """
        Refund the transaction.
        
        Args:
            amount: Amount to refund (defaults to full amount)
        """
        self.status = TransactionStatus.REFUNDED
        self.completed_at = datetime.utcnow()
        
        # Store refund amount in metadata
        if not self.metadata_:
            self.metadata_ = {}
        
        self.metadata_["refund_amount"] = str(amount or self.amount)
        self.metadata_["refunded_at"] = datetime.utcnow().isoformat()


class RevenueMetrics(BaseModel):
    """
    Revenue metrics model.
    
    Tracks revenue performance metrics and analytics.
    """
    
    __tablename__ = "revenue_metrics"
    
    # References
    revenue_stream_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("revenue_streams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the revenue stream"
    )
    
    # Metrics period
    period_start: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Start of metrics period"
    )
    
    period_end: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="End of metrics period"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period type (daily, weekly, monthly, yearly)"
    )
    
    # Revenue metrics
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
        comment="Total revenue in period"
    )
    
    gross_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
        comment="Gross revenue before fees"
    )
    
    net_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
        comment="Net revenue after fees"
    )
    
    fees: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
        comment="Total processing fees"
    )
    
    refunds: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
        comment="Total refunds in period"
    )
    
    # Customer metrics
    new_customers: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of new customers"
    )
    
    active_customers: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of active customers"
    )
    
    churned_customers: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of churned customers"
    )
    
    # Transaction metrics
    total_transactions: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Total number of transactions"
    )
    
    successful_transactions: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of successful transactions"
    )
    
    failed_transactions: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of failed transactions"
    )
    
    # Calculated metrics
    average_revenue_per_customer: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average revenue per customer"
    )
    
    churn_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Customer churn rate"
    )
    
    conversion_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Conversion rate"
    )
    
    # Relationships
    revenue_stream = relationship(
        "RevenueStream",
        back_populates="metrics",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("revenue_stream_id", "period_start", "period_end", "period_type", name="uq_revenue_metrics_period"),
        Index("idx_metrics_period", "period_start", "period_end"),
        Index("idx_metrics_revenue", "total_revenue"),
        {"comment": "Revenue performance metrics and analytics"}
    )
    
    def __repr__(self) -> str:
        """String representation of the revenue metrics."""
        return f"<RevenueMetrics(period='{self.period_type}', revenue={self.total_revenue})>"
    
    def calculate_derived_metrics(self) -> None:
        """Calculate derived metrics from base metrics."""
        # Average revenue per customer
        if self.active_customers and int(self.active_customers) > 0:
            self.average_revenue_per_customer = self.net_revenue / Decimal(int(self.active_customers))
        
        # Churn rate
        if self.active_customers and int(self.active_customers) > 0:
            self.churn_rate = Decimal(int(self.churned_customers)) / Decimal(int(self.active_customers))
        
        # Conversion rate
        if self.new_customers and int(self.new_customers) > 0:
            total_potential = int(self.new_customers) + int(self.churned_customers)
            if total_potential > 0:
                self.conversion_rate = Decimal(int(self.new_customers)) / Decimal(total_potential)
