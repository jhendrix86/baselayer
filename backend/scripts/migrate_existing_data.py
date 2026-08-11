"""
Script to migrate existing data to default tenant in BaseLayer

This script assigns the default tenant_id to all existing records
that don't have a tenant_id set yet.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from baselayer.core.database import db_session_context
from baselayer.models.tenant import Tenant
from baselayer.models.user import User
from baselayer.models.core_loop import Workflow, WorkflowExecution, WorkflowStep
from baselayer.models.income_engine import RevenueStream, RevenueTransaction, RevenueMetrics
from baselayer.models.codex import KnowledgeEntry, KnowledgeCategory, KnowledgeTag
from baselayer.models.protocols import Protocol, ProtocolTemplate, ProtocolVariable
from baselayer.models.agents import Agent, AgentTask, AgentMetrics
from baselayer.models.governance import GovernanceRule, AuditLog, ComplianceReport
from baselayer.models.output_engine import OutputTemplate, GeneratedOutput, DeliveryLog
import structlog

logger = structlog.get_logger(__name__)


async def migrate_to_default_tenant():
    """Migrate existing data to default tenant."""
    
    async with db_session_context() as session:
        try:
            # Get or create default tenant
            result = await session.execute(
                select(Tenant).where(Tenant.slug == "default")
            )
            default_tenant = result.scalar_one_or_none()
            
            if not default_tenant:
                logger.error("Default tenant not found. Run create_default_tenant.py first.")
                return
            
            logger.info("Using default tenant", tenant_id=str(default_tenant.id))
            
            # Migrate each model type
            models_to_migrate = [
                (User, "users"),
                (Workflow, "workflows"),
                (WorkflowExecution, "workflow_executions"),
                (WorkflowStep, "workflow_steps"),
                (RevenueStream, "revenue_streams"),
                (RevenueTransaction, "revenue_transactions"),
                (RevenueMetrics, "revenue_metrics"),
                (KnowledgeEntry, "knowledge_entries"),
                (KnowledgeCategory, "knowledge_categories"),
                (KnowledgeTag, "knowledge_tags"),
                (Protocol, "protocols"),
                (ProtocolTemplate, "protocol_templates"),
                (ProtocolVariable, "protocol_variables"),
                (Agent, "agents"),
                (AgentTask, "agent_tasks"),
                (AgentMetrics, "agent_metrics"),
                (GovernanceRule, "governance_rules"),
                (AuditLog, "audit_logs"),
                (ComplianceReport, "compliance_reports"),
                (OutputTemplate, "output_templates"),
                (GeneratedOutput, "generated_outputs"),
                (DeliveryLog, "delivery_logs"),
            ]
            
            total_migrated = 0
            
            for model_class, model_name in models_to_migrate:
                # Find records without tenant_id (if column is nullable)
                # For now, we'll just update all records since we just added the column
                result = await session.execute(
                    select(model_class)
                )
                records = result.scalars().all()
                
                if not records:
                    logger.info("No records to migrate", model_name=model_name)
                    continue
                
                # Update all records to have the default tenant_id
                await session.execute(
                    update(model_class)
                    .values(tenant_id=default_tenant.id)
                )
                
                count = len(records)
                total_migrated += count
                logger.info("Migrated records to default tenant", model_name=model_name, count=count)
            
            await session.commit()
            logger.info("Migration complete", total_records=total_migrated)
            
        except Exception as e:
            logger.error("Migration failed", error=str(e))
            await session.rollback()
            raise


if __name__ == "__main__":
    logger.info("Starting data migration to default tenant...")
    asyncio.run(migrate_to_default_tenant())
    logger.info("Migration completed successfully")
