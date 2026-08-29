"""
BaseLayer Governance/Doctrine API

REST API endpoints for policy management, compliance monitoring, and audit trails.

Only `policies` is implemented as an HTTP router today - it's also the only
governance router `api/v1/router.py` mounts. The compliance / audit / risk /
automation / dashboard capabilities exist at the engine layer
(governance/compliance_monitor.py, audit_trail.py, risk_assessor.py,
rule_automator.py, dashboard.py) but have no REST router module yet. This
`__init__` previously imported all five unconditionally, which made
`import baselayer.governance.api.policies` fail outright and took the whole
governance subsystem offline. Add each back here (and to api/v1/router.py's
_SUBSYSTEM_ROUTERS) as its router module is written.
"""

from .policies import router as policies_router

__all__ = [
    "policies_router",
]
