"""
BaseLayer Income Engine API - Payment Providers

REST API endpoints for payment provider status and direct payment
processing (used by other engines/services, not typically end users).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from structlog import get_logger

from ...models.user import User
from ...core.auth import get_current_user
from ..providers import PaymentProviderManager
from ..exceptions import PaymentError

logger = get_logger(__name__)

router = APIRouter(prefix="/providers", tags=["Payment Providers"])

# Global instance (injected at startup - see main.py lifespan)
provider_manager: PaymentProviderManager = None


def get_provider_manager() -> PaymentProviderManager:
    """Get payment provider manager instance."""
    global provider_manager
    if not provider_manager:
        raise HTTPException(status_code=500, detail="Payment provider manager not initialized")
    return provider_manager


class ProcessPaymentRequest(BaseModel):
    amount: float
    currency: str
    payment_method_token: str
    provider_name: Optional[str] = None
    customer_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RefundPaymentRequest(BaseModel):
    transaction_id: str
    amount: Optional[float] = None
    reason: Optional[str] = None
    provider_name: Optional[str] = None


@router.get("/status", response_model=Dict[str, Any])
async def get_provider_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get status of all registered payment providers."""
    manager = get_provider_manager()
    return manager.get_provider_status()


@router.get("/payments/{transaction_id}", response_model=Dict[str, Any])
async def get_payment_status(
    transaction_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get the status of a previously processed payment."""
    manager = get_provider_manager()

    try:
        return await manager.get_payment_status(transaction_id)
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/payments", response_model=Dict[str, Any])
async def process_payment(
    request: ProcessPaymentRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Process a payment directly through a registered provider."""
    manager = get_provider_manager()

    try:
        result = await manager.process_payment(
            amount=request.amount,
            currency=request.currency,
            payment_method_token=request.payment_method_token,
            provider_name=request.provider_name,
            customer_id=request.customer_id,
            metadata=request.metadata,
        )

        logger.info(
            "Payment processed via API",
            amount=request.amount,
            currency=request.currency,
            user_id=str(current_user.id),
        )

        return result

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refunds", response_model=Dict[str, Any])
async def refund_payment(
    request: RefundPaymentRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Refund a payment, fully or partially."""
    manager = get_provider_manager()

    try:
        result = await manager.refund_payment(
            transaction_id=request.transaction_id,
            amount=request.amount,
            reason=request.reason,
            provider_name=request.provider_name,
        )

        logger.info(
            "Payment refunded via API",
            transaction_id=request.transaction_id,
            user_id=str(current_user.id),
        )

        return result

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))
