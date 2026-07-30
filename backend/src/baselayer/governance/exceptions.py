"""
BaseLayer Governance/Doctrine Exceptions

Custom exceptions for policy management, compliance monitoring, and audit trails.
"""

from typing import Any, Dict, Optional


class GovernanceError(Exception):
    """Base exception for Governance/Doctrine errors."""
    
    def __init__(
        self,
        message: str,
        policy_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.policy_id = policy_id
        self.rule_id = rule_id
        self.user_id = user_id
        self.details = details or {}
        super().__init__(message)


class PolicyError(GovernanceError):
    """Raised when policy operations fail."""
    
    def __init__(
        self,
        message: str,
        policy_id: Optional[str] = None,
        policy_name: Optional[str] = None,
        policy_operation: Optional[str] = None,
        **kwargs
    ):
        self.policy_name = policy_name
        self.policy_operation = policy_operation
        super().__init__(message, policy_id=policy_id, **kwargs)


class ComplianceError(GovernanceError):
    """Raised when compliance operations fail."""
    
    def __init__(
        self,
        message: str,
        compliance_type: Optional[str] = None,
        compliance_rule: Optional[str] = None,
        violation_severity: Optional[str] = None,
        **kwargs
    ):
        self.compliance_type = compliance_type
        self.compliance_rule = compliance_rule
        self.violation_severity = violation_severity
        super().__init__(message, **kwargs)


class AuditError(GovernanceError):
    """Raised when audit operations fail."""
    
    def __init__(
        self,
        message: str,
        audit_id: Optional[str] = None,
        audit_type: Optional[str] = None,
        audit_operation: Optional[str] = None,
        **kwargs
    ):
        self.audit_id = audit_id
        self.audit_type = audit_type
        self.audit_operation = audit_operation
        super().__init__(message, **kwargs)


class RiskError(GovernanceError):
    """Raised when risk assessment operations fail."""
    
    def __init__(
        self,
        message: str,
        risk_id: Optional[str] = None,
        risk_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        **kwargs
    ):
        self.risk_id = risk_id
        self.risk_type = risk_type
        self.risk_level = risk_level
        super().__init__(message, **kwargs)


class AutomationError(GovernanceError):
    """Raised when governance automation operations fail."""
    
    def __init__(
        self,
        message: str,
        automation_type: Optional[str] = None,
        automation_rule: Optional[str] = None,
        trigger_event: Optional[str] = None,
        **kwargs
    ):
        self.automation_type = automation_type
        self.automation_rule = automation_rule
        self.trigger_event = trigger_event
        super().__init__(message, **kwargs)


class DashboardError(GovernanceError):
    """Raised when dashboard operations fail."""
    
    def __init__(
        self,
        message: str,
        dashboard_type: Optional[str] = None,
        widget_type: Optional[str] = None,
        data_source: Optional[str] = None,
        **kwargs
    ):
        self.dashboard_type = dashboard_type
        self.widget_type = widget_type
        self.data_source = data_source
        super().__init__(message, **kwargs)


class ValidationError(GovernanceError):
    """Raised when governance validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_type: Optional[str] = None,
        validation_errors: Optional[list[str]] = None,
        **kwargs
    ):
        self.validation_type = validation_type
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class AuthorizationError(GovernanceError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        user_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        **kwargs
    ):
        self.required_permission = required_permission
        self.user_role = user_role
        self.resource_type = resource_type
        super().__init__(message, **kwargs)


class ConfigurationError(GovernanceError):
    """Raised when governance configuration is invalid."""
    
    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ):
        self.config_field = config_field
        self.config_value = config_value
        super().__init__(message, **kwargs)


class IntegrationError(GovernanceError):
    """Raised when integration operations fail."""
    
    def __init__(
        self,
        message: str,
        integration_type: Optional[str] = None,
        target_system: Optional[str] = None,
        **kwargs
    ):
        self.integration_type = integration_type
        self.target_system = target_system
        super().__init__(message, **kwargs)
