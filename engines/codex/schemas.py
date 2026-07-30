"""
CODEX Pydantic Schemas

Request and response schemas for CODEX API endpoints.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


class KnowledgeEntryType(str, Enum):
    """Knowledge entry types."""
    FACT = "fact"
    DECISION = "decision"
    PATTERN = "pattern"
    OUTCOME = "outcome"
    PREFERENCE = "preference"
    CONTEXT = "context"


class SourceEngine(str, Enum):
    """Source engines that create knowledge."""
    MINT = "mint"
    WIRE = "wire"
    PULSE = "pulse"
    GATE = "gate"
    HOOK = "hook"
    SYSTEM = "system"
    MANUAL = "manual"


class KnowledgeLinkType(str, Enum):
    """Knowledge link relationship types."""
    RELATED = "related"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    EXAMPLE_OF = "example_of"
    CAUSES = "causes"
    CAUSED_BY = "caused_by"


# Request Schemas
class KnowledgeCreate(BaseModel):
    """Schema for creating knowledge entries."""
    key: str = Field(..., description="Unique key for the entry", min_length=1, max_length=255)
    value: str = Field(..., description="Knowledge content", min_length=1, max_length=10000)
    entry_type: KnowledgeEntryType = Field(..., description="Type of knowledge")
    source_engine: SourceEngine = Field(..., description="Source engine")
    source_agent: str = Field(..., description="Source agent name", min_length=1, max_length=100)
    tags: Optional[List[str]] = Field(default=None, description="Optional tags")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    generate_embedding: bool = Field(default=True, description="Generate embedding")
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if len(v) > 20:
                raise ValueError("Too many tags (max 20)")
            for tag in v:
                if len(tag) > 50:
                    raise ValueError("Tag too long (max 50 characters)")
        return v


class KnowledgeUpdate(BaseModel):
    """Schema for updating knowledge entries."""
    value: Optional[str] = Field(None, description="New value", min_length=1, max_length=10000)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="New confidence")
    tags: Optional[List[str]] = Field(None, description="New tags")
    regenerate_embedding: bool = Field(default=False, description="Regenerate embedding")
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if len(v) > 20:
                raise ValueError("Too many tags (max 20)")
            for tag in v:
                if len(tag) > 50:
                    raise ValueError("Tag too long (max 50 characters)")
        return v


class KnowledgeSearch(BaseModel):
    """Schema for knowledge search."""
    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    entry_types: Optional[List[KnowledgeEntryType]] = Field(None, description="Filter by entry types")
    source_engines: Optional[List[SourceEngine]] = Field(None, description="Filter by source engines")
    exclude_archived: bool = Field(default=True, description="Exclude archived entries")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Similarity threshold")


class KnowledgeContext(BaseModel):
    """Schema for context building."""
    query: str = Field(..., description="Context query", min_length=1, max_length=1000)
    max_tokens: int = Field(default=4000, ge=100, le=8000, description="Maximum tokens")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class KnowledgeLink(BaseModel):
    """Schema for creating knowledge links."""
    source_key: str = Field(..., description="Source entry key", min_length=1, max_length=255)
    target_key: str = Field(..., description="Target entry key", min_length=1, max_length=255)
    link_type: KnowledgeLinkType = Field(..., description="Type of relationship")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="Link strength")
    metadata: Optional[str] = Field(None, description="Optional metadata", max_length=500)


class KnowledgeIngest(BaseModel):
    """Schema for bulk knowledge ingestion."""
    source_type: str = Field(..., description="Source type (text, url, structured)")
    source_data: str = Field(..., description="Source data", min_length=1, max_length=100000)
    source: Optional[str] = Field(None, description="Source identifier", max_length=255)
    engine: Optional[str] = Field(None, description="Source engine", max_length=50)


class KnowledgeBulkCreate(BaseModel):
    """Schema for bulk knowledge creation."""
    entries: List[KnowledgeCreate] = Field(..., description="List of entries to create")
    
    @validator('entries')
    def validate_entries(cls, v):
        if len(v) == 0:
            raise ValueError("At least one entry required")
        if len(v) > 100:
            raise ValueError("Too many entries (max 100)")
        return v


# Response Schemas
class KnowledgeResponse(BaseModel):
    """Schema for knowledge entry response."""
    id: str = Field(..., description="Entry ID")
    key: str = Field(..., description="Entry key")
    value: str = Field(..., description="Entry value")
    entry_type: KnowledgeEntryType = Field(..., description="Entry type")
    source_engine: SourceEngine = Field(..., description="Source engine")
    source_agent: str = Field(..., description="Source agent")
    confidence: float = Field(..., description="Confidence score")
    tags: List[str] = Field(..., description="Entry tags")
    access_count: int = Field(..., description="Access count")
    last_accessed_at: Optional[datetime] = Field(None, description="Last accessed time")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")
    is_archived: bool = Field(..., description="Archived status")
    has_embedding: bool = Field(..., description="Has embedding")
    engagement_rate: Optional[float] = Field(None, description="Engagement rate")


class SearchResult(BaseModel):
    """Schema for search results."""
    id: str = Field(..., description="Entry ID")
    similarity: float = Field(..., description="Similarity score")
    key: str = Field(..., description="Entry key")
    value: str = Field(..., description="Entry value")
    entry_type: KnowledgeEntryType = Field(..., description="Entry type")
    source_engine: SourceEngine = Field(..., description="Source engine")
    source_agent: str = Field(..., description="Source agent")
    confidence: float = Field(..., description="Confidence score")
    tags: List[str] = Field(..., description="Entry tags")
    access_count: int = Field(..., description="Access count")
    created_at: datetime = Field(..., description="Creation time")
    search_weight: float = Field(..., description="Search weight")


class RelatedEntry(BaseModel):
    """Schema for related entries."""
    entry: KnowledgeResponse = Field(..., description="Related entry")
    relationship: str = Field(..., description="Relationship description")
    strength: float = Field(..., description="Relationship strength")
    link_type: KnowledgeLinkType = Field(..., description="Link type")
    depth: int = Field(..., description="Traversal depth")
    path: List[str] = Field(..., description="Path from source")


class KnowledgeStats(BaseModel):
    """Schema for knowledge base statistics."""
    total_entries: int = Field(..., description="Total entries")
    active_entries: int = Field(..., description="Active entries")
    archived_entries: int = Field(..., description="Archived entries")
    total_links: int = Field(..., description="Total links")
    embedding_stats: Dict[str, Any] = Field(..., description="Embedding statistics")
    health_score: float = Field(..., description="Health score")
    latest_snapshot: Optional[Dict[str, Any]] = Field(None, description="Latest snapshot")


class KnowledgeSnapshot(BaseModel):
    """Schema for knowledge snapshot."""
    id: str = Field(..., description="Snapshot ID")
    snapshot_date: datetime = Field(..., description="Snapshot date")
    total_entries: int = Field(..., description="Total entries")
    entries_by_type: Dict[str, int] = Field(..., description="Entries by type")
    entries_by_engine: Dict[str, int] = Field(..., description="Entries by engine")
    avg_confidence: float = Field(..., description="Average confidence")
    health_score: float = Field(..., description="Health score")
    performance_rating: str = Field(..., description="Performance rating")
    created_at: datetime = Field(..., description="Creation time")


class DecayResult(BaseModel):
    """Schema for decay operation results."""
    candidates_found: int = Field(..., description="Candidates found")
    entries_decayed: int = Field(..., description="Entries decayed")
    dry_run: bool = Field(..., description="Dry run flag")
    decay_threshold: float = Field(..., description="Decay threshold")
    days_threshold: int = Field(..., description="Days threshold")
    decayed_entries: List[Dict[str, Any]] = Field(..., description="Decayed entries")


class PruneResult(BaseModel):
    """Schema for prune operation results."""
    candidates_found: int = Field(..., description="Candidates found")
    entries_pruned: int = Field(..., description="Entries pruned")
    dry_run: bool = Field(..., description="Dry run flag")
    retention_days: int = Field(..., description="Retention days")
    cutoff_date: str = Field(..., description="Cutoff date")
    pruned_entries: List[Dict[str, Any]] = Field(..., description="Pruned entries")


class ExportResult(BaseModel):
    """Schema for export operation results."""
    export_timestamp: datetime = Field(..., description="Export timestamp")
    total_entries_exported: int = Field(..., description="Total entries exported")
    export_directory: str = Field(..., description="Export directory")
    results_by_type: Dict[str, Dict[str, Any]] = Field(..., description="Results by type")
    include_archived: bool = Field(..., description="Include archived flag")


class ContextResult(BaseModel):
    """Schema for context building results."""
    query: str = Field(..., description="Query")
    max_tokens: int = Field(..., description="Max tokens")
    context: str = Field(..., description="Built context")
    context_length: int = Field(..., description="Context length")
    entries_included: int = Field(..., description="Entries included")
    actual_tokens: int = Field(..., description="Actual tokens")


class HealthStatus(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Health status")
    details: str = Field(..., description="Health details")
    timestamp: datetime = Field(..., description="Check timestamp")
    stats: Optional[KnowledgeStats] = Field(None, description="Knowledge stats")


# Error Schemas
class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID")


class ValidationError(BaseModel):
    """Schema for validation errors."""
    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="Invalid value")


# Pagination Schemas
class PaginationParams(BaseModel):
    """Schema for pagination parameters."""
    limit: int = Field(default=50, ge=1, le=100, description="Results per page")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""
    items: List[Any] = Field(..., description="Items in current page")
    total: int = Field(..., description="Total items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Current offset")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


# Filter Schemas
class EntryFilter(BaseModel):
    """Schema for entry filtering."""
    entry_types: Optional[List[KnowledgeEntryType]] = Field(None, description="Filter by entry types")
    source_engines: Optional[List[SourceEngine]] = Field(None, description="Filter by source engines")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum confidence")
    max_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum confidence")
    created_after: Optional[datetime] = Field(None, description="Created after")
    created_before: Optional[datetime] = Field(None, description="Created before")
    include_archived: bool = Field(default=False, description="Include archived")
    min_access_count: Optional[int] = Field(None, ge=0, description="Minimum access count")
    has_embedding: Optional[bool] = Field(None, description="Has embedding")


# Sort Schemas
class SortField(str, Enum):
    """Available sort fields."""
    KEY = "key"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    CONFIDENCE = "confidence"
    ACCESS_COUNT = "access_count"
    LAST_ACCESSED_AT = "last_accessed_at"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class SortParams(BaseModel):
    """Schema for sorting parameters."""
    field: SortField = Field(default=SortField.CREATED_AT, description="Sort field")
    order: SortOrder = Field(default=SortOrder.DESC, description="Sort order")


# Combined Query Schemas
class EntryQuery(PaginationParams):
    """Combined query parameters for entries."""
    filter: Optional[EntryFilter] = Field(None, description="Filter parameters")
    sort: Optional[SortParams] = Field(None, description="Sort parameters")


# Batch Operation Schemas
class BulkOperation(BaseModel):
    """Schema for bulk operations."""
    operation: str = Field(..., description="Operation type")
    keys: List[str] = Field(..., description="Keys to operate on")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")
    
    @validator('keys')
    def validate_keys(cls, v):
        if len(v) == 0:
            raise ValueError("At least one key required")
        if len(v) > 1000:
            raise ValueError("Too many keys (max 1000)")
        return v


class BulkOperationResult(BaseModel):
    """Schema for bulk operation results."""
    operation: str = Field(..., description="Operation type")
    total_keys: int = Field(..., description="Total keys processed")
    successful: int = Field(..., description="Successful operations")
    failed: int = Field(..., description="Failed operations")
    errors: List[Dict[str, Any]] = Field(..., description="Error details")
    results: List[Dict[str, Any]] = Field(..., description="Operation results")
