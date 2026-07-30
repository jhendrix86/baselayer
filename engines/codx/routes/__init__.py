"""
CODX API Routes

FastAPI routes for CODX knowledge engine.
"""

from .knowledge import knowledge_router

__all__ = ["knowledge_router"]
