#!/usr/bin/env python3
"""
BaseLayer Database Seed Script

Populates the database with realistic initial data for all 7 subsystems.
Idempotent script that can be run multiple times safely.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baselayer.core.config import get_settings
from baselayer.core.database import Base
from baselayer.models import (
    User, UserRole, Workflow, WorkflowStatus, WorkflowPriority,
    RevenueStream, RevenueType, RevenueStatus, PricingModel,
    KnowledgeEntry, KnowledgeType, KnowledgeStatus,
    Protocol, ProtocolCategory, ProtocolStatus,
    Agent, AgentType, AgentStatus,
    GovernanceRule, GovernanceCategory, RuleStatus, RuleType,
    OutputTemplate, OutputType, OutputFormat,
)


class DatabaseSeeder:
    """Database seeder for BaseLayer."""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_async_engine(self.settings.database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def seed_all(self) -> None:
        """Seed all data for all subsystems."""
        async with self.async_session() as session:
            # Create tables if they don't exist
            await self.create_tables()
            
            # Seed data in dependency order
            await self.seed_users(session)
            await self.seed_governance_rules(session)
            await self.seed_workflows(session)
            await self.seed_revenue_streams(session)
            await self.seed_knowledge_entries(session)
            await self.seed_protocols(session)
            await self.seed_agents(session)
            await self.seed_output_templates(session)
            
            await session.commit()
            print("✅ Database seeded successfully!")
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created/verified")
    
    async def seed_users(self, session: AsyncSession) -> None:
        """Seed user accounts."""
        users_data = [
            {
                "username": "admin",
                "email": "admin@baselayer.local",
                "full_name": "System Administrator",
                "role": UserRole.ADMIN,
                "is_active": True,
                "is_verified": True,
                "password_hash": "$2b$12$hashed_password_here",  # Would be properly hashed
                "compliance_level": "high",
                "audit_required": True,
            },
            {
                "username": "operator",
                "email": "operator@baselayer.local",
                "full_name": "System Operator",
                "role": UserRole.OPERATOR,
                "is_active": True,
                "is_verified": True,
                "password_hash": "$2b$12$hashed_password_here",
                "compliance_level": "standard",
                "audit_required": False,
            },
            {
                "username": "viewer",
                "email": "viewer@baselayer.local",
                "full_name": "System Viewer",
                "role": UserRole.VIEWER,
                "is_active": True,
                "is_verified": True,
                "password_hash": "$2b$12$hashed_password_here",
                "compliance_level": "standard",
                "audit_required": False,
            },
        ]
        
        for user_data in users_data:
            # Check if user already exists
            existing = await session.execute(
                f"SELECT id FROM users WHERE username = '{user_data['username']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                user = User(**user_data)
                session.add(user)
                print(f"  ✅ Created user: {user_data['username']}")
            else:
                print(f"  ⏭️  User already exists: {user_data['username']}")
    
    async def seed_governance_rules(self, session: AsyncSession) -> None:
        """Seed governance rules."""
        rules_data = [
            {
                "name": "Security Baseline Enforcement",
                "description": "Enforces minimum security standards for all operations",
                "category": GovernanceCategory.SECURITY,
                "priority": "high",
                "status": RuleStatus.ACTIVE,
                "rule_type": RuleType.ENFORCEMENT,
                "rule_definition": {
                    "requirements": [
                        "all_api_calls_must_be_authenticated",
                        "sensitive_data_must_be_encrypted",
                        "password_minimum_length_8_chars"
                    ]
                },
                "enforcement_level": "blocking",
                "sys_crp_mapping": {"CRP-06": "Security Baseline"},
                "maturity_level": "4",
            },
            {
                "name": "Audit Trail Requirements",
                "description": "Maintains comprehensive audit logs for compliance",
                "category": GovernanceCategory.COMPLIANCE,
                "priority": "high",
                "status": RuleStatus.ACTIVE,
                "rule_type": RuleType.AUDIT,
                "rule_definition": {
                    "log_all_user_actions": True,
                    "log_data_changes": True,
                    "retention_days": 365
                },
                "enforcement_level": "advisory",
                "sys_crp_mapping": {"CRP-04": "Logging/Observability"},
                "maturity_level": "5",
            },
            {
                "name": "Performance Threshold Monitoring",
                "description": "Monitors system performance against defined thresholds",
                "category": GovernanceCategory.PERFORMANCE,
                "priority": "medium",
                "status": RuleStatus.ACTIVE,
                "rule_type": RuleType.MONITORING,
                "rule_definition": {
                    "response_time_threshold_ms": 5000,
                    "cpu_usage_threshold_percent": 80,
                    "memory_usage_threshold_percent": 85
                },
                "enforcement_level": "warning",
                "sys_crp_mapping": {"CRP-05": "Performance Thresholds"},
                "maturity_level": "3",
            },
        ]
        
        for rule_data in rules_data:
            existing = await session.execute(
                f"SELECT id FROM governance_rules WHERE name = '{rule_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                rule = GovernanceRule(**rule_data)
                session.add(rule)
                print(f"  ✅ Created governance rule: {rule_data['name']}")
            else:
                print(f"  ⏭️  Governance rule already exists: {rule_data['name']}")
    
    async def seed_workflows(self, session: AsyncSession) -> None:
        """Seed workflow definitions."""
        workflows_data = [
            {
                "name": "Daily System Health Check",
                "description": "Automated health check for all system components",
                "status": WorkflowStatus.ACTIVE,
                "priority": WorkflowPriority.HIGH,
                "config": {
                    "steps": [
                        {
                            "id": "check_database",
                            "name": "Check Database Connectivity",
                            "type": "task",
                            "config": {"timeout": 30}
                        },
                        {
                            "id": "check_redis",
                            "name": "Check Redis Connectivity",
                            "type": "task",
                            "config": {"timeout": 10}
                        },
                        {
                            "id": "check_ollama",
                            "name": "Check Ollama Service",
                            "type": "task",
                            "config": {"timeout": 60}
                        }
                    ]
                },
                "schedule_type": "recurring",
                "schedule_expression": "0 8 * * *",
                "governance_required": True,
                "audit_level": "standard",
                "category": "monitoring",
                "tags": ["health", "monitoring", "daily"],
            },
            {
                "name": "Revenue Report Generation",
                "description": "Generate monthly revenue reports",
                "status": WorkflowStatus.ACTIVE,
                "priority": WorkflowPriority.MEDIUM,
                "config": {
                    "steps": [
                        {
                            "id": "collect_revenue_data",
                            "name": "Collect Revenue Data",
                            "type": "task",
                            "config": {"date_range": "monthly"}
                        },
                        {
                            "id": "generate_report",
                            "name": "Generate PDF Report",
                            "type": "task",
                            "config": {"template": "monthly_revenue"}
                        },
                        {
                            "id": "send_email",
                            "name": "Email Report to Stakeholders",
                            "type": "webhook",
                            "config": {"recipients": ["finance@baselayer.local"]}
                        }
                    ]
                },
                "schedule_type": "recurring",
                "schedule_expression": "0 9 1 * *",
                "governance_required": True,
                "audit_level": "high",
                "category": "reporting",
                "tags": ["revenue", "reporting", "monthly"],
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for workflow_data in workflows_data:
            existing = await session.execute(
                f"SELECT id FROM workflows WHERE name = '{workflow_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                workflow_data["created_by"] = admin_id
                workflow = Workflow(**workflow_data)
                session.add(workflow)
                print(f"  ✅ Created workflow: {workflow_data['name']}")
            else:
                print(f"  ⏭️  Workflow already exists: {workflow_data['name']}")
    
    async def seed_revenue_streams(self, session: AsyncSession) -> None:
        """Seed revenue streams."""
        revenue_streams_data = [
            {
                "name": "Premium Subscription",
                "description": "Monthly premium subscription for advanced features",
                "revenue_type": RevenueType.SUBSCRIPTION,
                "status": RevenueStatus.ACTIVE,
                "pricing_model": PricingModel.TIERED,
                "base_amount": 29.99,
                "currency": "USD",
                "billing_cycle": "monthly",
                "billing_day": "1",
                "usage_limits": {
                    "tiers": [
                        {"name": "Basic", "price": 29.99, "features": ["api_access", "basic_support"]},
                        {"name": "Pro", "price": 99.99, "features": ["api_access", "priority_support", "advanced_analytics"]},
                        {"name": "Enterprise", "price": 299.99, "features": ["unlimited_api", "dedicated_support", "custom_integrations"]}
                    ]
                },
                "auto_bill": True,
                "retry_failed_payments": True,
                "category": "subscription",
                "tags": ["subscription", "recurring", "premium"],
            },
            {
                "name": "API Usage Billing",
                "description": "Pay-per-use API billing for additional requests",
                "revenue_type": RevenueType.USAGE_BASED,
                "status": RevenueStatus.ACTIVE,
                "pricing_model": PricingModel.USAGE_BASED,
                "base_amount": 0.001,
                "currency": "USD",
                "usage_limits": {
                    "unit": "request",
                    "pricing_tiers": [
                        {"min_requests": 0, "max_requests": 10000, "price_per_request": 0.001},
                        {"min_requests": 10001, "max_requests": 100000, "price_per_request": 0.0005},
                        {"min_requests": 100001, "max_requests": None, "price_per_request": 0.0001}
                    ]
                },
                "category": "usage",
                "tags": ["api", "usage", "billing"],
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for stream_data in revenue_streams_data:
            existing = await session.execute(
                f"SELECT id FROM revenue_streams WHERE name = '{stream_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                stream_data["created_by"] = admin_id
                stream = RevenueStream(**stream_data)
                session.add(stream)
                print(f"  ✅ Created revenue stream: {stream_data['name']}")
            else:
                print(f"  ⏭️  Revenue stream already exists: {stream_data['name']}")
    
    async def seed_knowledge_entries(self, session: AsyncSession) -> None:
        """Seed knowledge entries."""
        knowledge_data = [
            {
                "title": "System Architecture Overview",
                "description": "High-level overview of BaseLayer system architecture",
                "content": """# BaseLayer System Architecture

## Overview
BaseLayer is a modular, governance-grade operational system built on a 7-subsystem architecture.

## Subsystems
1. **Core Loop**: Workflow orchestration and execution
2. **Income Engine**: Revenue stream management and automation
3. **Codex/Memory**: Knowledge management and search
4. **Protocol Libraries**: Reusable workflow templates
5. **Multi-Agent Orchestration**: AI agent management
6. **Governance/Doctrine**: Compliance and rule enforcement
7. **Output Engineering**: Report generation and delivery

## Technology Stack
- Backend: Python 3.12, FastAPI, PostgreSQL 16, Redis 7
- Frontend: React 19, Vite 6, Tailwind CSS 4
- Infrastructure: Docker, Caddy, systemd
- AI: Ollama with local LLM models

## Hardware Requirements
- CPU: i5-2400 quad-core 3.10GHz
- RAM: 16GB DDR3
- Storage: 2x1TB HDD
- OS: Ubuntu 22.04 LTS
""",
                "knowledge_type": KnowledgeType.DOCUMENT,
                "status": KnowledgeStatus.PUBLISHED,
                "language": "en",
                "version": "1.0.0",
                "access_level": "public",
                "tags": ["architecture", "overview", "system"],
                "author": "System Administrator",
            },
            {
                "title": "API Authentication Guide",
                "description": "Guide to implementing API authentication with BaseLayer",
                "content": """# API Authentication Guide

## Overview
BaseLayer uses JWT-based authentication for API access.

## Getting Started
1. Generate an API key from the admin dashboard
2. Include the API key in the Authorization header
3. Use the token for subsequent requests

## Example
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \\
     https://baselayer.local/api/v1/users/me
```

## Token Lifecycle
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Use the refresh endpoint to get new access tokens
""",
                "knowledge_type": KnowledgeType.PROCEDURE,
                "status": KnowledgeStatus.PUBLISHED,
                "language": "en",
                "version": "1.1.0",
                "access_level": "restricted",
                "required_roles": ["operator", "admin"],
                "tags": ["api", "authentication", "security"],
                "author": "Security Team",
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for entry_data in knowledge_data:
            existing = await session.execute(
                f"SELECT id FROM knowledge_entries WHERE title = '{entry_data['title']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                entry_data["created_by"] = admin_id
                entry = KnowledgeEntry(**entry_data)
                session.add(entry)
                print(f"  ✅ Created knowledge entry: {entry_data['title']}")
            else:
                print(f"  ⏭️  Knowledge entry already exists: {entry_data['title']}")
    
    async def seed_protocols(self, session: AsyncSession) -> None:
        """Seed protocol templates."""
        protocols_data = [
            {
                "name": "User Onboarding Workflow",
                "description": "Standard workflow for onboarding new users",
                "category": ProtocolCategory.WORKFLOW,
                "status": ProtocolStatus.PUBLISHED,
                "version": "1.0.0",
                "template_definition": {
                    "description": "Complete user onboarding process",
                    "estimated_duration": "30 minutes",
                    "required_roles": ["operator"]
                },
                "variables": {
                    "user_email": {
                        "type": "string",
                        "required": True,
                        "description": "Email address of new user"
                    },
                    "user_role": {
                        "type": "string",
                        "required": True,
                        "default": "viewer",
                        "description": "Role to assign to user"
                    }
                },
                "steps": [
                    {
                        "id": "create_user",
                        "name": "Create User Account",
                        "type": "task",
                        "config": {"action": "create_user"}
                    },
                    {
                        "id": "send_welcome",
                        "name": "Send Welcome Email",
                        "type": "webhook",
                        "config": {"template": "welcome_email"}
                    },
                    {
                        "id": "schedule_training",
                        "name": "Schedule Training Session",
                        "type": "task",
                        "config": {"training_type": "basic"}
                    }
                ],
                "governance_required": True,
                "compliance_level": "standard",
                "tags": ["onboarding", "user", "workflow"],
                "author": "Operations Team",
            },
            {
                "name": "System Backup Protocol",
                "description": "Automated system backup and verification",
                "category": ProtocolCategory.AUTOMATION,
                "status": ProtocolStatus.PUBLISHED,
                "version": "1.2.0",
                "template_definition": {
                    "description": "Complete system backup with verification",
                    "estimated_duration": "2 hours",
                    "required_roles": ["operator", "admin"]
                },
                "variables": {
                    "backup_type": {
                        "type": "string",
                        "required": True,
                        "default": "full",
                        "description": "Type of backup (full, incremental)"
                    },
                    "retention_days": {
                        "type": "number",
                        "required": False,
                        "default": 30,
                        "description": "Days to retain backup"
                    }
                },
                "steps": [
                    {
                        "id": "backup_database",
                        "name": "Backup PostgreSQL Database",
                        "type": "task",
                        "config": {"compression": "gzip"}
                    },
                    {
                        "id": "backup_files",
                        "name": "Backup Application Files",
                        "type": "task",
                        "config": {"exclude_temp": True}
                    },
                    {
                        "id": "verify_backup",
                        "name": "Verify Backup Integrity",
                        "type": "task",
                        "config": {"checksum_verification": True}
                    },
                    {
                        "id": "upload_backup",
                        "name": "Upload to Backup Storage",
                        "type": "task",
                        "config": {"encryption": True}
                    }
                ],
                "governance_required": True,
                "compliance_level": "high",
                "tags": ["backup", "automation", "security"],
                "author": "System Administrator",
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for protocol_data in protocols_data:
            existing = await session.execute(
                f"SELECT id FROM protocols WHERE name = '{protocol_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                protocol_data["created_by"] = admin_id
                protocol = Protocol(**protocol_data)
                session.add(protocol)
                print(f"  ✅ Created protocol: {protocol_data['name']}")
            else:
                print(f"  ⏭️  Protocol already exists: {protocol_data['name']}")
    
    async def seed_agents(self, session: AsyncSession) -> None:
        """Seed AI agents."""
        agents_data = [
            {
                "name": "Code Review Agent",
                "description": "AI agent for automated code review and analysis",
                "agent_type": AgentType.SPECIALIST,
                "status": AgentStatus.IDLE,
                "model": "qwen2.5-coder:3b",
                "config": {
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "system_prompt": "You are a code review assistant. Analyze code for quality, security, and best practices."
                },
                "capabilities": {
                    "code_analysis": True,
                    "security_review": True,
                    "performance_analysis": True,
                    "style_checking": True
                },
                "max_concurrent_tasks": 3,
                "timeout_seconds": 300,
                "resource_requirements": {
                    "cpu_cores": 1,
                    "memory_mb": 512,
                    "disk_mb": 100
                },
                "governance_required": True,
                "audit_level": "standard",
            },
            {
                "name": "Workflow Coordinator",
                "description": "Coordinates workflow execution and task distribution",
                "agent_type": AgentType.COORDINATOR,
                "status": AgentStatus.IDLE,
                "model": "qwen2.5-coder:3b",
                "config": {
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "system_prompt": "You coordinate workflow execution and task distribution."
                },
                "capabilities": {
                    "task_scheduling": True,
                    "load_balancing": True,
                    "dependency_resolution": True,
                    "error_handling": True
                },
                "max_concurrent_tasks": 10,
                "timeout_seconds": 600,
                "resource_requirements": {
                    "cpu_cores": 2,
                    "memory_mb": 1024,
                    "disk_mb": 200
                },
                "governance_required": True,
                "audit_level": "high",
            },
            {
                "name": "Report Generator",
                "description": "Generates various types of reports from system data",
                "agent_type": AgentType.WORKER,
                "status": AgentStatus.IDLE,
                "model": "qwen2.5-coder:3b",
                "config": {
                    "temperature": 0.2,
                    "max_tokens": 4096,
                    "system_prompt": "You generate reports from system data. Focus on clarity and accuracy."
                },
                "capabilities": {
                    "data_analysis": True,
                    "report_generation": True,
                    "chart_creation": True,
                    "summary_generation": True
                },
                "max_concurrent_tasks": 5,
                "timeout_seconds": 180,
                "resource_requirements": {
                    "cpu_cores": 1,
                    "memory_mb": 768,
                    "disk_mb": 150
                },
                "governance_required": False,
                "audit_level": "standard",
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for agent_data in agents_data:
            existing = await session.execute(
                f"SELECT id FROM agents WHERE name = '{agent_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                agent_data["created_by"] = admin_id
                agent = Agent(**agent_data)
                session.add(agent)
                print(f"  ✅ Created agent: {agent_data['name']}")
            else:
                print(f"  ⏭️  Agent already exists: {agent_data['name']}")
    
    async def seed_output_templates(self, session: AsyncSession) -> None:
        """Seed output templates."""
        templates_data = [
            {
                "name": "Monthly Revenue Report",
                "description": "Template for generating monthly revenue reports",
                "output_type": OutputType.REPORT,
                "output_format": OutputFormat.PDF,
                "template_content": """# Monthly Revenue Report - {{month}} {{year}}

## Executive Summary
Total Revenue: ${{total_revenue:,.2f}}
Growth Rate: {{growth_rate}}%
New Customers: {{new_customers}}
Churned Customers: {{churned_customers}}

## Revenue Breakdown
{% for stream in revenue_streams %}
- {{stream.name}}: ${{stream.amount:,.2f}} ({{stream.percentage}}%)
{% endfor %}

## Key Metrics
- Average Revenue Per Customer: ${{arpc:,.2f}}
- Customer Lifetime Value: ${{clv:,.2f}}
- Monthly Recurring Revenue: ${{mrr:,.2f}}

## Recommendations
{{recommendations}}

---
*Report generated on {{generation_date}}*
""",
                "variables": {
                    "month": {
                        "type": "string",
                        "required": True,
                        "description": "Month for the report"
                    },
                    "year": {
                        "type": "number",
                        "required": True,
                        "description": "Year for the report"
                    },
                    "total_revenue": {
                        "type": "number",
                        "required": True,
                        "description": "Total revenue amount"
                    },
                    "growth_rate": {
                        "type": "number",
                        "required": True,
                        "description": "Growth rate percentage"
                    }
                },
                "default_delivery_methods": ["email", "file"],
                "governance_required": True,
                "tags": ["revenue", "report", "monthly"],
                "author": "Finance Team",
            },
            {
                "name": "System Health Notification",
                "description": "Template for system health alert notifications",
                "output_type": OutputType.NOTIFICATION,
                "output_format": OutputFormat.HTML,
                "template_content": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background-color: #{{alert_color}}; color: white; padding: 20px; text-align: center;">
    <h1>🚨 {{alert_type}} Alert</h1>
  </div>
  
  <div style="padding: 20px; background-color: #f9f9f9;">
    <h2>System Health Report</h2>
    <p><strong>Timestamp:</strong> {{timestamp}}</p>
    <p><strong>System:</strong> {{system_name}}</p>
    
    <h3>Service Status</h3>
    <ul>
      {% for service in services %}
      <li style="color: {{service.color}};">{{service.name}}: {{service.status}}</li>
      {% endfor %}
    </ul>
    
    {% if recommendations %}
    <h3>Recommendations</h3>
    <ul>
      {% for rec in recommendations %}
      <li>{{rec}}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  
  <div style="background-color: #eee; padding: 10px; text-align: center; font-size: 12px;">
    <p>This is an automated notification from BaseLayer.</p>
  </div>
</div>""",
                "variables": {
                    "alert_type": {
                        "type": "string",
                        "required": True,
                        "description": "Type of alert (Warning, Critical, Info)"
                    },
                    "alert_color": {
                        "type": "string",
                        "required": True,
                        "default": "#ff9800",
                        "description": "Color for alert header"
                    },
                    "system_name": {
                        "type": "string",
                        "required": True,
                        "default": "BaseLayer",
                        "description": "Name of the system"
                    },
                    "services": {
                        "type": "array",
                        "required": True,
                        "description": "List of services with status"
                    }
                },
                "default_delivery_methods": ["email"],
                "governance_required": False,
                "tags": ["health", "notification", "alert"],
                "author": "System Administrator",
            },
        ]
        
        # Get admin user for created_by
        admin_result = await session.execute(
            "SELECT id FROM users WHERE username = 'admin' AND deleted_at IS NULL"
        )
        admin_id = admin_result.scalar()
        
        for template_data in templates_data:
            existing = await session.execute(
                f"SELECT id FROM output_templates WHERE name = '{template_data['name']}' AND deleted_at IS NULL"
            )
            if not existing.scalar():
                template_data["created_by"] = admin_id
                template = OutputTemplate(**template_data)
                session.add(template)
                print(f"  ✅ Created output template: {template_data['name']}")
            else:
                print(f"  ⏭️  Output template already exists: {template_data['name']}")


async def main() -> None:
    """Main seeding function."""
    print("🌱 Starting BaseLayer database seeding...")
    
    seeder = DatabaseSeeder()
    await seeder.seed_all()
    
    print("🎉 Database seeding completed!")


if __name__ == "__main__":
    asyncio.run(main())
