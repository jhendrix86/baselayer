"""
BaseLayer Billing Engine

Automated billing cycles, invoice generation, and payment processing
for the Income Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.income_engine import (
    RevenueStream, RevenueTransaction, RevenueMetrics,
    RevenueType, RevenueStatus, TransactionStatus
)
from ..models.user import User
from .engine import RevenueEngine
from .exceptions import BillingError, PaymentError

logger = get_logger(__name__)


class BillingEngine:
    """
    Automated billing engine for revenue streams.
    
    Handles billing cycles, invoice generation, and payment processing
    with retry logic and compliance tracking.
    """
    
    def __init__(self, revenue_engine: RevenueEngine):
        self.revenue_engine = revenue_engine
        self.billing_queue: asyncio.Queue = asyncio.Queue()
        self.invoice_queue: asyncio.Queue = asyncio.Queue()
        self.payment_queue: asyncio.Queue = asyncio.Queue()
        self.billing_active: bool = False
        self.max_concurrent_billing: int = 3  # Optimized for i5-2400
    
    async def start_billing_worker(self) -> None:
        """Start the background billing worker."""
        if self.billing_active:
            return
        
        self.billing_active = True
        asyncio.create_task(self._billing_worker_loop())
        
        logger.info("Billing worker started")
    
    async def stop_billing_worker(self) -> None:
        """Stop the billing worker."""
        self.billing_active = False
        logger.info("Billing worker stopped")
    
    async def _billing_worker_loop(self) -> None:
        """Main billing worker loop."""
        while self.billing_active:
            try:
                # Process billing queue
                billing_task = await asyncio.wait_for(
                    self.billing_queue.get(),
                    timeout=60.0
                )
                await self._process_billing_task(billing_task)
                
            except asyncio.TimeoutError:
                # No billing tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Billing worker error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def schedule_billing_cycles(self) -> None:
        """Schedule all active billing cycles."""
        async with db_session_context() as session:
            # Get all active subscription revenue streams
            result = await session.execute(
                select(RevenueStream).where(
                    RevenueStream.revenue_type == RevenueType.SUBSCRIPTION,
                    RevenueStream.status == RevenueStatus.ACTIVE,
                    RevenueStream.billing_cycle.is_not(None),
                    RevenueStream.deleted_at.is_(None)
                )
            )
            streams = result.scalars().all()
            
            for stream in streams:
                await self._schedule_stream_billing(stream)
    
    async def _schedule_stream_billing(self, stream: RevenueStream) -> None:
        """
        Schedule billing for a specific revenue stream.
        
        Args:
            stream: Revenue stream to schedule billing for
        """
        billing_cycle = stream.billing_cycle
        next_billing_date = self._calculate_next_billing_date(stream, billing_cycle)
        
        if next_billing_date <= datetime.utcnow():
            # Queue for immediate billing
            billing_task = {
                "stream_id": str(stream.id),
                "billing_cycle": billing_cycle,
                "scheduled_date": next_billing_date,
                "type": "subscription_billing"
            }
            await self.billing_queue.put(billing_task)
            
            logger.info(
                "Billing task queued",
                stream_id=str(stream.id),
                billing_cycle=billing_cycle,
                scheduled_date=next_billing_date.isoformat()
            )
    
    def _calculate_next_billing_date(
        self,
        stream: RevenueStream,
        billing_cycle: str
    ) -> datetime:
        """
        Calculate the next billing date for a stream.
        
        Args:
            stream: Revenue stream
            billing_cycle: Billing cycle
            
        Returns:
            datetime: Next billing date
        """
        now = datetime.utcnow()
        
        if billing_cycle == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        elif billing_cycle == "weekly":
            days_until_monday = (7 - now.weekday()) % 7
            return (now + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        
        elif billing_cycle == "monthly":
            # First day of next month
            if now.month == 12:
                return datetime(now.year + 1, 1, 1)
            else:
                return datetime(now.year, now.month + 1, 1)
        
        elif billing_cycle == "quarterly":
            # First day of next quarter
            current_quarter = (now.month - 1) // 3
            next_quarter_month = (current_quarter + 1) * 3 + 1
            
            if next_quarter_month > 12:
                return datetime(now.year + 1, 1, 1)
            else:
                return datetime(now.year, next_quarter_month, 1)
        
        elif billing_cycle == "yearly":
            # First day of next year
            return datetime(now.year + 1, 1, 1)
        
        else:
            # Default to monthly
            return datetime(now.year, now.month + 1, 1)
    
    async def _process_billing_task(self, billing_task: Dict[str, Any]) -> None:
        """
        Process a billing task.
        
        Args:
            billing_task: Billing task to process
        """
        try:
            stream_id = billing_task["stream_id"]
            task_type = billing_task["type"]
            
            if task_type == "subscription_billing":
                await self._process_subscription_billing(stream_id)
            else:
                logger.warning(
                    "Unknown billing task type",
                    task_type=task_type,
                    stream_id=stream_id
                )
                
        except Exception as e:
            logger.error(
                "Billing task processing failed",
                billing_task=billing_task,
                error=str(e)
            )
    
    async def _process_subscription_billing(self, stream_id: str) -> None:
        """
        Process subscription billing for a revenue stream.
        
        Args:
            stream_id: Revenue stream ID
        """
        # Get revenue stream
        stream = await self.revenue_engine.get_revenue_stream(stream_id)
        if not stream:
            logger.error(
                "Revenue stream not found for billing",
                stream_id=stream_id
            )
            return
        
        # Get active customers for this stream
        customers = await self._get_active_customers(stream_id)
        
        # Process billing for each customer
        semaphore = asyncio.Semaphore(self.max_concurrent_billing)
        
        async def bill_customer(customer_id: str):
            async with semaphore:
                await self._bill_customer(stream, customer_id)
        
        tasks = [bill_customer(customer["customer_id"]) for customer in customers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Schedule next billing
        await self._schedule_stream_billing(stream)
        
        logger.info(
            "Subscription billing completed",
            stream_id=stream_id,
            customers_billed=len(customers)
        )
    
    async def _get_active_customers(self, stream_id: str) -> List[Dict[str, Any]]:
        """
        Get active customers for a revenue stream.
        
        Args:
            stream_id: Revenue stream ID
            
        Returns:
            List[Dict[str, Any]]: List of active customers
        """
        # In real implementation, this would query customer subscriptions
        # For now, return mock data
        return [
            {"customer_id": "cust_001", "tier": "basic"},
            {"customer_id": "cust_002", "tier": "pro"},
            {"customer_id": "cust_003", "tier": "enterprise"},
        ]
    
    async def _bill_customer(
        self,
        stream: RevenueStream,
        customer_id: str
    ) -> None:
        """
        Bill a specific customer.
        
        Args:
            stream: Revenue stream
            customer_id: Customer ID
        """
        try:
            # Get customer's current plan/tier
            customer_info = await self._get_customer_info(customer_id)
            
            # Calculate billing amount
            billing_amount = await self._calculate_billing_amount(stream, customer_info)
            
            # Create transaction
            transaction = await self.revenue_engine.process_transaction(
                revenue_stream_id=str(stream.id),
                amount=billing_amount,
                customer_id=customer_id,
                payment_method=customer_info.get("payment_method"),
                metadata={
                    "billing_cycle": stream.billing_cycle,
                    "customer_tier": customer_info.get("tier"),
                    "billing_date": datetime.utcnow().isoformat()
                }
            )
            
            # Generate invoice
            await self._generate_invoice(transaction, customer_info)
            
            # Send notification
            await self._send_billing_notification(transaction, customer_info)
            
            logger.info(
                "Customer billed successfully",
                stream_id=str(stream.id),
                customer_id=customer_id,
                amount=billing_amount,
                transaction_id=transaction.transaction_id
            )
            
        except Exception as e:
            logger.error(
                "Customer billing failed",
                stream_id=str(stream.id),
                customer_id=customer_id,
                error=str(e)
            )
            
            # Create failed transaction record
            try:
                await self.revenue_engine.process_transaction(
                    revenue_stream_id=str(stream.id),
                    amount=0.0,
                    customer_id=customer_id,
                    metadata={
                        "billing_cycle": stream.billing_cycle,
                        "error": str(e),
                        "billing_date": datetime.utcnow().isoformat()
                    }
                )
            except Exception as transaction_error:
                logger.error(
                    "Failed to create error transaction",
                    customer_id=customer_id,
                    error=str(transaction_error)
                )
    
    async def _get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer information.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dict[str, Any]: Customer information
        """
        # In real implementation, this would query customer database
        # For now, return mock data
        mock_customers = {
            "cust_001": {
                "customer_id": "cust_001",
                "name": "John Doe",
                "email": "john@example.com",
                "tier": "basic",
                "payment_method": "credit_card",
                "billing_address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip": "12345",
                    "country": "US"
                }
            },
            "cust_002": {
                "customer_id": "cust_002",
                "name": "Jane Smith",
                "email": "jane@example.com",
                "tier": "pro",
                "payment_method": "paypal",
                "billing_address": {
                    "street": "456 Oak Ave",
                    "city": "Somecity",
                    "state": "NY",
                    "zip": "67890",
                    "country": "US"
                }
            },
            "cust_003": {
                "customer_id": "cust_003",
                "name": "Acme Corp",
                "email": "billing@acme.com",
                "tier": "enterprise",
                "payment_method": "bank_transfer",
                "billing_address": {
                    "street": "789 Business Blvd",
                    "city": "Metropolis",
                    "state": "TX",
                    "zip": "10112",
                    "country": "US"
                }
            }
        }
        
        return mock_customers.get(customer_id, {
            "customer_id": customer_id,
            "name": "Unknown Customer",
            "email": "unknown@example.com",
            "tier": "basic",
            "payment_method": "credit_card"
        })
    
    async def _calculate_billing_amount(
        self,
        stream: RevenueStream,
        customer_info: Dict[str, Any]
    ) -> float:
        """
        Calculate billing amount for a customer.
        
        Args:
            stream: Revenue stream
            customer_info: Customer information
            
        Returns:
            float: Billing amount
        """
        if stream.pricing_model.name == "FIXED":
            return stream.base_amount
        
        elif stream.pricing_model.name == "TIERED":
            usage_limits = stream.usage_limits or {}
            tiers = usage_limits.get("tiers", [])
            customer_tier = customer_info.get("tier", "basic")
            
            for tier in tiers:
                if tier.get("name") == customer_tier:
                    return tier.get("price", stream.base_amount)
            
            # Default to base amount
            return stream.base_amount
        
        else:
            return stream.base_amount
    
    async def _generate_invoice(
        self,
        transaction: RevenueTransaction,
        customer_info: Dict[str, Any]
    ) -> None:
        """
        Generate invoice for a transaction.
        
        Args:
            transaction: Transaction
            customer_info: Customer information
        """
        invoice_data = {
            "invoice_id": str(uuid.uuid4()),
            "transaction_id": transaction.transaction_id,
            "customer_id": transaction.customer_id,
            "customer_name": customer_info.get("name"),
            "customer_email": customer_info.get("email"),
            "amount": transaction.amount,
            "currency": transaction.currency,
            "billing_date": datetime.utcnow().isoformat(),
            "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "billing_address": customer_info.get("billing_address", {}),
            "items": [
                {
                    "description": f"Subscription - {customer_info.get('tier', 'Basic')}",
                    "quantity": 1,
                    "unit_price": transaction.amount,
                    "total": transaction.amount
                }
            ],
            "subtotal": transaction.amount,
            "tax": 0.0,  # Calculate tax based on location
            "total": transaction.amount,
            "status": "pending"
        }
        
        # Queue invoice for processing
        await self.invoice_queue.put(invoice_data)
        
        logger.info(
            "Invoice generated",
            invoice_id=invoice_data["invoice_id"],
            transaction_id=transaction.transaction_id,
            amount=transaction.amount
        )
    
    async def _send_billing_notification(
        self,
        transaction: RevenueTransaction,
        customer_info: Dict[str, Any]
    ) -> None:
        """
        Send billing notification to customer.
        
        Args:
            transaction: Transaction
            customer_info: Customer information
        """
        notification_data = {
            "type": "billing_notification",
            "customer_id": customer_info["customer_id"],
            "customer_email": customer_info.get("email"),
            "subject": f"Payment Processed - ${transaction.amount:.2f}",
            "template": "billing_success",
            "data": {
                "customer_name": customer_info.get("name"),
                "amount": transaction.amount,
                "currency": transaction.currency,
                "transaction_id": transaction.transaction_id,
                "billing_date": transaction.processed_at.isoformat() if transaction.processed_at else datetime.utcnow().isoformat()
            }
        }
        
        # In real implementation, this would send email/SMS notification
        logger.info(
            "Billing notification sent",
            customer_id=customer_info["customer_id"],
            transaction_id=transaction.transaction_id,
            amount=transaction.amount
        )
    
    async def process_manual_billing(
        self,
        stream_id: str,
        customer_ids: List[str],
        amount: Optional[float] = None
    ) -> List[RevenueTransaction]:
        """
        Process manual billing for specific customers.
        
        Args:
            stream_id: Revenue stream ID
            customer_ids: List of customer IDs to bill
            amount: Optional amount to charge (uses stream default if not provided)
            
        Returns:
            List[RevenueTransaction]: List of created transactions
        """
        stream = await self.revenue_engine.get_revenue_stream(stream_id)
        if not stream:
            raise BillingError(f"Revenue stream not found: {stream_id}")
        
        transactions = []
        
        for customer_id in customer_ids:
            try:
                customer_info = await self._get_customer_info(customer_id)
                
                billing_amount = amount or await self._calculate_billing_amount(stream, customer_info)
                
                transaction = await self.revenue_engine.process_transaction(
                    revenue_stream_id=stream_id,
                    amount=billing_amount,
                    customer_id=customer_id,
                    payment_method=customer_info.get("payment_method"),
                    metadata={
                        "billing_type": "manual",
                        "customer_tier": customer_info.get("tier"),
                        "billing_date": datetime.utcnow().isoformat()
                    }
                )
                
                await self._generate_invoice(transaction, customer_info)
                await self._send_billing_notification(transaction, customer_info)
                
                transactions.append(transaction)
                
            except Exception as e:
                logger.error(
                    "Manual billing failed for customer",
                    stream_id=stream_id,
                    customer_id=customer_id,
                    error=str(e)
                )
        
        logger.info(
            "Manual billing completed",
            stream_id=stream_id,
            customers_requested=len(customer_ids),
            successful_transactions=len(transactions)
        )
        
        return transactions
    
    async def get_billing_summary(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get billing summary for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Billing summary
        """
        async with db_session_context() as session:
            # Get total revenue
            result = await session.execute(
                select(
                    func.sum(RevenueTransaction.amount),
                    func.count(RevenueTransaction.id)
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.status == TransactionStatus.COMPLETED,
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            total_revenue, total_transactions = result.first()
            
            # Get revenue by stream
            result = await session.execute(
                select(
                    RevenueStream.name,
                    func.sum(RevenueTransaction.amount),
                    func.count(RevenueTransaction.id)
                ).join(
                    RevenueTransaction, RevenueStream.id == RevenueTransaction.revenue_stream_id
                ).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.status == TransactionStatus.COMPLETED,
                    RevenueTransaction.deleted_at.is_(None)
                ).group_by(RevenueStream.name)
            )
            revenue_by_stream = [
                {
                    "stream_name": row[0],
                    "revenue": float(row[1]) if row[1] else 0.0,
                    "transactions": row[2]
                }
                for row in result.all()
            ]
            
            # Get failed transactions
            result = await session.execute(
                select(func.count(RevenueTransaction.id)).where(
                    RevenueTransaction.created_at >= period_start,
                    RevenueTransaction.created_at <= period_end,
                    RevenueTransaction.status != TransactionStatus.COMPLETED,
                    RevenueTransaction.deleted_at.is_(None)
                )
            )
            failed_transactions = result.scalar() or 0
            
            return {
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "summary": {
                    "total_revenue": float(total_revenue) if total_revenue else 0.0,
                    "total_transactions": total_transactions or 0,
                    "failed_transactions": failed_transactions,
                    "success_rate": (total_transactions / (total_transactions + failed_transactions)) 
                                  if (total_transactions + failed_transactions) > 0 else 0.0
                },
                "revenue_by_stream": revenue_by_stream
            }
    
    async def retry_failed_payments(self, max_retries: int = 3) -> Dict[str, Any]:
        """
        Retry failed payments.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict[str, Any]: Retry results
        """
        async with db_session_context() as session:
            # Get failed transactions
            result = await session.execute(
                select(RevenueTransaction).where(
                    RevenueTransaction.status == TransactionStatus.FAILED,
                    RevenueTransaction.retry_count < max_retries,
                    RevenueTransaction.deleted_at.is_(None)
                ).order_by(RevenueTransaction.created_at)
            )
            failed_transactions = result.scalars().all()
            
            retry_results = {
                "total_failed": len(failed_transactions),
                "retry_attempts": 0,
                "successful_retries": 0,
                "failed_retries": 0
            }
            
            for transaction in failed_transactions:
                try:
                    # Update retry count
                    transaction.retry_count += 1
                    
                    # Process payment again
                    await self._process_payment(transaction)
                    
                    retry_results["successful_retries"] += 1
                    
                    logger.info(
                        "Payment retry successful",
                        transaction_id=transaction.transaction_id,
                        retry_attempt=transaction.retry_count
                    )
                    
                except Exception as e:
                    retry_results["failed_retries"] += 1
                    
                    logger.error(
                        "Payment retry failed",
                        transaction_id=transaction.transaction_id,
                        retry_attempt=transaction.retry_count,
                        error=str(e)
                    )
                
                retry_results["retry_attempts"] += 1
                session.add(transaction)
            
            await session.commit()
            
            logger.info(
                "Payment retry batch completed",
                **retry_results
            )
            
            return retry_results
    
    async def _process_payment(self, transaction: RevenueTransaction) -> None:
        """
        Process payment for a transaction (retry version).
        
        Args:
            transaction: Transaction to process
        """
        # Simulate payment processing with potential failure
        await asyncio.sleep(0.1)
        
        # 80% success rate for retries
        import random
        if random.random() < 0.8:
            transaction.status = TransactionStatus.COMPLETED
            transaction.processed_at = datetime.utcnow()
        else:
            transaction.status = TransactionStatus.FAILED
            transaction.error_message = "Payment processing failed"
