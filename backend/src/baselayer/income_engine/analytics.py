"""
BaseLayer Revenue Analytics

Revenue analytics, forecasting, and reporting system
for the Income Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_
from structlog import get_logger

from ..core.database import db_session_context
from ..models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, TransactionStatus
)
from .exceptions import AnalyticsError

logger = get_logger(__name__)


class RevenueAnalytics:
    """
    Revenue analytics and forecasting engine.
    
    Provides comprehensive revenue analytics, trend analysis,
    and forecasting capabilities with performance optimization.
    """
    
    def __init__(self):
        self.cache_enabled: bool = True
        self.cache_ttl: int = 300  # 5 minutes
        self.analytics_cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self.forecasting_models: Dict[str, Any] = {}
    
    async def get_revenue_overview(
        self,
        period_start: datetime,
        period_end: datetime,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """
        Get revenue overview for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            group_by: Grouping level (day, week, month)
            
        Returns:
            Dict[str, Any]: Revenue overview
        """
        cache_key = f"revenue_overview_{period_start}_{period_end}_{group_by}"
        
        # Check cache
        if self.cache_enabled:
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
        
        async with db_session_context() as session:
            # Build time grouping
            if group_by == "day":
                time_format = func.date_trunc('day', RevenueTransaction.created_at)
            elif group_by == "week":
                time_format = func.date_trunc('week', RevenueTransaction.created_at)
            elif group_by == "month":
                time_format = func.date_trunc('month', RevenueTransaction.created_at)
            else:
                time_format = func.date_trunc('day', RevenueTransaction.created_at)
            
            # Get revenue over time
            result = await session.execute(
                select(
                    time_format.label('period'),
                    func.sum(RevenueTransaction.amount).label('revenue'),
                    func.count(RevenueTransaction.id).label('transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.COMPLETED, True)).label('successful')
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.deleted_at.is_(None)
                ).group_by(time_format).order_by(time_format)
            )
            
            revenue_data = []
            for row in result.all():
                revenue_data.append({
                    "period": row.period.isoformat(),
                    "revenue": float(row.revenue) if row.revenue else 0.0,
                    "transactions": row.transactions,
                    "successful_transactions": row.successful or 0,
                    "success_rate": (row.successful / row.transactions) if row.transactions > 0 else 0.0
                })
            
            # Get total summary
            result = await session.execute(
                select(
                    func.sum(RevenueTransaction.amount).label('total_revenue'),
                    func.count(RevenueTransaction.id).label('total_transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.COMPLETED, True)).label('total_successful')
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            
            total_row = result.first()
            total_revenue = float(total_row.total_revenue) if total_row.total_revenue else 0.0
            total_transactions = total_row.total_transactions or 0
            total_successful = total_row.total_successful or 0
            
            overview = {
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "group_by": group_by
                },
                "summary": {
                    "total_revenue": total_revenue,
                    "total_transactions": total_transactions,
                    "successful_transactions": total_successful,
                    "success_rate": (total_successful / total_transactions) if total_transactions > 0 else 0.0,
                    "average_transaction_value": total_revenue / total_transactions if total_transactions > 0 else 0.0
                },
                "time_series": revenue_data
            }
            
            # Cache result
            if self.cache_enabled:
                self._set_cache(cache_key, overview)
            
            return overview
    
    async def get_revenue_by_stream(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get revenue breakdown by stream.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            List[Dict[str, Any]]: Revenue by stream
        """
        async with db_session_context() as session:
            result = await session.execute(
                select(
                    RevenueStream.id,
                    RevenueStream.name,
                    RevenueStream.revenue_type,
                    func.sum(RevenueTransaction.amount).label('revenue'),
                    func.count(RevenueTransaction.id).label('transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.COMPLETED, True)).label('successful')
                ).join(
                    RevenueTransaction, RevenueStream.id == RevenueTransaction.revenue_stream_id
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.deleted_at.is_(None),
                    RevenueStream.deleted_at.is_(None)
                ).group_by(
                    RevenueStream.id, RevenueStream.name, RevenueStream.revenue_type
                ).order_by(func.sum(RevenueTransaction.amount).desc())
            )
            
            stream_data = []
            for row in result.all():
                stream_data.append({
                    "stream_id": str(row.id),
                    "stream_name": row.name,
                    "revenue_type": row.revenue_type.value,
                    "revenue": float(row.revenue) if row.revenue else 0.0,
                    "transactions": row.transactions,
                    "successful_transactions": row.successful or 0,
                    "success_rate": (row.successful / row.transactions) if row.transactions > 0 else 0.0
                })
            
            return stream_data
    
    async def get_customer_analytics(
        self,
        period_start: datetime,
        period_end: datetime,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get customer analytics.
        
        Args:
            period_start: Start of period
            period_end: End of period
            limit: Maximum number of customers
            
        Returns:
            List[Dict[str, Any]]: Customer analytics
        """
        async with db_session_context() as session:
            result = await session.execute(
                select(
                    RevenueTransaction.customer_id,
                    func.sum(RevenueTransaction.amount).label('total_revenue'),
                    func.count(RevenueTransaction.id).label('transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.COMPLETED, True)).label('successful'),
                    func.min(RevenueTransaction.created_at).label('first_transaction'),
                    func.max(RevenueTransaction.created_at).label('last_transaction')
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.customer_id.is_not(None),
                    RevenueTransaction.deleted_at.is_(None)
                ).group_by(RevenueTransaction.customer_id).order_by(
                    func.sum(RevenueTransaction.amount).desc()
                ).limit(limit)
            )
            
            customer_data = []
            for row in result.all():
                customer_data.append({
                    "customer_id": row.customer_id,
                    "total_revenue": float(row.total_revenue) if row.total_revenue else 0.0,
                    "transactions": row.transactions,
                    "successful_transactions": row.successful or 0,
                    "success_rate": (row.successful / row.transactions) if row.transactions > 0 else 0.0,
                    "average_transaction_value": (float(row.total_revenue) / row.transactions) if row.transactions > 0 else 0.0,
                    "first_transaction": row.first_transaction.isoformat() if row.first_transaction else None,
                    "last_transaction": row.last_transaction.isoformat() if row.last_transaction else None
                })
            
            return customer_data
    
    async def get_revenue_trends(
        self,
        period_start: datetime,
        period_end: datetime,
        comparison_period: str = "previous_period"
    ) -> Dict[str, Any]:
        """
        Get revenue trends with comparisons.
        
        Args:
            period_start: Start of period
            period_end: End of period
            comparison_period: Comparison period type
            
        Returns:
            Dict[str, Any]: Revenue trends
        """
        # Calculate comparison period
        period_duration = period_end - period_start
        
        if comparison_period == "previous_period":
            comparison_start = period_start - period_duration
            comparison_end = period_start
        elif comparison_period == "previous_year":
            comparison_start = period_start - timedelta(days=365)
            comparison_end = period_end - timedelta(days=365)
        else:
            comparison_start = period_start - period_duration
            comparison_end = period_start
        
        # Get current period data
        current_data = await self.get_revenue_overview(period_start, period_end)
        
        # Get comparison period data
        comparison_data = await self.get_revenue_overview(comparison_start, comparison_end)
        
        # Calculate trends
        current_revenue = current_data["summary"]["total_revenue"]
        comparison_revenue = comparison_data["summary"]["total_revenue"]
        
        revenue_change = current_revenue - comparison_revenue
        revenue_change_percent = (revenue_change / comparison_revenue) if comparison_revenue > 0 else 0.0
        
        current_transactions = current_data["summary"]["total_transactions"]
        comparison_transactions = comparison_data["summary"]["total_transactions"]
        
        transactions_change = current_transactions - comparison_transactions
        transactions_change_percent = (transactions_change / comparison_transactions) if comparison_transactions > 0 else 0.0
        
        trends = {
            "period": {
                "current": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "comparison": {
                    "start": comparison_start.isoformat(),
                    "end": comparison_end.isoformat(),
                    "type": comparison_period
                }
            },
            "revenue": {
                "current": current_revenue,
                "comparison": comparison_revenue,
                "change": revenue_change,
                "change_percent": revenue_change_percent,
                "trend": "increasing" if revenue_change_percent > 0.05 else "decreasing" if revenue_change_percent < -0.05 else "stable"
            },
            "transactions": {
                "current": current_transactions,
                "comparison": comparison_transactions,
                "change": transactions_change,
                "change_percent": transactions_change_percent,
                "trend": "increasing" if transactions_change_percent > 0.05 else "decreasing" if transactions_change_percent < -0.05 else "stable"
            },
            "success_rate": {
                "current": current_data["summary"]["success_rate"],
                "comparison": comparison_data["summary"]["success_rate"],
                "change": current_data["summary"]["success_rate"] - comparison_data["summary"]["success_rate"],
                "trend": "improving" if current_data["summary"]["success_rate"] > comparison_data["summary"]["success_rate"] else "declining"
            }
        }
        
        return trends
    
    async def forecast_revenue(
        self,
        stream_id: Optional[str] = None,
        forecast_period: int = 30,  # days
        model_type: str = "linear_regression"
    ) -> Dict[str, Any]:
        """
        Forecast revenue for the next period.
        
        Args:
            stream_id: Optional stream ID to forecast for
            forecast_period: Number of days to forecast
            model_type: Type of forecasting model
            
        Returns:
            Dict[str, Any]: Revenue forecast
        """
        # Get historical data (last 90 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
        
        if stream_id:
            historical_data = await self._get_stream_historical_data(stream_id, start_date, end_date)
        else:
            historical_data = await self._get_total_historical_data(start_date, end_date)
        
        if len(historical_data) < 7:
            raise AnalyticsError("Insufficient historical data for forecasting")
        
        # Generate forecast
        forecast_data = await self._generate_forecast(historical_data, forecast_period, model_type)
        
        return {
            "forecast_period": forecast_period,
            "model_type": model_type,
            "historical_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "data_points": len(historical_data)
            },
            "forecast": forecast_data
        }
    
    async def _get_stream_historical_data(
        self,
        stream_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical revenue data for a stream."""
        async with db_session_context() as session:
            result = await session.execute(
                select(
                    func.date_trunc('day', RevenueTransaction.created_at).label('date'),
                    func.sum(RevenueTransaction.amount).label('revenue')
                ).where(
                    RevenueTransaction.revenue_stream_id == uuid.UUID(stream_id),
                    RevenueTransaction.created_at >= start_date,
                    RevenueTransaction.created_at <= end_date,
                    RevenueTransaction.status == TransactionStatus.COMPLETED,
                    RevenueTransaction.deleted_at.is_(None)
                ).group_by(
                    func.date_trunc('day', RevenueTransaction.created_at)
                ).order_by(
                    func.date_trunc('day', RevenueTransaction.created_at)
                )
            )
            
            return [
                {
                    "date": row.date.isoformat(),
                    "revenue": float(row.revenue) if row.revenue else 0.0
                }
                for row in result.all()
            ]
    
    async def _get_total_historical_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get total historical revenue data."""
        async with db_session_context() as session:
            result = await session.execute(
                select(
                    func.date_trunc('day', RevenueTransaction.created_at).label('date'),
                    func.sum(RevenueTransaction.amount).label('revenue')
                ).where(
                    RevenueTransaction.created_at >= start_date,
                    RevenueTransaction.created_at <= end_date,
                    RevenueTransaction.status == TransactionStatus.COMPLETED,
                    RevenueTransaction.deleted_at.is_(None)
                ).group_by(
                    func.date_trunc('day', RevenueTransaction.created_at)
                ).order_by(
                    func.date_trunc('day', RevenueTransaction.created_at)
                )
            )
            
            return [
                {
                    "date": row.date.isoformat(),
                    "revenue": float(row.revenue) if row.revenue else 0.0
                }
                for row in result.all()
            ]
    
    async def _generate_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_period: int,
        model_type: str
    ) -> List[Dict[str, Any]]:
        """Generate revenue forecast using specified model."""
        if model_type == "linear_regression":
            return await self._linear_regression_forecast(historical_data, forecast_period)
        elif model_type == "moving_average":
            return await self._moving_average_forecast(historical_data, forecast_period)
        elif model_type == "exponential_smoothing":
            return await self._exponential_smoothing_forecast(historical_data, forecast_period)
        else:
            return await self._simple_forecast(historical_data, forecast_period)
    
    async def _linear_regression_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_period: int
    ) -> List[Dict[str, Any]]:
        """Generate forecast using linear regression."""
        import numpy as np
        
        # Extract data
        revenues = [point["revenue"] for point in historical_data]
        
        if len(revenues) < 2:
            return await self._simple_forecast(historical_data, forecast_period)
        
        # Simple linear regression
        x = np.arange(len(revenues))
        y = np.array(revenues)
        
        # Calculate coefficients
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Generate forecast
        forecast = []
        last_date = datetime.fromisoformat(historical_data[-1]["date"])
        
        for i in range(1, forecast_period + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast_value = slope * (len(revenues) + i - 1) + intercept
            
            # Ensure non-negative forecast
            forecast_value = max(0, forecast_value)
            
            forecast.append({
                "date": forecast_date.isoformat(),
                "forecasted_revenue": forecast_value,
                "confidence_interval": {
                    "lower": max(0, forecast_value * 0.8),
                    "upper": forecast_value * 1.2
                }
            })
        
        return forecast
    
    async def _moving_average_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_period: int
    ) -> List[Dict[str, Any]]:
        """Generate forecast using moving average."""
        window_size = min(7, len(historical_data))
        revenues = [point["revenue"] for point in historical_data]
        
        # Calculate moving average
        moving_avg = sum(revenues[-window_size:]) / window_size
        
        forecast = []
        last_date = datetime.fromisoformat(historical_data[-1]["date"])
        
        for i in range(1, forecast_period + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Add some randomness to simulate variation
            import random
            variation = random.uniform(0.9, 1.1)
            forecast_value = moving_avg * variation
            
            forecast.append({
                "date": forecast_date.isoformat(),
                "forecasted_revenue": forecast_value,
                "confidence_interval": {
                    "lower": max(0, forecast_value * 0.7),
                    "upper": forecast_value * 1.3
                }
            })
        
        return forecast
    
    async def _exponential_smoothing_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_period: int
    ) -> List[Dict[str, Any]]:
        """Generate forecast using exponential smoothing."""
        revenues = [point["revenue"] for point in historical_data]
        
        if len(revenues) < 2:
            return await self._simple_forecast(historical_data, forecast_period)
        
        # Simple exponential smoothing
        alpha = 0.3
        smoothed_values = [revenues[0]]
        
        for i in range(1, len(revenues)):
            smoothed = alpha * revenues[i] + (1 - alpha) * smoothed_values[-1]
            smoothed_values.append(smoothed)
        
        # Forecast using last smoothed value
        last_smoothed = smoothed_values[-1]
        
        forecast = []
        last_date = datetime.fromisoformat(historical_data[-1]["date"])
        
        for i in range(1, forecast_period + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Add trend component
            trend = (smoothed_values[-1] - smoothed_values[-2]) if len(smoothed_values) >= 2 else 0
            forecast_value = last_smoothed + trend * i
            
            forecast_value = max(0, forecast_value)
            
            forecast.append({
                "date": forecast_date.isoformat(),
                "forecasted_revenue": forecast_value,
                "confidence_interval": {
                    "lower": max(0, forecast_value * 0.8),
                    "upper": forecast_value * 1.2
                }
            })
        
        return forecast
    
    async def _simple_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_period: int
    ) -> List[Dict[str, Any]]:
        """Generate simple forecast using average of recent data."""
        revenues = [point["revenue"] for point in historical_data]
        avg_revenue = sum(revenues) / len(revenues)
        
        forecast = []
        last_date = datetime.fromisoformat(historical_data[-1]["date"])
        
        for i in range(1, forecast_period + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Add some variation
            import random
            variation = random.uniform(0.9, 1.1)
            forecast_value = avg_revenue * variation
            
            forecast.append({
                "date": forecast_date.isoformat(),
                "forecasted_revenue": forecast_value,
                "confidence_interval": {
                    "lower": max(0, forecast_value * 0.7),
                    "upper": forecast_value * 1.3
                }
            })
        
        return forecast
    
    async def get_performance_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get performance metrics for revenue operations.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Performance metrics
        """
        async with db_session_context() as session:
            # Transaction metrics
            result = await session.execute(
                select(
                    func.count(RevenueTransaction.id).label('total_transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.COMPLETED, True)).label('successful_transactions'),
                    func.count(func.nullif(RevenueTransaction.status != TransactionStatus.FAILED, True)).label('failed_transactions'),
                    func.avg(RevenueTransaction.amount).label('avg_transaction_amount'),
                    func.sum(RevenueTransaction.amount).label('total_revenue')
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            
            transaction_metrics = result.first()
            
            # Stream performance
            result = await session.execute(
                select(
                    func.count(RevenueStream.id).label('total_streams'),
                    func.count(func.nullif(RevenueStream.status != RevenueStatus.ACTIVE, True)).label('active_streams')
                ).where(
                    RevenueStream.deleted_at.is_(None)
                )
            )
            
            stream_metrics = result.first()
            
            # Customer metrics
            result = await session.execute(
                select(
                    func.count(func.distinct(RevenueTransaction.customer_id)).label('unique_customers')
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.customer_id.is_not(None),
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            
            customer_metrics = result.first()
            
            # Calculate derived metrics
            total_transactions = transaction_metrics.total_transactions or 0
            successful_transactions = transaction_metrics.successful_transactions or 0
            total_revenue = float(transaction_metrics.total_revenue) if transaction_metrics.total_revenue else 0.0
            
            metrics = {
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "transactions": {
                    "total": total_transactions,
                    "successful": successful_transactions,
                    "failed": transaction_metrics.failed_transactions or 0,
                    "success_rate": (successful_transactions / total_transactions) if total_transactions > 0 else 0.0,
                    "average_amount": float(transaction_metrics.avg_transaction_amount) if transaction_metrics.avg_transaction_amount else 0.0
                },
                "revenue": {
                    "total": total_revenue,
                    "average_per_transaction": total_revenue / total_transactions if total_transactions > 0 else 0.0,
                    "average_per_day": total_revenue / ((period_end - period_start).days or 1)
                },
                "streams": {
                    "total": stream_metrics.total_streams or 0,
                    "active": stream_metrics.active_streams or 0,
                    "active_rate": (stream_metrics.active_streams / stream_metrics.total_streams) if stream_metrics.total_streams > 0 else 0.0
                },
                "customers": {
                    "unique": customer_metrics.unique_customers or 0,
                    "average_revenue_per_customer": total_revenue / (customer_metrics.unique_customers or 1)
                }
            }
            
            return metrics
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if available and not expired."""
        if key not in self.analytics_cache:
            return None
        
        timestamp, data = self.analytics_cache[key]
        if datetime.utcnow() - timestamp > timedelta(seconds=self.cache_ttl):
            del self.analytics_cache[key]
            return None
        
        return data
    
    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Set data in cache."""
        self.analytics_cache[key] = (datetime.utcnow(), data)
    
    def clear_cache(self) -> None:
        """Clear analytics cache."""
        self.analytics_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "enabled": self.cache_enabled,
            "ttl_seconds": self.cache_ttl,
            "cached_items": len(self.analytics_cache),
            "cache_keys": list(self.analytics_cache.keys())
        }
