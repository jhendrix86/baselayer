"""
BaseLayer Income Engine API - Subscriptions

REST API endpoints for subscription lifecycle management: create, change
plan, cancel, pause, resume, and query subscriptions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from structlog import get_logger

from ...models.user import User
from ...core.auth import get_current_user
from ..subscriptions import SubscriptionManager
from ..exceptions import SubscriptionError

logger = get_logger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# Global instance (injected at startup - see main.py lifespan)
subscription_manager: SubscriptionManager = None


def get_subscription_manager() -> SubscriptionManager:
    """Get subscription manager instance."""
    global subscription_manager
    if not subscription_manager:
        raise HTTPException(status_code=500, detail="Subscription manager not initialized")
    return subscription_manager


class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    stream_id: str
    plan_tier: str
    billing_cycle: str
    payment_method: str
    trial_days: int = 0
    metadata: Optional[Dict[str, Any]] = None


class CancelSubscriptionRequest(BaseModel):
    reason: str = "Customer request"
    effective_date: Optional[datetime] = None
    refund_pro_rated: bool = False


class PauseSubscriptionRequest(BaseModel):
    reason: str = "Customer request"
    pause_duration_days: int = 30


@router.post("", response_model=Dict[str, Any])
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new subscription for a customer on a revenue stream."""
    manager = get_subscription_manager()

    try:
        subscription = await manager.create_subscription(
            customer_id=request.customer_id,
            stream_id=request.stream_id,
            plan_tier=request.plan_tier,
            billing_cycle=request.billing_cycle,
            payment_method=request.payment_method,
            trial_days=request.trial_days,
            metadata=request.metadata,
            created_by=current_user.id,
        )

        logger.info(
            "Subscription created via API",
            subscription_id=subscription["subscription_id"],
            user_id=str(current_user.id),
        )

        return subscription

    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{customer_id}/{stream_id}", response_model=Dict[str, Any])
async def get_subscription(
    customer_id: str,
    stream_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a customer's subscription details for a stream."""
    manager = get_subscription_manager()

    subscription = await manager.get_subscription(customer_id, stream_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return subscription


@router.get("/{customer_id}", response_model=List[Dict[str, Any]])
async def list_customer_subscriptions(
    customer_id: str,
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List all subscriptions for a customer."""
    manager = get_subscription_manager()

    return await manager.list_customer_subscriptions(customer_id, status=status)


@router.post("/{customer_id}/{stream_id}/cancel", response_model=Dict[str, Any])
async def cancel_subscription(
    customer_id: str,
    stream_id: str,
    request: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cancel a subscription, with optional pro-rated refund."""
    manager = get_subscription_manager()

    try:
        result = await manager.cancel_subscription(
            customer_id=customer_id,
            stream_id=stream_id,
            reason=request.reason,
            effective_date=request.effective_date,
            refund_pro_rated=request.refund_pro_rated,
        )

        logger.info(
            "Subscription cancelled via API",
            customer_id=customer_id,
            stream_id=stream_id,
            user_id=str(current_user.id),
        )

        return result

    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{customer_id}/{stream_id}/pause", response_model=Dict[str, Any])
async def pause_subscription(
    customer_id: str,
    stream_id: str,
    request: PauseSubscriptionRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Pause a subscription for a period."""
    manager = get_subscription_manager()

    try:
        return await manager.pause_subscription(
            customer_id=customer_id,
            stream_id=stream_id,
            reason=request.reason,
            pause_duration_days=request.pause_duration_days,
        )
    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{customer_id}/{stream_id}/resume", response_model=Dict[str, Any])
async def resume_subscription(
    customer_id: str,
    stream_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Resume a paused subscription."""
    manager = get_subscription_manager()

    try:
        return await manager.resume_subscription(customer_id=customer_id, stream_id=stream_id)
    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_subscription_metrics(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get subscription metrics (MRR, churn, etc.) for a period."""
    manager = get_subscription_manager()

    try:
        return await manager.get_subscription_metrics(period_start, period_end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
