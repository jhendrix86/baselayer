"""
BaseLayer Multi-Agent Orchestration API - Agents

REST API endpoints for agent lifecycle management.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.database import db_session_context
from ...models.agents import (
    Agent, AgentTask,
    AgentType, AgentStatus
)
from ...models.user import User
from ...core.auth import get_current_user
from ..orchestrator import AgentOrchestrator
from ..lifecycle import AgentLifecycleManager
from ..exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentLifecycleError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])

# Global instances (will be injected in startup)
agent_orchestrator: AgentOrchestrator = None
lifecycle_manager: AgentLifecycleManager = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get agent orchestrator instance."""
    global agent_orchestrator
    if not agent_orchestrator:
        raise HTTPException(status_code=500, detail="Agent orchestrator not initialized")
    return agent_orchestrator


def get_lifecycle_manager() -> AgentLifecycleManager:
    """Get lifecycle manager instance."""
    global lifecycle_manager
    if not lifecycle_manager:
        raise HTTPException(status_code=500, detail="Lifecycle manager not initialized")
    return lifecycle_manager


@router.get("/", response_model=List[Dict[str, Any]])
async def list_agents(
    status: Optional[AgentStatus] = Query(None),
    agent_type: Optional[AgentType] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List agents with optional filtering.
    
    Args:
        status: Filter by status
        agent_type: Filter by agent type
        limit: Maximum number of results
        offset: Pagination offset
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of agents
    """
    lifecycle = get_lifecycle_manager()
    
    agents = await lifecycle.list_agents(
        status=status,
        agent_type=agent_type,
        limit=limit,
        offset=offset
    )
    
    return [agent.to_dict() for agent in agents]


@router.get("/types", response_model=List[Dict[str, Any]])
async def get_agent_types(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get available agent types.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Available agent types
    """
    types = []
    for agent_type in AgentType:
        types.append({
            "value": agent_type.value,
            "name": agent_type.value.replace("_", " ").title(),
            "description": f"{agent_type.value.replace('_', ' ').title()} agent"
        })
    
    return types


@router.get("/statistics", response_model=Dict[str, Any])
async def get_agent_statistics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get agent statistics.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Agent statistics
    """
    try:
        async with db_session_context() as session:
            # Get agent counts by status
            result = await session.execute(
                select(
                    Agent.status,
                    func.count(Agent.id)
                ).where(
                    Agent.deleted_at.is_(None)
                ).group_by(Agent.status)
            )
            status_counts = dict(result.all())
            
            # Get agent counts by type
            result = await session.execute(
                select(
                    Agent.agent_type,
                    func.count(Agent.id)
                ).where(
                    Agent.deleted_at.is_(None)
                ).group_by(Agent.agent_type)
            )
            type_counts = dict(result.all())
            
            # Get total tasks
            result = await session.execute(
                select(func.count(AgentTask.id)).where(AgentTask.deleted_at.is_(None))
            )
            total_tasks = result.scalar() or 0
            
            statistics = {
                "total_agents": sum(status_counts.values()),
                "by_status": status_counts,
                "by_type": type_counts,
                "total_tasks": total_tasks,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return statistics
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=Dict[str, Any])
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific agent.
    
    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Agent details
    """
    try:
        lifecycle = get_lifecycle_manager()
        metrics = await lifecycle.get_agent_metrics(agent_id)
        
        return metrics
        
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict[str, Any])
async def create_agent(
    agent_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new agent.
    
    Args:
        agent_data: Agent data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created agent
    """
    lifecycle = get_lifecycle_manager()
    
    try:
        agent = await lifecycle.create_agent(
            agent_type=AgentType(agent_data["agent_type"]),
            name=agent_data["name"],
            config=agent_data.get("config", {}),
            capabilities=agent_data.get("capabilities", []),
            created_by=current_user.id
        )
        
        logger.info(
            "Agent created via API",
            agent_id=str(agent.id),
            name=agent.name,
            user_id=str(current_user.id)
        )
        
        return agent.to_dict()
        
    except (AgentLifecycleError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/activate", response_model=Dict[str, Any])
async def activate_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Activate an agent.
    
    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Activation result
    """
    lifecycle = get_lifecycle_manager()
    
    try:
        success = await lifecycle.activate_agent(agent_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        logger.info(
            "Agent activated via API",
            agent_id=agent_id,
            user_id=str(current_user.id)
        )
        
        return {"message": "Agent activated successfully"}
        
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentLifecycleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/deactivate", response_model=Dict[str, Any])
async def deactivate_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Deactivate an agent.
    
    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deactivation result
    """
    lifecycle = get_lifecycle_manager()
    
    try:
        success = await lifecycle.deactivate_agent(agent_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        logger.info(
            "Agent deactivated via API",
            agent_id=agent_id,
            user_id=str(current_user.id)
        )
        
        return {"message": "Agent deactivated successfully"}
        
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/restart", response_model=Dict[str, Any])
async def restart_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Restart an agent.
    
    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Restart result
    """
    lifecycle = get_lifecycle_manager()
    
    try:
        success = await lifecycle.restart_agent(agent_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        logger.info(
            "Agent restarted via API",
            agent_id=agent_id,
            user_id=str(current_user.id)
        )
        
        return {"message": "Agent restarted successfully"}
        
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}/config", response_model=Dict[str, Any])
async def update_agent_config(
    agent_id: str,
    config_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update agent configuration.
    
    Args:
        agent_id: Agent ID
        config_data: New configuration
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Update result
    """
    lifecycle = get_lifecycle_manager()
    
    try:
        success = await lifecycle.update_agent_config(agent_id, config_data)
        
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        logger.info(
            "Agent configuration updated via API",
            agent_id=agent_id,
            user_id=str(current_user.id)
        )
        
        return {"message": "Agent configuration updated successfully"}
        
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/health", response_model=Dict[str, Any])
async def get_agent_health(
    agent_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get agent health status.
    
    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Agent health status
    """
    try:
        async with db_session_context() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.id == uuid.UUID(agent_id),
                    Agent.deleted_at.is_(None)
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get health from monitor (would be injected in real implementation)
        from ..monitor import AgentMonitor
        monitor = AgentMonitor()
        health = await monitor.check_agent_health(agent)
        
        return health
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/tasks", response_model=List[Dict[str, Any]])
async def get_agent_tasks(
    agent_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get tasks for a specific agent.
    
    Args:
        agent_id: Agent ID
        status: Filter by task status
        limit: Maximum number of results
        offset: Pagination offset
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of tasks
    """
    try:
        async with db_session_context() as session:
            query = select(AgentTask).where(
                AgentTask.agent_id == uuid.UUID(agent_id),
                AgentTask.deleted_at.is_(None)
            )
            
            if status:
                query = query.where(AgentTask.status == status)
            
            query = query.order_by(AgentTask.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            return [task.to_dict() for task in tasks]
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))