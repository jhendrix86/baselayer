"""
BaseLayer Income Engine Tasks

Arq task definitions for background revenue processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ..core.database import db_session_context
from ..models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, TransactionStatus
)
from .engine import RevenueEngine
from .billing import BillingEngine
from .analytics import RevenueAnalytics
from .subscriptions import SubscriptionManager
from .providers import PaymentProviderManager

logger = get_logger(__name__)

# Global instances (will be initialized in startup)
revenue_engine: RevenueEngine = None
billing_engine: BillingEngine = None
revenue_analytics: RevenueAnalytics = None
subscription_manager: SubscriptionManager = None
payment_provider_manager: PaymentProviderManager = None


async def initialize_income_engine():
    """Initialize Income Engine components."""
    global revenue_engine, billing_engine, revenue_analytics
    global subscription_manager, payment_provider_manager
    
    revenue_engine = RevenueEngine()
    billing_engine = BillingEngine(revenue_engine)
    revenue_analytics = RevenueAnalytics()
    subscription_manager = SubscriptionManager(revenue_engine)
    payment_provider_manager = PaymentProviderManager()
    
    # Register payment providers
    stripe_provider = StripeProvider({
        "api_key": "sk_test_...",  # Would come from config
        "webhook_secret": "whsec_...",
        "enabled": True
    })
    payment_provider_manager.register_provider(stripe_provider)
    
    paypal_provider = PayPalProvider({
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "sandbox": True,
        "enabled": True
    })
    payment_provider_manager.register_provider(paypal_provider)
    
    bank_transfer_provider = BankTransferProvider({
        "bank_account": "123456789",
        "enabled": True
    })
    payment_provider_manager.register_provider(bank_transfer_provider)
    
    await billing_engine.start_billing_worker()
    
    logger.info("Income Engine components initialized")


async def shutdown_income_engine():
    """Shutdown Income Engine components."""
    global billing_engine
    
    if billing_engine:
        await billing_engine.stop_billing_worker()
    
    logger.info("Income Engine components shutdown")


async def process_recurring_billing(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process recurring billing.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Billing results
    """
    global billing_engine
    
    if not billing_engine:
        raise RuntimeError("Billing engine not initialized")
    
    try:
        # Schedule billing cycles
        await billing_engine.schedule_billing_cycles()
        
        # Process subscription billing
        subscription_results = await subscription_manager.process_subscription_billing()
        
        # Process regular billing
        billing_results = await billing_engine.process_manual_billing([], 0.0)  # Will be implemented
        
        results = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "subscription_billing": subscription_results,
            "regular_billing": billing_results
        }
        
        logger.info(
            "Recurring billing completed",
            subscription_processed=subscription_results.get("processed_subscriptions", 0),
            subscription_successful=subscription_results.get("successful_billings", 0)
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "Recurring billing task failed",
            error=str(e)
        )
        raise


async def update_revenue_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update revenue metrics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Metrics update result
    """
    global revenue_analytics
    
    if not revenue_analytics:
        raise RuntimeError("Revenue analytics not initialized")
    
    try:
        # Update metrics for all active streams
        async with db_session_context() as session:
            result = await session.execute(
                select(RevenueStream).where(
                    RevenueStream.status == RevenueStatus.ACTIVE,
                    RevenueStream.deleted_at.is_(None)
                )
            )
            streams = result.scalars().all()
        
        updated_streams = 0
        
        for stream in streams:
            try:
                # Calculate metrics for current month
                current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                next_month = current_month + timedelta(days=32)
                
                metrics = await revenue_analytics.get_revenue_overview(
                    current_month, next_month, "day"
                )
                
                # Update metrics in database
                await revenue_engine._update_revenue_metrics(stream.id, None)
                
                updated_streams += 1
                
            except Exception as e:
                logger.error(
                    "Failed to update metrics for stream",
                    stream_id=str(stream.id),
                    error=str(e)
                )
        
        logger.info(
            "Revenue metrics updated",
            updated_streams=updated_streams,
            total_streams=len(streams)
        )
        
        return {
            "status": "completed",
            "updated_streams": updated_streams,
            "total_streams": len(streams),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Metrics update task failed",
            error=str(e)
        )
        raise


async def process_payment_retries(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to retry failed payments.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Retry results
    """
    global billing_engine
    
    if not billing_engine:
        raise RuntimeError("Billing engine not initialized")
    
    try:
        retry_results = await billing_engine.retry_failed_payments(max_retries=3)
        
        logger.info(
            "Payment retries completed",
            total_failed=retry_results.get("total_failed", 0),
            successful_retries=retry_results.get("successful_retries", 0),
            failed_retries=retry_results.get("failed_retries", 0)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            **retry_results
        }
        
    except Exception as e:
        logger.error(
            "Payment retry task failed",
            error=str(e)
        )
        raise


async def generate_revenue_forecasts(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to generate revenue forecasts.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Forecast results
    """
    global revenue_analytics
    
    if not revenue_analytics:
        raise RuntimeError("Revenue analytics not initialized")
    
    try:
        # Generate forecasts for all active streams
        async with db_session_context() as session:
            result = await session.execute(
                select(RevenueStream).where(
                    RevenueStream.status == RevenueStatus.ACTIVE,
                    RevenueStream.deleted_at.is_(None)
                )
            )
            streams = result.scalars().all()
        
        forecasts = {}
        
        for stream in streams:
            try:
                forecast = await revenue_analytics.forecast_revenue(
                    stream_id=str(stream.id),
                    forecast_period=30,
                    model_type="linear_regression"
                )
                
                forecasts[str(stream.id)] = forecast
                
            except Exception as e:
                logger.error(
                    "Failed to generate forecast for stream",
                    stream_id=str(stream.id),
                    error=str(e)
                )
        
        logger.info(
            "Revenue forecasts generated",
            total_streams=len(streams),
            successful_forecasts=len(forecasts)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_streams": len(streams),
            "successful_forecasts": len(forecasts),
            "forecasts": forecasts
        }
        
    except Exception as e:
        logger.error(
            "Forecast generation task failed",
            error=str(e)
        )
        raise


async def cleanup_old_transactions(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old transactions.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup result
    """
    retention_days = 365
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        async with db_session_context() as session:
            # Soft delete old transactions
            result = await session.execute(
                select(RevenueTransaction).where(
                    RevenueTransaction.created_at < cutoff_date,
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            old_transactions = result.scalars().all()
            
            count = 0
            for transaction in old_transactions:
                transaction.soft_delete()
                session.add(transaction)
                count += 1
            
            await session.commit()
            
            logger.info(
                "Old transactions cleaned up",
                count=count,
                retention_days=retention_days
            )
            
            return {
                "status": "completed",
                "cleaned_transactions": count,
                "retention_days": retention_days,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(
            "Cleanup task failed",
            error=str(e)
        )
        raise


async def update_subscription_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update subscription metrics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Metrics update result
    """
    global subscription_manager
    
    if not subscription_manager:
        raise RuntimeError("Subscription manager not initialized")
    
    try:
        # Calculate metrics for current month
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = current_month + timedelta(days=32)
        
        metrics = await subscription_manager.get_subscription_metrics(current_month, next_month)
        
        logger.info(
            "Subscription metrics updated",
            total_subscriptions=metrics["subscriptions"]["total"],
            active_subscriptions=metrics["subscriptions"]["active"],
            mrr=metrics["revenue"]["monthly_recurring_revenue"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(
            "Subscription metrics update failed",
            error=str(e)
        )
        raise


async def check_payment_provider_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check payment provider health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check result
    """
    global payment_provider_manager
    
    if not payment_provider_manager:
        raise RuntimeError("Payment provider manager not initialized")
    
    try:
        provider_status = payment_provider_manager.get_provider_status()
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "providers": provider_status
        }
        
        # Determine overall health
        if provider_status["enabled_providers"] == 0:
            health_status["status"] = "unhealthy"
        elif provider_status["enabled_providers"] < provider_status["total_providers"]:
            health_status["status"] = "degraded"
        
        logger.info(
            "Payment provider health check completed",
            status=health_status["status"],
            enabled_providers=provider_status["enabled_providers"],
            total_providers=provider_status["total_providers"]
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Payment provider health check failed",
            error=str(e)
        )
        raise


# Import provider classes
from .providers import StripeProvider, PayPalProvider, BankTransferProvider

# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 3,  # Optimized for i5-2400
    "queue_name": "income_engine",
    "job_timeout": 1800,  # 30 minutes timeout
}

# Cron jobs
cron_jobs = [
    cron(
        process_recurring_billing,
        hour=0,  # Midnight daily
        minute=5,
    ),
    cron(
        update_revenue_metrics,
        hour=1,  # 1 AM daily
        minute=0,
    ),
    cron(
        process_payment_retries,
        hour=2,  # 2 AM daily
        minute=0,
    ),
    cron(
        generate_revenue_forecasts,
        hour=3,  # 3 AM daily
        minute=0,
    ),
    cron(
        update_subscription_metrics,
        hour=4,  # 4 AM daily
        minute=0,
    ),
    cron(
        cleanup_old_transactions,
        hour=5,  # 5 AM daily
        minute=0,
    ),
    cron(
        check_payment_provider_health,
        minute="*/30",  # Every 30 minutes
    ),
]
