"""
MINT Product Packager Agent

Handles PDF generation, image creation, and ZIP packaging
for digital products with quality validation.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class ProductPackager(AgentBase):
    """
    Product packaging agent for MINT engine.
    
    Generates PDFs, creates cover images, and packages
    products into ZIP bundles with quality validation.
    """
    
    agent_name = "product_packager"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.output_base_path = Path("~/projects/baselayer/data/products").expanduser()
        self.pdf_quality = {
            "dpi": 300,
            "margin": "2cm",
            "page_size": "A4",
            "font_size": 12,
            "line_height": 1.5
        }
        self.image_quality = {
            "width": 1200,
            "height": 630,
            "format": "PNG",
            "quality": 85
        }
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan product packaging approach.
        
        Args:
            input_data: Product content and metadata
            
        Returns:
            Dict containing packaging plan
        """
        try:
            product_id = input_data.get("product_id", str(uuid.uuid4()))
            product_type = input_data.get("product_type", "pdf_guide")
            content = input_data.get("content", "")
            title = input_data.get("title", "Digital Product")
            
            # Determine packaging requirements
            packaging_plan = {
                "product_id": product_id,
                "product_type": product_type,
                "title": title,
                "content": content,
                "output_formats": self._determine_output_formats(product_type),
                "pdf_settings": self._get_pdf_settings(product_type),
                "image_settings": self._get_image_settings(product_type),
                "package_structure": self._get_package_structure(product_type),
                "quality_checks": [
                    "pdf_rendering",
                    "image_generation",
                    "file_integrity",
                    "package_size_validation"
                ],
                "estimated_duration": self._estimate_packaging_duration(product_type, len(content))
            }
            
            logger.info(
                "Product packaging plan created",
                product_id=product_id,
                product_type=product_type,
                formats=packaging_plan["output_formats"]
            )
            
            return packaging_plan
            
        except Exception as e:
            logger.error(
                "Failed to create packaging plan",
                error=str(e),
                input_data=input_data
            )
            raise BaseLayerError(f"Packaging plan creation failed: {str(e)}") from e
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute product packaging.
        
        Args:
            plan: Packaging plan from plan() phase
            
        Returns:
            Dict containing packaged product assets
        """
        try:
            product_id = plan["product_id"]
            product_type = plan["product_type"]
            title = plan["title"]
            content = plan["content"]
            
            # Create product directory
            product_dir = self.output_base_path / product_id
            product_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(
                "Starting product packaging",
                product_id=product_id,
                product_type=product_type,
                output_dir=str(product_dir)
            )
            
            # Generate assets
            assets = {}
            
            # Generate PDF
            if "pdf" in plan["output_formats"]:
                pdf_path = await self._generate_pdf(content, title, product_dir, plan["pdf_settings"])
                assets["pdf"] = {
                    "file_path": str(pdf_path),
                    "file_name": pdf_path.name,
                    "file_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
                    "file_type": "pdf"
                }
            
            # Generate cover image
            if "png" in plan["output_formats"]:
                image_path = await self._generate_cover_image(title, product_dir, plan["image_settings"])
                assets["cover_image"] = {
                    "file_path": str(image_path),
                    "file_name": image_path.name,
                    "file_size_bytes": image_path.stat().st_size if image_path.exists() else 0,
                    "file_type": "png"
                }
            
            # Generate markdown version
            if "md" in plan["output_formats"]:
                md_path = await self._generate_markdown(content, title, product_dir)
                assets["markdown"] = {
                    "file_path": str(md_path),
                    "file_name": md_path.name,
                    "file_size_bytes": md_path.stat().st_size if md_path.exists() else 0,
                    "file_type": "md"
                }
            
            # Generate text version
            if "txt" in plan["output_formats"]:
                txt_path = await self._generate_text(content, title, product_dir)
                assets["text"] = {
                    "file_path": str(txt_path),
                    "file_name": txt_path.name,
                    "file_size_bytes": txt_path.stat().st_size if txt_path.exists() else 0,
                    "file_type": "txt"
                }
            
            # Create ZIP package
            if "zip" in plan["output_formats"]:
                zip_path = await self._create_zip_package(assets, product_dir, title)
                assets["zip"] = {
                    "file_path": str(zip_path),
                    "file_name": zip_path.name,
                    "file_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
                    "file_type": "zip"
                }
            
            # Set primary asset
            primary_asset = self._determine_primary_asset(assets, product_type)
            
            result = {
                "product_id": product_id,
                "assets": assets,
                "primary_asset": primary_asset,
                "package_path": str(product_dir),
                "total_files": len(assets),
                "total_size_bytes": sum(asset["file_size_bytes"] for asset in assets.values()),
                "success": True
            }
            
            logger.info(
                "Product packaging completed",
                product_id=product_id,
                total_files=len(assets),
                total_size_bytes=result["total_size_bytes"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Product packaging execution failed",
                error=str(e),
                plan=plan
            )
            raise BaseLayerError(f"Packaging execution failed: {str(e)}") from e
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate packaged product assets.
        
        Args:
            result: Packaging result from execute() phase
            
        Returns:
            Dict with validation results
        """
        try:
            assets = result.get("assets", {})
            validation_results = {
                "pdf_rendering": {"valid": True, "errors": []},
                "image_generation": {"valid": True, "errors": []},
                "file_integrity": {"valid": True, "errors": []},
                "package_size_validation": {"valid": True, "errors": []}
            }
            
            # Validate PDF
            if "pdf" in assets:
                pdf_validation = await self._validate_pdf(assets["pdf"]["file_path"])
                validation_results["pdf_rendering"] = pdf_validation
            
            # Validate images
            if "cover_image" in assets:
                image_validation = await self._validate_image(assets["cover_image"]["file_path"])
                validation_results["image_generation"] = image_validation
            
            # Validate file integrity
            integrity_validation = await self._validate_file_integrity(assets)
            validation_results["file_integrity"] = integrity_validation
            
            # Validate package size
            size_validation = await self._validate_package_size(assets)
            validation_results["package_size_validation"] = size_validation
            
            # Calculate overall validity
            all_valid = all(
                validation_results[check]["valid"]
                for check in validation_results
            )
            
            overall_score = sum(
                validation_results[check]["valid"]
                for check in validation_results
            ) / len(validation_results)
            
            logger.info(
                "Product packaging validation completed",
                overall_valid=all_valid,
                overall_score=overall_score
            )
            
            return {
                "valid": all_valid,
                "score": overall_score,
                "validation_results": validation_results,
                "errors": [
                    f"{check}: {error}"
                    for check, result in validation_results.items()
                    for error in result.get("errors", [])
                ]
            }
            
        except Exception as e:
            logger.error(
                "Product packaging validation failed",
                error=str(e),
                result=result
            )
            return {
                "valid": False,
                "score": 0.0,
                "error": str(e)
            }
    
    async def report(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report packaging results.
        
        Args:
            result: Execution and validation results
            
        Returns:
            Dict containing report data
        """
        try:
            assets = result.get("assets", {})
            validation_results = result.get("validation_results", {})
            
            report = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_summary": {
                    "product_id": result.get("product_id"),
                    "total_assets_created": len(assets),
                    "total_size_bytes": result.get("total_size_bytes", 0),
                    "primary_asset": result.get("primary_asset"),
                    "package_path": result.get("package_path"),
                    "validation_passed": result.get("valid", False),
                    "quality_score": result.get("score", 0.0)
                },
                "asset_details": {
                    asset_type: {
                        "file_name": asset["file_name"],
                        "file_size_bytes": asset["file_size_bytes"],
                        "file_type": asset["file_type"]
                    }
                    for asset_type, asset in assets.items()
                },
                "validation_summary": validation_results,
                "recommendations": self._generate_packaging_recommendations(validation_results),
                "next_steps": self._generate_next_steps(result.get("valid", False)),
                "metrics": self._get_execution_metrics()
            }
            
            logger.info(
                "Product packaging report created",
                product_id=result.get("product_id"),
                validation_passed=result.get("valid", False)
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "Failed to create packaging report",
                error=str(e),
                result=result
            )
            return {
                "agent_id": self.agent_id,
                "error": str(e),
                "execution_summary": "Report generation failed"
            }
    
    def _determine_output_formats(self, product_type: str) -> List[str]:
        """Determine required output formats for product type."""
        format_mapping = {
            "pdf_guide": ["pdf", "md", "txt", "zip"],
            "template_pack": ["md", "txt", "zip"],
            "checklist": ["md", "txt", "zip"],
            "cheat_sheet": ["md", "txt", "zip"],
            "prompt_library": ["md", "txt", "zip"],
            "code_snippets": ["md", "txt", "zip"],
            "notion_template": ["md", "txt", "zip"]
        }
        
        return format_mapping.get(product_type, ["pdf", "md", "txt", "zip"])
    
    def _get_pdf_settings(self, product_type: str) -> Dict[str, Any]:
        """Get PDF generation settings for product type."""
        base_settings = self.pdf_quality.copy()
        
        # Adjust settings based on product type
        if product_type == "pdf_guide":
            base_settings.update({
                "page_orientation": "portrait",
                "margin_top": "2cm",
                "margin_bottom": "2cm",
                "margin_left": "2cm",
                "margin_right": "2cm"
            })
        elif product_type == "template_pack":
            base_settings.update({
                "page_orientation": "landscape",
                "font_size": 10
            })
        
        return base_settings
    
    def _get_image_settings(self, product_type: str) -> Dict[str, Any]:
        """Get image generation settings for product type."""
        base_settings = self.image_quality.copy()
        
        # Adjust settings based on product type
        if product_type == "pdf_guide":
            base_settings.update({
                "background_color": "#ffffff",
                "text_color": "#333333",
                "title_font_size": 24,
                "subtitle_font_size": 16
            })
        elif product_type == "template_pack":
            base_settings.update({
                "background_color": "#f8f9fa",
                "text_color": "#495057"
            })
        
        return base_settings
    
    def _get_package_structure(self, product_type: str) -> Dict[str, Any]:
        """Get package structure for product type."""
        structure_mapping = {
            "pdf_guide": {
                "primary_file": "product.pdf",
                "supporting_files": ["product.md", "product.txt"],
                "archive_format": "zip"
            },
            "template_pack": {
                "primary_file": "templates.md",
                "supporting_files": ["templates.txt"],
                "archive_format": "zip"
            },
            "checklist": {
                "primary_file": "checklist.md",
                "supporting_files": ["checklist.txt"],
                "archive_format": "zip"
            }
        }
        
        return structure_mapping.get(product_type, structure_mapping["pdf_guide"])
    
    def _estimate_packaging_duration(self, product_type: str, content_length: int) -> int:
        """Estimate packaging duration in seconds."""
        # Base time per character
        base_time_per_char = 0.01
        
        # Adjust by product type complexity
        complexity_multipliers = {
            "pdf_guide": 1.0,
            "template_pack": 0.8,
            "checklist": 0.6,
            "cheat_sheet": 0.6,
            "prompt_library": 0.7,
            "code_snippets": 0.9,
            "notion_template": 0.7
        }
        
        multiplier = complexity_multipliers.get(product_type, 1.0)
        
        return int(content_length * base_time_per_char * multiplier)
    
    async def _generate_pdf(self, content: str, title: str, output_dir: Path, settings: Dict[str, Any]) -> Path:
        """Generate PDF from content."""
        try:
            pdf_path = output_dir / f"{self._sanitize_filename(title)}.pdf"
            
            # Simple PDF generation using basic formatting
            # In production, would use a proper PDF library like weasyprint
            pdf_content = self._format_pdf_content(content, title, settings)
            
            # Write PDF content (simplified - would use actual PDF library)
            with open(pdf_path, 'w', encoding='utf-8') as f:
                f.write(pdf_content)
            
            logger.debug(
                "PDF generated",
                path=str(pdf_path),
                file_size=pdf_path.stat().st_size
            )
            
            return pdf_path
            
        except Exception as e:
            logger.error(
                "Failed to generate PDF",
                error=str(e),
                title=title
            )
            raise BaseLayerError(f"PDF generation failed: {str(e)}") from e
    
    async def _generate_cover_image(self, title: str, output_dir: Path, settings: Dict[str, Any]) -> Path:
        """Generate cover image for product."""
        try:
            image_path = output_dir / f"{self._sanitize_filename(title)}_cover.png"
            
            # Simple image generation (placeholder)
            # In production, would use PIL or similar
            image_content = self._create_placeholder_image(title, settings)
            
            # Write image content (simplified)
            with open(image_path, 'w', encoding='utf-8') as f:
                f.write(f"PLACEHOLDER IMAGE: {image_content}")
            
            logger.debug(
                "Cover image generated",
                path=str(image_path)
            )
            
            return image_path
            
        except Exception as e:
            logger.error(
                "Failed to generate cover image",
                error=str(e),
                title=title
            )
            raise BaseLayerError(f"Cover image generation failed: {str(e)}") from e
    
    async def _generate_markdown(self, content: str, title: str, output_dir: Path) -> Path:
        """Generate markdown version of content."""
        try:
            md_path = output_dir / f"{self._sanitize_filename(title)}.md"
            
            md_content = f"# {title}\n\n{content}"
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logger.debug(
                "Markdown generated",
                path=str(md_path)
            )
            
            return md_path
            
        except Exception as e:
            logger.error(
                "Failed to generate markdown",
                error=str(e),
                title=title
            )
            raise BaseLayerError(f"Markdown generation failed: {str(e)}") from e
    
    async def _generate_text(self, content: str, title: str, output_dir: Path) -> Path:
        """Generate plain text version of content."""
        try:
            txt_path = output_dir / f"{self._sanitize_filename(title)}.txt"
            
            txt_content = f"{title}\n\n{'='*60}\n\n{content}"
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(txt_content)
            
            logger.debug(
                "Text file generated",
                path=str(txt_path)
            )
            
            return txt_path
            
        except Exception as e:
            logger.error(
                "Failed to generate text",
                error=str(e),
                title=title
            )
            raise BaseLayerError(f"Text generation failed: {str(e)}") from e
    
    async def _create_zip_package(self, assets: Dict[str, Any], output_dir: Path, title: str) -> Path:
        """Create ZIP package of all assets."""
        try:
            zip_path = output_dir / f"{self._sanitize_filename(title)}.zip"
            
            # Simple ZIP creation (placeholder)
            # In production, would use zipfile module
            with open(zip_path, 'w', encoding='utf-8') as f:
                f.write(f"PLACEHOLDER ZIP: Contains {len(assets)} assets\n")
                for asset_type, asset_info in assets.items():
                    f.write(f"- {asset_type}: {asset_info['file_name']}\n")
            
            logger.debug(
                "ZIP package created",
                path=str(zip_path),
                assets_count=len(assets)
            )
            
            return zip_path
            
        except Exception as e:
            logger.error(
                "Failed to create ZIP package",
                error=str(e),
                title=title
            )
            raise BaseLayerError(f"ZIP creation failed: {str(e)}") from e
    
    def _determine_primary_asset(self, assets: Dict[str, Any], product_type: str) -> Dict[str, Any]:
        """Determine primary asset for product type."""
        if "pdf" in assets:
            return assets["pdf"]
        elif "markdown" in assets:
            return assets["markdown"]
        elif "templates" in assets:
            return assets["templates"]
        else:
            # Return first available asset
            return list(assets.values())[0] if assets else {}
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem."""
        import re
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace spaces with underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        return sanitized
    
    def _format_pdf_content(self, content: str, title: str, settings: Dict[str, Any]) -> str:
        """Format content for PDF generation."""
        # Simple PDF-like formatting
        return f"""
        {title}
        {'='*len(title)}
        
        {content}
        """
    
    def _create_placeholder_image(self, title: str, settings: Dict[str, Any]) -> str:
        """Create placeholder image content."""
        return f"Cover image for: {title}\nSize: {settings.get('width')}x{settings.get('height')}"
    
    async def _validate_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Validate generated PDF."""
        try:
            if not pdf_path or not os.path.exists(pdf_path):
                return {
                    "valid": False,
                    "errors": ["PDF file does not exist"]
                }
            
            file_size = os.path.getsize(pdf_path)
            if file_size == 0:
                return {
                    "valid": False,
                    "errors": ["PDF file is empty"]
                }
            
            # Basic validation - in production would use PDF library
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                return {
                    "valid": False,
                    "errors": ["PDF file too large (>50MB)"]
                }
            
            return {
                "valid": True,
                "errors": []
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"PDF validation error: {str(e)}"]
            }
    
    async def _validate_image(self, image_path: str) -> Dict[str, Any]:
        """Validate generated image."""
        try:
            if not image_path or not os.path.exists(image_path):
                return {
                    "valid": False,
                    "errors": ["Image file does not exist"]
                }
            
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                return {
                    "valid": False,
                    "errors": ["Image file is empty"]
                }
            
            # Basic image validation
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return {
                    "valid": False,
                    "errors": ["Image file too large (>10MB)"]
                }
            
            return {
                "valid": True,
                "errors": []
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Image validation error: {str(e)}"]
            }
    
    async def _validate_file_integrity(self, assets: Dict[str, Any]) -> Dict[str, Any]:
        """Validate file integrity of all assets."""
        errors = []
        
        for asset_type, asset_info in assets.items():
            file_path = asset_info.get("file_path")
            
            if not file_path or not os.path.exists(file_path):
                errors.append(f"{asset_type}: File does not exist")
            elif asset_info.get("file_size_bytes", 0) == 0:
                errors.append(f"{asset_type}: File is empty")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _validate_package_size(self, assets: Dict[str, Any]) -> Dict[str, Any]:
        """Validate total package size."""
        total_size = sum(asset.get("file_size_bytes", 0) for asset in assets.values())
        
        # 100MB total package limit
        if total_size > 100 * 1024 * 1024:
            return {
                "valid": False,
                "errors": [f"Package too large: {total_size / (1024*1024):.1f}MB > 100MB"]
            }
        
        return {
            "valid": True,
            "errors": []
        }
    
    def _generate_packaging_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for check_name, result in validation_results.items():
            if not result.get("valid", True):
                if check_name == "pdf_rendering":
                    recommendations.append("Improve PDF formatting and layout")
                elif check_name == "image_generation":
                    recommendations.append("Enhance image quality and design")
                elif check_name == "file_integrity":
                    recommendations.append("Check file creation and saving process")
                elif check_name == "package_size_validation":
                    recommendations.append("Optimize content to reduce file sizes")
        
        return recommendations
    
    def _generate_next_steps(self, validation_passed: bool) -> List[str]:
        """Generate next steps based on validation."""
        if validation_passed:
            return [
                "Proceed to listing optimization",
                "Generate Gumroad listing copy",
                "Set product pricing",
                "Publish to Gumroad"
            ]
        else:
            return [
                "Fix validation issues",
                "Regenerate problematic assets",
                "Re-run quality checks",
                "Review content quality"
            ]
