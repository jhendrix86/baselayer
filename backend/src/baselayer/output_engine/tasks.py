"""
BaseLayer Output Engine Tasks

Arq task definitions for background output processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.output_engine import (
    OutputTemplate, GeneratedOutput, DeliveryLog,
    OutputStatus, DeliveryStatus
)
from .engine import OutputEngine
from .generator import OutputGenerator
from .delivery import OutputDelivery
from .tracker import OutputTracker

logger = get_logger(__name__)

# Global instances (will be initialized in startup)
output_engine: OutputEngine = None
output_generator: OutputGenerator = None
output_delivery: OutputDelivery = None
output_tracker: OutputTracker = None


async def initialize_output_engine():
    """Initialize Output Engine components."""
    global output_engine, output_generator, output_delivery, output_tracker
    
    output_engine = OutputEngine()
    output_generator = OutputGenerator()
    output_delivery = OutputDelivery()
    output_tracker = OutputTracker()
    
    await output_generator.start_generation_worker()
    await output_delivery.start_delivery_worker()
    await output_tracker.start_tracking()
    
    logger.info("Output Engine components initialized")


async def shutdown_output_engine():
    """Shutdown Output Engine components."""
    global output_generator, output_delivery, output_tracker
    
    if output_generator:
        await output_generator.stop_generation_worker()
    
    if output_delivery:
        await output_delivery.stop_delivery_worker()
    
    if output_tracker:
        await output_tracker.stop_tracking()
    
    logger.info("Output Engine components shutdown")


async def process_scheduled_generations(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process scheduled output generations.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Generation results
    """
    global output_generator
    
    if not output_generator:
        raise RuntimeError("Output generator not initialized")
    
    try:
        # Get pending generations
        async with db_session_context() as session:
            result = await session.execute(
                select(GeneratedOutput).where(
                    GeneratedOutput.status == OutputStatus.PENDING,
                    GeneratedOutput.deleted_at.is_(None)
                ).order_by(GeneratedOutput.priority.desc(), GeneratedOutput.created_at.asc())
                .limit(20)
            )
            pending_outputs = result.scalars().all()
        
        processed = 0
        failed = 0
        
        for output in pending_outputs:
            try:
                # Add to generation queue
                await output_generator.generation_queue.put(output)
                processed += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Failed to queue generation",
                    output_id=str(output.id),
                    error=str(e)
                )
        
        logger.info(
            "Scheduled generations processed",
            total=len(pending_outputs),
            processed=processed,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_generations": len(pending_outputs),
            "processed": processed,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Scheduled generations task failed",
            error=str(e)
        )
        raise


async def process_scheduled_deliveries(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process scheduled output deliveries.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Delivery results
    """
    global output_delivery
    
    if not output_delivery:
        raise RuntimeError("Output delivery not initialized")
    
    try:
        # Get pending deliveries
        async with db_session_context() as session:
            result = await session.execute(
                select(DeliveryLog).where(
                    DeliveryLog.status == DeliveryStatus.PENDING,
                    DeliveryLog.deleted_at.is_(None)
                ).order_by(DeliveryLog.priority.desc(), DeliveryLog.created_at.asc())
                .limit(20)
            )
            pending_deliveries = result.scalars().all()
        
        processed = 0
        failed = 0
        
        for delivery in pending_deliveries:
            try:
                # Add to delivery queue
                await output_delivery.delivery_queue.put(delivery)
                processed += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Failed to queue delivery",
                    delivery_id=str(delivery.id),
                    error=str(e)
                )
        
        logger.info(
            "Scheduled deliveries processed",
            total=len(pending_deliveries),
            processed=processed,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_deliveries": len(pending_deliveries),
            "processed": processed,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Scheduled deliveries task failed",
            error=str(e)
        )
        raise


async def cleanup_old_outputs(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old outputs.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup results
    """
    global output_generator
    
    if not output_generator:
        raise RuntimeError("Output generator not initialized")
    
    try:
        result = await output_generator.cleanup_old_outputs()
        
        logger.info(
            "Old outputs cleaned up",
            result=result
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "cleanup_result": result
        }
        
    except Exception as e:
        logger.error(
            "Output cleanup task failed",
            error=str(e)
        )
        raise


async def update_output_analytics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update output analytics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Analytics update result
    """
    global output_tracker
    
    if not output_tracker:
        raise RuntimeError("Output tracker not initialized")
    
    try:
        # Get recent analytics
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=7)
        
        output_analytics = await output_tracker.get_output_analytics(period_start, period_end)
        delivery_analytics = await output_tracker.get_delivery_analytics(period_start, period_end)
        
        logger.info(
            "Output analytics updated",
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_outputs=output_analytics.get("outputs", {}).get("total", 0),
            total_deliveries=delivery_analytics.get("deliveries", {}).get("total", 0)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "output_analytics": output_analytics,
            "delivery_analytics": delivery_analytics
        }
        
    except Exception as e:
        logger.error(
            "Output analytics update failed",
            error=str(e)
        )
        raise


async def optimize_template_cache(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to optimize template cache.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cache optimization result
    """
    global output_engine
    
    if not output_engine:
        raise RuntimeError("Output engine not initialized")
    
    try:
        # Clear old cache entries
        output_engine.clear_cache()
        
        # Pre-cache frequently used templates
        async with db_session_context() as session:
            result = await session.execute(
                select(OutputTemplate).where(
                    OutputTemplate.status == "active",
                    OutputTemplate.deleted_at.is_(None)
                ).order_by(
                    # In real implementation, would order by usage frequency
                    OutputTemplate.created_at.desc()
                ).limit(50)
            )
            templates = result.scalars().all()
        
        cached_count = 0
        for template in templates:
            try:
                output_engine._cache_template(template)
                cached_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to cache template",
                    template_id=str(template.id),
                    error=str(e)
                )
        
        logger.info(
            "Template cache optimized",
            total_templates=len(templates),
            cached=cached_count
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_templates": len(templates),
            "cached_templates": cached_count,
            "cache_size": len(output_engine.template_cache)
        }
        
    except Exception as e:
        logger.error(
            "Template cache optimization failed",
            error=str(e)
        )
        raise


async def check_output_system_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check output system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check result
    """
    try:
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check output engine
        global output_engine
        if output_engine:
            engine_stats = output_engine.get_engine_stats()
            health_status["checks"]["output_engine"] = {
                "status": "healthy",
                "template_cache_size": engine_stats["template_cache_size"],
                "output_cache_size": engine_stats["output_cache_size"],
                "generation_metrics": engine_stats["generation_metrics"]
            }
        else:
            health_status["checks"]["output_engine"] = {
                "status": "error",
                "message": "Output engine not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check output generator
        global output_generator
        if output_generator:
            generator_stats = output_generator.get_generator_stats()
            health_status["checks"]["output_generator"] = {
                "status": "healthy",
                "generation_active": generator_stats["generation_active"],
                "queue_size": generator_stats["queue_size"],
                "generation_metrics": generator_stats["generation_metrics"]
            }
        else:
            health_status["checks"]["output_generator"] = {
                "status": "error",
                "message": "Output generator not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check output delivery
        global output_delivery
        if output_delivery:
            delivery_stats = output_delivery.get_delivery_stats()
            health_status["checks"]["output_delivery"] = {
                "status": "healthy",
                "delivery_active": delivery_stats["delivery_active"],
                "queue_size": delivery_stats["queue_size"],
                "delivery_metrics": delivery_stats["delivery_metrics"]
            }
        else:
            health_status["checks"]["output_delivery"] = {
                "status": "error",
                "message": "Output delivery not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check output tracker
        global output_tracker
        if output_tracker:
            tracker_summary = await output_tracker.get_tracking_summary()
            health_status["checks"]["output_tracker"] = {
                "status": "healthy",
                "tracking_active": tracker_summary["tracking_active"],
                "cache_size": tracker_summary["cache_size"],
                "tracking_metrics": tracker_summary["tracking_metrics"]
            }
        else:
            health_status["checks"]["output_tracker"] = {
                "status": "error",
                "message": "Output tracker not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check database connectivity
        try:
            async with db_session_context() as session:
                await session.execute("SELECT 1")
                health_status["checks"]["database"] = {
                    "status": "healthy"
                }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Determine overall status
        component_statuses = [
            check["status"] for check in health_status["checks"].values()
        ]
        
        if any(status == "unhealthy" for status in component_statuses):
            health_status["status"] = "unhealthy"
        elif any(status == "degraded" for status in component_statuses):
            health_status["status"] = "degraded"
        
        logger.info(
            "Output system health check completed",
            status=health_status["status"]
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Output system health check failed",
            error=str(e)
        )
        raise


async def process_template_maintenance(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to perform template maintenance.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Maintenance results
    """
    try:
        maintenance_results = {
            "validated_templates": 0,
            "invalid_templates": 0,
            "optimized_templates": 0,
            "archived_templates": 0
        }
        
        async with db_session_context() as session:
            result = await session.execute(
                select(OutputTemplate).where(
                    OutputTemplate.deleted_at.is_(None)
                )
            )
            templates = result.scalars().all()
        
        global output_engine
        if output_engine:
            for template in templates:
                try:
                    # Validate template
                    validation_result = await output_engine.renderer.validate_template(template)
                    
                    if validation_result["valid"]:
                        maintenance_results["validated_templates"] += 1
                    else:
                        maintenance_results["invalid_templates"] += 1
                        logger.warning(
                            "Template validation failed",
                            template_id=str(template.id),
                            errors=validation_result["errors"]
                        )
                    
                except Exception as e:
                    logger.error(
                        "Template maintenance failed",
                        template_id=str(template.id),
                        error=str(e)
                    )
        
        logger.info(
            "Template maintenance completed",
            results=maintenance_results
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "maintenance_results": maintenance_results
        }
        
    except Exception as e:
        logger.error(
            "Template maintenance task failed",
            error=str(e)
        )
        raise


# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 3,  # Optimized for i5-2400
    "queue_name": "output_engine",
    "job_timeout": 1800,  # 30 minutes timeout
}

# Cron jobs
cron_jobs = [
    cron(
        process_scheduled_generations,
        minute="*/2",  # Every 2 minutes
    ),
    cron(
        process_scheduled_deliveries,
        minute="*/2",  # Every 2 minutes
    ),
    cron(
        cleanup_old_outputs,
        hour=3,  # 3 AM daily
        minute=0,
    ),
    cron(
        update_output_analytics,
        hour=4,  # 4 AM daily
        minute=0,
    ),
    cron(
        optimize_template_cache,
        hour=5,  # 5 AM daily
        minute=0,
    ),
    cron(
        process_template_maintenance,
        hour=6,  # 6 AM daily
        minute=0,
    ),
    cron(
        check_output_system_health,
        minute="*/15",  # Every 15 minutes
    ),
]
