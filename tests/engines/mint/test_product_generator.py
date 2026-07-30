"""
MINT Product Generator Tests

Test suite for ProductGenerator agent including
content generation, validation, and quality checks.
"""

import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional

from agents.agents.product_generator import ProductGenerator
from tests.engines.mint.conftest import (
    sample_product_data,
    sample_generation_request,
    mock_agent_context,
    mock_ollama_client,
    mock_prompt_engine,
    mock_memory_interface,
    sample_template_data,
    log_capture
)


class TestProductGenerator:
    """Test suite for ProductGenerator agent."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization with default configuration."""
        agent = ProductGenerator()
        
        assert agent.agent_name == "product_generator"
        assert agent.agent_version == "1.0.0"
        assert agent.quality_threshold == 0.8
        assert agent.min_word_count == 500
        assert agent.max_word_count == 10000
    
    @pytest.mark.asyncio
    async def test_agent_initialization_custom_config(self, mock_agent_config):
        """Test agent initialization with custom configuration."""
        agent = ProductGenerator(config=mock_agent_config)
        
        assert agent.config == mock_agent_config
        assert agent.quality_threshold == 0.8  # Default value
    
    @pytest.mark.asyncio
    async def test_plan_creation_success(self, sample_generation_request):
        """Test successful plan creation."""
        agent = ProductGenerator()
        
        plan = await agent.plan(sample_generation_request)
        
        assert plan is not None
        assert plan["product_type"] == sample_generation_request["product_type"]
        assert plan["brief"] == sample_generation_request["brief"]
        assert plan["generation_strategy"] in ["template", "brief"]
        assert plan["quality_checks"] is not None
        assert len(plan["quality_checks"]) > 0
        assert plan["estimated_duration"] > 0
        assert plan["llm_model"] is not None
        assert plan["temperature"] == 0.7
        assert plan["max_tokens"] == 2000
    
    @pytest.mark.asyncio
    async def test_plan_creation_with_template(self, sample_generation_request):
        """Test plan creation with template ID."""
        request_with_template = sample_generation_request.copy()
        request_with_template["template_id"] = "test-template-123"
        
        agent = ProductGenerator()
        plan = await agent.plan(request_with_template)
        
        assert plan["generation_strategy"] == "template"
        assert plan["template_id"] == "test-template-123"
        assert plan["structure"] is not None
    
    @pytest.mark.asyncio
    async def test_plan_creation_failure(self):
        """Test plan creation with invalid input."""
        agent = ProductGenerator()
        
        # Test with missing required fields
        invalid_request = {
            "product_type": "pdf_guide"
            # Missing brief
        }
        
        plan = await agent.plan(invalid_request)
        
        # Should still create plan but with limited data
        assert plan is not None
        assert plan["product_type"] == "pdf_guide"
        assert plan["brief"] == ""
    
    @pytest.mark.asyncio
    async def test_execution_success(
        self,
        sample_generation_request,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test successful content generation execution."""
        agent = ProductGenerator()
        
        # Mock the dependencies
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Create plan
        plan = await agent.plan(sample_generation_request)
        
        # Execute
        result = await agent.execute(plan)
        
        assert result["success"] is True
        assert "generation_id" in result
        assert "content" in result
        assert "sections" in result
        assert "word_count" in result
        assert result["word_count"] > 0
        assert "structure" in result
        assert result["structure"] is not None
    
    @pytest.mark.asyncio
    async def test_execution_with_template(
        self,
        sample_generation_request,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test execution with template-based generation."""
        request_with_template = sample_generation_request.copy()
        request_with_template["template_id"] = "test-template-123"
        
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        plan = await agent.plan(request_with_template)
        result = await agent.execute(plan)
        
        assert result["success"] is True
        assert "generation_id" in result
        assert len(result["sections"]) > 0
    
    @pytest.mark.asyncio
    async def test_execution_failure(
        self,
        sample_generation_request,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test execution failure handling."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Mock Ollama client to raise exception
        mock_ollama_client.chat.side_effect = Exception("LLM error")
        
        plan = await agent.plan(sample_generation_request)
        
        with pytest.raises(Exception):
            await agent.execute(plan)
    
    @pytest.mark.asyncio
    async def test_section_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test individual section generation."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Mock successful chat response
        mock_ollama_client.chat.return_value = type('MockResponse', (), {
            'response': "Generated section content",
            'done': True
        })()
        
        section_content = await agent._generate_section(
            "test_section",
            {"word_count": 500, "description": "Test section"},
            {"temperature": 0.7, "max_tokens": 1000}
        )
        
        assert section_content is not None
        assert len(section_content) > 0
        assert isinstance(section_content, str)
    
    @pytest.mark.asyncio
    async def test_content_compilation(
        self,
        mock_prompt_engine
    ):
        """Test content compilation from sections."""
        agent = ProductGenerator()
        agent.prompt_engine = mock_prompt_engine
        
        sections = {
            "introduction": "Test introduction content",
            "main_content": "Test main content",
            "conclusion": "Test conclusion content"
        }
        
        structure = {
            "sections": {
                "introduction": {"title": "Introduction"},
                "main_content": {"title": "Main Content"},
                "conclusion": {"title": "Conclusion"}
            }
        }
        
        compiled = agent._compile_product_content(
            sections,
            structure,
            "pdf_guide"
        )
        
        assert compiled is not None
        assert "Test introduction content" in compiled
        assert "Test main content" in compiled
        assert "Test conclusion content" in compiled
        assert "# Test introduction content" in compiled
    
    @pytest.mark.asyncio
    async def test_validation_success(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test successful content validation."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Create result with valid content
        result = {
            "content": "Valid content with sufficient word count and no violations",
            "word_count": 2000,
            "metadata": {
                "quality_score": 0.9,
                "word_count_target": 1500
            }
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is True
        assert validation["score"] >= 0.8
        assert len(validation["validation_results"]) == 5
        assert len(validation["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_validation_insufficient_word_count(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test validation with insufficient word count."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        result = {
            "content": "Short content",
            "word_count": 200,
            "metadata": {
                "word_count_target": 1500
            }
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("word_count" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_validation_kade_persona_violations(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test validation with Kade persona violations."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        result = {
            "content": "I think this is good. In my opinion, this content meets our standards. Personally, I believe this will help users.",
            "word_count": 1000,
            "metadata": {
                "word_count_target": 1000
            }
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("persona" in error for error in validation["errors"])
        assert any("personal anecdote" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_validation_placeholder_text(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test validation with placeholder text."""
        agent = ProductGenerator()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        result = {
            "content": "This content is [TODO] incomplete and needs [PLACEHOLDER] text.",
            "word_count": 500,
            "metadata": {
                "word_count_target": 1000
            }
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("placeholder" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_recommendations_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test recommendations generation from validation results."""
        agent = ProductGenerator()
        
        # Test with word count validation failure
        validation_results = {
            "word_count_validation": {
                "valid": False,
                "score": 0.3,
                "error": "Word count below minimum"
            }
        }
        
        recommendations = agent._generate_recommendations(validation_results)
        
        assert len(recommendations) > 0
        assert any("Expand content" in rec for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_next_steps_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test next steps generation from validation results."""
        agent = ProductGenerator()
        
        # Test with successful validation
        validation_results = {
            "overall_valid": True,
            "overall_score": 0.9
        }
        
        next_steps = agent._generate_next_steps(True)
        
        assert len(next_steps) > 0
        assert any("proceed" in step.lower() for step in next_steps)
        
        # Test with failed validation
        validation_results = {
            "overall_valid": False,
            "overall_score": 0.3
        }
        
        next_steps = agent._generate_next_steps(False)
        
        assert len(next_steps) > 0
        assert any("review" in step.lower() for step in next_steps)
    
    @pytest.mark.asyncio
    async def test_report_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test report generation from execution and validation results."""
        agent = ProductGenerator()
        
        execution_result = {
            "generation_id": "test-gen-123",
            "content": "Generated content for testing",
            "sections": {"introduction": "Test intro"},
            "word_count": 1000,
            "success": True
        }
        
        validation_result = {
            "valid": True,
            "score": 0.9,
            "validation_results": {}
        }
        
        report = await agent.report({
            "generation_id": execution_result["generation_id"],
            "result": execution_result,
            "validation_results": validation_result
        })
        
        assert report["agent_id"] == agent.agent_id
        assert report["agent_name"] == agent.agent_name
        assert report["generation_id"] == "test-gen-123"
        assert report["execution_summary"] is not None
        assert report["validation_summary"] is not None
        assert report["recommendations"] is not None
        assert report["next_steps"] is not None
        assert report["metrics"] is not None
    
    @pytest.mark.asyncio
    async def test_default_structure_selection(self, sample_generation_request):
        """Test default structure selection for product types."""
        agent = ProductGenerator()
        
        # Test PDF guide
        request = sample_generation_request.copy()
        request["product_type"] = "pdf_guide"
        
        structure = agent._get_default_structure("pdf_guide")
        
        assert structure is not None
        assert "sections" in structure
        assert "introduction" in structure["sections"]
        assert "problem_statement" in structure["sections"]
        assert "solution_overview" in structure["sections"]
        assert "implementation_steps" in structure["sections"]
        assert "conclusion" in structure["sections"]
    
    @pytest.mark.asyncio
    async def test_model_selection(self, sample_generation_request):
        """Test LLM model selection based on product type."""
        agent = ProductGenerator()
        
        # Test different product types
        test_cases = [
            ("pdf_guide", "llama2:13b"),
            ("template_pack", "llama2:7b"),
            ("checklist", "llama2:7b"),
            ("cheat_sheet", "llama2:7b"),
            ("prompt_library", "llama2:13b"),
            ("code_snippets", "llama2:13b"),
            ("notion_template", "llama2:7b")
        ]
        
        for product_type, expected_model in test_cases:
            selected_model = agent._select_model(product_type)
            assert selected_model == expected_model
    
    @pytest.mark.asyncio
    async def test_duration_estimation(self, sample_generation_request):
        """Test duration estimation for different product types."""
        agent = ProductGenerator()
        
        # Test different product types with same word count
        word_count = 2000
        test_cases = [
            ("pdf_guide", 1.0),  # Base multiplier
            ("template_pack", 0.8),  # Faster for templates
            ("checklist", 0.6),  # Faster for checklists
            ("cheat_sheet", 0.5),  # Fastest for cheat sheets
        ]
        
        for product_type, expected_multiplier in test_cases:
            duration = agent._estimate_duration(word_count, product_type)
            assert duration == int(word_count * 0.5 * expected_multiplier)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_generation_request):
        """Test error handling in various scenarios."""
        agent = ProductGenerator()
        
        # Test with missing required fields
        invalid_request = {}
        
        with pytest.raises(Exception):
            await agent.plan(invalid_request)
        
        # Test with invalid product type
        invalid_request = {
            "product_type": "invalid_type",
            "brief": "Test brief"
        }
        
        # Should still create plan but may fail later
        plan = await agent.plan(invalid_request)
        assert plan is not None
    
    @pytest.mark.asyncio
    async def test_logging(self, sample_generation_request, log_capture):
        """Test logging functionality."""
        agent = ProductGenerator()
        
        # Start capturing logs
        log_capture.start()
        
        # Execute plan and execution
        plan = await agent.plan(sample_generation_request)
        result = await agent.execute(plan)
        
        # Stop capturing logs
        log_capture.stop()
        
        # Check that logs were captured
        messages = log_capture.get_messages("INFO")
        assert len(messages) > 0
        
        # Check for specific log messages
        info_messages = [msg for msg in messages if "Product generation plan created" in msg["message"]]
        assert len(info_messages) > 0
    
    @pytest.mark.asyncio
    async def test_memory_usage_tracking(self, sample_generation_request):
        """Test memory usage tracking during generation."""
        agent = ProductGenerator()
        
        # Execute generation
        plan = await agent.plan(sample_generation_request)
        result = await agent.execute(plan)
        
        # Check that memory usage was tracked
        assert hasattr(agent, '_memory_usage_mb')
        assert agent._memory_usage_mb >= 0
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, sample_generation_request):
        """Test metrics tracking during generation."""
        agent = ProductGenerator()
        
        # Execute generation multiple times
        for i in range(3):
            plan = await agent.plan(sample_generation_request)
            result = await agent.execute(plan)
        
        # Check metrics
        metrics = agent._get_execution_metrics()
        assert metrics["total_runs"] == 3
        assert metrics["successful_runs"] == 3
        assert metrics["failed_runs"] == 0
        assert metrics["duration_ms"] > 0
