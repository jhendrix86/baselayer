"""
BaseLayer Codex/Memory API

REST API endpoints for knowledge management, search, and analysis.

Only `knowledge` is implemented as an HTTP router today - it's also the only
codex router `api/v1/router.py` mounts. Search / categories / tags /
analytics exist at the engine layer (codex/search.py, engine.py, analyzer.py,
indexer.py) but have no REST router module yet. This `__init__` previously
imported all five unconditionally, which made
`import baselayer.codex.api.knowledge` fail outright and took the whole codex
subsystem offline. Add each back here (and to api/v1/router.py's
_SUBSYSTEM_ROUTERS) as its router module is written.
"""

from .knowledge import router as knowledge_router

__all__ = [
    "knowledge_router",
]
