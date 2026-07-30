"""
BaseLayer Governance/Doctrine API

REST API endpoints for policy management, compliance monitoring, and audit trails.
"""

from .policies import router as policies_router
from .compliance import router as compliance_router
from .audit import router as audit_router
from .risk import router as risk_router
from .automation import router as automation_router
from .dashboard import router as dashboard_router

__all__ = [
    "policies_router",
    "compliance_router", 
    "audit_router",
    "risk_router",
    "automation_router",
    "dashboard_router",
]
