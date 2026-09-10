"""
BaseLayer Database Configuration

Handles SQLAlchemy async database setup and connection management.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase, Session, with_loader_criteria

from baselayer.core.config import get_settings
from baselayer.core.tenant_context import get_tenant_context

logger = structlog.get_logger(__name__)


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
        engine_kwargs: dict = {"echo": settings.debug}
        # pool_size/max_overflow configure QueuePool and aren't accepted by
        # SQLite's default pool (NullPool/SingletonThreadPool depending on
        # URL) - passing them raises a TypeError before the engine is even
        # built. Only relevant path today is the test suite's
        # sqlite+aiosqlite:///:memory: override (tests/conftest.py); every
        # real deployment uses Postgres.
        if not settings.database_url.startswith("sqlite"):
            engine_kwargs["pool_size"] = settings.database_pool_size
            engine_kwargs["max_overflow"] = settings.database_max_overflow
            # Validate a pooled connection before handing it out. On the
            # deployment target Postgres is restarted (or briefly stalls
            # under the post-reboot I/O storm) out from under a
            # long-lived pool; without pre-ping the first query after that
            # fails with a stale-connection error instead of transparently
            # reconnecting.
            engine_kwargs["pool_pre_ping"] = True
        engine = create_async_engine(settings.database_url, **engine_kwargs)
    return engine


async def _check_database_connection() -> None:
    """Open a throwaway connection and run ``SELECT 1``. Raises on failure.

    Factored out so ``wait_for_database`` has a single seam to exercise
    (and for tests to substitute).
    """
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def wait_for_database(
    max_attempts: int = 30,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> None:
    """Block until the database accepts a connection, or raise.

    On the deployment target (~40 containers cold-starting together on an
    HDD-backed host after a reboot), Postgres is regularly not ready for
    tens of seconds while the I/O storm passes. Without this gate the
    backend's first query in ``create_tables()`` raises
    ConnectionRefused/OperationalError, the container exits, and
    ``restart: unless-stopped`` just crash-loops against the same closed
    window until a human runs ``docker restart`` by hand. This has
    recurred on essentially every Nexus reboot (see HANDOFF.md,
    2026-08-29 through 2026-09-08).

    Retries with capped exponential backoff. With the defaults the
    worst-case total wait is ~4.5 min (1+2+4+8, then 10s flat), comfortably
    longer than any observed storm; after that it gives up so a genuinely
    misconfigured ``DATABASE_URL`` still fails loudly instead of hanging
    forever.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            await _check_database_connection()
            if attempt > 1:
                logger.info("database.ready", attempts=attempt)
            return
        except Exception as exc:  # noqa: BLE001 - any connect failure is retryable here
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "database.not_ready",
                attempt=attempt,
                max_attempts=max_attempts,
                retry_in_seconds=round(delay, 1),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"database not reachable after {max_attempts} attempts"
    ) from last_exc


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
