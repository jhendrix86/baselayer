"""
BaseLayer Governance/Doctrine Tasks

Arq task definitions for background governance processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from arq import cron
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.governance import (
    GovernanceRule, AuditLog, ComplianceReport,
    RuleType, RuleStatus, ComplianceStatus
)
from .engine import GovernanceEngine
from .policy_manager import PolicyManager
from .compliance_monitor import ComplianceMonitor
from .audit_trail import AuditTrail
from .risk_assessor import RiskAssessor
from .rule_automator import RuleAutomator
from .dashboard import ComplianceDashboard

logger = get_logger(__name__)

# Global instances (will be initialized in startup)
governance_engine: GovernanceEngine = None
policy_manager: PolicyManager = None
compliance_monitor: ComplianceMonitor = None
audit_trail: AuditTrail = None
risk_assessor: RiskAssessor = None
rule_automator: RuleAutomator = None
compliance_dashboard: ComplianceDashboard = None


async def initialize_governance_components():
    """Initialize Governance/Doctrine components."""
    global governance_engine, policy_manager, compliance_monitor
    global audit_trail, risk_assessor, rule_automator, compliance_dashboard
    
    governance_engine = GovernanceEngine()
    policy_manager = PolicyManager()
    compliance_monitor = ComplianceMonitor()
    audit_trail = AuditTrail()
    risk_assessor = RiskAssessor()
    rule_automator = RuleAutomator()
    compliance_dashboard = ComplianceDashboard()
    
    await governance_engine.start_governance()
    await policy_manager.start()
    await compliance_monitor.start()
    await audit_trail.start()
    await risk_assessor.start()
    await rule_automator.start()
    await compliance_dashboard.start()
    
    logger.info("Governance components initialized")


async def shutdown_governance_components():
    """Shutdown Governance/Doctrine components."""
    global governance_engine, policy_manager, compliance_monitor
    global audit_trail, risk_assessor, rule_automator, compliance_dashboard
    
    if governance_engine:
        await governance_engine.stop_governance()
    
    if policy_manager:
        await policy_manager.stop()
    
    if compliance_monitor:
        await compliance_monitor.stop()
    
    if audit_trail:
        await audit_trail.stop()
    
    if risk_assessor:
        await risk_assessor.stop()
    
    if rule_automator:
        await rule_automator.stop()
    
    if compliance_dashboard:
        await compliance_dashboard.stop()
    
    logger.info("Governance components shutdown")


async def process_policy_enforcement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process policy enforcement.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Enforcement results
    """
    global governance_engine
    
    if not governance_engine:
        raise RuntimeError("Governance engine not initialized")
    
    try:
        # Get policies to enforce
        async with db_session_context() as session:
            result = await session.execute(
                select(GovernanceRule).where(
                    GovernanceRule.enabled == True,
                    GovernanceRule.deleted_at.is_(None)
                ).order_by(GovernanceRule.priority.desc())
                .limit(20)
            )
            policies = result.scalars().all()
        
        enforced = 0
        failed = 0
        
        for policy in policies:
            try:
                # Create enforcement context
                context = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "system": "background_enforcement"
                }
                
                # Enforce policy
                result = await governance_engine.enforce_rule(
                    str(policy.id),
                    context
                )
                
                if result.get("enforced"):
                    enforced += 1
                else:
                    failed += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Policy enforcement failed",
                    policy_id=str(policy.id),
                    error=str(e)
                )
        
        logger.info(
            "Policy enforcement completed",
            total=len(policies),
            enforced=enforced,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_policies": len(policies),
            "enforced": enforced,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Policy enforcement task failed",
            error=str(e)
        )
        raise


async def run_compliance_scan(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to run compliance scans.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Scan results
    """
    global compliance_monitor
    
    if not compliance_monitor:
        raise RuntimeError("Compliance monitor not initialized")
    
    try:
        # Run comprehensive compliance scan
        scan_result = await compliance_monitor.run_compliance_scan(deep_scan=True)
        
        logger.info(
            "Compliance scan completed",
            scan_id=scan_result["scan_id"],
            entities_scanned=scan_result["entities_scanned"],
            overall_compliance=scan_result["overall_compliance"]["score"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "scan_result": scan_result
        }
        
    except Exception as e:
        logger.error(
            "Compliance scan task failed",
            error=str(e)
        )
        raise


async def process_audit_logs(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process audit logs.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Processing results
    """
    global audit_trail
    
    if not audit_trail:
        raise RuntimeError("Audit trail not initialized")
    
    try:
        # Process audit queue
        processed = 0
        failed = 0
        
        # In real implementation, would process audit queue
        # For now, simulate processing
        for i in range(50):  # Process 50 mock events
            try:
                await audit_trail.log_event(
                    event_type="background_check",
                    details={"check_id": i},
                    severity="info"
                )
                processed += 1
            except Exception as e:
                failed += 1
                logger.error(
                    "Audit log processing failed",
                    check_id=i,
                    error=str(e)
                )
        
        logger.info(
            "Audit log processing completed",
            processed=processed,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "processed": processed,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Audit log processing task failed",
            error=str(e)
        )
        raise


async def run_risk_assessment(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to run risk assessments.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Assessment results
    """
    global risk_assessor
    
    if not risk_assessor:
        raise RuntimeError("Risk assessor not initialized")
    
    try:
        # Run system risk assessment
        assessment_result = await risk_assessor.run_system_risk_assessment()
        
        logger.info(
            "Risk assessment completed",
            assessment_id=assessment_result["assessment_id"],
            total_risks=assessment_result["total_risks"],
            overall_score=assessment_result["overall_metrics"]["average_score"]
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "assessment_result": assessment_result
        }
        
    except Exception as e:
        logger.error(
            "Risk assessment task failed",
            error=str(e)
        )
        raise


async def generate_compliance_reports(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to generate compliance reports.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Report generation results
    """
    global compliance_monitor
    
    if not compliance_monitor:
        raise RuntimeError("Compliance monitor not initialized")
    
    try:
        # Generate different types of reports
        report_types = ["summary", "detailed", "trend", "violation"]
        generated_reports = []
        
        for report_type in report_types:
            try:
                # Generate report data
                report_data = await compliance_monitor.generate_report_data(
                    report_type=report_type
                )
                
                generated_reports.append({
                    "type": report_type,
                    "generated_at": datetime.utcnow().isoformat(),
                    "data_size": len(str(report_data))
                })
                
            except Exception as e:
                logger.error(
                    "Report generation failed",
                    report_type=report_type,
                    error=str(e)
                )
        
        logger.info(
            "Compliance reports generated",
            total_reports=len(generated_reports)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "generated_reports": generated_reports
        }
        
    except Exception as e:
        logger.error(
            "Compliance report generation task failed",
            error=str(e)
        )
        raise


async def update_governance_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to update governance metrics.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Metrics update results
    """
    try:
        # Get current metrics from all components
        metrics = {}
        
        global governance_engine, policy_manager, compliance_monitor
        global audit_trail, risk_assessor, rule_automator, compliance_dashboard
        
        if governance_engine:
            metrics["governance_engine"] = await governance_engine.get_governance_summary()
        
        if policy_manager:
            metrics["policy_manager"] = policy_manager.get_policy_manager_stats()
        
        if compliance_monitor:
            metrics["compliance_monitor"] = compliance_monitor.get_compliance_monitor_stats()
        
        if audit_trail:
            metrics["audit_trail"] = audit_trail.get_audit_trail_stats()
        
        if risk_assessor:
            metrics["risk_assessor"] = risk_assessor.get_risk_assessor_stats()
        
        if rule_automator:
            metrics["rule_automator"] = rule_automator.get_rule_automator_stats()
        
        if compliance_dashboard:
            metrics["compliance_dashboard"] = compliance_dashboard.get_dashboard_stats()
        
        logger.info(
            "Governance metrics updated",
            components_updated=len(metrics)
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(
            "Governance metrics update failed",
            error=str(e)
        )
        raise


async def cleanup_old_governance_data(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to clean up old governance data.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Cleanup results
    """
    try:
        cleanup_results = {}
        
        # Clean up old audit logs
        global audit_trail
        if audit_trail:
            audit_cleanup = await audit_trail.cleanup_old_audit_logs()
            cleanup_results["audit_logs"] = audit_cleanup
        
        # Clean up old compliance reports
        async with db_session_context() as session:
            # Delete compliance reports older than 1 year
            cutoff_date = datetime.utcnow() - timedelta(days=365)
            
            result = await session.execute(
                select(ComplianceReport).where(
                    ComplianceReport.created_at < cutoff_date,
                    ComplianceReport.deleted_at.is_(None)
                )
            )
            old_reports = result.scalars().all()
            
            deleted_reports = 0
            for report in old_reports:
                report.soft_delete()
                session.add(report)
                deleted_reports += 1
            
            await session.commit()
            
            cleanup_results["compliance_reports"] = {
                "deleted_count": deleted_reports,
                "cutoff_date": cutoff_date.isoformat()
            }
        
        logger.info(
            "Governance data cleanup completed",
            results=cleanup_results
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "cleanup_results": cleanup_results
        }
        
    except Exception as e:
        logger.error(
            "Governance data cleanup failed",
            error=str(e)
        )
        raise


async def check_governance_system_health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check governance system health.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Health check results
    """
    try:
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check governance engine
        global governance_engine
        if governance_engine and governance_engine.governance_active:
            health_status["checks"]["governance_engine"] = {
                "status": "healthy",
                "active": True,
                "cache_size": len(governance_engine.policy_cache)
            }
        else:
            health_status["checks"]["governance_engine"] = {
                "status": "error",
                "message": "Governance engine not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check policy manager
        global policy_manager
        if policy_manager and policy_manager.policy_active:
            health_status["checks"]["policy_manager"] = {
                "status": "healthy",
                "active": True,
                "cache_size": len(policy_manager.policy_cache)
            }
        else:
            health_status["checks"]["policy_manager"] = {
                "status": "error",
                "message": "Policy manager not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check compliance monitor
        global compliance_monitor
        if compliance_monitor and compliance_monitor.monitoring_active:
            health_status["checks"]["compliance_monitor"] = {
                "status": "healthy",
                "active": True,
                "cache_size": len(compliance_monitor.compliance_cache)
            }
        else:
            health_status["checks"]["compliance_monitor"] = {
                "status": "error",
                "message": "Compliance monitor not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check audit trail
        global audit_trail
        if audit_trail and audit_trail.audit_active:
            health_status["checks"]["audit_trail"] = {
                "status": "healthy",
                "active": True,
                "queue_size": audit_trail.audit_queue.qsize()
            }
        else:
            health_status["checks"]["audit_trail"] = {
                "status": "error",
                "message": "Audit trail not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check risk assessor
        global risk_assessor
        if risk_assessor and risk_assessor.assessment_active:
            health_status["checks"]["risk_assessor"] = {
                "status": "healthy",
                "active": True,
                "cache_size": len(risk_assessor.risk_cache)
            }
        else:
            health_status["checks"]["risk_assessor"] = {
                "status": "error",
                "message": "Risk assessor not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check rule automator
        global rule_automator
        if rule_automator and rule_automator.automation_active:
            health_status["checks"]["rule_automator"] = {
                "status": "healthy",
                "active": True,
                "queue_size": rule_automator.automation_queue.qsize()
            }
        else:
            health_status["checks"]["rule_automator"] = {
                "status": "error",
                "message": "Rule automator not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check compliance dashboard
        global compliance_dashboard
        if compliance_dashboard and compliance_dashboard.dashboard_active:
            health_status["checks"]["compliance_dashboard"] = {
                "status": "healthy",
                "active": True,
                "cache_size": len(compliance_dashboard.dashboard_cache)
            }
        else:
            health_status["checks"]["compliance_dashboard"] = {
                "status": "error",
                "message": "Compliance dashboard not active"
            }
            health_status["status"] = "unhealthy"
        
        # Check database connectivity
        try:
            async with db_session_context() as session:
                await session.execute("SELECT 1")
                health_status["checks"]["database"] = {
                    "status": "healthy"
                }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Determine overall status
        component_statuses = [
            check["status"] for check in health_status["checks"].values()
        ]
        
        if any(status == "unhealthy" for status in component_statuses):
            health_status["status"] = "unhealthy"
        elif any(status == "degraded" for status in component_statuses):
            health_status["status"] = "degraded"
        
        logger.info(
            "Governance system health check completed",
            status=health_status["status"]
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Governance system health check failed",
            error=str(e)
        )
        raise


async def process_automated_rules(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to process automated governance rules.
    
    Args:
        ctx: Arq context
        
    Returns:
        Dict[str, Any]: Rule processing results
    """
    global rule_automator
    
    if not rule_automator:
        raise RuntimeError("Rule automator not initialized")
    
    try:
        # Get automation rules to process
        automation_rules = await rule_automator.list_automation_rules(enabled=True)
        
        processed = 0
        triggered = 0
        failed = 0
        
        for rule in automation_rules:
            try:
                # Trigger automation rule
                result = await rule_automator.trigger_automation(
                    rule["rule_id"],
                    trigger_data={"scheduled_execution": True}
                )
                
                processed += 1
                
                if result.get("status") == "queued":
                    triggered += 1
                
            except Exception as e:
                failed += 1
                logger.error(
                    "Automation rule processing failed",
                    rule_id=rule["rule_id"],
                    error=str(e)
                )
        
        logger.info(
            "Automated rules processed",
            total=len(automation_rules),
            processed=processed,
            triggered=triggered,
            failed=failed
        )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "total_rules": len(automation_rules),
            "processed": processed,
            "triggered": triggered,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(
            "Automated rules processing task failed",
            error=str(e)
        )
        raise


# Arq job settings
WorkerSettings = {
    "burst": True,
    "max_jobs": 3,  # Optimized for i5-2400
    "queue_name": "governance",
    "job_timeout": 1800,  # 30 minutes timeout
}

# Cron jobs
cron_jobs = [
    cron(
        process_policy_enforcement,
        minute="*/15",  # Every 15 minutes
    ),
    cron(
        run_compliance_scan,
        hour=2,  # 2 AM daily
        minute=0,
    ),
    cron(
        process_audit_logs,
        minute="*/5",  # Every 5 minutes
    ),
    cron(
        run_risk_assessment,
        hour=3,  # 3 AM daily
        minute=0,
    ),
    cron(
        generate_compliance_reports,
        hour=4,  # 4 AM daily
        minute=0,
    ),
    cron(
        update_governance_metrics,
        minute="*/30",  # Every 30 minutes
    ),
    cron(
        cleanup_old_governance_data,
        hour=5,  # 5 AM daily
        minute=0,
    ),
    cron(
        process_automated_rules,
        minute="*/10",  # Every 10 minutes
    ),
    cron(
        check_governance_system_health,
        minute="*/20",  # Every 20 minutes
    ),
]
