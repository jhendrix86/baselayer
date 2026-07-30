"""
WIRE Sequence API Routes

FastAPI routes for email sequence management,
enrollment, and analytics with JWT protection.
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

from ..models.sequence import Sequence, SequenceStatus, SequenceTrigger
from ..models.sequence_enrollment import SequenceEnrollment, EnrollmentStatus
from ..models.schemas import (
    SequenceCreate, SequenceUpdate, SequenceResponse, SequenceListResponse,
    SequenceEnrollmentRequest, SequenceEnrollmentResponse, SequenceStatsResponse
)
from ...core.dependencies import get_db_session, get_current_user, get_redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/sequences", tags=["sequences"])


@router.post("/", response_model=SequenceResponse)
async def create_sequence(
    sequence_data: SequenceCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SequenceResponse:
    """Create a new email sequence."""
    try:
        # Create sequence
        sequence = Sequence(
            name=sequence_data.name,
            description=sequence_data.description,
            slug=sequence_data.slug,
            trigger=sequence_data.trigger,
            trigger_config=sequence_data.trigger_config,
            steps=sequence_data.steps,
            max_enrollments=sequence_data.max_enrollments,
            enrollment_rate_limit=sequence_data.enrollment_rate_limit,
            auto_reenroll=sequence_data.auto_reenroll,
            segment_filters=sequence_data.segment_filters,
            exclusion_filters=sequence_data.exclusion_filters,
            send_on_weekends=sequence_data.send_on_weekends,
            send_time_start=sequence_data.send_time_start,
            send_time_end=sequence_data.send_time_end,
            timezone=sequence_data.timezone,
            created_by=current_user.get("id") if current_user else None
        )
        
        # Validate steps
        validation_errors = sequence.validate_steps()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence validation failed: {', '.join(validation_errors)}"
            )
        
        db.add(sequence)
        await db.commit()
        
        logger.info("Sequence created", 
                   sequence_id=str(sequence.id),
                   name=sequence.name)
        
        return success_response(
            data=sequence.to_dict(),
            message="Sequence created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create sequence", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=SequenceListResponse)
async def list_sequences(
    status: Optional[SequenceStatus] = Query(None),
    trigger: Optional[SequenceTrigger] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|name|subscriber_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SequenceListResponse:
    """List sequences with filtering and pagination."""
    try:
        stmt = select(Sequence)
        
        # Apply filters
        if status:
            stmt = stmt.where(Sequence.status == status)
        if trigger:
            stmt = stmt.where(Sequence.trigger == trigger)
        if search:
            stmt = stmt.where(
                or_(
                    Sequence.name.ilike(f"%{search}%"),
                    Sequence.description.ilike(f"%{search}%")
                )
            )
        
        # Apply sorting
        if sort_by == "created_at":
            stmt = stmt.order_by(
                Sequence.created_at.desc() if sort_order == "desc" else Sequence.created_at.asc()
            )
        elif sort_by == "updated_at":
            stmt = stmt.order_by(
                Sequence.updated_at.desc() if sort_order == "desc" else Sequence.updated_at.asc()
            )
        elif sort_by == "name":
            stmt = stmt.order_by(
                Sequence.name.desc() if sort_order == "desc" else Sequence.name.asc()
            )
        elif sort_by == "subscriber_count":
            stmt = stmt.order_by(
                Sequence.subscriber_count.desc() if sort_order == "desc" else Sequence.subscriber_count.asc()
            )
        
        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        sequences = result.scalars().all()
        
        # Get total count
        count_stmt = select(Sequence)
        if status:
            count_stmt = count_stmt.where(Sequence.status == status)
        if trigger:
            count_stmt = count_stmt.where(Sequence.trigger == trigger)
        if search:
            count_stmt = count_stmt.where(
                or_(
                    Sequence.name.ilike(f"%{search}%"),
                    Sequence.description.ilike(f"%{search}%")
                )
            )
        
        count_result = await db.execute(count_stmt)
        total_count = len(count_result.scalars().all())
        
        return success_response(
            data={
                "sequences": [seq.to_dict() for seq in sequences],
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Sequences retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to list sequences", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SequenceResponse:
    """Get sequence by ID."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        return success_response(
            data=sequence.to_dict(),
            message="Sequence retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get sequence", sequence_id=str(sequence_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: uuid.UUID,
    sequence_data: SequenceUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SequenceResponse:
    """Update sequence information."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        # Update fields
        if sequence_data.name is not None:
            sequence.name = sequence_data.name
        if sequence_data.description is not None:
            sequence.description = sequence_data.description
        if sequence_data.steps is not None:
            sequence.steps = sequence_data.steps
        if sequence_data.segment_filters is not None:
            sequence.segment_filters = sequence_data.segment_filters
        if sequence_data.exclusion_filters is not None:
            sequence.exclusion_filters = sequence_data.exclusion_filters
        if sequence_data.send_on_weekends is not None:
            sequence.send_on_weekends = sequence_data.send_on_weekends
        if sequence_data.send_time_start is not None:
            sequence.send_time_start = sequence_data.send_time_start
        if sequence_data.send_time_end is not None:
            sequence.send_time_end = sequence_data.send_time_end
        
        sequence.last_modified_by = current_user.get("id") if current_user else None
        
        # Validate steps if updated
        if sequence_data.steps is not None:
            validation_errors = sequence.validate_steps()
            if validation_errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sequence validation failed: {', '.join(validation_errors)}"
                )
        
        await db.commit()
        
        logger.info("Sequence updated", sequence_id=str(sequence_id))
        
        return success_response(
            data=sequence.to_dict(),
            message="Sequence updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update sequence", sequence_id=str(sequence_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{sequence_id}")
async def delete_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete sequence."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        # Check if sequence has enrollments
        enrollment_stmt = select(SequenceEnrollment).where(SequenceEnrollment.sequence_id == sequence_id)
        enrollment_result = await db.execute(enrollment_stmt)
        enrollments = enrollment_result.scalars().all()
        
        if enrollments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete sequence with active enrollments"
            )
        
        await db.delete(sequence)
        await db.commit()
        
        logger.info("Sequence deleted", sequence_id=str(sequence_id))
        
        return success_response(
            data={"deleted": True},
            message="Sequence deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete sequence", sequence_id=str(sequence_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{sequence_id}/activate")
async def activate_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Activate sequence."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        # Validate sequence before activation
        validation_errors = sequence.validate_steps()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot activate sequence with validation errors: {', '.join(validation_errors)}"
            )
        
        sequence.activate()
        await db.commit()
        
        logger.info("Sequence activated", sequence_id=str(sequence_id))
        
        return success_response(
            data=sequence.to_dict(),
            message="Sequence activated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to activate sequence", sequence_id=str(sequence_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{sequence_id}/pause")
async def pause_sequence(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Pause sequence."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        sequence = result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        sequence.pause()
        await db.commit()
        
        logger.info("Sequence paused", sequence_id=str(sequence_id))
        
        return success_response(
            data=sequence.to_dict(),
            message="Sequence paused successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to pause sequence", sequence_id=str(sequence_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{sequence_id}/enroll")
async def enroll_subscriber(
    sequence_id: uuid.UUID,
    enrollment: SequenceEnrollmentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enroll subscriber in sequence."""
    try:
        # Get sequence
        seq_stmt = select(Sequence).where(Sequence.id == sequence_id)
        seq_result = await db.execute(seq_stmt)
        sequence = seq_result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        if not sequence.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enroll in inactive sequence"
            )
        
        # Get subscriber
        from ...email_core.models.subscriber import Subscriber
        sub_stmt = select(Subscriber).where(Subscriber.id == enrollment.subscriber_id)
        sub_result = await db.execute(sub_stmt)
        subscriber = sub_result.scalar_one_or_none()
        
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscriber not found"
            )
        
        # Check if already enrolled
        existing_stmt = select(SequenceEnrollment).where(
            and_(
                SequenceEnrollment.subscriber_id == enrollment.subscriber_id,
                SequenceEnrollment.sequence_id == sequence_id
            )
        )
        existing_result = await db.execute(existing_stmt)
        existing_enrollment = existing_result.scalar_one_or_none()
        
        if existing_enrollment and not sequence.auto_reenroll:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscriber already enrolled in sequence"
            )
        
        # Create or update enrollment
        if existing_enrollment and sequence.auto_reenroll:
            existing_enrollment.restart()
            enrollment_obj = existing_enrollment
        else:
            enrollment_obj = SequenceEnrollment(
                subscriber_id=enrollment.subscriber_id,
                sequence_id=sequence_id,
                total_steps=len(sequence.steps),
                enrollment_source=enrollment.enrollment_source or "api",
                enrollment_data=enrollment.enrollment_data or {}
            )
            db.add(enrollment_obj)
        
        # Calculate next step time
        next_time = sequence.get_next_send_time(
            datetime.now(timezone.utc), 
            enrollment_obj.current_step
        )
        enrollment_obj.next_step_at = next_time
        
        await db.commit()
        
        # Update sequence subscriber count
        sequence.increment_subscriber_count()
        await db.commit()
        
        logger.info("Subscriber enrolled in sequence", 
                   sequence_id=str(sequence_id),
                   subscriber_id=str(enrollment.subscriber_id))
        
        return success_response(
            data=enrollment_obj.to_dict(),
            message="Subscriber enrolled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enroll subscriber", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{sequence_id}/enrollments")
async def list_enrollments(
    sequence_id: uuid.UUID,
    status: Optional[EnrollmentStatus] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """List enrollments for a sequence."""
    try:
        stmt = select(SequenceEnrollment).where(SequenceEnrollment.sequence_id == sequence_id)
        
        if status:
            stmt = stmt.where(SequenceEnrollment.status == status)
        
        stmt = stmt.order_by(SequenceEnrollment.enrolled_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        enrollments = result.scalars().all()
        
        # Get total count
        count_stmt = select(SequenceEnrollment).where(SequenceEnrollment.sequence_id == sequence_id)
        if status:
            count_stmt = count_stmt.where(SequenceEnrollment.status == status)
        
        count_result = await db.execute(count_stmt)
        total_count = len(count_result.scalars().all())
        
        return success_response(
            data={
                "enrollments": [enrollment.to_dict() for enrollment in enrollments],
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Enrollments retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to list enrollments", sequence_id=str(sequence_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{sequence_id}/stats", response_model=SequenceStatsResponse)
async def get_sequence_stats(
    sequence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> SequenceStatsResponse:
    """Get sequence statistics and analytics."""
    try:
        # Get sequence
        seq_stmt = select(Sequence).where(Sequence.id == sequence_id)
        seq_result = await db.execute(seq_stmt)
        sequence = seq_result.scalar_one_or_none()
        
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        # Get enrollment stats
        enrollment_stmt = select(SequenceEnrollment).where(SequenceEnrollment.sequence_id == sequence_id)
        enrollment_result = await db.execute(enrollment_stmt)
        enrollments = enrollment_result.scalars().all()
        
        # Calculate stats
        total_enrollments = len(enrollments)
        active_enrollments = len([e for e in enrollments if e.is_active])
        completed_enrollments = len([e for e in enrollments if e.is_completed])
        cancelled_enrollments = len([e for e in enrollments if e.is_cancelled])
        
        # Calculate completion rate
        completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
        
        # Calculate average completion time
        completed_times = [
            (e.completed_at - e.enrolled_at).total_seconds() / 86400  # days
            for e in enrollments if e.completed_at and e.enrolled_at
        ]
        avg_completion_time = sum(completed_times) / len(completed_times) if completed_times else 0
        
        # Calculate engagement rates
        total_sent = sum(e.total_sent for e in enrollments)
        total_opened = sum(e.total_opened for e in enrollments)
        total_clicked = sum(e.total_clicked for e in enrollments)
        
        open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        click_rate = (total_clicked / total_opened * 100) if total_opened > 0 else 0
        
        stats = {
            "sequence_id": str(sequence_id),
            "sequence_name": sequence.name,
            "total_enrollments": total_enrollments,
            "active_enrollments": active_enrollments,
            "completed_enrollments": completed_enrollments,
            "cancelled_enrollments": cancelled_enrollments,
            "completion_rate": completion_rate,
            "average_completion_time_days": avg_completion_time,
            "total_emails_sent": total_sent,
            "total_opens": total_opened,
            "total_clicks": total_clicked,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "sequence_performance": {
                "subscriber_count": sequence.subscriber_count,
                "open_rate": sequence.open_rate,
                "click_rate": sequence.click_rate,
                "unsubscribe_rate": sequence.unsubscribe_rate
            }
        }
        
        return success_response(
            data=stats,
            message="Sequence stats retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get sequence stats", sequence_id=str(sequence_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{sequence_id}/clone")
async def clone_sequence(
    sequence_id: uuid.UUID,
    new_name: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clone an existing sequence."""
    try:
        stmt = select(Sequence).where(Sequence.id == sequence_id)
        result = await db.execute(stmt)
        original_sequence = result.scalar_one_or_none()
        
        if not original_sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sequence not found"
            )
        
        # Clone sequence
        new_sequence = original_sequence.clone(new_name)
        new_sequence.created_by = current_user.get("id") if current_user else None
        
        db.add(new_sequence)
        await db.commit()
        
        logger.info("Sequence cloned", 
                   original_id=str(sequence_id),
                   new_id=str(new_sequence.id))
        
        return success_response(
            data=new_sequence.to_dict(),
            message="Sequence cloned successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clone sequence", sequence_id=str(sequence_id), error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
