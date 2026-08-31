"""
BaseLayer Output Engine API - Templates

REST API endpoints for template management.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ...core.database import db_session_context
from ...models.output_engine import (
    OutputTemplate, TemplateType, OutputType, OutputFormat
)
from ...models.user import User
from ...core.auth import get_current_user
from ..engine import OutputEngine
from ..exceptions import (
    OutputEngineError,
    TemplateNotFoundError,
    ValidationError
)

logger = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["Templates"])

# Global instance (will be injected in startup)
output_engine: OutputEngine = None


def get_output_engine() -> OutputEngine:
    """Get output engine instance."""
    global output_engine
    if not output_engine:
        raise HTTPException(status_code=500, detail="Output engine not initialized")
    return output_engine


@router.get("/", response_model=List[Dict[str, Any]])
async def list_templates(
    template_type: Optional[TemplateType] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    List templates with optional filtering.
    
    Args:
        template_type: Filter by template type
        status: Filter by status
        tags: Filter by tags
        limit: Maximum number of results
        offset: Pagination offset
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: List of templates
    """
    engine = get_output_engine()
    
    templates = await engine.list_templates(
        template_type=template_type,
        status=status,
        tags=tags,
        limit=limit,
        offset=offset
    )
    
    return [template.to_dict() for template in templates]


@router.get("/types", response_model=List[Dict[str, Any]])
async def get_template_types(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get available template types.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[Dict[str, Any]]: Available template types
    """
    types = []
    for template_type in TemplateType:
        types.append({
            "value": template_type.value,
            "name": template_type.value.replace("_", " ").title(),
            "description": f"{template_type.value.replace('_', ' ').title()} template"
        })
    
    return types


@router.get("/statistics", response_model=Dict[str, Any])
async def get_template_statistics(
    period_start: Optional[datetime] = Query(None),
    period_end: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get template statistics.
    
    Args:
        period_start: Start of period
        period_end: End of period
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Template statistics
    """
    try:
        async with db_session_context() as session:
            # Get template counts by type (no separate template_type column
            # - output_type is the real, equivalent field)
            result = await session.execute(
                select(
                    OutputTemplate.output_type,
                    func.count(OutputTemplate.id)
                ).where(
                    OutputTemplate.deleted_at.is_(None)
                ).group_by(OutputTemplate.output_type)
            )
            type_counts = dict(result.all())

            # Get template counts by status (no status column - is_active
            # is the real active/inactive toggle)
            result = await session.execute(
                select(
                    OutputTemplate.is_active,
                    func.count(OutputTemplate.id)
                ).where(
                    OutputTemplate.deleted_at.is_(None)
                ).group_by(OutputTemplate.is_active)
            )
            status_counts = {
                ("active" if is_active else "inactive"): count
                for is_active, count in result.all()
            }
            
            # Get total templates
            result = await session.execute(
                select(func.count(OutputTemplate.id)).where(OutputTemplate.deleted_at.is_(None))
            )
            total_templates = result.scalar() or 0
            
            statistics = {
                "total_templates": total_templates,
                "by_type": type_counts,
                "by_status": status_counts,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return statistics
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=Dict[str, Any])
async def get_template(
    template_id: str,
    include_content: bool = Query(True),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific template.
    
    Args:
        template_id: Template ID
        include_content: Whether to include content
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Template details
    """
    engine = get_output_engine()
    
    template = await engine.get_template(template_id, include_content=include_content)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template.to_dict()


@router.post("/", response_model=Dict[str, Any])
async def create_template(
    template_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new template.
    
    Args:
        template_data: Template data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Created template
    """
    engine = get_output_engine()
    
    try:
        template = await engine.create_template(
            name=template_data["name"],
            content=template_data["content"],
            template_type=TemplateType(template_data["template_type"]),
            output_format=OutputFormat(template_data["output_format"]) if "output_format" in template_data else None,
            description=template_data.get("description"),
            variables=template_data.get("variables"),
            tags=template_data.get("tags"),
            engine=template_data.get("engine", "jinja2"),
            created_by=current_user.id
        )
        
        logger.info(
            "Template created via API",
            template_id=str(template.id),
            name=template.name,
            user_id=str(current_user.id)
        )
        
        return template.to_dict()
        
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OutputEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=Dict[str, Any])
async def update_template(
    template_id: str,
    template_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update a template.
    
    Args:
        template_id: Template ID
        template_data: Updated template data
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Updated template
    """
    engine = get_output_engine()
    
    try:
        template = await engine.update_template(
            template_id=template_id,
            updates=template_data,
            updated_by=current_user.id
        )
        
        logger.info(
            "Template updated via API",
            template_id=template_id,
            user_id=str(current_user.id)
        )
        
        return template.to_dict()
        
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OutputEngineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", response_model=Dict[str, Any])
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a template.
    
    Args:
        template_id: Template ID
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    engine = get_output_engine()
    
    success = await engine.delete_template(template_id, deleted_by=current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    logger.info(
        "Template deleted via API",
        template_id=template_id,
        user_id=str(current_user.id)
    )
    
    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/validate", response_model=Dict[str, Any])
async def validate_template(
    template_id: str,
    engine: str = Query("jinja2"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Validate a template.
    
    Args:
        template_id: Template ID
        engine: Template engine to use for validation
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Validation results
    """
    engine_instance = get_output_engine()
    
    template = await engine_instance.get_template(template_id, include_content=True)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        validation_result = await engine_instance.renderer.validate_template(template, engine)
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/{template_id}/preview", response_model=Dict[str, Any])
async def preview_template(
    template_id: str,
    preview_data: Dict[str, Any],
    engine: str = Query("jinja2"),
    output_format: str = Query("html"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Preview template rendering.
    
    Args:
        template_id: Template ID
        preview_data: Data for preview
        engine: Template engine to use
        output_format: Output format for preview
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Preview result
    """
    engine_instance = get_output_engine()
    
    template = await engine_instance.get_template(template_id, include_content=True)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        # Render template
        rendered_content = await engine_instance.renderer.render_template(
            template=template,
            data=preview_data,
            engine=engine
        )
        
        # Format output
        formatted_output = await engine_instance.formatter.format_output(
            content=rendered_content,
            format_type=output_format
        )
        
        return {
            "template_id": template_id,
            "rendered_content": rendered_content,
            "formatted_output": formatted_output.decode('utf-8'),
            "format": output_format,
            "engine": engine
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")