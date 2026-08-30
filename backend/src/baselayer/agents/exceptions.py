"""
BaseLayer Multi-Agent Orchestration Exceptions

Custom exceptions for agent management, coordination, and communication.
"""

from typing import Any, Dict, Optional


class AgentError(Exception):
    """Base exception for agent-related errors."""
    
    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.agent_id = agent_id
        self.task_id = task_id
        self.details = details or {}
        super().__init__(message)


class AgentNotFoundError(AgentError):
    """Raised when an agent is not found."""
    
    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        **kwargs
    ):
        self.agent_type = agent_type
        super().__init__(message, agent_id=agent_id, **kwargs)


class AgentLifecycleError(AgentError):
    """Raised when agent lifecycle operations fail."""
    
    def __init__(
        self,
        message: str,
        lifecycle_state: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        self.lifecycle_state = lifecycle_state
        self.operation = operation
        super().__init__(message, **kwargs)


class AgentCommunicationError(AgentError):
    """Raised when agent communication fails."""
    
    def __init__(
        self,
        message: str,
        communication_type: Optional[str] = None,
        target_agent_id: Optional[str] = None,
        **kwargs
    ):
        self.communication_type = communication_type
        self.target_agent_id = target_agent_id
        super().__init__(message, **kwargs)


class TaskCoordinationError(AgentError):
    """Raised when task coordination fails."""
    
    def __init__(
        self,
        message: str,
        task_type: Optional[str] = None,
        coordination_strategy: Optional[str] = None,
        **kwargs
    ):
        self.task_type = task_type
        self.coordination_strategy = coordination_strategy
        super().__init__(message, **kwargs)


class AgentScalingError(AgentError):
    """Raised when agent scaling operations fail."""
    
    def __init__(
        self,
        message: str,
        scaling_operation: Optional[str] = None,
        target_count: Optional[int] = None,
        **kwargs
    ):
        self.scaling_operation = scaling_operation
        self.target_count = target_count
        super().__init__(message, **kwargs)


class AgentPerformanceError(AgentError):
    """Raised when agent performance issues occur."""
    
    def __init__(
        self,
        message: str,
        performance_metric: Optional[str] = None,
        threshold: Optional[float] = None,
        actual_value: Optional[float] = None,
        **kwargs
    ):
        self.performance_metric = performance_metric
        self.threshold = threshold
        self.actual_value = actual_value
        super().__init__(message, **kwargs)


class AgentConfigurationError(AgentError):
    """Raised when agent configuration is invalid."""

    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        config_value: Optional[Any] = None,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        self.config_field = config_field
        self.config_value = config_value
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class AgentResourceError(AgentError):
    """Raised when agent resource allocation fails."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        requested_amount: Optional[float] = None,
        available_amount: Optional[float] = None,
        **kwargs
    ):
        self.resource_type = resource_type
        self.requested_amount = requested_amount
        self.available_amount = available_amount
        super().__init__(message, **kwargs)


class AgentSecurityError(AgentError):
    """Raised when agent security issues occur."""
    
    def __init__(
        self,
        message: str,
        security_policy: Optional[str] = None,
        violation_type: Optional[str] = None,
        **kwargs
    ):
        self.security_policy = security_policy
        self.violation_type = violation_type
        super().__init__(message, **kwargs)
