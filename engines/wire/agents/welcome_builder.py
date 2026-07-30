"""
WIRE Welcome Builder Agent

Pre-built 5-email welcome sequence with Kade persona
and value-driven content strategy.
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


class WelcomeBuilder(AgentBase):
    """
    Pre-built welcome sequence builder.
    
    Creates a 5-email welcome sequence with specific
    content strategy and Kade persona enforcement.
    """
    
    agent_name = "welcome_builder"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.sequence_length = 5
        self.quality_threshold = 0.85  # Higher threshold for welcome sequence
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan welcome sequence structure.
        
        Args:
            input_data: Welcome sequence configuration
            
        Returns:
            Dict containing welcome sequence plan
        """
        try:
            logger.info("Planning welcome sequence")
            
            # Extract configuration
            company_name = input_data.get("company_name", "Kade Digital")
            lead_magnet = input_data.get("lead_magnet", "")
            target_audience = input_data.get("target_audience", "professionals")
            value_proposition = input_data.get("value_proposition", "professional growth")
            main_product = input_data.get("main_product", "digital products")
            
            # Define welcome sequence strategy
            plan = {
                "sequence_name": f"{company_name} Welcome Sequence",
                "description": f"5-email welcome sequence for new subscribers with {lead_magnet}",
                "trigger": "subscription",
                "audience": target_audience,
                "sequence_length": self.sequence_length,
                "content_strategy": self._define_welcome_strategy(
                    company_name, lead_magnet, value_proposition, main_product
                ),
                "timing_strategy": self._define_welcome_timing(),
                "kade_persona_enforcement": self._get_persona_rules(),
                "quality_standards": self._get_quality_standards()
            }
            
            logger.info("Welcome sequence plan created", 
                       company_name=company_name,
                       lead_magnet=lead_magnet)
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan welcome sequence", error=str(e))
            raise BaseLayerError(f"Failed to plan welcome sequence: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate welcome sequence content.
        
        Args:
            plan: Welcome sequence plan
            
        Returns:
            Dict containing generated welcome sequence
        """
        try:
            logger.info("Executing welcome sequence generation")
            
            sequence_steps = []
            content_strategy = plan["content_strategy"]
            
            # Generate each email in the welcome sequence
            for step_num in range(1, self.sequence_length + 1):
                step_config = content_strategy["steps"][step_num - 1]
                
                step_data = await self._generate_welcome_step(
                    plan, step_config, step_num
                )
                sequence_steps.append(step_data)
                
                logger.debug("Generated welcome step", 
                           step=step_num,
                           purpose=step_config["purpose"])
            
            # Create complete sequence
            sequence = {
                "name": plan["sequence_name"],
                "description": plan["description"],
                "trigger": plan["trigger"],
                "steps": sequence_steps,
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "agent_version": self.agent_version,
                    "sequence_type": "welcome",
                    "plan": plan
                }
            }
            
            logger.info("Welcome sequence generation completed", 
                       sequence_name=plan["sequence_name"],
                       steps=len(sequence_steps))
            
            return sequence
            
        except Exception as e:
            logger.error("Failed to execute welcome sequence generation", error=str(e))
            raise BaseLayerError(f"Failed to execute welcome sequence generation: {e}")
    
    async def validate(self, sequence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate welcome sequence.
        
        Args:
            sequence: Generated welcome sequence
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating welcome sequence")
            
            validation_errors = []
            validation_warnings = []
            quality_score = 0.0
            
            # Basic structure validation
            structure_errors = self._validate_welcome_structure(sequence)
            validation_errors.extend(structure_errors)
            
            # Content validation for each step
            steps = sequence.get("steps", [])
            for i, step in enumerate(steps, 1):
                step_errors, step_warnings = await self._validate_welcome_step(step, i)
                validation_errors.extend(step_errors)
                validation_warnings.extend(step_warnings)
            
            # Welcome-specific validation
            welcome_errors = self._validate_welcome_flow(sequence)
            validation_errors.extend(welcome_errors)
            
            # Calculate quality score
            quality_score = self._calculate_welcome_quality_score(
                len(validation_errors), len(validation_warnings), len(steps)
            )
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "quality_score": quality_score,
                "errors": validation_errors,
                "warnings": validation_warnings,
                "meets_threshold": quality_score >= self.quality_threshold,
                "welcome_specific_checks": self._perform_welcome_specific_checks(sequence),
                "recommendations": self._generate_welcome_recommendations(
                    validation_errors, validation_warnings
                )
            }
            
            logger.info("Welcome sequence validation completed", 
                       is_valid=validation_result["is_valid"],
                       quality_score=quality_score)
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate welcome sequence", error=str(e))
            raise BaseLayerError(f"Failed to validate welcome sequence: {e}")
    
    async def report(self, sequence: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate welcome sequence completion report.
        
        Args:
            sequence: Generated welcome sequence
            validation: Validation results
            
        Returns:
            Dict with completion report
        """
        try:
            logger.info("Generating welcome sequence report")
            
            report = {
                "sequence_id": str(uuid.uuid4()),
                "sequence_name": sequence.get("name"),
                "sequence_type": "welcome",
                "status": "DRAFT" if validation["is_valid"] else "FAILED_VALIDATION",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sequence_data": sequence,
                "validation_results": validation,
                "welcome_metrics": {
                    "total_steps": len(sequence.get("steps", [])),
                    "total_words": sum(
                        len(step.get("content", "").split())
                        for step in sequence.get("steps", [])
                    ),
                    "average_words_per_email": self._calculate_average_words(sequence),
                    "quality_score": validation["quality_score"],
                    "validation_errors": len(validation["errors"]),
                    "validation_warnings": len(validation["warnings"]),
                    "welcome_compliance": validation["welcome_specific_checks"]
                },
                "implementation_notes": self._get_implementation_notes(sequence),
                "next_steps": self._get_welcome_next_steps(validation),
                "metadata": {
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    "processing_time": datetime.now(timezone.utc).isoformat()
                }
            }
            
            logger.info("Welcome sequence report generated", 
                       sequence_name=sequence.get("name"),
                       status=report["status"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate welcome sequence report", error=str(e))
            raise BaseLayerError(f"Failed to generate welcome sequence report: {e}")
    
    def _define_welcome_strategy(
        self, 
        company_name: str, 
        lead_magnet: str, 
        value_proposition: str, 
        main_product: str
    ) -> Dict[str, Any]:
        """Define welcome sequence content strategy."""
        return {
            "framework": "VALUE-FIRST",
            "persona": "Kade",
            "tone": "welcoming yet professional",
            "goals": [
                "Deliver lead magnet immediately",
                "Establish credibility and trust",
                "Demonstrate value proposition",
                "Build relationship through valuable content",
                "Drive towards main product offer"
            ],
            "steps": [
                {
                    "day": 0,
                    "purpose": "welcome_and_delivery",
                    "focus": "Immediate welcome + lead magnet delivery",
                    "key_elements": ["Welcome message", "Lead magnet access", "Set expectations"]
                },
                {
                    "day": 1,
                    "purpose": "common_mistake",
                    "focus": "#1 mistake people make in this area",
                    "key_elements": ["Problem identification", "Quick win", "Teaser for next email"]
                },
                {
                    "day": 3,
                    "purpose": "framework_introduction",
                    "focus": "Kade framework introduction",
                    "key_elements": ["Framework overview", "Practical application", "Case study preview"]
                },
                {
                    "day": 5,
                    "purpose": "results_and_proof",
                    "focus": "Results and social proof",
                    "key_elements": ["Success stories", "Testimonials", "Results framework"]
                },
                {
                    "day": 7,
                    "purpose": "subscriber_offer",
                    "focus": "Subscriber-only special offer",
                    "key_elements": ["Exclusive offer", "Urgency", "Clear call to action"]
                }
            ]
        }
    
    def _define_welcome_timing(self) -> Dict[str, Any]:
        """Define welcome sequence timing."""
        return {
            "delays": [
                {"value": 0, "unit": "minutes"},    # Immediate
                {"value": 24, "unit": "hours"},    # Day 1
                {"value": 72, "unit": "hours"},    # Day 3
                {"value": 120, "unit": "hours"},   # Day 5
                {"value": 168, "unit": "hours"}    # Day 7
            ],
            "send_window": "09:00-17:00",
            "skip_weekends": False,
            "timezone_aware": True
        }
    
    def _get_persona_rules(self) -> List[str]:
        """Get Kade persona enforcement rules."""
        return [
            "No personal anecdotes or stories",
            "No first-person references (I, my, etc.)",
            "Professional and authoritative tone",
            "Focus on actionable advice",
            "Value-driven content",
            "No placeholder text",
            "Complete all sections fully"
        ]
    
    def _get_quality_standards(self) -> List[str]:
        """Get quality standards for welcome sequence."""
        return [
            "Minimum 150 words per email",
            "Subject lines under 50 characters",
            "Clear value proposition in each email",
            "Progressive content building",
            "Strong call to action in final email",
            "CAN-SPAM compliance",
            "Mobile-responsive design consideration"
        ]
    
    async def _generate_welcome_step(
        self, 
        plan: Dict[str, Any], 
        step_config: Dict[str, Any], 
        step_num: int
    ) -> Dict[str, Any]:
        """Generate content for a specific welcome step."""
        try:
            # Get timing for this step
            timing_strategy = plan["timing_strategy"]
            delay = timing_strategy["delays"][step_num - 1]
            
            # Generate content using LLM
            prompt_context = {
                "step_number": step_num,
                "total_steps": self.sequence_length,
                "sequence_name": plan["sequence_name"],
                "step_purpose": step_config["purpose"],
                "step_focus": step_config["focus"],
                "key_elements": step_config["key_elements"],
                "company_name": plan["content_strategy"]["steps"][0].get("company_name", "Kade Digital"),
                "lead_magnet": plan.get("lead_magnet", ""),
                "delay": delay,
                "persona_rules": plan["kade_persona_enforcement"],
                "quality_standards": plan["quality_standards"]
            }
            
            # Render prompt template
            prompt = await prompt_engine.render_prompt(
                "welcome_step_writer_v1.j2",
                prompt_context
            )
            
            # Generate content with LLM
            response = await ollama_client.chat(
                messages=[
                    {"role": "system", "content": "You are Kade, creating a professional welcome email sequence."},
                    {"role": "user", "content": prompt}
                ],
                options=OllamaChatOptions(
                    temperature=0.6,  # Slightly lower temperature for consistency
                    max_tokens=1500
                )
            )
            
            # Parse response
            parsed_content = await response_parser.parse_json(response.response)
            
            # Structure step data
            step_data = {
                "step_number": step_num,
                "subject": parsed_content.get("subject", f"Welcome - Step {step_num}"),
                "preview_text": parsed_content.get("preview_text", ""),
                "template_name": "welcome_email",
                "delay": delay,
                "content": parsed_content.get("content", ""),
                "purpose": step_config["purpose"],
                "focus": step_config["focus"],
                "key_elements": step_config["key_elements"],
                "call_to_action": parsed_content.get("call_to_action", ""),
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "word_count": len(parsed_content.get("content", "").split()),
                    "welcome_specific": True
                }
            }
            
            return step_data
            
        except Exception as e:
            logger.error("Failed to generate welcome step", step=step_num, error=str(e))
            raise BaseLayerError(f"Failed to generate welcome step {step_num}: {e}")
    
    def _validate_welcome_structure(self, sequence: Dict[str, Any]) -> List[str]:
        """Validate welcome sequence structure."""
        errors = []
        
        if not sequence.get("name"):
            errors.append("Welcome sequence name is required")
        
        steps = sequence.get("steps", [])
        if len(steps) != self.sequence_length:
            errors.append(f"Welcome sequence must have exactly {self.sequence_length} steps")
        
        # Check for required steps
        required_purposes = [
            "welcome_and_delivery",
            "common_mistake", 
            "framework_introduction",
            "results_and_proof",
            "subscriber_offer"
        ]
        
        step_purposes = [step.get("purpose") for step in steps]
        for required_purpose in required_purposes:
            if required_purpose not in step_purposes:
                errors.append(f"Missing required step purpose: {required_purpose}")
        
        return errors
    
    async def _validate_welcome_step(self, step: Dict[str, Any], step_num: int) -> tuple[List[str], List[str]]:
        """Validate individual welcome step."""
        errors = []
        warnings = []
        
        # Subject validation
        subject = step.get("subject", "")
        if not subject:
            errors.append(f"Welcome Step {step_num}: Subject is required")
        elif len(subject) > 50:  # Stricter for welcome sequence
            warnings.append(f"Welcome Step {step_num}: Subject too long for welcome ({len(subject)} chars)")
        
        # Content validation
        content = step.get("content", "")
        if not content:
            errors.append(f"Welcome Step {step_num}: Content is required")
        elif len(content.split()) < 150:  # Higher minimum for welcome
            errors.append(f"Welcome Step {step_num}: Content too short for welcome ({len(content.split())} words)")
        
        # Check for welcome-specific elements
        step_purpose = step.get("purpose", "")
        if step_purpose == "welcome_and_delivery" and "lead magnet" not in content.lower():
            warnings.append(f"Welcome Step {step_num}: Should mention lead magnet delivery")
        
        if step_purpose == "subscriber_offer" and "offer" not in content.lower():
            warnings.append(f"Welcome Step {step_num}: Should include subscriber offer")
        
        # Check for Kade persona compliance (stricter for welcome)
        persona_violations = self._check_welcome_persona_compliance(content)
        if persona_violations:
            errors.extend([f"Welcome Step {step_num}: {violation}" for violation in persona_violations])
        
        return errors, warnings
    
    def _validate_welcome_flow(self, sequence: Dict[str, Any]) -> List[str]:
        """Validate welcome sequence flow."""
        errors = []
        steps = sequence.get("steps", [])
        
        # Check for progressive value building
        if len(steps) >= 2:
            # First email should be welcoming
            first_step = steps[0]
            if "welcome" not in first_step.get("content", "").lower():
                errors.append("First email should be clearly welcoming")
            
            # Last email should have strong CTA
            last_step = steps[-1]
            if "call to action" not in last_step.get("content", "").lower() and "cta" not in last_step.get("content", "").lower():
                errors.append("Final email should have strong call to action")
        
        return errors
    
    def _check_welcome_persona_compliance(self, content: str) -> List[str]:
        """Check content for Kade persona compliance (stricter for welcome)."""
        violations = []
        
        # Check for first-person references (strictly forbidden in welcome)
        first_person_strict = ["i am", "i have", "i think", "i believe", "my experience", "my story"]
        content_lower = content.lower()
        for indicator in first_person_strict:
            if indicator in content_lower:
                violations.append(f"First-person reference (strict): {indicator}")
        
        # Check for overly casual language
        casual_indicators = ["hey", "guys", "awesome", "cool", "super excited"]
        for indicator in casual_indicators:
            if indicator in content_lower:
                violations.append(f"Too casual for welcome: {indicator}")
        
        return violations
    
    def _calculate_welcome_quality_score(self, errors: int, warnings: int, steps: int) -> float:
        """Calculate quality score for welcome sequence."""
        if steps == 0:
            return 0.0
        
        # Base score starts at 100
        score = 100.0
        
        # Deduct more points for errors in welcome sequence
        score -= (errors * 15)  # Higher penalty for errors
        
        # Deduct points for warnings
        score -= (warnings * 3)
        
        # Bonus for perfect welcome sequence
        if errors == 0 and warnings == 0:
            score += 5
        
        # Ensure score doesn't go negative or exceed 100
        score = max(0.0, min(100.0, score))
        
        return score
    
    def _perform_welcome_specific_checks(self, sequence: Dict[str, Any]) -> Dict[str, bool]:
        """Perform welcome-specific validation checks."""
        checks = {}
        
        steps = sequence.get("steps", [])
        
        # Check for progressive complexity
        checks["progressive_complexity"] = self._check_progressive_complexity(steps)
        
        # Check for value delivery in each step
        checks["value_in_each_step"] = self._check_value_delivery(steps)
        
        # Check for proper welcome sequence structure
        checks["proper_welcome_structure"] = self._check_welcome_structure_flow(steps)
        
        # Check for engagement elements
        checks["engagement_elements"] = self._check_engagement_elements(steps)
        
        return checks
    
    def _check_progressive_complexity(self, steps: List[Dict[str, Any]]) -> bool:
        """Check if content complexity progresses appropriately."""
        word_counts = [len(step.get("content", "").split()) for step in steps]
        
        # Should generally increase in complexity/length
        for i in range(1, len(word_counts)):
            if word_counts[i] < word_counts[i-1] * 0.8:  # Allow some variation
                return False
        
        return True
    
    def _check_value_delivery(self, steps: List[Dict[str, Any]]) -> bool:
        """Check if each step delivers clear value."""
        value_indicators = ["learn", "discover", "get", "achieve", "implement", "apply"]
        
        for step in steps:
            content = step.get("content", "").lower()
            if not any(indicator in content for indicator in value_indicators):
                return False
        
        return True
    
    def _check_welcome_structure_flow(self, steps: List[Dict[str, Any]]) -> bool:
        """Check proper welcome sequence structure."""
        if len(steps) != 5:
            return False
        
        # Check that each step has its intended purpose
        expected_purposes = [
            "welcome_and_delivery",
            "common_mistake",
            "framework_introduction", 
            "results_and_proof",
            "subscriber_offer"
        ]
        
        actual_purposes = [step.get("purpose", "") for step in steps]
        return actual_purposes == expected_purposes
    
    def _check_engagement_elements(self, steps: List[Dict[str, Any]]) -> bool:
        """Check for engagement elements in emails."""
        engagement_indicators = ["question", "click", "reply", "comment", "share"]
        
        for step in steps:
            content = step.get("content", "").lower()
            if not any(indicator in content for indicator in engagement_indicators):
                return False
        
        return True
    
    def _generate_welcome_recommendations(self, errors: List[str], warnings: List[str]) -> List[str]:
        """Generate welcome-specific improvement recommendations."""
        recommendations = []
        
        if any("welcome" in error.lower() for error in errors):
            recommendations.append("Ensure first email clearly welcomes new subscribers")
        
        if any("lead magnet" in warning.lower() for warning in warnings):
            recommendations.append("Clearly mention lead magnet delivery in first email")
        
        if any("call to action" in error.lower() for error in errors):
            recommendations.append("Strengthen call to action in final email")
        
        if any("persona" in error.lower() for error in errors):
            recommendations.append("Review content to ensure strict Kade persona compliance")
        
        if any("too short" in error.lower() for error in errors):
            recommendations.append("Expand content to provide more value to new subscribers")
        
        recommendations.append("Test welcome sequence with new subscribers before full deployment")
        
        return recommendations
    
    def _calculate_average_words(self, sequence: Dict[str, Any]) -> float:
        """Calculate average words per email."""
        steps = sequence.get("steps", [])
        if not steps:
            return 0.0
        
        total_words = sum(
            len(step.get("content", "").split())
            for step in steps
        )
        
        return total_words / len(steps)
    
    def _get_implementation_notes(self, sequence: Dict[str, Any]) -> List[str]:
        """Get implementation notes for welcome sequence."""
        return [
            "Set up automatic enrollment for all new subscribers",
            "Ensure lead magnet delivery is working properly",
            "Monitor open and click rates for optimization",
            "Set up analytics tracking for each step",
            "Prepare subscriber-only offer landing page",
            "Test unsubscribe functionality",
            "Set up webhook tracking for engagement"
        ]
    
    def _get_welcome_next_steps(self, validation: Dict[str, Any]) -> List[str]:
        """Get next steps for welcome sequence."""
        next_steps = []
        
        if validation["is_valid"]:
            next_steps.extend([
                "Review welcome sequence content for final approval",
                "Set up automatic enrollment triggers",
                "Test lead magnet delivery process",
                "Configure analytics tracking",
                "Activate sequence for new subscribers"
            ])
        else:
            next_steps.extend([
                "Fix validation errors immediately",
                "Review persona compliance carefully",
                "Ensure all welcome-specific requirements are met",
                "Re-run validation process"
            ])
        
        if not validation["meets_threshold"]:
            next_steps.append("Consider regenerating with different parameters")
        
        if not validation["welcome_specific_checks"]["proper_welcome_structure"]:
            next_steps.append("Fix welcome sequence structure flow")
        
        return next_steps
