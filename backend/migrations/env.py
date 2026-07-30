"""
BaseLayer Alembic Environment Configuration

Database migration environment for PostgreSQL 16 with async support.
"""

from __future__ import with_statement

import asyncio
from logging.config import fileConfig
from os import environ
from pathlib import Path
from typing import Any, Dict

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.orm import sessionmaker

# Add the src directory to the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baselayer.core.database import Base
from baselayer.core.config import get_settings
from baselayer.models import *  # Import all models

# Alembic Config object
alembic_config = context.config

# Interpret the config file for Python logging
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Get database URL from settings
settings = get_settings()
database_url = settings.database_url

# Override sqlalchemy.url in alembic.ini
alembic_config.set_main_option("sqlalchemy.url", database_url)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """
    Get database URL from environment or settings.
    
    Returns:
        str: Database URL
    """
    # Check for environment variable first
    if "DATABASE_URL" in environ:
        return environ["DATABASE_URL"]
    
    # Fall back to settings
    return database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_item_batch_table_fk=render_item_batch_table_fk,
        render_item_constraint=render_item_constraint,
        render_item_index=render_item_index,
        render_item_table=render_item_table,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with the given connection.
    
    Args:
        connection: Database connection
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_item_batch_table_fk=render_item_batch_table_fk,
        render_item_constraint=render_item_constraint,
        render_item_index=render_item_index,
        render_item_table=render_item_table,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.
    """
    configuration = alembic_config.get_section(alembic_config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    asyncio.run(run_async_migrations())


# Custom render functions for better migration readability
def render_item_batch_table_fk(constraint, autogen_context):
    """
    Render batch table foreign key constraints.
    """
    return None  # Skip rendering for cleaner migrations


def render_item_constraint(constraint, autogen_context):
    """
    Render table constraints with better formatting.
    """
    if constraint.name is None:
        return None
    
    # Format constraint names
    if constraint.name.startswith("fk_"):
        return f"ForeignKeyConstraint(['{constraint.columns[0].name}'], " \
               f"['{constraint.column.name}'], name='{constraint.name}')"
    
    return None


def render_item_index(index, autogen_context):
    """
    Render indexes with better formatting.
    """
    if index.name is None:
        return None
    
    columns = [f"'{col.name}'" for col in index.columns]
    return f"Index('{index.name}', {', '.join(columns)})"


def render_item_table(table, autogen_context):
    """
    Render table definitions with better formatting.
    """
    return None  # Use default rendering


# Migration context configuration
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
