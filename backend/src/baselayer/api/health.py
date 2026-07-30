"""
BaseLayer Health Check Endpoints

Provides health, readiness, and liveness endpoints for monitoring.
"""

from datetime import datetime
from typing import Dict, Any

import asyncpg
import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from baselayer.core.database import get_db_session
from baselayer.core.config import get_settings
from baselayer.core.logging import get_logger

logger = get_logger(__name__)
health_router = APIRouter()


async def check_database_health() -> Dict[str, Any]:
    """
    Check database connectivity and health.
    
    Returns:
        Dict[str, Any]: Database health status
    """
    try:
        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("SELECT 1")
        await conn.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "details": "Database connection successful",
        }
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


async def check_redis_health() -> Dict[str, Any]:
    """
    Check Redis connectivity and health.
    
    Returns:
        Dict[str, Any]: Redis health status
    """
    try:
        settings = get_settings()
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "details": "Redis connection successful",
        }
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


async def check_ollama_health() -> Dict[str, Any]:
    """
    Check Ollama service connectivity.
    
    Returns:
        Dict[str, Any]: Ollama health status
    """
    try:
        import httpx
        
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "details": "Ollama service accessible",
        }
    except Exception as e:
        logger.error("ollama_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


@health_router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns minimal health status for load balancers.
    
    Returns:
        Dict[str, Any]: Health status
    """
    return {
        "status": "healthy",
        "service": "BaseLayer API",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@health_router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Readiness check endpoint.
    
    Checks if all required services are ready to accept traffic.
    
    Args:
        db: Database session
        
    Returns:
        Dict[str, Any]: Readiness status
    """
    # Check database
    db_health = await check_database_health()
    redis_health = await check_redis_health()
    ollama_health = await check_ollama_health()
    
    # Determine overall readiness
    services = {
        "database": db_health["status"] == "healthy",
        "redis": redis_health["status"] == "healthy",
        "ollama": ollama_health["status"] == "healthy",
    }
    
    is_ready = all(services.values())
    
    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": db_health,
            "redis": redis_health,
            "ollama": ollama_health,
        },
    }


@health_router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint.
    
    Checks if the application is alive and responding.
    
    Returns:
        Dict[str, Any]: Liveness status
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "TODO: Implement uptime tracking",
    }


@health_router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Detailed health check endpoint.
    
    Returns comprehensive health information for monitoring.
    
    Args:
        db: Database session
        
    Returns:
        Dict[str, Any]: Detailed health status
    """
    # Check all services
    db_health = await check_database_health()
    redis_health = await check_redis_health()
    ollama_health = await check_ollama_health()
    
    # Get system info
    import psutil
    
    system_info = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "load_average": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
    }
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "environment": get_settings().environment,
        "services": {
            "database": db_health,
            "redis": redis_health,
            "ollama": ollama_health,
        },
        "system": system_info,
        "governance": {
            "mode": get_settings().governance_mode,
            "audit_enabled": get_settings().audit_enabled,
        },
    }
