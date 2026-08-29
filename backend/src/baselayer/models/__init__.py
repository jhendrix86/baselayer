"""
BaseLayer Database Models

SQLAlchemy models for all 7 subsystems with proper relationships,
constraints, and indexes optimized for i5-2400 hardware.
"""

from .base import Base, BaseModel
from .tenant import Tenant
from .user import User
from .core_loop import Workflow, WorkflowExecution, WorkflowStep
from .income_engine import RevenueStream, RevenueTransaction, RevenueMetrics
from .codex import KnowledgeEntry, KnowledgeCategory, KnowledgeTag
from .protocols import Protocol, ProtocolTemplate, ProtocolVariable
from .agents import Agent, AgentTask, AgentMetrics, AgentMessage
from .governance import GovernanceRule, AuditLog, ComplianceReport
from .output_engine import OutputTemplate, GeneratedOutput, DeliveryLog

__all__ = [
    # Base
    "Base",
    "BaseModel",
    # Multi-tenancy
    "Tenant",
    # User Management
    "User",
    # Core Loop
    "Workflow",
    "WorkflowExecution", 
    "WorkflowStep",
    # Income Engine
    "RevenueStream",
    "RevenueTransaction",
    "RevenueMetrics",
    # Codex/Memory
    "KnowledgeEntry",
    "KnowledgeCategory",
    "KnowledgeTag",
    # Protocol Libraries
    "Protocol",
    "ProtocolTemplate",
    "ProtocolVariable",
    # Multi-Agent Orchestration
    "Agent",
    "AgentTask",
    "AgentMetrics",
    "AgentMessage",
    # Governance/Doctrine
    "GovernanceRule",
    "AuditLog",
    "ComplianceReport",
    # Output Engineering
    "OutputTemplate",
    "GeneratedOutput",
    "DeliveryLog",
]
