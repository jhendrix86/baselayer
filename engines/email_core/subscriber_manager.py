"""
EMAIL_CORE Subscriber Manager

Subscriber CRUD operations with Brevo synchronization,
double opt-in, and segmentation support.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, delete

from .models.subscriber import Subscriber, SubscriberStatus, SubscriberSource, LeadMagnet
from .brevo_client import BrevoClient, BrevoContact, get_brevo_client
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class SubscriberManager:
    """
    Subscriber management with Brevo synchronization.
    
    Handles subscriber CRUD operations, segmentation,
    and Brevo API integration.
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        brevo_client: Optional[BrevoClient] = None,
        enable_double_opt_in: bool = False,
        default_list_ids: List[int] = None
    ) -> None:
        """Initialize subscriber manager."""
        self.db = db_session
        self.brevo_client = brevo_client or get_brevo_client()
        self.enable_double_opt_in = enable_double_opt_in
        self.default_list_ids = default_list_ids or []
        
        logger.info("SubscriberManager initialized", 
                   double_opt_in=self.enable_double_opt_in,
                   default_lists=len(self.default_list_ids))
    
    async def add_subscriber(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        source: SubscriberSource = SubscriberSource.LANDING_PAGE,
        tags: Optional[List[str]] = None,
        lead_magnet_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        custom_attributes: Optional[Dict[str, Any]] = None,
        list_ids: Optional[List[int]] = None
    ) -> Subscriber:
        """
        Add new subscriber with Brevo synchronization.
        
        Args:
            email: Subscriber email address
            first_name: First name
            last_name: Last name
            source: Acquisition source
            tags: Initial tags
            lead_magnet_id: Lead magnet that generated this subscriber
            metadata: Additional metadata
            custom_attributes: Custom attributes for Brevo
            list_ids: Brevo list IDs to add subscriber to
            
        Returns:
            Created subscriber object
        """
        try:
            # Check if subscriber already exists
            existing = await self.get_subscriber_by_email(email)
            if existing:
                logger.info("Subscriber already exists", email=email, subscriber_id=str(existing.id))
                return existing
            
            # Create subscriber
            subscriber = Subscriber(
                email=email,
                first_name=first_name,
                last_name=last_name,
                source=source,
                tags=tags or [],
                lead_magnet_id=lead_magnet_id,
                metadata=metadata or {},
                custom_attributes=custom_attributes or {},
                status=SubscriberStatus.ACTIVE if not self.enable_double_opt_in else SubscriberStatus.ACTIVE  # TODO: Implement double opt-in
            )
            
            # Add to database
            self.db.add(subscriber)
            await self.db.flush()
            
            # Sync with Brevo
            await self._sync_subscriber_to_brevo(subscriber, list_ids or self.default_list_ids)
            
            # Update lead magnet stats if applicable
            if lead_magnet_id:
                await self._update_lead_magnet_stats(lead_magnet_id)
            
            await self.db.commit()
            
            logger.info("Subscriber added", 
                       email=email, 
                       subscriber_id=str(subscriber.id),
                       source=source.value)
            
            return subscriber
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to add subscriber", email=email, error=str(e))
            raise BaseLayerError(f"Failed to add subscriber: {e}")
    
    async def get_subscriber_by_email(self, email: str) -> Optional[Subscriber]:
        """Get subscriber by email address."""
        try:
            stmt = select(Subscriber).where(Subscriber.email == email)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get subscriber by email", email=email, error=str(e))
            raise BaseLayerError(f"Failed to get subscriber: {e}")
    
    async def get_subscriber_by_id(self, subscriber_id: uuid.UUID) -> Optional[Subscriber]:
        """Get subscriber by ID."""
        try:
            stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get subscriber by ID", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to get subscriber: {e}")
    
    async def update_subscriber(
        self,
        subscriber_id: uuid.UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        custom_attributes: Optional[Dict[str, Any]] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None
    ) -> Subscriber:
        """Update subscriber information."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                raise BaseLayerError(f"Subscriber not found: {subscriber_id}")
            
            # Update fields
            if first_name is not None:
                subscriber.first_name = first_name
            if last_name is not None:
                subscriber.last_name = last_name
            if tags is not None:
                subscriber.tags = tags
            if metadata is not None:
                subscriber.metadata = metadata
            if custom_attributes is not None:
                subscriber.custom_attributes = custom_attributes
            if timezone is not None:
                subscriber.timezone = timezone
            if language is not None:
                subscriber.language = language
            
            # Sync with Brevo
            await self._sync_subscriber_to_brevo(subscriber)
            
            await self.db.commit()
            
            logger.info("Subscriber updated", subscriber_id=str(subscriber_id))
            return subscriber
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update subscriber", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to update subscriber: {e}")
    
    async def unsubscribe_subscriber(
        self,
        subscriber_id: uuid.UUID,
        reason: Optional[str] = None
    ) -> Subscriber:
        """Unsubscribe subscriber and sync with Brevo."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                raise BaseLayerError(f"Subscriber not found: {subscriber_id}")
            
            # Update status
            subscriber.unsubscribe(reason)
            
            # Remove from Brevo lists
            if subscriber.brevo_contact_id:
                await self._remove_from_brevo_lists(subscriber)
            
            await self.db.commit()
            
            logger.info("Subscriber unsubscribed", 
                       subscriber_id=str(subscriber_id),
                       reason=reason)
            
            return subscriber
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to unsubscribe subscriber", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to unsubscribe subscriber: {e}")
    
    async def tag_subscriber(
        self,
        subscriber_id: uuid.UUID,
        tags: List[str],
        operation: str = "add"  # add, remove, replace
    ) -> Subscriber:
        """Manage subscriber tags."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                raise BaseLayerError(f"Subscriber not found: {subscriber_id}")
            
            # Update tags based on operation
            if operation == "add":
                for tag in tags:
                    subscriber.add_tag(tag)
            elif operation == "remove":
                for tag in tags:
                    subscriber.remove_tag(tag)
            elif operation == "replace":
                subscriber.tags = tags
            else:
                raise BaseLayerError(f"Invalid tag operation: {operation}")
            
            # Sync with Brevo
            await self._sync_subscriber_to_brevo(subscriber)
            
            await self.db.commit()
            
            logger.info("Subscriber tags updated", 
                       subscriber_id=str(subscriber_id),
                       operation=operation,
                       tags=tags)
            
            return subscriber
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update subscriber tags", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to update subscriber tags: {e}")
    
    async def segment_subscribers(
        self,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Subscriber]:
        """
        Get subscribers based on segmentation filters.
        
        Args:
            filters: Segmentation filters
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of matching subscribers
        """
        try:
            stmt = select(Subscriber)
            
            # Apply filters
            if "status" in filters:
                stmt = stmt.where(Subscriber.status == filters["status"])
            
            if "source" in filters:
                stmt = stmt.where(Subscriber.source == filters["source"])
            
            if "tags" in filters:
                tags = filters["tags"]
                if isinstance(tags, list):
                    # Subscribers with any of these tags
                    stmt = stmt.where(Subscriber.tags.overlap(tags))
                elif isinstance(tags, dict):
                    if "any" in tags:
                        stmt = stmt.where(Subscriber.tags.overlap(tags["any"]))
                    elif "all" in tags:
                        # Subscribers with all of these tags
                        for tag in tags["all"]:
                            stmt = stmt.where(Subscriber.tags.contains([tag]))
            
            if "date_range" in filters:
                date_range = filters["date_range"]
                if "subscribed_after" in date_range:
                    stmt = stmt.where(Subscriber.subscribed_at >= date_range["subscribed_after"])
                if "subscribed_before" in date_range:
                    stmt = stmt.where(Subscriber.subscribed_at <= date_range["subscribed_before"])
            
            if "engagement" in filters:
                engagement = filters["engagement"]
                if "min_open_rate" in engagement:
                    # This would require a more complex query with joins
                    # For now, we'll skip this in the basic implementation
                    pass
            
            # Order by most recent
            stmt = stmt.order_by(Subscriber.subscribed_at.desc())
            
            # Apply pagination
            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to segment subscribers", filters=filters, error=str(e))
            raise BaseLayerError(f"Failed to segment subscribers: {e}")
    
    async def sync_with_brevo(self, subscriber_id: uuid.UUID) -> Subscriber:
        """Sync subscriber with Brevo API."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                raise BaseLayerError(f"Subscriber not found: {subscriber_id}")
            
            await self._sync_subscriber_to_brevo(subscriber)
            await self.db.commit()
            
            logger.info("Subscriber synced with Brevo", subscriber_id=str(subscriber_id))
            return subscriber
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to sync subscriber with Brevo", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to sync subscriber with Brevo: {e}")
    
    async def bulk_sync_with_brevo(self, limit: int = 100) -> Dict[str, Any]:
        """Bulk sync subscribers with Brevo."""
        try:
            # Get subscribers that need syncing
            stmt = select(Subscriber).where(
                or_(
                    Subscriber.brevo_contact_id.is_(None),
                    Subscriber.updated_at > Subscriber.subscribed_at
                )
            ).limit(limit)
            
            result = await self.db.execute(stmt)
            subscribers = result.scalars().all()
            
            synced_count = 0
            failed_count = 0
            
            for subscriber in subscribers:
                try:
                    await self._sync_subscriber_to_brevo(subscriber)
                    synced_count += 1
                except Exception as e:
                    logger.error("Failed to sync subscriber", 
                               subscriber_id=str(subscriber.id), 
                               error=str(e))
                    failed_count += 1
            
            await self.db.commit()
            
            logger.info("Bulk sync completed", 
                       total=len(subscribers),
                       synced=synced_count,
                       failed=failed_count)
            
            return {
                "total": len(subscribers),
                "synced": synced_count,
                "failed": failed_count
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to bulk sync with Brevo", error=str(e))
            raise BaseLayerError(f"Failed to bulk sync with Brevo: {e}")
    
    async def get_subscriber_stats(self, subscriber_id: uuid.UUID) -> Dict[str, Any]:
        """Get subscriber statistics."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                raise BaseLayerError(f"Subscriber not found: {subscriber_id}")
            
            return {
                "subscriber_id": str(subscriber.id),
                "email": subscriber.mask_email(subscriber.email),
                "status": subscriber.status,
                "subscribed_at": subscriber.subscribed_at.isoformat() if subscriber.subscribed_at else None,
                "email_count": subscriber.email_count,
                "open_count": subscriber.open_count,
                "click_count": subscriber.click_count,
                "bounce_count": subscriber.bounce_count,
                "complaint_count": subscriber.complaint_count,
                "engagement_rate": subscriber.engagement_rate,
                "open_rate": subscriber.open_rate,
                "click_rate": subscriber.click_rate,
                "tags": subscriber.tags,
                "last_emailed_at": subscriber.last_emailed_at.isoformat() if subscriber.last_emailed_at else None
            }
            
        except Exception as e:
            logger.error("Failed to get subscriber stats", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to get subscriber stats: {e}")
    
    async def _sync_subscriber_to_brevo(self, subscriber: Subscriber, list_ids: Optional[List[int]] = None) -> None:
        """Sync subscriber with Brevo API."""
        try:
            if not self.brevo_client:
                logger.warning("No Brevo client available, skipping sync")
                return
            
            # Prepare contact data
            contact_data = BrevoContact(
                email=subscriber.email,
                attributes=subscriber.get_brevo_attributes(),
                listIds=list_ids or subscriber.brevo_list_ids or self.default_list_ids,
                updateEnabled=True
            )
            
            # Check if contact exists in Brevo
            brevo_contact = await self.brevo_client.get_contact(subscriber.email)
            
            if brevo_contact:
                # Update existing contact
                await self.brevo_client.update_contact(subscriber.email, contact_data.attributes)
                subscriber.brevo_contact_id = brevo_contact.get("id")
                
                # Update list memberships if needed
                if list_ids:
                    for list_id in list_ids:
                        await self.brevo_client.add_contact_to_list(subscriber.email, list_id)
            else:
                # Create new contact
                result = await self.brevo_client.create_contact(contact_data)
                subscriber.brevo_contact_id = result.get("id")
            
            # Update list IDs
            if list_ids:
                subscriber.brevo_list_ids = list_ids
            
        except Exception as e:
            logger.error("Failed to sync subscriber to Brevo", 
                       subscriber_id=str(subscriber.id), 
                       error=str(e))
            # Don't raise here - we don't want to fail the whole operation
            # due to Brevo sync issues
    
    async def _remove_from_brevo_lists(self, subscriber: Subscriber) -> None:
        """Remove subscriber from all Brevo lists."""
        try:
            if not self.brevo_client or not subscriber.brevo_list_ids:
                return
            
            for list_id in subscriber.brevo_list_ids:
                await self.brevo_client.remove_contact_from_list(subscriber.email, list_id)
            
            subscriber.brevo_list_ids = []
            
        except Exception as e:
            logger.error("Failed to remove subscriber from Brevo lists", 
                       subscriber_id=str(subscriber.id), 
                       error=str(e))
    
    async def _update_lead_magnet_stats(self, lead_magnet_id: uuid.UUID) -> None:
        """Update lead magnet statistics."""
        try:
            stmt = select(LeadMagnet).where(LeadMagnet.id == lead_magnet_id)
            result = await self.db.execute(stmt)
            lead_magnet = result.scalar_one_or_none()
            
            if lead_magnet:
                lead_magnet.increment_subscriber_count()
            
        except Exception as e:
            logger.error("Failed to update lead magnet stats", 
                       lead_magnet_id=str(lead_magnet_id), 
                       error=str(e))
    
    async def delete_subscriber(self, subscriber_id: uuid.UUID) -> bool:
        """Delete subscriber (GDPR compliance)."""
        try:
            subscriber = await self.get_subscriber_by_id(subscriber_id)
            if not subscriber:
                return False
            
            # Delete from Brevo first
            if subscriber.brevo_contact_id and self.brevo_client:
                try:
                    await self.brevo_client.delete_contact(subscriber.email)
                except Exception as e:
                    logger.error("Failed to delete from Brevo", 
                               subscriber_id=str(subscriber_id), 
                               error=str(e))
            
            # Delete from database
            stmt = delete(Subscriber).where(Subscriber.id == subscriber_id)
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.info("Subscriber deleted", subscriber_id=str(subscriber_id))
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to delete subscriber", subscriber_id=str(subscriber_id), error=str(e))
            raise BaseLayerError(f"Failed to delete subscriber: {e}")
    
    async def get_all_subscribers(
        self,
        status: Optional[SubscriberStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Subscriber]:
        """Get all subscribers with optional filtering."""
        try:
            stmt = select(Subscriber)
            
            if status:
                stmt = stmt.where(Subscriber.status == status)
            
            stmt = stmt.order_by(Subscriber.subscribed_at.desc())
            
            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get all subscribers", error=str(e))
            raise BaseLayerError(f"Failed to get all subscribers: {e}")
