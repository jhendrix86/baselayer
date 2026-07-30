"""
MINT Listing Optimizer Tests

Test suite for ListingOptimizer agent including
Gumroad listing copy generation and optimization.
"""

import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional

from agents.agents.listing_optimizer import ListingOptimizer
from tests.engines.mint.conftest import (
    sample_product_data,
    mock_agent_context,
    mock_ollama_client,
    mock_prompt_engine,
    mock_memory_interface,
    log_capture
)


class TestListingOptimizer:
    """Test suite for ListingOptimizer agent."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization with default configuration."""
        agent = ListingOptimizer()
        
        assert agent.agent_name == "listing_optimizer"
        assert agent.agent_version == "1.0.0"
        assert agent.character_limits["title"] == 80
        assert agent.character_limits["subtitle"] == 200
        assert agent.character_limits["description"] == 5000
        assert len(agent.optimization_strategies) > 0
    
    @pytest.mark.asyncio
    async def test_agent_initialization_custom_config(self, mock_agent_config):
        """Test agent initialization with custom configuration."""
        agent = ListingOptimizer(config=mock_agent_config)
        
        assert agent.config == mock_agent_config
        assert agent.character_limits["title"] == 80  # Default value
    
    @pytest.mark.asyncio
    async def test_plan_creation_success(self, sample_product_data):
        """Test successful plan creation."""
        agent = ListingOptimizer()
        
        plan = await agent.plan(sample_product_data)
        
        assert plan is not None
        assert plan["product_title"] == sample_product_data["title"]
        assert plan["product_type"] == sample_product_data["product_type"]
        assert plan["content"] == sample_product_data["description"]
        assert plan["target_audience"] == sample_product_data.get("target_audience", "general")
        assert plan["price_cents"] == sample_product_data["price_cents"]
        assert plan["optimization_strategy"] in agent.optimization_strategies
        assert plan["copy_structure"] is not None
        assert plan["optimization_focus"] is not None
        assert len(plan["optimization_focus"]) > 0
        assert plan["estimated_duration"] > 0
        assert plan["llm_model"] is not None
        assert plan["temperature"] == 0.8
        assert plan["max_tokens"] == 2000
    
    @pytest.mark.asyncio
    async def test_plan_creation_high_priced_product(self, sample_product_data):
        """Test plan creation for high-priced product."""
        high_priced_data = sample_product_data.copy()
        high_priced_data["price_cents"] = 5000  # $50
        
        agent = ListingOptimizer()
        plan = await agent.plan(high_priced_data)
        
        assert plan["optimization_strategy"] == "premium_positioning"
        assert plan["copy_structure"]["framework"] == "AIDA"
        assert plan["copy_structure"]["focus"] == "exclusivity and value"
    
    @pytest.mark.asyncio
    async def test_plan_creation_beginner_audience(self, sample_product_data):
        """Test plan creation for beginner audience."""
        beginner_data = sample_product_data.copy()
        beginner_data["target_audience"] = "beginner"
        
        agent = ListingOptimizer()
        plan = await agent.plan(beginner_data)
        
        assert plan["optimization_strategy"] == "educational_approach"
        assert plan["copy_structure"]["framework"] == "AIDA"
        assert plan["copy_structure"]["focus"] == "learning and transformation"
    
    @pytest.mark.asyncio
    async def test_plan_creation_with_content_analysis(self, sample_product_data):
        """Test plan creation with content analysis."""
        # Add content with optimization potential
        rich_content_data = sample_product_data.copy()
        rich_content_data["description"] = "This guide provides numerous benefits and helps you solve common problems. You'll discover new advantages and master key skills."
        
        agent = ListingOptimizer()
        plan = await agent.plan(rich_content_data)
        
        assert plan["content_analysis"] is not None
        assert plan["content_analysis"]["optimization_potential"] is True
        assert plan["content_analysis"]["benefit_count"] > 0
        assert plan["content_analysis"]["problem_count"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_success(
        self,
        sample_product_data,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test successful listing optimization execution."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Create plan
        plan = await agent.plan(sample_product_data)
        
        # Execute
        result = await agent.execute(plan)
        
        assert result["success"] is True
        assert "optimization_id" in result
        assert "components" in result
        assert "full_listing" in result
        assert "character_counts" in result
        assert "strategy" in result
        
        # Check components
        components = result["components"]
        assert "title" in components
        assert "subtitle" in components
        assert "description" in components
        assert "features" in components
        assert "benefits" in components
        assert "cta" in components
    
    @pytest.mark.asyncio
    async def test_execution_with_different_strategies(
        self,
        sample_product_data,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test execution with different optimization strategies."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        strategies_to_test = [
            "benefit_driven",
            "problem_solution",
            "scarcity_urgency",
            "social_proof",
            "risk_reversal"
        ]
        
        for strategy in strategies_to_test:
            # Force strategy in plan
            plan = await agent.plan(sample_product_data)
            plan["optimization_strategy"] = strategy
            
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert result["strategy"] == strategy
            assert result["components"] is not None
    
    @pytest.mark.asyncio
    async def test_title_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test optimized title generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Mock successful JSON parsing
        mock_prompt_engine.create_system_message.return_value = "System message"
        mock_ollama_client.chat.return_value = type('MockResponse', (), {
            'response': '{"title": "Optimized Product Title", "score": 0.9}',
            'done': True
        })()
        
        title = await agent._generate_optimized_title(
            "Base Title",
            "Product description",
            {
                "target_audience": "general",
                "max_length": 80,
                "optimization_strategy": "benefit_driven"
            }
        )
        
        assert title is not None
        assert len(title) <= 80
        assert isinstance(title, str)
    
    @pytest.mark.asyncio
    async def test_subtitle_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test subtitle generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        subtitle = await agent._generate_subtitle(
            "Product content",
            {
                "max_length": 200,
                "optimization_strategy": "benefit_driven",
                "target_audience": "general"
            }
        )
        
        assert subtitle is not None
        assert len(subtitle) <= 200
        assert isinstance(subtitle, str)
    
    @pytest.mark.asyncio
    async def test_description_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test description generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        description = await agent._generate_description(
            "Product content",
            {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "max_length": 5000,
                "optimization_strategy": "benefit_driven",
                "target_audience": "general"
            }
        )
        
        assert description is not None
        assert len(description) <= 5000
        assert isinstance(description, str)
    
    @pytest.mark.asyncio
    async def test_features_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test features generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        features = await agent._generate_features(
            "Product content",
            {
                "max_features": 7,
                "max_length": 300,
                "optimization_strategy": "benefit_driven",
                "target_audience": "general"
            }
        )
        
        assert features is not None
        assert isinstance(features, list)
        assert len(features) <= 7
        assert all(isinstance(feature, str) for feature in features)
    
    @pytest.mark.asyncio
    async def test_benefits_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test benefits generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        benefits = await agent._generate_benefits(
            "Product content",
            {
                "max_benefits": 5,
                "max_length": 200,
                "optimization_strategy": "benefit_driven",
                "target_audience": "general"
            }
        )
        
        assert benefits is not None
        assert isinstance(benefits, list)
        assert len(benefits) <= 5
        assert all(isinstance(benefit, str) for benefit in benefits)
    
    @pytest.mark.asyncio
    async def test_cta_generation(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test call-to-action generation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        cta = await agent._generate_cta(
            "pdf_guide",
            {
                "optimization_strategy": "benefit_driven",
                "target_audience": "general"
            }
        )
        
        assert cta is not None
        assert isinstance(cta, str)
        assert len(cta) > 0
    
    @pytest.mark.asyncio
    async def test_listing_compilation(
        self,
        mock_prompt_engine
    ):
        """Test full listing compilation."""
        agent = ListingOptimizer()
        agent.prompt_engine = mock_prompt_engine
        
        components = {
            "title": "Test Product Title",
            "subtitle": "Test Subtitle",
            "description": "Test Description",
            "features": ["Feature 1", "Feature 2"],
            "benefits": ["Benefit 1", "Benefit 2"],
            "cta": "Get Started Now"
        }
        
        copy_structure = {
            "framework": "AIDA",
            "flow": "attention -> interest -> desire -> action",
            "focus": "benefits and outcomes"
        }
        
        listing = agent._compile_listing_copy(components, copy_structure)
        
        assert listing is not None
        assert "# Test Product Title" in listing
        assert "## Test Subtitle" in listing
        assert "Test Description" in listing
        assert "Feature 1" in listing
        assert "Benefit 1" in listing
        assert "Get Started Now" in listing
    
    @pytest.mark.asyncio
    async def test_character_limit_optimization(self):
        """Test character limit optimization."""
        agent = ListingOptimizer()
        
        # Test with text within limits
        short_text = "Short text within limits"
        limits = {"description": 100}
        
        optimized = agent._optimize_for_character_limits(short_text, limits)
        assert optimized == short_text
        
        # Test with text exceeding limits
        long_text = "This is a very long text that exceeds the character limit and needs to be truncated to fit within the specified constraints for testing purposes"
        limits = {"description": 50}
        
        optimized = agent._optimize_for_character_limits(long_text, limits)
        assert len(optimized) <= 50
    
    @pytest.mark.asyncio
    async def test_character_counting(self):
        """Test character counting functionality."""
        agent = ListingOptimizer()
        
        test_listing = """# Test Title
## Test Subtitle
This is the description content with some text to count characters.

• Feature 1
• Feature 2

**Get Started Now**
"""
        
        counts = agent._count_characters(test_listing)
        
        assert counts["total"] > 0
        assert counts["title"] > 0
        assert counts["subtitle"] > 0
        assert counts["description"] > 0
        assert counts["features"] > 0
        assert counts["cta"] > 0
    
    @pytest.mark.asyncio
    async def test_validation_success(
        self,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test successful listing validation."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Create valid result
        result = {
            "full_listing": "Valid listing content with proper structure and all required elements",
            "character_counts": {
                "title": 50,
                "subtitle": 100,
                "description": 1000,
                "features": 200,
                "benefits": 150,
                "cta": 20
            },
            "strategy": "benefit_driven"
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is True
        assert validation["score"] >= 0.8
        assert len(validation["validation_results"]) == 5
        assert len(validation["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_validation_character_limit_violations(self):
        """Test validation with character limit violations."""
        agent = ListingOptimizer()
        
        result = {
            "full_listing": "Listing with character limit violations",
            "character_counts": {
                "title": 100,  # Exceeds 80 limit
                "subtitle": 300,  # Exceeds 200 limit
                "description": 6000,  # Exceeds 5000 limit
                "features": 400,  # Exceeds 300 limit
                "benefits": 300,  # Exceeds 200 limit
                "cta": 20
            },
            "strategy": "benefit_driven"
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("exceeds limit" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_validation_missing_sections(self):
        """Test validation with missing sections."""
        agent = ListingOptimizer()
        
        # Create listing without CTA
        result = {
            "full_listing": "Listing without clear call to action",
            "character_counts": {
                "title": 50,
                "subtitle": 100,
                "description": 1000,
                "features": 200,
                "benefits": 150,
                "cta": 0  # Missing CTA
            },
            "strategy": "benefit_driven"
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("call-to-action" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_validation_kade_persona_violations(self):
        """Test validation with Kade persona violations."""
        agent = ListingOptimizer()
        
        result = {
            "full_listing": "I think this is a great product. In my opinion, you should buy it. Personally, I believe this will help you. As an AI, I can assure you this is high quality.",
            "character_counts": {
                "title": 50,
                "subtitle": 100,
                "description": 1000,
                "features": 200,
                "benefits": 150,
                "cta": 20
            },
            "strategy": "benefit_driven"
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("persona" in error for error in validation["errors"])
        assert any("personal anecdote" in error for error in validation["errors"])
        assert any("AI identity" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_content_analysis(self):
        """Test content analysis functionality."""
        agent = ListingOptimizer()
        
        # Test with rich content
        rich_content = "This comprehensive guide provides numerous benefits and helps you solve common problems. You'll discover new advantages and master key skills to improve your workflow."
        
        analysis = await agent._analyze_content_for_optimization(rich_content)
        
        assert analysis is not None
        assert analysis["word_count"] > 0
        assert analysis["optimization_potential"] is True
        assert analysis["benefit_count"] > 0
        assert analysis["problem_count"] > 0
        assert len(analysis["keywords"]) > 0
        assert analysis["complexity_score"] > 0
    
    @pytest.mark.asyncio
    async def test_strategy_selection(self):
        """Test optimization strategy selection."""
        agent = ListingOptimizer()
        
        # Test high-priced product
        strategy = agent._select_optimization_strategy(
            "pdf_guide",
            "general",
            5000,  # $50
            {"optimization_potential": False}
        )
        assert strategy == "premium_positioning"
        
        # Test beginner audience
        strategy = agent._select_optimization_strategy(
            "pdf_guide",
            "beginner",
            999,   # $9.99
            {"optimization_potential": False}
        )
        assert strategy == "educational_approach"
        
        # Test with optimization potential
        strategy = agent._select_optimization_strategy(
            "pdf_guide",
            "general",
            999,   # $9.99
            {"optimization_potential": True}
        )
        assert strategy == "benefit_driven"
    
    @pytest.mark.asyncio
    async def test_copy_structure_configuration(self):
        """Test copy structure configuration for different strategies."""
        agent = ListingOptimizer()
        
        strategies_to_test = [
            "benefit_driven",
            "problem_solution",
            "scarcity_urgency",
            "social_proof",
            "risk_reversal",
            "premium_positioning",
            "value_proposition",
            "educational_approach",
            "expert_positioning",
            "basic"
        ]
        
        for strategy in strategies_to_test:
            structure = agent._get_copy_structure(strategy)
            
            assert structure is not None
            assert "framework" in structure
            assert "flow" in structure
            assert "focus" in structure
            assert structure["framework"] == "AIDA"
            assert "attention -> interest -> desire -> action" in structure["flow"]
    
    @pytest.mark.asyncio
    async def test_duration_estimation(self):
        """Test duration estimation for different strategies."""
        agent = ListingOptimizer()
        
        content_length = 2000
        
        strategies_to_test = [
            ("basic", 1.0),
            ("benefit_driven", 1.2),
            ("problem_solution", 1.3),
            ("scarcity_urgency", 1.1),
            ("social_proof", 1.4),
            ("risk_reversal", 1.3),
            ("premium_positioning", 1.5),
            ("value_proposition", 1.4),
            ("educational_approach", 1.6),
            ("expert_positioning", 1.7)
        ]
        
        for strategy, expected_multiplier in strategies_to_test:
            duration = agent._estimate_optimization_duration(content_length, strategy)
            expected_duration = int(content_length * 0.3 * expected_multiplier)
            assert duration == expected_duration
    
    @pytest.mark.asyncio
    async def test_model_selection(self):
        """Test LLM model selection for optimization."""
        agent = ListingOptimizer()
        
        model = agent._select_model_for_optimization()
        assert model == "llama2:7b"  # Should use smaller model for creative tasks
    
    @pytest.mark.asyncio
    async def test_keyword_extraction(self):
        """Test keyword extraction from content."""
        agent = ListingOptimizer()
        
        content = "This comprehensive guide covers digital product creation, marketing strategies, and sales optimization techniques for entrepreneurs and small business owners."
        
        keywords = agent._extract_keywords(content)
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert all(isinstance(keyword, str) for keyword in keywords)
        assert len(keywords) <= 10  # Limited to top 10
    
    @pytest.mark.asyncio
    async def test_recommendations_generation(self):
        """Test recommendations generation from validation results."""
        agent = ListingOptimizer()
        
        # Test with character limit violations
        validation_results = {
            "character_limits": {
                "valid": False,
                "errors": ["Title exceeds limit: 100/80"]
            },
            "cta_presence": {
                "valid": False,
                "errors": ["No clear call-to-action"]
            }
        }
        
        recommendations = agent._generate_recommendations(validation_results)
        
        assert len(recommendations) > 0
        assert any("Reduce text" in rec for rec in recommendations)
        assert any("call-to-action" in rec for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_next_steps_generation(self):
        """Test next steps generation from validation results."""
        agent = ListingOptimizer()
        
        # Test with successful validation
        next_steps = agent._generate_next_steps(True)
        
        assert len(next_steps) > 0
        assert any("Gumroad" in step for step in next_steps)
        assert any("publishing" in step for step in next_steps)
        
        # Test with failed validation
        next_steps = agent._generate_next_steps(False)
        
        assert len(next_steps) > 0
        assert any("fix" in step for step in next_steps)
        assert any("review" in step for step in next_steps)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_product_data):
        """Test error handling in various scenarios."""
        agent = ListingOptimizer()
        
        # Test with missing required fields
        invalid_request = {
            "product_type": "pdf_guide"
            # Missing title and description
        }
        
        plan = await agent.plan(invalid_request)
        
        # Should still create plan but with limited data
        assert plan is not None
        assert plan["product_title"] == ""
        assert plan["content"] == ""
    
    @pytest.mark.asyncio
    async def test_logging(self, sample_product_data, log_capture):
        """Test logging functionality."""
        agent = ListingOptimizer()
        
        # Start capturing logs
        log_capture.start()
        
        # Execute plan and execution
        plan = await agent.plan(sample_product_data)
        
        # Stop capturing logs
        log_capture.stop()
        
        # Check that logs were captured
        messages = log_capture.get_messages("INFO")
        assert len(messages) > 0
        
        # Check for specific log messages
        info_messages = [msg for msg in messages if "Listing optimization plan created" in msg["message"]]
        assert len(info_messages) > 0
    
    @pytest.mark.asyncio
    async def test_report_generation(
        self,
        sample_product_data,
        mock_ollama_client,
        mock_prompt_engine
    ):
        """Test report generation from execution and validation results."""
        agent = ListingOptimizer()
        agent.ollama_client = mock_ollama_client
        agent.prompt_engine = mock_prompt_engine
        
        # Create execution result
        execution_result = {
            "optimization_id": "test-opt-123",
            "components": {
                "title": "Test Title",
                "description": "Test Description"
            },
            "full_listing": "Test listing content",
            "character_counts": {"total": 500},
            "strategy": "benefit_driven",
            "success": True
        }
        
        # Create validation result
        validation_result = {
            "valid": True,
            "score": 0.9,
            "validation_results": {}
        }
        
        report = await agent.report({
            "optimization_id": execution_result["optimization_id"],
            "result": execution_result,
            "validation_results": validation_result
        })
        
        assert report["agent_id"] == agent.agent_id
        assert report["agent_name"] == agent.agent_name
        assert report["optimization_id"] == "test-opt-123"
        assert report["execution_summary"] is not None
        assert report["validation_summary"] is not None
        assert report["recommendations"] is not None
        assert report["next_steps"] is not None
        assert report["metrics"] is not None
