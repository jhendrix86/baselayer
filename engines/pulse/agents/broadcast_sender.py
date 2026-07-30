"""
PULSE Broadcast Sender Agent

Agent for sending broadcasts and newsletters with
segmentation, daily limit management, and queue overflow.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..models.broadcast import Broadcast, BroadcastStatus, BroadcastType
from ...email_core.models.subscriber import Subscriber, SubscriberStatus
from ...email_core.models.email_log import EmailLog, EmailType, EmailStatus
from ...email_core.template_engine import EmailTemplateEngine
from ...email_core.brevo_client import BrevoClient, get_brevo_client

logger = get_logger(__name__)


class BroadcastSender(AgentBase):
    """
    Broadcast sending agent.
    
    Sends newsletters and broadcasts with segmentation,
    daily limit management, and queue overflow handling.
    """
    
    agent_name = "broadcast_sender"
    agent_version = "1.0.0"
    
    def __init__(
        self, 
        config: Optional[AgentConfig] = None,
        db_session: Optional[AsyncSession] = None,
        redis_client=None
    ) -> None:
        super().__init__(config)
        self.db = db_session
        self.redis_client = redis_client
        self.template_engine = EmailTemplateEngine()
        self.brevo_client = get_brevo_client()
        self.daily_limit = 300
        self.batch_size = 100
        self.send_rate_limit = 100  # Emails per minute
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan broadcast sending.
        
        Args:
            input_data: Broadcast ID and sending parameters
            
        Returns:
            Dict with sending plan
        """
        try:
            logger.info("Planning broadcast sending", 
                       broadcast_id=input_data.get("broadcast_id"))
            
            broadcast_id = input_data.get("broadcast_id")
            send_immediately = input_data.get("send_immediately", False)
            test_mode = input_data.get("test_mode", False)
            
            # Get broadcast
            broadcast = await self._get_broadcast(broadcast_id)
            if not broadcast:
                raise BaseLayerError(f"Broadcast not found: {broadcast_id}")
            
            # Check daily limit
            limit_info = await self._check_daily_limit()
            
            # Resolve target segment
            target_subscribers = await self._resolve_target_segment(broadcast, test_mode)
            
            # Plan sending strategy
            plan = {
                "broadcast_id": broadcast_id,
                "broadcast_name": broadcast.name,
                "broadcast_type": broadcast.broadcast_type,
                "send_immediately": send_immediately,
                "test_mode": test_mode,
                "daily_limit_info": limit_info,
                "target_subscribers_count": len(target_subscribers),
                "can_send": limit_info["remaining"] > 0,
                "sending_strategy": self._plan_sending_strategy(
                    limit_info, target_subscribers, broadcast
                ),
                "estimated_batches": self._calculate_batches(
                    len(target_subscribers), limit_info["remaining"]
                )
            }
            
            logger.info("Broadcast sending plan created", 
                       broadcast_name=broadcast.name,
                       target_count=plan["target_subscribers_count"],
                       can_send=plan["can_send"])
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan broadcast sending", error=str(e))
            raise BaseLayerError(f"Failed to plan broadcast sending: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute broadcast sending.
        
        Args:
            plan: Sending plan from planning phase
            
        Returns:
            Dict with sending results
        """
        try:
            logger.info("Executing broadcast sending", 
                       broadcast_id=plan["broadcast_id"])
            
            if not plan["can_send"]:
                return {
                    "status": "queued",
                    "reason": "Daily limit reached",
                    "queued_count": plan["target_subscribers_count"],
                    "sent_count": 0
                }
            
            results = {
                "status": "completed",
                "queued_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "errors": []
            }
            
            # Get broadcast and subscribers
            broadcast = await self._get_broadcast(plan["broadcast_id"])
            target_subscribers = await self._resolve_target_segment(
                broadcast, plan["test_mode"]
            )
            
            # Update broadcast status
            broadcast.start_sending()
            await self.db.commit()
            
            # Process in batches
            batch_results = await self._process_broadcast_batches(
                broadcast, target_subscribers, plan
            )
            
            # Update results
            results.update(batch_results)
            
            # Update final broadcast status
            if results["sent_count"] > 0:
                broadcast.mark_as_sent()
            else:
                broadcast.fail("No emails sent successfully")
            
            await self.db.commit()
            
            logger.info("Broadcast sending completed", 
                       broadcast_name=broadcast.name,
                       sent=results["sent_count"],
                       failed=results["failed_count"])
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute broadcast sending", error=str(e))
            raise BaseLayerError(f"Failed to execute broadcast sending: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate sending results.
        
        Args:
            results: Sending results
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating broadcast sending results")
            
            validation_errors = []
            
            # Check for reasonable counts
            if results["sent_count"] < 0:
                validation_errors.append("Negative sent count")
            
            if results["failed_count"] < 0:
                validation_errors.append("Negative failed count")
            
            if results["skipped_count"] < 0:
                validation_errors.append("Negative skipped count")
            
            # Check error rate
            total_processed = results["sent_count"] + results["failed_count"]
            if total_processed > 0:
                error_rate = results["failed_count"] / total_processed
                if error_rate > 0.2:  # More than 20% failure rate
                    validation_errors.append(f"High error rate: {error_rate:.2%}")
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "statistics": {
                    "success_rate": (results["sent_count"] / max(total_processed, 1)) * 100,
                    "error_rate": (results["failed_count"] / max(total_processed, 1)) * 100,
                    "skip_rate": (results["skipped_count"] / max(results.get("queued_count", 1), 1)) * 100
                }
            }
            
            logger.info("Broadcast sending validation completed", 
                       is_valid=validation_result["is_valid"])
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate broadcast sending results", error=str(e))
            raise BaseLayerError(f"Failed to validate broadcast sending results: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate sending report.
        
        Args:
            results: Sending results
            validation: Validation results
            
        Returns:
            Dict with sending report
        """
        try:
            logger.info("Generating broadcast sending report")
            
            report = {
                "send_id": str(uuid.uuid4()),
                "send_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "performance_metrics": {
                    "send_rate": results.get("sent_count", 0) / 60,  # Per minute
                    "success_rate": validation["statistics"]["success_rate"],
                    "error_rate": validation["statistics"]["error_rate"]
                },
                "daily_limit_usage": await self._check_daily_limit(),
                "next_send_suggestions": self._get_next_send_suggestions(results, validation),
                "metadata": {
                    "batch_size": self.batch_size,
                    "send_rate_limit": self.send_rate_limit,
                    "daily_limit": self.daily_limit
                }
            }
            
            logger.info("Broadcast sending report generated", 
                       sent=results.get("sent_count", 0),
                       success_rate=validation["statistics"]["success_rate"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate broadcast sending report", error=str(e))
            raise BaseLayerError(f"Failed to generate broadcast sending report: {e}")
    
    async def _check_daily_limit(self) -> Dict[str, Any]:
        """Check daily email limit."""
        try:
            if not self.redis_client:
                return {"sent_today": 0, "remaining": self.daily_limit, "within_limit": True}
            
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key = f"brevo:daily_limit:{today}"
            
            sent_today = await self.redis_client.get(key)
            sent_today = int(sent_today) if sent_today else 0
            
            remaining = max(0, self.daily_limit - sent_today)
            
            return {
                "sent_today": sent_today,
                "remaining": remaining,
                "within_limit": sent_today < self.daily_limit,
                "reset_time": (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to check daily limit", error=str(e))
            return {"sent_today": 0, "remaining": self.daily_limit, "within_limit": True}
    
    async def _get_broadcast(self, broadcast_id: uuid.UUID) -> Optional[Broadcast]:
        """Get broadcast by ID."""
        try:
            stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get broadcast", broadcast_id=str(broadcast_id), error=str(e))
            return None
    
    async def _resolve_target_segment(self, broadcast: Broadcast, test_mode: bool = False) -> List[Subscriber]:
        """Resolve target subscriber segment."""
        try:
            # Start with all active subscribers
            stmt = select(Subscriber).where(Subscriber.status == SubscriberStatus.ACTIVE)
            
            # Apply segment filters
            segment_filters = broadcast.segment_filters or {}
            
            if segment_filters.get("tags"):
                tags = segment_filters["tags"]
                if isinstance(tags, list):
                    stmt = stmt.where(Subscriber.tags.overlap(tags))
                elif isinstance(tags, dict):
                    if "any" in tags:
                        stmt = stmt.where(Subscriber.tags.overlap(tags["any"]))
                    elif "all" in tags:
                        for tag in tags["all"]:
                            stmt = stmt.where(Subscriber.tags.contains([tag]))
            
            if segment_filters.get("source"):
                sources = segment_filters["source"]
                if isinstance(sources, list):
                    stmt = stmt.where(Subscriber.source.in_(sources))
                else:
                    stmt = stmt.where(Subscriber.source == sources)
            
            # Apply exclusion filters
            exclusion_filters = broadcast.exclusion_filters or {}
            
            if exclusion_filters.get("tags"):
                excluded_tags = exclusion_filters["tags"]
                if isinstance(excluded_tags, list):
                    stmt = stmt.where(~Subscriber.tags.overlap(excluded_tags))
            
            if exclusion_filters.get("recently_sent"):
                # Exclude subscribers sent to recently
                recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                stmt = stmt.where(
                    or_(
                        Subscriber.last_emailed_at.is_(None),
                        Subscriber.last_emailed_at < recent_cutoff
                    )
                )
            
            # Limit for test mode
            if test_mode:
                stmt = stmt.limit(10)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to resolve target segment", error=str(e))
            return []
    
    def _plan_sending_strategy(
        self, 
        limit_info: Dict[str, Any], 
        subscribers: List[Subscriber], 
        broadcast: Broadcast
    ) -> Dict[str, Any]:
        """Plan sending strategy."""
        available_slots = limit_info["remaining"]
        total_subscribers = len(subscribers)
        
        if available_slots >= total_subscribers:
            return {
                "strategy": "send_all",
                "batches_needed": (total_subscribers + self.batch_size - 1) // self.batch_size,
                "send_all_now": True
            }
        else:
            return {
                "strategy": "partial_send_queue_rest",
                "batches_needed": (available_slots + self.batch_size - 1) // self.batch_size,
                "send_now": available_slots,
                "queue_count": total_subscribers - available_slots,
                "send_all_now": False
            }
    
    def _calculate_batches(self, subscriber_count: int, available_limit: int) -> int:
        """Calculate number of batches needed."""
        sendable_count = min(subscriber_count, available_limit)
        return (sendable_count + self.batch_size - 1) // self.batch_size
    
    async def _process_broadcast_batches(
        self, 
        broadcast: Broadcast, 
        subscribers: List[Subscriber], 
        plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process broadcast in batches."""
        results = {
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": [],
            "queued_count": 0
        }
        
        strategy = plan["sending_strategy"]
        
        if strategy["send_all_now"]:
            # Send to all subscribers
            batch_results = await self._send_to_all_subscribers(
                broadcast, subscribers
            )
            results.update(batch_results)
        else:
            # Send to available limit, queue the rest
            available_subscribers = subscribers[:strategy["send_now"]]
            queued_subscribers = subscribers[strategy["send_now"]:]
            
            # Send available batch
            batch_results = await self._send_to_all_subscribers(
                broadcast, available_subscribers
            )
            results.update(batch_results)
            
            # Queue the rest
            results["queued_count"] = len(queued_subscribers)
            await self._queue_overflow_subscribers(broadcast, queued_subscribers)
        
        # Update broadcast metrics
        broadcast.recipient_count = len(subscribers)
        broadcast.sent_count = results["sent_count"]
        broadcast.delivered_count = results["sent_count"]  # Will be updated by webhooks
        
        return results
    
    async def _send_to_all_subscribers(
        self, 
        broadcast: Broadcast, 
        subscribers: List[Subscriber]
    ) -> Dict[str, Any]:
        """Send broadcast to all subscribers in batches."""
        results = {
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": []
        }
        
        # Process in batches
        for i in range(0, len(subscribers), self.batch_size):
            batch = subscribers[i:i + self.batch_size]
            
            # Check daily limit before each batch
            limit_info = await self._check_daily_limit()
            if not limit_info["within_limit"]:
                results["skipped_count"] += len(batch)
                continue
            
            # Send batch
            batch_results = await self._send_batch(broadcast, batch)
            
            results["sent_count"] += batch_results["sent_count"]
            results["failed_count"] += batch_results["failed_count"]
            results["errors"].extend(batch_results["errors"])
            
            # Rate limiting between batches
            if i + self.batch_size < len(subscribers):
                await asyncio.sleep(60 / self.send_rate_limit)  # Rate limiting
        
        return results
    
    async def _send_batch(
        self, 
        broadcast: Broadcast, 
        subscribers: List[Subscriber]
    ) -> Dict[str, Any]:
        """Send broadcast to a batch of subscribers."""
        results = {
            "sent_count": 0,
            "failed_count": 0,
            "errors": []
        }
        
        for subscriber in subscribers:
            try:
                success = await self._send_broadcast_email(broadcast, subscriber)
                
                if success:
                    results["sent_count"] += 1
                else:
                    results["failed_count"] += 1
                
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append(f"Subscriber {subscriber.id}: {str(e)}")
                logger.error("Failed to send broadcast email", 
                           subscriber_id=subscriber.id, 
                           broadcast_id=broadcast.id,
                           error=str(e))
        
        return results
    
    async def _send_broadcast_email(
        self, 
        broadcast: Broadcast, 
        subscriber: Subscriber
    ) -> bool:
        """Send broadcast email to individual subscriber."""
        try:
            # Render email template
            context = {
                "subscriber": subscriber,
                "broadcast": broadcast,
                "unsubscribe_url": f"{self.template_engine.base_url}/unsubscribe?email={subscriber.email}&broadcast={broadcast.id}"
            }
            
            rendered = await self.template_engine.render_email(
                broadcast.template_name or "newsletter",
                context,
                subscriber,
                broadcast.preview_text
            )
            
            # Create email log
            email_log = EmailLog(
                subscriber_id=subscriber.id,
                broadcast_id=broadcast.id,
                email_type=EmailType.BROADCAST,
                subject=broadcast.subject,
                template_name=broadcast.template_name,
                content_html=rendered["html"],
                content_text=rendered["text"],
                status=EmailStatus.QUEUED
            )
            
            self.db.add(email_log)
            await self.db.flush()
            
            # Send via Brevo
            from ...email_core.brevo_client import BrevoEmail
            email_data = BrevoEmail(
                sender={
                    "name": broadcast.sender_name,
                    "email": broadcast.sender_email
                },
                to=[{
                    "name": subscriber.full_name,
                    "email": subscriber.email
                }],
                subject=rendered["subject"],
                htmlContent=rendered["html"],
                textContent=rendered["text"],
                replyTo={
                    "name": broadcast.sender_name,
                    "email": broadcast.reply_to_email or broadcast.sender_email
                } if broadcast.reply_to_email else None,
                tags=[f"broadcast_{broadcast.id}", broadcast.broadcast_type]
            )
            
            result = await self.brevo_client.send_transactional_email(
                email_data, self.redis_client
            )
            
            # Update email log
            email_log.mark_as_sent(result.get("messageId"))
            
            # Update subscriber metrics
            subscriber.increment_email_count()
            
            await self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error("Failed to send broadcast email", 
                       subscriber_id=subscriber.id,
                       broadcast_id=broadcast.id,
                       error=str(e))
            return False
    
    async def _queue_overflow_subscribers(
        self, 
        broadcast: Broadcast, 
        subscribers: List[Subscriber]
    ) -> None:
        """Queue subscribers for next day's sending."""
        try:
            if not self.redis_client:
                logger.warning("No Redis client available, cannot queue overflow")
                return
            
            tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
            queue_key = f"broadcast_queue:{tomorrow}:{broadcast.id}"
            
            # Add subscriber IDs to queue
            subscriber_ids = [str(sub.id) for sub in subscribers]
            
            if subscriber_ids:
                await self.redis_client.lpush(queue_key, *subscriber_ids)
                await self.redis_client.expire(queue_key, 86400 * 2)  # 2 days expiry
                
                logger.info("Queued overflow subscribers", 
                           count=len(subscriber_ids),
                           broadcast_id=str(broadcast.id),
                           send_date=tomorrow)
            
        except Exception as e:
            logger.error("Failed to queue overflow subscribers", error=str(e))
    
    def _get_next_send_suggestions(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get suggestions for next sending."""
        suggestions = []
        
        if results["failed_count"] > 0:
            suggestions.append("Review failed sends for common issues")
        
        if validation["statistics"]["error_rate"] > 0.1:
            suggestions.append("Investigate high error rate - check Brevo configuration")
        
        if results["queued_count"] > 0:
            suggestions.append("Monitor queue for next day's sending")
        
        if results["sent_count"] == 0:
            suggestions.append("Check daily limit and subscriber segment")
        
        return suggestions
