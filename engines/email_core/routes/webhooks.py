"""
EMAIL_CORE Webhook API Routes

FastAPI routes for handling Brevo webhooks
for email delivery, opens, clicks, bounces, and complaints.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError
from baselayer.core.middleware import success_response, error_response

from ..models.email_log import EmailLog, EmailStatus, EmailType
from ..models.subscriber import Subscriber, SubscriberStatus
from ..brevo_client import BrevoClient, get_brevo_client
from ...core.dependencies import get_db_session

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/brevo/delivery")
async def brevo_delivery_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo delivery webhook."""
    try:
        # Parse webhook data
        webhook_data = await request.json()
        
        # Validate webhook structure
        if not webhook_data.get("event"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing event in webhook data"
            )
        
        if not webhook_data.get("messageId"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing messageId in webhook data"
            )
        
        # Get Brevo client for parsing
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            logger.warning("Email log not found for webhook", 
                        message_id=webhook.messageId,
                        event=webhook.event)
            return success_response(
                data={"processed": False, "reason": "Email log not found"},
                message="Webhook processed but email not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Process webhook event
        await _process_webhook_event(webhook, email_log, subscriber, db)
        
        await db.commit()
        
        logger.info("Brevo webhook processed", 
                   event=webhook.event,
                   message_id=webhook.messageId,
                   subscriber_email=subscriber.email if subscriber else None)
        
        return success_response(
            data={"processed": True, "event": webhook.event},
            message="Webhook processed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process Brevo webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/brevo/open")
async def brevo_open_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo open webhook."""
    try:
        webhook_data = await request.json()
        
        # Parse and validate
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            return success_response(
                data={"processed": False},
                message="Email log not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Update email log
        email_log.mark_as_opened(
            user_agent=webhook.details.get("user_agent") if webhook.details else None,
            ip_address=webhook.details.get("ip_address") if webhook.details else None,
            location=webhook.details.get("location") if webhook.details else None
        )
        
        # Update subscriber metrics
        if subscriber:
            subscriber.increment_open_count()
        
        await db.commit()
        
        logger.info("Open webhook processed", 
                   message_id=webhook.messageId,
                   subscriber_email=subscriber.email if subscriber else None)
        
        return success_response(
            data={"processed": True},
            message="Open webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to process open webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/brevo/click")
async def brevo_click_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo click webhook."""
    try:
        webhook_data = await request.json()
        
        # Parse and validate
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            return success_response(
                data={"processed": False},
                message="Email log not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Extract clicked URL
        clicked_url = webhook.details.get("url") if webhook.details else None
        
        # Update email log
        email_log.mark_as_clicked(
            url=clicked_url,
            user_agent=webhook.details.get("user_agent") if webhook.details else None,
            ip_address=webhook.details.get("ip_address") if webhook.details else None
        )
        
        # Update subscriber metrics
        if subscriber:
            subscriber.increment_click_count()
        
        await db.commit()
        
        logger.info("Click webhook processed", 
                   message_id=webhook.messageId,
                   subscriber_email=subscriber.email if subscriber else None,
                   url=clicked_url)
        
        return success_response(
            data={"processed": True},
            message="Click webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to process click webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/brevo/bounce")
async def brevo_bounce_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo bounce webhook."""
    try:
        webhook_data = await request.json()
        
        # Parse and validate
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            return success_response(
                data={"processed": False},
                message="Email log not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Extract bounce details
        bounce_type = webhook.details.get("bounce_type", "unknown") if webhook.details else "unknown"
        bounce_reason = webhook.reason or "Unknown reason"
        
        # Update email log
        email_log.mark_as_bounced(bounce_type, bounce_reason)
        
        # Update subscriber
        if subscriber:
            subscriber.increment_bounce_count()
            
            # Mark as bounced if too many bounces
            if subscriber.bounce_count >= 3:
                subscriber.mark_as_bounced(bounce_type)
        
        await db.commit()
        
        logger.warning("Bounce webhook processed", 
                      message_id=webhook.messageId,
                      subscriber_email=subscriber.email if subscriber else None,
                      bounce_type=bounce_type,
                      reason=bounce_reason)
        
        return success_response(
            data={"processed": True},
            message="Bounce webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to process bounce webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/brevo/complaint")
async def brevo_complaint_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo complaint webhook."""
    try:
        webhook_data = await request.json()
        
        # Parse and validate
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            return success_response(
                data={"processed": False},
                message="Email log not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Extract complaint details
        complaint_type = webhook.details.get("complaint_type", "spam") if webhook.details else "spam"
        
        # Update email log
        email_log.mark_as_complained(complaint_type)
        
        # Update subscriber - immediately mark as complained
        if subscriber:
            subscriber.mark_as_complained()
        
        await db.commit()
        
        logger.warning("Complaint webhook processed", 
                      message_id=webhook.messageId,
                      subscriber_email=subscriber.email if subscriber else None,
                      complaint_type=complaint_type)
        
        return success_response(
            data={"processed": True},
            message="Complaint webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to process complaint webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/brevo/unsubscribe")
async def brevo_unsubscribe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Handle Brevo unsubscribe webhook."""
    try:
        webhook_data = await request.json()
        
        # Parse and validate
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(webhook_data)
        
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == webhook.messageId)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            return success_response(
                data={"processed": False},
                message="Email log not found"
            )
        
        # Get subscriber
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        # Update subscriber
        if subscriber:
            subscriber.unsubscribe("Unsubscribed via email link")
        
        await db.commit()
        
        logger.info("Unsubscribe webhook processed", 
                   message_id=webhook.messageId,
                   subscriber_email=subscriber.email if subscriber else None)
        
        return success_response(
            data={"processed": True},
            message="Unsubscribe webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to process unsubscribe webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def _process_webhook_event(
    webhook: Any, 
    email_log: EmailLog, 
    subscriber: Optional[Subscriber], 
    db: AsyncSession
) -> None:
    """Process generic webhook event."""
    event = webhook.event.lower()
    
    if event == "delivered":
        email_log.mark_as_delivered()
        
    elif event == "sent":
        # Already marked as sent during sending
        pass
        
    elif event == "opened":
        email_log.mark_as_opened()
        if subscriber:
            subscriber.increment_open_count()
            
    elif event == "click":
        clicked_url = webhook.details.get("url") if webhook.details else None
        email_log.mark_as_clicked(clicked_url)
        if subscriber:
            subscriber.increment_click_count()
            
    elif event == "bounce":
        bounce_type = webhook.details.get("bounce_type", "unknown") if webhook.details else "unknown"
        bounce_reason = webhook.reason or "Unknown reason"
        email_log.mark_as_bounced(bounce_type, bounce_reason)
        if subscriber:
            subscriber.increment_bounce_count()
            if subscriber.bounce_count >= 3:
                subscriber.mark_as_bounced(bounce_type)
                
    elif event == "complaint":
        complaint_type = webhook.details.get("complaint_type", "spam") if webhook.details else "spam"
        email_log.mark_as_complained(complaint_type)
        if subscriber:
            subscriber.mark_as_complained()
            
    elif event == "unsubscribe":
        if subscriber:
            subscriber.unsubscribe("Unsubscribed via email")
            
    else:
        logger.warning("Unknown webhook event", event=event, message_id=webhook.messageId)


@router.get("/status")
async def webhook_status(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get webhook processing status."""
    try:
        # Get recent webhook activity
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timezone.timedelta(hours=24)
        
        # Count recent events by type
        recent_stmt = select(EmailLog).where(EmailLog.updated_at >= recent_cutoff)
        recent_result = await db.execute(recent_stmt)
        recent_logs = recent_result.scalars().all()
        
        event_counts = {}
        for log in recent_logs:
            if log.status not in event_counts:
                event_counts[log.status] = 0
            event_counts[log.status] += 1
        
        return success_response(
            data={
                "webhook_status": "active",
                "recent_events_24h": event_counts,
                "total_recent": len(recent_logs),
                "last_updated": now.isoformat()
            },
            message="Webhook status retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get webhook status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/test")
async def test_webhook(
    event_type: str = Query(..., regex="^(delivered|opened|clicked|bounced|complained|unsubscribed)$"),
    message_id: str = Query(...),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Test webhook processing (for development)."""
    try:
        # Find email log
        stmt = select(EmailLog).where(EmailLog.brevo_message_id == message_id)
        result = await db.execute(stmt)
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email log not found"
            )
        
        # Create test webhook data
        test_webhook_data = {
            "event": event_type,
            "messageId": message_id,
            "to": email_log.subscriber.email if email_log.subscriber else "test@example.com",
            "subject": email_log.subject,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "test": True,
                "user_agent": "Test Agent",
                "ip_address": "127.0.0.1"
            }
        }
        
        # Process webhook
        brevo_client = get_brevo_client()
        webhook = brevo_client.parse_webhook(test_webhook_data)
        
        subscriber_stmt = select(Subscriber).where(Subscriber.id == email_log.subscriber_id)
        subscriber_result = await db.execute(subscriber_stmt)
        subscriber = subscriber_result.scalar_one_or_none()
        
        await _process_webhook_event(webhook, email_log, subscriber, db)
        await db.commit()
        
        logger.info("Test webhook processed", 
                   event_type=event_type,
                   message_id=message_id)
        
        return success_response(
            data={"processed": True, "test": True},
            message="Test webhook processed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process test webhook", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
