"""
BaseLayer Codex/Memory Tasks

Arq task definitions for background knowledge processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.codex import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag, SearchIndex,
    KnowledgeStatus, EntryType, KnowledgeType
)
from .engine import KnowledgeEngine
from .search import SearchEngine
from .indexer import KnowledgeIndexer
from .extractor import KnowledgeExtractor
from .analyzer import KnowledgeAnalyzer

logger = get_logger(__name__)

# Global instances (will be initialized in startup)
knowledge_engine: KnowledgeEngine = None
search_engine: SearchEngine = None
knowledge_indexer: KnowledgeIndexer = None
knowledge_extractor: KnowledgeExtractor = None
knowledge_analyzer: KnowledgeAnalyzer = None


async def initialize_codex():
    """Initialize Codex/Memory components."""
    global knowledge_engine, search_engine, knowledge_indexer
    global knowledge_extractor, knowledge_analyzer
    
    knowledge_engine = KnowledgeEngine()
    search_engine = SearchEngine()
    knowledge_indexer = KnowledgeIndexer()
    knowledge_extractor = KnowledgeExtractor()
    knowledge_analyzer = KnowledgeAnalyzer()
    
    await knowledge_indexer.start_indexing_worker()
    await knowledge_extractor.start_extraction_worker()
    await knowledge_analyzer.start_analysis_worker()
    
    logger.info("Codex/Memory components initialized")


async def shutdown_codex():
    """Shutdown Codex/Memory components."""
    global knowledge_indexer, knowledge_extractor, knowledge_analyzer
    
    if knowledge_indexer:
        await knowledge_indexer.stop_indexing_worker()
    
    if knowledge_extractor:
        await knowledge_extractor.stop_extraction_worker()
    
    if knowledge_analyzer:
        await knowledge_analyzer.stop_analysis_worker()
    
    logger.info("Codex/Memory components shutdown")


async def process_pending_indexing(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process pending indexing tasks.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Indexing results
    """
    global knowledge_indexer
    
    if not knowledge_indexer:
        raise RuntimeError("Knowledge indexer not initialized")
    
    try:
        # Get entries that need indexing
        async with db_session_context() as session:
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.deleted_at.is_(None),
                    KnowledgeEntry.status == KnowledgeStatus.PUBLISHED
                ).outerjoin(
                    SearchIndex, KnowledgeEntry.id == SearchIndex.entry_id
                ).where(
                    SearchIndex.id.is_(None)
                ).limit(50)
            )
            entries = result.scalars().all()
        
        processed = 0
        failed = 0
        
        for entry in entries:
            try:
                await knowledge_indexer.index_entry(entry)
                processed += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Failed to index entry",
                    entry_id=str(entry.id),
                    error=str(e)
                )
        
        logger.info(
            "Pending indexing processed",
            total=len(entries),
            processed=processed,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_entries": len(entries),
            "processed": processed,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Pending indexing task failed",
            error=str(e)
        )
        raise


async def update_search_analytics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update search analytics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Analytics update result
    """
    global search_engine
    
    if not search_engine:
        raise RuntimeError("Search engine not initialized")
    
    try:
        # Get search statistics
        cache_stats = search_engine.get_cache_stats()
        
        # Log analytics
        logger.info(
            "Search analytics updated",
            cache_size=cache_stats["cache_size"],
            cache_ttl=cache_stats["cache_ttl"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "cache_stats": cache_stats
        }
        
    except Exception as e:
        logger.error(
            "Search analytics update failed",
            error=str(e)
        )
        raise


async def cleanup_old_entries(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old knowledge entries.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup result
    """
    retention_days = 730  # 2 years
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        async with db_session_context() as session:
            # Soft delete old entries
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.created_at < cutoff_date,
                    KnowledgeEntry.deleted_at.is_(None),
                    KnowledgeEntry.status == KnowledgeStatus.DRAFT
                )
            )
            old_entries = result.scalars().all()
            
            count = 0
            for entry in old_entries:
                entry.soft_delete()
                session.add(entry)
                count += 1
            
            await session.commit()
            
            logger.info(
                "Old knowledge entries cleaned up",
                count=count,
                retention_days=retention_days
            )
            
            return {
                "status": "completed",
                "cleaned_entries": count,
                "retention_days": retention_days,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(
            "Cleanup task failed",
            error=str(e)
        )
        raise


async def optimize_search_index(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to optimize search index.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Optimization result
    """
    global knowledge_indexer
    
    if not knowledge_indexer:
        raise RuntimeError("Knowledge indexer not initialized")
    
    try:
        result = await knowledge_indexer.optimize_search_index()
        
        logger.info(
            "Search index optimization completed",
            status=result["status"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "optimization_result": result
        }
        
    except Exception as e:
        logger.error(
            "Search index optimization failed",
            error=str(e)
        )
        raise


async def analyze_knowledge_trends(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to analyze knowledge trends.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Trend analysis result
    """
    global knowledge_analyzer
    
    if not knowledge_analyzer:
        raise RuntimeError("Knowledge analyzer not initialized")
    
    try:
        # Analyze trends for the last 30 days
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=30)
        
        insights = await knowledge_analyzer.get_knowledge_insights(period_start, period_end)
        
        logger.info(
            "Knowledge trends analysis completed",
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat()
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "insights": insights
        }
        
    except Exception as e:
        logger.error(
            "Knowledge trends analysis failed",
            error=str(e)
        )
        raise


async def update_knowledge_statistics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update knowledge statistics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Statistics update result
    """
    global knowledge_engine
    
    if not knowledge_engine:
        raise RuntimeError("Knowledge engine not initialized")
    
    try:
        # Get current statistics
        stats = await knowledge_engine.get_entry_statistics()
        
        # Log statistics
        logger.info(
            "Knowledge statistics updated",
            total_entries=stats["total_entries"],
            by_status=stats["by_status"],
            by_type=stats["by_type"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(
            "Knowledge statistics update failed",
            error=str(e)
        )
        raise


async def process_ai_analysis_queue(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process AI analysis queue.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Analysis processing result
    """
    global knowledge_analyzer
    
    if not knowledge_analyzer:
        raise RuntimeError("Knowledge analyzer not initialized")
    
    try:
        # Get entries that need AI analysis
        async with db_session_context() as session:
            result = await session.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.deleted_at.is_(None),
                    KnowledgeEntry.status == KnowledgeStatus.PUBLISHED,
                    KnowledgeEntry.metadata_.is_(None)  # No analysis metadata
                ).limit(20)
            )
            entries = result.scalars().all()
        
        processed = 0
        failed = 0
        
        for entry in entries:
            try:
                # Analyze content
                analysis = await knowledge_analyzer.analyze_content(
                    entry.content,
                    ["sentiment", "topics", "keywords", "readability"]
                )
                
                # Update entry metadata with analysis results
                entry.metadata_ = entry.metadata_ or {}
                entry.metadata_["ai_analysis"] = {
                    "analyzed_at": datetime.utcnow().isoformat(),
                    "sentiment": analysis.get("sentiment"),
                    "topics": analysis.get("topics", [])[:5],  # Top 5 topics
                    "keywords": analysis.get("keywords", [])[:10],  # Top 10 keywords
                    "readability": analysis.get("readability")
                }
                
                async with db_session_context() as update_session:
                    update_session.add(entry)
                    await update_session.commit()
                
                processed += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Failed to analyze entry",
                    entry_id=str(entry.id),
                    error=str(e)
                )
        
        logger.info(
            "AI analysis queue processed",
            total_entries=len(entries),
            processed=processed,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_entries": len(entries),
            "processed": processed,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "AI analysis queue processing failed",
            error=str(e)
        )
        raise


async def check_knowledge_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check knowledge system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check result
    """
    try:
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check knowledge engine
        global knowledge_engine
        if knowledge_engine:
            cache_stats = len(knowledge_engine.entry_cache)
            health_status["checks"]["knowledge_engine"] = {
                "status": "healthy",
                "cache_size": cache_stats
            }
        else:
            health_status["checks"]["knowledge_engine"] = {
                "status": "error",
                "message": "Knowledge engine not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check search engine
        global search_engine
        if search_engine:
            cache_stats = search_engine.get_cache_stats()
            health_status["checks"]["search_engine"] = {
                "status": "healthy",
                "cache_size": cache_stats["cache_size"],
                "semantic_enabled": cache_stats["semantic_enabled"]
            }
        else:
            health_status["checks"]["search_engine"] = {
                "status": "error",
                "message": "Search engine not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check indexer
        global knowledge_indexer
        if knowledge_indexer:
            index_stats = await knowledge_indexer.get_index_statistics()
            health_status["checks"]["indexer"] = {
                "status": "healthy",
                "total_indexed": index_stats["total_indexed"],
                "embedding_coverage": index_stats["embedding_coverage"],
                "queue_size": index_stats["queue_size"]
            }
        else:
            health_status["checks"]["indexer"] = {
                "status": "error",
                "message": "Knowledge indexer not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check analyzer
        global knowledge_analyzer
        if knowledge_analyzer:
            cache_stats = knowledge_analyzer.get_cache_stats()
            health_status["checks"]["analyzer"] = {
                "status": "healthy",
                "cache_size": cache_stats["cache_size"],
                "ai_enabled": cache_stats["ai_enabled"]
            }
        else:
            health_status["checks"]["analyzer"] = {
                "status": "error",
                "message": "Knowledge analyzer not initialized"
            }
            health_status["status"] = "unhealthy"
        
        # Check database connectivity
        try:
            async with db_session_context() as session:
                await session.execute("SELECT 1")
                health_status["checks"]["database"] = {
                    "status": "healthy"
                }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Determine overall status
        component_statuses = [
            check["status"] for check in health_status["checks"].values()
        ]
        
        if any(status == "unhealthy" for status in component_statuses):
            health_status["status"] = "unhealthy"
        elif any(status == "degraded" for status in component_statuses):
            health_status["status"] = "degraded"
        
        logger.info(
            "Knowledge health check completed",
            status=health_status["status"]
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Knowledge health check failed",
            error=str(e)
        )
        raise


async def rebuild_search_index(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to rebuild entire search index.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Rebuild result
    """
    global knowledge_indexer
    
    if not knowledge_indexer:
        raise RuntimeError("Knowledge indexer not initialized")
    
    try:
        result = await knowledge_indexer.reindex_all_entries()
        
        logger.info(
            "Search index rebuild completed",
            total=result["total_entries"],
            indexed=result["indexed"],
            failed=result["failed"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "rebuild_result": result
        }
        
    except Exception as e:
        logger.error(
            "Search index rebuild failed",
            error=str(e)
        )
        raise


# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 2,  # Optimized for i5-2400
    "queue_name": "codex",
    "job_timeout": 1800,  # 30 minutes timeout
}

# Cron jobs
cron_jobs = [
    cron(
        process_pending_indexing,
        hour=1,  # 1 AM daily
        minute=0,
    ),
    cron(
        update_search_analytics,
        hour=2,  # 2 AM daily
        minute=0,
    ),
    cron(
        cleanup_old_entries,
        hour=3,  # 3 AM daily
        minute=0,
    ),
    cron(
        optimize_search_index,
        hour=4,  # 4 AM daily (Sunday)
        minute=0,
        weekday=6,
    ),
    cron(
        analyze_knowledge_trends,
        hour=5,  # 5 AM daily
        minute=0,
    ),
    cron(
        update_knowledge_statistics,
        hour=6,  # 6 AM daily
        minute=0,
    ),
    cron(
        process_ai_analysis_queue,
        hour=7,  # 7 AM daily
        minute=0,
    ),
    cron(
        check_knowledge_health,
        minute="*/15",  # Every 15 minutes
    ),
]
