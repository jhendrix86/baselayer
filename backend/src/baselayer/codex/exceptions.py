"""
BaseLayer Codex/Memory Exceptions

Custom exceptions for knowledge management, search, and AI integration.
"""

from typing import Any, Dict, Optional


class CodexError(Exception):
    """Base exception for Codex/Memory errors."""
    
    def __init__(
        self,
        message: str,
        entry_id: Optional[str] = None,
        search_query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.entry_id = entry_id
        self.search_query = search_query
        self.details = details or {}
        super().__init__(message)


class KnowledgeNotFoundError(CodexError):
    """Raised when knowledge entry is not found."""
    
    def __init__(
        self,
        message: str,
        entry_id: Optional[str] = None,
        entry_type: Optional[str] = None,
        **kwargs
    ):
        self.entry_type = entry_type
        super().__init__(message, entry_id=entry_id, **kwargs)


class SearchError(CodexError):
    """Raised when search operations fail."""
    
    def __init__(
        self,
        message: str,
        search_type: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ):
        self.search_type = search_type
        super().__init__(message, search_query=query, **kwargs)


class IndexError(CodexError):
    """Raised when indexing operations fail."""
    
    def __init__(
        self,
        message: str,
        index_type: Optional[str] = None,
        document_id: Optional[str] = None,
        **kwargs
    ):
        self.index_type = index_type
        self.document_id = document_id
        super().__init__(message, entry_id=document_id, **kwargs)


class ExtractionError(CodexError):
    """Raised when knowledge extraction fails."""
    
    def __init__(
        self,
        message: str,
        extraction_type: Optional[str] = None,
        source_type: Optional[str] = None,
        **kwargs
    ):
        self.extraction_type = extraction_type
        self.source_type = source_type
        super().__init__(message, **kwargs)


class AnalysisError(CodexError):
    """Raised when knowledge analysis fails."""
    
    def __init__(
        self,
        message: str,
        analysis_type: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ):
        self.analysis_type = analysis_type
        self.model_name = model_name
        super().__init__(message, **kwargs)


class ValidationError(CodexError):
    """Raised when knowledge validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list[str]] = None,
        **kwargs
    ):
        self.validation_errors = validation_errors or []
        super().__init__(message, **kwargs)


class AIModelError(CodexError):
    """Raised when AI model operations fail."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.error_code = error_code
        super().__init__(message, **kwargs)


class StorageError(CodexError):
    """Raised when storage operations fail."""
    
    def __init__(
        self,
        message: str,
        storage_type: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        self.storage_type = storage_type
        self.operation = operation
        super().__init__(message, **kwargs)
