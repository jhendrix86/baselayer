"""
BaseLayer FastAPI Application Entry Point

This is the main entry point for the BaseLayer backend API.
It initializes the FastAPI application, middleware, and includes all routers.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from baselayer.core.config import get_settings
from baselayer.core.database import create_tables, close_database
from baselayer.core.logging import setup_logging
from baselayer.core.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    TenantMiddleware,
)
from baselayer.api.v1.router import api_v1_router
from baselayer.api.health import health_router
from baselayer.api.metrics import metrics_router
from baselayer.income_engine.engine import RevenueEngine
from baselayer.income_engine.billing import BillingEngine
from baselayer.income_engine.subscriptions import SubscriptionManager
from baselayer.income_engine.providers import PaymentProviderManager
from baselayer.income_engine.api import revenue as income_engine_revenue
from baselayer.income_engine.api import billing as income_engine_billing
from baselayer.income_engine.api import subscriptions as income_engine_subscriptions
from baselayer.income_engine.api import providers as income_engine_providers
from baselayer.core_loop.engine import WorkflowEngine
from baselayer.core_loop.scheduler import WorkflowScheduler
from baselayer.core_loop.monitor import WorkflowMonitor
from baselayer.core_loop.api import workflows as core_loop_workflows
from baselayer.core_loop.api import executions as core_loop_executions
from baselayer.core_loop.api import monitoring as core_loop_monitoring
from baselayer.codex.engine import KnowledgeEngine
from baselayer.codex.extractor import KnowledgeExtractor
from baselayer.codex.analyzer import KnowledgeAnalyzer
from baselayer.codex.api import knowledge as codex_knowledge
from baselayer.agents.orchestrator import AgentOrchestrator
from baselayer.agents.lifecycle import AgentLifecycleManager
from baselayer.agents.api import agents as agents_api
from baselayer.governance.engine import GovernanceEngine
from baselayer.governance.api import policies as governance_policies
from baselayer.output_engine.engine import OutputEngine
from baselayer.output_engine.api import templates as output_engine_templates

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)

# Get application settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting BaseLayer API server", version="0.1.0")
    
    # Initialize database tables
    await create_tables()
    logger.info("Database tables initialized")

    # Initialize the income engine subsystem. Without this, every
    # income_engine/api/*.py endpoint's get_x_engine() dependency raises
    # 500 "not initialized" - the module-level globals it reads were never
    # set anywhere before this.
    revenue_engine = RevenueEngine()
    income_engine_revenue.revenue_engine = revenue_engine
    income_engine_billing.billing_engine = BillingEngine(revenue_engine)
    income_engine_subscriptions.subscription_manager = SubscriptionManager(revenue_engine)
    income_engine_providers.provider_manager = PaymentProviderManager()
    logger.info("Income engine initialized")

    # Initialize the core_loop subsystem. Same bug shape as income_engine
    # above, just never fixed for this subsystem: workflows.py/executions.py/
    # monitoring.py each declare their own module-level workflow_engine/
    # workflow_scheduler/workflow_monitor globals (three independent globals,
    # not shared state) and get_workflow_engine()/get_workflow_scheduler()/
    # get_workflow_monitor() unconditionally raise 500 "not initialized" if
    # nothing ever sets them - nothing did, anywhere, so every core-loop
    # endpoint that needs the engine/scheduler/monitor was unreachable.
    # core_loop/tasks.py's initialize_core_loop() looks like it was meant to
    # do this, but it's never imported/called from anywhere (dead code) and
    # it also `await`s start_execution_worker() directly, which would hang
    # startup forever since that method is an infinite `while True` loop -
    # not used here for that reason. WorkflowScheduler.start() and
    # WorkflowMonitor.start() already background their own loops via
    # asyncio.create_task(); the execution worker is backgrounded the same
    # way for consistency.
    workflow_engine = WorkflowEngine()
    await workflow_engine.connect()
    workflow_scheduler = WorkflowScheduler(workflow_engine)
    await workflow_scheduler.start()
    workflow_monitor = WorkflowMonitor(workflow_engine)
    await workflow_monitor.start()
    execution_worker_task = asyncio.create_task(workflow_engine.start_execution_worker())

    core_loop_workflows.workflow_engine = workflow_engine
    core_loop_workflows.workflow_scheduler = workflow_scheduler
    core_loop_executions.workflow_engine = workflow_engine
    core_loop_executions.workflow_monitor = workflow_monitor
    core_loop_monitoring.workflow_monitor = workflow_monitor
    core_loop_monitoring.workflow_scheduler = workflow_scheduler
    logger.info("Core loop initialized")

    # Initialize codex / agents / governance / output_engine subsystems.
    # Same bug shape as income_engine and core_loop above: each api/*.py
    # module has a module-level engine/manager global that starts as None,
    # and its get_x_engine() dependency raises 500 "not initialized" until
    # something assigns it. Nothing did until now, so every endpoint in
    # these four subsystems 500'd unconditionally even though the routers
    # mounted fine. All seven engine classes take no constructor args.
    # AgentLifecycleManager.start() (spawns a 30s health-check loop) is
    # deliberately NOT called here - the CRUD endpoints don't need the
    # loop, and its schema reconciliation with the models is still
    # outstanding (see api/v1/router.py's docstring / OS42_REPAIR_PLAN.md).
    # Each is wrapped independently: these subsystems' engine layers are
    # only partially reconciled with their models (see api/v1/router.py's
    # docstring), so a constructor may still raise on a stale reference.
    # One failing here must not take down auth / income_engine / core_loop.
    for _label, _init in (
        ("codex", lambda: (
            setattr(codex_knowledge, "knowledge_engine", KnowledgeEngine()),
            setattr(codex_knowledge, "knowledge_extractor", KnowledgeExtractor()),
            setattr(codex_knowledge, "knowledge_analyzer", KnowledgeAnalyzer()),
        )),
        ("agents", lambda: (
            setattr(agents_api, "agent_orchestrator", AgentOrchestrator()),
            setattr(agents_api, "lifecycle_manager", AgentLifecycleManager()),
        )),
        ("governance", lambda: setattr(governance_policies, "governance_engine", GovernanceEngine())),
        ("output_engine", lambda: setattr(output_engine_templates, "output_engine", OutputEngine())),
    ):
        try:
            _init()
            logger.info(f"{_label} subsystem initialized")
        except Exception as exc:  # noqa: BLE001 - deliberate: keep the API up
            logger.error(f"{_label} subsystem init failed - its endpoints will 500", error=str(exc))

    # Initialize Redis connection
    # This will be implemented in Phase 4

    yield

    # Shutdown
    logger.info("Shutting down BaseLayer API server")
    execution_worker_task.cancel()
    try:
        await execution_worker_task
    except asyncio.CancelledError:
        pass
    await workflow_monitor.stop()
    await workflow_scheduler.stop()
    await workflow_engine.disconnect()
    await close_database()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="BaseLayer API",
    description="A modular, governance-grade operational system",
    version="0.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
    lifespan=lifespan,
)

# Add middleware in the correct order
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
app.include_router(api_v1_router, prefix="/api/v1", tags=["API v1"])


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.
    
    Returns basic information about the API.
    """
    return {
        "name": "BaseLayer API",
        "version": "0.1.0",
        "description": "A modular, governance-grade operational system",
        "docs": "/docs" if settings.environment == "development" else "Documentation disabled",
    }


@app.get("/prometheus")
async def prometheus_metrics() -> str:
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for Netdata integration.
    """
    return generate_latest()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "baselayer.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level="info",
    )
