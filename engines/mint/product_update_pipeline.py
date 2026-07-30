"""
MINT Product Update Pipeline

Pipeline for updating existing products
with content regeneration and Gumroad synchronization.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.core.pipeline import Pipeline, PipelineConfig, PipelineStep, PipelineMode, ErrorHandling
from agents.core.context import AgentContext
from agents.core.state import AgentState
from agents.queue.tasks import enqueue_agent_task, enqueue_pipeline_task
from ..agents.product_generator import ProductGenerator
from ..agents.product_packager import ProductPackager
from ..agents.listing_optimizer import ListingOptimizer
from ..agents.gumroad_publisher import GumroadPublisher
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class ProductUpdatePipeline(Pipeline):
    """
    Product update pipeline for MINT engine.
    
    Handles product content updates, regeneration,
    and Gumroad synchronization.
    """
    
    def __init__(
        self,
        db_session=None,
        redis_client=None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize product update pipeline."""
        # Create pipeline configuration
        pipeline_config = PipelineConfig(
            name="product_update",
            description="Product update and regeneration pipeline",
            steps=[
                PipelineStep(
                    name="analyze_existing_product",
                    agent=ProductGenerator,
                    error_handling=ErrorHandling.RETRY,
                    max_retries=2
                ),
                PipelineStep(
                    name="regenerate_sections",
                    agent=ProductGenerator,
                    depends_on=["analyze_existing_product"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=3
                ),
                PipelineStep(
                    name="repackage_product",
                    agent=ProductPackager,
                    depends_on=["regenerate_sections"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=2
                ),
                PipelineStep(
                    name="update_listing",
                    agent=ListingOptimizer,
                    depends_on=["regenerate_sections"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=2
                ),
                PipelineStep(
                    name="sync_to_gumroad",
                    agent=GumroadPublisher,
                    depends_on=["repackage_product", "update_listing"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=3
                )
            ],
            mode=PipelineMode.SEQUENTIAL,
            timeout_seconds=1200,  # 20 minutes
            enable_persistence=True,
            enable_events=True,
            metadata={
                "pipeline_type": "product_update",
                "version": "1.0.0",
                "supports_partial_update": True
            }
        )
        
        # Initialize agents
        agents = {
            "ProductGenerator": ProductGenerator(),
            "ProductPackager": ProductPackager(),
            "ListingOptimizer": ListingOptimizer(),
            "GumroadPublisher": GumroadPublisher()
        }
        
        super().__init__(pipeline_config, agents, db_session, redis_client)
        
        # Update state
        self.update_id: Optional[str] = None
        self.product_data: Dict[str, Any] = {}
        self.update_progress: Dict[str, Any] = {}
    
    async def execute(self, input_data: Dict[str, Any], context: Optional[AgentContext] = None) -> Dict[str, Any]:
        """
        Execute product update pipeline.
        
        Args:
            input_data: Product update request
            context: Optional execution context
            
        Returns:
            Dict containing update results
        """
        try:
            # Initialize update session
            self.update_id = str(uuid.uuid4())
            self.product_data = input_data.copy()
            
            logger.info(
                "Starting product update pipeline",
                update_id=self.update_id,
                product_id=input_data.get("product_id"),
                sections=input_data.get("sections", [])
            )
            
            # Create pipeline context
            pipeline_context = self._create_pipeline_context(input_data, context)
            
            # Execute pipeline steps
            result = await super().execute(input_data, pipeline_context)
            
            # Compile final results
            final_result = self._compile_update_results(result)
            
            logger.info(
                "Product update pipeline completed",
                update_id=self.update_id,
                success=final_result.get("success", False)
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                "Product update pipeline failed",
                update_id=self.update_id,
                error=str(e)
            )
            raise BaseLayerError(f"Pipeline execution failed: {str(e)}") from e
    
    def _create_pipeline_context(self, input_data: Dict[str, Any], parent_context: Optional[AgentContext]) -> AgentContext:
        """Create pipeline execution context."""
        return AgentContext(
            task_id=self.update_id,
            task_type="product_update",
            input_data=input_data,
            memory_interface=parent_context.memory_interface if parent_context else None,
            config=parent_context.config if parent_context else None,
            request_id=parent_context.request_id if parent_context else str(uuid.uuid4()),
            parent_agent_id=parent_context.agent_id if parent_context else None,
            pipeline_id="product_update",
            metadata={
                "update_id": self.update_id,
                "product_id": input_data.get("product_id"),
                "sections_to_update": input_data.get("sections", []),
                "update_type": input_data.get("update_type", "full"),
                "pipeline_version": "1.0.0"
            }
        )
    
    def _compile_update_results(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compile final update results from pipeline results."""
        try:
            step_results = pipeline_result.get("step_results", {})
            
            # Extract results from each step
            analysis_result = step_results.get("analyze_existing_product", {})
            regeneration_result = step_results.get("regenerate_sections", {})
            packaging_result = step_results.get("repackage_product", {})
            listing_result = step_results.get("update_listing", {})
            sync_result = step_results.get("sync_to_gumroad", {})
            
            # Determine overall success
            overall_success = all([
                analysis_result.get("success", False),
                regeneration_result.get("success", False),
                packaging_result.get("success", False),
                listing_result.get("success", False),
                sync_result.get("success", False)
            ])
            
            # Compile product information
            product_info = {
                "update_id": self.update_id,
                "product_id": self.product_data.get("product_id"),
                "title": self.product_data.get("title"),
                "product_type": self.product_data.get("product_type"),
                "updated_sections": self.product_data.get("sections", []),
                "content": regeneration_result.get("result", {}).get("content", ""),
                "assets": packaging_result.get("result", {}).get("assets", {}),
                "listing_copy": listing_result.get("result", {}).get("full_listing", ""),
                "gumroad_info": {
                    "product_id": sync_result.get("result", {}).get("gumroad_product_id"),
                    "url": sync_result.get("result", {}).get("gumroad_url"),
                    "status": sync_result.get("result", {}).get("publishing_status")
                }
            }
            
            # Compile execution summary
            execution_summary = {
                "total_duration_ms": pipeline_result.get("duration_ms", 0),
                "steps_completed": len([r for r in step_results.values() if r.get("success", False)]),
                "total_steps": len(step_results),
                "quality_scores": {
                    "analysis_quality": analysis_result.get("result", {}).get("score", 0.0),
                    "regeneration_quality": regeneration_result.get("result", {}).get("score", 0.0),
                    "packaging_quality": packaging_result.get("result", {}).get("score", 0.0),
                    "listing_quality": listing_result.get("result", {}).get("score", 0.0),
                    "sync_quality": sync_result.get("result", {}).get("score", 0.0)
                },
                "errors": [
                    f"{step}: {step_result.get('error', 'Unknown error')}"
                    for step, step_result in step_results.items()
                    if not step_result.get("success", False)
                ]
            }
            
            # Compile next steps
            next_steps = []
            if overall_success:
                next_steps.extend([
                    "Monitor Gumroad sales and analytics",
                    "Update product metadata if needed",
                    "Create promotional materials for updated content",
                    "Schedule regular content refreshes"
                ])
            else:
                next_steps.extend([
                    "Review and fix failed steps",
                    "Retry product update with corrected inputs",
                    "Validate product requirements",
                    "Check Gumroad API status"
                ])
            
            return {
                "update_id": self.update_id,
                "success": overall_success,
                "product_info": product_info,
                "execution_summary": execution_summary,
                "step_results": step_results,
                "next_steps": next_steps,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Failed to compile update results",
                update_id=self.update_id,
                error=str(e)
            )
            return {
                "update_id": self.update_id,
                "success": False,
                "error": f"Result compilation failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_update_status(self, update_id: str) -> Dict[str, Any]:
        """
        Get status of product update.
        
        Args:
            update_id: Update session ID
            
        Returns:
            Dict containing update status
        """
        try:
            if update_id != self.update_id:
                return {
                    "update_id": update_id,
                    "status": "not_found",
                    "error": "Update session not found"
                }
            
            # Get current pipeline status
            pipeline_status = self.get_status()
            
            # Map pipeline status to update status
            update_status = self._map_pipeline_status_to_update_status(pipeline_status)
            
            # Add update-specific information
            update_status.update({
                "update_id": self.update_id,
                "product_id": self.product_data.get("product_id"),
                "sections_to_update": self.product_data.get("sections", []),
                "current_step": pipeline_status.get("current_step"),
                "progress": self._calculate_progress(pipeline_status)
            })
            
            return update_status
            
        except Exception as e:
            logger.error(
                "Failed to get update status",
                update_id=update_id,
                error=str(e)
            )
            return {
                "update_id": update_id,
                "status": "error",
                "error": str(e)
            }
    
    async def cancel_update(self, update_id: str) -> bool:
        """
        Cancel product update.
        
        Args:
            update_id: Update session ID
            
        Returns:
            True if cancelled successfully
        """
        try:
            if update_id != self.update_id:
                return False
            
            # Cancel pipeline
            cancelled = await self.cancel()
            
            if cancelled:
                logger.info(
                    "Product update cancelled",
                    update_id=self.update_id
                )
            
            return cancelled
            
        except Exception as e:
            logger.error(
                "Failed to cancel update",
                update_id=update_id,
                error=str(e)
            )
            return False
    
    def _map_pipeline_status_to_update_status(self, pipeline_status: Dict[str, Any]) -> str:
        """Map pipeline status to update status."""
        pipeline_status_value = pipeline_status.get("status", "INITIALIZED")
        
        status_mapping = {
            "INITIALIZED": "initializing",
            "RUNNING": "updating",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "CANCELLED": "cancelled"
        }
        
        return status_mapping.get(pipeline_status_value, "unknown")
    
    def _calculate_progress(self, pipeline_status: Dict[str, Any]) -> float:
        """Calculate update progress percentage."""
        current_step = pipeline_status.get("current_step")
        total_steps = len(self.config.steps)
        
        if not current_step:
            return 0.0
        
        # Find step index
        step_names = [step.name for step in self.config.steps]
        
        if current_step in step_names:
            step_index = step_names.index(current_step)
            return (step_index / total_steps) * 100
        
        return 0.0
    
    async def update_product_async(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> str:
        """
        Update product asynchronously.
        
        Args:
            input_data: Product update request
            context: Optional execution context
            
        Returns:
            Update session ID
        """
        try:
            # Enqueue pipeline task
            job_id = await enqueue_pipeline_task(
                pipeline_name="product_update",
                input_data=input_data,
                config_overrides={
                    "update_id": self.update_id,
                    "async_mode": True
                }
            )
            
            logger.info(
                "Product update enqueued",
                update_id=self.update_id,
                job_id=job_id
            )
            
            return self.update_id
            
        except Exception as e:
            logger.error(
                "Failed to enqueue product update",
                update_id=self.update_id,
                error=str(e)
            )
            raise BaseLayerError(f"Async update failed: {str(e)}") from e
    
    def get_update_summary(self) -> Dict[str, Any]:
        """
        Get summary of current update session.
        
        Returns:
            Dict containing update summary
        """
        try:
            if not self.update_id:
                return {
                    "status": "no_active_session",
                    "message": "No active update session"
                }
            
            # Get pipeline status
            pipeline_status = self.get_status()
            
            # Compile summary
            summary = {
                "update_id": self.update_id,
                "status": self._map_pipeline_status_to_update_status(pipeline_status),
                "product_info": {
                    "product_id": self.product_data.get("product_id"),
                    "title": self.product_data.get("title"),
                    "product_type": self.product_data.get("product_type"),
                    "sections_to_update": self.product_data.get("sections", [])
                },
                "progress": self._calculate_progress(pipeline_status),
                "current_step": pipeline_status.get("current_step"),
                "completed_steps": pipeline_status.get("completed_steps", []),
                "failed_steps": pipeline_status.get("failed_steps", []),
                "duration_ms": pipeline_status.get("duration_ms", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(
                "Failed to get update summary",
                update_id=self.update_id,
                error=str(e)
            )
            return {
                "update_id": self.update_id,
                "status": "error",
                "error": str(e)
            }


# Factory function
def create_product_update_pipeline(
    db_session=None,
    redis_client=None,
    config: Optional[Dict[str, Any]] = None
) -> ProductUpdatePipeline:
    """
    Create product update pipeline instance.
    
    Args:
        db_session: Database session
        redis_client: Redis client
        config: Optional configuration
        
    Returns:
        ProductUpdatePipeline instance
    """
    return ProductUpdatePipeline(db_session, redis_client, config)


# Register pipeline for task system
from agents.queue.tasks import PIPELINE_REGISTRY
PIPELINE_REGISTRY["product_update"] = {
    "name": "product_update",
    "description": "Product update and regeneration pipeline",
    "steps": [
        {
            "name": "analyze_existing_product",
            "agent": "ProductGenerator",
            "error_handling": "retry",
            "max_retries": 2
        },
        {
            "name": "regenerate_sections",
            "agent": "ProductGenerator",
            "depends_on": ["analyze_existing_product"],
            "error_handling": "retry",
            "max_retries": 3
        },
        {
            "name": "repackage_product",
            "agent": "ProductPackager",
            "depends_on": ["regenerate_sections"],
            "error_handling": "retry",
            "max_retries": 2
        },
        {
            "name": "update_listing",
            "agent": "ListingOptimizer",
            "depends_on": ["regenerate_sections"],
            "error_handling": "retry",
            "max_retries": 2
        },
        {
            "name": "sync_to_gumroad",
            "agent": "GumroadPublisher",
            "depends_on": ["repackage_product", "update_listing"],
            "error_handling": "retry",
            "max_retries": 3
        }
    ],
    "mode": "sequential",
    "timeout_seconds": 1200,
    "enable_persistence": True,
    "enable_events": True,
    "metadata": {
        "pipeline_type": "product_update",
        "version": "1.0.0",
        "supports_partial_update": True
    }
}
