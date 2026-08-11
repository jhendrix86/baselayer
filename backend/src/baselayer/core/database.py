"""
BaseLayer Database Configuration

Handles SQLAlchemy async database setup and connection management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase, Session, with_loader_criteria

from baselayer.core.config import get_settings
from baselayer.core.tenant_context import get_tenant_context


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    All models should inherit from this base class to ensure proper
    table creation and relationship management.
    """
    pass


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filtering(orm_execute_state):
    """
    Automatically scope SELECTs against income_engine's tenant-owned
    entities to the current tenant context.

    No-ops whenever no tenant context is set on the current request - the
    same fail-open posture used elsewhere in this fleet (e.g. unkey-auth)
    so existing callers that don't set X-Tenant-ID aren't silently broken.

    tenant_id is resolved here, once, into a plain closure variable before
    building each criteria lambda - SQLAlchemy's lambda-SQL caching
    forbids invoking a function (e.g. get_tenant_context()) from inside a
    with_loader_criteria callable, since it normally extracts bound
    values without calling the lambda body at all. Each entity gets its
    own with_loader_criteria call (rather than one shared callable
    branching on cls) so the lambda's returned expression shape never
    varies within a single cached code object - see content-engine's
    commit 405bee5 for the full writeup of what breaks otherwise.

    NOT verified against a real query execution (unlike the equivalent
    change on content-engine/marketing-automation-engine/
    revenue-operations-engine, each proven via a real cross-tenant test):
    income_engine's models use Postgres-specific JSONB/ENUM columns that
    don't compile against the SQLite fallback this environment's tests
    otherwise use, and no real Postgres is available here (a pre-existing,
    already-documented gap - see HANDOFF.md's "baselayer backend repair"
    section). Reviewed carefully against the same pattern already proven
    correct three times over, but flagging this explicitly rather than
    claiming verified.
    """
    if not orm_execute_state.is_select:
        return

    tenant_id = get_tenant_context()
    if tenant_id is None:
        return

    from baselayer.models.income_engine import RevenueStream, RevenueTransaction, RevenueMetrics

    def _tenant_criteria(cls):
        return cls.tenant_id == tenant_id

    orm_execute_state.statement = orm_execute_state.statement.options(
        with_loader_criteria(RevenueStream, _tenant_criteria, include_aliases=True),
        with_loader_criteria(RevenueTransaction, _tenant_criteria, include_aliases=True),
        with_loader_criteria(RevenueMetrics, _tenant_criteria, include_aliases=True),
    )


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
