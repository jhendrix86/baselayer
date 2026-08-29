"""
BaseLayer Compliance Monitor

Compliance monitoring and reporting system
for the Governance/Doctrine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.governance import (
    GovernanceRule, ComplianceReport,
    RuleType, ComplianceStatus
)
from ..models.user import User
from .exceptions import (
    ComplianceError,
    ValidationError
)

logger = get_logger(__name__)


class ComplianceMonitor:
    """
    Compliance monitoring and reporting system.
    
    Monitors compliance across all subsystems, generates reports,
    and tracks compliance metrics with real-time alerts.
    """
    
    def __init__(self):
        self.monitoring_active: bool = False
        self.compliance_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 1800  # 30 minutes
        self.monitoring_interval: int = 3600  # 1 hour
        self.alert_thresholds = {
            "compliance_rate": 80.0,  # Below this triggers alerts
            "violation_count": 10,  # Above this triggers alerts
            "critical_violations": 3  # Any critical violations trigger alerts
        }
        
        # Compliance configuration
        self.compliance_categories = {
            "data_protection": {
                "description": "Data protection and privacy compliance",
                "regulations": ["GDPR", "CCPA", "HIPAA"],
                "check_frequency": "daily",
                "severity_weights": {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
            },
            "access_control": {
                "description": "Access control and authorization compliance",
                "regulations": ["SOX", "PCI-DSS", "ISO27001"],
                "check_frequency": "hourly",
                "severity_weights": {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
            },
            "operational": {
                "description": "Operational and procedural compliance",
                "regulations": ["ISO9001", "SOC2", "ITIL"],
                "check_frequency": "daily",
                "severity_weights": {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
            },
            "security": {
                "description": "Security and vulnerability compliance",
                "regulations": ["NIST", "CIS", "OWASP"],
                "check_frequency": "continuous",
                "severity_weights": {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
            },
            "financial": {
                "description": "Financial and accounting compliance",
                "regulations": ["SOX", "GAAP", "IFRS"],
                "check_frequency": "daily",
                "severity_weights": {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
            }
        }
        
        # Compliance metrics
        self.compliance_metrics = {
            "total_checks": 0,
            "compliant_checks": 0,
            "violations_detected": 0,
            "reports_generated": 0,
            "alerts_triggered": 0,
            "average_compliance_rate": 0.0
        }
    
    async def start(self) -> None:
        """Start the compliance monitor."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        asyncio.create_task(self._monitoring_loop())
        
        logger.info("Compliance monitor started")
    
    async def stop(self) -> None:
        """Stop the compliance monitor."""
        self.monitoring_active = False
        logger.info("Compliance monitor stopped")
    
    async def check_rule_compliance(
        self,
        rule: GovernanceRule,
        entity_type: str,
        entity_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check compliance for a specific rule.
        
        Args:
            rule: Governance rule to check
            entity_type: Type of entity
            entity_id: Entity ID
            context: Additional context
            
        Returns:
            Dict[str, Any]: Compliance check result
        """
        try:
            # Prepare check context
            check_context = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "rule_id": str(rule.id),
                **(context or {})
            }
            
            # Evaluate rule conditions
            conditions_met = await self._evaluate_rule_conditions(rule, check_context)
            
            # Determine compliance status
            compliant = conditions_met
            
            # Calculate compliance score
            compliance_score = 100.0 if compliant else 0.0
            
            # Identify violations
            violations = []
            if not compliant:
                violations.append({
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "severity": rule.metadata.get("severity", "medium"),
                    "description": f"Rule violation: {rule.name}",
                    "remediation": rule.metadata.get("remediation", "Contact administrator"),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            result = {
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "compliant": compliant,
                "compliance_score": compliance_score,
                "violations": violations,
                "check_timestamp": datetime.utcnow().isoformat()
            }
            
            # Update metrics
            self.compliance_metrics["total_checks"] += 1
            if compliant:
                self.compliance_metrics["compliant_checks"] += 1
            else:
                self.compliance_metrics["violations_detected"] += len(violations)
            
            return result
            
        except Exception as e:
            raise ComplianceError(f"Failed to check rule compliance: {str(e)}") from e
    
    async def run_compliance_scan(
        self,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        deep_scan: bool = False
    ) -> Dict[str, Any]:
        """
        Run a comprehensive compliance scan.
        
        Args:
            entity_type: Type of entities to scan
            entity_ids: Specific entity IDs to scan
            category: Compliance category to focus on
            deep_scan: Whether to perform deep scan
            
        Returns:
            Dict[str, Any]: Scan results
        """
        try:
            start_time = datetime.utcnow()
            
            # Get applicable rules
            applicable_rules = await self._get_applicable_rules(entity_type, category)
            
            # Get entities to scan
            entities = await self._get_entities_to_scan(entity_type, entity_ids)
            
            # Run compliance checks
            scan_results = []
            total_violations = []
            
            for entity in entities:
                entity_results = []
                
                for rule in applicable_rules:
                    try:
                        result = await self.check_rule_compliance(
                            rule, entity["type"], entity["id"], entity.get("context")
                        )
                        entity_results.append(result)
                        
                        # Collect violations
                        total_violations.extend(result.get("violations", []))
                        
                    except Exception as e:
                        logger.error(
                            "Compliance check failed",
                            rule_id=str(rule.id),
                            entity_id=entity["id"],
                            error=str(e)
                        )
                
                # Calculate entity compliance
                entity_compliance = self._calculate_entity_compliance(entity_results)
                
                scan_results.append({
                    "entity_type": entity["type"],
                    "entity_id": entity["id"],
                    "compliance_score": entity_compliance["score"],
                    "compliance_status": entity_compliance["status"],
                    "violations_count": len(entity_compliance["violations"]),
                    "violations": entity_compliance["violations"],
                    "checks_performed": len(entity_results)
                })
            
            # Calculate overall compliance
            overall_compliance = self._calculate_overall_compliance(scan_results)
            
            # Check for alerts
            alerts = await self._check_compliance_alerts(overall_compliance, total_violations)
            
            scan_duration = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "scan_id": str(uuid.uuid4()),
                "scan_timestamp": start_time.isoformat(),
                "scan_duration": scan_duration,
                "entity_type": entity_type,
                "category": category,
                "deep_scan": deep_scan,
                "entities_scanned": len(entities),
                "rules_checked": len(applicable_rules),
                "overall_compliance": overall_compliance,
                "total_violations": len(total_violations),
                "violations_by_severity": self._group_violations_by_severity(total_violations),
                "alerts": alerts,
                "scan_results": scan_results
            }
            
            # Update metrics
            self.compliance_metrics["reports_generated"] += 1
            if alerts:
                self.compliance_metrics["alerts_triggered"] += len(alerts)
            
            logger.info(
                "Compliance scan completed",
                scan_id=result["scan_id"],
                entities_scanned=len(entities),
                overall_compliance=overall_compliance["score"]
            )
            
            return result
            
        except Exception as e:
            raise ComplianceError(f"Failed to run compliance scan: {str(e)}") from e
    
    async def generate_report_data(
        self,
        report_type: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate data for compliance reports.
        
        Args:
            report_type: Type of report
            period_start: Start of period
            period_end: End of period
            entity_type: Filter by entity type
            entity_ids: Filter by entity IDs
            
        Returns:
            Dict[str, Any]: Report data
        """
        try:
            # Set default period
            if not period_start:
                period_start = datetime.utcnow() - timedelta(days=30)
            if not period_end:
                period_end = datetime.utcnow()
            
            # Get compliance data
            compliance_data = await self._get_compliance_data(
                period_start, period_end, entity_type, entity_ids
            )
            
            # Generate report based on type
            if report_type == "summary":
                report_data = await self._generate_summary_report(compliance_data, period_start, period_end)
            elif report_type == "detailed":
                report_data = await self._generate_detailed_report(compliance_data, period_start, period_end)
            elif report_type == "trend":
                report_data = await self._generate_trend_report(compliance_data, period_start, period_end)
            elif report_type == "violation":
                report_data = await self._generate_violation_report(compliance_data, period_start, period_end)
            else:
                raise ComplianceError(f"Unknown report type: {report_type}")
            
            return report_data
            
        except Exception as e:
            raise ComplianceError(f"Failed to generate report data: {str(e)}") from e
    
    async def get_compliance_dashboard(
        self,
        time_range: str = "7d"
    ) -> Dict[str, Any]:
        """
        Get compliance dashboard data.
        
        Args:
            time_range: Time range for data (1d, 7d, 30d, 90d)
            
        Returns:
            Dict[str, Any]: Dashboard data
        """
        try:
            # Calculate period based on time range
            time_ranges = {
                "1d": timedelta(days=1),
                "7d": timedelta(days=7),
                "30d": timedelta(days=30),
                "90d": timedelta(days=90)
            }
            
            period_delta = time_ranges.get(time_range, timedelta(days=7))
            period_start = datetime.utcnow() - period_delta
            period_end = datetime.utcnow()
            
            # Get compliance metrics
            compliance_metrics = await self._get_compliance_metrics(period_start, period_end)
            
            # Get recent violations
            recent_violations = await self._get_recent_violations(period_start, period_end)
            
            # Get compliance trends
            compliance_trends = await self._get_compliance_trends(period_start, period_end)
            
            # Get category breakdown
            category_breakdown = await self._get_category_breakdown(period_start, period_end)
            
            dashboard_data = {
                "time_range": time_range,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "overall_metrics": compliance_metrics,
                "recent_violations": recent_violations[:10],  # Top 10
                "compliance_trends": compliance_trends,
                "category_breakdown": category_breakdown,
                "alert_status": await self._get_alert_status(),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return dashboard_data
            
        except Exception as e:
            raise ComplianceError(f"Failed to get compliance dashboard: {str(e)}") from e
    
    async def _monitoring_loop(self) -> None:
        """Main compliance monitoring loop."""
        while self.monitoring_active:
            try:
                # Run scheduled compliance checks
                await self._run_scheduled_checks()
                
                # Update compliance metrics
                await self._update_compliance_metrics()
                
                # Clean up old cache entries
                await self._cleanup_cache()
                
                # Sleep before next iteration
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(
                    "Compliance monitoring loop error",
                    error=str(e)
                )
                await asyncio.sleep(300)  # 5 minutes on error
    
    async def _run_scheduled_checks(self) -> None:
        """Run scheduled compliance checks."""
        try:
            for category, config in self.compliance_categories.items():
                check_frequency = config.get("check_frequency", "daily")
                
                # Determine if check should run now
                should_run = await self._should_run_check(category, check_frequency)
                
                if should_run:
                    logger.info(
                        "Running scheduled compliance check",
                        category=category,
                        frequency=check_frequency
                    )
                    
                    # Run compliance scan for category
                    await self.run_compliance_scan(category=category)
                    
        except Exception as e:
            logger.error(
                "Failed to run scheduled checks",
                error=str(e)
            )
    
    async def _should_run_check(self, category: str, frequency: str) -> bool:
        """Determine if a compliance check should run."""
        # In real implementation, would check last run time from database
        # For now, return True for demonstration
        return True
    
    async def _evaluate_rule_conditions(self, rule: GovernanceRule, context: Dict[str, Any]) -> bool:
        """Evaluate rule conditions for compliance."""
        try:
            conditions = rule.conditions
            
            # Simple condition evaluation
            for condition_key, condition_value in conditions.items():
                if condition_key not in context:
                    return False
                
                context_value = context[condition_key]
                
                if isinstance(condition_value, dict):
                    operator = condition_value.get("operator", "equals")
                    value = condition_value.get("value")
                    
                    if operator == "equals":
                        if context_value != value:
                            return False
                    elif operator == "not_equals":
                        if context_value == value:
                            return False
                    elif operator == "in":
                        if context_value not in value:
                            return False
                    elif operator == "greater_than":
                        if not context_value > value:
                            return False
                    elif operator == "less_than":
                        if not context_value < value:
                            return False
                else:
                    if context_value != condition_value:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Rule condition evaluation failed",
                rule_id=str(rule.id),
                error=str(e)
            )
            return False
    
    async def _get_applicable_rules(
        self,
        entity_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[GovernanceRule]:
        """Get applicable compliance rules."""
        try:
            async with db_session_context() as session:
                query = select(GovernanceRule).where(
                    GovernanceRule.enabled == True,
                    GovernanceRule.deleted_at.is_(None)
                )
                
                if entity_type:
                    query = query.where(
                        GovernanceRule.conditions["applies_to"].astext.contains([entity_type])
                    )
                
                result = await session.execute(query)
                rules = result.scalars().all()
                
                # Filter by category if specified
                if category:
                    rules = [r for r in rules if r.conditions.get("category") == category]
                
                return list(rules)
                
        except Exception as e:
            logger.error(
                "Failed to get applicable rules",
                error=str(e)
            )
            return []
    
    async def _get_entities_to_scan(
        self,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get entities to include in compliance scan."""
        # In real implementation, would query actual entities from database
        # For now, return mock entities
        entities = []
        
        if entity_ids:
            for entity_id in entity_ids:
                entities.append({
                    "type": entity_type or "unknown",
                    "id": entity_id,
                    "context": {}
                })
        else:
            # Generate mock entities for demonstration
            for i in range(10):
                entities.append({
                    "type": entity_type or "user",
                    "id": f"entity_{i}",
                    "context": {"active": True, "role": "user"}
                })
        
        return entities
    
    def _calculate_entity_compliance(self, entity_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate compliance for an entity."""
        if not entity_results:
            return {"score": 100.0, "status": "compliant", "violations": []}
        
        total_score = sum(r["compliance_score"] for r in entity_results)
        average_score = total_score / len(entity_results)
        
        all_violations = []
        for result in entity_results:
            all_violations.extend(result.get("violations", []))
        
        # Determine status
        if average_score >= 100:
            status = "compliant"
        elif average_score >= 80:
            status = "partially_compliant"
        else:
            status = "non_compliant"
        
        return {
            "score": average_score,
            "status": status,
            "violations": all_violations
        }
    
    def _calculate_overall_compliance(self, scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall compliance across all entities."""
        if not scan_results:
            return {"score": 100.0, "status": "compliant", "entities_compliant": 0}
        
        total_score = sum(r["compliance_score"] for r in scan_results)
        average_score = total_score / len(scan_results)
        
        entities_compliant = len([r for r in scan_results if r["compliance_score"] >= 100])
        
        # Determine status
        if average_score >= 100:
            status = "compliant"
        elif average_score >= 80:
            status = "partially_compliant"
        else:
            status = "non_compliant"
        
        return {
            "score": average_score,
            "status": status,
            "entities_compliant": entities_compliant,
            "total_entities": len(scan_results)
        }
    
    def _group_violations_by_severity(self, violations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group violations by severity."""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        
        for violation in violations:
            severity = violation.get("severity", "medium")
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        return severity_counts
    
    async def _check_compliance_alerts(
        self,
        overall_compliance: Dict[str, Any],
        violations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for compliance alerts."""
        alerts = []
        
        # Check compliance rate threshold
        if overall_compliance["score"] < self.alert_thresholds["compliance_rate"]:
            alerts.append({
                "type": "compliance_rate_low",
                "severity": "high",
                "message": f"Compliance rate ({overall_compliance['score']:.1f}%) below threshold ({self.alert_thresholds['compliance_rate']}%)",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Check violation count threshold
        if len(violations) > self.alert_thresholds["violation_count"]:
            alerts.append({
                "type": "violation_count_high",
                "severity": "medium",
                "message": f"Violation count ({len(violations)}) above threshold ({self.alert_thresholds['violation_count']})",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Check critical violations
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        if len(critical_violations) >= self.alert_thresholds["critical_violations"]:
            alerts.append({
                "type": "critical_violations",
                "severity": "critical",
                "message": f"Critical violations detected ({len(critical_violations)})",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return alerts
    
    async def _get_compliance_data(
        self,
        period_start: datetime,
        period_end: datetime,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get compliance data for a period."""
        # In real implementation, would query actual compliance data
        # For now, return mock data
        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "entity_type": entity_type,
            "entity_ids": entity_ids or [],
            "compliance_checks": [],
            "violations": [],
            "reports": []
        }
    
    async def _generate_summary_report(self, data: Dict[str, Any], period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate summary compliance report."""
        return {
            "report_type": "summary",
            "period": data["period"],
            "overall_compliance": 95.5,
            "total_checks": 1000,
            "compliant_checks": 955,
            "violations": 45,
            "trends": "improving",
            "key_findings": [
                "Overall compliance improved by 2.3%",
                "Critical violations reduced by 15%",
                "Data protection compliance at 98%"
            ]
        }
    
    async def _generate_detailed_report(self, data: Dict[str, Any], period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate detailed compliance report."""
        return {
            "report_type": "detailed",
            "period": data["period"],
            "sections": [
                {"title": "Executive Summary", "content": "Detailed executive summary..."},
                {"title": "Compliance Overview", "content": "Compliance overview..."},
                {"title": "Violation Analysis", "content": "Violation analysis..."},
                {"title": "Remediation Status", "content": "Remediation status..."}
            ]
        }
    
    async def _generate_trend_report(self, data: Dict[str, Any], period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate trend compliance report."""
        return {
            "report_type": "trend",
            "period": data["period"],
            "trends": {
                "compliance_rate": [90, 92, 91, 93, 95, 94, 95.5],
                "violation_count": [60, 55, 58, 52, 48, 50, 45],
                "categories": {
                    "data_protection": "stable",
                    "access_control": "improving",
                    "security": "declining"
                }
            }
        }
    
    async def _generate_violation_report(self, data: Dict[str, Any], period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate violation-focused compliance report."""
        return {
            "report_type": "violation",
            "period": data["period"],
            "violations": [
                {
                    "id": "v1",
                    "severity": "high",
                    "category": "data_protection",
                    "description": "Unauthorized data access",
                    "status": "open",
                    "remediation": "Review access controls"
                }
            ],
            "violation_trends": "decreasing",
            "remediation_status": "75% resolved"
        }
    
    async def _get_compliance_metrics(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get compliance metrics for a period."""
        # In real implementation, would calculate from actual data
        return {
            "overall_compliance_rate": 95.5,
            "total_checks": 1000,
            "compliant_checks": 955,
            "violation_count": 45,
            "critical_violations": 2,
            "high_violations": 8,
            "medium_violations": 20,
            "low_violations": 15
        }
    
    async def _get_recent_violations(self, period_start: datetime, period_end: datetime) -> List[Dict[str, Any]]:
        """Get recent violations."""
        # In real implementation, would query from database
        return [
            {
                "id": "v1",
                "severity": "high",
                "category": "access_control",
                "description": "Unauthorized access attempt",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "open"
            }
        ]
    
    async def _get_compliance_trends(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get compliance trends."""
        return {
            "daily_compliance": [92, 93, 91, 94, 95, 94, 95.5],
            "violation_trends": "decreasing",
            "improvement_areas": ["access_control", "data_protection"]
        }
    
    async def _get_category_breakdown(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get compliance breakdown by category."""
        return {
            "data_protection": {"compliance_rate": 98.0, "violations": 5},
            "access_control": {"compliance_rate": 94.0, "violations": 15},
            "operational": {"compliance_rate": 96.0, "violations": 10},
            "security": {"compliance_rate": 93.0, "violations": 12},
            "financial": {"compliance_rate": 97.0, "violations": 3}
        }
    
    async def _get_alert_status(self) -> Dict[str, Any]:
        """Get current alert status."""
        return {
            "active_alerts": 2,
            "critical_alerts": 0,
            "high_alerts": 1,
            "medium_alerts": 1,
            "last_alert": datetime.utcnow().isoformat()
        }
    
    async def _update_compliance_metrics(self) -> None:
        """Update compliance metrics from database."""
        # In real implementation, would calculate from database
        pass
    
    async def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.utcnow()
        
        for key, (timestamp, _) in list(self.compliance_cache.items()):
            if current_time - timestamp > timedelta(seconds=self.cache_ttl):
                del self.compliance_cache[key]
    
    def get_compliance_monitor_stats(self) -> Dict[str, Any]:
        """Get compliance monitor statistics."""
        return {
            "monitoring_active": self.monitoring_active,
            "monitoring_interval": self.monitoring_interval,
            "cache_size": len(self.compliance_cache),
            "cache_ttl": self.cache_ttl,
            "alert_thresholds": self.alert_thresholds,
            "compliance_categories": list(self.compliance_categories.keys()),
            "compliance_metrics": self.compliance_metrics
        }
