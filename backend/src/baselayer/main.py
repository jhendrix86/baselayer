"""
BaseLayer FastAPI Application Entry Point

This is the main entry point for the BaseLayer backend API.
It initializes the FastAPI application, middleware, and includes all routers.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from baselayer.core.config import get_settings
from baselayer.core.database import engine, Base
from baselayer.core.logging import setup_logging
from baselayer.core.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
)
from baselayer.api.v1.router import api_v1_router
from baselayer.api.health import health_router
from baselayer.api.metrics import metrics_router

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)

# Get application settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting BaseLayer API server", version="0.1.0")
    
    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
    
    # Initialize Redis connection
    # This will be implemented in Phase 4
    
    yield
    
    # Shutdown
    logger.info("Shutting down BaseLayer API server")
    await engine.dispose()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="BaseLayer API",
    description="A modular, governance-grade operational system",
    version="0.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
    lifespan=lifespan,
)

# Add middleware in the correct order
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
app.include_router(api_v1_router, prefix="/api/v1", tags=["API v1"])


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.
    
    Returns basic information about the API.
    """
    return {
        "name": "BaseLayer API",
        "version": "0.1.0",
        "description": "A modular, governance-grade operational system",
        "docs": "/docs" if settings.environment == "development" else "Documentation disabled",
    }


@app.get("/prometheus")
async def prometheus_metrics() -> str:
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for Netdata integration.
    """
    return generate_latest()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "baselayer.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level="info",
    )
