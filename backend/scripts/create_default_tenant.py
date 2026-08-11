"""
Script to create a default tenant for existing data migration in BaseLayer

This script creates a default tenant that can be used to assign
tenant_id to existing data during the migration process.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from baselayer.core.database import db_session_context
from baselayer.models.tenant import Tenant
import structlog

logger = structlog.get_logger(__name__)


async def create_default_tenant():
    """Create a default tenant for existing data migration."""
    
    async with db_session_context() as session:
        try:
            # Check if default tenant already exists
            result = await session.execute(
                select(Tenant).where(Tenant.slug == "default")
            )
            existing_tenant = result.scalar_one_or_none()
            
            if existing_tenant:
                logger.info("Default tenant already exists", tenant_id=str(existing_tenant.id))
                return existing_tenant.id
            
            # Create default tenant
            default_tenant = Tenant(
                name="Default Tenant",
                slug="default",
                description="Default tenant for migrating existing data",
                is_active=True
            )
            
            session.add(default_tenant)
            await session.commit()
            await session.refresh(default_tenant)
            
            logger.info("Created default tenant", tenant_id=str(default_tenant.id))
            logger.info("Use this tenant_id for migrating existing data", tenant_id=str(default_tenant.id))
            
            return default_tenant.id
            
        except Exception as e:
            logger.error("Failed to create default tenant", error=str(e))
            await session.rollback()
            raise


if __name__ == "__main__":
    logger.info("Creating default tenant...")
    tenant_id = asyncio.run(create_default_tenant())
    logger.info("Default tenant ID", tenant_id=str(tenant_id))
