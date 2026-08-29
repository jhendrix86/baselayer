"""
BaseLayer Governance/Doctrine API - Policies

REST API endpoints for policy management and enforcement.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import get_db_session
from ...models.governance import (
    GovernanceRule, RuleType, RuleStatus
)
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import GovernanceEngine
from ..exceptions import (
    GovernanceError,
    PolicyError,
    ValidationError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/policies", tags=["Policies"])

# Global instance (will be injected in startup)
governance_engine: GovernanceEngine = None


def get_governance_engine() -> GovernanceEngine:
    """Get governance engine instance."""
    global governance_engine
    if not governance_engine:
        raise HTTPException(status_code=500, detail="Governance engine not initialized")
    return governance_engine


@router.get("/", response_model=List[Dict[str, Any]])
async def list_policies(
    rule_type: Optional[RuleType] = Query(None),
    status: Optional[RuleStatus] = Query(None),
    enabled: Optional[bool] = Query(None),
    tags: Optional[List[str]] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List governance policies with optional filtering.
    
    Args:
        rule_type: Filter by rule type
        status: Filter by status
        enabled: Filter by enabled status
        tags: Filter by tags
        limit: Maximum number of results
        offset: Pagination offset
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of policies
    """
    engine = get_governance_engine()
    
    policies = await engine.list_rules(
        rule_type=rule_type,
        status=status,
        enabled=enabled,
        tags=tags,
        limit=limit,
        offset=offset
    )
    
    return [policy.to_dict() for policy in policies]


@router.get("/types", response_model=List[Dict[str, Any]])
async def get_policy_types(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get available policy types.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Available policy types
    """
    types = []
    for rule_type in RuleType:
        types.append({
            "value": rule_type.value,
            "name": rule_type.value.replace("_", " ").title(),
            "description": f"{rule_type.value.replace('_', ' ').title()} policy"
        })
    
    return types


@router.get("/statistics", response_model=Dict[str, Any])
async def get_policy_statistics(
    period_start: Optional[datetime] = Query(None),
    period_end: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get policy statistics.
    
    Args:
        period_start: Start of period
        period_end: End of period
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Policy statistics
    """
    engine = get_governance_engine()
    
    try:
        statistics = await engine.get_governance_summary()
        
        return statistics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-enforce", response_model=Dict[str, Any])
async def batch_enforce_policies(
    policy_ids: List[str],
    context: Dict[str, Any],
    dry_run: bool = Query(False),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Enforce multiple policies in batch.
    
    Args:
        policy_ids: List of policy IDs
        context: Enforcement context
        dry_run: Whether to perform a dry run
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Batch enforcement results
    """
    engine = get_governance_engine()
    
    results = []
    successful = 0
    failed = 0
    
    for policy_id in policy_ids:
        try:
            result = await engine.enforce_rule(
                rule_id=policy_id,
                context=context,
                user_id=current_user.id
            )
            results.append(result)
            
            if result.get("enforced"):
                successful += 1
            else:
                failed += 1
                
        except Exception as e:
            failed += 1
            results.append({
                "policy_id": policy_id,
                "enforced": False,
                "error": str(e)
            })
    
    logger.info(
        "Batch policy enforcement completed via API",
        total_policies=len(policy_ids),
        successful=successful,
        failed=failed,
        user_id=str(current_user.id)
    )
    
    return {
        "total_policies": len(policy_ids),
        "successful": successful,
        "failed": failed,
        "results": results,
        "dry_run": dry_run
    }


@router.get("/{policy_id}", response_model=Dict[str, Any])
async def get_policy(
    policy_id: str,
    include_details: bool = Query(True),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific policy.
    
    Args:
        policy_id: Policy ID
        include_details: Whether to include detailed information
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Policy details
    """
    engine = get_governance_engine()
    
    policy = await engine.get_rule(policy_id, include_details=include_details)
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return policy.to_dict()


@router.post("/", response_model=Dict[str, Any])
async def create_policy(
    policy_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new governance policy.
    
    Args:
        policy_data: Policy data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created policy
    """
    engine = get_governance_engine()
    
    try:
        policy = await engine.create_rule(
            name=policy_data["name"],
            description=policy_data["description"],
            rule_type=RuleType(policy_data["rule_type"]),
            conditions=policy_data["conditions"],
            actions=policy_data["actions"],
            priority=policy_data.get("priority", 50),
            enabled=policy_data.get("enabled", True),
            tags=policy_data.get("tags"),
            metadata=policy_data.get("metadata"),
            created_by=current_user.id
        )
        
        logger.info(
            "Policy created via API",
            policy_id=str(policy.id),
            name=policy.name,
            user_id=str(current_user.id)
        )
        
        return policy.to_dict()
        
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GovernanceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{policy_id}", response_model=Dict[str, Any])
async def update_policy(
    policy_id: str,
    policy_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update a policy.
    
    Args:
        policy_id: Policy ID
        policy_data: Updated policy data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Updated policy
    """
    engine = get_governance_engine()
    
    try:
        policy = await engine.update_rule(
            policy_id=policy_id,
            updates=policy_data,
            updated_by=current_user.id
        )
        
        logger.info(
            "Policy updated via API",
            policy_id=policy_id,
            user_id=str(current_user.id)
        )
        
        return policy.to_dict()
        
    except GovernanceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{policy_id}", response_model=Dict[str, Any])
async def delete_policy(
    policy_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a policy.
    
    Args:
        policy_id: Policy ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    engine = get_governance_engine()
    
    success = await engine.delete_rule(policy_id, deleted_by=current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    logger.info(
        "Policy deleted via API",
        policy_id=policy_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Policy deleted successfully"}


@router.post("/{policy_id}/enforce", response_model=Dict[str, Any])
async def enforce_policy(
    policy_id: str,
    context: Dict[str, Any],
    dry_run: bool = Query(False),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Enforce a policy.
    
    Args:
        policy_id: Policy ID
        context: Enforcement context
        dry_run: Whether to perform a dry run
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Enforcement result
    """
    engine = get_governance_engine()
    
    try:
        result = await engine.enforce_rule(
            rule_id=policy_id,
            context=context,
            user_id=current_user.id
        )
        
        logger.info(
            "Policy enforced via API",
            policy_id=policy_id,
            user_id=str(current_user.id),
            dry_run=dry_run
        )
        
        return result
        
    except GovernanceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{policy_id}/check-compliance", response_model=Dict[str, Any])
async def check_policy_compliance(
    policy_id: str,
    entity_type: str,
    entity_id: str,
    context: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check compliance for a specific policy.
    
    Args:
        policy_id: Policy ID
        entity_type: Type of entity
        entity_id: Entity ID
        context: Additional context
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Compliance check result
    """
    engine = get_governance_engine()
    
    try:
        result = await engine.check_compliance(
            entity_type=entity_type,
            entity_id=entity_id,
            context=context
        )
        
        logger.info(
            "Policy compliance checked via API",
            policy_id=policy_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=str(current_user.id)
        )
        
        return result
        
    except GovernanceError as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{policy_id}/history", response_model=List[Dict[str, Any]])
async def get_policy_history(
    policy_id: str,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get policy enforcement history.
    
    Args:
        policy_id: Policy ID
        limit: Maximum number of results
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Policy history
    """
    # In real implementation, would query from audit logs
    # For now, return mock data
    mock_history = [
        {
            "enforcement_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "context": {"user": "system"},
            "result": "enforced",
            "actions_taken": ["log", "notify"]
        }
    ]
    
    return mock_history[:limit]
