"""
BaseLayer Policy Manager

Policy management and enforcement system
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
    GovernanceRule, AuditLog,
    RuleType, RuleStatus
)
from ..models.user import User
from .exceptions import (
    PolicyError,
    ValidationError,
    AuthorizationError
)

logger = get_logger(__name__)


class PolicyManager:
    """
    Policy management and enforcement system.
    
    Handles policy creation, validation, enforcement,
    and lifecycle management with comprehensive tracking.
    """
    
    def __init__(self):
        self.policy_active: bool = False
        self.policy_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 600  # 10 minutes
        self.max_policy_depth: int = 10
        self.policy_enforcement_queue: asyncio.Queue = asyncio.Queue()
        
        # Policy configuration
        self.policy_types = {
            "access_control": {
                "description": "Controls access to resources",
                "required_fields": ["resource", "permission", "conditions"],
                "default_actions": ["allow", "deny", "log"]
            },
            "data_protection": {
                "description": "Protects sensitive data",
                "required_fields": ["data_type", "protection_level", "access_controls"],
                "default_actions": ["encrypt", "mask", "restrict", "audit"]
            },
            "security": {
                "description": "Security policies and controls",
                "required_fields": ["security_level", "controls", "monitoring"],
                "default_actions": ["enforce", "monitor", "alert", "block"]
            },
            "operational": {
                "description": "Operational policies and procedures",
                "required_fields": ["procedure", "responsibilities", "escalation"],
                "default_actions": ["execute", "notify", "escalate", "log"]
            },
            "compliance": {
                "description": "Regulatory compliance policies",
                "required_fields": ["regulation", "requirements", "evidence"],
                "default_actions": ["audit", "report", "enforce", "remediate"]
            }
        }
        
        # Policy metrics
        self.policy_metrics = {
            "total_policies": 0,
            "active_policies": 0,
            "enforced_policies": 0,
            "violations_detected": 0,
            "average_enforcement_time": 0.0
        }
    
    async def start(self) -> None:
        """Start the policy manager."""
        if self.policy_active:
            return
        
        self.policy_active = True
        asyncio.create_task(self._policy_enforcement_loop())
        
        logger.info("Policy manager started")
    
    async def stop(self) -> None:
        """Stop the policy manager."""
        self.policy_active = False
        logger.info("Policy manager stopped")
    
    async def create_policy(
        self,
        name: str,
        description: str,
        policy_type: str,
        rules: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        priority: int = 50,
        enabled: bool = True,
        created_by: Optional[uuid.UUID] = None
    ) -> GovernanceRule:
        """
        Create a new policy.
        
        Args:
            name: Policy name
            description: Policy description
            policy_type: Type of policy
            rules: Policy rules
            metadata: Additional metadata
            tags: Policy tags
            priority: Policy priority
            enabled: Whether policy is enabled
            created_by: User who created the policy
            
        Returns:
            GovernanceRule: Created policy
            
        Raises:
            PolicyError: If creation fails
        """
        try:
            # Validate policy type
            if policy_type not in self.policy_types:
                raise PolicyError(f"Unknown policy type: {policy_type}")
            
            # Validate policy rules
            await self._validate_policy_rules(policy_type, rules)
            
            # Convert to governance rule format
            conditions = {
                "policy_type": policy_type,
                "rules": rules,
                "metadata": metadata or {}
            }
            
            # Define default actions based on policy type
            default_actions = self.policy_types[policy_type]["default_actions"]
            actions = [{"type": action} for action in default_actions]
            
            async with get_db_session() as session:
                policy = GovernanceRule(
                    name=name,
                    description=description,
                    rule_type=RuleType.ACCESS_CONTROL,  # Map to existing enum
                    conditions=conditions,
                    actions=actions,
                    priority=priority,
                    enabled=enabled,
                    tags=tags or [],
                    metadata=metadata or {},
                    status=RuleStatus.ACTIVE if enabled else RuleStatus.DRAFT,
                    created_by=created_by
                )
                
                session.add(policy)
                await session.commit()
                await session.refresh(policy)
                
                # Cache policy
                self._cache_policy(policy)
                
                # Update metrics
                self.policy_metrics["total_policies"] += 1
                if enabled:
                    self.policy_metrics["active_policies"] += 1
                
                logger.info(
                    "Policy created",
                    policy_id=str(policy.id),
                    name=name,
                    policy_type=policy_type
                )
                
                return policy
                
        except Exception as e:
            raise PolicyError(f"Failed to create policy: {str(e)}") from e
    
    async def enforce_policy(
        self,
        policy_id: str,
        context: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce a policy.
        
        Args:
            policy_id: Policy ID
            context: Context for policy enforcement
            user_id: User ID performing the action
            dry_run: Whether to perform a dry run
            
        Returns:
            Dict[str, Any]: Policy enforcement result
        """
        try:
            # Get policy
            policy = await self._get_policy(policy_id)
            if not policy:
                raise PolicyError(f"Policy not found: {policy_id}")
            
            if not policy.enabled:
                return {"enforced": False, "reason": "Policy is disabled"}
            
            # Evaluate policy rules
            start_time = datetime.utcnow()
            evaluation_result = await self._evaluate_policy(policy, context)
            
            # Execute actions if not dry run
            action_results = []
            if not dry_run and evaluation_result["applicable"]:
                for action in policy.actions:
                    try:
                        result = await self._execute_policy_action(action, context, user_id)
                        action_results.append(result)
                    except Exception as e:
                        logger.error(
                            "Policy action execution failed",
                            policy_id=policy_id,
                            action=action,
                            error=str(e)
                        )
                        action_results.append({"success": False, "error": str(e)})
            
            # Calculate enforcement time
            enforcement_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Log enforcement
            await self._log_policy_enforcement(
                policy, context, evaluation_result, action_results, enforcement_time, user_id, dry_run
            )
            
            # Update metrics
            if not dry_run:
                self.policy_metrics["enforced_policies"] += 1
                if evaluation_result.get("violations"):
                    self.policy_metrics["violations_detected"] += len(evaluation_result["violations"])
                
                # Update average enforcement time
                enforced = self.policy_metrics["enforced_policies"]
                if enforced > 0:
                    current_avg = self.policy_metrics["average_enforcement_time"]
                    self.policy_metrics["average_enforcement_time"] = (
                        (current_avg * (enforced - 1) + enforcement_time) / enforced
                    )
            
            result = {
                "policy_id": policy_id,
                "policy_name": policy.name,
                "applicable": evaluation_result["applicable"],
                "compliant": evaluation_result["compliant"],
                "violations": evaluation_result.get("violations", []),
                "action_results": action_results,
                "enforcement_time": enforcement_time,
                "dry_run": dry_run,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return result
            
        except Exception as e:
            raise PolicyError(f"Failed to enforce policy: {str(e)}") from e
    
    async def evaluate_policy_compliance(
        self,
        policy_id: str,
        entity_type: str,
        entity_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate policy compliance for an entity.
        
        Args:
            policy_id: Policy ID
            entity_type: Type of entity
            entity_id: Entity ID
            context: Additional context
            
        Returns:
            Dict[str, Any]: Compliance evaluation result
        """
        try:
            # Get policy
            policy = await self._get_policy(policy_id)
            if not policy:
                raise PolicyError(f"Policy not found: {policy_id}")
            
            # Prepare evaluation context
            eval_context = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                **(context or {})
            }
            
            # Evaluate policy
            evaluation_result = await self._evaluate_policy(policy, eval_context)
            
            # Calculate compliance score
            total_rules = len(policy.conditions.get("rules", []))
            compliant_rules = total_rules - len(evaluation_result.get("violations", []))
            compliance_score = (compliant_rules / total_rules * 100) if total_rules > 0 else 100
            
            result = {
                "policy_id": policy_id,
                "policy_name": policy.name,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "compliant": evaluation_result["compliant"],
                "compliance_score": compliance_score,
                "total_rules": total_rules,
                "compliant_rules": compliant_rules,
                "violations": evaluation_result.get("violations", []),
                "evaluation_timestamp": datetime.utcnow().isoformat()
            }
            
            return result
            
        except Exception as e:
            raise PolicyError(f"Failed to evaluate policy compliance: {str(e)}") from e
    
    async def get_policy(
        self,
        policy_id: str,
        include_details: bool = True
    ) -> Optional[GovernanceRule]:
        """
        Get a policy by ID.
        
        Args:
            policy_id: Policy ID
            include_details: Whether to include detailed information
            
        Returns:
            GovernanceRule: Policy or None
        """
        return await self._get_policy(policy_id, include_details)
    
    async def list_policies(
        self,
        policy_type: Optional[str] = None,
        status: Optional[RuleStatus] = None,
        enabled: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[GovernanceRule]:
        """
        List policies with optional filtering.
        
        Args:
            policy_type: Filter by policy type
            status: Filter by status
            enabled: Filter by enabled status
            tags: Filter by tags
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[GovernanceRule]: List of policies
        """
        async with get_db_session() as session:
            query = select(GovernanceRule).where(GovernanceRule.deleted_at.is_(None))
            
            if policy_type:
                query = query.where(
                    GovernanceRule.conditions["policy_type"].astext == policy_type
                )
            
            if status:
                query = query.where(GovernanceRule.status == status)
            
            if enabled is not None:
                query = query.where(GovernanceRule.enabled == enabled)
            
            if tags:
                for tag in tags:
                    query = query.where(GovernanceRule.tags.contains([tag]))
            
            query = query.order_by(GovernanceRule.priority.desc(), GovernanceRule.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            policies = result.scalars().all()
            
            return list(policies)
    
    async def update_policy(
        self,
        policy_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[uuid.UUID] = None
    ) -> GovernanceRule:
        """
        Update a policy.
        
        Args:
            policy_id: Policy ID
            updates: Fields to update
            updated_by: User who updated the policy
            
        Returns:
            GovernanceRule: Updated policy
            
        Raises:
            PolicyError: If update fails
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(GovernanceRule).where(
                        GovernanceRule.id == uuid.UUID(policy_id),
                        GovernanceRule.deleted_at.is_(None)
                    )
                )
                policy = result.scalar_one_or_none()
                
                if not policy:
                    raise PolicyError(f"Policy not found: {policy_id}")
                
                # Update fields
                if "name" in updates:
                    policy.name = updates["name"]
                
                if "description" in updates:
                    policy.description = updates["description"]
                
                if "conditions" in updates:
                    # Validate new conditions
                    policy_type = policy.conditions.get("policy_type")
                    rules = updates["conditions"].get("rules", [])
                    await self._validate_policy_rules(policy_type, rules)
                    policy.conditions = updates["conditions"]
                
                if "actions" in updates:
                    policy.actions = updates["actions"]
                
                if "priority" in updates:
                    policy.priority = updates["priority"]
                
                if "enabled" in updates:
                    policy.enabled = updates["enabled"]
                    policy.status = RuleStatus.ACTIVE if updates["enabled"] else RuleStatus.DRAFT
                
                if "tags" in updates:
                    policy.tags = updates["tags"]
                
                if "metadata" in updates:
                    policy.metadata = updates["metadata"]
                
                policy.updated_by = updated_by
                policy.updated_at = datetime.utcnow()
                
                session.add(policy)
                await session.commit()
                await session.refresh(policy)
                
                # Update cache
                self._cache_policy(policy)
                
                logger.info(
                    "Policy updated",
                    policy_id=policy_id,
                    user_id=str(updated_by) if updated_by else None
                )
                
                return policy
                
        except Exception as e:
            raise PolicyError(f"Failed to update policy: {str(e)}") from e
    
    async def delete_policy(
        self,
        policy_id: str,
        deleted_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Delete a policy (soft delete).
        
        Args:
            policy_id: Policy ID
            deleted_by: User who deleted the policy
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(GovernanceRule).where(
                        GovernanceRule.id == uuid.UUID(policy_id),
                        GovernanceRule.deleted_at.is_(None)
                    )
                )
                policy = result.scalar_one_or_none()
                
                if not policy:
                    return False
                
                policy.soft_delete(deleted_by)
                session.add(policy)
                await session.commit()
                
                # Remove from cache
                cache_key = f"policy_{policy_id}"
                self.policy_cache.pop(cache_key, None)
                
                logger.info(
                    "Policy deleted",
                    policy_id=policy_id,
                    user_id=str(deleted_by) if deleted_by else None
                )
                
                return True
                
        except Exception as e:
            raise PolicyError(f"Failed to delete policy: {str(e)}") from e
    
    async def get_policy_statistics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get policy statistics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Policy statistics
        """
        try:
            async with get_db_session() as session:
                # Get policy counts by type
                query = select(GovernanceRule).where(GovernanceRule.deleted_at.is_(None))
                
                if period_start:
                    query = query.where(GovernanceRule.created_at >= period_start)
                
                if period_end:
                    query = query.where(GovernanceRule.created_at <= period_end)
                
                result = await session.execute(query)
                policies = result.scalars().all()
                
                # Calculate statistics
                total_policies = len(policies)
                active_policies = len([p for p in policies if p.enabled])
                
                # Policy type distribution
                type_counts = {}
                for policy in policies:
                    policy_type = policy.conditions.get("policy_type", "unknown")
                    type_counts[policy_type] = type_counts.get(policy_type, 0) + 1
                
                # Priority distribution
                priority_counts = {}
                for policy in policies:
                    priority_range = self._get_priority_range(policy.priority)
                    priority_counts[priority_range] = priority_counts.get(priority_range, 0) + 1
                
                statistics = {
                    "period": {
                        "start": period_start.isoformat() if period_start else None,
                        "end": period_end.isoformat() if period_end else None
                    },
                    "total_policies": total_policies,
                    "active_policies": active_policies,
                    "by_type": type_counts,
                    "by_priority": priority_counts,
                    "policy_metrics": self.policy_metrics
                }
                
                return statistics
                
        except Exception as e:
            raise PolicyError(f"Failed to get policy statistics: {str(e)}") from e
    
    async def _policy_enforcement_loop(self) -> None:
        """Main policy enforcement loop."""
        while self.policy_active:
            try:
                # Process policy enforcement queue
                while not self.policy_enforcement_queue.empty():
                    try:
                        enforcement_request = self.policy_enforcement_queue.get_nowait()
                        await self._process_enforcement_request(enforcement_request)
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        logger.error(
                            "Policy enforcement request failed",
                            error=str(e)
                        )
                
                # Sleep before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(
                    "Policy enforcement loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_enforcement_request(self, request: Dict[str, Any]) -> None:
        """Process a policy enforcement request."""
        try:
            policy_id = request["policy_id"]
            context = request["context"]
            user_id = request.get("user_id")
            dry_run = request.get("dry_run", False)
            
            await self.enforce_policy(policy_id, context, user_id, dry_run)
            
        except Exception as e:
            logger.error(
                "Failed to process enforcement request",
                request=request,
                error=str(e)
            )
    
    async def _validate_policy_rules(self, policy_type: str, rules: List[Dict[str, Any]]) -> None:
        """Validate policy rules."""
        if not rules:
            raise ValidationError("Policy must have at least one rule")
        
        policy_config = self.policy_types.get(policy_type, {})
        required_fields = policy_config.get("required_fields", [])
        
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValidationError(f"Rule {i} must be a dictionary")
            
            # Check required fields
            for field in required_fields:
                if field not in rule:
                    raise ValidationError(f"Rule {i} missing required field: {field}")
            
            # Validate rule structure
            if "conditions" not in rule:
                raise ValidationError(f"Rule {i} must have conditions")
            
            if "actions" not in rule:
                raise ValidationError(f"Rule {i} must have actions")
    
    async def _evaluate_policy(self, policy: GovernanceRule, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a policy against context."""
        try:
            rules = policy.conditions.get("rules", [])
            violations = []
            
            for rule in rules:
                rule_result = await self._evaluate_policy_rule(rule, context)
                
                if not rule_result["compliant"]:
                    violations.append({
                        "rule": rule,
                        "violation": rule_result.get("violation", "Policy rule violated"),
                        "severity": rule.get("severity", "medium")
                    })
            
            applicable = len(rules) > 0
            compliant = len(violations) == 0
            
            return {
                "applicable": applicable,
                "compliant": compliant,
                "violations": violations,
                "evaluated_rules": len(rules)
            }
            
        except Exception as e:
            logger.error(
                "Policy evaluation failed",
                policy_id=str(policy.id),
                error=str(e)
            )
            return {
                "applicable": False,
                "compliant": False,
                "violations": [{"error": str(e)}],
                "evaluated_rules": 0
            }
    
    async def _evaluate_policy_rule(self, rule: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single policy rule."""
        try:
            conditions = rule.get("conditions", {})
            
            # Evaluate conditions
            for condition_key, condition_value in conditions.items():
                if condition_key not in context:
                    return {"compliant": False, "violation": f"Missing context: {condition_key}"}
                
                context_value = context[condition_key]
                
                if not self._evaluate_condition(condition_value, context_value):
                    return {"compliant": False, "violation": f"Condition failed: {condition_key}"}
            
            return {"compliant": True}
            
        except Exception as e:
            return {"compliant": False, "violation": f"Rule evaluation error: {str(e)}"}
    
    def _evaluate_condition(self, condition: Any, value: Any) -> bool:
        """Evaluate a single condition."""
        if isinstance(condition, dict):
            operator = condition.get("operator", "equals")
            expected_value = condition.get("value")
            
            if operator == "equals":
                return value == expected_value
            elif operator == "not_equals":
                return value != expected_value
            elif operator == "in":
                return value in expected_value
            elif operator == "not_in":
                return value not in expected_value
            elif operator == "greater_than":
                return value > expected_value
            elif operator == "less_than":
                return value < expected_value
            elif operator == "contains":
                return expected_value in value
            elif operator == "not_contains":
                return expected_value not in value
            else:
                return False
        else:
            return value == condition
    
    async def _execute_policy_action(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Execute a policy action."""
        action_type = action.get("type")
        
        try:
            if action_type == "allow":
                return {"success": True, "action": "allow", "message": "Access granted"}
            
            elif action_type == "deny":
                reason = action.get("reason", "Access denied by policy")
                return {"success": True, "action": "deny", "reason": reason}
            
            elif action_type == "log":
                message = action.get("message", "Policy action logged")
                logger.info(
                    "Policy action: log",
                    message=message,
                    context=context
                )
                return {"success": True, "action": "log", "message": message}
            
            elif action_type == "notify":
                recipients = action.get("recipients", [])
                message = action.get("message", "Policy notification")
                # In real implementation, would send notification
                logger.info(
                    "Policy action: notify",
                    recipients=recipients,
                    message=message
                )
                return {"success": True, "action": "notify", "recipients": recipients}
            
            elif action_type == "escalate":
                escalation_level = action.get("level", "medium")
                reason = action.get("reason", "Policy escalation")
                logger.warning(
                    "Policy action: escalate",
                    level=escalation_level,
                    reason=reason
                )
                return {"success": True, "action": "escalate", "level": escalation_level}
            
            else:
                raise PolicyError(f"Unknown policy action type: {action_type}")
                
        except Exception as e:
            return {"success": False, "action": action_type, "error": str(e)}
    
    async def _log_policy_enforcement(
        self,
        policy: GovernanceRule,
        context: Dict[str, Any],
        evaluation_result: Dict[str, Any],
        action_results: List[Dict[str, Any]],
        enforcement_time: float,
        user_id: Optional[uuid.UUID],
        dry_run: bool
    ) -> None:
        """Log policy enforcement."""
        try:
            async with get_db_session() as session:
                audit_log = AuditLog(
                    event_type="policy_enforcement",
                    resource_id=str(policy.id),
                    resource_type="policy",
                    details={
                        "policy_name": policy.name,
                        "context": context,
                        "evaluation_result": evaluation_result,
                        "action_results": action_results,
                        "enforcement_time": enforcement_time,
                        "dry_run": dry_run
                    },
                    user_id=user_id,
                    created_at=datetime.utcnow()
                )
                
                session.add(audit_log)
                await session.commit()
                
        except Exception as e:
            logger.error(
                "Failed to log policy enforcement",
                policy_id=str(policy.id),
                error=str(e)
            )
    
    async def _get_policy(
        self,
        policy_id: str,
        include_details: bool = True
    ) -> Optional[GovernanceRule]:
        """Get policy from cache or database."""
        # Check cache first
        cache_key = f"policy_{policy_id}"
        if cache_key in self.policy_cache:
            cached_policy = self.policy_cache[cache_key]
            cache_age = datetime.utcnow() - cached_policy["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                return cached_policy["policy"]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(GovernanceRule).where(
                    GovernanceRule.id == uuid.UUID(policy_id),
                    GovernanceRule.deleted_at.is_(None)
                )
            )
            policy = result.scalar_one_or_none()
            
            if policy:
                # Cache policy
                self._cache_policy(policy)
            
            return policy
    
    def _cache_policy(self, policy: GovernanceRule) -> None:
        """Cache a policy."""
        cache_key = f"policy_{str(policy.id)}"
        self.policy_cache[cache_key] = {
            "policy": policy,
            "cached_at": datetime.utcnow()
        }
    
    def _get_priority_range(self, priority: int) -> str:
        """Get priority range category."""
        if priority >= 80:
            return "high"
        elif priority >= 50:
            return "medium"
        else:
            return "low"
    
    def get_policy_manager_stats(self) -> Dict[str, Any]:
        """Get policy manager statistics."""
        return {
            "policy_active": self.policy_active,
            "cache_size": len(self.policy_cache),
            "cache_ttl": self.cache_ttl,
            "max_policy_depth": self.max_policy_depth,
            "policy_types": list(self.policy_types.keys()),
            "policy_metrics": self.policy_metrics
        }
