"""
BaseLayer Core Loop Exceptions

Custom exceptions for workflow engine and execution errors.
"""

from typing import Any, Dict, Optional


class WorkflowEngineError(Exception):
    """Base exception for workflow engine errors."""
    
    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.details = details or {}
        super().__init__(message)


class WorkflowValidationError(WorkflowEngineError):
    """Raised when workflow validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list[str]] = None,
        **kwargs
    ):
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class WorkflowExecutionError(WorkflowEngineError):
    """Raised when workflow execution fails."""
    
    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ):
        self.step_id = step_id
        self.error_code = error_code
        super().__init__(message, **kwargs)


class WorkflowTimeoutError(WorkflowEngineError):
    """Raised when workflow execution times out."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, **kwargs)


class WorkflowDependencyError(WorkflowEngineError):
    """Raised when workflow dependency resolution fails."""
    
    def __init__(
        self,
        message: str,
        dependency_graph: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.dependency_graph = dependency_graph
        super().__init__(message, **kwargs)


class WorkflowResourceError(WorkflowEngineError):
    """Raised when workflow resource allocation fails."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        required_resources: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.resource_type = resource_type
        self.required_resources = required_resources
        super().__init__(message, **kwargs)


class WorkflowGovernanceError(WorkflowEngineError):
    """Raised when workflow governance checks fail."""
    
    def __init__(
        self,
        message: str,
        governance_rules: Optional[list[str]] = None,
        compliance_level: Optional[str] = None,
        **kwargs
    ):
        self.governance_rules = governance_rules
        self.compliance_level = compliance_level
        super().__init__(message, **kwargs)
