"""
PULSE Broadcast Scheduler

ARQ cron-based scheduler for recurring broadcasts
with automatic newsletter generation and sending.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..models.broadcast import Broadcast, BroadcastStatus, BroadcastType
from ..agents.broadcast_writer import BroadcastWriter
from ..agents.broadcast_sender import BroadcastSender

logger = get_logger(__name__)


class BroadcastScheduler(AgentBase):
    """
    Broadcast scheduler for recurring newsletters.
    
    Manages ARQ cron jobs for weekly newsletter generation
    and automatic sending with queue management.
    """
    
    agent_name = "broadcast_scheduler"
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
        self.broadcast_writer = BroadcastWriter()
        self.broadcast_sender = BroadcastSender(
            config=config,
            db_session=db_session,
            redis_client=redis_client
        )
        
        # Default scheduling configuration
        self.default_newsletter_day = "tuesday"  # Tuesday 9am EST
        self.default_newsletter_time = "09:00"
        self.default_timezone = "America/New_York"
        
        logger.info("BroadcastScheduler initialized", 
                   newsletter_day=self.default_newsletter_day,
                   newsletter_time=self.default_newsletter_time)
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan broadcast scheduling.
        
        Args:
            input_data: Scheduling parameters and configuration
            
        Returns:
            Dict with scheduling plan
        """
        try:
            logger.info("Planning broadcast scheduling", 
                       schedule_type=input_data.get("schedule_type"))
            
            schedule_type = input_data.get("schedule_type", "weekly_newsletter")
            
            if schedule_type == "weekly_newsletter":
                plan = await self._plan_weekly_newsletter(input_data)
            elif schedule_type == "recurring_broadcast":
                plan = await self._plan_recurring_broadcast(input_data)
            else:
                raise BaseLayerError(f"Unknown schedule type: {schedule_type}")
            
            logger.info("Broadcast scheduling plan created", 
                       schedule_type=schedule_type,
                       next_run=plan.get("next_run_time"))
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan broadcast scheduling", error=str(e))
            raise BaseLayerError(f"Failed to plan broadcast scheduling: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scheduled broadcast generation and sending.
        
        Args:
            plan: Scheduling plan from planning phase
            
        Returns:
            Dict with execution results
        """
        try:
            logger.info("Executing scheduled broadcast", 
                       schedule_type=plan["schedule_type"])
            
            if plan["schedule_type"] == "weekly_newsletter":
                results = await self._execute_weekly_newsletter(plan)
            elif plan["schedule_type"] == "recurring_broadcast":
                results = await self._execute_recurring_broadcast(plan)
            else:
                raise BaseLayerError(f"Unknown schedule type: {plan['schedule_type']}")
            
            logger.info("Scheduled broadcast execution completed", 
                       schedule_type=plan["schedule_type"],
                       broadcast_id=results.get("broadcast_id"))
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute scheduled broadcast", error=str(e))
            raise BaseLayerError(f"Failed to execute scheduled broadcast: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate scheduled broadcast execution results.
        
        Args:
            results: Execution results
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating scheduled broadcast results")
            
            validation_errors = []
            
            # Check for required fields
            if not results.get("broadcast_id"):
                validation_errors.append("Missing broadcast ID")
            
            if not results.get("status"):
                validation_errors.append("Missing execution status")
            
            # Check for successful execution
            if results.get("status") == "failed":
                validation_errors.append("Scheduled broadcast failed")
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "execution_summary": {
                    "broadcast_id": results.get("broadcast_id"),
                    "status": results.get("status"),
                    "generated_at": results.get("generated_at"),
                    "sent_at": results.get("sent_at")
                }
            }
            
            logger.info("Scheduled broadcast validation completed", 
                       is_valid=validation_result["is_valid"])
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate scheduled broadcast results", error=str(e))
            raise BaseLayerError(f"Failed to validate scheduled broadcast results: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate scheduling execution report.
        
        Args:
            results: Execution results
            validation: Validation results
            
        Returns:
            Dict with execution report
        """
        try:
            logger.info("Generating scheduled broadcast report")
            
            report = {
                "schedule_id": str(uuid.uuid4()),
                "schedule_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "next_scheduling": await self._calculate_next_schedule(results),
                "performance_metrics": self._get_performance_metrics(results),
                "recommendations": self._get_scheduling_recommendations(results, validation),
                "metadata": {
                    "schedule_type": results.get("schedule_type"),
                    "newsletter_day": self.default_newsletter_day,
                    "newsletter_time": self.default_newsletter_time
                }
            }
            
            logger.info("Scheduled broadcast report generated", 
                       broadcast_id=results.get("broadcast_id"),
                       status=validation["execution_summary"]["status"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate scheduled broadcast report", error=str(e))
            raise BaseLayerError(f"Failed to generate scheduled broadcast report: {e}")
    
    async def _plan_weekly_newsletter(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan weekly newsletter generation."""
        try:
            # Get configuration
            newsletter_day = input_data.get("newsletter_day", self.default_newsletter_day)
            newsletter_time = input_data.get("newsletter_time", self.default_newsletter_time)
            timezone_str = input_data.get("timezone", self.default_timezone)
            
            # Calculate next run time
            next_run = self._calculate_next_newsletter_time(newsletter_day, newsletter_time, timezone_str)
            
            # Get newsletter content parameters
            content_config = input_data.get("content_config", {})
            default_topics = content_config.get("default_topics", [
                "productivity tips",
                "business strategy", 
                "professional growth",
                "industry insights"
            ])
            
            plan = {
                "schedule_type": "weekly_newsletter",
                "next_run_time": next_run.isoformat(),
                "newsletter_day": newsletter_day,
                "newsletter_time": newsletter_time,
                "timezone": timezone_str,
                "content_config": {
                    "broadcast_type": BroadcastType.NEWSLETTER,
                    "target_audience": "general subscribers",
                    "primary_topic": "weekly insights",
                    "secondary_topics": default_topics,
                    "goals": ["provide value", "maintain engagement", "drive traffic"],
                    "tone": "professional and insightful",
                    "call_to_action": "visit blog or check resources"
                },
                "sending_config": {
                    "segment_filters": {
                        "status": [SubscriberStatus.ACTIVE],
                        "tags": ["newsletter_subscriber"]
                    },
                    "exclusion_filters": {
                        "recently_sent": True
                    },
                    "send_immediately": True,
                    "test_mode": False
                }
            }
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan weekly newsletter", error=str(e))
            raise BaseLayerError(f"Failed to plan weekly newsletter: {e}")
    
    async def _plan_recurring_broadcast(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan recurring broadcast."""
        try:
            # Get configuration
            cron_expression = input_data.get("cron_expression")
            broadcast_template_id = input_data.get("broadcast_template_id")
            
            if not cron_expression:
                raise BaseLayerError("Cron expression required for recurring broadcast")
            
            # Get template broadcast
            template_broadcast = await self._get_broadcast(broadcast_template_id)
            if not template_broadcast:
                raise BaseLayerError(f"Template broadcast not found: {broadcast_template_id}")
            
            plan = {
                "schedule_type": "recurring_broadcast",
                "cron_expression": cron_expression,
                "template_broadcast_id": broadcast_template_id,
                "template_broadcast_name": template_broadcast.name,
                "content_config": {
                    "broadcast_type": template_broadcast.broadcast_type,
                    "target_audience": template_broadcast.segment_filters,
                    "primary_topic": template_broadcast.name,
                    "goals": ["automated communication", "maintain engagement"],
                    "tone": "consistent with template"
                },
                "sending_config": {
                    "segment_filters": template_broadcast.segment_filters,
                    "exclusion_filters": template_broadcast.exclusion_filters,
                    "send_immediately": True,
                    "test_mode": False
                }
            }
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan recurring broadcast", error=str(e))
            raise BaseLayerError(f"Failed to plan recurring broadcast: {e}")
    
    async def _execute_weekly_newsletter(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weekly newsletter generation and sending."""
        try:
            logger.info("Executing weekly newsletter generation")
            
            # Generate newsletter content
            content_plan = plan["content_config"]
            content_plan["name"] = f"Weekly Newsletter - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            
            # Generate content using BroadcastWriter
            writer_context = AgentContext(
                task_id=str(uuid.uuid4()),
                task_type="newsletter_generation",
                input_data=content_plan,
                memory_interface=None,
                config=self.config,
                request_id=str(uuid.uuid4())
            )
            
            writer_plan = await self.broadcast_writer.plan(content_plan)
            generated_content = await self.broadcast_writer.execute(writer_plan)
            content_validation = await self.broadcast_writer.validate(generated_content)
            
            if not content_validation["is_valid"]:
                return {
                    "status": "failed",
                    "error": "Content validation failed",
                    "validation_errors": content_validation["errors"]
                }
            
            # Create broadcast record
            broadcast = await self._create_broadcast_from_content(
                generated_content, plan
            )
            
            # Send newsletter
            sender_input = {
                "broadcast_id": str(broadcast.id),
                "send_immediately": True,
                "test_mode": False
            }
            
            sender_context = AgentContext(
                task_id=str(uuid.uuid4()),
                task_type="newsletter_sending",
                input_data=sender_input,
                memory_interface=None,
                config=self.config,
                request_id=str(uuid.uuid4())
            )
            
            sender_plan = await self.broadcast_sender.plan(sender_input)
            send_results = await self.broadcast_sender.execute(sender_plan)
            
            return {
                "status": "completed",
                "broadcast_id": str(broadcast.id),
                "broadcast_name": broadcast.name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "content_validation": content_validation,
                "send_results": send_results,
                "newsletter_metrics": {
                    "word_count": generated_content.get("word_count", 0),
                    "subject": generated_content.get("subject", ""),
                    "recipient_count": send_results.get("sent_count", 0)
                }
            }
            
        except Exception as e:
            logger.error("Failed to execute weekly newsletter", error=str(e))
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_recurring_broadcast(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute recurring broadcast."""
        try:
            logger.info("Executing recurring broadcast")
            
            # Clone template broadcast
            template_broadcast = await self._get_broadcast(plan["template_broadcast_id"])
            if not template_broadcast:
                raise BaseLayerError(f"Template broadcast not found: {plan['template_broadcast_id']}")
            
            # Create new broadcast from template
            new_broadcast = template_broadcast.clone(
                f"Recurring - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Update with current date
            new_broadcast.content_md = self._update_content_with_date(
                new_broadcast.content_md
            )
            new_broadcast.content_html = self._update_content_with_date(
                new_broadcast.content_html
            )
            
            # Save broadcast
            self.db.add(new_broadcast)
            await self.db.commit()
            
            # Send broadcast
            sender_input = {
                "broadcast_id": str(new_broadcast.id),
                "send_immediately": True,
                "test_mode": False
            }
            
            sender_context = AgentContext(
                task_id=str(uuid.uuid4()),
                task_type="recurring_broadcast_sending",
                input_data=sender_input,
                memory_interface=None,
                config=self.config,
                request_id=str(uuid.uuid4())
            )
            
            sender_plan = await self.broadcast_sender.plan(sender_input)
            send_results = await self.broadcast_sender.execute(sender_plan)
            
            return {
                "status": "completed",
                "broadcast_id": str(new_broadcast.id),
                "broadcast_name": new_broadcast.name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "template_used": plan["template_broadcast_id"],
                "send_results": send_results
            }
            
        except Exception as e:
            logger.error("Failed to execute recurring broadcast", error=str(e))
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _calculate_next_newsletter_time(
        self, 
        newsletter_day: str, 
        newsletter_time: str, 
        timezone_str: str
    ) -> datetime:
        """Calculate next newsletter send time."""
        try:
            import pytz
            
            # Get timezone
            tz = pytz.timezone(timezone_str)
            now = datetime.now(timezone.utc)
            local_now = now.astimezone(tz)
            
            # Parse time
            hour, minute = map(int, newsletter_time.split(':'))
            
            # Find next occurrence of the specified day
            days_of_week = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            target_day = days_of_week[newsletter_day.lower()]
            current_day = local_now.weekday()
            
            # Calculate days to add
            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0 and local_now.hour >= hour:
                days_ahead = 7  # Next week if today has passed
            
            # Calculate next send time
            next_send = local_now + timedelta(days=days_ahead)
            next_send = next_send.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Convert back to UTC
            return next_send.astimezone(timezone.utc)
            
        except Exception as e:
            logger.error("Failed to calculate next newsletter time", error=str(e))
            # Fallback to next week same time
            return datetime.now(timezone.utc) + timedelta(days=7)
    
    async def _create_broadcast_from_content(
        self, 
        content: Dict[str, Any], 
        plan: Dict[str, Any]
    ) -> Broadcast:
        """Create broadcast record from generated content."""
        try:
            broadcast = Broadcast(
                name=content["name"],
                subject=content["subject"],
                preview_text=content.get("preview_text", ""),
                content_md=content["content_md"],
                content_html=content["content_html"],
                content_text=content.get("content_text", ""),
                broadcast_type=content["broadcast_type"],
                segment_filters=plan["sending_config"]["segment_filters"],
                exclusion_filters=plan["sending_config"]["exclusion_filters"],
                status=BroadcastStatus.DRAFT,
                word_count=content.get("word_count", 0),
                reading_time_minutes=content.get("reading_time_minutes", 0),
                campaign_name="Weekly Newsletter",
                campaign_tags=["automated", "newsletter"],
                created_by="broadcast_scheduler"
            )
            
            self.db.add(broadcast)
            await self.db.flush()
            
            return broadcast
            
        except Exception as e:
            logger.error("Failed to create broadcast from content", error=str(e))
            raise BaseLayerError(f"Failed to create broadcast from content: {e}")
    
    async def _get_broadcast(self, broadcast_id: uuid.UUID) -> Optional[Broadcast]:
        """Get broadcast by ID."""
        try:
            stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get broadcast", broadcast_id=str(broadcast_id), error=str(e))
            return None
    
    def _update_content_with_date(self, content: str) -> str:
        """Update content with current date."""
        current_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        current_week = datetime.now(timezone.utc).strftime("%W")
        
        # Replace date placeholders
        content = content.replace("[DATE]", current_date)
        content = content.replace("[WEEK]", f"Week {current_week}")
        content = content.replace("[YEAR]", str(datetime.now(timezone.utc).year))
        
        return content
    
    async def _calculate_next_schedule(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate next scheduling time."""
        try:
            if results["schedule_type"] == "weekly_newsletter":
                next_run = self._calculate_next_newsletter_time(
                    self.default_newsletter_day,
                    self.default_newsletter_time,
                    self.default_timezone
                )
            else:
                # For recurring broadcasts, next run is based on cron
                next_run = datetime.now(timezone.utc) + timedelta(days=1)  # Placeholder
            
            return {
                "next_run_time": next_run.isoformat(),
                "next_run_in_days": (next_run - datetime.now(timezone.utc)).days,
                "next_run_in_hours": (next_run - datetime.now(timezone.utc)).total_seconds() / 3600
            }
            
        except Exception as e:
            logger.error("Failed to calculate next schedule", error=str(e))
            return {
                "next_run_time": None,
                "next_run_in_days": 7,
                "next_run_in_hours": 168
            }
    
    def _get_performance_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Get performance metrics for the execution."""
        return {
            "execution_time": "completed",  # Would track actual time in real implementation
            "success_rate": 100.0 if results.get("status") == "completed" else 0.0,
            "content_quality": results.get("content_validation", {}).get("quality_score", 0.0),
            "delivery_success": results.get("send_results", {}).get("sent_count", 0)
        }
    
    def _get_scheduling_recommendations(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get recommendations for scheduling improvements."""
        recommendations = []
        
        if results.get("status") == "failed":
            recommendations.append("Review error logs and fix issues")
        
        if not validation.get("is_valid"):
            recommendations.append("Address validation errors")
        
        if results.get("send_results", {}).get("failed_count", 0) > 0:
            recommendations.append("Investigate sending failures")
        
        recommendations.append("Monitor engagement metrics after sending")
        recommendations.append("Consider A/B testing subject lines")
        
        return recommendations
