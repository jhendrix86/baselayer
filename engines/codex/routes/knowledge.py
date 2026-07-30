"""
CODEX Knowledge API Routes

FastAPI routes for knowledge management, search,
and maintenance operations.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..api.knowledge_manager import KnowledgeManager
from ..models.knowledge_entry import KnowledgeEntryType, SourceEngine
from ..models.knowledge_link import KnowledgeLinkType

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/codex", tags=["codex"])


# Pydantic schemas for request/response
class KnowledgeCreate(BaseModel):
    """Schema for creating knowledge entries."""
    key: str = Field(..., description="Unique key for the entry")
    value: str = Field(..., description="Knowledge content")
    entry_type: str = Field(..., description="Type of knowledge")
    source_engine: str = Field(..., description="Source engine")
    source_agent: str = Field(..., description="Source agent")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    generate_embedding: bool = Field(default=True, description="Generate embedding")


class KnowledgeUpdate(BaseModel):
    """Schema for updating knowledge entries."""
    value: Optional[str] = Field(None, description="New value")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="New confidence")
    tags: Optional[List[str]] = Field(None, description="New tags")
    regenerate_embedding: bool = Field(default=False, description="Regenerate embedding")


class KnowledgeSearch(BaseModel):
    """Schema for knowledge search."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    entry_types: Optional[List[str]] = Field(None, description="Filter by entry types")
    source_engines: Optional[List[str]] = Field(None, description="Filter by source engines")
    exclude_archived: bool = Field(default=True, description="Exclude archived entries")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Similarity threshold")


class KnowledgeContext(BaseModel):
    """Schema for context building."""
    query: str = Field(..., description="Context query")
    max_tokens: int = Field(default=4000, ge=100, le=8000, description="Maximum tokens")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class KnowledgeLink(BaseModel):
    """Schema for creating knowledge links."""
    source_key: str = Field(..., description="Source entry key")
    target_key: str = Field(..., description="Target entry key")
    link_type: str = Field(..., description="Type of relationship")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="Link strength")
    metadata: Optional[str] = Field(None, description="Optional metadata")


class KnowledgeIngest(BaseModel):
    """Schema for bulk knowledge ingestion."""
    source_type: str = Field(..., description="Source type (text, url, structured)")
    source_data: str = Field(..., description="Source data")
    source: Optional[str] = Field(None, description="Source identifier")
    engine: Optional[str] = Field(None, description="Source engine")


# Dependency injection for knowledge manager
async def get_knowledge_manager() -> KnowledgeManager:
    """Get knowledge manager instance."""
    # This would be injected from the application
    # For now, return a placeholder
    # TODO: Implement proper dependency injection
    return None


@router.post("/entries", response_model=Dict[str, Any])
async def create_entry(
    entry_data: KnowledgeCreate,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Store a new knowledge entry."""
    try:
        # Convert string types to enums
        entry_type = KnowledgeEntryType(entry_data.entry_type)
        source_engine = SourceEngine(entry_data.source_engine)
        
        # Store entry
        entry = await knowledge_manager.store(
            key=entry_data.key,
            value=entry_data.value,
            entry_type=entry_type,
            source_engine=source_engine,
            source_agent=entry_data.source_agent,
            tags=entry_data.tags,
            confidence=entry_data.confidence,
            generate_embedding=entry_data.generate_embedding
        )
        
        return {
            "id": str(entry.id),
            "key": entry.key,
            "entry_type": entry.entry_type,
            "source_engine": entry.source_engine,
            "source_agent": entry.source_agent,
            "confidence": entry.confidence,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat(),
            "has_embedding": entry.embedding is not None
        }
        
    except BaseLayerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create knowledge entry", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entries", response_model=List[Dict[str, Any]])
async def list_entries(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    entry_type: Optional[str] = Query(None),
    source_engine: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    include_archived: bool = Query(default=False),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """List and filter knowledge entries."""
    try:
        # This would implement the actual listing logic
        # For now, return empty list as placeholder
        logger.warning("Entry listing not implemented")
        return []
        
    except Exception as e:
        logger.error("Failed to list knowledge entries", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entries/{key}", response_model=Dict[str, Any])
async def get_entry(
    key: str,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Get a knowledge entry by key."""
    try:
        entry = await knowledge_manager.retrieve_by_key(key)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        return entry.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get knowledge entry", key=key, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/entries/{key}", response_model=Dict[str, Any])
async def update_entry(
    key: str,
    update_data: KnowledgeUpdate,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Update a knowledge entry."""
    try:
        entry = await knowledge_manager.update(
            key=key,
            value=update_data.value,
            confidence=update_data.confidence,
            tags=update_data.tags,
            regenerate_embedding=update_data.regenerate_embedding
        )
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        return entry.to_dict()
        
    except HTTPException:
        raise
    except BaseLayerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update knowledge entry", key=key, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/entries/{key}", response_model=Dict[str, Any])
async def archive_entry(
    key: str,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Archive (soft delete) a knowledge entry."""
    try:
        success = await knowledge_manager.archive(key)
        
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        return {"key": key, "archived": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to archive knowledge entry", key=key, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_entries(
    search_data: KnowledgeSearch,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Search knowledge entries."""
    try:
        # Convert string types to enums
        entry_types = None
        if search_data.entry_types:
            entry_types = [KnowledgeEntryType(et) for et in search_data.entry_types]
        
        source_engines = None
        if search_data.source_engines:
            source_engines = [SourceEngine(se) for se in search_data.source_engines]
        
        # Perform search
        results = await knowledge_manager.search_semantic(
            query=search_data.query,
            limit=search_data.limit,
            min_confidence=search_data.min_confidence,
            tags=search_data.tags,
            entry_types=entry_types,
            source_engines=source_engines,
            exclude_archived=search_data.exclude_archived,
            threshold=search_data.threshold
        )
        
        return results
        
    except Exception as e:
        logger.error("Failed to search knowledge entries", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/context", response_model=Dict[str, Any])
async def build_context(
    context_data: KnowledgeContext,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Build context for LLM from relevant knowledge."""
    try:
        context = await knowledge_manager.get_context(
            query=context_data.query,
            max_tokens=context_data.max_tokens,
            min_confidence=context_data.min_confidence,
            tags=context_data.tags
        )
        
        return {
            "query": context_data.query,
            "max_tokens": context_data.max_tokens,
            "context": context,
            "context_length": len(context)
        }
        
    except Exception as e:
        logger.error("Failed to build context", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/link", response_model=Dict[str, Any])
async def create_link(
    link_data: KnowledgeLink,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Create a relationship between two knowledge entries."""
    try:
        # Convert string type to enum
        link_type = KnowledgeLinkType(link_data.link_type)
        
        link = await knowledge_manager.link(
            source_key=link_data.source_key,
            target_key=link_data.target_key,
            link_type=link_type,
            strength=link_data.strength,
            metadata=link_data.metadata
        )
        
        if not link:
            raise HTTPException(status_code=404, detail="Source or target entry not found")
        
        return {
            "id": str(link.id),
            "source_key": link_data.source_key,
            "target_key": link_data.target_key,
            "link_type": link.link_type,
            "strength": link.strength,
            "created_at": link.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except BaseLayerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create knowledge link", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entries/{key}/related", response_model=List[Dict[str, Any]])
async def get_related_entries(
    key: str,
    depth: int = Query(default=2, ge=1, le=5),
    min_strength: float = Query(default=0.3, ge=0.0, le=1.0),
    max_results: int = Query(default=50, ge=1, le=100),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Get entries related to a specific entry."""
    try:
        related = await knowledge_manager.get_related(
            key=key,
            depth=depth,
            min_strength=min_strength,
            max_results=max_results
        )
        
        return related
        
    except Exception as e:
        logger.error("Failed to get related entries", key=key, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Get knowledge base statistics."""
    try:
        stats = await knowledge_manager.get_stats()
        return stats
        
    except Exception as e:
        logger.error("Failed to get knowledge stats", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_knowledge(
    ingest_data: KnowledgeIngest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Bulk ingest knowledge from various sources."""
    try:
        # This would use the knowledge ingester agent
        # For now, return placeholder response
        logger.warning("Knowledge ingestion not implemented")
        
        return {
            "source_type": ingest_data.source_type,
            "source_data_length": len(ingest_data.source_data),
            "status": "not_implemented"
        }
        
    except Exception as e:
        logger.error("Failed to ingest knowledge", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/decay", response_model=Dict[str, Any])
async def decay_confidence(
    dry_run: bool = Query(default=False),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Decay confidence of old, low-access entries."""
    try:
        result = await knowledge_manager.decay(dry_run=dry_run)
        return result
        
    except Exception as e:
        logger.error("Failed to decay confidence", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/prune", response_model=Dict[str, Any])
async def prune_entries(
    retention_days: int = Query(default=90, ge=1),
    dry_run: bool = Query(default=False),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Prune old archived entries."""
    try:
        result = await knowledge_manager.prune(
            retention_days=retention_days,
            dry_run=dry_run
        )
        return result
        
    except Exception as e:
        logger.error("Failed to prune entries", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/snapshot", response_model=Dict[str, Any])
async def create_snapshot(
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Generate a daily knowledge snapshot."""
    try:
        snapshot = await knowledge_manager.snapshot()
        
        return {
            "id": str(snapshot.id),
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "total_entries": snapshot.total_entries,
            "avg_confidence": snapshot.avg_confidence,
            "created_at": snapshot.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to create snapshot", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/snapshots", response_model=List[Dict[str, Any]])
async def list_snapshots(
    limit: int = Query(default=30, ge=1, le=100),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """List knowledge snapshots."""
    try:
        # This would implement snapshot listing
        # For now, return empty list as placeholder
        logger.warning("Snapshot listing not implemented")
        return []
        
    except Exception as e:
        logger.error("Failed to list snapshots", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/snapshots/{snapshot_id}", response_model=Dict[str, Any])
async def get_snapshot(
    snapshot_id: str,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Get a specific knowledge snapshot."""
    try:
        # This would implement snapshot retrieval
        # For now, return placeholder response
        logger.warning("Snapshot retrieval not implemented")
        
        return {
            "id": snapshot_id,
            "status": "not_implemented"
        }
        
    except Exception as e:
        logger.error("Failed to get snapshot", snapshot_id=snapshot_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Health check endpoint."""
    try:
        # Get basic stats to check health
        stats = await knowledge_manager.get_stats()
        
        # Determine health status
        if "error" in stats:
            status = "unhealthy"
            details = stats["error"]
        else:
            health_score = stats.get("health_score", 0.0)
            if health_score >= 0.8:
                status = "healthy"
            elif health_score >= 0.6:
                status = "degraded"
            else:
                status = "unhealthy"
            details = f"Health score: {health_score:.2f}"
        
        return {
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": stats
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
