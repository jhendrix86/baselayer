"""
BaseLayer Governance/Doctrine Module

Policy management, compliance monitoring, and audit trail
for the Governance/Doctrine subsystem.
"""

from .engine import GovernanceEngine
from .policy_manager import PolicyManager
from .compliance_monitor import ComplianceMonitor
from .audit_trail import AuditTrail
from .risk_assessor import RiskAssessor
from .rule_automator import RuleAutomator
from .dashboard import ComplianceDashboard
from .exceptions import (
    GovernanceError,
    PolicyError,
    ComplianceError,
    AuditError,
    RiskError,
    AutomationError,
    DashboardError,
)

__all__ = [
    # Core components
    "GovernanceEngine",
    "PolicyManager",
    "ComplianceMonitor",
    "AuditTrail",
    "RiskAssessor",
    "RuleAutomator",
    "ComplianceDashboard",
    # Exceptions
    "GovernanceError",
    "PolicyError",
    "ComplianceError",
    "AuditError",
    "RiskError",
    "AutomationError",
    "DashboardError",
]
