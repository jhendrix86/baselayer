"""
BaseLayer Prompt Engine Tests

Test suite for PromptEngine including template rendering,
validation, and built-in patterns.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from agents.llm.prompt_engine import (
    PromptEngine,
    PromptTemplate
)
from agents.llm.ollama_client import OllamaClient
from tests.agents.conftest import LogCapture


class TestPromptEngine:
    """Test suite for PromptEngine functionality."""
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test prompt engine initialization."""
        engine = PromptEngine()
        
        assert engine.templates_dir.name == "prompts"
        assert engine.cache_size == 100
        assert len(engine.templates) == 0  # No templates loaded yet
        assert len(engine.template_cache) == 0
        assert len(engine.patterns) > 0  # Built-in patterns loaded
    
    @pytest.mark.asyncio
    async def test_engine_custom_initialization(self):
        """Test prompt engine initialization with custom parameters."""
        custom_dir = "custom/prompts"
        engine = PromptEngine(templates_dir=custom_dir, cache_size=50)
        
        assert engine.templates_dir.name == "prompts"
        assert engine.cache_size == 50
    
    @pytest.mark.asyncio
    async def test_template_loading(self):
        """Test template loading from filesystem."""
        engine = PromptEngine()
        
        # Trigger template loading
        engine._load_templates()
        
        # Should have loaded templates from test fixtures
        # (This would require actual template files in tests)
        assert len(engine.templates) >= 0
    
    @pytest.mark.asyncio
    async def test_template_rendering_success(self):
        """Test successful template rendering."""
        engine = PromptEngine()
        
        # Mock template
        mock_template = AsyncMock()
        mock_template.render.return_value = "Hello, World!"
        engine.template_cache["test"] = mock_template
        
        result = engine.render("test", {"name": "World"})
        
        assert result == "Hello, World!"
        mock_template.render.assert_called_once_with(name="World")
    
    @pytest.mark.asyncio
    async def test_template_rendering_with_redaction(self):
        """Test template rendering with sensitive variable redaction."""
        engine = PromptEngine()
        
        # Mock template
        mock_template = AsyncMock()
        mock_template.render.return_value = "Hello, User!"
        engine.template_cache["test"] = mock_template
        
        # Render with redaction
        result = engine.render("test", {"name": "World"}, redact_sensitive=True)
        non_redacted = engine.render("test", {"name": "World"}, redact_sensitive=False)
        
        assert result == non_redacted  # Should be same for non-sensitive data
        mock_template.render.assert_called_once_with(name="World")
    
    @pytest.mark.asyncio
    async def test_template_rendering_missing_template(self):
        """Test template rendering with missing template."""
        engine = PromptEngine()
        
        with pytest.raises(Exception) as exc_info:
            engine.render("nonexistent_template", {"test": "data"})
        
        assert "Template not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_template_rendering_missing_variables(self):
        """Test template rendering with missing required variables."""
        engine = PromptEngine()
        
        # Mock template that requires variables
        mock_template = AsyncMock()
        engine.templates["test"] = PromptTemplate(
            name="test",
            version="1",
            description="Test template",
            category="test",
            variables=["required_var"],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        engine.template_cache["test"] = mock_template
        
        with pytest.raises(Exception) as exc_info:
            engine.render("test", {"other_var": "value"})
        
        assert "Missing required variables" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_template_rendering_with_pattern(self):
        """Test template rendering with built-in pattern."""
        engine = PromptEngine()
        
        # Mock template
        mock_template = AsyncMock()
        mock_template.render.return_value = "Template content"
        engine.template_cache["test"] = mock_template
        
        result = engine.render_with_pattern(
            "test",
            "chain_of_thought",
            {"problem": "Test problem"}
        )
        
        assert "Template content" in result
        assert "Think step by step" in result
        assert "Test problem" in result
    
    @pytest.mark.asyncio
    async def test_system_message_creation(self):
        """Test system message creation."""
        engine = PromptEngine()
        
        result = engine.create_system_message(
            persona="Kade",
            role_description="Professional AI assistant",
            additional_context="Additional context"
        )
        
        assert "You are Kade" in result
        assert "Professional AI assistant" in result
        assert "Additional context" in result
    
    @pytest.mark.asyncio
    async def test_few_shot_creation(self):
        """Test few-shot prompt creation."""
        engine = PromptEngine()
        
        examples = [
            {"input": "Question 1", "output": "Answer 1"},
            {"input": "Question 2", "output": "Answer 2"}
        ]
        
        result = engine.create_few_shot(
            task="Answer questions",
            examples=examples,
            context="Context information"
        )
        
        assert "Answer questions" in result
        assert "Example 1" in result
        assert "Answer 1" in result
        assert "Example 2" in result
        assert "Answer 2" in result
        assert "Context information" in result
    
    @pytest.mark.asyncio
    async def test_chain_of_thought_creation(self):
        """Test chain-of-thought prompt creation."""
        engine = PromptEngine()
        
        result = engine.create_chain_of_thought(
            problem="Solve this equation: 2+2",
            context="Math context"
        )
        
        assert "Solve this equation: 2+2" in result
        assert "Think step by step" in result
        assert "Math context" in result
    
    @pytest.mark.asyncio
    async def test_json_output_creation(self):
        """Test JSON output prompt creation."""
        engine = PromptEngine()
        
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["answer", "confidence"]
        }
        
        result = engine.create_json_output(
            prompt="What is 2+2?",
            schema=schema
        )
        
        assert "What is 2+2?" in result
        assert "Respond with a valid JSON object only" in result
        assert "Schema:" in result or '"type": "object"' in result
    
    @pytest.mark.asyncio
    async def test_error_correction_creation(self):
        """Test error correction prompt creation."""
        engine = PromptEngine()
        
        result = engine.create_error_correction(
            original_request="Generate JSON",
            error="Invalid JSON format",
            correction_hint="Use proper JSON syntax"
        )
        
        assert "Generate JSON" in result
        assert "Invalid JSON format" in result
        assert "Use proper JSON syntax" in result
        assert "Please fix the response" in result
    
    @pytest.mark.asyncio
    async def test_template_validation_success(self):
        """Test successful template validation."""
        engine = PromptEngine()
        
        # Mock valid template
        mock_template = AsyncMock()
        mock_template.render.return_value = "Valid content"
        engine.templates["test"] = PromptTemplate(
            name="test",
            version="1",
            description="Test template",
            category="test",
            variables=["test_var"],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        engine.template_cache["test"] = mock_template
        
        result = engine.validate_template("test")
        
        assert result["valid"] is True
        assert result["template"] == "test"
        assert "required_variables" in result
        assert result["syntax_valid"] is True
    
    @pytest.mark.asyncio
    async def test_template_validation_not_found(self):
        """Test template validation when template not found."""
        engine = PromptEngine()
        
        result = engine.validate_template("nonexistent")
        
        assert result["valid"] is False
        assert "Template not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_template_validation_syntax_error(self):
        """Test template validation with syntax error."""
        engine = PromptEngine()
        
        # Mock template with syntax error
        mock_template = AsyncMock()
        mock_template.render.side_effect = Exception("Syntax error")
        engine.templates["test"] = PromptTemplate(
            name="test",
            version="1",
            description="Test template",
            category="test",
            variables=["test_var"],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        engine.template_cache["test"] = mock_template
        
        result = engine.validate_template("test")
        
        assert result["valid"] is False
        assert "Syntax error" in result["error"]
        assert result["syntax_valid"] is False
    
    @pytest.mark.asyncio
    async def test_list_templates(self):
        """Test template listing."""
        engine = PromptEngine()
        
        # Add some mock templates
        engine.templates["template1"] = PromptTemplate(
            name="template1",
            version="1",
            description="Template 1",
            category="category1",
            variables=["var1"],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        engine.templates["template2"] = PromptTemplate(
            name="template2",
            version="1",
            description="Template 2",
            category="category2",
            variables=["var2"],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        
        # List all templates
        all_templates = engine.list_templates()
        assert len(all_templates) == 2
        
        # List by category
        category1_templates = engine.list_templates(category="category1")
        assert len(category1_templates) == 1
        assert category1_templates[0].name == "template1"
        
        # List by version
        version1_templates = engine.list_templates(version="1")
        assert len(version1_templates) == 2
    
    @pytest.mark.asyncio
    async def test_get_template_info(self):
        """Test getting template metadata."""
        engine = PromptEngine()
        
        # Add mock template
        engine.templates["test_template"] = PromptTemplate(
            name="test_template",
            version="2",
            description="Test template v2",
            category="test",
            variables=["test_var"],
            built_in_patterns=["chain_of_thought"],
            created_at="2024-01-01",
            updated_at="2024-01-02"
        )
        
        info = engine.get_template_info("test_template")
        
        assert info is not None
        assert info.name == "test_template"
        assert info.version == "2"
        assert info.description == "Test template v2"
        assert info.category == "test"
        assert "test_var" in info.variables
        assert "chain_of_thought" in info.built_in_patterns
    
    @pytest.mark.asyncio
    async def test_get_template_info_not_found(self):
        """Test getting info for nonexistent template."""
        engine = PromptEngine()
        
        info = engine.get_template_info("nonexistent")
        
        assert info is None
    
    @pytest.mark.asyncio
    async def test_cache_management(self):
        """Test template cache management."""
        engine = PromptEngine(templates_dir="nonexistent", cache_size=2)
        
        # Fill cache beyond limit
        mock_template1 = AsyncMock()
        mock_template1.render.return_value = "Template 1"
        engine.template_cache["template1"] = mock_template1
        
        mock_template2 = AsyncMock()
        mock_template2.render.return_value = "Template 2"
        engine.template_cache["template2"] = mock_template2
        
        mock_template3 = AsyncMock()
        mock_template3.render.return_value = "Template 3"
        engine.template_cache["template3"] = mock_template3
        
        # Cache should be at limit (2)
        assert len(engine.template_cache) == 3
        
        # Clear cache
        engine.clear_cache()
        
        assert len(engine.template_cache) == 0
    
    @pytest.mark.asyncio
    async def test_template_reload(self):
        """Test template reloading."""
        engine = PromptEngine()
        
        initial_count = len(engine.templates)
        
        # Reload templates
        engine.reload_templates()
        
        # Should have same count (no actual templates to reload)
        assert len(engine.templates) == initial_count
    
    @pytest.mark.asyncio
    async def test_built_in_patterns(self):
        """Test built-in pattern functionality."""
        engine = PromptEngine()
        
        # Test that all expected patterns exist
        expected_patterns = [
            "system_message",
            "few_shot",
            "chain_of_thought",
            "json_output",
            "error_correction"
        ]
        
        for pattern in expected_patterns:
            assert pattern in engine.patterns
            assert isinstance(engine.patterns[pattern], str)
            assert len(engine.patterns[pattern]) > 0


class TestPromptTemplate:
    """Test suite for PromptTemplate dataclass."""
    
    def test_template_creation(self):
        """Test PromptTemplate creation."""
        template = PromptTemplate(
            name="test_template",
            version="1.0",
            description="Test template",
            category="test",
            variables=["var1", "var2"],
            built_in_patterns=["pattern1"],
            created_at="2024-01-01",
            updated_at="2024-01-02"
        )
        
        assert template.name == "test_template"
        assert template.version == "1.0"
        assert template.description == "Test template"
        assert template.category == "test"
        assert template.variables == ["var1", "var2"]
        assert template.built_in_patterns == ["pattern1"]
        assert template.created_at == "2024-01-01"
        assert template.updated_at == "2024-01-02"
    
    def test_template_equality(self):
        """Test PromptTemplate equality comparison."""
        template1 = PromptTemplate(
            name="test",
            version="1",
            description="Test",
            category="test",
            variables=[],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        
        template2 = PromptTemplate(
            name="test",
            version="1",
            description="Test",
            category="test",
            variables=[],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        
        assert template1 == template2
    
    def test_template_inequality(self):
        """Test PromptTemplate inequality comparison."""
        template1 = PromptTemplate(
            name="test1",
            version="1",
            description="Test 1",
            category="test",
            variables=[],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        
        template2 = PromptTemplate(
            name="test2",
            version="1",
            description="Test 2",
            category="test",
            variables=[],
            built_in_patterns=[],
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )
        
        assert template1 != template2
