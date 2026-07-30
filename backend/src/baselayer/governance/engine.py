"""
BaseLayer Governance Engine

Core governance management and policy enforcement system
for the Governance/Doctrine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.governance import (
    GovernanceRule, AuditLog, ComplianceReport,
    RuleType, RuleStatus, ComplianceStatus
)
from ..models.user import User
from .policy_manager import PolicyManager
from .compliance_monitor import ComplianceMonitor
from .audit_trail import AuditTrail
from .risk_assessor import RiskAssessor
from .rule_automator import RuleAutomator
from .dashboard import ComplianceDashboard
from .exceptions import (
    GovernanceError,
    PolicyError,
    ComplianceError,
    ValidationError
)

logger = get_logger(__name__)


class GovernanceEngine:
    """
    Core governance management and policy enforcement engine.
    
    Handles policy management, compliance monitoring, audit trails,
    risk assessment, and automated rule enforcement.
    """
    
    def __init__(self):
        self.governance_active: bool = False
        self.policy_cache: Dict[str, Dict[str, Any]] = {}
        self.compliance_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 300  # 5 minutes
        
        # Component managers
        self.policy_manager = PolicyManager()
        self.compliance_monitor = ComplianceMonitor()
        self.audit_trail = AuditTrail()
        self.risk_assessor = RiskAssessor()
        self.rule_automator = RuleAutomator()
        self.dashboard = ComplianceDashboard()
        
        # Configuration
        self.default_policy_priority: int = 50
        self.max_policy_depth: int = 10  # Prevent infinite recursion
        self.compliance_check_interval: int = 3600  # 1 hour
        self.audit_retention_days: int = 2555  # 7 years
        
        # Governance metrics
        self.governance_metrics = {
            "total_policies": 0,
            "active_policies": 0,
            "compliance_checks": 0,
            "audit_events": 0,
            "risk_assessments": 0,
            "automated_enforcements": 0
        }
    
    async def start_governance(self) -> None:
        """Start the governance engine."""
        if self.governance_active:
            return
        
        self.governance_active = True
        
        # Start component managers
        await self.policy_manager.start()
        await self.compliance_monitor.start()
        await self.audit_trail.start()
        await self.risk_assessor.start()
        await self.rule_automator.start()
        await self.dashboard.start()
        
        # Start background tasks
        asyncio.create_task(self._governance_loop())
        
        logger.info("Governance engine started")
    
    async def stop_governance(self) -> None:
        """Stop the governance engine."""
        self.governance_active = False
        
        # Stop component managers
        await self.policy_manager.stop()
        await self.compliance_monitor.stop()
        await self.audit_trail.stop()
        await self.risk_assessor.stop()
        await self.rule_automator.stop()
        await self.dashboard.stop()
        
        logger.info("Governance engine stopped")
    
    async def create_rule(
        self,
        name: str,
        description: str,
        rule_type: RuleType,
        conditions: Dict[str, Any],
        actions: List[Dict[str, Any]],
        priority: int = 50,
        enabled: bool = True,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> GovernanceRule:
        """
        Create a new governance rule.
        
        Args:
            name: Rule name
            description: Rule description
            rule_type: Type of rule
            conditions: Rule conditions
            actions: Rule actions
            priority: Rule priority (0-100)
            enabled: Whether rule is enabled
            tags: Rule tags
            metadata: Additional metadata
            created_by: User who created the rule
            
        Returns:
            GovernanceRule: Created rule
            
        Raises:
            GovernanceError: If creation fails
        """
        try:
            # Validate rule data
            await self._validate_rule_data(rule_type, conditions, actions)
            
            async with get_db_session() as session:
                rule = GovernanceRule(
                    name=name,
                    description=description,
                    rule_type=rule_type,
                    conditions=conditions,
                    actions=actions,
                    priority=priority,
                    enabled=enabled,
                    tags=tags or [],
                    metadata=metadata or {},
                    status=RuleStatus.ACTIVE if enabled else RuleStatus.DRAFT,
                    created_by=created_by
                )
                
                session.add(rule)
                await session.commit()
                await session.refresh(rule)
                
                # Cache rule
                self._cache_rule(rule)
                
                # Update metrics
                self.governance_metrics["total_policies"] += 1
                if enabled:
                    self.governance_metrics["active_policies"] += 1
                
                logger.info(
                    "Governance rule created",
                    rule_id=str(rule.id),
                    name=name,
                    rule_type=rule_type.value
                )
                
                return rule
                
        except Exception as e:
            raise GovernanceError(f"Failed to create governance rule: {str(e)}") from e
    
    async def enforce_rule(
        self,
        rule_id: str,
        context: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Enforce a governance rule.
        
        Args:
            rule_id: Rule ID
            context: Context for rule evaluation
            user_id: User ID performing the action
            
        Returns:
            Dict[str, Any]: Rule enforcement result
            
        Raises:
            GovernanceError: If enforcement fails
        """
        try:
            # Get rule
            rule = await self._get_rule(rule_id)
            if not rule:
                raise GovernanceError(f"Rule not found: {rule_id}")
            
            if not rule.enabled:
                return {"enforced": False, "reason": "Rule is disabled"}
            
            # Evaluate conditions
            conditions_met = await self._evaluate_conditions(rule.conditions, context)
            
            if not conditions_met:
                return {"enforced": False, "reason": "Conditions not met"}
            
            # Execute actions
            action_results = []
            for action in rule.actions:
                try:
                    result = await self._execute_action(action, context, user_id)
                    action_results.append(result)
                except Exception as e:
                    logger.error(
                        "Action execution failed",
                        rule_id=rule_id,
                        action=action,
                        error=str(e)
                    )
                    action_results.append({"success": False, "error": str(e)})
            
            # Log enforcement
            await self.audit_trail.log_event(
                event_type="rule_enforced",
                resource_id=rule_id,
                details={
                    "rule_name": rule.name,
                    "context": context,
                    "action_results": action_results
                },
                user_id=user_id
            )
            
            # Update metrics
            self.governance_metrics["automated_enforcements"] += 1
            
            logger.info(
                "Rule enforced successfully",
                rule_id=rule_id,
                actions_count=len(action_results)
            )
            
            return {
                "enforced": True,
                "rule_id": rule_id,
                "rule_name": rule.name,
                "action_results": action_results
            }
            
        except Exception as e:
            logger.error(
                "Rule enforcement failed",
                rule_id=rule_id,
                error=str(e)
            )
            
            raise GovernanceError(f"Failed to enforce rule: {str(e)}") from e
    
    async def check_compliance(
        self,
        entity_type: str,
        entity_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check compliance for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            context: Additional context
            
        Returns:
            Dict[str, Any]: Compliance check result
        """
        try:
            # Get applicable rules
            applicable_rules = await self._get_applicable_rules(entity_type, context)
            
            compliance_results = []
            violations = []
            
            for rule in applicable_rules:
                try:
                    result = await self.compliance_monitor.check_rule_compliance(
                        rule, entity_type, entity_id, context
                    )
                    compliance_results.append(result)
                    
                    if not result["compliant"]:
                        violations.append({
                            "rule_id": str(rule.id),
                            "rule_name": rule.name,
                            "severity": rule.metadata.get("severity", "medium"),
                            "description": result.get("violation_description", "Rule violation"),
                            "remediation": result.get("remediation", "No remediation available")
                        })
                        
                except Exception as e:
                    logger.error(
                        "Compliance check failed",
                        rule_id=str(rule.id),
                        error=str(e)
                    )
                    compliance_results.append({
                        "rule_id": str(rule.id),
                        "compliant": False,
                        "error": str(e)
                    })
            
            # Calculate overall compliance
            total_checks = len(compliance_results)
            compliant_checks = len([r for r in compliance_results if r.get("compliant", False)])
            compliance_rate = (compliant_checks / total_checks * 100) if total_checks > 0 else 0
            
            # Determine compliance status
            if compliance_rate >= 100:
                compliance_status = ComplianceStatus.COMPLIANT
            elif compliance_rate >= 80:
                compliance_status = ComplianceStatus.PARTIALLY_COMPLIANT
            else:
                compliance_status = ComplianceStatus.NON_COMPLIANT
            
            result = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "compliance_status": compliance_status.value,
                "compliance_rate": compliance_rate,
                "total_checks": total_checks,
                "compliant_checks": compliant_checks,
                "violations": violations,
                "check_timestamp": datetime.utcnow().isoformat()
            }
            
            # Update metrics
            self.governance_metrics["compliance_checks"] += 1
            
            return result
            
        except Exception as e:
            raise GovernanceError(f"Failed to check compliance: {str(e)}") from e
    
    async def generate_compliance_report(
        self,
        report_type: str = "summary",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None
    ) -> ComplianceReport:
        """
        Generate a compliance report.
        
        Args:
            report_type: Type of report
            period_start: Start of period
            period_end: End of period
            entity_type: Filter by entity type
            entity_ids: Filter by entity IDs
            
        Returns:
            ComplianceReport: Generated report
        """
        try:
            # Generate report data
            report_data = await self.compliance_monitor.generate_report_data(
                report_type, period_start, period_end, entity_type, entity_ids
            )
            
            async with get_db_session() as session:
                report = ComplianceReport(
                    report_type=report_type,
                    period_start=period_start or datetime.utcnow() - timedelta(days=30),
                    period_end=period_end or datetime.utcnow(),
                    entity_type=entity_type,
                    entity_ids=entity_ids or [],
                    report_data=report_data,
                    status="completed",
                    generated_at=datetime.utcnow()
                )
                
                session.add(report)
                await session.commit()
                await session.refresh(report)
            
            logger.info(
                "Compliance report generated",
                report_id=str(report.id),
                report_type=report_type
            )
            
            return report
            
        except Exception as e:
            raise GovernanceError(f"Failed to generate compliance report: {str(e)}") from e
    
    async def get_rule(
        self,
        rule_id: str,
        include_details: bool = True
    ) -> Optional[GovernanceRule]:
        """
        Get a governance rule by ID.
        
        Args:
            rule_id: Rule ID
            include_details: Whether to include detailed information
            
        Returns:
            GovernanceRule: Rule or None
        """
        return await self._get_rule(rule_id, include_details)
    
    async def list_rules(
        self,
        rule_type: Optional[RuleType] = None,
        status: Optional[RuleStatus] = None,
        enabled: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[GovernanceRule]:
        """
        List governance rules with optional filtering.
        
        Args:
            rule_type: Filter by rule type
            status: Filter by status
            enabled: Filter by enabled status
            tags: Filter by tags
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[GovernanceRule]: List of rules
        """
        async with get_db_session() as session:
            query = select(GovernanceRule).where(GovernanceRule.deleted_at.is_(None))
            
            if rule_type:
                query = query.where(GovernanceRule.rule_type == rule_type)
            
            if status:
                query = query.where(GovernanceRule.status == status)
            
            if enabled is not None:
                query = query.where(GovernanceRule.enabled == enabled)
            
            if tags:
                # Simple tag filtering
                for tag in tags:
                    query = query.where(GovernanceRule.tags.contains([tag]))
            
            query = query.order_by(GovernanceRule.priority.desc(), GovernanceRule.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            rules = result.scalars().all()
            
            return list(rules)
    
    async def update_rule(
        self,
        rule_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[uuid.UUID] = None
    ) -> GovernanceRule:
        """
        Update a governance rule.
        
        Args:
            rule_id: Rule ID
            updates: Fields to update
            updated_by: User who updated the rule
            
        Returns:
            GovernanceRule: Updated rule
            
        Raises:
            GovernanceError: If update fails
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(GovernanceRule).where(
                        GovernanceRule.id == uuid.UUID(rule_id),
                        GovernanceRule.deleted_at.is_(None)
                    )
                )
                rule = result.scalar_one_or_none()
                
                if not rule:
                    raise GovernanceError(f"Rule not found: {rule_id}")
                
                # Update fields
                if "name" in updates:
                    rule.name = updates["name"]
                
                if "description" in updates:
                    rule.description = updates["description"]
                
                if "conditions" in updates:
                    rule.conditions = updates["conditions"]
                
                if "actions" in updates:
                    rule.actions = updates["actions"]
                
                if "priority" in updates:
                    rule.priority = updates["priority"]
                
                if "enabled" in updates:
                    rule.enabled = updates["enabled"]
                    rule.status = RuleStatus.ACTIVE if updates["enabled"] else RuleStatus.DRAFT
                
                if "tags" in updates:
                    rule.tags = updates["tags"]
                
                if "metadata" in updates:
                    rule.metadata = updates["metadata"]
                
                rule.updated_by = updated_by
                rule.updated_at = datetime.utcnow()
                
                session.add(rule)
                await session.commit()
                await session.refresh(rule)
                
                # Update cache
                self._cache_rule(rule)
                
                logger.info(
                    "Governance rule updated",
                    rule_id=rule_id,
                    user_id=str(updated_by) if updated_by else None
                )
                
                return rule
                
        except Exception as e:
            raise GovernanceError(f"Failed to update rule: {str(e)}") from e
    
    async def delete_rule(
        self,
        rule_id: str,
        deleted_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Delete a governance rule (soft delete).
        
        Args:
            rule_id: Rule ID
            deleted_by: User who deleted the rule
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(GovernanceRule).where(
                        GovernanceRule.id == uuid.UUID(rule_id),
                        GovernanceRule.deleted_at.is_(None)
                    )
                )
                rule = result.scalar_one_or_none()
                
                if not rule:
                    return False
                
                rule.soft_delete(deleted_by)
                session.add(rule)
                await session.commit()
                
                # Remove from cache
                cache_key = f"rule_{rule_id}"
                self.policy_cache.pop(cache_key, None)
                
                logger.info(
                    "Governance rule deleted",
                    rule_id=rule_id,
                    user_id=str(deleted_by) if deleted_by else None
                )
                
                return True
                
        except Exception as e:
            raise GovernanceError(f"Failed to delete rule: {str(e)}") from e
    
    async def get_governance_summary(self) -> Dict[str, Any]:
        """
        Get overall governance summary.
        
        Returns:
            Dict[str, Any]: Governance summary
        """
        try:
            async with get_db_session() as session:
                # Get rule counts
                result = await session.execute(
                    select(
                        GovernanceRule.status,
                        func.count(GovernanceRule.id)
                    ).where(
                        GovernanceRule.deleted_at.is_(None)
                    ).group_by(GovernanceRule.status)
                )
                status_counts = dict(result.all())
                
                result = await session.execute(
                    select(
                        GovernanceRule.rule_type,
                        func.count(GovernanceRule.id)
                    ).where(
                        GovernanceRule.deleted_at.is_(None)
                    ).group_by(GovernanceRule.rule_type)
                )
                type_counts = dict(result.all())
                
                # Get compliance stats
                result = await session.execute(
                    select(
                        ComplianceReport.status,
                        func.count(ComplianceReport.id)
                    ).where(
                        ComplianceReport.deleted_at.is_(None)
                    ).group_by(ComplianceReport.status)
                )
                compliance_counts = dict(result.all())
                
                # Get audit stats
                result = await session.execute(
                    select(func.count(AuditLog.id)).where(AuditLog.deleted_at.is_(None))
                )
                total_audits = result.scalar() or 0
            
            summary = {
                "governance_active": self.governance_active,
                "rules": {
                    "total": sum(status_counts.values()),
                    "by_status": status_counts,
                    "by_type": type_counts,
                    "enabled": len([r for r in await self.list_rules(enabled=True)])
                },
                "compliance": {
                    "total_reports": sum(compliance_counts.values()),
                    "by_status": compliance_counts
                },
                "audits": {
                    "total_events": total_audits
                },
                "metrics": self.governance_metrics,
                "cache_size": len(self.policy_cache),
                "cache_ttl": self.cache_ttl
            }
            
            return summary
            
        except Exception as e:
            raise GovernanceError(f"Failed to get governance summary: {str(e)}") from e
    
    async def _governance_loop(self) -> None:
        """Main governance loop."""
        while self.governance_active:
            try:
                # Clean up old cache entries
                await self._cleanup_cache()
                
                # Update governance metrics
                await self._update_governance_metrics()
                
                # Sleep before next iteration
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(
                    "Governance loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _validate_rule_data(
        self,
        rule_type: RuleType,
        conditions: Dict[str, Any],
        actions: List[Dict[str, Any]]
    ) -> None:
        """Validate rule data."""
        errors = []
        
        # Validate conditions
        if not conditions:
            errors.append("Conditions are required")
        elif not isinstance(conditions, dict):
            errors.append("Conditions must be a dictionary")
        
        # Validate actions
        if not actions:
            errors.append("Actions are required")
        elif not isinstance(actions, list):
            errors.append("Actions must be a list")
        else:
            for i, action in enumerate(actions):
                if not isinstance(action, dict):
                    errors.append(f"Action {i} must be a dictionary")
                elif "type" not in action:
                    errors.append(f"Action {i} must have a type")
        
        # Type-specific validation
        if rule_type == RuleType.ACCESS_CONTROL:
            required_fields = ["resource", "permission"]
            for field in required_fields:
                if field not in conditions:
                    errors.append(f"Access control rule requires {field} in conditions")
        
        elif rule_type == RuleType.DATA_PROTECTION:
            required_fields = ["data_type", "protection_level"]
            for field in required_fields:
                if field not in conditions:
                    errors.append(f"Data protection rule requires {field} in conditions")
        
        if errors:
            raise ValidationError(
                f"Rule validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    async def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate rule conditions."""
        try:
            # Simple condition evaluation
            for condition_key, condition_value in conditions.items():
                if condition_key not in context:
                    return False
                
                context_value = context[condition_key]
                
                if isinstance(condition_value, dict):
                    # Complex condition
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
                    elif operator == "not_in":
                        if context_value in value:
                            return False
                    elif operator == "greater_than":
                        if not context_value > value:
                            return False
                    elif operator == "less_than":
                        if not context_value < value:
                            return False
                    elif operator == "contains":
                        if value not in context_value:
                            return False
                else:
                    # Simple equality check
                    if context_value != condition_value:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Condition evaluation failed",
                conditions=conditions,
                error=str(e)
            )
            return False
    
    async def _execute_action(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Execute a rule action."""
        action_type = action.get("type")
        
        try:
            if action_type == "log":
                # Log action
                message = action.get("message", "Rule action executed")
                logger.info(
                    "Rule action: log",
                    message=message,
                    context=context
                )
                return {"success": True, "action": "log", "message": message}
            
            elif action_type == "block":
                # Block action
                reason = action.get("reason", "Access denied by policy")
                return {"success": True, "action": "block", "reason": reason}
            
            elif action_type == "notify":
                # Notify action
                recipients = action.get("recipients", [])
                message = action.get("message", "Policy notification")
                # In real implementation, would send notification
                logger.info(
                    "Rule action: notify",
                    recipients=recipients,
                    message=message
                )
                return {"success": True, "action": "notify", "recipients": recipients}
            
            elif action_type == "escalate":
                # Escalate action
                escalation_level = action.get("level", "medium")
                reason = action.get("reason", "Policy escalation")
                logger.warning(
                    "Rule action: escalate",
                    level=escalation_level,
                    reason=reason
                )
                return {"success": True, "action": "escalate", "level": escalation_level}
            
            else:
                raise GovernanceError(f"Unknown action type: {action_type}")
                
        except Exception as e:
            return {"success": False, "action": action_type, "error": str(e)}
    
    async def _get_rule(
        self,
        rule_id: str,
        include_details: bool = True
    ) -> Optional[GovernanceRule]:
        """Get rule from cache or database."""
        # Check cache first
        cache_key = f"rule_{rule_id}"
        if cache_key in self.policy_cache:
            cached_rule = self.policy_cache[cache_key]
            cache_age = datetime.utcnow() - cached_rule["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                return cached_rule["rule"]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(GovernanceRule).where(
                    GovernanceRule.id == uuid.UUID(rule_id),
                    GovernanceRule.deleted_at.is_(None)
                )
            )
            rule = result.scalar_one_or_none()
            
            if rule:
                # Cache rule
                self._cache_rule(rule)
            
            return rule
    
    async def _get_applicable_rules(
        self,
        entity_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[GovernanceRule]:
        """Get rules applicable to an entity type."""
        try:
            # Get all active rules
            rules = await self.list_rules(enabled=True)
            
            # Filter by applicability
            applicable_rules = []
            for rule in rules:
                # Check if rule applies to entity type
                applies_to = rule.conditions.get("applies_to", [])
                if applies_to and entity_type not in applies_to:
                    continue
                
                # Check other conditions
                if context and not await self._evaluate_conditions(rule.conditions, context):
                    continue
                
                applicable_rules.append(rule)
            
            # Sort by priority
            applicable_rules.sort(key=lambda r: r.priority, reverse=True)
            
            return applicable_rules
            
        except Exception as e:
            logger.error(
                "Failed to get applicable rules",
                entity_type=entity_type,
                error=str(e)
            )
            return []
    
    def _cache_rule(self, rule: GovernanceRule) -> None:
        """Cache a rule."""
        cache_key = f"rule_{str(rule.id)}"
        self.policy_cache[cache_key] = {
            "rule": rule,
            "cached_at": datetime.utcnow()
        }
    
    async def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.utcnow()
        
        for key, (timestamp, _) in list(self.policy_cache.items()):
            if current_time - timestamp > timedelta(seconds=self.cache_ttl):
                del self.policy_cache[key]
    
    async def _update_governance_metrics(self) -> None:
        """Update governance metrics from database."""
        try:
            async with get_db_session() as session:
                # Get current counts
                result = await session.execute(
                    select(func.count(GovernanceRule.id)).where(GovernanceRule.deleted_at.is_(None))
                )
                current_rules = result.scalar() or 0
                
                result = await session.execute(
                    select(func.count(AuditLog.id)).where(AuditLog.deleted_at.is_(None))
                )
                current_audits = result.scalar() or 0
                
                # Update metrics if they've changed
                if current_rules > self.governance_metrics["total_policies"]:
                    self.governance_metrics["total_policies"] = current_rules
                
                if current_audits > self.governance_metrics["audit_events"]:
                    self.governance_metrics["audit_events"] = current_audits
                
        except Exception as e:
            logger.error(
                "Failed to update governance metrics",
                error=str(e)
            )
