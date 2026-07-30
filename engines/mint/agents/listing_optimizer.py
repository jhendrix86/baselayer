"""
MINT Listing Optimizer Agent

Generates Gumroad listing copy with optimization
for conversions and sales performance.
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


class ListingOptimizer(AgentBase):
    """
    Gumroad listing optimization agent for MINT engine.
    
    Generates compelling Gumroad listing copy with
    AIDA framework, character limits, and optimization.
    """
    
    agent_name = "listing_optimizer"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.character_limits = {
            "title": 80,
            "subtitle": 200,
            "description": 5000,
            "features": 300,
            "benefits": 200
        }
        self.optimization_strategies = [
            "benefit_driven",
            "problem_solution",
            "scarcity_urgency",
            "social_proof",
            "risk_reversal"
        ]
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan listing optimization approach.
        
        Args:
            input_data: Product information and content
            
        Returns:
            Dict containing optimization plan
        """
        try:
            # Extract product information
            product_title = input_data.get("title", "")
            product_type = input_data.get("product_type", "pdf_guide")
            content = input_data.get("content", "")
            target_audience = input_data.get("target_audience", "general")
            price_cents = input_data.get("price_cents", 0)
            tags = input_data.get("tags", [])
            
            # Analyze content for optimization opportunities
            content_analysis = await self._analyze_content_for_optimization(content)
            
            # Determine optimization strategy
            strategy = self._select_optimization_strategy(
                product_type,
                target_audience,
                price_cents,
                content_analysis
            )
            
            # Create optimization plan
            plan = {
                "product_title": product_title,
                "product_type": product_type,
                "content": content,
                "target_audience": target_audience,
                "price_cents": price_cents,
                "tags": tags,
                "content_analysis": content_analysis,
                "optimization_strategy": strategy,
                "copy_structure": self._get_copy_structure(strategy),
                "character_limits": self.character_limits,
                "optimization_focus": [
                    "title_optimization",
                    "subtitle_creation",
                    "description_enhancement",
                    "feature_benefit_alignment",
                    "cta_optimization",
                    "seo_optimization"
                ],
                "estimated_duration": self._estimate_optimization_duration(
                    len(content),
                    strategy
                ),
                "llm_model": self._select_model_for_optimization(),
                "temperature": 0.8,  # Higher creativity for marketing copy
                "max_tokens": 2000
            }
            
            logger.info(
                "Listing optimization plan created",
                product_title=product_title,
                strategy=strategy,
                optimization_focus=plan["optimization_focus"]
            )
            
            return plan
            
        except Exception as e:
            logger.error(
                "Failed to create listing optimization plan",
                error=str(e),
                input_data=input_data
            )
            raise BaseLayerError(f"Plan creation failed: {str(e)}") from e
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute listing optimization.
        
        Args:
            plan: Optimization plan from plan() phase
            
        Returns:
            Dict containing optimized listing copy
        """
        try:
            # Initialize optimization state
            optimization_id = str(uuid.uuid4())
            product_title = plan["product_title"]
            content = plan["content"]
            strategy = plan["optimization_strategy"]
            copy_structure = plan["copy_structure"]
            
            logger.info(
                "Starting listing optimization",
                optimization_id=optimization_id,
                strategy=strategy
            )
            
            # Generate listing components
            optimized_components = {}
            
            # Generate title
            optimized_components["title"] = await self._generate_optimized_title(
                product_title,
                content,
                plan
            )
            
            # Generate subtitle
            optimized_components["subtitle"] = await self._generate_subtitle(
                content,
                plan
            )
            
            # Generate description
            optimized_components["description"] = await self._generate_description(
                content,
                copy_structure,
                plan
            )
            
            # Generate features and benefits
            optimized_components["features"] = await self._generate_features(
                content,
                plan
            )
            
            optimized_components["benefits"] = await self._generate_benefits(
                content,
                plan
            )
            
            # Generate call-to-action
            optimized_components["cta"] = await self._generate_cta(
                plan["product_type"],
                plan
            )
            
            # Compile full listing
            full_listing = self._compile_listing_copy(
                optimized_components,
                copy_structure
            )
            
            # Optimize for character limits
            final_listing = self._optimize_for_character_limits(
                full_listing,
                plan["character_limits"]
            )
            
            result = {
                "optimization_id": optimization_id,
                "components": optimized_components,
                "full_listing": final_listing,
                "character_counts": self._count_characters(final_listing),
                "strategy": strategy,
                "success": len(optimized_components) > 0
            }
            
            logger.info(
                "Listing optimization completed",
                optimization_id=optimization_id,
                components_generated=len(optimized_components),
                strategy=strategy
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Listing optimization execution failed",
                error=str(e),
                plan=plan
            )
            raise BaseLayerError(f"Optimization execution failed: {str(e)}") from e
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate optimized listing copy.
        
        Args:
            result: Optimization result from execute() phase
            
        Returns:
            Dict with validation results
        """
        try:
            full_listing = result.get("full_listing", "")
            character_counts = result.get("character_counts", {})
            strategy = result.get("strategy", "")
            
            validation_results = {
                "character_limits": self._validate_character_limits(
                    character_counts,
                    self.character_limits
                ),
                "content_completeness": self._validate_content_completeness(
                    full_listing,
                    strategy
                ),
                "marketing_effectiveness": self._validate_marketing_effectiveness(
                    full_listing,
                    strategy
                ),
                "kade_persona_compliance": self._validate_kade_persona_compliance(
                    full_listing
                ),
                "cta_presence": self._validate_cta_presence(full_listing)
            }
            
            # Calculate overall quality score
            quality_scores = [
                validation_results["character_limits"]["score"],
                validation_results["content_completeness"]["score"],
                validation_results["marketing_effectiveness"]["score"],
                validation_results["kade_persona_compliance"]["score"],
                validation_results["cta_presence"]["score"]
            ]
            
            overall_score = sum(quality_scores) / len(quality_scores)
            validation_results["overall_score"] = overall_score
            validation_results["overall_valid"] = overall_score >= 0.8
            
            logger.info(
                "Listing optimization validation completed",
                overall_score=overall_score,
                overall_valid=validation_results["overall_valid"]
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
                "Listing optimization validation failed",
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
        Report optimization results.
        
        Args:
            result: Execution and validation results
            
        Returns:
            Dict containing report data
        """
        try:
            optimization_id = result.get("optimization_id", str(uuid.uuid4()))
            full_listing = result.get("full_listing", "")
            validation_results = result.get("validation_results", {})
            
            # Create report
            report = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "optimization_id": optimization_id,
                "execution_summary": {
                    "strategy": result.get("strategy", ""),
                    "components_generated": len(result.get("components", {})),
                    "character_counts": result.get("character_counts", {}),
                    "quality_score": validation_results.get("overall_score", 0.0),
                    "validation_passed": validation_results.get("overall_valid", False)
                },
                "listing_preview": full_listing[:500] + "..." if len(full_listing) > 500 else full_listing,
                "validation_summary": validation_results,
                "recommendations": self._generate_recommendations(validation_results),
                "next_steps": self._generate_next_steps(validation_results.get("overall_valid", False)),
                "metrics": self._get_execution_metrics()
            }
            
            logger.info(
                "Listing optimization report created",
                optimization_id=optimization_id,
                quality_score=validation_results.get("overall_score", 0.0),
                validation_passed=validation_results.get("overall_valid", False)
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "Failed to create optimization report",
                error=str(e),
                result=result
            )
            return {
                "agent_id": self.agent_id,
                "error": str(e),
                "execution_summary": "Report generation failed"
            }
    
    async def _analyze_content_for_optimization(self, content: str) -> Dict[str, Any]:
        """Analyze content for optimization opportunities."""
        try:
            # Extract key themes and benefits
            word_count = len(content.split())
            
            # Simple keyword extraction (would use NLP in production)
            keywords = self._extract_keywords(content)
            
            # Identify benefit statements
            benefit_indicators = ["benefit", "advantage", "learn", "discover", "master", "improve"]
            benefit_count = sum(
                content.lower().count(indicator) 
                for indicator in benefit_indicators
            )
            
            # Identify problem statements
            problem_indicators = ["problem", "challenge", "struggle", "difficult", "issue"]
            problem_count = sum(
                content.lower().count(indicator)
                for indicator in problem_indicators
            )
            
            return {
                "word_count": word_count,
                "keywords": keywords,
                "benefit_count": benefit_count,
                "problem_count": problem_count,
                "complexity_score": min(word_count / 1000, 1.0),
                "optimization_potential": benefit_count > 0 or problem_count > 0
            }
            
        except Exception as e:
            logger.error(
                "Content analysis failed",
                error=str(e)
            )
            return {
                "word_count": 0,
                "keywords": [],
                "benefit_count": 0,
                "problem_count": 0,
                "complexity_score": 0.0,
                "optimization_potential": False
            }
    
    def _select_optimization_strategy(
        self,
        product_type: str,
        target_audience: str,
        price_cents: int,
        content_analysis: Dict[str, Any]
    ) -> str:
        """Select optimization strategy based on product and content."""
        try:
            # Base strategy on product type
            if content_analysis.get("optimization_potential", False):
                return "basic"
            
            # Price-based strategy
            if price_cents >= 2000:  # $20+
                return "premium_positioning"
            elif price_cents >= 1000:  # $10+
                return "value_proposition"
            
            # Audience-based strategy
            if "beginner" in target_audience.lower():
                return "educational_approach"
            elif "advanced" in target_audience.lower():
                return "expert_positioning"
            
            # Default to benefit-driven
            return "benefit_driven"
            
        except Exception as e:
            logger.error(
                "Strategy selection failed",
                error=str(e)
            )
            return "benefit_driven"
    
    def _get_copy_structure(self, strategy: str) -> Dict[str, Any]:
        """Get copy structure for optimization strategy."""
        structures = {
            "benefit_driven": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "benefits and outcomes"
            },
            "problem_solution": {
                "framework": "PAS",
                "flow": "problem -> agitation -> solution",
                "focus": "pain points and relief"
            },
            "scarcity_urgency": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "limited time/quantity"
            },
            "social_proof": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "testimonials and results"
            },
            "risk_reversal": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "risk reversal and guarantee"
            },
            "premium_positioning": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "exclusivity and value"
            },
            "value_proposition": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "value and ROI"
            },
            "educational_approach": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "learning and transformation"
            },
            "expert_positioning": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "authority and expertise"
            },
            "basic": {
                "framework": "AIDA",
                "flow": "attention -> interest -> desire -> action",
                "focus": "clear and direct"
            }
        }
        
        return structures.get(strategy, structures["basic"])
    
    def _estimate_optimization_duration(self, content_length: int, strategy: str) -> int:
        """Estimate optimization duration in seconds."""
        # Base time per word
        base_time_per_word = 0.3
        
        # Strategy multipliers
        strategy_multipliers = {
            "basic": 1.0,
            "benefit_driven": 1.2,
            "problem_solution": 1.3,
            "scarcity_urgency": 1.1,
            "social_proof": 1.4,
            "risk_reversal": 1.3,
            "premium_positioning": 1.5,
            "value_proposition": 1.4,
            "educational_approach": 1.6,
            "expert_positioning": 1.7
        }
        
        multiplier = strategy_multipliers.get(strategy, 1.0)
        
        return int(content_length * base_time_per_word * multiplier)
    
    def _select_model_for_optimization(self) -> str:
        """Select appropriate LLM model for optimization."""
        # Use smaller model for creative tasks (faster iteration)
        return "llama2:7b"
    
    async def _generate_optimized_title(
        self,
        base_title: str,
        content: str,
        plan: Dict[str, Any]
    ) -> str:
        """Generate optimized title."""
        try:
            # Create title generation prompt
            prompt = prompt_engine.render_with_pattern(
                "title_generator_v1",
                "json_output",
                {
                    "base_title": base_title,
                    "content_preview": content[:500],
                    "target_audience": plan.get("target_audience", "general"),
                    "max_length": self.character_limits["title"],
                    "optimization_strategy": plan.get("strategy", "benefit_driven")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in compelling product titles",
                        purpose="Generate optimized product titles for Gumroad listings",
                        constraints=[
                            "Maximum character limits",
                            "Benefit-focused language",
                            "No clickbait",
                            "Professional tone"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=200,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            # Parse and validate response
            parsed_result = response_parser.parse_json(response.response)
            
            if parsed_result.success:
                title = parsed_result.data.get("title", base_title)
                return title[:self.character_limits["title"]]
            else:
                # Fallback to base title
                return base_title[:self.character_limits["title"]]
                
        except Exception as e:
            logger.error(
                "Title generation failed",
                error=str(e)
            )
            return base_title[:self.character_limits["title"]]
    
    async def _generate_subtitle(
        self,
        content: str,
        plan: Dict[str, Any]
    ) -> str:
        """Generate compelling subtitle."""
        try:
            # Create subtitle prompt
            prompt = prompt_engine.render_with_pattern(
                "listing_copy_v1",
                "chain_of_thought",
                {
                    "content": content,
                    "component": "subtitle",
                    "max_length": self.character_limits["subtitle"],
                    "optimization_strategy": plan.get("strategy", "benefit_driven"),
                    "target_audience": plan.get("target_audience", "general")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in compelling subtitles",
                        purpose="Generate optimized subtitles for Gumroad listings",
                        constraints=[
                            "Benefit-driven language",
                            "Emotional appeal",
                            "Character limit compliance"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=300,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            return response.response.strip()[:self.character_limits["subtitle"]]
            
        except Exception as e:
            logger.error(
                "Subtitle generation failed",
                error=str(e)
            )
            return ""
    
    async def _generate_description(
        self,
        content: str,
        copy_structure: Dict[str, Any],
        plan: Dict[str, Any]
    ) -> str:
        """Generate optimized description."""
        try:
            # Create description prompt
            prompt = prompt_engine.render_with_pattern(
                "listing_copy_v1",
                "chain_of_thought",
                {
                    "content": content,
                    "component": "description",
                    "framework": copy_structure.get("framework", "AIDA"),
                    "flow": copy_structure.get("flow", "attention -> interest -> desire -> action"),
                    "max_length": self.character_limits["description"],
                    "optimization_strategy": plan.get("strategy", "benefit_driven"),
                    "target_audience": plan.get("target_audience", "general")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in compelling product descriptions",
                        purpose="Generate optimized descriptions for Gumroad listings",
                        constraints=[
                            "Follow AIDA framework",
                            "Benefit-focused language",
                            "No placeholder text",
                            "Professional tone"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=1000,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            return response.response.strip()[:self.character_limits["description"]]
            
        except Exception as e:
            logger.error(
                "Description generation failed",
                error=str(e)
            )
            return ""
    
    async def _generate_features(
        self,
        content: str,
        plan: Dict[str, Any]
    ) -> List[str]:
        """Generate feature bullet points."""
        try:
            # Create features prompt
            prompt = prompt_engine.render_with_pattern(
                "listing_copy_v1",
                "chain_of_thought",
                {
                    "content": content,
                    "component": "features",
                    "max_features": 7,
                    "max_length": self.character_limits["features"],
                    "optimization_strategy": plan.get("strategy", "benefit_driven"),
                    "target_audience": plan.get("target_audience", "general")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in feature bullet points",
                        purpose="Generate compelling feature lists for Gumroad listings",
                        constraints=[
                            "Benefit-oriented language",
                            "Specific and measurable",
                            "Action-oriented verbs"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=400,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            # Parse features from response
            features_text = response.response.strip()
            features = [f.strip() for f in features_text.split('\n') if f.strip()]
            
            return features[:7]  # Limit to 7 features
            
        except Exception as e:
            logger.error(
                "Features generation failed",
                error=str(e)
            )
            return []
    
    async def _generate_benefits(
        self,
        content: str,
        plan: Dict[str, Any]
    ) -> List[str]:
        """Generate benefit bullet points."""
        try:
            # Create benefits prompt
            prompt = prompt_engine.render_with_pattern(
                "listing_copy_v1",
                "chain_of_thought",
                {
                    "content": content,
                    "component": "benefits",
                    "max_benefits": 5,
                    "max_length": self.character_limits["benefits"],
                    "optimization_strategy": plan.get("strategy", "benefit_driven"),
                    "target_audience": plan.get("target_audience", "general")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in benefit statements",
                        purpose="Generate compelling benefit lists for Gumroad listings",
                        constraints=[
                            "Outcome-focused language",
                            "Emotional appeal",
                            "Specific results"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=300,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            # Parse benefits from response
            benefits_text = response.response.strip()
            benefits = [f.strip() for f in benefits_text.split('\n') if f.strip()]
            
            return benefits[:5]  # Limit to 5 benefits
            
        except Exception as e:
            logger.error(
                "Benefits generation failed",
                error=str(e)
            )
            return []
    
    async def _generate_cta(
        self,
        product_type: str,
        plan: Dict[str, Any]
    ) -> str:
        """Generate call-to-action."""
        try:
            # Create CTA prompt
            prompt = prompt_engine.render_with_pattern(
                "listing_copy_v1",
                "chain_of_thought",
                {
                    "product_type": product_type,
                    "component": "cta",
                    "optimization_strategy": plan.get("strategy", "benefit_driven"),
                    "target_audience": plan.get("target_audience", "general")
                }
            )
            
            # Generate using Ollama
            messages = [
                {
                    "role": "system",
                    "content": prompt_engine.create_system_message(
                        persona="Kade",
                        role_description="Expert copywriter specializing in call-to-action statements",
                        purpose="Generate compelling CTAs for Gumroad listings",
                        constraints=[
                            "Action-oriented language",
                            "Sense of urgency",
                            "Clear next steps"
                        ]
                    )
                },
                {"role": "user", "content": prompt}
            ]
            
            options = OllamaChatOptions(
                temperature=plan.get("temperature", 0.8),
                max_tokens=200,
                top_p=0.9
            )
            
            response = await ollama_client.chat(
                messages=messages,
                model=plan.get("llm_model", "llama2:7b"),
                options=options
            )
            
            return response.response.strip()
            
        except Exception as e:
            logger.error(
                "CTA generation failed",
                error=str(e)
            )
            return "Get instant access now"
    
    def _compile_listing_copy(
        self,
        components: Dict[str, Any],
        copy_structure: Dict[str, Any]
    ) -> str:
        """Compile full listing copy from components."""
        try:
            # Build listing according to framework
            framework = copy_structure.get("framework", "AIDA")
            flow = copy_structure.get("flow", "attention -> interest -> desire -> action")
            
            sections = []
            
            # Title
            if "title" in components:
                sections.append(f"# {components['title']}")
                sections.append("")
            
            # Subtitle
            if "subtitle" in components:
                sections.append(f"## {components['subtitle']}")
                sections.append("")
            
            # Description (following framework flow)
            if "description" in components:
                if framework == "AIDA":
                    sections.append("## What You'll Get")
                    sections.append("")
                    sections.append(components["description"])
                    sections.append("")
                elif framework == "PAS":
                    sections.append("## The Problem")
                    sections.append("")
                    sections.append(components["description"])
                    sections.append("")
            
            # Features
            if "features" in components:
                sections.append("## Key Features")
                sections.append("")
                for feature in components["features"]:
                    sections.append(f"• {feature}")
                sections.append("")
            
            # Benefits
            if "benefits" in components:
                sections.append("## Benefits")
                sections.append("")
                for benefit in components["benefits"]:
                    sections.append(f"• {benefit}")
                sections.append("")
            
            # Call-to-action
            if "cta" in components:
                sections.append("## Get Started")
                sections.append("")
                sections.append(f"**{components['cta']}**")
                sections.append("")
            
            return "\n".join(sections)
            
        except Exception as e:
            logger.error(
                "Failed to compile listing copy",
                error=str(e)
            )
            return ""
    
    def _optimize_for_character_limits(
        self,
        full_listing: str,
        limits: Dict[str, int]
    ) -> str:
        """Optimize listing for character limits."""
        try:
            # Simple truncation based on limits
            lines = full_listing.split('\n')
            optimized_lines = []
            
            for line in lines:
                if len(line.strip()) <= limits.get("description", 5000):
                    optimized_lines.append(line)
                else:
                    # Truncate long lines
                    optimized_lines.append(line[:limits.get("description", 5000)])
            
            return "\n".join(optimized_lines)
            
        except Exception as e:
            logger.error(
                "Character limit optimization failed",
                error=str(e)
            )
            return full_listing
    
    def _count_characters(self, text: str) -> Dict[str, int]:
        """Count characters in different sections."""
        lines = text.split('\n')
        
        counts = {
            "total": len(text),
            "title": 0,
            "subtitle": 0,
            "description": 0,
            "features": 0,
            "benefits": 0,
            "cta": 0
        }
        
        current_section = "description"
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('# '):
                current_section = "title"
                counts["title"] += len(line) - 2  # Remove "# "
            elif line.startswith('## '):
                current_section = "subtitle"
                counts["subtitle"] += len(line) - 3  # Remove "## "
            elif line.startswith('• '):
                if current_section in ["features", "benefits"]:
                    counts[current_section] += len(line) - 2  # Remove "• "
            elif line.startswith('**'):
                current_section = "cta"
                counts["cta"] += len(line) - 4  # Remove "**"
            else:
                counts["description"] += len(line)
        
        return counts
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simplified)."""
        # Simple keyword extraction
        words = text.lower().split()
        
        # Filter out common words and keep important terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when',
            'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
            'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'than', 'too', 'very', 'just', 'now'
        }
        
        keywords = []
        for word in words:
            word = word.strip('.,!?;:()[]{}"\'')
            if (len(word) > 3 and 
                word not in stop_words and 
                word not in keywords):
                keywords.append(word)
        
        return keywords[:10]  # Top 10 keywords
    
    def _validate_character_limits(
        self,
        character_counts: Dict[str, int],
        limits: Dict[str, int]
    ) -> Dict[str, Any]:
        """Validate character limits."""
        errors = []
        
        # Check each limit
        if character_counts.get("title", 0) > limits.get("title", 80):
            errors.append(f"Title exceeds limit: {character_counts['title']}/{limits['title']}")
        
        if character_counts.get("subtitle", 0) > limits.get("subtitle", 200):
            errors.append(f"Subtitle exceeds limit: {character_counts['subtitle']}/{limits['subtitle']}")
        
        if character_counts.get("description", 0) > limits.get("description", 5000):
            errors.append(f"Description exceeds limit: {character_counts['description']}/{limits['description']}")
        
        return {
            "valid": len(errors) == 0,
            "score": max(0.0, 1.0 - len(errors) * 0.2),
            "errors": errors
        }
    
    def _validate_content_completeness(
        self,
        full_listing: str,
        strategy: str
    ) -> Dict[str, Any]:
        """Validate content completeness."""
        required_sections = ["title", "description", "features", "benefits", "cta"]
        
        completeness_score = 0.0
        errors = []
        
        # Check for required sections
        if not full_listing or len(full_listing.strip()) == 0:
            errors.append("Empty listing")
            return {"valid": False, "score": 0.0, "errors": errors}
        
        # Simple section detection
        has_title = any(line.strip().startswith('# ') for line in full_listing.split('\n'))
        has_description = len(full_listing) > 200  # Basic check
        has_features = '• ' in full_listing
        has_benefits = 'benefit' in full_listing.lower() or 'get' in full_listing.lower()
        has_cta = 'Get Started' in full_listing or 'Buy Now' in full_listing or 'Access Now' in full_listing
        
        sections_present = [
            has_title,
            has_description,
            has_features,
            has_benefits,
            has_cta
        ]
        
        completeness_score = sum(sections_present) / len(required_sections)
        
        if completeness_score < 0.8:
            missing_sections = [
                section for section, present in zip(required_sections, sections_present)
                if not present
            ]
            errors.append(f"Missing sections: {', '.join(missing_sections)}")
        
        return {
            "valid": completeness_score >= 0.8,
            "score": completeness_score,
            "errors": errors
        }
    
    def _validate_marketing_effectiveness(
        self,
        full_listing: str,
        strategy: str
    ) -> Dict[str, Any]:
        """Validate marketing effectiveness."""
        effectiveness_indicators = [
            "benefit", "advantage", "you", "your", "learn", "discover", "master",
            "guarantee", "risk-free", "instant", "immediate", "proven", "results"
        ]
        
        indicator_count = sum(
            full_listing.lower().count(indicator)
            for indicator in effectiveness_indicators
        )
        
        # Score based on indicator density
        text_length = len(full_listing)
        density_score = indicator_count / max(text_length / 1000, 1)
        
        # Adjust score based on strategy
        strategy_multipliers = {
            "benefit_driven": 1.0,
            "problem_solution": 1.1,
            "scarcity_urgency": 1.0,
            "social_proof": 1.2,
            "risk_reversal": 1.1,
            "premium_positioning": 1.0,
            "value_proposition": 1.1,
            "educational_approach": 0.9,
            "expert_positioning": 1.0,
            "basic": 0.8
        }
        
        multiplier = strategy_multipliers.get(strategy, 1.0)
        final_score = min(density_score * multiplier, 1.0)
        
        return {
            "valid": final_score >= 0.3,
            "score": final_score,
            "indicator_count": indicator_count,
            "text_length": text_length,
            "errors": [] if final_score >= 0.3 else ["Low marketing effectiveness"]
        }
    
    def _validate_kade_persona_compliance(
        self,
        full_listing: str
    ) -> Dict[str, Any]:
        """Validate Kade persona compliance."""
        violations = []
        
        # Check for first-person references
        first_person_indicators = ["I think", "I believe", "In my opinion", "Personally", "My experience"]
        for indicator in first_person_indicators:
            if indicator.lower() in full_listing.lower():
                violations.append("First-person reference detected")
        
        # Check for personal anecdotes
        anecdote_indicators = ["When I", "Let me tell you", "In my case", "From my experience"]
        for indicator in anecdote_indicators:
            if indicator.lower() in full_listing.lower():
                violations.append("Personal anecdote detected")
        
        # Check for identity disclosure
        identity_indicators = ["As an AI", "I am an AI", "As a language model", "Machine generated"]
        for indicator in identity_indicators:
            if indicator.lower() in full_listing.lower():
                violations.append("AI identity disclosure detected")
        
        # Check for overly casual language
        casual_indicators = ["hey guys", "what's up", "check this out", "super cool"]
        for indicator in casual_indicators:
            if indicator.lower() in full_listing.lower():
                violations.append("Overly casual language detected")
        
        # Calculate score
        score = max(0.0, 1.0 - (len(violations) * 0.2))
        
        return {
            "valid": len(violations) == 0,
            "score": score,
            "violations": violations
        }
    
    def _validate_cta_presence(self, full_listing: str) -> Dict[str, Any]:
        """Validate call-to-action presence."""
        cta_indicators = [
            "Buy Now", "Get Started", "Access Now", "Download Now", "Purchase",
            "Add to Cart", "Get Instant Access", "Click Here", "Order Now"
        ]
        
        has_cta = any(
            indicator.lower() in full_listing.lower()
            for indicator in cta_indicators
        )
        
        return {
            "valid": has_cta,
            "score": 1.0 if has_cta else 0.0,
            "errors": [] if has_cta else ["No clear call-to-action"]
        }
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for check_name, result in validation_results.items():
            if isinstance(result, dict) and not result.get("valid", True):
                if check_name == "character_limits":
                    recommendations.append("Reduce text to fit within character limits")
                elif check_name == "content_completeness":
                    recommendations.append("Add missing sections (title, features, benefits, CTA)")
                elif check_name == "marketing_effectiveness":
                    recommendations.append("Add more benefit-oriented language and emotional triggers")
                elif check_name == "kade_persona_compliance":
                    recommendations.append("Remove first-person references and personal anecdotes")
                elif check_name == "cta_presence":
                    recommendations.append("Add clear call-to-action with urgency")
        
        return recommendations
    
    def _generate_next_steps(self, validation_passed: bool) -> List[str]:
        """Generate next steps based on validation."""
        if validation_passed:
            return [
                "Proceed to Gumroad publishing",
                "Set up product pricing",
                "Create promotional materials",
                "Schedule product launch"
            ]
        else:
            return [
                "Review and fix validation issues",
                "Regenerate problematic sections",
                "Improve content quality",
                "Re-run validation checks"
            ]
