"""
BaseLayer Output Engine API

REST API endpoints for template management, output generation, and delivery.

Only `templates` is implemented as an HTTP router today - it's also the only
output-engine router `api/v1/router.py` mounts. Output generation, delivery
and analytics exist at the engine layer (output_engine/engine.py,
generator.py, tracker.py) but have no REST router module yet. This `__init__`
previously imported all four unconditionally, which made
`import baselayer.output_engine.api.templates` fail outright and took the
whole output-engine subsystem offline. Add each back here (and to
api/v1/router.py's _SUBSYSTEM_ROUTERS) as its router module is written.
"""

from .templates import router as templates_router

__all__ = [
    "templates_router",
]
