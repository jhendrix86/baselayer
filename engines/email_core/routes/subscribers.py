"""
EMAIL_CORE Subscriber API Routes

FastAPI routes for subscriber management,
segmentation, and analytics with JWT protection.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError
from baselayer.core.middleware import success_response, error_response

from ..models.subscriber import Subscriber, SubscriberStatus, SubscriberSource
from ..models.schemas import (
    SubscriberCreate, SubscriberUpdate, SubscriberResponse, SubscriberListResponse,
    SubscriberStatsResponse, SegmentationRequest, BulkOperationRequest
)
from ..subscriber_manager import SubscriberManager
from ...core.dependencies import get_db_session, get_current_user, get_redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/subscribers", tags=["subscribers"])


@router.post("/", response_model=SubscriberResponse)
async def create_subscriber(
    subscriber_data: SubscriberCreate,
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> SubscriberResponse:
    """Create a new subscriber."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        subscriber = await subscriber_manager.add_subscriber(
            email=subscriber_data.email,
            first_name=subscriber_data.first_name,
            last_name=subscriber_data.last_name,
            source=subscriber_data.source,
            tags=subscriber_data.tags,
            lead_magnet_id=subscriber_data.lead_magnet_id,
            metadata=subscriber_data.metadata,
            custom_attributes=subscriber_data.custom_attributes,
            list_ids=subscriber_data.list_ids
        )
        
        logger.info("Subscriber created", 
                   subscriber_id=str(subscriber.id),
                   email=subscriber.email)
        
        return success_response(
            data=subscriber.to_dict(),
            message="Subscriber created successfully"
        )
        
    except BaseLayerError as e:
        logger.error("Failed to create subscriber", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error creating subscriber", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{subscriber_id}", response_model=SubscriberResponse)
async def get_subscriber(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SubscriberResponse:
    """Get subscriber by ID."""
    try:
        subscriber_manager = SubscriberManager(db)
        
        subscriber = await subscriber_manager.get_subscriber_by_id(subscriber_id)
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscriber not found"
            )
        
        return success_response(
            data=subscriber.to_dict(),
            message="Subscriber retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=SubscriberListResponse)
async def list_subscribers(
    status: Optional[SubscriberStatus] = Query(None),
    source: Optional[SubscriberSource] = Query(None),
    tags: Optional[List[str]] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("subscribed_at", regex="^(subscribed_at|email|first_name|email_count|open_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SubscriberListResponse:
    """List subscribers with filtering and pagination."""
    try:
        subscriber_manager = SubscriberManager(db)
        
        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if source:
            filters["source"] = source
        if tags:
            filters["tags"] = tags
        
        # Get subscribers
        subscribers = await subscriber_manager.segment_subscribers(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        # Apply search if provided
        if search:
            subscribers = [s for s in subscribers if search.lower() in s.email.lower() or 
                          (s.first_name and search.lower() in s.first_name.lower()) or
                          (s.last_name and search.lower() in s.last_name.lower())]
        
        # Sort results
        if sort_by == "subscribed_at":
            subscribers.sort(key=lambda x: x.subscribed_at or datetime.min, reverse=(sort_order == "desc"))
        elif sort_by == "email":
            subscribers.sort(key=lambda x: x.email.lower(), reverse=(sort_order == "desc"))
        elif sort_by == "first_name":
            subscribers.sort(key=lambda x: x.first_name or "", reverse=(sort_order == "desc"))
        elif sort_by == "email_count":
            subscribers.sort(key=lambda x: x.email_count, reverse=(sort_order == "desc"))
        elif sort_by == "open_count":
            subscribers.sort(key=lambda x: x.open_count, reverse=(sort_order == "desc"))
        
        # Get total count
        total_count = len(subscribers)
        
        return success_response(
            data={
                "subscribers": [sub.to_dict() for sub in subscribers],
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Subscribers retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to list subscribers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{subscriber_id}", response_model=SubscriberResponse)
async def update_subscriber(
    subscriber_id: uuid.UUID,
    subscriber_data: SubscriberUpdate,
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> SubscriberResponse:
    """Update subscriber information."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        subscriber = await subscriber_manager.update_subscriber(
            subscriber_id=subscriber_id,
            first_name=subscriber_data.first_name,
            last_name=subscriber_data.last_name,
            tags=subscriber_data.tags,
            metadata=subscriber_data.metadata,
            custom_attributes=subscriber_data.custom_attributes,
            timezone=subscriber_data.timezone,
            language=subscriber_data.language
        )
        
        logger.info("Subscriber updated", subscriber_id=str(subscriber_id))
        
        return success_response(
            data=subscriber.to_dict(),
            message="Subscriber updated successfully"
        )
        
    except BaseLayerError as e:
        logger.error("Failed to update subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error updating subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{subscriber_id}")
async def delete_subscriber(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete subscriber (GDPR compliance)."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        success = await subscriber_manager.delete_subscriber(subscriber_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscriber not found"
            )
        
        logger.info("Subscriber deleted", subscriber_id=str(subscriber_id))
        
        return success_response(
            data={"deleted": True},
            message="Subscriber deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{subscriber_id}/unsubscribe")
async def unsubscribe_subscriber(
    subscriber_id: uuid.UUID,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Unsubscribe subscriber."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        subscriber = await subscriber_manager.unsubscribe_subscriber(
            subscriber_id=subscriber_id,
            reason=reason
        )
        
        logger.info("Subscriber unsubscribed", 
                   subscriber_id=str(subscriber_id),
                   reason=reason)
        
        return success_response(
            data=subscriber.to_dict(),
            message="Subscriber unsubscribed successfully"
        )
        
    except BaseLayerError as e:
        logger.error("Failed to unsubscribe subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error unsubscribing subscriber", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{subscriber_id}/tags")
async def manage_subscriber_tags(
    subscriber_id: uuid.UUID,
    operation: str = Query(..., regex="^(add|remove|replace)$"),
    tags: List[str] = Query(...),
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Manage subscriber tags."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        subscriber = await subscriber_manager.tag_subscriber(
            subscriber_id=subscriber_id,
            tags=tags,
            operation=operation
        )
        
        logger.info("Subscriber tags updated", 
                   subscriber_id=str(subscriber_id),
                   operation=operation,
                   tags=tags)
        
        return success_response(
            data=subscriber.to_dict(),
            message=f"Tags {operation}ed successfully"
        )
        
    except BaseLayerError as e:
        logger.error("Failed to manage subscriber tags", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error managing subscriber tags", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/segment")
async def segment_subscribers(
    segmentation: SegmentationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Segment subscribers based on filters."""
    try:
        subscriber_manager = SubscriberManager(db)
        
        subscribers = await subscriber_manager.segment_subscribers(
            filters=segmentation.filters,
            limit=segmentation.limit,
            offset=segmentation.offset
        )
        
        return success_response(
            data={
                "subscribers": [sub.to_dict() for sub in subscribers],
                "total": len(subscribers),
                "filters": segmentation.filters
            },
            message="Subscribers segmented successfully"
        )
        
    except Exception as e:
        logger.error("Failed to segment subscribers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{subscriber_id}/stats", response_model=SubscriberStatsResponse)
async def get_subscriber_stats(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SubscriberStatsResponse:
    """Get subscriber statistics and analytics."""
    try:
        subscriber_manager = SubscriberManager(db)
        
        stats = await subscriber_manager.get_subscriber_stats(subscriber_id)
        
        return success_response(
            data=stats,
            message="Subscriber stats retrieved successfully"
        )
        
    except BaseLayerError as e:
        logger.error("Failed to get subscriber stats", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error getting subscriber stats", subscriber_id=str(subscriber_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/bulk")
async def bulk_operations(
    operation: BulkOperationRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Perform bulk operations on subscribers."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        results = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        subscriber_ids = operation.subscriber_ids
        
        for subscriber_id in subscriber_ids:
            try:
                results["processed"] += 1
                
                if operation.operation == "unsubscribe":
                    await subscriber_manager.unsubscribe_subscriber(subscriber_id)
                elif operation.operation == "add_tags":
                    await subscriber_manager.tag_subscriber(
                        subscriber_id, operation.tags or [], "add"
                    )
                elif operation.operation == "remove_tags":
                    await subscriber_manager.tag_subscriber(
                        subscriber_id, operation.tags or [], "remove"
                    )
                elif operation.operation == "delete":
                    await subscriber_manager.delete_subscriber(subscriber_id)
                else:
                    raise ValueError(f"Unknown operation: {operation.operation}")
                
                results["success"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Subscriber {subscriber_id}: {str(e)}")
        
        logger.info("Bulk operation completed", 
                   operation=operation.operation,
                   processed=results["processed"],
                   success=results["success"])
        
        return success_response(
            data=results,
            message=f"Bulk {operation.operation} completed"
        )
        
    except Exception as e:
        logger.error("Failed to perform bulk operation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/sync-breveo")
async def sync_with_brevo(
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Sync subscribers with Brevo API."""
    try:
        subscriber_manager = SubscriberManager(db, redis_client=redis_client)
        
        sync_results = await subscriber_manager.bulk_sync_with_brevo(limit)
        
        logger.info("Brevo sync completed", sync_results=sync_results)
        
        return success_response(
            data=sync_results,
            message="Brevo sync completed"
        )
        
    except Exception as e:
        logger.error("Failed to sync with Brevo", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/export/csv")
async def export_subscribers_csv(
    status: Optional[SubscriberStatus] = Query(None),
    tags: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Export subscribers to CSV format."""
    try:
        subscriber_manager = SubscriberManager(db)
        
        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if tags:
            filters["tags"] = tags
        
        # Get subscribers
        subscribers = await subscriber_manager.segment_subscribers(filters=filters)
        
        # Convert to CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "id", "email", "first_name", "last_name", "status", "source",
            "subscribed_at", "email_count", "open_count", "click_count",
            "engagement_rate", "tags"
        ])
        
        # Data rows
        for subscriber in subscribers:
            writer.writerow([
                str(subscriber.id),
                subscriber.email,
                subscriber.first_name or "",
                subscriber.last_name or "",
                subscriber.status,
                subscriber.source,
                subscriber.subscribed_at.isoformat() if subscriber.subscribed_at else "",
                subscriber.email_count,
                subscriber.open_count,
                subscriber.click_count,
                f"{subscriber.engagement_rate:.2f}%",
                ",".join(subscriber.tags or [])
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return success_response(
            data={
                "csv_content": csv_content,
                "filename": f"subscribers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "count": len(subscribers)
            },
            message="Subscribers exported successfully"
        )
        
    except Exception as e:
        logger.error("Failed to export subscribers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
