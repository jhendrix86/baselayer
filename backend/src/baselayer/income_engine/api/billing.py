"""
BaseLayer Income Engine API - Billing

REST API endpoints for the automated billing engine: manual billing runs,
billing summaries, and payment retries.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from structlog import get_logger

from ...models.user import User
from ...core.auth import get_current_user
from ..billing import BillingEngine
from ..exceptions import BillingError

logger = get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])

# Global instance (injected at startup - see main.py lifespan)
billing_engine: BillingEngine = None


def get_billing_engine() -> BillingEngine:
    """Get billing engine instance."""
    global billing_engine
    if not billing_engine:
        raise HTTPException(status_code=500, detail="Billing engine not initialized")
    return billing_engine


class ManualBillingRequest(BaseModel):
    stream_id: str
    customer_ids: List[str]
    amount: Optional[float] = None


@router.post("/manual", response_model=List[Dict[str, Any]])
async def process_manual_billing(
    request: ManualBillingRequest,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Process manual billing for specific customers on a revenue stream."""
    engine = get_billing_engine()

    try:
        transactions = await engine.process_manual_billing(
            stream_id=request.stream_id,
            customer_ids=request.customer_ids,
            amount=request.amount,
        )

        logger.info(
            "Manual billing processed via API",
            stream_id=request.stream_id,
            customer_count=len(request.customer_ids),
            user_id=str(current_user.id),
        )

        return [transaction.to_dict() for transaction in transactions]

    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=Dict[str, Any])
async def get_billing_summary(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a billing summary (revenue, transaction counts, failures) for a period."""
    engine = get_billing_engine()

    try:
        return await engine.get_billing_summary(period_start, period_end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-failed", response_model=Dict[str, Any])
async def retry_failed_payments(
    max_retries: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retry failed payments up to a maximum retry count."""
    engine = get_billing_engine()

    try:
        result = await engine.retry_failed_payments(max_retries=max_retries)

        logger.info(
            "Failed payment retry run via API",
            user_id=str(current_user.id),
            **result,
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
