"""
BaseLayer Revenue Engine

Core revenue stream management and transaction processing
with automated billing and compliance tracking.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, PricingModel, TransactionStatus
)
from ..models.user import User
from .exceptions import (
    RevenueEngineError,
    RevenueValidationError,
    RevenueComplianceError
)

logger = get_logger(__name__)


class RevenueEngine:
    """
    Core revenue engine for managing revenue streams and transactions.
    
    Handles revenue stream lifecycle, transaction processing,
    and automated billing with compliance tracking.
    """
    
    def __init__(self):
        self.active_streams: Dict[str, RevenueStream] = {}
        self.billing_queue: asyncio.Queue = asyncio.Queue()
        self.compliance_enabled: bool = True
        self.audit_threshold: float = 1000.00  # Audit transactions over $1000
    
    async def create_revenue_stream(
        self,
        name: str,
        description: str,
        revenue_type: RevenueType,
        pricing_model: PricingModel,
        base_amount: float,
        currency: str = "USD",
        billing_cycle: Optional[str] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> RevenueStream:
        """
        Create a new revenue stream.
        
        Args:
            name: Revenue stream name
            description: Revenue stream description
            revenue_type: Type of revenue
            pricing_model: Pricing model
            base_amount: Base amount
            currency: Currency code
            billing_cycle: Billing cycle
            usage_limits: Usage limits configuration
            created_by: User who created the stream
            
        Returns:
            RevenueStream: Created revenue stream
            
        Raises:
            RevenueValidationError: If validation fails
            RevenueComplianceError: If compliance checks fail
        """
        # Validate revenue stream data
        await self._validate_revenue_stream({
            "name": name,
            "description": description,
            "revenue_type": revenue_type,
            "pricing_model": pricing_model,
            "base_amount": base_amount,
            "currency": currency,
            "billing_cycle": billing_cycle,
            "usage_limits": usage_limits
        })
        
        # Check compliance requirements
        await self._check_compliance_requirements({
            "base_amount": base_amount,
            "revenue_type": revenue_type,
            "created_by": created_by
        })
        
        async with get_db_session() as session:
            # Create revenue stream
            revenue_stream = RevenueStream(
                name=name,
                description=description,
                revenue_type=revenue_type,
                status=RevenueStatus.ACTIVE,
                pricing_model=pricing_model,
                base_amount=base_amount,
                currency=currency,
                billing_cycle=billing_cycle,
                usage_limits=usage_limits or {},
                created_by=created_by
            )
            
            session.add(revenue_stream)
            await session.commit()
            await session.refresh(revenue_stream)
            
            # Add to active streams
            self.active_streams[str(revenue_stream.id)] = revenue_stream
            
            logger.info(
                "Revenue stream created",
                stream_id=str(revenue_stream.id),
                stream_name=name,
                revenue_type=revenue_type.value,
                base_amount=base_amount,
                currency=currency
            )
            
            return revenue_stream
    
    async def process_transaction(
        self,
        revenue_stream_id: str,
        amount: float,
        customer_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> RevenueTransaction:
        """
        Process a revenue transaction.
        
        Args:
            revenue_stream_id: Revenue stream ID
            amount: Transaction amount
            customer_id: Customer ID
            payment_method: Payment method
            metadata: Transaction metadata
            created_by: User who created the transaction
            
        Returns:
            RevenueTransaction: Processed transaction
            
        Raises:
            RevenueEngineError: If processing fails
        """
        # Get revenue stream
        revenue_stream = self.active_streams.get(revenue_stream_id)
        if not revenue_stream:
            # Load from database
            async with get_db_session() as session:
                result = await session.execute(
                    select(RevenueStream).where(
                        RevenueStream.id == uuid.UUID(revenue_stream_id),
                        RevenueStream.deleted_at.is_(None)
                    )
                )
                revenue_stream = result.scalar_one_or_none()
                
                if not revenue_stream:
                    raise RevenueEngineError(
                        f"Revenue stream not found: {revenue_stream_id}",
                        revenue_stream_id=revenue_stream_id
                    )
                
                self.active_streams[revenue_stream_id] = revenue_stream
        
        # Validate transaction
        await self._validate_transaction(revenue_stream, amount, metadata)
        
        # Calculate transaction amount based on pricing model
        calculated_amount = await self._calculate_transaction_amount(
            revenue_stream, amount, metadata
        )
        
        async with get_db_session() as session:
            # Create transaction
            transaction = RevenueTransaction(
                revenue_stream_id=revenue_stream.id,
                transaction_id=str(uuid.uuid4()),
                amount=calculated_amount,
                currency=revenue_stream.currency,
                customer_id=customer_id,
                payment_method=payment_method,
                status=TransactionStatus.PENDING,
                metadata_=metadata or {},
                created_by=created_by
            )
            
            session.add(transaction)
            await session.commit()
            await session.refresh(transaction)
            
            # Process payment
            await self._process_payment(transaction)
            
            # Update metrics
            await self._update_revenue_metrics(revenue_stream.id, transaction)
            
            # Check compliance
            if calculated_amount >= self.audit_threshold:
                await self._audit_transaction(transaction)
            
            logger.info(
                "Transaction processed",
                transaction_id=transaction.transaction_id,
                revenue_stream_id=revenue_stream_id,
                amount=calculated_amount,
                currency=revenue_stream.currency,
                status=transaction.status.value
            )
            
            return transaction
    
    async def _validate_revenue_stream(self, stream_data: Dict[str, Any]) -> None:
        """
        Validate revenue stream data.
        
        Args:
            stream_data: Revenue stream data to validate
            
        Raises:
            RevenueValidationError: If validation fails
        """
        errors = []
        
        # Required fields
        if not stream_data.get("name"):
            errors.append("Revenue stream name is required")
        
        if not stream_data.get("revenue_type"):
            errors.append("Revenue type is required")
        
        if not stream_data.get("pricing_model"):
            errors.append("Pricing model is required")
        
        base_amount = stream_data.get("base_amount")
        if base_amount is None or base_amount < 0:
            errors.append("Base amount must be a non-negative number")
        
        # Currency validation
        currency = stream_data.get("currency", "USD")
        if not self._is_valid_currency(currency):
            errors.append(f"Invalid currency: {currency}")
        
        # Billing cycle validation for subscriptions
        if stream_data.get("revenue_type") == RevenueType.SUBSCRIPTION:
            billing_cycle = stream_data.get("billing_cycle")
            if not billing_cycle:
                errors.append("Billing cycle is required for subscription revenue")
            elif not self._is_valid_billing_cycle(billing_cycle):
                errors.append(f"Invalid billing cycle: {billing_cycle}")
        
        # Usage limits validation
        usage_limits = stream_data.get("usage_limits", {})
        if usage_limits:
            if not isinstance(usage_limits, dict):
                errors.append("Usage limits must be a dictionary")
            else:
                # Validate tiered pricing
                tiers = usage_limits.get("tiers", [])
                if tiers and not isinstance(tiers, list):
                    errors.append("Usage tiers must be a list")
        
        if errors:
            raise RevenueValidationError(
                f"Revenue stream validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    async def _validate_transaction(
        self,
        revenue_stream: RevenueStream,
        amount: float,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """
        Validate transaction data.
        
        Args:
            revenue_stream: Revenue stream
            amount: Transaction amount
            metadata: Transaction metadata
            
        Raises:
            RevenueValidationError: If validation fails
        """
        errors = []

        # Amount validation — refunds and downgrade/cancellation proration
        # legitimately carry a negative amount; only reject unexplained ones.
        transaction_type = (metadata or {}).get("transaction_type", "")
        is_credit = "refund" in transaction_type or "proration" in transaction_type
        if amount < 0 and not is_credit:
            errors.append("Transaction amount cannot be negative")
        
        # Revenue stream status
        if revenue_stream.status != RevenueStatus.ACTIVE:
            errors.append(f"Revenue stream is not active: {revenue_stream.status.value}")
        
        # Usage-based validation
        if revenue_stream.revenue_type == RevenueType.USAGE_BASED:
            if not metadata:
                errors.append("Metadata is required for usage-based transactions")
            else:
                usage_units = metadata.get("usage_units")
                if usage_units is None or usage_units < 0:
                    errors.append("Usage units must be a non-negative number")
        
        if errors:
            raise RevenueValidationError(
                f"Transaction validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    async def _check_compliance_requirements(
        self,
        stream_data: Dict[str, Any]
    ) -> None:
        """
        Check compliance requirements for revenue operations.
        
        Args:
            stream_data: Revenue stream data
            
        Raises:
            RevenueComplianceError: If compliance checks fail
        """
        if not self.compliance_enabled:
            return
        
        base_amount = stream_data.get("base_amount", 0)
        revenue_type = stream_data.get("revenue_type")
        created_by = stream_data.get("created_by")
        
        compliance_issues = []
        
        # High-value revenue streams require approval
        if base_amount > 10000:
            compliance_issues.append("High-value revenue stream requires approval")
        
        # Check user permissions
        if created_by:
            async with get_db_session() as session:
                result = await session.execute(
                    select(User).where(User.id == created_by)
                )
                user = result.scalar_one_or_none()
                
                if user and not user.can_manage_revenue:
                    compliance_issues.append("User lacks revenue management permissions")
        
        if compliance_issues:
            raise RevenueComplianceError(
                f"Compliance check failed: {'; '.join(compliance_issues)}",
                compliance_rules=["revenue_stream_approval", "user_permissions"],
                audit_level="high"
            )
    
    async def _calculate_transaction_amount(
        self,
        revenue_stream: RevenueStream,
        input_amount: float,
        metadata: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate transaction amount based on pricing model.
        
        Args:
            revenue_stream: Revenue stream
            input_amount: Input amount
            metadata: Transaction metadata
            
        Returns:
            float: Calculated amount
        """
        if revenue_stream.pricing_model == PricingModel.FIXED:
            # Every caller (initial charge, proration, refund) already computes
            # the exact amount to charge — trust it instead of re-charging the
            # full base_amount regardless of context (was double-charging plan
            # upgrades and discarding proration/refund adjustments entirely).
            return input_amount

        elif revenue_stream.pricing_model == PricingModel.USAGE_BASED:
            usage_limits = revenue_stream.usage_limits or {}
            pricing_tiers = usage_limits.get("pricing_tiers", [])

            if not pricing_tiers:
                return revenue_stream.base_amount * Decimal(str(input_amount))
            
            # Find applicable tier
            usage_units = metadata.get("usage_units", input_amount) if metadata else input_amount
            
            for tier in sorted(pricing_tiers, key=lambda x: x.get("min_requests", 0)):
                min_requests = tier.get("min_requests", 0)
                max_requests = tier.get("max_requests")
                
                if usage_units >= min_requests and (max_requests is None or usage_units <= max_requests):
                    price_per_unit = tier.get("price_per_request", revenue_stream.base_amount)
                    return price_per_unit * usage_units
            
            # Default to last tier
            last_tier = pricing_tiers[-1]
            price_per_unit = last_tier.get("price_per_request", revenue_stream.base_amount)
            return price_per_unit * usage_units
        
        elif revenue_stream.pricing_model == PricingModel.TIERED:
            usage_limits = revenue_stream.usage_limits or {}
            tiers = usage_limits.get("tiers", [])
            
            if not tiers:
                return revenue_stream.base_amount
            
            # Find tier based on metadata or default to first tier
            tier_name = metadata.get("tier") if metadata else None
            
            for tier in tiers:
                if tier_name and tier.get("name") == tier_name:
                    return tier.get("price", revenue_stream.base_amount)
            
            # Default to first tier
            return tiers[0].get("price", revenue_stream.base_amount)
        
        else:
            return revenue_stream.base_amount
    
    async def _process_payment(self, transaction: RevenueTransaction) -> None:
        """
        Process payment for a transaction.
        
        Args:
            transaction: Transaction to process
        """
        # Simulate payment processing
        # In real implementation, this would integrate with payment providers
        # (see income_engine/providers.py — built but not yet wired in here)
        await asyncio.sleep(0.1)

        # Error-placeholder transactions (created by billing.py when the real
        # billing attempt already failed) must not be recorded as completed —
        # that was silently breaking failed_transactions accounting.
        if (transaction.metadata_ or {}).get("error"):
            transaction.status = TransactionStatus.FAILED
            transaction.processed_at = datetime.utcnow()

            async with get_db_session() as session:
                session.add(transaction)
                await session.commit()
            return

        # Update transaction status
        transaction.status = TransactionStatus.COMPLETED
        transaction.processed_at = datetime.utcnow()
        
        async with get_db_session() as session:
            session.add(transaction)
            await session.commit()
    
    async def _update_revenue_metrics(
        self,
        revenue_stream_id: uuid.UUID,
        transaction: RevenueTransaction
    ) -> None:
        """
        Update revenue metrics for a stream.
        
        Args:
            revenue_stream_id: Revenue stream ID
            transaction: Transaction to include in metrics
        """
        async with get_db_session() as session:
            # Get or create metrics for current period
            current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Lock the row for the duration of this transaction so concurrent
            # billing runs on the same stream/period serialize instead of
            # racing on the read-modify-write below (was silently dropping
            # increments under concurrent billing).
            result = await session.execute(
                select(RevenueMetrics).where(
                    RevenueMetrics.revenue_stream_id == revenue_stream_id,
                    RevenueMetrics.period_start == current_month
                ).with_for_update()
            )
            metrics = result.scalar_one_or_none()

            if not metrics:
                metrics = RevenueMetrics(
                    revenue_stream_id=revenue_stream_id,
                    period_start=current_month,
                    period_end=current_month + timedelta(days=32) - timedelta(seconds=1),
                    total_revenue=Decimal("0"),
                    total_transactions=0,
                    successful_transactions=0,
                    failed_transactions=0
                )
                session.add(metrics)
                await session.flush()
            
            # Update metrics
            metrics.total_revenue += transaction.amount
            metrics.total_transactions += 1
            
            if transaction.status == TransactionStatus.COMPLETED:
                metrics.successful_transactions += 1
            else:
                metrics.failed_transactions += 1
            
            # Calculate derived metrics
            await metrics.calculate_derived_metrics()
            
            await session.commit()
    
    async def _audit_transaction(self, transaction: RevenueTransaction) -> None:
        """
        Audit a high-value transaction.
        
        Args:
            transaction: Transaction to audit
        """
        logger.info(
            "High-value transaction audit triggered",
            transaction_id=transaction.transaction_id,
            amount=transaction.amount,
            currency=transaction.currency
        )
        
        # In real implementation, this would:
        # 1. Create audit log entry
        # 2. Notify compliance team
        # 3. Require manual review
        # 4. Update compliance metrics
    
    def _is_valid_currency(self, currency: str) -> bool:
        """Check if currency code is valid."""
        valid_currencies = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"}
        return currency in valid_currencies
    
    def _is_valid_billing_cycle(self, billing_cycle: str) -> bool:
        """Check if billing cycle is valid."""
        valid_cycles = {"daily", "weekly", "monthly", "quarterly", "yearly"}
        return billing_cycle.lower() in valid_cycles
    
    async def get_revenue_stream(
        self,
        stream_id: str
    ) -> Optional[RevenueStream]:
        """
        Get a revenue stream by ID.
        
        Args:
            stream_id: Revenue stream ID
            
        Returns:
            RevenueStream: Revenue stream or None
        """
        # Check cache first
        if stream_id in self.active_streams:
            return self.active_streams[stream_id]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(RevenueStream).where(
                    RevenueStream.id == uuid.UUID(stream_id),
                    RevenueStream.deleted_at.is_(None)
                )
            )
            stream = result.scalar_one_or_none()
            
            if stream:
                self.active_streams[stream_id] = stream
            
            return stream
    
    async def list_revenue_streams(
        self,
        status: Optional[RevenueStatus] = None,
        revenue_type: Optional[RevenueType] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[RevenueStream]:
        """
        List revenue streams with optional filtering.
        
        Args:
            status: Filter by status
            revenue_type: Filter by revenue type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[RevenueStream]: List of revenue streams
        """
        async with get_db_session() as session:
            query = select(RevenueStream).where(RevenueStream.deleted_at.is_(None))
            
            if status:
                query = query.where(RevenueStream.status == status)
            
            if revenue_type:
                query = query.where(RevenueStream.revenue_type == revenue_type)
            
            query = query.order_by(RevenueStream.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            streams = result.scalars().all()
            
            # Update cache
            for stream in streams:
                self.active_streams[str(stream.id)] = stream
            
            return list(streams)
    
    async def get_revenue_metrics(
        self,
        stream_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[RevenueMetrics]:
        """
        Get revenue metrics for a stream within a period.
        
        Args:
            stream_id: Revenue stream ID
            period_start: Start of period
            period_end: End of period
            
        Returns:
            List[RevenueMetrics]: List of metrics
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(RevenueMetrics).where(
                    RevenueMetrics.revenue_stream_id == uuid.UUID(stream_id),
                    RevenueMetrics.period_start >= period_start,
                    RevenueMetrics.period_end <= period_end
                ).order_by(RevenueMetrics.period_start)
            )
            return list(result.scalars().all())
    
    async def deactivate_revenue_stream(
        self,
        stream_id: str,
        reason: str = "Manual deactivation"
    ) -> bool:
        """
        Deactivate a revenue stream.
        
        Args:
            stream_id: Revenue stream ID
            reason: Deactivation reason
            
        Returns:
            bool: True if deactivated successfully
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(RevenueStream).where(
                    RevenueStream.id == uuid.UUID(stream_id),
                    RevenueStream.deleted_at.is_(None)
                )
            )
            stream = result.scalar_one_or_none()
            
            if not stream:
                return False
            
            stream.status = RevenueStatus.INACTIVE
            stream.metadata_ = stream.metadata_ or {}
            stream.metadata_["deactivation_reason"] = reason
            stream.metadata_["deactivated_at"] = datetime.utcnow().isoformat()
            
            session.add(stream)
            await session.commit()
            
            # Remove from active cache
            self.active_streams.pop(stream_id, None)
            
            logger.info(
                "Revenue stream deactivated",
                stream_id=stream_id,
                reason=reason
            )
            
            return True
