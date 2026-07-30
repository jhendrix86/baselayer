"""
BaseLayer API v1 Router

Main router for API v1 endpoints.
"""

from fastapi import APIRouter

# Import subsystem routers
from baselayer.core_loop.api.workflows import router as core_loop_router
from baselayer.core_loop.api.executions import router as executions_router
from baselayer.core_loop.api.monitoring import router as monitoring_router
from baselayer.income_engine.api.revenue import router as income_engine_router
from baselayer.codex.api.knowledge import router as codex_router
from baselayer.agents.api.agents import router as agents_router
from baselayer.governance.api.policies import router as governance_router
from baselayer.output_engine.api.templates import router as output_engine_router
from .auth import router as auth_router
from .users import router as users_router

api_v1_router = APIRouter()

# Include all subsystem routers
api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(core_loop_router, prefix="/workflows", tags=["Core Loop"])
api_v1_router.include_router(executions_router, prefix="/executions", tags=["Workflow Executions"])
api_v1_router.include_router(monitoring_router, prefix="/monitoring", tags=["Workflow Monitoring"])
api_v1_router.include_router(income_engine_router, prefix="/revenue", tags=["Income Engine"])
api_v1_router.include_router(codex_router, prefix="/knowledge", tags=["Codex/Memory"])
api_v1_router.include_router(agents_router, prefix="/agents", tags=["Multi-Agent"])
api_v1_router.include_router(governance_router, prefix="/governance", tags=["Governance"])
api_v1_router.include_router(output_engine_router, prefix="/outputs", tags=["Output Engine"])
api_v1_router.include_router(users_router, prefix="/users", tags=["User Management"])

# Temporary endpoints for testing
@api_v1_router.get("/")
async def api_v1_root() -> dict[str, str]:
    """
    API v1 root endpoint.
    
    Returns information about the v1 API.
    """
    return {
        "name": "BaseLayer API v1",
        "version": "1.0.0",
        "description": "Version 1 of the BaseLayer REST API",
        "subsystems": [
            "core-loop",
            "income-engine", 
            "codex",
            "protocols",
            "agents",
            "governance",
            "output-engine",
        ],
    }


@api_v1_router.get("/status")
async def api_status() -> dict[str, str]:
    """
    API status endpoint.
    
    Returns the current status of all subsystems.
    """
    return {
        "status": "operational",
        "subsystems": {
            "core-loop": "pending",
            "income-engine": "pending",
            "codex": "pending", 
            "protocols": "pending",
            "agents": "pending",
            "governance": "pending",
            "output-engine": "pending",
        },
        "governance": {
            "mode": "strict",
            "compliance": "SYS-CRP",
            "maturity": "prototype",
        },
    }
