"""
BaseLayer API v1 Router

Main router for API v1 endpoints.

Subsystem routers are imported defensively: a broken subsystem is logged
and skipped rather than blocking every other subsystem, including the ones
that work. As of 2026-08-29 all six mounted subsystems load cleanly - the
try/except is kept as a guard for future breakage, not because anything
is currently failing.

History (see `OS42_REPAIR_PLAN.md` / `HANDOFF.md`): codex, agents,
governance and output_engine were each offline for a distinct
import-time reason, all fixed 2026-08-29 -
  * codex: `EntryType` enum + `KnowledgeEntry.entry_type` column added to
    models/codex.py; a missing `AsyncSession` import in codex/extractor.py.
  * agents: `AgentMessage` model added to models/agents.py.
  * output_engine: `TemplateType` / `OutputStatus` enums added to
    models/output_engine.py.
  * codex/agents/governance/output_engine api/__init__.py each imported
    4-5 router submodules that don't exist on disk (only knowledge /
    agents / policies / templates respectively do); trimmed to what
    exists. Add the rest back here and in _SUBSYSTEM_ROUTERS as their
    router modules get written.

Still outstanding (runtime, not load-time): the codex / output_engine
engine layers were written against an older model shape (e.g.
`create_template(content=, engine=, status=, template_type=)` vs. the
model's `template_content` / `output_type` / no such columns), and their
internal `async with get_db_session()` calls use the FastAPI-dependency
generator as a context manager. Those paths will 500 until reconciled -
tracked in OS42_REPAIR_PLAN.md.
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
