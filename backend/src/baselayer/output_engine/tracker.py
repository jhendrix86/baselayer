"""
BaseLayer Output Tracker

Output tracking and analytics system
for the Output Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.output_engine import (
    OutputTemplate, GeneratedOutput, DeliveryLog,
    TemplateType, OutputStatus, DeliveryStatus
)
from .exceptions import TrackingError

logger = get_logger(__name__)


class OutputTracker:
    """
    Output tracking and analytics system.
    
    Tracks output generation, delivery, and usage
    with comprehensive analytics and reporting.
    """
    
    def __init__(self):
        self.tracking_active: bool = False
        self.tracking_interval: int = 300  # 5 minutes
        self.analytics_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 3600  # 1 hour
        
        # Tracking metrics
        self.tracking_metrics = {
            "total_tracked": 0,
            "generations_tracked": 0,
            "deliveries_tracked": 0,
            "template_usage_tracked": 0
        }
    
    async def start_tracking(self) -> None:
        """Start the tracking system."""
        if self.tracking_active:
            return
        
        self.tracking_active = True
        asyncio.create_task(self._tracking_loop())
        
        logger.info("Output tracking started")
    
    async def stop_tracking(self) -> None:
        """Stop the tracking system."""
        self.tracking_active = False
        logger.info("Output tracking stopped")
    
    async def track_generation(self, output: GeneratedOutput, generation_time: float) -> None:
        """
        Track output generation.
        
        Args:
            output: Generated output
            generation_time: Time taken to generate
        """
        try:
            # Update tracking metrics
            self.tracking_metrics["generations_tracked"] += 1
            self.tracking_metrics["total_tracked"] += 1
            
            # Log generation tracking
            logger.debug(
                "Output generation tracked",
                output_id=str(output.id),
                template_id=str(output.template_id),
                format=output.output_format,
                generation_time=generation_time
            )
            
            # Update template usage
            await self._track_template_usage(output.template_id)
            
        except Exception as e:
            logger.error(
                "Failed to track generation",
                output_id=str(output.id),
                error=str(e)
            )
    
    async def track_delivery(self, delivery_log: DeliveryLog) -> None:
        """
        Track output delivery.
        
        Args:
            delivery_log: Delivery log entry
        """
        try:
            # Update tracking metrics
            self.tracking_metrics["deliveries_tracked"] += 1
            self.tracking_metrics["total_tracked"] += 1
            
            # Log delivery tracking
            logger.debug(
                "Output delivery tracked",
                delivery_id=str(delivery_log.id),
                output_id=str(delivery_log.output_id),
                method=delivery_log.delivery_method.value,
                status=delivery_log.status.value
            )
            
        except Exception as e:
            logger.error(
                "Failed to track delivery",
                delivery_id=str(delivery_log.id),
                error=str(e)
            )
    
    async def get_template_analytics(
        self,
        template_id: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get template usage analytics.
        
        Args:
            template_id: Specific template ID or None for all
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Template analytics
        """
        cache_key = f"template_analytics_{template_id}_{period_start}_{period_end}"
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            async with get_db_session() as session:
                query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
                
                if template_id:
                    query = query.where(GeneratedOutput.template_id == uuid.UUID(template_id))
                
                if period_start:
                    query = query.where(GeneratedOutput.created_at >= period_start)
                
                if period_end:
                    query = query.where(GeneratedOutput.created_at <= period_end)
                
                result = await session.execute(query)
                outputs = result.scalars().all()
                
                # Calculate analytics
                total_outputs = len(outputs)
                successful_outputs = len([o for o in outputs if o.status == OutputStatus.COMPLETED])
                failed_outputs = len([o for o in outputs if o.status == OutputStatus.FAILED])
                
                # Format distribution
                format_counts = {}
                for output in outputs:
                    format_type = output.output_format
                    format_counts[format_type] = format_counts.get(format_type, 0) + 1
                
                # Generation time statistics
                generation_times = [o.generation_time for o in outputs if o.generation_time]
                avg_generation_time = sum(generation_times) / len(generation_times) if generation_times else 0
                min_generation_time = min(generation_times) if generation_times else 0
                max_generation_time = max(generation_times) if generation_times else 0
                
                # Daily usage
                daily_usage = {}
                for output in outputs:
                    date = output.created_at.date().isoformat()
                    daily_usage[date] = daily_usage.get(date, 0) + 1
                
                analytics = {
                    "template_id": template_id,
                    "period": {
                        "start": period_start.isoformat() if period_start else None,
                        "end": period_end.isoformat() if period_end else None
                    },
                    "total_outputs": total_outputs,
                    "successful_outputs": successful_outputs,
                    "failed_outputs": failed_outputs,
                    "success_rate": (successful_outputs / total_outputs * 100) if total_outputs > 0 else 0,
                    "format_distribution": format_counts,
                    "generation_time": {
                        "average": avg_generation_time,
                        "minimum": min_generation_time,
                        "maximum": max_generation_time
                    },
                    "daily_usage": daily_usage,
                    "most_used_format": max(format_counts.items(), key=lambda x: x[1])[0] if format_counts else None
                }
                
                # Cache result
                self._set_cache(cache_key, analytics)
                
                return analytics
                
        except Exception as e:
            raise TrackingError(f"Failed to get template analytics: {str(e)}") from e
    
    async def get_output_analytics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get overall output analytics.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Output analytics
        """
        cache_key = f"output_analytics_{period_start}_{period_end}"
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            async with get_db_session() as session:
                # Get output statistics
                query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
                
                if period_start:
                    query = query.where(GeneratedOutput.created_at >= period_start)
                
                if period_end:
                    query = query.where(GeneratedOutput.created_at <= period_end)
                
                result = await session.execute(query)
                outputs = result.scalars().all()
                
                # Calculate statistics
                total_outputs = len(outputs)
                completed_outputs = len([o for o in outputs if o.status == OutputStatus.COMPLETED])
                failed_outputs = len([o for o in outputs if o.status == OutputStatus.FAILED])
                pending_outputs = len([o for o in outputs if o.status == OutputStatus.PENDING])
                
                # Format distribution
                format_counts = {}
                for output in outputs:
                    format_type = output.output_format
                    format_counts[format_type] = format_counts.get(format_type, 0) + 1
                
                # Template distribution
                template_counts = {}
                for output in outputs:
                    template_id = str(output.template_id)
                    template_counts[template_id] = template_counts.get(template_id, 0) + 1
                
                # Generation time statistics
                generation_times = [o.generation_time for o in outputs if o.generation_time]
                avg_generation_time = sum(generation_times) / len(generation_times) if generation_times else 0
                
                # Hourly usage pattern
                hourly_usage = {}
                for output in outputs:
                    hour = output.created_at.hour
                    hourly_usage[hour] = hourly_usage.get(hour, 0) + 1
                
                # Size statistics
                sizes = [len(output.formatted_output) for o in outputs if o.formatted_output]
                avg_size = sum(sizes) / len(sizes) if sizes else 0
                
                analytics = {
                    "period": {
                        "start": period_start.isoformat() if period_start else None,
                        "end": period_end.isoformat() if period_end else None
                    },
                    "outputs": {
                        "total": total_outputs,
                        "completed": completed_outputs,
                        "failed": failed_outputs,
                        "pending": pending_outputs,
                        "success_rate": (completed_outputs / total_outputs * 100) if total_outputs > 0 else 0
                    },
                    "formats": {
                        "distribution": format_counts,
                        "most_popular": max(format_counts.items(), key=lambda x: x[1])[0] if format_counts else None
                    },
                    "templates": {
                        "distribution": template_counts,
                        "most_used": max(template_counts.items(), key=lambda x: x[1])[0] if template_counts else None
                    },
                    "performance": {
                        "average_generation_time": avg_generation_time,
                        "average_size": avg_size
                    },
                    "usage_patterns": {
                        "hourly_distribution": hourly_usage,
                        "peak_hour": max(hourly_usage.items(), key=lambda x: x[1])[0] if hourly_usage else None
                    }
                }
                
                # Cache result
                self._set_cache(cache_key, analytics)
                
                return analytics
                
        except Exception as e:
            raise TrackingError(f"Failed to get output analytics: {str(e)}") from e
    
    async def get_delivery_analytics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get delivery analytics.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Delivery analytics
        """
        cache_key = f"delivery_analytics_{period_start}_{period_end}"
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            async with get_db_session() as session:
                # Get delivery statistics
                query = select(DeliveryLog).where(DeliveryLog.deleted_at.is_(None))
                
                if period_start:
                    query = query.where(DeliveryLog.created_at >= period_start)
                
                if period_end:
                    query = query.where(DeliveryLog.created_at <= period_end)
                
                result = await session.execute(query)
                deliveries = result.scalars().all()
                
                # Calculate statistics
                total_deliveries = len(deliveries)
                delivered_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.DELIVERED])
                failed_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.FAILED])
                pending_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.PENDING])
                cancelled_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.CANCELLED])
                
                # Method distribution
                method_counts = {}
                for delivery in deliveries:
                    method = delivery.delivery_method.value
                    method_counts[method] = method_counts.get(method, 0) + 1
                
                # Delivery time statistics
                delivery_times = [d.delivery_time for d in deliveries if d.delivery_time]
                avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
                
                # Retry statistics
                retry_counts = {}
                for delivery in deliveries:
                    retry_count = delivery.retry_count
                    retry_counts[retry_count] = retry_counts.get(retry_count, 0) + 1
                
                # Daily delivery pattern
                daily_deliveries = {}
                for delivery in deliveries:
                    date = delivery.created_at.date().isoformat()
                    daily_deliveries[date] = daily_deliveries.get(date, 0) + 1
                
                analytics = {
                    "period": {
                        "start": period_start.isoformat() if period_start else None,
                        "end": period_end.isoformat() if period_end else None
                    },
                    "deliveries": {
                        "total": total_deliveries,
                        "delivered": delivered_deliveries,
                        "failed": failed_deliveries,
                        "pending": pending_deliveries,
                        "cancelled": cancelled_deliveries,
                        "success_rate": (delivered_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
                    },
                    "methods": {
                        "distribution": method_counts,
                        "most_used": max(method_counts.items(), key=lambda x: x[1])[0] if method_counts else None
                    },
                    "performance": {
                        "average_delivery_time": avg_delivery_time,
                        "retry_distribution": retry_counts
                    },
                    "patterns": {
                        "daily_deliveries": daily_deliveries,
                        "peak_day": max(daily_deliveries.items(), key=lambda x: x[1])[0] if daily_deliveries else None
                    }
                }
                
                # Cache result
                self._set_cache(cache_key, analytics)
                
                return analytics
                
        except Exception as e:
            raise TrackingError(f"Failed to get delivery analytics: {str(e)}") from e
    
    async def get_user_analytics(
        self,
        user_id: uuid.UUID,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get user-specific analytics.
        
        Args:
            user_id: User ID
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: User analytics
        """
        cache_key = f"user_analytics_{user_id}_{period_start}_{period_end}"
        
        # Check cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            async with get_db_session() as session:
                # Get user's outputs
                output_query = select(GeneratedOutput).where(
                    GeneratedOutput.created_by == user_id,
                    GeneratedOutput.deleted_at.is_(None)
                )
                
                if period_start:
                    output_query = output_query.where(GeneratedOutput.created_at >= period_start)
                
                if period_end:
                    output_query = output_query.where(GeneratedOutput.created_at <= period_end)
                
                result = await session.execute(output_query)
                user_outputs = result.scalars().all()
                
                # Get user's deliveries
                delivery_query = select(DeliveryLog).where(
                    DeliveryLog.created_by == user_id,
                    DeliveryLog.deleted_at.is_(None)
                )
                
                if period_start:
                    delivery_query = delivery_query.where(DeliveryLog.created_at >= period_start)
                
                if period_end:
                    delivery_query = delivery_query.where(DeliveryLog.created_at <= period_end)
                
                result = await session.execute(delivery_query)
                user_deliveries = result.scalars().all()
                
                # Calculate statistics
                total_outputs = len(user_outputs)
                completed_outputs = len([o for o in user_outputs if o.status == OutputStatus.COMPLETED])
                total_deliveries = len(user_deliveries)
                successful_deliveries = len([d for d in user_deliveries if d.status == DeliveryStatus.DELIVERED])
                
                # Format preferences
                format_counts = {}
                for output in user_outputs:
                    format_type = output.output_format
                    format_counts[format_type] = format_counts.get(format_type, 0) + 1
                
                # Template preferences
                template_counts = {}
                for output in user_outputs:
                    template_id = str(output.template_id)
                    template_counts[template_id] = template_counts.get(template_id, 0) + 1
                
                analytics = {
                    "user_id": str(user_id),
                    "period": {
                        "start": period_start.isoformat() if period_start else None,
                        "end": period_end.isoformat() if period_end else None
                    },
                    "outputs": {
                        "total": total_outputs,
                        "completed": completed_outputs,
                        "success_rate": (completed_outputs / total_outputs * 100) if total_outputs > 0 else 0
                    },
                    "deliveries": {
                        "total": total_deliveries,
                        "successful": successful_deliveries,
                        "success_rate": (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
                    },
                    "preferences": {
                        "formats": format_counts,
                        "templates": template_counts
                    },
                    "activity": {
                        "total_activities": total_outputs + total_deliveries
                    }
                }
                
                # Cache result
                self._set_cache(cache_key, analytics)
                
                return analytics
                
        except Exception as e:
            raise TrackingError(f"Failed to get user analytics: {str(e)}") from e
    
    async def get_tracking_summary(self) -> Dict[str, Any]:
        """
        Get overall tracking summary.
        
        Returns:
            Dict[str, Any]: Tracking summary
        """
        try:
            # Get current statistics
            async with get_db_session() as session:
                # Output counts
                result = await session.execute(
                    select(func.count(GeneratedOutput.id)).where(GeneratedOutput.deleted_at.is_(None))
                )
                total_outputs = result.scalar() or 0
                
                result = await session.execute(
                    select(func.count(DeliveryLog.id)).where(DeliveryLog.deleted_at.is_(None))
                )
                total_deliveries = result.scalar() or 0
                
                # Template counts
                result = await session.execute(
                    select(func.count(OutputTemplate.id)).where(OutputTemplate.deleted_at.is_(None))
                )
                total_templates = result.scalar() or 0
            
            summary = {
                "tracking_active": self.tracking_active,
                "tracking_interval": self.tracking_interval,
                "cache_size": len(self.analytics_cache),
                "cache_ttl": self.cache_ttl,
                "tracking_metrics": self.tracking_metrics,
                "system_stats": {
                    "total_outputs": total_outputs,
                    "total_deliveries": total_deliveries,
                    "total_templates": total_templates
                }
            }
            
            return summary
            
        except Exception as e:
            raise TrackingError(f"Failed to get tracking summary: {str(e)}") from e
    
    async def _tracking_loop(self) -> None:
        """Main tracking loop."""
        while self.tracking_active:
            try:
                # Clean up old cache entries
                await self._cleanup_cache()
                
                # Update tracking metrics
                await self._update_tracking_metrics()
                
                # Sleep before next iteration
                await asyncio.sleep(self.tracking_interval)
                
            except Exception as e:
                logger.error(
                    "Tracking loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _track_template_usage(self, template_id: uuid.UUID) -> None:
        """Track template usage."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(OutputTemplate).where(
                        OutputTemplate.id == template_id,
                        OutputTemplate.deleted_at.is_(None)
                    )
                )
                template = result.scalar_one_or_none()
                
                if template:
                    # Update usage count (would be a separate field in real implementation)
                    # For now, just log the usage
                    logger.debug(
                        "Template usage tracked",
                        template_id=str(template_id),
                        template_name=template.name
                    )
                    
        except Exception as e:
            logger.error(
                "Failed to track template usage",
                template_id=str(template_id),
                error=str(e)
            )
    
    async def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.utcnow()
        
        for key, (timestamp, _) in list(self.analytics_cache.items()):
            if current_time - timestamp > timedelta(seconds=self.cache_ttl):
                del self.analytics_cache[key]
    
    async def _update_tracking_metrics(self) -> None:
        """Update tracking metrics from database."""
        try:
            async with get_db_session() as session:
                # Get current counts
                result = await session.execute(
                    select(func.count(GeneratedOutput.id)).where(GeneratedOutput.deleted_at.is_(None))
                )
                current_generations = result.scalar() or 0
                
                result = await session.execute(
                    select(func.count(DeliveryLog.id)).where(DeliveryLog.deleted_at.is_(None))
                )
                current_deliveries = result.scalar() or 0
                
                # Update metrics if they've changed
                if current_generations > self.tracking_metrics["generations_tracked"]:
                    self.tracking_metrics["generations_tracked"] = current_generations
                
                if current_deliveries > self.tracking_metrics["deliveries_tracked"]:
                    self.tracking_metrics["deliveries_tracked"] = current_deliveries
                
        except Exception as e:
            logger.error(
                "Failed to update tracking metrics",
                error=str(e)
            )
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get analytics result from cache."""
        if key not in self.analytics_cache:
            return None
        
        timestamp, result = self.analytics_cache[key]
        if datetime.utcnow() - timestamp > timedelta(seconds=self.cache_ttl):
            del self.analytics_cache[key]
            return None
        
        return result
    
    def _set_cache(self, key: str, result: Dict[str, Any]) -> None:
        """Set analytics result in cache."""
        self.analytics_cache[key] = (datetime.utcnow(), result)
        
        # Limit cache size
        if len(self.analytics_cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(
                self.analytics_cache.keys(),
                key=lambda k: self.analytics_cache[k][0]
            )[:20]
            
            for old_key in oldest_keys:
                del self.analytics_cache[old_key]
