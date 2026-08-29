"""
BaseLayer Output Generator

Output generation and management system
for the Output Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.output_engine import (
    OutputTemplate, GeneratedOutput,
    OutputStatus
)
from ..models.user import User
from .exceptions import GenerationError

logger = get_logger(__name__)


class OutputGenerator:
    """
    Output generation and management system.
    
    Handles output creation, versioning, and lifecycle management
    with comprehensive tracking and validation.
    """
    
    def __init__(self):
        self.generation_queue: asyncio.Queue = asyncio.Queue()
        self.generation_active: bool = False
        self.max_concurrent_generations: int = 3  # Optimized for i5-2400
        self.generation_timeout: int = 300  # 5 minutes
        self.max_output_size: int = 50 * 1024 * 1024  # 50MB
        self.output_retention_days: int = 30
        
        # Generation metrics
        self.generation_metrics = {
            "total_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "average_generation_time": 0.0,
            "queue_size": 0
        }
    
    async def start_generation_worker(self) -> None:
        """Start the background generation worker."""
        if self.generation_active:
            return
        
        self.generation_active = True
        asyncio.create_task(self._generation_worker_loop())
        
        logger.info("Output generation worker started")
    
    async def stop_generation_worker(self) -> None:
        """Stop the generation worker."""
        self.generation_active = False
        logger.info("Output generation worker stopped")
    
    async def create_output(
        self,
        template: OutputTemplate,
        rendered_content: str,
        formatted_output: bytes,
        output_format: str,
        data: Dict[str, Any],
        options: Dict[str, Any],
        metadata: Dict[str, Any],
        created_by: Optional[uuid.UUID] = None
    ) -> GeneratedOutput:
        """
        Create a new generated output.
        
        Args:
            template: Template used for generation
            rendered_content: Rendered template content
            formatted_output: Formatted output bytes
            output_format: Output format
            data: Data used for generation
            options: Generation options
            metadata: Additional metadata
            created_by: User who created the output
            
        Returns:
            GeneratedOutput: Created output
            
        Raises:
            GenerationError: If creation fails
        """
        try:
            # Validate inputs
            await self._validate_output_inputs(
                template, rendered_content, formatted_output, output_format
            )
            
            async with db_session_context() as session:
                # Create output record
                output = GeneratedOutput(
                    template_id=template.id,
                    rendered_content=rendered_content,
                    formatted_output=formatted_output,
                    output_format=output_format,
                    data=data,
                    options=options,
                    metadata=metadata,
                    status=OutputStatus.COMPLETED,
                    generation_time=0.0,  # Will be updated by caller
                    created_by=created_by
                )
                
                session.add(output)
                await session.commit()
                await session.refresh(output)
                
                logger.info(
                    "Output created successfully",
                    output_id=str(output.id),
                    template_id=str(template.id),
                    format=output_format
                )
                
                return output
                
        except Exception as e:
            raise GenerationError(f"Failed to create output: {str(e)}") from e
    
    async def schedule_generation(
        self,
        template_id: str,
        data: Dict[str, Any],
        output_format: str = "html",
        options: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> GeneratedOutput:
        """
        Schedule output generation for background processing.
        
        Args:
            template_id: Template ID
            data: Data for generation
            output_format: Output format
            options: Generation options
            priority: Generation priority
            scheduled_at: When to generate
            metadata: Additional metadata
            created_by: User who scheduled the generation
            
        Returns:
            GeneratedOutput: Scheduled output
            
        Raises:
            GenerationError: If scheduling fails
        """
        try:
            async with db_session_context() as session:
                # Create pending output record
                output = GeneratedOutput(
                    template_id=uuid.UUID(template_id),
                    data=data,
                    options=options or {},
                    output_format=output_format,
                    metadata=metadata or {},
                    status=OutputStatus.PENDING,
                    priority=priority,
                    scheduled_at=scheduled_at or datetime.utcnow(),
                    created_by=created_by
                )
                
                session.add(output)
                await session.commit()
                await session.refresh(output)
                
                # Add to generation queue
                await self.generation_queue.put(output)
                
                logger.info(
                    "Output generation scheduled",
                    output_id=str(output.id),
                    template_id=template_id,
                    format=output_format,
                    priority=priority
                )
                
                return output
                
        except Exception as e:
            raise GenerationError(f"Failed to schedule generation: {str(e)}") from e
    
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
        async with db_session_context() as session:
            result = await session.execute(
                select(GeneratedOutput).where(
                    GeneratedOutput.id == uuid.UUID(output_id),
                    GeneratedOutput.deleted_at.is_(None)
                )
            )
            output = result.scalar_one_or_none()
            
            if output and not include_content:
                # Return output without large content
                output_data = output.to_dict()
                output_data["rendered_content"] = "[Content not requested]"
                output_data["formatted_output"] = "[Content not requested]"
                return output_data
            
            return output
    
    async def list_outputs(
        self,
        template_id: Optional[str] = None,
        status: Optional[OutputStatus] = None,
        format_type: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[GeneratedOutput]:
        """
        List generated outputs with optional filtering.
        
        Args:
            template_id: Filter by template ID
            status: Filter by status
            format_type: Filter by format type
            created_by: Filter by creator
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[GeneratedOutput]: List of outputs
        """
        async with db_session_context() as session:
            query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
            
            if template_id:
                query = query.where(GeneratedOutput.template_id == uuid.UUID(template_id))
            
            if status:
                query = query.where(GeneratedOutput.status == status)
            
            if format_type:
                query = query.where(GeneratedOutput.output_format == format_type)
            
            if created_by:
                query = query.where(GeneratedOutput.created_by == created_by)
            
            query = query.order_by(GeneratedOutput.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            outputs = result.scalars().all()
            
            return list(outputs)
    
    async def update_output_status(
        self,
        output_id: str,
        status: OutputStatus,
        error_message: Optional[str] = None,
        generation_time: Optional[float] = None
    ) -> bool:
        """
        Update output status.
        
        Args:
            output_id: Output ID
            status: New status
            error_message: Error message if failed
            generation_time: Generation time
            
        Returns:
            bool: True if updated successfully
        """
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(GeneratedOutput).where(
                        GeneratedOutput.id == uuid.UUID(output_id),
                        GeneratedOutput.deleted_at.is_(None)
                    )
                )
                output = result.scalar_one_or_none()
                
                if not output:
                    return False
                
                output.status = status
                output.updated_at = datetime.utcnow()
                
                if error_message:
                    output.error_message = error_message
                
                if generation_time is not None:
                    output.generation_time = generation_time
                
                session.add(output)
                await session.commit()
                
                logger.debug(
                    "Output status updated",
                    output_id=output_id,
                    status=status.value
                )
                
                return True
                
        except Exception as e:
            logger.error(
                "Failed to update output status",
                output_id=output_id,
                error=str(e)
            )
            return False
    
    async def delete_output(
        self,
        output_id: str,
        deleted_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Delete a generated output (soft delete).
        
        Args:
            output_id: Output ID
            deleted_by: User who deleted the output
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(GeneratedOutput).where(
                        GeneratedOutput.id == uuid.UUID(output_id),
                        GeneratedOutput.deleted_at.is_(None)
                    )
                )
                output = result.scalar_one_or_none()
                
                if not output:
                    return False
                
                output.soft_delete(deleted_by)
                session.add(output)
                await session.commit()
                
                logger.info(
                    "Output deleted",
                    output_id=output_id,
                    user_id=str(deleted_by) if deleted_by else None
                )
                
                return True
                
        except Exception as e:
            logger.error(
                "Failed to delete output",
                output_id=output_id,
                error=str(e)
            )
            return False
    
    async def cleanup_old_outputs(self, max_age_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Clean up old outputs.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Dict[str, Any]: Cleanup results
        """
        max_age_days = max_age_days or self.output_retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(GeneratedOutput).where(
                        GeneratedOutput.created_at < cutoff_date,
                        GeneratedOutput.deleted_at.is_(None)
                    )
                )
                old_outputs = result.scalars().all()
                
                cleaned_count = 0
                for output in old_outputs:
                    output.soft_delete()
                    session.add(output)
                    cleaned_count += 1
                
                await session.commit()
                
                logger.info(
                    "Old outputs cleaned up",
                    count=cleaned_count,
                    max_age_days=max_age_days
                )
                
                return {
                    "cleaned_count": cleaned_count,
                    "max_age_days": max_age_days,
                    "cutoff_date": cutoff_date.isoformat()
                }
                
        except Exception as e:
            logger.error(
                "Failed to cleanup old outputs",
                error=str(e)
            )
            return {"error": str(e)}
    
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
        async with db_session_context() as session:
            query = select(GeneratedOutput).where(GeneratedOutput.deleted_at.is_(None))
            
            if period_start:
                query = query.where(GeneratedOutput.created_at >= period_start)
            
            if period_end:
                query = query.where(GeneratedOutput.created_at <= period_end)
            
            result = await session.execute(query)
            outputs = result.scalars().all()
            
            # Calculate statistics
            total_outputs = len(outputs)
            completed_outputs = len([o for o in outputs if o.status == OutputStatus.COMPLETED])
            failed_outputs = len([o for o in outputs if o.status == OutputStatus.FAILED])
            pending_outputs = len([o for o in outputs if o.status == OutputStatus.PENDING])
            
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
                "completed_outputs": completed_outputs,
                "failed_outputs": failed_outputs,
                "pending_outputs": pending_outputs,
                "success_rate": (completed_outputs / total_outputs * 100) if total_outputs > 0 else 0,
                "format_distribution": format_counts,
                "average_generation_time": avg_generation_time,
                "generator_metrics": self.generation_metrics
            }
            
            return statistics
    
    async def _generation_worker_loop(self) -> None:
        """Main generation worker loop."""
        while self.generation_active:
            try:
                # Get next generation task
                output = await asyncio.wait_for(
                    self.generation_queue.get(),
                    timeout=60.0
                )
                
                await self._process_generation_task(output)
                
            except asyncio.TimeoutError:
                # No generation tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Generation worker loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_generation_task(self, output: GeneratedOutput) -> None:
        """Process a generation task."""
        try:
            # Update status to processing
            await self.update_output_status(str(output.id), OutputStatus.PROCESSING)
            
            # Get template
            async with db_session_context() as session:
                result = await session.execute(
                    select(OutputTemplate).where(
                        OutputTemplate.id == output.template_id,
                        OutputTemplate.deleted_at.is_(None)
                    )
                )
                template = result.scalar_one_or_none()
                
                if not template:
                    await self.update_output_status(
                        str(output.id),
                        OutputStatus.FAILED,
                        "Template not found"
                    )
                    return
            
            # Render template (would use renderer in real implementation)
            rendered_content = f"Rendered content for template {template.name}"
            
            # Format output (would use formatter in real implementation)
            formatted_output = rendered_content.encode('utf-8')
            
            # Update output with generated content
            output.rendered_content = rendered_content
            output.formatted_output = formatted_output
            output.status = OutputStatus.COMPLETED
            output.completed_at = datetime.utcnow()
            output.generation_time = 1.0  # Simulated
            
            async with db_session_context() as session:
                session.add(output)
                await session.commit()
            
            logger.info(
                "Output generation completed",
                output_id=str(output.id),
                template_id=str(template.id)
            )
            
        except Exception as e:
            logger.error(
                "Output generation failed",
                output_id=str(output.id),
                error=str(e)
            )
            
            await self.update_output_status(
                str(output.id),
                OutputStatus.FAILED,
                str(e)
            )
    
    async def _validate_output_inputs(
        self,
        template: OutputTemplate,
        rendered_content: str,
        formatted_output: bytes,
        output_format: str
    ) -> None:
        """Validate output generation inputs."""
        if not template:
            raise GenerationError("Template is required")
        
        if not rendered_content or not rendered_content.strip():
            raise GenerationError("Rendered content is empty")
        
        if not formatted_output:
            raise GenerationError("Formatted output is empty")
        
        if len(formatted_output) > self.max_output_size:
            raise GenerationError(f"Formatted output too large: {len(formatted_output)} bytes")
        
        if not output_format:
            raise GenerationError("Output format is required")
    
    def get_generator_stats(self) -> Dict[str, Any]:
        """Get generator statistics."""
        return {
            "generation_active": self.generation_active,
            "queue_size": self.generation_queue.qsize(),
            "max_concurrent_generations": self.max_concurrent_generations,
            "generation_timeout": self.generation_timeout,
            "max_output_size": self.max_output_size,
            "output_retention_days": self.output_retention_days,
            "generation_metrics": self.generation_metrics
        }
