"""
BaseLayer API v1 Router

Main router for API v1 endpoints.

Subsystem routers are imported defensively: several subsystems (codex,
agents, governance, output_engine, as of this writing) have pre-existing
import errors that would otherwise take down the entire API if imported
unconditionally at module level. A broken subsystem is logged and skipped
rather than blocking every other subsystem, including the ones that work.

Current known causes (see `OS42_REPAIR_PLAN.md` for status): codex and
output_engine each reference an enum/column (`EntryType`, `TemplateType`)
that was never added to their models file - a real rename mismatch between
the model and the code that consumes it, not a 1-line fix, since the
model's existing enum values don't cover what the consuming code needs.
agents references a whole `AgentMessage` model that doesn't exist yet.
governance's `RuleStatus` mismatch is fixed (was the same shape as
codex/output_engine's), but governance/api/__init__.py still imports 5
router modules (compliance, audit, risk, automation, dashboard) of which
only policies.py exists on disk.
"""

import structlog
from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router

logger = structlog.get_logger(__name__)

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, tags=["Authentication"])
api_v1_router.include_router(users_router, tags=["User Management"])

# Every one of these routers already declares its own internal prefix
# (e.g. revenue.py: APIRouter(prefix="/revenue", ...)) - mount kwargs below
# deliberately carry no additional prefix. An earlier version of this file
# added a second, redundant prefix at every mount point (e.g. income_engine's
# revenue router ended up at /api/v1/revenue/revenue/streams instead of
# /api/v1/revenue/streams, and auth/users had the same bug) - fixed here.
# (module path, import path, attribute name, mount kwargs, subsystem label)
_SUBSYSTEM_ROUTERS = [
    ("baselayer.core_loop.api.workflows", "router", {"tags": ["Core Loop"]}, "core-loop"),
    ("baselayer.core_loop.api.executions", "router", {"tags": ["Workflow Executions"]}, "core-loop"),
    ("baselayer.core_loop.api.monitoring", "router", {"tags": ["Workflow Monitoring"]}, "core-loop"),
    ("baselayer.income_engine.api.revenue", "router", {"tags": ["Income Engine"]}, "income-engine"),
    ("baselayer.income_engine.api.billing", "router", {"tags": ["Income Engine"]}, "income-engine"),
    ("baselayer.income_engine.api.subscriptions", "router", {"tags": ["Income Engine"]}, "income-engine"),
    ("baselayer.income_engine.api.providers", "router", {"tags": ["Income Engine"]}, "income-engine"),
    ("baselayer.income_engine.api.analytics", "router", {"tags": ["Income Engine"]}, "income-engine"),
    ("baselayer.codex.api.knowledge", "router", {"tags": ["Codex/Memory"]}, "codex"),
    ("baselayer.agents.api.agents", "router", {"tags": ["Multi-Agent"]}, "agents"),
    ("baselayer.governance.api.policies", "router", {"tags": ["Governance"]}, "governance"),
    ("baselayer.output_engine.api.templates", "router", {"tags": ["Output Engine"]}, "output-engine"),
]

_loaded_subsystems: set[str] = set()
_failed_subsystems: dict[str, str] = {}

for module_path, attr_name, mount_kwargs, subsystem in _SUBSYSTEM_ROUTERS:
    try:
        import importlib
        module = importlib.import_module(module_path)
        router = getattr(module, attr_name)
        api_v1_router.include_router(router, **mount_kwargs)
        _loaded_subsystems.add(subsystem)
    except Exception as e:
        _failed_subsystems[module_path] = str(e)
        logger.error(
            "Subsystem router failed to load, skipping (other subsystems still mount)",
            module=module_path,
            subsystem=subsystem,
            error=str(e),
        )


@api_v1_router.get("/")
async def api_v1_root() -> dict:
    """API v1 root endpoint."""
    return {
        "name": "BaseLayer API v1",
        "version": "1.0.0",
        "description": "Version 1 of the BaseLayer REST API",
        "subsystems": sorted(_loaded_subsystems),
    }


@api_v1_router.get("/status")
async def api_status() -> dict:
    """
    API status endpoint.

    Reports which subsystems actually loaded, not an aspirational list -
    a subsystem only appears "operational" here if its router genuinely
    mounted this run.
    """
    all_subsystems = {subsystem for *_, subsystem in _SUBSYSTEM_ROUTERS}
    return {
        "status": "operational" if not _failed_subsystems else "degraded",
        "subsystems": {
            subsystem: "operational" if subsystem in _loaded_subsystems else "failed_to_load"
            for subsystem in sorted(all_subsystems)
        },
        "load_errors": _failed_subsystems,
        "governance": {
            "mode": "strict",
            "compliance": "SYS-CRP",
            "maturity": "prototype",
        },
    }
