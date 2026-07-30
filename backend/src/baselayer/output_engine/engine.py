"""
BaseLayer Output Engine

Core output generation and management system
for the Output Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select, func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.output_engine import (
    OutputTemplate, GeneratedOutput, DeliveryLog,
    TemplateType, OutputStatus, DeliveryStatus
)
from ..models.user import User
from .renderer import OutputRenderer
from .formatter import OutputFormatter
from .generator import OutputGenerator
from .delivery import OutputDelivery
from .tracker import OutputTracker
from .exceptions import (
    OutputEngineError,
    TemplateNotFoundError,
    RenderingError,
    FormattingError,
    GenerationError
)

logger = get_logger(__name__)


class OutputEngine:
    """
    Core output generation and management engine.
    
    Handles template management, output generation,
    formatting, and delivery with comprehensive tracking.
    """
    
    def __init__(self):
        self.template_cache: Dict[str, Dict[str, Any]] = {}
        self.output_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 300  # 5 minutes
        self.max_output_size: int = 50 * 1024 * 1024  # 50MB
        
        # Component managers
        self.renderer = OutputRenderer()
        self.formatter = OutputFormatter()
        self.generator = OutputGenerator()
        self.delivery = OutputDelivery()
        self.tracker = OutputTracker()
        
        # Configuration
        self.default_template_engine = "jinja2"
        self.supported_formats = ["html", "pdf", "json", "xml", "csv", "txt"]
        self.delivery_methods = ["email", "webhook", "api", "file", "storage"]
        self.max_concurrent_generations: int = 3  # Optimized for i5-2400
        
        # Performance metrics
        self.generation_metrics = {
            "total_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_generation_time": 0.0
        }
    
    async def create_template(
        self,
        name: str,
        content: str,
        template_type: TemplateType,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        engine: str = "jinja2",
        created_by: Optional[uuid.UUID] = None
    ) -> OutputTemplate:
        """
        Create a new output template.
        
        Args:
            name: Template name
            content: Template content
            template_type: Type of template
            description: Template description
            variables: Template variables
            tags: Template tags
            engine: Template engine
            created_by: User who created the template
            
        Returns:
            OutputTemplate: Created template
            
        Raises:
            OutputEngineError: If creation fails
        """
        try:
            # Validate template content
            await self._validate_template_content(content, engine)
            
            # Extract variables from content if not provided
            if variables is None:
                variables = await self._extract_template_variables(content, engine)
            
            async with get_db_session() as session:
                template = OutputTemplate(
                    name=name,
                    content=content,
                    template_type=template_type,
                    description=description,
                    variables=variables or [],
                    tags=tags or [],
                    engine=engine,
                    status="active",
                    created_by=created_by
                )
                
                session.add(template)
                await session.commit()
                await session.refresh(template)
                
                # Cache template
                self._cache_template(template)
                
                logger.info(
                    "Output template created",
                    template_id=str(template.id),
                    name=name,
                    template_type=template_type.value
                )
                
                return template
                
        except Exception as e:
            raise OutputEngineError(f"Failed to create template: {str(e)}") from e
    
    async def generate_output(
        self,
        template_id: str,
        data: Dict[str, Any],
        output_format: str = "html",
        options: Optional[Dict[str, Any]] = None,
        delivery_methods: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> GeneratedOutput:
        """
        Generate output from a template.
        
        Args:
            template_id: Template ID
            data: Data for template rendering
            output_format: Output format
            options: Generation options
            delivery_methods: Delivery methods
            metadata: Additional metadata
            created_by: User who created the output
            
        Returns:
            GeneratedOutput: Generated output
            
        Raises:
            OutputEngineError: If generation fails
        """
        try:
            # Validate inputs
            if output_format not in self.supported_formats:
                raise OutputEngineError(f"Unsupported format: {output_format}")
            
            # Get template
            template = await self._get_template(template_id)
            if not template:
                raise TemplateNotFoundError(f"Template not found: {template_id}")
            
            # Render template
            start_time = datetime.utcnow()
            rendered_content = await self.renderer.render_template(
                template=template,
                data=data,
                engine=template.engine
            )
            
            # Format output
            formatted_output = await self.formatter.format_output(
                content=rendered_content,
                format_type=output_format,
                options=options or {}
            )
            
            # Generate output
            output = await self.generator.create_output(
                template=template,
                rendered_content=rendered_content,
                formatted_output=formatted_output,
                output_format=output_format,
                data=data,
                options=options or {},
                metadata=metadata or {},
                created_by=created_by
            )
            
            # Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update metrics
            self._update_generation_metrics(True, generation_time)
            
            # Cache output
            self._cache_output(output)
            
            # Track generation
            await self.tracker.track_generation(output, generation_time)
            
            # Schedule delivery if requested
            if delivery_methods:
                await self._schedule_delivery(output, delivery_methods)
            
            logger.info(
                "Output generated successfully",
                output_id=str(output.id),
                template_id=template_id,
                format=output_format,
                generation_time=generation_time
            )
            
            return output
            
        except Exception as e:
            self._update_generation_metrics(False, 0)
            
            logger.error(
                "Output generation failed",
                template_id=template_id,
                error=str(e)
            )
            
            raise OutputEngineError(f"Failed to generate output: {str(e)}") from e
    
    async def get_template(
        self,
        template_id: str,
        include_content: bool = True
    ) -> Optional[OutputTemplate]:
        """
        Get a template by ID.
        
        Args:
            template_id: Template ID
            include_content: Whether to include content
            
        Returns:
            OutputTemplate: Template or None
        """
        # Check cache first
        cache_key = f"template_{template_id}"
        if cache_key in self.template_cache:
            cached_template = self.template_cache[cache_key]
            cache_age = datetime.utcnow() - cached_template["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                if not include_content:
                    # Return template without content
                    template_data = cached_template["template"].to_dict()
                    template_data["content"] = "[Content not requested]"
                    return template_data
                return cached_template["template"]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(OutputTemplate).where(
                    OutputTemplate.id == uuid.UUID(template_id),
                    OutputTemplate.deleted_at.is_(None)
                )
            )
            template = result.scalar_one_or_none()
            
            if template:
                # Cache template
                self._cache_template(template)
            
            return template
    
    async def list_templates(
        self,
        template_type: Optional[TemplateType] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[OutputTemplate]:
        """
        List templates with optional filtering.
        
        Args:
            template_type: Filter by template type
            status: Filter by status
            tags: Filter by tags
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[OutputTemplate]: List of templates
        """
        async with get_db_session() as session:
            query = select(OutputTemplate).where(OutputTemplate.deleted_at.is_(None))
            
            if template_type:
                query = query.where(OutputTemplate.template_type == template_type)
            
            if status:
                query = query.where(OutputTemplate.status == status)
            
            if tags:
                # Simple tag filtering - in real implementation would use proper tag relationships
                for tag in tags:
                    query = query.where(OutputTemplate.tags.contains([tag]))
            
            query = query.order_by(OutputTemplate.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            templates = result.scalars().all()
            
            return list(templates)
    
    async def update_template(
        self,
        template_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[uuid.UUID] = None
    ) -> OutputTemplate:
        """
        Update a template.
        
        Args:
            template_id: Template ID
            updates: Fields to update
            updated_by: User who updated the template
            
        Returns:
            OutputTemplate: Updated template
            
        Raises:
            TemplateNotFoundError: If template not found
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(OutputTemplate).where(
                    OutputTemplate.id == uuid.UUID(template_id),
                    OutputTemplate.deleted_at.is_(None)
                )
            )
            template = result.scalar_one_or_none()
            
            if not template:
                raise TemplateNotFoundError(f"Template not found: {template_id}")
            
            # Update fields
            if "name" in updates:
                template.name = updates["name"]
            
            if "content" in updates:
                template.content = updates["content"]
                # Re-extract variables
                template.variables = await self._extract_template_variables(
                    updates["content"], template.engine
                )
            
            if "description" in updates:
                template.description = updates["description"]
            
            if "variables" in updates:
                template.variables = updates["variables"]
            
            if "tags" in updates:
                template.tags = updates["tags"]
            
            if "status" in updates:
                template.status = updates["status"]
            
            template.updated_by = updated_by
            template.updated_at = datetime.utcnow()
            
            session.add(template)
            await session.commit()
            await session.refresh(template)
            
            # Update cache
            self._cache_template(template)
            
            logger.info(
                "Template updated",
                template_id=template_id,
                user_id=str(updated_by) if updated_by else None
            )
            
            return template
    
    async def delete_template(
        self,
        template_id: str,
        deleted_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Delete a template (soft delete).
        
        Args:
            template_id: Template ID
            deleted_by: User who deleted the template
            
        Returns:
            bool: True if deleted successfully
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(OutputTemplate).where(
                    OutputTemplate.id == uuid.UUID(template_id),
                    OutputTemplate.deleted_at.is_(None)
                )
            )
            template = result.scalar_one_or_none()
            
            if not template:
                return False
            
            template.soft_delete(deleted_by)
            session.add(template)
            await session.commit()
            
            # Remove from cache
            cache_key = f"template_{template_id}"
            self.template_cache.pop(cache_key, None)
            
            logger.info(
                "Template deleted",
                template_id=template_id,
                user_id=str(deleted_by) if deleted_by else None
            )
            
            return True
    
    async def get_output(
        self,
        output_id: str,
        include_content: bool = True
    ) -> Optional[GeneratedOutput]:
        """
        Get a generated output by ID.
        
        Args:
            output_id: Output ID
            include_content: Whether to include content
            
        Returns:
            GeneratedOutput: Generated output or None
        """
        # Check cache first
        cache_key = f"output_{output_id}"
        if cache_key in self.output_cache:
            cached_output = self.output_cache[cache_key]
            cache_age = datetime.utcnow() - cached_output["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                if not include_content:
                    output_data = cached_output["output"].to_dict()
                    output_data["formatted_output"] = "[Content not requested]"
                    return output_data
                return cached_output["output"]
        
        # Load from database
        async with get_db_session() as session:
            result = await session.execute(
                select(GeneratedOutput).where(
                    GeneratedOutput.id == uuid.UUID(output_id),
                    GeneratedOutput.deleted_at.is_(None)
                )
            )
            output = result.scalar_one_or_none()
            
            if output:
                # Cache output
                self._cache_output(output)
            
            return output
    
    async def list_outputs(
        self,
        template_id: Optional[str] = None,
        status: Optional[OutputStatus] = None,
        format_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[GeneratedOutput]:
        """
        List generated outputs with optional filtering.
        
        Args:
            template_id: Filter by template ID
            status: Filter by status
            format_type: Filter by format type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[GeneratedOutput]: List of outputs
        """
        async with get_db_session() as session:
            query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
            
            if template_id:
                query = query.where(GeneratedOutput.template_id == uuid.UUID(template_id))
            
            if status:
                query = query.where(GeneratedOutput.status == status)
            
            if format_type:
                query = query.where(GeneratedOutput.output_format == format_type)
            
            query = query.order_by(GeneratedOutput.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            outputs = result.scalars().all()
            
            return list(outputs)
    
    async def get_generation_statistics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get generation statistics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Generation statistics
        """
        async with get_db_session() as session:
            query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
            
            if period_start:
                query = query.where(GeneratedOutput.created_at >= period_start)
            
            if period_end:
                query = query.where(GeneratedOutput.created_at <= period_end)
            
            result = await session.execute(query)
            outputs = result.scalars().all()
            
            # Calculate statistics
            total_outputs = len(outputs)
            successful_outputs = len([o for o in outputs if o.status == OutputStatus.COMPLETED])
            failed_outputs = len([o for o in outputs if o.status == OutputStatus.FAILED])
            
            # Get format distribution
            format_counts = {}
            for output in outputs:
                format_type = output.output_format
                format_counts[format_type] = format_counts.get(format_type, 0) + 1
            
            # Get average generation time
            generation_times = [o.generation_time for o in outputs if o.generation_time]
            avg_generation_time = sum(generation_times) / len(generation_times) if generation_times else 0
            
            statistics = {
                "period": {
                    "start": period_start.isoformat() if period_start else None,
                    "end": period_end.isoformat() if period_end else None
                },
                "total_outputs": total_outputs,
                "successful_outputs": successful_outputs,
                "failed_outputs": failed_outputs,
                "success_rate": (successful_outputs / total_outputs * 100) if total_outputs > 0 else 0,
                "format_distribution": format_counts,
                "average_generation_time": avg_generation_time,
                "engine_metrics": self.generation_metrics
            }
            
            return statistics
    
    async def _validate_template_content(self, content: str, engine: str) -> None:
        """Validate template content."""
        try:
            if engine == "jinja2":
                from jinja2 import Environment, meta, TemplateSyntaxError
                env = Environment()
                try:
                    env.parse(content)
                except TemplateSyntaxError as e:
                    raise RenderingError(f"Template syntax error: {str(e)}", rendering_engine=engine)
            else:
                # Add validation for other engines as needed
                pass
                
        except Exception as e:
            raise RenderingError(f"Template validation failed: {str(e)}", rendering_engine=engine) from e
    
    async def _extract_template_variables(self, content: str, engine: str) -> List[str]:
        """Extract variables from template content."""
        try:
            if engine == "jinja2":
                from jinja2 import Environment, meta
                env = Environment()
                ast = env.parse(content)
                variables = meta.find_undeclared_variables(ast)
                return list(variables)
            else:
                # Add extraction for other engines as needed
                return []
                
        except Exception as e:
            logger.warning(
                "Failed to extract template variables",
                engine=engine,
                error=str(e)
            )
            return []
    
    async def _get_template(self, template_id: str) -> Optional[OutputTemplate]:
        """Get template from cache or database."""
        return await self.get_template(template_id, include_content=True)
    
    def _cache_template(self, template: OutputTemplate) -> None:
        """Cache a template."""
        cache_key = f"template_{str(template.id)}"
        self.template_cache[cache_key] = {
            "template": template,
            "cached_at": datetime.utcnow()
        }
    
    def _cache_output(self, output: GeneratedOutput) -> None:
        """Cache a generated output."""
        cache_key = f"output_{str(output.id)}"
        self.output_cache[cache_key] = {
            "output": output,
            "cached_at": datetime.utcnow()
        }
    
    def _update_generation_metrics(self, success: bool, generation_time: float) -> None:
        """Update generation metrics."""
        self.generation_metrics["total_generated"] += 1
        
        if success:
            self.generation_metrics["successful_generations"] += 1
        else:
            self.generation_metrics["failed_generations"] += 1
        
        # Update average generation time
        successful = self.generation_metrics["successful_generations"]
        if successful > 0:
            current_avg = self.generation_metrics["average_generation_time"]
            self.generation_metrics["average_generation_time"] = (
                (current_avg * (successful - 1) + generation_time) / successful
            )
    
    async def _schedule_delivery(self, output: GeneratedOutput, delivery_methods: List[str]) -> None:
        """Schedule output delivery."""
        for method in delivery_methods:
            if method not in self.delivery_methods:
                logger.warning(
                    "Unknown delivery method",
                    method=method,
                    output_id=str(output.id)
                )
                continue
            
            try:
                await self.delivery.schedule_delivery(output, method)
            except Exception as e:
                logger.error(
                    "Failed to schedule delivery",
                    output_id=str(output.id),
                    method=method,
                    error=str(e)
                )
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "template_cache_size": len(self.template_cache),
            "output_cache_size": len(self.output_cache),
            "cache_ttl": self.cache_ttl,
            "max_output_size": self.max_output_size,
            "supported_formats": self.supported_formats,
            "delivery_methods": self.delivery_methods,
            "max_concurrent_generations": self.max_concurrent_generations,
            "generation_metrics": self.generation_metrics
        }
