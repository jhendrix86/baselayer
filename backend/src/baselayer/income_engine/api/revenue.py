"""
BaseLayer Income Engine API - Revenue

REST API endpoints for revenue stream management and transactions.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import get_db_session, db_session_context
from ...models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, PricingModel, TransactionStatus
)
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import RevenueEngine
from ..exceptions import (
    RevenueEngineError,
    RevenueValidationError,
    RevenueComplianceError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/revenue", tags=["Revenue"])

# Global instances (will be injected in startup)
revenue_engine: RevenueEngine = None


def get_revenue_engine() -> RevenueEngine:
    """Get revenue engine instance."""
    global revenue_engine
    if not revenue_engine:
        raise HTTPException(status_code=500, detail="Revenue engine not initialized")
    return revenue_engine


@router.get("/streams", response_model=List[Dict[str, Any]])
async def list_revenue_streams(
    status: Optional[RevenueStatus] = Query(None),
    revenue_type: Optional[RevenueType] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List revenue streams with optional filtering.
    
    Args:
        status: Filter by status
        revenue_type: Filter by revenue type
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of revenue streams
    """
    engine = get_revenue_engine()
    
    streams = await engine.list_revenue_streams(
        status=status,
        revenue_type=revenue_type,
        limit=limit,
        offset=offset
    )
    
    return [stream.to_dict() for stream in streams]


@router.get("/streams/{stream_id}", response_model=Dict[str, Any])
async def get_revenue_stream(
    stream_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific revenue stream.
    
    Args:
        stream_id: Revenue stream ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Revenue stream details
    """
    engine = get_revenue_engine()
    
    stream = await engine.get_revenue_stream(stream_id)
    
    if not stream:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    
    return stream.to_dict()


@router.post("/streams", response_model=Dict[str, Any])
async def create_revenue_stream(
    stream_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new revenue stream.
    
    Args:
        stream_data: Revenue stream data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created revenue stream
    """
    engine = get_revenue_engine()
    
    try:
        stream = await engine.create_revenue_stream(
            name=stream_data["name"],
            description=stream_data.get("description"),
            revenue_type=RevenueType(stream_data["revenue_type"]),
            pricing_model=PricingModel(stream_data["pricing_model"]),
            base_amount=stream_data["base_amount"],
            currency=stream_data.get("currency", "USD"),
            billing_cycle=stream_data.get("billing_cycle"),
            usage_limits=stream_data.get("usage_limits"),
            created_by=current_user.id
        )
        
        logger.info(
            "Revenue stream created via API",
            stream_id=str(stream.id),
            stream_name=stream.name,
            user_id=str(current_user.id)
        )
        
        return stream.to_dict()
        
    except (RevenueValidationError, RevenueComplianceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RevenueEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/streams/{stream_id}", response_model=Dict[str, Any])
async def update_revenue_stream(
    stream_id: str,
    stream_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update a revenue stream.
    
    Args:
        stream_id: Revenue stream ID
        stream_data: Updated stream data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Updated revenue stream
    """
    try:
        stream_uuid = uuid.UUID(stream_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stream ID")
    
    result = await db.execute(
        select(RevenueStream).where(
            RevenueStream.id == stream_uuid,
            RevenueStream.deleted_at.is_(None)
        )
    )
    stream = result.scalar_one_or_none()
    
    if not stream:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    
    # Check permissions
    if not current_user.is_admin and stream.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this stream")
    
    # Update fields
    if "name" in stream_data:
        stream.name = stream_data["name"]
    
    if "description" in stream_data:
        stream.description = stream_data["description"]
    
    if "base_amount" in stream_data:
        stream.base_amount = stream_data["base_amount"]
    
    if "currency" in stream_data:
        stream.currency = stream_data["currency"]
    
    if "billing_cycle" in stream_data:
        stream.billing_cycle = stream_data["billing_cycle"]
    
    if "usage_limits" in stream_data:
        stream.usage_limits = stream_data["usage_limits"]
    
    if "status" in stream_data:
        stream.status = RevenueStatus(stream_data["status"])
    
    stream.updated_by = current_user.id
    stream.increment_version()
    
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    
    logger.info(
        "Revenue stream updated via API",
        stream_id=str(stream.id),
        stream_name=stream.name,
        user_id=str(current_user.id)
    )
    
    return stream.to_dict()


@router.delete("/streams/{stream_id}", response_model=Dict[str, Any])
async def delete_revenue_stream(
    stream_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a revenue stream (soft delete).
    
    Args:
        stream_id: Revenue stream ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    engine = get_revenue_engine()
    
    success = await engine.deactivate_revenue_stream(stream_id, "API deletion")
    
    if not success:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    
    logger.info(
        "Revenue stream deleted via API",
        stream_id=stream_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Revenue stream deactivated successfully"}


@router.post("/transactions", response_model=Dict[str, Any])
async def create_transaction(
    transaction_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a revenue transaction.
    
    Args:
        transaction_data: Transaction data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created transaction
    """
    engine = get_revenue_engine()
    
    try:
        transaction = await engine.process_transaction(
            revenue_stream_id=transaction_data["revenue_stream_id"],
            amount=transaction_data["amount"],
            customer_id=transaction_data.get("customer_id"),
            payment_method=transaction_data.get("payment_method"),
            metadata=transaction_data.get("metadata"),
            created_by=current_user.id
        )
        
        logger.info(
            "Transaction created via API",
            transaction_id=transaction.transaction_id,
            revenue_stream_id=transaction_data["revenue_stream_id"],
            amount=transaction.amount,
            user_id=str(current_user.id)
        )
        
        return transaction.to_dict()
        
    except RevenueEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=List[Dict[str, Any]])
async def list_transactions(
    stream_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    status: Optional[TransactionStatus] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List transactions with optional filtering.
    
    Args:
        stream_id: Filter by revenue stream ID
        customer_id: Filter by customer ID
        status: Filter by transaction status
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of transactions
    """
    query = select(RevenueTransaction).where(RevenueTransaction.deleted_at.is_(None))
    
    if stream_id:
        try:
            stream_uuid = uuid.UUID(stream_id)
            query = query.where(RevenueTransaction.revenue_stream_id == stream_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid stream ID")
    
    if customer_id:
        query = query.where(RevenueTransaction.customer_id == customer_id)
    
    if status:
        query = query.where(RevenueTransaction.status == status)
    
    query = query.order_by(RevenueTransaction.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    return [transaction.to_dict() for transaction in transactions]


@router.get("/transactions/{transaction_id}", response_model=Dict[str, Any])
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific transaction.
    
    Args:
        transaction_id: Transaction ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Transaction details
    """
    result = await db.execute(
        select(RevenueTransaction).where(
            RevenueTransaction.transaction_id == transaction_id,
            RevenueTransaction.deleted_at.is_(None)
        )
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction.to_dict()


@router.get("/metrics", response_model=Dict[str, Any])
async def get_revenue_metrics(
    stream_id: str,
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get revenue metrics for a stream.
    
    Args:
        stream_id: Revenue stream ID
        period_start: Start of period
        period_end: End of period
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Revenue metrics
    """
    engine = get_revenue_engine()
    
    try:
        metrics = await engine.get_revenue_metrics(stream_id, period_start, period_end)
        
        return {
            "stream_id": stream_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "metrics": [metric.to_dict() for metric in metrics]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", response_model=Dict[str, Any])
async def get_revenue_overview(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    group_by: str = Query("day", regex="^(day|week|month)$"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get revenue overview for a period.
    
    Args:
        period_start: Start of period
        period_end: End of period
        group_by: Grouping level
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Revenue overview
    """
    from ..analytics import RevenueAnalytics
    
    analytics = RevenueAnalytics()
    
    try:
        overview = await analytics.get_revenue_overview(
            period_start=period_start,
            period_end=period_end,
            group_by=group_by
        )
        
        return overview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-stream", response_model=List[Dict[str, Any]])
async def get_revenue_by_stream(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get revenue breakdown by stream.
    
    Args:
        period_start: Start of period
        period_end: End of period
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Revenue by stream
    """
    from ..analytics import RevenueAnalytics
    
    analytics = RevenueAnalytics()
    
    try:
        stream_revenue = await analytics.get_revenue_by_stream(
            period_start=period_start,
            period_end=period_end
        )
        
        return stream_revenue
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", response_model=Dict[str, Any])
async def get_revenue_trends(
    period_start: datetime = Query(...),
    period_end: datetime = Query(...),
    comparison_period: str = Query("previous_period", regex="^(previous_period|previous_year)$"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get revenue trends with comparisons.
    
    Args:
        period_start: Start of period
        period_end: End of period
        comparison_period: Comparison period type
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Revenue trends
    """
    from ..analytics import RevenueAnalytics
    
    analytics = RevenueAnalytics()
    
    try:
        trends = await analytics.get_revenue_trends(
            period_start=period_start,
            period_end=period_end,
            comparison_period=comparison_period
        )
        
        return trends
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/streams/{stream_id}/activate", response_model=Dict[str, Any])
async def activate_revenue_stream(
    stream_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Activate a revenue stream.
    
    Args:
        stream_id: Revenue stream ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Activation result
    """
    engine = get_revenue_engine()
    
    stream = await engine.get_revenue_stream(stream_id)
    
    if not stream:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    
    if stream.status == RevenueStatus.ACTIVE:
        return {"message": "Revenue stream is already active"}
    
    # Update status
    async with db_session_context() as db:
        stream.status = RevenueStatus.ACTIVE
        stream.updated_by = current_user.id
        db.add(stream)
        await db.commit()
    
    # Update cache
    engine.active_streams[stream_id] = stream
    
    logger.info(
        "Revenue stream activated via API",
        stream_id=stream_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Revenue stream activated successfully"}


@router.post("/streams/{stream_id}/deactivate", response_model=Dict[str, Any])
async def deactivate_revenue_stream(
    stream_id: str,
    reason: str = Query("Manual deactivation"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Deactivate a revenue stream.
    
    Args:
        stream_id: Revenue stream ID
        reason: Deactivation reason
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deactivation result
    """
    engine = get_revenue_engine()
    
    success = await engine.deactivate_revenue_stream(stream_id, reason)
    
    if not success:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    
    logger.info(
        "Revenue stream deactivated via API",
        stream_id=stream_id,
        reason=reason,
        user_id=str(current_user.id)
    )
    
    return {"message": "Revenue stream deactivated successfully"}
