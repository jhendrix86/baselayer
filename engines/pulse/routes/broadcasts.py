"""
PULSE Broadcast API Routes

FastAPI routes for broadcast and newsletter management,
scheduling, and analytics with JWT protection.
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

from ..models.broadcast import Broadcast, BroadcastStatus, BroadcastType
from ..models.schemas import (
    BroadcastCreate, BroadcastUpdate, BroadcastResponse, BroadcastListResponse,
    BroadcastSendRequest, BroadcastScheduleRequest, BroadcastStatsResponse
)
from ..agents.broadcast_writer import BroadcastWriter
from ..agents.broadcast_sender import BroadcastSender
from ..scheduler import BroadcastScheduler
from ...core.dependencies import get_db_session, get_current_user, get_redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])


@router.post("/", response_model=BroadcastResponse)
async def create_broadcast(
    broadcast_data: BroadcastCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> BroadcastResponse:
    """Create a new broadcast."""
    try:
        # Create broadcast
        broadcast = Broadcast(
            name=broadcast_data.name,
            subject=broadcast_data.subject,
            preview_text=broadcast_data.preview_text,
            description=broadcast_data.description,
            content_md=broadcast_data.content_md,
            content_html=broadcast_data.content_html,
            content_text=broadcast_data.content_text,
            broadcast_type=broadcast_data.broadcast_type,
            template_name=broadcast_data.template_name,
            segment_filters=broadcast_data.segment_filters,
            exclusion_filters=broadcast_data.exclusion_filters,
            sender_name=broadcast_data.sender_name,
            sender_email=broadcast_data.sender_email,
            reply_to_email=broadcast_data.reply_to_email,
            campaign_name=broadcast_data.campaign_name,
            campaign_tags=broadcast_data.campaign_tags,
            send_timezone=broadcast_data.send_timezone,
            send_time_start=broadcast_data.send_time_start,
            send_time_end=broadcast_data.send_time_end,
            send_on_weekends=broadcast_data.send_on_weekends,
            send_rate_limit=broadcast_data.send_rate_limit,
            batch_size=broadcast_data.batch_size,
            created_by=current_user.get("id") if current_user else None
        )
        
        # Calculate word count and reading time
        broadcast.word_count = len(broadcast_data.content_md.split())
        broadcast.reading_time_minutes = max(1, broadcast.word_count // 200)
        
        # Validate content
        validation_errors = broadcast.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Broadcast validation failed: {', '.join(validation_errors)}"
            )
        
        db.add(broadcast)
        await db.commit()
        
        logger.info("Broadcast created", 
                   broadcast_id=str(broadcast.id),
                   name=broadcast.name)
        
        return success_response(
            data=broadcast.to_dict(),
            message="Broadcast created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create broadcast", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=BroadcastListResponse)
async def list_broadcasts(
    status: Optional[BroadcastStatus] = Query(None),
    broadcast_type: Optional[BroadcastType] = Query(None),
    campaign_name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|sent_at|name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> BroadcastListResponse:
    """List broadcasts with filtering and pagination."""
    try:
        stmt = select(Broadcast)
        
        # Apply filters
        if status:
            stmt = stmt.where(Broadcast.status == status)
        if broadcast_type:
            stmt = stmt.where(Broadcast.broadcast_type == broadcast_type)
        if campaign_name:
            stmt = stmt.where(Broadcast.campaign_name == campaign_name)
        if search:
            stmt = stmt.where(
                or_(
                    Broadcast.name.ilike(f"%{search}%"),
                    Broadcast.subject.ilike(f"%{search}%"),
                    Broadcast.description.ilike(f"%{search}%")
                )
            )
        
        # Apply sorting
        if sort_by == "created_at":
            stmt = stmt.order_by(
                Broadcast.created_at.desc() if sort_order == "desc" else Broadcast.created_at.asc()
            )
        elif sort_by == "updated_at":
            stmt = stmt.order_by(
                Broadcast.updated_at.desc() if sort_order == "desc" else Broadcast.updated_at.asc()
            )
        elif sort_by == "sent_at":
            stmt = stmt.order_by(
                Broadcast.sent_at.desc().nulls_last() if sort_order == "desc" else Broadcast.sent_at.asc().nulls_first()
            )
        elif sort_by == "name":
            stmt = stmt.order_by(
                Broadcast.name.desc() if sort_order == "desc" else Broadcast.name.asc()
            )
        
        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        broadcasts = result.scalars().all()
        
        # Get total count
        count_stmt = select(Broadcast)
        if status:
            count_stmt = count_stmt.where(Broadcast.status == status)
        if broadcast_type:
            count_stmt = count_stmt.where(Broadcast.broadcast_type == broadcast_type)
        if campaign_name:
            count_stmt = count_stmt.where(Broadcast.campaign_name == campaign_name)
        if search:
            count_stmt = count_stmt.where(
                or_(
                    Broadcast.name.ilike(f"%{search}%"),
                    Broadcast.subject.ilike(f"%{search}%"),
                    Broadcast.description.ilike(f"%{search}%")
                )
            )
        
        count_result = await db.execute(count_stmt)
        total_count = len(count_result.scalars().all())
        
        return success_response(
            data={
                "broadcasts": [broadcast.to_dict() for broadcast in broadcasts],
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Broadcasts retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to list broadcasts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{broadcast_id}", response_model=BroadcastResponse)
async def get_broadcast(
    broadcast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> BroadcastResponse:
    """Get broadcast by ID."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        return success_response(
            data=broadcast.to_dict(),
            message="Broadcast retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get broadcast", broadcast_id=str(broadcast_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{broadcast_id}", response_model=BroadcastResponse)
async def update_broadcast(
    broadcast_id: uuid.UUID,
    broadcast_data: BroadcastUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> BroadcastResponse:
    """Update broadcast information."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Check if broadcast can be updated
        if broadcast.is_sent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update sent broadcast"
            )
        
        # Update fields
        if broadcast_data.name is not None:
            broadcast.name = broadcast_data.name
        if broadcast_data.subject is not None:
            broadcast.subject = broadcast_data.subject
        if broadcast_data.preview_text is not None:
            broadcast.preview_text = broadcast_data.preview_text
        if broadcast_data.description is not None:
            broadcast.description = broadcast_data.description
        if broadcast_data.content_md is not None:
            broadcast.update_content(
                broadcast.subject or broadcast.subject,
                broadcast_data.content_md,
                broadcast.content_html or broadcast.content_html,
                current_user.get("id") if current_user else None
            )
        if broadcast_data.segment_filters is not None:
            broadcast.segment_filters = broadcast_data.segment_filters
        if broadcast_data.exclusion_filters is not None:
            broadcast.exclusion_filters = broadcast_data.exclusion_filters
        if broadcast_data.sender_name is not None:
            broadcast.sender_name = broadcast_data.sender_name
        if broadcast_data.sender_email is not None:
            broadcast.sender_email = broadcast_data.sender_email
        if broadcast_data.reply_to_email is not None:
            broadcast.reply_to_email = broadcast_data.reply_to_email
        if broadcast_data.campaign_name is not None:
            broadcast.campaign_name = broadcast_data.campaign_name
        if broadcast_data.campaign_tags is not None:
            broadcast.campaign_tags = broadcast_data.campaign_tags
        
        broadcast.last_modified_by = current_user.get("id") if current_user else None
        
        # Validate content if updated
        if broadcast_data.content_md is not None:
            validation_errors = broadcast.validate_content()
            if validation_errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Broadcast validation failed: {', '.join(validation_errors)}"
                )
        
        await db.commit()
        
        logger.info("Broadcast updated", broadcast_id=str(broadcast_id))
        
        return success_response(
            data=broadcast.to_dict(),
            message="Broadcast updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update broadcast", broadcast_id=str(broadcast_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{broadcast_id}")
async def delete_broadcast(
    broadcast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete broadcast."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Check if broadcast can be deleted
        if broadcast.is_sent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete sent broadcast"
            )
        
        await db.delete(broadcast)
        await db.commit()
        
        logger.info("Broadcast deleted", broadcast_id=str(broadcast_id))
        
        return success_response(
            data={"deleted": True},
            message="Broadcast deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete broadcast", broadcast_id=str(broadcast_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id: uuid.UUID,
    send_request: BroadcastSendRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Send broadcast immediately."""
    try:
        # Get broadcast
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Check if broadcast can be sent
        if broadcast.is_sent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Broadcast already sent"
            )
        
        # Validate broadcast content
        validation_errors = broadcast.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot send broadcast with validation errors: {', '.join(validation_errors)}"
            )
        
        # Send broadcast
        sender = BroadcastSender(db_session=db, redis_client=redis_client)
        
        sender_input = {
            "broadcast_id": str(broadcast_id),
            "send_immediately": True,
            "test_mode": send_request.test_mode
        }
        
        from agents.core.context import AgentContext, AgentConfig
        sender_context = AgentContext(
            task_id=str(uuid.uuid4()),
            task_type="broadcast_sending",
            input_data=sender_input,
            memory_interface=None,
            config=AgentConfig(),
            request_id=str(uuid.uuid4())
        )
        
        sender_plan = await sender.plan(sender_input)
        send_results = await sender.execute(sender_plan)
        
        logger.info("Broadcast sent", 
                   broadcast_id=str(broadcast_id),
                   sent_count=send_results.get("sent_count", 0))
        
        return success_response(
            data=send_results,
            message="Broadcast sent successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send broadcast", broadcast_id=str(broadcast_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{broadcast_id}/schedule")
async def schedule_broadcast(
    broadcast_id: uuid.UUID,
    schedule_request: BroadcastScheduleRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Schedule broadcast for future sending."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Check if broadcast can be scheduled
        if broadcast.is_sent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot schedule sent broadcast"
            )
        
        # Validate broadcast content
        validation_errors = broadcast.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot schedule broadcast with validation errors: {', '.join(validation_errors)}"
            )
        
        # Schedule broadcast
        send_time = datetime.fromisoformat(schedule_request.send_time.replace('Z', '+00:00'))
        broadcast.schedule(send_time, current_user.get("id") if current_user else None)
        
        await db.commit()
        
        logger.info("Broadcast scheduled", 
                   broadcast_id=str(broadcast_id),
                   send_time=send_time.isoformat())
        
        return success_response(
            data=broadcast.to_dict(),
            message="Broadcast scheduled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to schedule broadcast", broadcast_id=str(broadcast_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{broadcast_id}/unschedule")
async def unschedule_broadcast(
    broadcast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Unschedule broadcast."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        if not broadcast.is_scheduled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Broadcast is not scheduled"
            )
        
        broadcast.unschedule()
        await db.commit()
        
        logger.info("Broadcast unscheduled", broadcast_id=str(broadcast_id))
        
        return success_response(
            data=broadcast.to_dict(),
            message="Broadcast unscheduled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unschedule broadcast", broadcast_id=str(broadcast_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{broadcast_id}/generate")
async def generate_broadcast_content(
    broadcast_id: uuid.UUID,
    content_request: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Generate broadcast content using AI."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Generate content
        writer = BroadcastWriter()
        
        writer_input = {
            "name": broadcast.name,
            "type": broadcast.broadcast_type,
            "audience": content_request.get("audience", "general subscribers"),
            "primary_topic": content_request.get("primary_topic", ""),
            "secondary_topics": content_request.get("secondary_topics", []),
            "goals": content_request.get("goals", []),
            "tone": content_request.get("tone", "professional"),
            "call_to_action": content_request.get("call_to_action", ""),
            "key_insights": content_request.get("key_insights", [])
        }
        
        from agents.core.context import AgentContext, AgentConfig
        writer_context = AgentContext(
            task_id=str(uuid.uuid4()),
            task_type="broadcast_content_generation",
            input_data=writer_input,
            memory_interface=None,
            config=AgentConfig(),
            request_id=str(uuid.uuid4())
        )
        
        writer_plan = await writer.plan(writer_input)
        generated_content = await writer.execute(writer_plan)
        content_validation = await writer.validate(generated_content)
        
        if not content_validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Generated content validation failed: {', '.join(content_validation['errors'])}"
            )
        
        # Update broadcast with generated content
        broadcast.update_content(
            generated_content["subject"],
            generated_content["content_md"],
            generated_content["content_html"],
            current_user.get("id") if current_user else None
        )
        broadcast.preview_text = generated_content.get("preview_text", "")
        
        await db.commit()
        
        logger.info("Broadcast content generated", 
                   broadcast_id=str(broadcast_id),
                   word_count=generated_content.get("word_count", 0))
        
        return success_response(
            data={
                "broadcast": broadcast.to_dict(),
                "generation_results": {
                    "quality_score": content_validation["quality_score"],
                    "word_count": generated_content.get("word_count", 0),
                    "reading_time": generated_content.get("reading_time_minutes", 0)
                }
            },
            message="Broadcast content generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate broadcast content", broadcast_id=str(broadcast_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{broadcast_id}/stats", response_model=BroadcastStatsResponse)
async def get_broadcast_stats(
    broadcast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> BroadcastStatsResponse:
    """Get broadcast statistics and analytics."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        stats = broadcast.get_performance_summary()
        stats["broadcast_id"] = str(broadcast_id)
        stats["broadcast_name"] = broadcast.name
        
        return success_response(
            data=stats,
            message="Broadcast stats retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get broadcast stats", broadcast_id=str(broadcast_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{broadcast_id}/clone")
async def clone_broadcast(
    broadcast_id: uuid.UUID,
    new_name: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clone an existing broadcast."""
    try:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await db.execute(stmt)
        original_broadcast = result.scalar_one_or_none()
        
        if not original_broadcast:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Broadcast not found"
            )
        
        # Clone broadcast
        new_broadcast = original_broadcast.clone(new_name)
        new_broadcast.created_by = current_user.get("id") if current_user else None
        
        db.add(new_broadcast)
        await db.commit()
        
        logger.info("Broadcast cloned", 
                   original_id=str(broadcast_id),
                   new_id=str(new_broadcast.id))
        
        return success_response(
            data=new_broadcast.to_dict(),
            message="Broadcast cloned successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clone broadcast", broadcast_id=str(broadcast_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/scheduled/upcoming")
async def get_upcoming_scheduled_broadcasts(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get upcoming scheduled broadcasts."""
    try:
        now = datetime.now(timezone.utc)
        stmt = select(Broadcast).where(
            and_(
                Broadcast.status == BroadcastStatus.SCHEDULED,
                Broadcast.scheduled_at > now
            )
        ).order_by(Broadcast.scheduled_at.asc()).limit(limit)
        
        result = await db.execute(stmt)
        broadcasts = result.scalars().all()
        
        return success_response(
            data={
                "broadcasts": [broadcast.to_dict() for broadcast in broadcasts],
                "total": len(broadcasts)
            },
            message="Upcoming scheduled broadcasts retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get upcoming scheduled broadcasts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
