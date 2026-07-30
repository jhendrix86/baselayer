"""
BaseLayer Codex/Memory API - Knowledge

REST API endpoints for knowledge entry management.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import get_db_session
from ...models.codex import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag,
    KnowledgeType, EntryType, KnowledgeStatus
)
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import KnowledgeEngine
from ..extractor import KnowledgeExtractor
from ..analyzer import KnowledgeAnalyzer
from ..exceptions import (
    CodexError,
    KnowledgeNotFoundError,
    ValidationError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

# Global instances (will be injected in startup)
knowledge_engine: KnowledgeEngine = None
knowledge_extractor: KnowledgeExtractor = None
knowledge_analyzer: KnowledgeAnalyzer = None


def get_knowledge_engine() -> KnowledgeEngine:
    """Get knowledge engine instance."""
    global knowledge_engine
    if not knowledge_engine:
        raise HTTPException(status_code=500, detail="Knowledge engine not initialized")
    return knowledge_engine


def get_knowledge_extractor() -> KnowledgeExtractor:
    """Get knowledge extractor instance."""
    global knowledge_extractor
    if not knowledge_extractor:
        raise HTTPException(status_code=500, detail="Knowledge extractor not initialized")
    return knowledge_extractor


def get_knowledge_analyzer() -> KnowledgeAnalyzer:
    """Get knowledge analyzer instance."""
    global knowledge_analyzer
    if not knowledge_analyzer:
        raise HTTPException(status_code=500, detail="Knowledge analyzer not initialized")
    return knowledge_analyzer


@router.get("/entries", response_model=List[Dict[str, Any]])
async def list_knowledge_entries(
    status: Optional[KnowledgeStatus] = Query(None),
    entry_type: Optional[EntryType] = Query(None),
    knowledge_type: Optional[KnowledgeType] = Query(None),
    category_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|title|author)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List knowledge entries with optional filtering.
    
    Args:
        status: Filter by status
        entry_type: Filter by entry type
        knowledge_type: Filter by knowledge type
        category_id: Filter by category
        language: Filter by language
        author: Filter by author
        limit: Maximum number of results
        offset: Pagination offset
        sort_by: Sort field
        sort_order: Sort order
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of knowledge entries
    """
    engine = get_knowledge_engine()
    
    entries = await engine.list_knowledge_entries(
        status=status,
        entry_type=entry_type,
        knowledge_type=knowledge_type,
        category_id=category_id,
        language=language,
        author=author,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return [entry.to_dict() for entry in entries]


@router.get("/entries/{entry_id}", response_model=Dict[str, Any])
async def get_knowledge_entry(
    entry_id: str,
    include_content: bool = Query(True),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific knowledge entry.
    
    Args:
        entry_id: Entry ID
        include_content: Whether to include content
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Knowledge entry details
    """
    engine = get_knowledge_engine()
    
    entry = await engine.get_knowledge_entry(entry_id, include_content=include_content)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    return entry.to_dict()


@router.post("/entries", response_model=Dict[str, Any])
async def create_knowledge_entry(
    entry_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new knowledge entry.
    
    Args:
        entry_data: Entry data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created knowledge entry
    """
    engine = get_knowledge_engine()
    
    try:
        entry = await engine.create_knowledge_entry(
            title=entry_data["title"],
            content=entry_data["content"],
            entry_type=EntryType(entry_data["entry_type"]),
            knowledge_type=KnowledgeType(entry_data["knowledge_type"]),
            category_id=entry_data.get("category_id"),
            tags=entry_data.get("tags"),
            language=entry_data.get("language", "en"),
            access_level=entry_data.get("access_level", "public"),
            metadata=entry_data.get("metadata"),
            author=entry_data.get("author"),
            created_by=current_user.id
        )
        
        logger.info(
            "Knowledge entry created via API",
            entry_id=str(entry.id),
            title=entry.title,
            user_id=str(current_user.id)
        )
        
        return entry.to_dict()
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CodexError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entries/{entry_id}", response_model=Dict[str, Any])
async def update_knowledge_entry(
    entry_id: str,
    entry_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update a knowledge entry.
    
    Args:
        entry_id: Entry ID
        entry_data: Updated entry data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Updated knowledge entry
    """
    engine = get_knowledge_engine()
    
    try:
        # Get existing entry to check permissions
        existing_entry = await engine.get_knowledge_entry(entry_id)
        
        if not existing_entry:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")
        
        # Check permissions (user can update their own entries or if admin)
        if not current_user.is_admin and existing_entry.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this entry")
        
        entry = await engine.update_knowledge_entry(
            entry_id=entry_id,
            updates=entry_data,
            updated_by=current_user.id,
            create_version=True
        )
        
        logger.info(
            "Knowledge entry updated via API",
            entry_id=entry_id,
            user_id=str(current_user.id)
        )
        
        return entry.to_dict()
        
    except KnowledgeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CodexError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entries/{entry_id}", response_model=Dict[str, Any])
async def delete_knowledge_entry(
    entry_id: str,
    permanent: bool = Query(False),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a knowledge entry.
    
    Args:
        entry_id: Entry ID
        permanent: Whether to permanently delete
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    engine = get_knowledge_engine()
    
    # Get existing entry to check permissions
    existing_entry = await engine.get_knowledge_entry(entry_id)
    
    if not existing_entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Check permissions (user can delete their own entries or if admin)
    if not current_user.is_admin and existing_entry.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this entry")
    
    success = await engine.delete_knowledge_entry(
        entry_id=entry_id,
        deleted_by=current_user.id,
        permanent=permanent
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    logger.info(
        "Knowledge entry deleted via API",
        entry_id=entry_id,
        permanent=permanent,
        user_id=str(current_user.id)
    )
    
    return {"message": "Knowledge entry deleted successfully"}


@router.get("/entries/{entry_id}/versions", response_model=List[Dict[str, Any]])
async def get_entry_versions(
    entry_id: str,
    limit: int = Query(10, le=20),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get version history for a knowledge entry.
    
    Args:
        entry_id: Entry ID
        limit: Maximum number of versions
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Version history
    """
    engine = get_knowledge_engine()
    
    versions = await engine.get_entry_versions(entry_id, limit)
    
    return versions


@router.post("/entries/{entry_id}/publish", response_model=Dict[str, Any])
async def publish_knowledge_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Publish a knowledge entry.
    
    Args:
        entry_id: Entry ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Publish result
    """
    engine = get_knowledge_engine()
    
    # Get existing entry to check permissions
    existing_entry = await engine.get_knowledge_entry(entry_id)
    
    if not existing_entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Check permissions
    if not current_user.is_admin and existing_entry.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to publish this entry")
    
    # Update status to published
    entry = await engine.update_knowledge_entry(
        entry_id=entry_id,
        updates={"status": KnowledgeStatus.PUBLISHED},
        updated_by=current_user.id,
        create_version=False
    )
    
    logger.info(
        "Knowledge entry published via API",
        entry_id=entry_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Knowledge entry published successfully", "status": entry.status.value}


@router.post("/entries/{entry_id}/archive", response_model=Dict[str, Any])
async def archive_knowledge_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Archive a knowledge entry.
    
    Args:
        entry_id: Entry ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Archive result
    """
    engine = get_knowledge_engine()
    
    # Get existing entry to check permissions
    existing_entry = await engine.get_knowledge_entry(entry_id)
    
    if not existing_entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Check permissions
    if not current_user.is_admin and existing_entry.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to archive this entry")
    
    # Update status to archived
    entry = await engine.update_knowledge_entry(
        entry_id=entry_id,
        updates={"status": KnowledgeStatus.ARCHIVED},
        updated_by=current_user.id,
        create_version=False
    )
    
    logger.info(
        "Knowledge entry archived via API",
        entry_id=entry_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Knowledge entry archived successfully", "status": entry.status.value}


@router.post("/extract/url", response_model=Dict[str, Any])
async def extract_from_url(
    extraction_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract knowledge from a URL.
    
    Args:
        extraction_data: Extraction data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created knowledge entry
    """
    extractor = get_knowledge_extractor()
    
    try:
        entry = await extractor.extract_from_url(
            url=extraction_data["url"],
            category_id=extraction_data.get("category_id"),
            tags=extraction_data.get("tags"),
            created_by=current_user.id
        )
        
        logger.info(
            "Knowledge extracted from URL via API",
            entry_id=str(entry.id),
            url=extraction_data["url"],
            user_id=str(current_user.id)
        )
        
        return entry.to_dict()
        
    except Exception as e:
        logger.error(
            "URL extraction failed via API",
            url=extraction_data["url"],
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/document", response_model=Dict[str, Any])
async def extract_from_document(
    extraction_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract knowledge from a document.
    
    Args:
        extraction_data: Extraction data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created knowledge entry
    """
    extractor = get_knowledge_extractor()
    
    try:
        entry = await extractor.extract_from_document(
            file_path=extraction_data["file_path"],
            file_type=extraction_data["file_type"],
            category_id=extraction_data.get("category_id"),
            tags=extraction_data.get("tags"),
            created_by=current_user.id
        )
        
        logger.info(
            "Knowledge extracted from document via API",
            entry_id=str(entry.id),
            file_path=extraction_data["file_path"],
            file_type=extraction_data["file_type"],
            user_id=str(current_user.id)
        )
        
        return entry.to_dict()
        
    except Exception as e:
        logger.error(
            "Document extraction failed via API",
            file_path=extraction_data["file_path"],
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/text", response_model=Dict[str, Any])
async def extract_from_text(
    extraction_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract knowledge from raw text.
    
    Args:
        extraction_data: Extraction data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created knowledge entry
    """
    extractor = get_knowledge_extractor()
    
    try:
        entry = await extractor.extract_from_text(
            content=extraction_data["content"],
            title=extraction_data["title"],
            source=extraction_data.get("source", "Manual entry"),
            category_id=extraction_data.get("category_id"),
            tags=extraction_data.get("tags"),
            created_by=current_user.id
        )
        
        logger.info(
            "Knowledge extracted from text via API",
            entry_id=str(entry.id),
            title=extraction_data["title"],
            user_id=str(current_user.id)
        )
        
        return entry.to_dict()
        
    except Exception as e:
        logger.error(
            "Text extraction failed via API",
            title=extraction_data["title"],
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/entries/{entry_id}/analyze", response_model=Dict[str, Any])
async def analyze_entry(
    entry_id: str,
    analysis_types: List[str] = Query(["sentiment", "topics", "keywords"]),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyze a knowledge entry.
    
    Args:
        entry_id: Entry ID
        analysis_types: Types of analysis to perform
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Analysis results
    """
    analyzer = get_knowledge_analyzer()
    
    # Get entry
    engine = get_knowledge_engine()
    entry = await engine.get_knowledge_entry(entry_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    try:
        analysis = await analyzer.analyze_content(entry.content, analysis_types)
        
        logger.info(
            "Knowledge entry analyzed via API",
            entry_id=entry_id,
            analysis_types=analysis_types,
            user_id=str(current_user.id)
        )
        
        return {
            "entry_id": entry_id,
            "analysis": analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Entry analysis failed via API",
            entry_id=entry_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/entries/{entry_id}/categorize", response_model=Dict[str, Any])
async def categorize_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get AI-powered categorization suggestions for an entry.
    
    Args:
        entry_id: Entry ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Categorization suggestions
    """
    analyzer = get_knowledge_analyzer()
    
    # Get entry
    engine = get_knowledge_engine()
    entry = await engine.get_knowledge_entry(entry_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    try:
        categorization = await analyzer.categorize_entry(entry)
        
        logger.info(
            "Entry categorization generated via API",
            entry_id=entry_id,
            user_id=str(current_user.id)
        )
        
        return categorization
        
    except Exception as e:
        logger.error(
            "Entry categorization failed via API",
            entry_id=entry_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Categorization failed: {str(e)}")


@router.get("/statistics", response_model=Dict[str, Any])
async def get_knowledge_statistics(
    period_start: Optional[datetime] = Query(None),
    period_end: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get knowledge base statistics.
    
    Args:
        period_start: Start of period
        period_end: End of period
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Knowledge statistics
    """
    engine = get_knowledge_engine()
    
    try:
        stats = await engine.get_entry_statistics(period_start, period_end)
        
        return stats
        
    except Exception as e:
        logger.error(
            "Knowledge statistics retrieval failed via API",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Statistics retrieval failed: {str(e)}")


@router.get("/my-entries", response_model=List[Dict[str, Any]])
async def get_my_entries(
    status: Optional[KnowledgeStatus] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get entries created by the current user.
    
    Args:
        status: Filter by status
        limit: Maximum number of results
        offset: Pagination offset
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of user's entries
    """
    engine = get_knowledge_engine()
    
    entries = await engine.list_knowledge_entries(
        status=status,
        author=str(current_user.id),
        limit=limit,
        offset=offset
    )
    
    return [entry.to_dict() for entry in entries]
