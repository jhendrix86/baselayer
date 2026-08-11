"""
BaseLayer Database Configuration

Handles SQLAlchemy async database setup and connection management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

from baselayer.core.config import get_settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    All models should inherit from this base class to ensure proper
    table creation and relationship management.
    """
    pass


# Global engine and session instances
engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get async database engine.
    
    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    global engine
    if engine is None:
        settings = get_settings()
        engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.debug,
        )
    return engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Get async session maker.
    
    Returns:
        async_sessionmaker[AsyncSession]: Session factory
    """
    global async_session_maker
    if async_session_maker is None:
        async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for FastAPI dependency injection (Depends(get_db_session)).

    This is a plain async generator, not an async context manager - FastAPI
    handles the yield/cleanup protocol itself for generator-based
    dependencies. Calling `async with get_db_session()` directly (as several
    income_engine modules used to) fails since a bare async generator has no
    __aenter__/__aexit__. Code that needs a session outside of a FastAPI
    dependency (background tasks, engine internals) should use
    db_session_context() below instead.

    Yields:
        AsyncSession: Database session
    """
    async with get_session_maker()() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as a real async context manager, for use outside
    FastAPI's dependency injection (background tasks, engine/manager
    internals that open their own session rather than receiving one).
    """
    async with get_session_maker()() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Create all database tables.
    
    This should only be called during application startup or migrations.
    """
    # Import all models to ensure they're registered in metadata
    from baselayer.models import (
        tenant,
        user,
        core_loop,
        income_engine,
        codex,
        protocols,
        agents,
        governance,
        output_engine,
    )
    
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """
    Drop all database tables.
    
    This should only be called in testing environments.
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_database() -> None:
    """
    Close database connections.
    
    This should be called during application shutdown.
    """
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_maker = None
