"""
BaseLayer Multi-Agent Orchestration API

REST API endpoints for agent management, coordination, and monitoring.

Only `agents` is implemented as an HTTP router today - it's also the only
agents router `api/v1/router.py` mounts. Task / orchestration / monitoring /
scaling logic exists at the engine layer (agents/orchestrator.py, tasks.py,
monitor.py, scaler.py) but has no REST router module yet. This `__init__`
previously imported all five unconditionally, which made
`import baselayer.agents.api.agents` fail outright and took the whole agents
subsystem offline. Add each back here (and to api/v1/router.py's
_SUBSYSTEM_ROUTERS) as its router module is written.
"""

from .agents import router as agents_router

__all__ = [
    "agents_router",
]
