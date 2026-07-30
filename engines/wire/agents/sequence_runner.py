"""
WIRE Sequence Runner Agent

ARQ-based agent for executing email sequences
with 15-minute intervals and daily limit management.
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

from ..models.sequence import Sequence, SequenceStatus, SequenceTrigger
from ..models.sequence_enrollment import SequenceEnrollment, EnrollmentStatus
from ...email_core.models.subscriber import Subscriber, SubscriberStatus
from ...email_core.models.email_log import EmailLog, EmailType, EmailStatus
from ...email_core.template_engine import EmailTemplateEngine
from ...email_core.brevo_client import BrevoClient, get_brevo_client

logger = get_logger(__name__)


class SequenceRunner(AgentBase):
    """
    Email sequence execution agent.
    
    Runs every 15 minutes via ARQ cron to process
    sequence enrollments and send scheduled emails.
    """
    
    agent_name = "sequence_runner"
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
        self.batch_size = 50
        self.max_processing_time = 600  # 10 minutes max per run
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan sequence execution run.
        
        Args:
            input_data: ARQ context and run parameters
            
        Returns:
            Dict with execution plan
        """
        try:
            logger.info("Planning sequence runner execution")
            
            # Check daily limit
            limit_info = await self._check_daily_limit()
            
            # Get active sequences
            active_sequences = await self._get_active_sequences()
            
            # Get pending enrollments
            pending_enrollments = await self._get_pending_enrollments()
            
            # Plan execution batches
            plan = {
                "daily_limit_info": limit_info,
                "active_sequences_count": len(active_sequences),
                "pending_enrollments_count": len(pending_enrollments),
                "can_process": limit_info["remaining"] > 0,
                "batch_size": min(self.batch_size, limit_info["remaining"]),
                "estimated_processing_time": min(
                    len(pending_enrollments) * 2,  # 2 seconds per email estimate
                    self.max_processing_time
                ),
                "execution_strategy": self._plan_execution_strategy(
                    limit_info, active_sequences, pending_enrollments
                )
            }
            
            logger.info("Sequence runner plan created", 
                       can_process=plan["can_process"],
                       pending_enrollments=plan["pending_enrollments_count"])
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan sequence execution", error=str(e))
            raise BaseLayerError(f"Failed to plan sequence execution: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute sequence processing.
        
        Args:
            plan: Execution plan from planning phase
            
        Returns:
            Dict with execution results
        """
        try:
            logger.info("Executing sequence runner")
            
            if not plan["can_process"]:
                return {
                    "status": "skipped",
                    "reason": "Daily limit reached",
                    "processed_count": 0
                }
            
            results = {
                "processed_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "errors": []
            }
            
            # Process enrollments in batches
            batch_size = plan["batch_size"]
            offset = 0
            
            while results["processed_count"] < plan["pending_enrollments_count"]:
                # Get next batch
                enrollments = await self._get_pending_enrollments_batch(
                    limit=batch_size, offset=offset
                )
                
                if not enrollments:
                    break
                
                # Process batch
                batch_results = await self._process_enrollment_batch(enrollments)
                
                # Update results
                results["processed_count"] += len(enrollments)
                results["sent_count"] += batch_results["sent_count"]
                results["failed_count"] += batch_results["failed_count"]
                results["skipped_count"] += batch_results["skipped_count"]
                results["errors"].extend(batch_results["errors"])
                
                # Check if we've hit the daily limit
                current_limit = await self._check_daily_limit()
                if current_limit["remaining"] <= 0:
                    logger.info("Daily limit reached during processing")
                    break
                
                offset += batch_size
                
                # Prevent infinite loops
                if results["processed_count"] >= 1000:  # Safety limit
                    logger.warning("Processing limit reached, stopping execution")
                    break
            
            logger.info("Sequence execution completed", 
                       processed=results["processed_count"],
                       sent=results["sent_count"],
                       failed=results["failed_count"])
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute sequence runner", error=str(e))
            raise BaseLayerError(f"Failed to execute sequence runner: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate execution results.
        
        Args:
            results: Execution results
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating sequence runner results")
            
            validation_errors = []
            
            # Check for reasonable processing counts
            if results["processed_count"] < 0:
                validation_errors.append("Negative processed count")
            
            if results["sent_count"] > results["processed_count"]:
                validation_errors.append("Sent count exceeds processed count")
            
            if results["failed_count"] > results["processed_count"]:
                validation_errors.append("Failed count exceeds processed count")
            
            # Check error rate
            total_processed = results["sent_count"] + results["failed_count"]
            if total_processed > 0:
                error_rate = results["failed_count"] / total_processed
                if error_rate > 0.1:  # More than 10% failure rate
                    validation_errors.append(f"High error rate: {error_rate:.2%}")
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "statistics": {
                    "success_rate": (results["sent_count"] / max(results["processed_count"], 1)) * 100,
                    "error_rate": (results["failed_count"] / max(results["processed_count"], 1)) * 100,
                    "skip_rate": (results["skipped_count"] / max(results["processed_count"], 1)) * 100
                }
            }
            
            logger.info("Sequence runner validation completed", 
                       is_valid=validation_result["is_valid"])
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate sequence runner results", error=str(e))
            raise BaseLayerError(f"Failed to validate sequence runner results: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate execution report.
        
        Args:
            results: Execution results
            validation: Validation results
            
        Returns:
            Dict with execution report
        """
        try:
            logger.info("Generating sequence runner report")
            
            report = {
                "run_id": str(uuid.uuid4()),
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "daily_limit_info": await self._check_daily_limit(),
                "performance_metrics": {
                    "processing_rate": results["processed_count"] / 60,  # Per minute
                    "success_rate": validation["statistics"]["success_rate"],
                    "error_rate": validation["statistics"]["error_rate"]
                },
                "next_run_suggestions": self._get_next_run_suggestions(results, validation),
                "metadata": {
                    "batch_size": self.batch_size,
                    "max_processing_time": self.max_processing_time,
                    "daily_limit": self.daily_limit
                }
            }
            
            logger.info("Sequence runner report generated", 
                       processed=results["processed_count"],
                       success_rate=validation["statistics"]["success_rate"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate sequence runner report", error=str(e))
            raise BaseLayerError(f"Failed to generate sequence runner report: {e}")
    
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
    
    async def _get_active_sequences(self) -> List[Sequence]:
        """Get all active sequences."""
        try:
            stmt = select(Sequence).where(Sequence.status == SequenceStatus.ACTIVE)
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get active sequences", error=str(e))
            return []
    
    async def _get_pending_enrollments(self) -> List[SequenceEnrollment]:
        """Get all pending enrollments."""
        try:
            now = datetime.now(timezone.utc)
            stmt = select(SequenceEnrollment).where(
                and_(
                    SequenceEnrollment.status == EnrollmentStatus.ACTIVE,
                    SequenceEnrollment.next_step_at <= now
                )
            ).order_by(SequenceEnrollment.next_step_at.asc())
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get pending enrollments", error=str(e))
            return []
    
    async def _get_pending_enrollments_batch(self, limit: int, offset: int) -> List[SequenceEnrollment]:
        """Get a batch of pending enrollments."""
        try:
            now = datetime.now(timezone.utc)
            stmt = select(SequenceEnrollment).where(
                and_(
                    SequenceEnrollment.status == EnrollmentStatus.ACTIVE,
                    SequenceEnrollment.next_step_at <= now
                )
            ).order_by(SequenceEnrollment.next_step_at.asc()).limit(limit).offset(offset)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get pending enrollments batch", error=str(e))
            return []
    
    def _plan_execution_strategy(
        self, 
        limit_info: Dict[str, Any], 
        sequences: List[Sequence], 
        enrollments: List[SequenceEnrollment]
    ) -> Dict[str, Any]:
        """Plan execution strategy."""
        return {
            "strategy": "batch_processing",
            "prioritization": "next_step_at",
            "batch_size": min(self.batch_size, limit_info["remaining"]),
            "estimated_batches": (len(enrollments) + min(self.batch_size, limit_info["remaining"]) - 1) // min(self.batch_size, limit_info["remaining"]),
            "time_limit": self.max_processing_time
        }
    
    async def _process_enrollment_batch(self, enrollments: List[SequenceEnrollment]) -> Dict[str, Any]:
        """Process a batch of enrollments."""
        results = {
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": []
        }
        
        for enrollment in enrollments:
            try:
                # Check daily limit before each email
                limit_info = await self._check_daily_limit()
                if not limit_info["within_limit"]:
                    results["skipped_count"] += 1
                    continue
                
                # Process individual enrollment
                success = await self._process_enrollment(enrollment)
                
                if success:
                    results["sent_count"] += 1
                else:
                    results["failed_count"] += 1
                
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append(f"Enrollment {enrollment.id}: {str(e)}")
                logger.error("Failed to process enrollment", 
                           enrollment_id=str(enrollment.id), 
                           error=str(e))
        
        return results
    
    async def _process_enrollment(self, enrollment: SequenceEnrollment) -> bool:
        """Process individual enrollment."""
        try:
            # Get sequence and subscriber
            sequence = await self._get_sequence(enrollment.sequence_id)
            subscriber = await self._get_subscriber(enrollment.subscriber_id)
            
            if not sequence or not subscriber:
                logger.warning("Missing sequence or subscriber", 
                             enrollment_id=str(enrollment.id))
                return False
            
            # Check if subscriber can receive emails
            if not subscriber.can_receive_emails:
                logger.info("Subscriber cannot receive emails", 
                          subscriber_email=subscriber.email)
                enrollment.pause("Subscriber cannot receive emails")
                await self.db.commit()
                return False
            
            # Get current step
            step = sequence.get_step(enrollment.current_step)
            if not step:
                # Sequence complete
                enrollment.complete()
                await self.db.commit()
                logger.info("Sequence completed", 
                          enrollment_id=str(enrollment.id))
                return True
            
            # Send email
            success = await self._send_sequence_email(
                sequence, subscriber, enrollment, step
            )
            
            if success:
                # Update enrollment
                enrollment.mark_step_sent(enrollment.current_step)
                
                # Calculate next step time
                if enrollment.advance_to_next_step():
                    next_time = sequence.get_next_send_time(
                        datetime.now(timezone.utc), 
                        enrollment.current_step
                    )
                    enrollment.next_step_at = next_time
                else:
                    enrollment.complete()
                
                await self.db.commit()
                
                logger.info("Email sent successfully", 
                          enrollment_id=str(enrollment.id),
                          step=enrollment.current_step)
                
                return True
            else:
                results["failed_count"] += 1
                logger.error("Failed to send email", 
                          enrollment_id=str(enrollment.id))
                return False
                
        except Exception as e:
            logger.error("Failed to process enrollment", 
                       enrollment_id=str(enrollment.id), 
                       error=str(e))
            return False
    
    async def _send_sequence_email(
        self, 
        sequence: Sequence, 
        subscriber: Subscriber, 
        enrollment: SequenceEnrollment, 
        step: Dict[str, Any]
    ) -> bool:
        """Send individual sequence email."""
        try:
            # Render email template
            context = {
                "subscriber": subscriber,
                "sequence": sequence,
                "enrollment": enrollment,
                "step": step,
                "unsubscribe_url": f"{self.template_engine.base_url}/unsubscribe?email={subscriber.email}&sequence={sequence.id}"
            }
            
            rendered = await self.template_engine.render_email(
                step.get("template_name", "sequence_email"),
                context,
                subscriber
            )
            
            # Create email log
            email_log = EmailLog(
                subscriber_id=subscriber.id,
                sequence_id=sequence.id,
                email_type=EmailType.SEQUENCE,
                subject=rendered["subject"],
                template_name=step.get("template_name"),
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
                    "name": "Kade Digital",
                    "email": "noreply@example.com"
                },
                to=[{
                    "name": subscriber.full_name,
                    "email": subscriber.email
                }],
                subject=rendered["subject"],
                htmlContent=rendered["html"],
                textContent=rendered["text"],
                tags=[f"sequence_{sequence.id}", f"step_{step['step_number']}"]
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
            logger.error("Failed to send sequence email", 
                       subscriber_id=subscriber.id,
                       sequence_id=sequence.id,
                       error=str(e))
            return False
    
    async def _get_sequence(self, sequence_id: uuid.UUID) -> Optional[Sequence]:
        """Get sequence by ID."""
        try:
            stmt = select(Sequence).where(Sequence.id == sequence_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get sequence", sequence_id=str(sequence_id), error=str(e))
            return None
    
    async def _get_subscriber(self, subscriber_id: uuid.UUID) -> Optional[Subscriber]:
        """Get subscriber by ID."""
        try:
            stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get subscriber", subscriber_id=str(subscriber_id), error=str(e))
            return None
    
    def _get_next_run_suggestions(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get suggestions for next run."""
        suggestions = []
        
        if results["failed_count"] > 0:
            suggestions.append("Review failed enrollments for common issues")
        
        if validation["statistics"]["error_rate"] > 0.05:
            suggestions.append("Investigate high error rate - check Brevo configuration")
        
        if results["skipped_count"] > 0:
            suggestions.append("Consider increasing processing frequency if hitting daily limits")
        
        if results["processed_count"] == 0:
            suggestions.append("No enrollments to process - check sequence configurations")
        
        return suggestions
