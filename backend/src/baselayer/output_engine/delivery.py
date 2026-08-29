"""
BaseLayer Output Delivery

Output delivery and distribution system
for the Output Engine subsystem.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.output_engine import (
    GeneratedOutput, DeliveryLog,
    DeliveryStatus, DeliveryMethod
)
from ..models.user import User
from .exceptions import DeliveryError

logger = get_logger(__name__)


class OutputDelivery:
    """
    Output delivery and distribution system.
    
    Handles delivery of generated outputs through multiple channels
    with tracking, retry logic, and error handling.
    """
    
    def __init__(self):
        self.delivery_queue: asyncio.Queue = asyncio.Queue()
        self.delivery_active: bool = False
        self.max_concurrent_deliveries: int = 3  # Optimized for i5-2400
        self.delivery_timeout: int = 300  # 5 minutes
        self.max_retry_attempts: int = 3
        self.retry_delay: int = 60  # seconds
        
        # Delivery configurations
        self.delivery_configs = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "use_tls": True,
                "max_attachment_size": 25 * 1024 * 1024  # 25MB
            },
            "webhook": {
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 5
            },
            "api": {
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 5
            },
            "file": {
                "base_path": "/tmp/outputs",
                "create_dirs": True
            },
            "storage": {
                "provider": "local",
                "bucket": "outputs",
                "encryption": True
            }
        }
        
        # Delivery metrics
        self.delivery_metrics = {
            "total_deliveries": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "retry_attempts": 0,
            "average_delivery_time": 0.0
        }
    
    async def start_delivery_worker(self) -> None:
        """Start the background delivery worker."""
        if self.delivery_active:
            return
        
        self.delivery_active = True
        asyncio.create_task(self._delivery_worker_loop())
        
        logger.info("Output delivery worker started")
    
    async def stop_delivery_worker(self) -> None:
        """Stop the delivery worker."""
        self.delivery_active = False
        logger.info("Output delivery worker stopped")
    
    async def schedule_delivery(
        self,
        output: GeneratedOutput,
        delivery_method: str,
        recipients: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> DeliveryLog:
        """
        Schedule output delivery.
        
        Args:
            output: Generated output to deliver
            delivery_method: Delivery method
            recipients: Delivery recipients
            options: Delivery options
            scheduled_at: When to deliver
            metadata: Additional metadata
            created_by: User who scheduled the delivery
            
        Returns:
            DeliveryLog: Delivery log entry
            
        Raises:
            DeliveryError: If scheduling fails
        """
        try:
            # Validate inputs
            await self._validate_delivery_inputs(output, delivery_method, recipients)
            
            async with db_session_context() as session:
                # Create delivery log
                delivery_log = DeliveryLog(
                    output_id=output.id,
                    delivery_method=DeliveryMethod(delivery_method),
                    recipients=recipients or [],
                    options=options or {},
                    metadata=metadata or {},
                    status=DeliveryStatus.PENDING,
                    scheduled_at=scheduled_at or datetime.utcnow(),
                    created_by=created_by
                )
                
                session.add(delivery_log)
                await session.commit()
                await session.refresh(delivery_log)
                
                # Add to delivery queue
                await self.delivery_queue.put(delivery_log)
                
                logger.info(
                    "Output delivery scheduled",
                    delivery_id=str(delivery_log.id),
                    output_id=str(output.id),
                    method=delivery_method,
                    recipients=recipients
                )
                
                return delivery_log
                
        except Exception as e:
            raise DeliveryError(f"Failed to schedule delivery: {str(e)}") from e
    
    async def deliver_immediately(
        self,
        output: GeneratedOutput,
        delivery_method: str,
        recipients: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> DeliveryLog:
        """
        Deliver output immediately.
        
        Args:
            output: Generated output to deliver
            delivery_method: Delivery method
            recipients: Delivery recipients
            options: Delivery options
            metadata: Additional metadata
            created_by: User who initiated delivery
            
        Returns:
            DeliveryLog: Delivery log entry
            
        Raises:
            DeliveryError: If delivery fails
        """
        try:
            # Create delivery log
            async with db_session_context() as session:
                delivery_log = DeliveryLog(
                    output_id=output.id,
                    delivery_method=DeliveryMethod(delivery_method),
                    recipients=recipients or [],
                    options=options or {},
                    metadata=metadata or {},
                    status=DeliveryStatus.PROCESSING,
                    created_by=created_by
                )
                
                session.add(delivery_log)
                await session.commit()
                await session.refresh(delivery_log)
            
            # Process delivery immediately
            await self._process_delivery(delivery_log)
            
            return delivery_log
            
        except Exception as e:
            raise DeliveryError(f"Failed to deliver immediately: {str(e)}") from e
    
    async def get_delivery_log(
        self,
        delivery_id: str
    ) -> Optional[DeliveryLog]:
        """
        Get a delivery log by ID.
        
        Args:
            delivery_id: Delivery log ID
            
        Returns:
            DeliveryLog: Delivery log or None
        """
        async with db_session_context() as session:
            result = await session.execute(
                select(DeliveryLog).where(
                    DeliveryLog.id == uuid.UUID(delivery_id),
                    DeliveryLog.deleted_at.is_(None)
                )
            )
            return result.scalar_one_or_none()
    
    async def list_delivery_logs(
        self,
        output_id: Optional[str] = None,
        delivery_method: Optional[str] = None,
        status: Optional[DeliveryStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[DeliveryLog]:
        """
        List delivery logs with optional filtering.
        
        Args:
            output_id: Filter by output ID
            delivery_method: Filter by delivery method
            status: Filter by status
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[DeliveryLog]: List of delivery logs
        """
        async with db_session_context() as session:
            query = select(DeliveryLog).where(DeliveryLog.deleted_at.is_(None))
            
            if output_id:
                query = query.where(DeliveryLog.output_id == uuid.UUID(output_id))
            
            if delivery_method:
                query = query.where(DeliveryLog.delivery_method == DeliveryMethod(delivery_method))
            
            if status:
                query = query.where(DeliveryLog.status == status)
            
            query = query.order_by(DeliveryLog.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def retry_delivery(
        self,
        delivery_id: str,
        created_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Retry a failed delivery.
        
        Args:
            delivery_id: Delivery log ID
            created_by: User who initiated retry
            
        Returns:
            bool: True if retry scheduled successfully
        """
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(DeliveryLog).where(
                        DeliveryLog.id == uuid.UUID(delivery_id),
                        DeliveryLog.deleted_at.is_(None)
                    )
                )
                delivery_log = result.scalar_one_or_none()
                
                if not delivery_log:
                    return False
                
                # Check if delivery can be retried
                if delivery_log.status != DeliveryStatus.FAILED:
                    return False
                
                if delivery_log.retry_count >= self.max_retry_attempts:
                    return False
                
                # Update for retry
                delivery_log.status = DeliveryStatus.PENDING
                delivery_log.retry_count += 1
                delivery_log.updated_by = created_by
                delivery_log.updated_at = datetime.utcnow()
                
                session.add(delivery_log)
                await session.commit()
                
                # Add to delivery queue
                await self.delivery_queue.put(delivery_log)
                
                logger.info(
                    "Delivery retry scheduled",
                    delivery_id=delivery_id,
                    retry_count=delivery_log.retry_count
                )
                
                return True
                
        except Exception as e:
            logger.error(
                "Failed to retry delivery",
                delivery_id=delivery_id,
                error=str(e)
            )
            return False
    
    async def cancel_delivery(
        self,
        delivery_id: str,
        cancelled_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Cancel a pending delivery.
        
        Args:
            delivery_id: Delivery log ID
            cancelled_by: User who cancelled the delivery
            
        Returns:
            bool: True if cancelled successfully
        """
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(DeliveryLog).where(
                        DeliveryLog.id == uuid.UUID(delivery_id),
                        DeliveryLog.deleted_at.is_(None)
                    )
                )
                delivery_log = result.scalar_one_or_none()
                
                if not delivery_log:
                    return False
                
                # Check if delivery can be cancelled
                if delivery_log.status not in [DeliveryStatus.PENDING, DeliveryStatus.PROCESSING]:
                    return False
                
                # Update status
                delivery_log.status = DeliveryStatus.CANCELLED
                delivery_log.updated_by = cancelled_by
                delivery_log.updated_at = datetime.utcnow()
                
                session.add(delivery_log)
                await session.commit()
                
                logger.info(
                    "Delivery cancelled",
                    delivery_id=delivery_id,
                    user_id=str(cancelled_by) if cancelled_by else None
                )
                
                return True
                
        except Exception as e:
            logger.error(
                "Failed to cancel delivery",
                delivery_id=delivery_id,
                error=str(e)
            )
            return False
    
    async def get_delivery_statistics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get delivery statistics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Delivery statistics
        """
        async with db_session_context() as session:
            query = select(DeliveryLog).where(DeliveryLog.deleted_at.is_(None))
            
            if period_start:
                query = query.where(DeliveryLog.created_at >= period_start)
            
            if period_end:
                query = query.where(DeliveryLog.created_at <= period_end)
            
            result = await session.execute(query)
            deliveries = result.scalars().all()
            
            # Calculate statistics
            total_deliveries = len(deliveries)
            successful_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.DELIVERED])
            failed_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.FAILED])
            pending_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.PENDING])
            cancelled_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.CANCELLED])
            
            # Get method distribution
            method_counts = {}
            for delivery in deliveries:
                method = delivery.delivery_method.value
                method_counts[method] = method_counts.get(method, 0) + 1
            
            # Get average delivery time
            delivery_times = [d.delivery_time for d in deliveries if d.delivery_time]
            avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
            
            statistics = {
                "period": {
                    "start": period_start.isoformat() if period_start else None,
                    "end": period_end.isoformat() if period_end else None
                },
                "total_deliveries": total_deliveries,
                "successful_deliveries": successful_deliveries,
                "failed_deliveries": failed_deliveries,
                "pending_deliveries": pending_deliveries,
                "cancelled_deliveries": cancelled_deliveries,
                "success_rate": (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0,
                "method_distribution": method_counts,
                "average_delivery_time": avg_delivery_time,
                "delivery_metrics": self.delivery_metrics
            }
            
            return statistics
    
    async def _delivery_worker_loop(self) -> None:
        """Main delivery worker loop."""
        while self.delivery_active:
            try:
                # Get next delivery task
                delivery_log = await asyncio.wait_for(
                    self.delivery_queue.get(),
                    timeout=60.0
                )
                
                await self._process_delivery(delivery_log)
                
            except asyncio.TimeoutError:
                # No delivery tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Delivery worker loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_delivery(self, delivery_log: DeliveryLog) -> None:
        """Process a delivery task."""
        try:
            # Update status to processing
            await self._update_delivery_status(delivery_log, DeliveryStatus.PROCESSING)
            
            # Get output
            async with db_session_context() as session:
                result = await session.execute(
                    select(GeneratedOutput).where(
                        GeneratedOutput.id == delivery_log.output_id,
                        GeneratedOutput.deleted_at.is_(None)
                    )
                )
                output = result.scalar_one_or_none()
                
                if not output:
                    await self._update_delivery_status(
                        delivery_log,
                        DeliveryStatus.FAILED,
                        "Output not found"
                    )
                    return
            
            # Get delivery configuration
            config = self.delivery_configs.get(delivery_log.delivery_method.value, {})
            
            # Process delivery based on method
            start_time = datetime.utcnow()
            
            if delivery_log.delivery_method == DeliveryMethod.EMAIL:
                await self._deliver_email(delivery_log, output, config)
            elif delivery_log.delivery_method == DeliveryMethod.WEBHOOK:
                await self._deliver_webhook(delivery_log, output, config)
            elif delivery_log.delivery_method == DeliveryMethod.API:
                await self._deliver_api(delivery_log, output, config)
            elif delivery_log.delivery_method == DeliveryMethod.FILE:
                await self._deliver_file(delivery_log, output, config)
            elif delivery_log.delivery_method == DeliveryMethod.STORAGE:
                await self._deliver_storage(delivery_log, output, config)
            else:
                raise DeliveryError(f"Unknown delivery method: {delivery_log.delivery_method.value}")
            
            # Calculate delivery time
            delivery_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update status to delivered
            await self._update_delivery_status(
                delivery_log,
                DeliveryStatus.DELIVERED,
                delivery_time=delivery_time
            )
            
            # Update metrics
            self._update_delivery_metrics(True, delivery_time)
            
            logger.info(
                "Delivery completed successfully",
                delivery_id=str(delivery_log.id),
                method=delivery_log.delivery_method.value,
                delivery_time=delivery_time
            )
            
        except Exception as e:
            logger.error(
                "Delivery failed",
                delivery_id=str(delivery_log.id),
                error=str(e)
            )
            
            # Update status to failed
            await self._update_delivery_status(
                delivery_log,
                DeliveryStatus.FAILED,
                str(e)
            )
            
            # Update metrics
            self._update_delivery_metrics(False, 0)
    
    async def _deliver_email(self, delivery_log: DeliveryLog, output: GeneratedOutput, config: Dict[str, Any]) -> None:
        """Deliver output via email."""
        # In a real implementation, this would use SMTP to send emails
        # For now, simulate email delivery
        
        recipients = delivery_log.recipients
        if not recipients:
            raise DeliveryError("No recipients specified for email delivery")
        
        # Simulate email sending
        await asyncio.sleep(1)
        
        # Log delivery details
        logger.info(
            "Email delivery simulated",
            delivery_id=str(delivery_log.id),
            recipients=recipients,
            output_format=output.output_format
        )
    
    async def _deliver_webhook(self, delivery_log: DeliveryLog, output: GeneratedOutput, config: Dict[str, Any]) -> None:
        """Deliver output via webhook."""
        import aiohttp
        
        webhook_url = delivery_log.options.get("webhook_url")
        if not webhook_url:
            raise DeliveryError("No webhook URL specified")
        
        # Prepare payload
        payload = {
            "output_id": str(output.id),
            "format": output.output_format,
            "content": output.formatted_output.decode('utf-8'),
            "metadata": output.metadata,
            "delivery_id": str(delivery_log.id)
        }
        
        # Send webhook
        timeout = config.get("timeout", 30)
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=timeout) as response:
                if response.status not in [200, 201, 202]:
                    raise DeliveryError(f"Webhook failed with status: {response.status}")
        
        logger.info(
            "Webhook delivery completed",
            delivery_id=str(delivery_log.id),
            webhook_url=webhook_url,
            status=response.status
        )
    
    async def _deliver_api(self, delivery_log: DeliveryLog, output: GeneratedOutput, config: Dict[str, Any]) -> None:
        """Deliver output via API call."""
        import aiohttp
        
        api_url = delivery_log.options.get("api_url")
        method = delivery_log.options.get("method", "POST")
        headers = delivery_log.options.get("headers", {})
        
        if not api_url:
            raise DeliveryError("No API URL specified")
        
        # Prepare payload
        payload = {
            "output_id": str(output.id),
            "format": output.output_format,
            "content": output.formatted_output.decode('utf-8'),
            "metadata": output.metadata
        }
        
        # Make API call
        timeout = config.get("timeout", 30)
        async with aiohttp.ClientSession() as session:
            async with session.request(method, api_url, json=payload, headers=headers, timeout=timeout) as response:
                if response.status not in [200, 201, 202]:
                    raise DeliveryError(f"API call failed with status: {response.status}")
        
        logger.info(
            "API delivery completed",
            delivery_id=str(delivery_log.id),
            api_url=api_url,
            method=method,
            status=response.status
        )
    
    async def _deliver_file(self, delivery_log: DeliveryLog, output: GeneratedOutput, config: Dict[str, Any]) -> None:
        """Deliver output to file system."""
        import os
        from pathlib import Path
        
        base_path = config.get("base_path", "/tmp/outputs")
        create_dirs = config.get("create_dirs", True)
        
        # Create directory if needed
        if create_dirs:
            Path(base_path).mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"output_{output.id}_{timestamp}.{output.output_format}"
        file_path = os.path.join(base_path, filename)
        
        # Write file
        with open(file_path, 'wb') as f:
            f.write(output.formatted_output)
        
        logger.info(
            "File delivery completed",
            delivery_id=str(delivery_log.id),
            file_path=file_path,
            size=len(output.formatted_output)
        )
    
    async def _deliver_storage(self, delivery_log: DeliveryLog, output: GeneratedOutput, config: Dict[str, Any]) -> None:
        """Deliver output to storage."""
        # In a real implementation, this would upload to cloud storage
        # For now, simulate storage delivery
        
        provider = config.get("provider", "local")
        bucket = config.get("bucket", "outputs")
        
        # Simulate upload
        await asyncio.sleep(2)
        
        logger.info(
            "Storage delivery simulated",
            delivery_id=str(delivery_log.id),
            provider=provider,
            bucket=bucket,
            size=len(output.formatted_output)
        )
    
    async def _validate_delivery_inputs(
        self,
        output: GeneratedOutput,
        delivery_method: str,
        recipients: Optional[List[str]]
    ) -> None:
        """Validate delivery inputs."""
        if not output:
            raise DeliveryError("Output is required")
        
        if not delivery_method:
            raise DeliveryError("Delivery method is required")
        
        if delivery_method not in [dm.value for dm in DeliveryMethod]:
            raise DeliveryError(f"Unsupported delivery method: {delivery_method}")
        
        # Check method-specific requirements
        if delivery_method == "email" and not recipients:
            raise DeliveryError("Email delivery requires recipients")
        
        if delivery_method == "webhook":
            webhook_url = output.metadata.get("webhook_url")
            if not webhook_url:
                raise DeliveryError("Webhook delivery requires webhook_url in metadata")
    
    async def _update_delivery_status(
        self,
        delivery_log: DeliveryLog,
        status: DeliveryStatus,
        error_message: Optional[str] = None,
        delivery_time: Optional[float] = None
    ) -> None:
        """Update delivery log status."""
        try:
            async with db_session_context() as session:
                delivery_log.status = status
                delivery_log.updated_at = datetime.utcnow()
                
                if error_message:
                    delivery_log.error_message = error_message
                
                if delivery_time is not None:
                    delivery_log.delivery_time = delivery_time
                
                session.add(delivery_log)
                await session.commit()
                
        except Exception as e:
            logger.error(
                "Failed to update delivery status",
                delivery_id=str(delivery_log.id),
                error=str(e)
            )
    
    def _update_delivery_metrics(self, success: bool, delivery_time: float) -> None:
        """Update delivery metrics."""
        self.delivery_metrics["total_deliveries"] += 1
        
        if success:
            self.delivery_metrics["successful_deliveries"] += 1
        else:
            self.delivery_metrics["failed_deliveries"] += 1
        
        # Update average delivery time
        successful = self.delivery_metrics["successful_deliveries"]
        if successful > 0:
            current_avg = self.delivery_metrics["average_delivery_time"]
            self.delivery_metrics["average_delivery_time"] = (
                (current_avg * (successful - 1) + delivery_time) / successful
            )
    
    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        return {
            "delivery_active": self.delivery_active,
            "queue_size": self.delivery_queue.qsize(),
            "max_concurrent_deliveries": self.max_concurrent_deliveries,
            "delivery_timeout": self.delivery_timeout,
            "max_retry_attempts": self.max_retry_attempts,
            "retry_delay": self.retry_delay,
            "delivery_configs": self.delivery_configs,
            "delivery_metrics": self.delivery_metrics
        }
