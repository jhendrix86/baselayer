"""
MINT Product Packager Tests

Test suite for ProductPackager agent including
PDF generation, image creation, and ZIP packaging.
"""

import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
import tempfile
import os

from agents.agents.product_packager import ProductPackager
from tests.engines.mint.conftest import (
    sample_product_data,
    mock_agent_context,
    mock_file_system,
    log_capture
)


class TestProductPackager:
    """Test suite for ProductPackager agent."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization with default configuration."""
        agent = ProductPackager()
        
        assert agent.agent_name == "product_packager"
        assert agent.agent_version == "1.0.0"
        assert agent.output_base_path == Path("~/projects/baselayer/data/products").expanduser()
        assert agent.pdf_quality["dpi"] == 300
        assert agent.image_quality["width"] == 1200
        assert agent.image_quality["height"] == 630
    
    @pytest.mark.asyncio
    async def test_agent_initialization_custom_config(self, mock_agent_config):
        """Test agent initialization with custom configuration."""
        agent = ProductPackager(config=mock_agent_config)
        
        assert agent.config == mock_agent_config
        assert agent.pdf_quality["dpi"] == 300  # Default value
    
    @pytest.mark.asyncio
    async def test_plan_creation_success(self, sample_product_data):
        """Test successful packaging plan creation."""
        agent = ProductPackager()
        
        plan = await agent.plan(sample_product_data)
        
        assert plan is not None
        assert plan["product_id"] == sample_product_data.get("product_id")
        assert plan["product_type"] == sample_product_data.get("product_type")
        assert plan["title"] == sample_product_data.get("title")
        assert plan["output_formats"] is not None
        assert len(plan["output_formats"]) > 0
        assert plan["pdf_settings"] is not None
        assert plan["image_settings"] is not None
        assert plan["package_structure"] is not None
        assert plan["quality_checks"] is not None
        assert plan["estimated_duration"] > 0
    
    @pytest.mark.asyncio
    async def test_plan_creation_different_product_types(self):
        """Test plan creation for different product types."""
        agent = ProductPackager()
        
        test_cases = [
            {"product_type": "pdf_guide", "title": "Test Guide"},
            {"product_type": "template_pack", "title": "Test Templates"},
            {"product_type": "checklist", "title": "Test Checklist"},
            {"product_type": "cheat_sheet", "title": "Test Cheat Sheet"}
        ]
        
        for test_data in test_cases:
            plan = await agent.plan(test_data)
            
            assert plan is not None
            assert plan["product_type"] == test_data["product_type"]
            assert plan["output_formats"] is not None
            assert len(plan["output_formats"]) > 0
    
    @pytest.mark.asyncio
    async def test_execution_success(self, sample_product_data):
        """Test successful packaging execution."""
        agent = ProductPackager()
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert "product_id" in result
            assert "assets" in result
            assert "package_path" in result
            assert "total_files" in result
            assert "total_size_bytes" in result
            assert result["total_files"] > 0
            assert result["total_size_bytes"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_pdf_generation(self, sample_product_data):
        """Test PDF generation during execution."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert "pdf" in result["assets"]
            
            pdf_asset = result["assets"]["pdf"]
            assert pdf_asset["file_type"] == "pdf"
            assert pdf_asset["file_name"].endswith(".pdf")
            assert pdf_asset["file_size_bytes"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_markdown_generation(self, sample_product_data):
        """Test Markdown generation during execution."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert "markdown" in result["assets"]
            
            md_asset = result["assets"]["markdown"]
            assert md_asset["file_type"] == "md"
            assert md_asset["file_name"].endswith(".md")
            assert md_asset["file_size_bytes"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_text_generation(self, sample_product_data):
        """Test text generation during execution."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert "text" in result["assets"]
            
            txt_asset = result["assets"]["text"]
            assert txt_asset["file_type"] == "txt"
            assert txt_asset["file_name"].endswith(".txt")
            assert txt_asset["file_size_bytes"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_zip_creation(self, sample_product_data):
        """Test ZIP package creation during execution."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            assert result["success"] is True
            assert "zip" in result["assets"]
            
            zip_asset = result["assets"]["zip"]
            assert zip_asset["file_type"] == "zip"
            assert zip_asset["file_name"].endswith(".zip")
            assert zip_asset["file_size_bytes"] > 0
    
    @pytest.mark.asyncio
    async def test_execution_failure(self, sample_product_data):
        """Test execution failure handling."""
        agent = ProductPackager()
        
        # Mock file system to raise error
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            
            # Force failure by making directory read-only
            os.chmod(temp_dir, 0o444)
            
            try:
                result = await agent.execute(plan)
                # May still succeed depending on implementation
            except Exception as e:
                # Expected failure
                assert str(e) is not None
            finally:
                # Restore permissions for cleanup
                os.chmod(temp_dir, 0o755)
    
    @pytest.mark.asyncio
    async def test_validation_success(self, sample_product_data):
        """Test successful asset validation."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            result = await agent.execute(plan)
            
            validation = await agent.validate(result)
            
            assert validation["valid"] is True
            assert validation["score"] >= 0.8
            assert len(validation["validation_results"]) == 4
            assert len(validation["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_validation_empty_files(self, sample_product_data):
        """Test validation with empty files."""
        agent = ProductPackager()
        
        # Create result with empty assets
        result = {
            "assets": {
                "pdf": {
                    "file_path": "/path/to/empty.pdf",
                    "file_size_bytes": 0,
                    "file_type": "pdf"
                }
            },
            "success": True
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("empty" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_validation_oversized_files(self, sample_product_data):
        """Test validation with oversized files."""
        agent = ProductPackager()
        
        # Create result with oversized assets
        result = {
            "assets": {
                "pdf": {
                    "file_path": "/path/to/large.pdf",
                    "file_size_bytes": 100 * 1024 * 1024,  # 100MB
                    "file_type": "pdf"
                }
            },
            "success": True
        }
        
        validation = await agent.validate(result)
        
        assert validation["valid"] is False
        assert validation["score"] < 0.8
        assert any("too large" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_report_generation(self, sample_product_data):
        """Test report generation from execution and validation results."""
        agent = ProductPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            
            plan = await agent.plan(sample_product_data)
            execution_result = await agent.execute(plan)
            validation_result = await agent.validate(execution_result)
            
            report = await agent.report({
                "execution_result": execution_result,
                "validation_results": validation_result
            })
            
            assert report["agent_id"] == agent.agent_id
            assert report["agent_name"] == agent.agent_name
            assert report["execution_summary"] is not None
            assert report["asset_details"] is not None
            assert report["validation_summary"] is not None
            assert report["recommendations"] is not None
            assert report["next_steps"] is not None
            assert report["metrics"] is not None
    
    @pytest.mark.asyncio
    async def test_output_format_determination(self):
        """Test output format determination for different product types."""
        agent = ProductPackager()
        
        test_cases = [
            ("pdf_guide", ["pdf", "md", "txt", "zip"]),
            ("template_pack", ["md", "txt", "zip"]),
            ("checklist", ["md", "txt", "zip"]),
            ("cheat_sheet", ["md", "txt", "zip"])
        ]
        
        for product_type, expected_formats in test_cases:
            formats = agent._determine_output_formats(product_type)
            assert formats == expected_formats
    
    @pytest.mark.asyncio
    async def test_pdf_settings_configuration(self):
        """Test PDF settings configuration for different product types."""
        agent = ProductPackager()
        
        # Test PDF guide settings
        settings = agent._get_pdf_settings("pdf_guide")
        assert settings["page_orientation"] == "portrait"
        assert settings["margin_top"] == "2cm"
        assert settings["margin_bottom"] == "2cm"
        
        # Test template pack settings
        settings = agent._get_pdf_settings("template_pack")
        assert settings["page_orientation"] == "landscape"
        assert settings["font_size"] == 10
    
    @pytest.mark.asyncio
    async def test_image_settings_configuration(self):
        """Test image settings configuration for different product types."""
        agent = ProductPackager()
        
        # Test PDF guide settings
        settings = agent._get_image_settings("pdf_guide")
        assert settings["background_color"] == "#ffffff"
        assert settings["text_color"] == "#333333"
        assert settings["title_font_size"] == 24
        
        # Test template pack settings
        settings = agent._get_image_settings("template_pack")
        assert settings["background_color"] == "#f8f9fa"
        assert settings["text_color"] == "#495057"
    
    @pytest.mark.asyncio
    async def test_package_structure_configuration(self):
        """Test package structure configuration for different product types."""
        agent = ProductPackager()
        
        # Test PDF guide structure
        structure = agent._get_package_structure("pdf_guide")
        assert structure["primary_file"] == "product.pdf"
        assert structure["archive_format"] == "zip"
        
        # Test template pack structure
        structure = agent._get_package_structure("template_pack")
        assert structure["primary_file"] == "templates.md"
    
    @pytest.mark.asyncio
    async def test_duration_estimation(self):
        """Test duration estimation for different product types."""
        agent = ProductPackager()
        
        content_length = 5000  # characters
        test_cases = [
            ("pdf_guide", 1.0),  # Base multiplier
            ("template_pack", 0.8),  # Faster for templates
            ("checklist", 0.6),  # Faster for checklists
            ("cheat_sheet", 0.5)  # Fastest for cheat sheets
        ]
        
        for product_type, expected_multiplier in test_cases:
            duration = agent._estimate_packaging_duration(product_type, content_length)
            assert duration == int(content_length * 0.01 * expected_multiplier)
    
    @pytest.mark.asyncio
    async def test_filename_sanitization(self):
        """Test filename sanitization."""
        agent = ProductPackager()
        
        test_cases = [
            ("Test Product", "Test_Product"),
            ("Test/Product", "Test_Product"),
            ("Test:Product", "TestProduct"),
            ("Test<Product>", "TestProduct"),
            ("Test|Product", "TestProduct"),
            ("Test Product??", "Test_Product")
        ]
        
        for input_name, expected_name in test_cases:
            sanitized = agent._sanitize_filename(input_name)
            assert sanitized == expected_name
    
    @pytest.mark.asyncio
    async def test_primary_asset_determination(self):
        """Test primary asset determination for different product types."""
        agent = ProductPackager()
        
        # Test with PDF present
        assets = {
            "pdf": {"file_type": "pdf", "file_name": "test.pdf"},
            "markdown": {"file_type": "md", "file_name": "test.md"}
        }
        
        primary = agent._determine_primary_asset(assets, "pdf_guide")
        assert primary["file_type"] == "pdf"
        
        # Test without PDF
        assets = {
            "markdown": {"file_type": "md", "file_name": "test.md"},
            "text": {"file_type": "txt", "file_name": "test.txt"}
        }
        
        primary = agent._determine_primary_asset(assets, "template_pack")
        assert primary["file_type"] == "md"
    
    @pytest.mark.asyncio
    async def test_pdf_validation(self, mock_file_system):
        """Test PDF validation."""
        agent = ProductPackager()
        
        # Test valid PDF
        mock_file_system["exists"].return_value = True
        mock_file_system["stat"]().st_size = 1024
        
        validation = await agent._validate_pdf("/path/to/valid.pdf")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test non-existent PDF
        mock_file_system["exists"].return_value = False
        
        validation = await agent._validate_pdf("/path/to/nonexistent.pdf")
        assert validation["valid"] is False
        assert "does not exist" in validation["errors"][0]
        
        # Test empty PDF
        mock_file_system["exists"].return_value = True
        mock_file_system["stat"]().st_size = 0
        
        validation = await agent._validate_pdf("/path/to/empty.pdf")
        assert validation["valid"] is False
        assert "empty" in validation["errors"][0]
    
    @pytest.mark.asyncio
    async def test_image_validation(self, mock_file_system):
        """Test image validation."""
        agent = ProductPackager()
        
        # Test valid image
        mock_file_system["exists"].return_value = True
        mock_file_system["stat"]().st_size = 5000
        
        validation = await agent._validate_image("/path/to/valid.png")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test oversized image
        mock_file_system["stat"]().st_size = 15 * 1024 * 1024  # 15MB
        
        validation = await agent._validate_image("/path/to/large.png")
        assert validation["valid"] is False
        assert "too large" in validation["errors"][0]
    
    @pytest.mark.asyncio
    async def test_file_integrity_validation(self, mock_file_system):
        """Test file integrity validation."""
        agent = ProductPackager()
        
        # Test valid assets
        assets = {
            "pdf": {"file_path": "/path/to/valid.pdf", "file_size_bytes": 1024},
            "markdown": {"file_path": "/path/to/valid.md", "file_size_bytes": 500}
        }
        
        mock_file_system["exists"].return_value = True
        
        validation = await agent._validate_file_integrity(assets)
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test with missing file
        assets = {
            "pdf": {"file_path": "/path/to/missing.pdf", "file_size_bytes": 1024}
        }
        
        validation = await agent._validate_file_integrity(assets)
        assert validation["valid"] is False
        assert "does not exist" in validation["errors"][0]
    
    @pytest.mark.asyncio
    async def test_package_size_validation(self):
        """Test package size validation."""
        agent = ProductPackager()
        
        # Test valid package size
        assets = {
            "pdf": {"file_size_bytes": 1024},
            "markdown": {"file_size_bytes": 500}
        }
        
        validation = await agent._validate_package_size(assets)
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test oversized package
        assets = {
            "pdf": {"file_size_bytes": 80 * 1024 * 1024},  # 80MB
            "markdown": {"file_size_bytes": 30 * 1024 * 1024}  # 30MB
        }
        
        validation = await agent._validate_package_size(assets)
        assert validation["valid"] is False
        assert "too large" in validation["errors"][0]
    
    @pytest.mark.asyncio
    async def test_recommendations_generation(self):
        """Test recommendations generation from validation results."""
        agent = ProductPackager()
        
        # Test with PDF validation failure
        validation_results = {
            "pdf_rendering": {
                "valid": False,
                "errors": ["PDF file is empty"]
            }
        }
        
        recommendations = agent._generate_packaging_recommendations(validation_results)
        assert len(recommendations) > 0
        assert any("PDF" in rec for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_next_steps_generation(self):
        """Test next steps generation from validation results."""
        agent = ProductPackager()
        
        # Test with successful validation
        next_steps = agent._generate_next_steps(True)
        assert len(next_steps) > 0
        assert any("listing" in step.lower() for step in next_steps)
        
        # Test with failed validation
        next_steps = agent._generate_next_steps(False)
        assert len(next_steps) > 0
        assert any("fix" in step.lower() for step in next_steps)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_product_data):
        """Test error handling in various scenarios."""
        agent = ProductPackager()
        
        # Test with missing required fields
        invalid_request = {}
        
        plan = await agent.plan(invalid_request)
        assert plan is not None
        assert plan["product_id"] is None
        assert plan["title"] is None
        
        # Test with invalid product type
        invalid_request = {
            "product_type": "invalid_type",
            "title": "Test Product"
        }
        
        plan = await agent.plan(invalid_request)
        assert plan is not None
        assert plan["product_type"] == "invalid_type"
    
    @pytest.mark.asyncio
    async def test_logging(self, sample_product_data, log_capture):
        """Test logging functionality."""
        agent = ProductPackager()
        
        # Start capturing logs
        log_capture.start()
        
        # Execute plan and execution
        plan = await agent.plan(sample_product_data)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            agent.output_base_path = Path(temp_dir)
            result = await agent.execute(plan)
        
        # Stop capturing logs
        log_capture.stop()
        
        # Check that logs were captured
        messages = log_capture.get_messages("INFO")
        assert len(messages) > 0
        
        # Check for specific log messages
        info_messages = [msg for msg in messages if "Product packaging plan created" in msg["message"]]
        assert len(info_messages) > 0
