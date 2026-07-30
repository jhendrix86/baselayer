"""
MINT Product Pipeline Tests

Test suite for product creation and update
pipelines including end-to-end workflows.
"""

import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agents.core.pipeline import PipelineStatus
from ..product_creation_pipeline import create_product_creation_pipeline
from ..product_update_pipeline import create_product_update_pipeline
from tests.engines.mint.conftest import (
    sample_product_data,
    sample_generation_request,
    sample_regenerate_request,
    mock_agent_context,
    log_capture
)


class TestProductCreationPipeline:
    """Test suite for ProductCreationPipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = create_product_creation_pipeline()
        
        assert pipeline.config.name == "product_creation"
        assert pipeline.config.description == "End-to-end digital product creation pipeline"
        assert len(pipeline.config.steps) == 4
        assert pipeline.config.mode.value == "sequential"
        assert pipeline.config.timeout_seconds == 1800
        assert pipeline.config.enable_persistence is True
        assert pipeline.config.enable_events is True
    
    @pytest.mark.asyncio
    async def test_pipeline_step_configuration(self):
        """Test pipeline step configuration."""
        pipeline = create_product_creation_pipeline()
        
        steps = pipeline.config.steps
        
        # Check step names and dependencies
        step_names = [step.name for step in steps]
        expected_steps = [
            "generate_content",
            "package_product", 
            "optimize_listing",
            "publish_to_gumroad"
        ]
        
        for expected_step in expected_steps:
            assert expected_step in step_names
        
        # Check dependencies
        generate_content_step = next(step for step in steps if step.name == "generate_content")
        package_product_step = next(step for step in steps if step.name == "package_product")
        
        assert package_product_step.depends_on == ["generate_content"]
        assert generate_content_step.depends_on == []
    
    @pytest.mark.asyncio
    async def test_pipeline_execution_success(self, sample_generation_request):
        """Test successful pipeline execution."""
        pipeline = create_product_creation_pipeline()
        
        # Mock agent execution
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        result = await pipeline.execute(sample_generation_request)
        
        assert result["success"] is True
        assert "creation_id" in result
        assert "product_info" in result
        assert "execution_summary" in result
        assert "step_results" in result
        assert "next_steps" in result
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_pipeline_execution_with_step_failure(self, sample_generation_request):
        """Test pipeline execution with step failure."""
        pipeline = create_product_creation_pipeline()
        
        # Mock agent execution with failure
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": False, "error": "Test failure"})
            agent.validate = AsyncMock(return_value={"valid": False, "score": 0.3})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        result = await pipeline.execute(sample_generation_request)
        
        assert result["success"] is False
        assert "creation_id" in result
        assert "product_info" in result
        assert "execution_summary" in result
        assert len(result["execution_summary"]["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_pipeline_context_creation(self, sample_generation_request):
        """Test pipeline context creation."""
        pipeline = create_product_creation_pipeline()
        
        context = pipeline._create_pipeline_context(sample_generation_request, None)
        
        assert context.task_id == pipeline.creation_id
        assert context.task_type == "product_creation"
        assert context.input_data == sample_generation_request
        assert context.pipeline_id == "product_creation"
        assert "creation_id" in context.metadata
        assert "product_type" in context.metadata
        assert "pipeline_version" in context.metadata
    
    @pytest.mark.asyncio
    async def test_result_compilation(self, sample_generation_request):
        """Test result compilation from step results."""
        pipeline = create_product_creation_pipeline()
        
        # Create mock step results
        step_results = {
            "generate_content": {
                "success": True,
                "result": {
                    "generation_id": "test-gen-123",
                    "content": "Test content",
                    "metadata": {"quality_score": 0.9}
                }
            },
            "package_product": {
                "success": True,
                "result": {
                    "assets": {"pdf": {"file_size_bytes": 1024}},
                    "success": True
                }
            },
            "optimize_listing": {
                "success": True,
                "result": {
                    "full_listing": "Test listing",
                    "score": 0.95
                }
            },
            "publish_to_gumroad": {
                "success": True,
                "result": {
                    "gumroad_product_id": "gumroad-123",
                    "gumroad_url": "https://gumroad.com/l/test"
                }
            }
        }
        
        pipeline_result = {"step_results": step_results}
        final_result = pipeline._compile_creation_results(pipeline_result)
        
        assert final_result["success"] is True
        assert final_result["product_info"]["content"] == "Test content"
        assert final_result["product_info"]["assets"]["pdf"]["file_size_bytes"] == 1024
        assert final_result["product_info"]["listing_copy"] == "Test listing"
        assert final_result["product_info"]["gumroad_info"]["gumroad_product_id"] == "gumroad-123"
        assert final_result["execution_summary"]["quality_scores"]["content_quality"] == 0.9
        assert final_result["execution_summary"]["quality_scores"]["packaging_quality"] == 1.0
        assert final_result["execution_summary"]["quality_scores"]["listing_quality"] == 0.95
        assert final_result["execution_summary"]["quality_scores"]["publishing_quality"] == 1.0
    
    @pytest.mark.asyncio
    async def test_status_tracking(self, sample_generation_request):
        """Test pipeline status tracking."""
        pipeline = create_product_creation_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_generation_request)
        
        # Get status
        status = await pipeline.get_creation_status(pipeline.creation_id)
        
        assert status["creation_id"] == pipeline.creation_id
        assert status["status"] in ["initializing", "creating", "completed"]
        assert "current_step" in status
        assert "progress" in status
    
    @pytest.mark.asyncio
    async def test_status_not_found(self):
        """Test status tracking for non-existent creation."""
        pipeline = create_product_creation_pipeline()
        
        status = await pipeline.get_creation_status("nonexistent-id")
        
        assert status["status"] == "not_found"
        assert "error" in status
    
    @pytest.mark.asyncio
    async def test_cancellation(self, sample_generation_request):
        """Test pipeline cancellation."""
        pipeline = create_product_creation_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_generation_request)
        
        # Cancel pipeline
        cancelled = await pipeline.cancel_creation(pipeline.creation_id)
        
        assert cancelled is True
    
    @pytest.mark.asyncio
    async def test_cancellation_not_found(self):
        """Test cancellation for non-existent creation."""
        pipeline = create_product_creation_pipeline()
        
        cancelled = await pipeline.cancel_creation("nonexistent-id")
        
        assert cancelled is False
    
    @pytest.mark.asyncio
    async def test_async_execution(self, sample_generation_request):
        """Test async pipeline execution."""
        pipeline = create_product_creation_pipeline()
        
        # Mock enqueue task
        with pytest.mock.patch('engines.mint.product_creation_pipeline.enqueue_pipeline_task') as mock_enqueue:
            mock_enqueue.return_value = "test-job-id"
            
            creation_id = await pipeline.create_product_async(sample_generation_request)
            
            assert creation_id == pipeline.creation_id
            mock_enqueue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_summary(self, sample_generation_request):
        """Test pipeline summary generation."""
        pipeline = create_product_creation_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_generation_request)
        
        # Get summary
        summary = pipeline.get_creation_summary()
        
        assert summary["creation_id"] == pipeline.creation_id
        assert summary["status"] in ["initializing", "creating", "completed"]
        assert "product_info" in summary
        assert "progress" in summary
        assert "current_step" in summary
        assert "completed_steps" in summary
        assert "failed_steps" in summary
        assert "duration_ms" in summary
    
    @pytest.mark.asyncio
    async def test_no_active_session_summary(self):
        """Test summary when no active session."""
        pipeline = create_product_creation_pipeline()
        
        summary = pipeline.get_creation_summary()
        
        assert summary["status"] == "no_active_session"
        assert "message" in summary


class TestProductUpdatePipeline:
    """Test suite for ProductUpdatePipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self):
        """Test update pipeline initialization."""
        pipeline = create_product_update_pipeline()
        
        assert pipeline.config.name == "product_update"
        assert pipeline.config.description == "Product update and regeneration pipeline"
        assert len(pipeline.config.steps) == 5
        assert pipeline.config.mode.value == "sequential"
        assert pipeline.config.timeout_seconds == 1200
        assert pipeline.config.enable_persistence is True
        assert pipeline.config.enable_events is True
    
    @pytest.mark.asyncio
    async def test_pipeline_step_configuration(self):
        """Test update pipeline step configuration."""
        pipeline = create_product_update_pipeline()
        
        steps = pipeline.config.steps
        
        # Check step names and dependencies
        step_names = [step.name for step in steps]
        expected_steps = [
            "analyze_existing_product",
            "regenerate_sections",
            "repackage_product",
            "update_listing",
            "sync_to_gumroad"
        ]
        
        for expected_step in expected_steps:
            assert expected_step in step_names
        
        # Check dependencies
        regenerate_sections_step = next(step for step in steps if step.name == "regenerate_sections")
        repackage_product_step = next(step for step in steps if step.name == "repackage_product")
        
        assert regenerate_sections_step.depends_on == ["analyze_existing_product"]
        assert repackage_product_step.depends_on == ["regenerate_sections"]
    
    @pytest.mark.asyncio
    async def test_pipeline_execution_success(self, sample_regenerate_request):
        """Test successful update pipeline execution."""
        pipeline = create_product_update_pipeline()
        
        # Mock agent execution
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        result = await pipeline.execute(sample_regenerate_request)
        
        assert result["success"] is True
        assert "update_id" in result
        assert "product_info" in result
        assert "execution_summary" in result
        assert "step_results" in result
        assert "next_steps" in result
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_pipeline_execution_partial_update(self, sample_regenerate_request):
        """Test pipeline execution with partial update."""
        pipeline = create_product_update_pipeline()
        
        # Mock agent execution
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        result = await pipeline.execute(sample_regenerate_request)
        
        assert result["success"] is True
        assert result["product_info"]["updated_sections"] == sample_regenerate_request["sections"]
    
    @pytest.mark.asyncio
    async def test_update_context_creation(self, sample_regenerate_request):
        """Test update pipeline context creation."""
        pipeline = create_product_update_pipeline()
        
        context = pipeline._create_pipeline_context(sample_regenerate_request, None)
        
        assert context.task_id == pipeline.update_id
        assert context.task_type == "product_update"
        assert context.input_data == sample_regenerate_request
        assert context.pipeline_id == "product_update"
        assert "update_id" in context.metadata
        assert "product_id" in context.metadata
        assert "sections_to_update" in context.metadata
        assert "pipeline_version" in context.metadata
    
    @pytest.mark.asyncio
    async def test_update_result_compilation(self, sample_regenerate_request):
        """Test update result compilation."""
        pipeline = create_product_update_pipeline()
        
        # Create mock step results
        step_results = {
            "analyze_existing_product": {
                "success": True,
                "result": {"test": "analysis"}
            },
            "regenerate_sections": {
                "success": True,
                "result": {
                    "content": "Updated content",
                    "sections": {"introduction": "Updated intro"}
                }
            },
            "repackage_product": {
                "success": True,
                "result": {
                    "assets": {"pdf": {"file_size_bytes": 2048}}
                }
            },
            "update_listing": {
                "success": True,
                "result": {
                    "full_listing": "Updated listing"
                }
            },
            "sync_to_gumroad": {
                "success": True,
                "result": {
                    "gumroad_product_id": "gumroad-456",
                    "gumroad_url": "https://gumroad.com/l/updated-test"
                }
            }
        }
        
        pipeline_result = {"step_results": step_results}
        final_result = pipeline._compile_update_results(pipeline_result)
        
        assert final_result["success"] is True
        assert final_result["product_info"]["updated_sections"] == sample_regenerate_request["sections"]
        assert final_result["product_info"]["content"] == "Updated content"
        assert final_result["product_info"]["assets"]["pdf"]["file_size_bytes"] == 2048
        assert final_result["product_info"]["listing_copy"] == "Updated listing"
        assert final_result["product_info"]["gumroad_info"]["gumroad_product_id"] == "gumroad-456"
    
    @pytest.mark.asyncio
    async def test_update_status_tracking(self, sample_regenerate_request):
        """Test update pipeline status tracking."""
        pipeline = create_product_update_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_regenerate_request)
        
        # Get status
        status = await pipeline.get_update_status(pipeline.update_id)
        
        assert status["update_id"] == pipeline.update_id
        assert status["status"] in ["initializing", "updating", "completed"]
        assert "current_step" in status
        assert "progress" in status
    
    @pytest.mark.asyncio
    async def test_update_status_not_found(self):
        """Test update status for non-existent update."""
        pipeline = create_product_update_pipeline()
        
        status = await pipeline.get_update_status("nonexistent-id")
        
        assert status["status"] == "not_found"
        assert "error" in status
    
    @pytest.mark.asyncio
    async def test_update_cancellation(self, sample_regenerate_request):
        """Test update pipeline cancellation."""
        pipeline = create_product_update_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_regenerate_request)
        
        # Cancel pipeline
        cancelled = await pipeline.cancel_update(pipeline.update_id)
        
        assert cancelled is True
    
    @pytest.mark.asyncio
    async def test_update_cancellation_not_found(self):
        """Test update cancellation for non-existent update."""
        pipeline = create_product_update_pipeline()
        
        cancelled = await pipeline.cancel_update("nonexistent-id")
        
        assert cancelled is False
    
    @pytest.mark.asyncio
    async def test_update_async_execution(self, sample_regenerate_request):
        """Test async update pipeline execution."""
        pipeline = create_product_update_pipeline()
        
        # Mock enqueue task
        with pytest.mock.patch('engines.mint.product_update_pipeline.enqueue_pipeline_task') as mock_enqueue:
            mock_enqueue.return_value = "test-update-job-id"
            
            update_id = await pipeline.update_product_async(sample_regenerate_request)
            
            assert update_id == pipeline.update_id
            mock_enqueue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_get_summary(self, sample_regenerate_request):
        """Test update pipeline summary generation."""
        pipeline = create_product_update_pipeline()
        
        # Mock agents
        for agent_name, agent in pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await pipeline.execute(sample_regenerate_request)
        
        # Get summary
        summary = pipeline.get_update_summary()
        
        assert summary["update_id"] == pipeline.update_id
        assert summary["status"] in ["initializing", "updating", "completed"]
        assert "product_info" in summary
        assert "progress" in summary
        assert "current_step" in summary
        assert "completed_steps" in summary
        assert "failed_steps" in summary
        assert "duration_ms" in summary
    
    @pytest.mark.asyncio
    async def test_update_no_active_session_summary(self):
        """Test update summary when no active session."""
        pipeline = create_product_update_pipeline()
        
        summary = pipeline.get_update_summary()
        
        assert summary["status"] == "no_active_session"
        assert "message" in summary


class TestPipelineIntegration:
    """Test suite for pipeline integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_creation_workflow(self, sample_generation_request):
        """Test complete creation workflow."""
        creation_pipeline = create_product_creation_pipeline()
        
        # Mock realistic agent responses
        for agent_name, agent in creation_pipeline.agents.items():
            if agent_name == "ProductGenerator":
                agent.plan = AsyncMock(return_value={
                    "product_type": "pdf_guide",
                    "generation_strategy": "brief",
                    "structure": {"sections": {"introduction": {}, "main": {}}},
                    "estimated_duration": 30
                })
                agent.execute = AsyncMock(return_value={
                    "success": True,
                    "generation_id": "gen-123",
                    "content": "Generated PDF guide content",
                    "sections": {"introduction": "Intro content", "main": "Main content"},
                    "metadata": {"quality_score": 0.85, "word_count": 1500}
                })
                agent.validate = AsyncMock(return_value={
                    "valid": True,
                    "score": 0.85
                })
                agent.report = AsyncMock(return_value={
                    "agent_id": agent.agent_id,
                    "execution_summary": {"quality_score": 0.85}
                })
            
            elif agent_name == "ProductPackager":
                agent.plan = AsyncMock(return_value={
                    "output_formats": ["pdf", "md", "txt", "zip"],
                    "estimated_duration": 20
                })
                agent.execute = AsyncMock(return_value={
                    "success": True,
                    "assets": {
                        "pdf": {"file_name": "test.pdf", "file_size_bytes": 1024000},
                        "zip": {"file_name": "test.zip", "file_size_bytes": 2048000}
                    },
                    "primary_asset": "pdf"
                })
                agent.validate = AsyncMock(return_value={
                    "valid": True,
                    "score": 0.9
                })
                agent.report = AsyncMock(return_value={
                    "agent_id": agent.agent_id,
                    "execution_summary": {"total_files": 2}
                })
            
            elif agent_name == "ListingOptimizer":
                agent.plan = AsyncMock(return_value={
                    "optimization_strategy": "benefit_driven",
                    "estimated_duration": 25
                })
                agent.execute = AsyncMock(return_value={
                    "success": True,
                    "full_listing": "Optimized Gumroad listing copy",
                    "character_counts": {"total": 500, "title": 50}
                })
                agent.validate = AsyncMock(return_value={
                    "valid": True,
                    "score": 0.95
                })
                agent.report = AsyncMock(return_value={
                    "agent_id": agent.agent_id,
                    "execution_summary": {"character_counts": {"total": 500}}
                })
            
            elif agent_name == "GumroadPublisher":
                agent.plan = AsyncMock(return_value={
                    "publishing_strategy": "immediate",
                    "estimated_duration": 15
                })
                agent.execute = AsyncMock(return_value={
                    "success": True,
                    "gumroad_product_id": "gumroad-789",
                    "gumroad_url": "https://gumroad.com/l/test-product",
                    "publishing_status": "published"
                })
                agent.validate = AsyncMock(return_value={
                    "valid": True,
                    "score": 1.0
                })
                agent.report = AsyncMock(return_value={
                    "agent_id": agent.agent_id,
                    "execution_summary": {"gumroad_product_id": "gumroad-789"}
                })
        
        result = await creation_pipeline.execute(sample_generation_request)
        
        assert result["success"] is True
        assert result["product_info"]["content"] == "Generated PDF guide content"
        assert result["product_info"]["assets"]["pdf"]["file_name"] == "test.pdf"
        assert result["product_info"]["listing_copy"] == "Optimized Gumroad listing copy"
        assert result["product_info"]["gumroad_info"]["gumroad_product_id"] == "gumroad-789"
        assert result["execution_summary"]["total_steps"] == 4
        assert result["execution_summary"]["steps_completed"] == 4
    
    @pytest.mark.asyncio
    async def test_error_propagation(self, sample_generation_request):
        """Test error propagation through pipeline."""
        creation_pipeline = create_product_creation_pipeline()
        
        # Mock first step to fail
        for agent_name, agent in creation_pipeline.agents.items():
            if agent_name == "ProductGenerator":
                agent.plan = AsyncMock(return_value={"test": "plan"})
                agent.execute = AsyncMock(return_value={
                    "success": False,
                    "error": "Content generation failed"
                })
                agent.validate = AsyncMock(return_value={
                    "valid": False,
                    "score": 0.0,
                    "error": "Validation failed"
                })
                agent.report = AsyncMock(return_value={
                    "agent_id": agent.agent_id,
                    "error": "Report generation failed"
                })
            else:
                agent.plan = AsyncMock(return_value={"test": "plan"})
                agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
                agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
                agent.report = AsyncMock(return_value={"test": "report"})
        
        result = await creation_pipeline.execute(sample_generation_request)
        
        assert result["success"] is False
        assert len(result["execution_summary"]["errors"]) > 0
        assert "Content generation failed" in str(result["execution_summary"]["errors"])
    
    @pytest.mark.asyncio
    async def test_logging_integration(self, sample_generation_request, log_capture):
        """Test logging integration across pipeline."""
        creation_pipeline = create_product_creation_pipeline()
        
        # Start capturing logs
        log_capture.start()
        
        # Mock agents
        for agent_name, agent in creation_pipeline.agents.items():
            agent.plan = AsyncMock(return_value={"test": "plan"})
            agent.execute = AsyncMock(return_value={"success": True, "result": {"test": "result"}})
            agent.validate = AsyncMock(return_value={"valid": True, "score": 0.9})
            agent.report = AsyncMock(return_value={"test": "report"})
        
        # Execute pipeline
        await creation_pipeline.execute(sample_generation_request)
        
        # Stop capturing logs
        log_capture.stop()
        
        # Check that logs were captured
        messages = log_capture.get_messages("INFO")
        assert len(messages) > 0
        
        # Check for specific log messages
        info_messages = [msg for msg in messages if "Product creation pipeline" in msg["message"]]
        assert len(info_messages) > 0
