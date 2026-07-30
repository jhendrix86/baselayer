"""
MINT Product Creation Pipeline

End-to-end pipeline for creating digital products
from generation to Gumroad publishing.
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


class ProductCreationPipeline(Pipeline):
    """
    End-to-end product creation pipeline.
    
    Orchestrates product generation, packaging,
    listing optimization, and Gumroad publishing.
    """
    
    def __init__(
        self,
        db_session=None,
        redis_client=None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize product creation pipeline."""
        # Create pipeline configuration
        pipeline_config = PipelineConfig(
            name="product_creation",
            description="End-to-end digital product creation pipeline",
            steps=[
                PipelineStep(
                    name="generate_content",
                    agent=ProductGenerator,
                    error_handling=ErrorHandling.RETRY,
                    max_retries=3
                ),
                PipelineStep(
                    name="package_product",
                    agent=ProductPackager,
                    depends_on=["generate_content"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=2
                ),
                PipelineStep(
                    name="optimize_listing",
                    agent=ListingOptimizer,
                    depends_on=["generate_content"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=2
                ),
                PipelineStep(
                    name="publish_to_gumroad",
                    agent=GumroadPublisher,
                    depends_on=["package_product", "optimize_listing"],
                    error_handling=ErrorHandling.RETRY,
                    max_retries=3
                )
            ],
            mode=PipelineMode.SEQUENTIAL,
            timeout_seconds=1800,  # 30 minutes
            enable_persistence=True,
            enable_events=True,
            metadata={
                "pipeline_type": "product_creation",
                "version": "1.0.0",
                "supports_async": True
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
        
        # Pipeline state
        self.creation_id: Optional[str] = None
        self.product_data: Dict[str, Any] = {}
        self.creation_progress: Dict[str, Any] = {}
    
    async def execute(self, input_data: Dict[str, Any], context: Optional[AgentContext] = None) -> Dict[str, Any]:
        """
        Execute product creation pipeline.
        
        Args:
            input_data: Product creation request
            context: Optional execution context
            
        Returns:
            Dict containing pipeline results
        """
        try:
            # Initialize creation session
            self.creation_id = str(uuid.uuid4())
            self.product_data = input_data.copy()
            
            logger.info(
                "Starting product creation pipeline",
                creation_id=self.creation_id,
                product_type=input_data.get("product_type"),
                title=input_data.get("title")
            )
            
            # Create pipeline context
            pipeline_context = self._create_pipeline_context(input_data, context)
            
            # Execute pipeline steps
            result = await super().execute(input_data, pipeline_context)
            
            # Compile final results
            final_result = self._compile_creation_results(result)
            
            logger.info(
                "Product creation pipeline completed",
                creation_id=self.creation_id,
                success=final_result.get("success", False)
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                "Product creation pipeline failed",
                creation_id=self.creation_id,
                error=str(e)
            )
            raise BaseLayerError(f"Pipeline execution failed: {str(e)}") from e
    
    def _create_pipeline_context(self, input_data: Dict[str, Any], parent_context: Optional[AgentContext]) -> AgentContext:
        """Create pipeline execution context."""
        return AgentContext(
            task_id=self.creation_id,
            task_type="product_creation",
            input_data=input_data,
            memory_interface=parent_context.memory_interface if parent_context else None,
            config=parent_context.config if parent_context else None,
            request_id=parent_context.request_id if parent_context else str(uuid.uuid4()),
            parent_agent_id=parent_context.agent_id if parent_context else None,
            pipeline_id="product_creation",
            metadata={
                "creation_id": self.creation_id,
                "product_type": input_data.get("product_type"),
                "title": input_data.get("title"),
                "pipeline_version": "1.0.0"
            }
        )
    
    def _compile_creation_results(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compile final creation results from pipeline results."""
        try:
            step_results = pipeline_result.get("step_results", {})
            
            # Extract results from each step
            generation_result = step_results.get("generate_content", {})
            packaging_result = step_results.get("package_product", {})
            listing_result = step_results.get("optimize_listing", {})
            publishing_result = step_results.get("publish_to_gumroad", {})
            
            # Determine overall success
            overall_success = all([
                generation_result.get("success", False),
                packaging_result.get("success", False),
                listing_result.get("success", False),
                publishing_result.get("success", False)
            ])
            
            # Compile product information
            product_info = {
                "creation_id": self.creation_id,
                "title": self.product_data.get("title"),
                "product_type": self.product_data.get("product_type"),
                "description": self.product_data.get("description"),
                "price_cents": self.product_data.get("price_cents", 0),
                "target_audience": self.product_data.get("target_audience"),
                "tags": self.product_data.get("tags", []),
                "content": generation_result.get("result", {}).get("content", ""),
                "assets": packaging_result.get("result", {}).get("assets", {}),
                "listing_copy": listing_result.get("result", {}).get("full_listing", ""),
                "gumroad_info": {
                    "product_id": publishing_result.get("result", {}).get("gumroad_product_id"),
                    "url": publishing_result.get("result", {}).get("gumroad_url"),
                    "status": publishing_result.get("result", {}).get("publishing_status")
                }
            }
            
            # Compile execution summary
            execution_summary = {
                "total_duration_ms": pipeline_result.get("duration_ms", 0),
                "steps_completed": len([r for r in step_results.values() if r.get("success", False)]),
                "total_steps": len(step_results),
                "quality_scores": {
                    "content_quality": generation_result.get("result", {}).get("metadata", {}).get("quality_score", 0.0),
                    "packaging_quality": packaging_result.get("result", {}).get("score", 0.0),
                    "listing_quality": listing_result.get("result", {}).get("score", 0.0),
                    "publishing_quality": publishing_result.get("result", {}).get("score", 0.0)
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
                    "Create promotional materials",
                    "Set up email automation for buyers",
                    "Plan product updates and improvements"
                ])
            else:
                next_steps.extend([
                    "Review and fix failed steps",
                    "Retry product creation with corrected inputs",
                    "Validate product requirements",
                    "Check system configuration"
                ])
            
            return {
                "creation_id": self.creation_id,
                "success": overall_success,
                "product_info": product_info,
                "execution_summary": execution_summary,
                "step_results": step_results,
                "next_steps": next_steps,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Failed to compile creation results",
                creation_id=self.creation_id,
                error=str(e)
            )
            return {
                "creation_id": self.creation_id,
                "success": False,
                "error": f"Result compilation failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_creation_status(self, creation_id: str) -> Dict[str, Any]:
        """
        Get status of product creation.
        
        Args:
            creation_id: Creation session ID
            
        Returns:
            Dict containing creation status
        """
        try:
            if creation_id != self.creation_id:
                return {
                    "creation_id": creation_id,
                    "status": "not_found",
                    "error": "Creation session not found"
                }
            
            # Get current pipeline status
            pipeline_status = self.get_status()
            
            # Map pipeline status to creation status
            creation_status = self._map_pipeline_status_to_creation_status(pipeline_status)
            
            # Add creation-specific information
            creation_status.update({
                "creation_id": self.creation_id,
                "product_type": self.product_data.get("product_type"),
                "title": self.product_data.get("title"),
                "current_step": pipeline_status.get("current_step"),
                "progress": self._calculate_progress(pipeline_status)
            })
            
            return creation_status
            
        except Exception as e:
            logger.error(
                "Failed to get creation status",
                creation_id=creation_id,
                error=str(e)
            )
            return {
                "creation_id": creation_id,
                "status": "error",
                "error": str(e)
            }
    
    async def cancel_creation(self, creation_id: str) -> bool:
        """
        Cancel product creation.
        
        Args:
            creation_id: Creation session ID
            
        Returns:
            True if cancelled successfully
        """
        try:
            if creation_id != self.creation_id:
                return False
            
            # Cancel pipeline
            cancelled = await self.cancel()
            
            if cancelled:
                logger.info(
                    "Product creation cancelled",
                    creation_id=self.creation_id
                )
            
            return cancelled
            
        except Exception as e:
            logger.error(
                "Failed to cancel creation",
                creation_id=creation_id,
                error=str(e)
            )
            return False
    
    def _map_pipeline_status_to_creation_status(self, pipeline_status: Dict[str, Any]) -> str:
        """Map pipeline status to creation status."""
        pipeline_status_value = pipeline_status.get("status", "INITIALIZED")
        
        status_mapping = {
            "INITIALIZED": "initializing",
            "RUNNING": "creating",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "CANCELLED": "cancelled"
        }
        
        return status_mapping.get(pipeline_status_value, "unknown")
    
    def _calculate_progress(self, pipeline_status: Dict[str, Any]) -> float:
        """Calculate creation progress percentage."""
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
    
    async def create_product_async(
        self,
        input_data: Dict[str, Any],
        context: Optional[AgentContext] = None
    ) -> str:
        """
        Create product asynchronously.
        
        Args:
            input_data: Product creation request
            context: Optional execution context
            
        Returns:
            Creation session ID
        """
        try:
            # Enqueue pipeline task
            job_id = await enqueue_pipeline_task(
                pipeline_name="product_creation",
                input_data=input_data,
                config_overrides={
                    "creation_id": self.creation_id,
                    "async_mode": True
                }
            )
            
            logger.info(
                "Product creation enqueued",
                creation_id=self.creation_id,
                job_id=job_id
            )
            
            return self.creation_id
            
        except Exception as e:
            logger.error(
                "Failed to enqueue product creation",
                creation_id=self.creation_id,
                error=str(e)
            )
            raise BaseLayerError(f"Async creation failed: {str(e)}") from e
    
    def get_creation_summary(self) -> Dict[str, Any]:
        """
        Get summary of current creation session.
        
        Returns:
            Dict containing creation summary
        """
        try:
            if not self.creation_id:
                return {
                    "status": "no_active_session",
                    "message": "No active creation session"
                }
            
            # Get pipeline status
            pipeline_status = self.get_status()
            
            # Compile summary
            summary = {
                "creation_id": self.creation_id,
                "status": self._map_pipeline_status_to_creation_status(pipeline_status),
                "product_info": {
                    "title": self.product_data.get("title"),
                    "product_type": self.product_data.get("product_type"),
                    "price_cents": self.product_data.get("price_cents", 0)
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
                "Failed to get creation summary",
                creation_id=self.creation_id,
                error=str(e)
            )
            return {
                "creation_id": self.creation_id,
                "status": "error",
                "error": str(e)
            }


# Factory function
def create_product_creation_pipeline(
    db_session=None,
    redis_client=None,
    config: Optional[Dict[str, Any]] = None
) -> ProductCreationPipeline:
    """
    Create product creation pipeline instance.
    
    Args:
        db_session: Database session
        redis_client: Redis client
        config: Optional configuration
        
    Returns:
        ProductCreationPipeline instance
    """
    return ProductCreationPipeline(db_session, redis_client, config)


# Register pipeline for task system
from agents.queue.tasks import PIPELINE_REGISTRY
PIPELINE_REGISTRY["product_creation"] = {
    "name": "product_creation",
    "description": "End-to-end digital product creation pipeline",
    "steps": [
        {
            "name": "generate_content",
            "agent": "ProductGenerator",
            "error_handling": "retry",
            "max_retries": 3
        },
        {
            "name": "package_product",
            "agent": "ProductPackager",
            "depends_on": ["generate_content"],
            "error_handling": "retry",
            "max_retries": 2
        },
        {
            "name": "optimize_listing",
            "agent": "ListingOptimizer",
            "depends_on": ["generate_content"],
            "error_handling": "retry",
            "max_retries": 2
        },
        {
            "name": "publish_to_gumroad",
            "agent": "GumroadPublisher",
            "depends_on": ["package_product", "optimize_listing"],
            "error_handling": "retry",
            "max_retries": 3
        }
    ],
    "mode": "sequential",
    "timeout_seconds": 1800,
    "enable_persistence": True,
    "enable_events": True,
    "metadata": {
        "pipeline_type": "product_creation",
        "version": "1.0.0",
        "supports_async": True
    }
}
