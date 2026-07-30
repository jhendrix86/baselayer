"""
BaseLayer Income Engine Exceptions

Custom exceptions for revenue processing, billing, and payment errors.
"""

from typing import Any, Dict, Optional


class RevenueEngineError(Exception):
    """Base exception for revenue engine errors."""
    
    def __init__(
        self,
        message: str,
        revenue_stream_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.revenue_stream_id = revenue_stream_id
        self.transaction_id = transaction_id
        self.details = details or {}
        super().__init__(message)


class BillingError(RevenueEngineError):
    """Raised when billing operations fail."""
    
    def __init__(
        self,
        message: str,
        billing_cycle: Optional[str] = None,
        customer_id: Optional[str] = None,
        **kwargs
    ):
        self.billing_cycle = billing_cycle
        self.customer_id = customer_id
        super().__init__(message, **kwargs)


class PaymentError(RevenueEngineError):
    """Raised when payment processing fails."""
    
    def __init__(
        self,
        message: str,
        payment_method: Optional[str] = None,
        provider: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ):
        self.payment_method = payment_method
        self.provider = provider
        self.error_code = error_code
        super().__init__(message, **kwargs)


class SubscriptionError(RevenueEngineError):
    """Raised when subscription operations fail."""
    
    def __init__(
        self,
        message: str,
        subscription_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        **kwargs
    ):
        self.subscription_id = subscription_id
        self.plan_id = plan_id
        super().__init__(message, **kwargs)


class AnalyticsError(RevenueEngineError):
    """Raised when analytics operations fail."""
    
    def __init__(
        self,
        message: str,
        metric_type: Optional[str] = None,
        time_period: Optional[str] = None,
        **kwargs
    ):
        self.metric_type = metric_type
        self.time_period = time_period
        super().__init__(message, **kwargs)


class RevenueValidationError(RevenueEngineError):
    """Raised when revenue data validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list[str]] = None,
        **kwargs
    ):
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class RevenueComplianceError(RevenueEngineError):
    """Raised when revenue compliance checks fail."""
    
    def __init__(
        self,
        message: str,
        compliance_rules: Optional[list[str]] = None,
        audit_level: Optional[str] = None,
        **kwargs
    ):
        self.compliance_rules = compliance_rules
        self.audit_level = audit_level
        super().__init__(message, **kwargs)
