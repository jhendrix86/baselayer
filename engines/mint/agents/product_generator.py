"""
MINT Product Generator Agent

AI-powered agent for generating digital product content
using LLM with Kade persona and quality controls.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.llm.ollama_client import ollama_client, OllamaChatOptions
from agents.llm.prompt_engine import prompt_engine
from agents.llm.response_parser import response_parser
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class ProductGenerator(AgentBase):
    """
    AI-powered product generation agent.
    
    Generates digital product content using LLM with
    Kade persona, quality controls, and validation.
    """
    
    agent_name = "product_generator"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.quality_threshold = 0.8
        self.min_word_count = 500
        self.max_word_count = 10000
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan product generation approach.
        
        Args:
            input_data: Product brief or template data
            
        Returns:
            Dict containing generation plan
        """
        try:
            # Extract product information
            product_type = input_data.get("product_type", "pdf_guide")
            brief = input_data.get("brief", "")
            template_id = input_data.get("template_id")
            target_audience = input_data.get("target_audience", "general")
            word_count_target = input_data.get("word_count_target", 2000)
            
            # Determine generation strategy
            if template_id:
                # Use template-based generation
                from ..models.product_template import ProductTemplate
                # TODO: Fetch template from database
                template = None  # Would fetch from DB
                structure = template.structure if template else self._get_default_structure(product_type)
            else:
                # Use brief-based generation
                structure = self._get_default_structure(product_type)
            
            # Create generation plan
            plan = {
                "product_type": product_type,
                "brief": brief,
                "template_id": template_id,
                "target_audience": target_audience,
                "word_count_target": word_count_target,
                "structure": structure,
                "generation_strategy": "template" if template_id else "brief",
                "quality_checks": [
                    "word_count_validation",
                    "content_completeness",
                    "kade_persona_compliance",
                    "placeholder_removal",
                    "ai_self_reference_check"
                ],
                "estimated_duration": self._estimate_duration(word_count_target, product_type),
                "llm_model": self._select_model(product_type),
                "temperature": 0.7,  # Balanced creativity
                "max_tokens": min(word_count_target * 2, 4000)
            }
            
            logger.info(
                "Product generation plan created",
                product_type=product_type,
                strategy=plan["generation_strategy"],
                word_count_target=word_count_target
            )
            
            return plan
            
        except Exception as e:
            logger.error(
                "Failed to create product generation plan",
                error=str(e),
                input_data=input_data
            )
            raise BaseLayerError(f"Plan creation failed: {str(e)}") from e
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute product generation.
        
        Args:
            plan: Generation plan from plan() phase
            
        Returns:
            Dict containing generated product content
        """
        try:
            # Initialize generation state
            generation_id = str(uuid.uuid4())
            product_type = plan["product_type"]
            structure = plan["structure"]
            
            logger.info(
                "Starting product generation",
                generation_id=generation_id,
                product_type=product_type,
                sections_count=len(structure.get("sections", []))
            )
            
            # Generate content for each section
            generated_sections = {}
            total_word_count = 0
            
            for section_name, section_config in structure.get("sections", {}).items():
                try:
                    # Generate section content
                    section_content = await self._generate_section(
                        section_name,
                        section_config,
                        plan
                    )
                    
                    generated_sections[section_name] = section_content
                    total_word_count += len(section_content.split())
                    
                    logger.debug(
                        "Section generated",
                        generation_id=generation_id,
                        section=section_name,
                        word_count=len(section_content.split())
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to generate section",
                        generation_id=generation_id,
                        section=section_name,
                        error=str(e)
                    )
                    generated_sections[section_name] = f"Error generating {section_name}: {str(e)}"
            
            # Generate metadata
            metadata = {
                "generation_id": generation_id,
                "product_type": product_type,
                "word_count": total_word_count,
                "target_word_count": plan.get("word_count_target", 2000),
                "sections_generated": len(generated_sections),
                "llm_model": plan.get("llm_model"),
                "generation_time": datetime.now(timezone.utc).isoformat(),
                "quality_score": 0.0  # Will be calculated in validation
            }
            
            # Compile final content
            final_content = self._compile_product_content(
                generated_sections,
                structure,
                product_type
            )
            
            result = {
                "generation_id": generation_id,
                "content": final_content,
                "sections": generated_sections,
                "metadata": metadata,
                "word_count": total_word_count,
                "structure": structure,
                "success": len(generated_sections) > 0
            }
            
            logger.info(
                "Product generation completed",
                generation_id=generation_id,
                word_count=total_word_count,
                sections_count=len(generated_sections)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Product generation execution failed",
                error=str(e),
                plan=plan
            )
            raise BaseLayerError(f"Generation execution failed: {str(e)}") from e
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate generated product content.
        
        Args:
            result: Generation result from execute() phase
            
        Returns:
            Dict with validation results
        """
        try:
            content = result.get("content", "")
            sections = result.get("sections", {})
            metadata = result.get("metadata", {})
            
            validation_results = {
                "word_count_validation": self._validate_word_count(content, metadata),
                "content_completeness": self._validate_completeness(sections, metadata),
                "kade_persona_compliance": self._validate_kade_persona(content),
                "placeholder_removal": self._validate_no_placeholders(content),
                "ai_self_reference_check": self._validate_no_ai_references(content)
            }
            
            # Calculate overall quality score
            quality_scores = [
                validation_results["word_count_validation"]["score"],
                validation_results["content_completeness"]["score"],
                validation_results["kade_persona_compliance"]["score"],
                validation_results["placeholder_removal"]["score"],
                validation_results["ai_self_reference_check"]["score"]
            ]
            
            overall_score = sum(quality_scores) / len(quality_scores)
            validation_results["overall_score"] = overall_score
            validation_results["overall_valid"] = overall_score >= self.quality_threshold
            
            # Update metadata with validation results
            metadata["validation_results"] = validation_results
            metadata["quality_score"] = overall_score
            
            logger.info(
                "Product validation completed",
                overall_score=overall_score,
                overall_valid=validation_results["overall_valid"],
                quality_threshold=self.quality_threshold
            )
            
            return {
                "valid": validation_results["overall_valid"],
                "score": overall_score,
                "validation_results": validation_results,
                "errors": [
                    f"{check}: {result['error']}"
                    for check, result in validation_results.items()
                    if not result.get("valid", True)
                ]
            }
            
        except Exception as e:
            logger.error(
                "Product validation failed",
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
        Report generation results.
        
        Args:
            result: Execution and validation results
            
        Returns:
            Dict containing report data
        """
        try:
            generation_id = result.get("generation_id", str(uuid.uuid4()))
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            validation_results = result.get("validation_results", {})
            
            # Create report
            report = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "generation_id": generation_id,
                "execution_summary": {
                    "product_type": metadata.get("product_type"),
                    "word_count": metadata.get("word_count"),
                    "target_word_count": metadata.get("target_word_count"),
                    "sections_generated": metadata.get("sections_generated"),
                    "quality_score": validation_results.get("overall_score", 0.0),
                    "validation_passed": validation_results.get("overall_valid", False)
                },
                "content_preview": content[:500] + "..." if len(content) > 500 else content,
                "validation_details": validation_results,
                "recommendations": self._generate_recommendations(validation_results),
                "next_steps": self._generate_next_steps(validation_results),
                "metrics": self._get_execution_metrics()
            }
            
            logger.info(
                "Product generation report created",
                generation_id=generation_id,
                quality_score=validation_results.get("overall_score", 0.0),
                validation_passed=validation_results.get("overall_valid", False)
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "Failed to create generation report",
                error=str(e),
                result=result
            )
            return {
                "agent_id": self.agent_id,
                "error": str(e),
                "execution_summary": "Report generation failed"
            }
    
    async def _generate_section(
        self,
        section_name: str,
        section_config: Dict[str, Any],
        plan: Dict[str, Any]
    ) -> str:
        """Generate content for a specific section."""
        try:
            # Create section prompt
            section_prompt = prompt_engine.render_with_pattern(
                "product_outline_v1",
                "chain_of_thought",
                {
                    "section_name": section_name,
                    "section_config": section_config,
                    "product_type": plan["product_type"],
                    "target_audience": plan.get("target_audience", "general"),
                    "brief": plan.get("brief", ""),
                    "word_count_target": section_config.get("word_count", 500)
                }
            )
            
            # Create Kade system message
            system_message = prompt_engine.create_system_message(
                persona="Kade",
                role_description="Professional digital product creator specializing in high-quality, practical content",
                purpose=f"Generate compelling {plan['product_type']} content",
                constraints=[
                    "No personal anecdotes or identity disclosure",
                    "Maintain professional, authoritative tone",
                    "Focus on practical value and actionable insights",
                    "Ensure content is complete and comprehensive"
                ]
            )
            
            # Generate content using Ollama
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": section_prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.7),
                max_tokens=plan.get("max_tokens", 2000),
                top_p=0.9,
                top_k=40
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            return response.response.strip()
            
        except Exception as e:
            logger.error(
                "Failed to generate section",
                section=section_name,
                error=str(e)
            )
            raise BaseLayerError(f"Section generation failed: {str(e)}") from e
    
    def _get_default_structure(self, product_type: str) -> Dict[str, Any]:
        """Get default structure for product type."""
        structures = {
            "pdf_guide": {
                "sections": {
                    "introduction": {
                        "title": "Introduction",
                        "word_count": 300,
                        "description": "Hook the reader and state the problem"
                    },
                    "problem_statement": {
                        "title": "Problem Statement",
                        "word_count": 400,
                        "description": "Clearly define the problem and its impact"
                    },
                    "solution_overview": {
                        "title": "Solution Overview",
                        "word_count": 600,
                        "description": "Present the main solution and approach"
                    },
                    "implementation_steps": {
                        "title": "Implementation Steps",
                        "word_count": 800,
                        "description": "Detailed step-by-step implementation guide"
                    },
                    "examples": {
                        "title": "Examples and Case Studies",
                        "word_count": 400,
                        "description": "Real-world examples and applications"
                    },
                    "conclusion": {
                        "title": "Conclusion",
                        "word_count": 200,
                        "description": "Summarize key takeaways and next steps"
                    }
                }
            },
            "template_pack": {
                "sections": {
                    "overview": {
                        "title": "Template Pack Overview",
                        "word_count": 200,
                        "description": "Introduction to the template pack"
                    },
                    "templates": {
                        "title": "Individual Templates",
                        "word_count": 1000,
                        "description": "Collection of template files"
                    },
                    "usage_guide": {
                        "title": "Usage Guide",
                        "word_count": 600,
                        "description": "How to use each template effectively"
                    },
                    "best_practices": {
                        "title": "Best Practices",
                        "word_count": 400,
                        "description": "Tips for getting the most value"
                    }
                }
            },
            "checklist": {
                "sections": {
                    "introduction": {
                        "title": "Introduction",
                        "word_count": 150,
                        "description": "Purpose and scope of the checklist"
                    },
                    "checklist_items": {
                        "title": "Checklist Items",
                        "word_count": 800,
                        "description": "Comprehensive checklist items"
                    },
                    "instructions": {
                        "title": "Instructions",
                        "word_count": 400,
                        "description": "How to use the checklist effectively"
                    }
                }
            }
        }
        
        return structures.get(product_type, structures["pdf_guide"])
    
    def _compile_product_content(
        self,
        sections: Dict[str, str],
        structure: Dict[str, Any],
        product_type: str
    ) -> str:
        """Compile sections into final product content."""
        try:
            content_parts = []
            
            # Add title if not present
            if "title" not in sections:
                content_parts.append(f"# {structure.get('title', 'Digital Product')}")
                content_parts.append("")
            
            # Compile sections in order
            for section_name, section_config in structure.get("sections", {}).items():
                if section_name in sections:
                    section_content = sections[section_name]
                    section_title = section_config.get("title", section_name.title())
                    
                    content_parts.append(f"## {section_title}")
                    content_parts.append("")
                    content_parts.append(section_content)
                    content_parts.append("")
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(
                "Failed to compile product content",
                error=str(e)
            )
            raise BaseLayerError(f"Content compilation failed: {str(e)}") from e
    
    def _validate_word_count(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate word count requirements."""
        word_count = len(content.split())
        target_count = metadata.get("target_word_count", 2000)
        
        # Check minimum word count
        min_valid = word_count >= self.min_word_count
        
        # Check target word count (within 20% tolerance)
        target_valid = abs(word_count - target_count) / target_count <= 0.2
        
        # Calculate score
        if min_valid and target_valid:
            score = 1.0
        elif min_valid:
            score = 0.7
        else:
            score = 0.3
        
        return {
            "valid": min_valid and target_valid,
            "score": score,
            "word_count": word_count,
            "target_count": target_count,
            "min_required": self.min_word_count,
            "error": None if min_valid else f"Word count ({word_count}) below minimum ({self.min_word_count})"
        }
    
    def _validate_completeness(self, sections: Dict[str, str], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content completeness."""
        total_sections = len(sections)
        completed_sections = len([s for s in sections.values() if s and not s.startswith("Error")])
        
        # Calculate completeness score
        if total_sections == 0:
            score = 0.0
        else:
            score = completed_sections / total_sections
        
        return {
            "valid": score >= 0.8,  # At least 80% of sections completed
            "score": score,
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "error": None if score >= 0.8 else f"Only {completed_sections}/{total_sections} sections completed"
        }
    
    def _validate_kade_persona(self, content: str) -> Dict[str, Any]:
        """Validate Kade persona compliance."""
        # Check for persona violations
        violations = []
        
        # Check for first-person references
        first_person_indicators = ["I think", "I believe", "In my opinion", "Personally", "My experience"]
        for indicator in first_person_indicators:
            if indicator.lower() in content.lower():
                violations.append("First-person reference detected")
        
        # Check for personal anecdotes
        anecdote_indicators = ["When I", "Let me tell you", "In my case", "From my experience"]
        for indicator in anecdote_indicators:
            if indicator.lower() in content.lower():
                violations.append("Personal anecdote detected")
        
        # Check for identity disclosure
        identity_indicators = ["As an AI", "I am an AI", "As a language model"]
        for indicator in identity_indicators:
            if indicator.lower() in content.lower():
                violations.append("AI identity disclosure detected")
        
        # Calculate score
        score = max(0.0, 1.0 - (len(violations) * 0.2))
        
        return {
            "valid": len(violations) == 0,
            "score": score,
            "violations": violations,
            "error": None if len(violations) == 0 else f"Persona violations: {', '.join(violations)}"
        }
    
    def _validate_no_placeholders(self, content: str) -> Dict[str, Any]:
        """Validate no placeholder text."""
        placeholder_indicators = [
            "[TODO]", "[PLACEHOLDER]", "[COMING SOON]", "[FILL IN]",
            "TODO:", "PLACEHOLDER:", "Example text here", "Your content here"
        ]
        
        violations = []
        for indicator in placeholder_indicators:
            if indicator.lower() in content.lower():
                violations.append(f"Placeholder found: {indicator}")
        
        score = max(0.0, 1.0 - (len(violations) * 0.3))
        
        return {
            "valid": len(violations) == 0,
            "score": score,
            "violations": violations,
            "error": None if len(violations) == 0 else f"Placeholders found: {', '.join(violations)}"
        }
    
    def _validate_no_ai_references(self, content: str) -> Dict[str, Any]:
        """Validate no AI self-references."""
        ai_indicators = [
            "As an AI", "As a language model", "AI-generated", "Machine generated",
            "This content was generated", "Created by AI"
        ]
        
        violations = []
        for indicator in ai_indicators:
            if indicator.lower() in content.lower():
                violations.append(f"AI reference found: {indicator}")
        
        score = max(0.0, 1.0 - (len(violations) * 0.4))
        
        return {
            "valid": len(violations) == 0,
            "score": score,
            "violations": violations,
            "error": None if len(violations) == 0 else f"AI references found: {', '.join(violations)}"
        }
    
    def _estimate_duration(self, word_count: int, product_type: str) -> int:
        """Estimate generation duration in seconds."""
        # Base time per word
        base_time_per_word = 0.5  # seconds
        
        # Adjust by product type complexity
        complexity_multipliers = {
            "pdf_guide": 1.0,
            "template_pack": 0.8,
            "checklist": 0.6,
            "cheat_sheet": 0.5,
            "prompt_library": 0.7,
            "code_snippets": 0.9,
            "notion_template": 0.8
        }
        
        multiplier = complexity_multipliers.get(product_type, 1.0)
        
        return int(word_count * base_time_per_word * multiplier)
    
    def _select_model(self, product_type: str) -> str:
        """Select appropriate LLM model for product type."""
        # Simple model selection based on product complexity
        model_mapping = {
            "pdf_guide": "llama2:13b",
            "template_pack": "llama2:7b",
            "checklist": "llama2:7b",
            "cheat_sheet": "llama2:7b",
            "prompt_library": "llama2:13b",
            "code_snippets": "llama2:13b",
            "notion_template": "llama2:7b"
        }
        
        return model_mapping.get(product_type, "llama2:7b")
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for check_name, result in validation_results.items():
            if isinstance(result, dict) and not result.get("valid", True):
                if check_name == "word_count_validation":
                    recommendations.append("Expand content to meet word count requirements")
                elif check_name == "content_completeness":
                    recommendations.append("Complete missing sections or add more detail")
                elif check_name == "kade_persona_compliance":
                    recommendations.append("Remove first-person references and personal anecdotes")
                elif check_name == "placeholder_removal":
                    recommendations.append("Remove placeholder text and complete all sections")
                elif check_name == "ai_self_reference_check":
                    recommendations.append("Remove AI self-references and maintain professional tone")
        
        return recommendations
    
    def _generate_next_steps(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate next steps based on validation."""
        overall_valid = validation_results.get("overall_valid", False)
        
        if overall_valid:
            return [
                "Proceed to product packaging",
                "Create product assets (PDF, images)",
                "Generate Gumroad listing copy",
                "Set up product pricing"
            ]
        else:
            return [
                "Review and fix validation issues",
                "Regenerate problematic sections",
                "Improve content quality",
                "Re-run validation checks"
            ]
