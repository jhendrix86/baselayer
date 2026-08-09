"""
BaseLayer Income Engine API - Analytics

REST API endpoints for customer analytics, revenue forecasting, and
performance metrics. Revenue overview/by-stream/trends live in revenue.py;
this covers the rest of RevenueAnalytics' surface.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from structlog import get_logger

from ...models.user import User
from ...core.auth import get_current_user
from ..analytics import RevenueAnalytics
from ..exceptions import AnalyticsError

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Revenue Analytics"])


@router.get("/customers", response_model=List[Dict[str, Any]])
async def get_customer_analytics(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get per-customer revenue analytics for a period."""
    analytics = RevenueAnalytics()

    try:
        return await analytics.get_customer_analytics(period_start, period_end, limit=limit)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=Dict[str, Any])
async def forecast_revenue(
    stream_id: Optional[str] = Query(None),
    forecast_period: int = Query(30, ge=1, le=365),
    model_type: str = Query("linear_regression"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Forecast revenue for the next N days, optionally scoped to one stream."""
    analytics = RevenueAnalytics()

    try:
        return await analytics.forecast_revenue(
            stream_id=stream_id,
            forecast_period=forecast_period,
            model_type=model_type,
        )
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_metrics(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get overall performance metrics for revenue operations."""
    analytics = RevenueAnalytics()

    try:
        return await analytics.get_performance_metrics(period_start, period_end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
