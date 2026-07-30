"""
BaseLayer Output Engine Exceptions

Custom exceptions for template management, output generation, and formatting.
"""

from typing import Any, Dict, Optional


class OutputEngineError(Exception):
    """Base exception for Output Engine errors."""
    
    def __init__(
        self,
        message: str,
        template_id: Optional[str] = None,
        output_id: Optional[str] = None,
        format_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.template_id = template_id
        self.output_id = output_id
        self.format_type = format_type
        self.details = details or {}
        super().__init__(message)


class TemplateNotFoundError(OutputEngineError):
    """Raised when a template is not found."""
    
    def __init__(
        self,
        message: str,
        template_id: Optional[str] = None,
        template_name: Optional[str] = None,
        **kwargs
    ):
        self.template_name = template_name
        super().__init__(message, template_id=template_id, **kwargs)


class RenderingError(OutputEngineError):
    """Raised when template rendering fails."""
    
    def __init__(
        self,
        message: str,
        template_id: Optional[str] = None,
        rendering_engine: Optional[str] = None,
        **kwargs
    ):
        self.rendering_engine = rendering_engine
        super().__init__(message, template_id=template_id, **kwargs)


class FormattingError(OutputEngineError):
    """Raised when output formatting fails."""
    
    def __init__(
        self,
        message: str,
        format_type: Optional[str] = None,
        output_id: Optional[str] = None,
        **kwargs
    ):
        self.format_type = format_type
        super().__init__(message, output_id=output_id, format_type=format_type, **kwargs)


class GenerationError(OutputEngineError):
    """Raised when output generation fails."""
    
    def __init__(
        self,
        message: str,
        generation_type: Optional[str] = None,
        output_id: Optional[str] = None,
        **kwargs
    ):
        self.generation_type = generation_type
        super().__init__(message, output_id=output_id, **kwargs)


class DeliveryError(OutputEngineError):
    """Raised when output delivery fails."""
    
    def __init__(
        self,
        message: str,
        delivery_method: Optional[str] = None,
        output_id: Optional[str] = None,
        **kwargs
    ):
        self.delivery_method = delivery_method
        super().__init__(message, output_id=output_id, **kwargs)


class TrackingError(OutputEngineError):
    """Raised when output tracking fails."""
    
    def __init__(
        self,
        message: str,
        tracking_type: Optional[str] = None,
        output_id: Optional[str] = None,
        **kwargs
    ):
        self.tracking_type = tracking_type
        super().__init__(message, output_id=output_id, **kwargs)


class ValidationError(OutputEngineError):
    """Raised when output validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list[str]] = None,
        **kwargs
    ):
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class TemplateError(OutputEngineError):
    """Raised when template operations fail."""
    
    def __init__(
        self,
        message: str,
        template_operation: Optional[str] = None,
        template_id: Optional[str] = None,
        **kwargs
    ):
        self.template_operation = template_operation
        super().__init__(message, template_id=template_id, **kwargs)


class CacheError(OutputEngineError):
    """Raised when cache operations fail."""
    
    def __init__(
        self,
        message: str,
        cache_operation: Optional[str] = None,
        cache_key: Optional[str] = None,
        **kwargs
    ):
        self.cache_operation = cache_operation
        self.cache_key = cache_key
        super().__init__(message, **kwargs)


class ConfigurationError(OutputEngineError):
    """Raised when output configuration is invalid."""
    
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
