"""
BaseLayer Subscription Manager

Subscription lifecycle management, plan changes, and automated billing
for the Income Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, TransactionStatus
)
from ..models.user import User
from .engine import RevenueEngine
from .exceptions import SubscriptionError

logger = get_logger(__name__)


class SubscriptionManager:
    """
    Subscription lifecycle manager.
    
    Handles subscription creation, plan changes, cancellations,
    and automated billing with proration support.
    """
    
    def __init__(self, revenue_engine: RevenueEngine):
        self.revenue_engine = revenue_engine
        self.subscription_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 300  # 5 minutes
    
    async def create_subscription(
        self,
        customer_id: str,
        stream_id: str,
        plan_tier: str,
        billing_cycle: str,
        payment_method: str,
        trial_days: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a new subscription.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            plan_tier: Subscription plan tier
            billing_cycle: Billing cycle
            payment_method: Payment method
            trial_days: Number of trial days
            metadata: Additional metadata
            created_by: User who created the subscription
            
        Returns:
            Dict[str, Any]: Created subscription details
            
        Raises:
            SubscriptionError: If creation fails
        """
        # Validate stream supports subscriptions
        stream = await self.revenue_engine.get_revenue_stream(stream_id)
        if not stream:
            raise SubscriptionError(f"Revenue stream not found: {stream_id}")
        
        if stream.revenue_type != RevenueType.SUBSCRIPTION:
            raise SubscriptionError(f"Stream {stream_id} does not support subscriptions")
        
        # Check for existing subscription
        existing = await self._get_customer_subscription(customer_id, stream_id)
        if existing and existing["status"] == "active":
            raise SubscriptionError(f"Customer {customer_id} already has an active subscription")
        
        # Calculate billing dates
        now = datetime.utcnow()
        trial_end = now + timedelta(days=trial_days) if trial_days > 0 else None
        next_billing = trial_end if trial_end else now
        
        # Calculate first billing amount
        if trial_days > 0:
            first_amount = 0.0
        else:
            first_amount = await self._calculate_plan_amount(stream, plan_tier)
        
        # Create subscription record
        subscription_id = str(uuid.uuid4())
        subscription = {
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "stream_id": stream_id,
            "plan_tier": plan_tier,
            "billing_cycle": billing_cycle,
            "payment_method": payment_method,
            "status": "trial" if trial_days > 0 else "active",
            "created_at": now,
            "trial_end": trial_end.isoformat() if trial_end else None,
            "next_billing_date": next_billing.isoformat(),
            "current_period_start": now.isoformat(),
            "current_period_end": self._calculate_period_end(next_billing, billing_cycle).isoformat(),
            "metadata": metadata or {}
        }
        
        # Cache subscription
        self.subscription_cache[f"{customer_id}:{stream_id}"] = subscription
        
        # Create initial transaction if not trial
        if trial_days == 0:
            await self._create_subscription_transaction(
                stream, subscription, first_amount, "initial_payment"
            )
        
        logger.info(
            "Subscription created",
            subscription_id=subscription_id,
            customer_id=customer_id,
            stream_id=stream_id,
            plan_tier=plan_tier,
            trial_days=trial_days
        )
        
        return subscription
    
    async def update_subscription_plan(
        self,
        customer_id: str,
        stream_id: str,
        new_plan_tier: str,
        effective_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update subscription plan with proration.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            new_plan_tier: New plan tier
            effective_date: When the change takes effect
            
        Returns:
            Dict[str, Any]: Updated subscription details
            
        Raises:
            SubscriptionError: If update fails
        """
        subscription = await self._get_customer_subscription(customer_id, stream_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found for customer {customer_id}")
        
        if subscription["status"] != "active":
            raise SubscriptionError(f"Cannot update inactive subscription: {subscription['status']}")
        
        stream = await self.revenue_engine.get_revenue_stream(stream_id)
        old_plan = subscription["plan_tier"]
        
        # Calculate proration
        effective_date = effective_date or datetime.utcnow()
        proration_amount = await self._calculate_proration(
            stream, old_plan, new_plan_tier, effective_date
        )
        
        # Update subscription
        subscription["plan_tier"] = new_plan_tier
        subscription["previous_plan"] = old_plan
        subscription["plan_changed_at"] = effective_date.isoformat()
        
        # Cache updated subscription
        self.subscription_cache[f"{customer_id}:{stream_id}"] = subscription
        
        # Create proration transaction if needed
        if abs(proration_amount) > 0.01:  # Only create transaction for significant amounts
            await self._create_subscription_transaction(
                stream, subscription, proration_amount, "plan_change_proration"
            )
        
        logger.info(
            "Subscription plan updated",
            subscription_id=subscription["subscription_id"],
            customer_id=customer_id,
            old_plan=old_plan,
            new_plan=new_plan_tier,
            proration_amount=proration_amount
        )
        
        return subscription
    
    async def cancel_subscription(
        self,
        customer_id: str,
        stream_id: str,
        reason: str = "Customer request",
        effective_date: Optional[datetime] = None,
        refund_pro_rated: bool = False
    ) -> Dict[str, Any]:
        """
        Cancel subscription with optional refund.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            reason: Cancellation reason
            effective_date: When cancellation takes effect
            refund_pro_rated: Whether to refund pro-rated amount
            
        Returns:
            Dict[str, Any]: Cancellation details
            
        Raises:
            SubscriptionError: If cancellation fails
        """
        subscription = await self._get_customer_subscription(customer_id, stream_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found for customer {customer_id}")
        
        if subscription["status"] in ["cancelled", "expired"]:
            raise SubscriptionError(f"Subscription already {subscription['status']}")
        
        effective_date = effective_date or datetime.utcnow()
        
        # Calculate refund if requested
        refund_amount = 0.0
        if refund_pro_rated:
            stream = await self.revenue_engine.get_revenue_stream(stream_id)
            refund_amount = await self._calculate_refund(subscription, stream, effective_date)
        
        # Update subscription
        subscription["status"] = "cancelled"
        subscription["cancelled_at"] = effective_date.isoformat()
        subscription["cancellation_reason"] = reason
        subscription["refund_amount"] = refund_amount
        
        # Cache updated subscription
        self.subscription_cache[f"{customer_id}:{stream_id}"] = subscription
        
        # Create refund transaction if needed
        if refund_amount > 0:
            await self._create_subscription_transaction(
                stream, subscription, -refund_amount, "cancellation_refund"
            )
        
        logger.info(
            "Subscription cancelled",
            subscription_id=subscription["subscription_id"],
            customer_id=customer_id,
            reason=reason,
            refund_amount=refund_amount
        )
        
        return subscription
    
    async def pause_subscription(
        self,
        customer_id: str,
        stream_id: str,
        reason: str = "Customer request",
        pause_duration_days: int = 30
    ) -> Dict[str, Any]:
        """
        Pause subscription for a period.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            reason: Pause reason
            pause_duration_days: Duration of pause in days
            
        Returns:
            Dict[str, Any]: Pause details
            
        Raises:
            SubscriptionError: If pause fails
        """
        subscription = await self._get_customer_subscription(customer_id, stream_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found for customer {customer_id}")
        
        if subscription["status"] != "active":
            raise SubscriptionError(f"Cannot pause inactive subscription: {subscription['status']}")
        
        now = datetime.utcnow()
        resume_date = now + timedelta(days=pause_duration_days)
        
        # Update subscription
        subscription["status"] = "paused"
        subscription["paused_at"] = now.isoformat()
        subscription["pause_reason"] = reason
        subscription["resume_date"] = resume_date.isoformat()
        
        # Cache updated subscription
        self.subscription_cache[f"{customer_id}:{stream_id}"] = subscription
        
        logger.info(
            "Subscription paused",
            subscription_id=subscription["subscription_id"],
            customer_id=customer_id,
            pause_duration_days=pause_duration_days,
            resume_date=resume_date.isoformat()
        )
        
        return subscription
    
    async def resume_subscription(
        self,
        customer_id: str,
        stream_id: str
    ) -> Dict[str, Any]:
        """
        Resume a paused subscription.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            
        Returns:
            Dict[str, Any]: Resume details
            
        Raises:
            SubscriptionError: If resume fails
        """
        subscription = await self._get_customer_subscription(customer_id, stream_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found for customer {customer_id}")
        
        if subscription["status"] != "paused":
            raise SubscriptionError(f"Subscription is not paused: {subscription['status']}")
        
        now = datetime.utcnow()
        
        # Update subscription
        subscription["status"] = "active"
        subscription["resumed_at"] = now.isoformat()
        subscription["next_billing_date"] = now.isoformat()
        
        # Remove pause-related fields
        subscription.pop("paused_at", None)
        subscription.pop("pause_reason", None)
        subscription.pop("resume_date", None)
        
        # Cache updated subscription
        self.subscription_cache[f"{customer_id}:{stream_id}"] = subscription
        
        # Create immediate billing transaction
        stream = await self.revenue_engine.get_revenue_stream(stream_id)
        billing_amount = await self._calculate_plan_amount(stream, subscription["plan_tier"])
        
        await self._create_subscription_transaction(
            stream, subscription, billing_amount, "resume_billing"
        )
        
        logger.info(
            "Subscription resumed",
            subscription_id=subscription["subscription_id"],
            customer_id=customer_id
        )
        
        return subscription
    
    async def get_subscription(
        self,
        customer_id: str,
        stream_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription details.
        
        Args:
            customer_id: Customer ID
            stream_id: Revenue stream ID
            
        Returns:
            Dict[str, Any]: Subscription details or None
        """
        return await self._get_customer_subscription(customer_id, stream_id)
    
    async def list_customer_subscriptions(
        self,
        customer_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all subscriptions for a customer.
        
        Args:
            customer_id: Customer ID
            status: Filter by status
            
        Returns:
            List[Dict[str, Any]]: List of subscriptions
        """
        # In real implementation, this would query a subscription table
        # For now, return cached subscriptions
        customer_subscriptions = []
        
        for key, subscription in self.subscription_cache.items():
            if subscription["customer_id"] == customer_id:
                if status is None or subscription["status"] == status:
                    customer_subscriptions.append(subscription)
        
        return customer_subscriptions
    
    async def process_subscription_billing(self) -> Dict[str, Any]:
        """
        Process all due subscription billings.
        
        Returns:
            Dict[str, Any]: Billing results
        """
        now = datetime.utcnow()
        billing_results = {
            "processed_subscriptions": 0,
            "successful_billings": 0,
            "failed_billings": 0,
            "total_amount": 0.0
        }
        
        # Get all active subscriptions due for billing
        due_subscriptions = []
        for subscription in self.subscription_cache.values():
            if (subscription["status"] == "active" and
                datetime.fromisoformat(subscription["next_billing_date"]) <= now):
                due_subscriptions.append(subscription)
        
        # Process billing for each subscription
        for subscription in due_subscriptions:
            try:
                stream = await self.revenue_engine.get_revenue_stream(subscription["stream_id"])
                billing_amount = await self._calculate_plan_amount(stream, subscription["plan_tier"])
                
                # Create billing transaction
                transaction = await self._create_subscription_transaction(
                    stream, subscription, billing_amount, "recurring_billing"
                )
                
                # Update next billing date
                next_billing = self._calculate_next_billing_date(
                    datetime.fromisoformat(subscription["next_billing_date"]),
                    subscription["billing_cycle"]
                )
                subscription["next_billing_date"] = next_billing.isoformat()
                
                billing_results["successful_billings"] += 1
                billing_results["total_amount"] += billing_amount
                
                logger.info(
                    "Subscription billing processed",
                    subscription_id=subscription["subscription_id"],
                    customer_id=subscription["customer_id"],
                    amount=billing_amount,
                    next_billing=next_billing.isoformat()
                )
                
            except Exception as e:
                billing_results["failed_billings"] += 1
                logger.error(
                    "Subscription billing failed",
                    subscription_id=subscription["subscription_id"],
                    customer_id=subscription["customer_id"],
                    error=str(e)
                )
            
            billing_results["processed_subscriptions"] += 1
        
        return billing_results
    
    async def _get_customer_subscription(
        self,
        customer_id: str,
        stream_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get customer subscription from cache or database."""
        cache_key = f"{customer_id}:{stream_id}"
        
        # Check cache first
        if cache_key in self.subscription_cache:
            return self.subscription_cache[cache_key]
        
        # In real implementation, this would query the database
        # For now, return None (no subscription found)
        return None
    
    async def _calculate_plan_amount(
        self,
        stream: RevenueStream,
        plan_tier: str
    ) -> float:
        """Calculate billing amount for a plan tier."""
        usage_limits = stream.usage_limits or {}
        tiers = usage_limits.get("tiers", [])
        
        for tier in tiers:
            if tier.get("name") == plan_tier:
                return tier.get("price", stream.base_amount)
        
        # Default to base amount
        return stream.base_amount
    
    async def _calculate_proration(
        self,
        stream: RevenueStream,
        old_plan: str,
        new_plan: str,
        effective_date: datetime
    ) -> float:
        """Calculate proration amount for plan change."""
        old_amount = await self._calculate_plan_amount(stream, old_plan)
        new_amount = await self._calculate_plan_amount(stream, new_plan)
        
        # Simple proration: difference in monthly amounts
        # In real implementation, this would consider remaining days in billing period
        proration = new_amount - old_amount
        
        return proration
    
    async def _calculate_refund(
        self,
        subscription: Dict[str, Any],
        stream: RevenueStream,
        effective_date: datetime
    ) -> float:
        """Calculate refund amount for subscription cancellation."""
        plan_amount = await self._calculate_plan_amount(stream, subscription["plan_tier"])
        
        # Simple refund calculation based on remaining days
        current_period_end = datetime.fromisoformat(subscription["current_period_end"])
        remaining_days = (current_period_end - effective_date).days
        
        if remaining_days <= 0:
            return 0.0
        
        # Daily rate calculation
        daily_rate = plan_amount / 30  # Assume 30-day month
        refund_amount = daily_rate * remaining_days
        
        return refund_amount
    
    async def _create_subscription_transaction(
        self,
        stream: RevenueStream,
        subscription: Dict[str, Any],
        amount: float,
        transaction_type: str
    ) -> RevenueTransaction:
        """Create a transaction for subscription operations."""
        transaction = await self.revenue_engine.process_transaction(
            revenue_stream_id=str(stream.id),
            amount=amount,
            customer_id=subscription["customer_id"],
            payment_method=subscription["payment_method"],
            metadata={
                "subscription_id": subscription["subscription_id"],
                "transaction_type": transaction_type,
                "plan_tier": subscription["plan_tier"],
                "billing_cycle": subscription["billing_cycle"]
            }
        )
        
        return transaction
    
    def _calculate_period_end(self, start_date: datetime, billing_cycle: str) -> datetime:
        """Calculate end date for billing period."""
        if billing_cycle == "daily":
            return start_date + timedelta(days=1)
        elif billing_cycle == "weekly":
            return start_date + timedelta(weeks=1)
        elif billing_cycle == "monthly":
            # Add one month (approximate)
            if start_date.month == 12:
                return datetime(start_date.year + 1, 1, start_date.day)
            else:
                return datetime(start_date.year, start_date.month + 1, start_date.day)
        elif billing_cycle == "quarterly":
            return start_date + timedelta(days=90)
        elif billing_cycle == "yearly":
            return start_date + timedelta(days=365)
        else:
            return start_date + timedelta(days=30)
    
    def _calculate_next_billing_date(self, current_date: datetime, billing_cycle: str) -> datetime:
        """Calculate next billing date."""
        return self._calculate_period_end(current_date, billing_cycle)
    
    async def get_subscription_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get subscription metrics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Subscription metrics
        """
        # Count subscriptions by status
        status_counts = {}
        total_subscriptions = len(self.subscription_cache)
        
        for subscription in self.subscription_cache.values():
            status = subscription["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate MRR (Monthly Recurring Revenue)
        mrr = 0.0
        active_subscriptions = 0
        
        for subscription in self.subscription_cache.values():
            if subscription["status"] == "active":
                active_subscriptions += 1
                # In real implementation, this would calculate based on plan amounts
                mrr += 29.99  # Placeholder average
        
        # Calculate churn rate
        churned_subscriptions = status_counts.get("cancelled", 0)
        churn_rate = (churned_subscriptions / total_subscriptions) if total_subscriptions > 0 else 0.0
        
        metrics = {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "subscriptions": {
                "total": total_subscriptions,
                "active": active_subscriptions,
                "cancelled": churned_subscriptions,
                "paused": status_counts.get("paused", 0),
                "trial": status_counts.get("trial", 0)
            },
            "revenue": {
                "monthly_recurring_revenue": mrr,
                "average_revenue_per_subscription": mrr / active_subscriptions if active_subscriptions > 0 else 0.0
            },
            "rates": {
                "churn_rate": churn_rate,
                "active_rate": (active_subscriptions / total_subscriptions) if total_subscriptions > 0 else 0.0
            }
        }
        
        return metrics
