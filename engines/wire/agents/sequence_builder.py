"""
WIRE Sequence Builder Agent

AI-powered agent for creating email sequences with
AIDA framework, Kade persona, and quality controls.
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


class SequenceBuilder(AgentBase):
    """
    AI-powered email sequence builder agent.
    
    Creates automated email sequences using LLM with
    Kade persona, AIDA framework, and quality validation.
    """
    
    agent_name = "sequence_builder"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.quality_threshold = 0.8
        self.max_sequence_length = 10
        self.min_sequence_length = 3
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan email sequence structure.
        
        Args:
            input_data: Sequence brief with goals, audience, trigger conditions
            
        Returns:
            Dict containing sequence plan
        """
        try:
            logger.info("Planning email sequence", 
                       sequence_name=input_data.get("name"),
                       trigger=input_data.get("trigger"))
            
            # Extract sequence requirements
            sequence_name = input_data.get("name", "Untitled Sequence")
            description = input_data.get("description", "")
            trigger = input_data.get("trigger", "subscription")
            audience = input_data.get("audience", "general")
            goals = input_data.get("goals", [])
            tone = input_data.get("tone", "professional")
            sequence_length = input_data.get("sequence_length", 5)
            key_topics = input_data.get("key_topics", [])
            
            # Validate inputs
            if sequence_length < self.min_sequence_length:
                sequence_length = self.min_sequence_length
            elif sequence_length > self.max_sequence_length:
                sequence_length = self.max_sequence_length
            
            # Create sequence plan
            plan = {
                "sequence_name": sequence_name,
                "description": description,
                "trigger": trigger,
                "audience": audience,
                "goals": goals,
                "tone": tone,
                "sequence_length": sequence_length,
                "key_topics": key_topics,
                "content_strategy": self._plan_content_strategy(goals, audience, sequence_length),
                "timing_strategy": self._plan_timing_strategy(trigger, sequence_length),
                "quality_checks": self._get_quality_checklist()
            }
            
            logger.info("Sequence plan created", 
                       sequence_name=sequence_name,
                       steps=sequence_length)
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan sequence", error=str(e))
            raise BaseLayerError(f"Failed to plan sequence: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate email sequence content.
        
        Args:
            plan: Sequence plan from planning phase
            
        Returns:
            Dict containing generated sequence
        """
        try:
            logger.info("Executing sequence generation", 
                       sequence_name=plan["sequence_name"])
            
            sequence_steps = []
            sequence_length = plan["sequence_length"]
            
            # Generate each email in the sequence
            for step_num in range(1, sequence_length + 1):
                step_data = await self._generate_sequence_step(
                    plan, step_num, sequence_length
                )
                sequence_steps.append(step_data)
                
                logger.debug("Generated sequence step", 
                           step=step_num,
                           subject=step_data.get("subject"))
            
            # Create complete sequence
            sequence = {
                "name": plan["sequence_name"],
                "description": plan["description"],
                "trigger": plan["trigger"],
                "steps": sequence_steps,
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "agent_version": self.agent_version,
                    "plan": plan
                }
            }
            
            logger.info("Sequence generation completed", 
                       sequence_name=plan["sequence_name"],
                       steps=len(sequence_steps))
            
            return sequence
            
        except Exception as e:
            logger.error("Failed to execute sequence generation", error=str(e))
            raise BaseLayerError(f"Failed to execute sequence generation: {e}")
    
    async def validate(self, sequence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate generated sequence.
        
        Args:
            sequence: Generated sequence data
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating sequence", sequence_name=sequence.get("name"))
            
            validation_errors = []
            validation_warnings = []
            quality_score = 0.0
            
            # Basic structure validation
            structure_errors = self._validate_sequence_structure(sequence)
            validation_errors.extend(structure_errors)
            
            # Content validation for each step
            steps = sequence.get("steps", [])
            for i, step in enumerate(steps, 1):
                step_errors, step_warnings = await self._validate_step_content(step, i)
                validation_errors.extend(step_errors)
                validation_warnings.extend(step_warnings)
            
            # Overall sequence validation
            sequence_errors = self._validate_sequence_flow(sequence)
            validation_errors.extend(sequence_errors)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(
                len(validation_errors), len(validation_warnings), len(steps)
            )
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "quality_score": quality_score,
                "errors": validation_errors,
                "warnings": validation_warnings,
                "meets_threshold": quality_score >= self.quality_threshold,
                "recommendations": self._generate_recommendations(validation_errors, validation_warnings)
            }
            
            logger.info("Sequence validation completed", 
                       sequence_name=sequence.get("name"),
                       is_valid=validation_result["is_valid"],
                       quality_score=quality_score)
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate sequence", error=str(e))
            raise BaseLayerError(f"Failed to validate sequence: {e}")
    
    async def report(self, sequence: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completion report.
        
        Args:
            sequence: Generated sequence
            validation: Validation results
            
        Returns:
            Dict with completion report
        """
        try:
            logger.info("Generating sequence report")
            
            report = {
                "sequence_id": str(uuid.uuid4()),
                "sequence_name": sequence.get("name"),
                "status": "DRAFT" if validation["is_valid"] else "FAILED_VALIDATION",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sequence_data": sequence,
                "validation_results": validation,
                "statistics": {
                    "total_steps": len(sequence.get("steps", [])),
                    "total_words": sum(
                        len(step.get("content", "").split())
                        for step in sequence.get("steps", [])
                    ),
                    "average_words_per_email": self._calculate_average_words(sequence),
                    "quality_score": validation["quality_score"],
                    "validation_errors": len(validation["errors"]),
                    "validation_warnings": len(validation["warnings"])
                },
                "next_steps": self._get_next_steps(validation),
                "metadata": {
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    "processing_time": datetime.now(timezone.utc).isoformat()
                }
            }
            
            logger.info("Sequence report generated", 
                       sequence_name=sequence.get("name"),
                       status=report["status"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate report", error=str(e))
            raise BaseLayerError(f"Failed to generate report: {e}")
    
    def _plan_content_strategy(self, goals: List[str], audience: str, sequence_length: int) -> Dict[str, Any]:
        """Plan content strategy for the sequence."""
        return {
            "framework": "AIDA",  # Attention, Interest, Desire, Action
            "persona": "Kade",
            "tone": "professional and authoritative",
            "content_purpose": {
                "early_emails": "build trust and provide value",
                "middle_emails": "demonstrate expertise and results",
                "final_emails": "drive action and conversion"
            },
            "key_elements": [
                "compelling subject lines",
                "personalized greetings",
                "value-driven content",
                "clear calls to action",
                "professional signature"
            ]
        }
    
    def _plan_timing_strategy(self, trigger: str, sequence_length: int) -> Dict[str, Any]:
        """Plan timing strategy for the sequence."""
        if trigger == "subscription":
            # Welcome sequence timing
            delays = [
                {"value": 0, "unit": "days"},      # Day 0: Immediate
                {"value": 1, "unit": "days"},      # Day 1
                {"value": 2, "unit": "days"},      # Day 3
                {"value": 2, "unit": "days"},      # Day 5
                {"value": 2, "unit": "days"},      # Day 7
            ]
        elif trigger == "purchase":
            # Post-purchase sequence timing
            delays = [
                {"value": 0, "unit": "hours"},     # Immediate: Thank you
                {"value": 24, "unit": "hours"},    # Day 1: Getting started
                {"value": 72, "unit": "hours"},    # Day 3: Tips
                {"value": 168, "unit": "hours"},   # Day 7: Results
                {"value": 336, "unit": "hours"},   # Day 14: Upsell
            ]
        else:
            # Default timing
            delays = [
                {"value": i * 24, "unit": "hours"}
                for i in range(sequence_length)
            ]
        
        return {
            "delays": delays[:sequence_length],
            "send_window": "09:00-17:00",
            "skip_weekends": False,
            "timezone_aware": True
        }
    
    def _get_quality_checklist(self) -> List[str]:
        """Get quality checklist for validation."""
        return [
            "Subject line under 60 characters",
            "No placeholder text",
            "Kade persona maintained",
            "AIDA framework followed",
            "Unsubscribe link included",
            "Professional tone",
            "Value-driven content",
            "Clear call to action",
            "No spam triggers",
            "CAN-SPAM compliance"
        ]
    
    async def _generate_sequence_step(
        self, 
        plan: Dict[str, Any], 
        step_num: int, 
        total_steps: int
    ) -> Dict[str, Any]:
        """Generate content for a specific sequence step."""
        try:
            # Determine step purpose based on position
            step_purpose = self._get_step_purpose(step_num, total_steps, plan["goals"])
            
            # Get timing for this step
            timing_strategy = plan["timing_strategy"]
            delay = timing_strategy["delays"][step_num - 1] if step_num <= len(timing_strategy["delays"]) else {"value": 24, "unit": "hours"}
            
            # Generate content using LLM
            prompt_context = {
                "step_number": step_num,
                "total_steps": total_steps,
                "sequence_name": plan["sequence_name"],
                "description": plan["description"],
                "audience": plan["audience"],
                "step_purpose": step_purpose,
                "key_topics": plan["key_topics"],
                "tone": plan["tone"],
                "delay": delay
            }
            
            # Render prompt template
            prompt = await prompt_engine.render_prompt(
                "sequence_step_writer_v1.j2",
                prompt_context
            )
            
            # Generate content with LLM
            response = await ollama_client.chat(
                messages=[
                    {"role": "system", "content": "You are Kade, a professional email sequence writer."},
                    {"role": "user", "content": prompt}
                ],
                options=OllamaChatOptions(
                    temperature=0.7,
                    max_tokens=2000
                )
            )
            
            # Parse response
            parsed_content = await response_parser.parse_json(response.response)
            
            # Structure step data
            step_data = {
                "step_number": step_num,
                "subject": parsed_content.get("subject", f"Step {step_num}"),
                "preview_text": parsed_content.get("preview_text", ""),
                "template_name": "sequence_email",
                "delay": delay,
                "content": parsed_content.get("content", ""),
                "purpose": step_purpose,
                "key_points": parsed_content.get("key_points", []),
                "call_to_action": parsed_content.get("call_to_action", ""),
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "word_count": len(parsed_content.get("content", "").split())
                }
            }
            
            return step_data
            
        except Exception as e:
            logger.error("Failed to generate sequence step", step=step_num, error=str(e))
            raise BaseLayerError(f"Failed to generate sequence step {step_num}: {e}")
    
    def _get_step_purpose(self, step_num: int, total_steps: int, goals: List[str]) -> str:
        """Determine the purpose of a specific step."""
        if step_num == 1:
            return "introduction_and_welcome"
        elif step_num == total_steps:
            return "final_action_and_conversion"
        elif step_num <= total_steps * 0.3:
            return "build_trust_and_value"
        elif step_num <= total_steps * 0.7:
            return "demonstrate_expertise"
        else:
            return "drive_action"
    
    def _validate_sequence_structure(self, sequence: Dict[str, Any]) -> List[str]:
        """Validate basic sequence structure."""
        errors = []
        
        if not sequence.get("name"):
            errors.append("Sequence name is required")
        
        if not sequence.get("trigger"):
            errors.append("Sequence trigger is required")
        
        steps = sequence.get("steps", [])
        if len(steps) < self.min_sequence_length:
            errors.append(f"Sequence must have at least {self.min_sequence_length} steps")
        
        if len(steps) > self.max_sequence_length:
            errors.append(f"Sequence cannot have more than {self.max_sequence_length} steps")
        
        return errors
    
    async def _validate_step_content(self, step: Dict[str, Any], step_num: int) -> tuple[List[str], List[str]]:
        """Validate individual step content."""
        errors = []
        warnings = []
        
        # Subject validation
        subject = step.get("subject", "")
        if not subject:
            errors.append(f"Step {step_num}: Subject is required")
        elif len(subject) > 60:
            warnings.append(f"Step {step_num}: Subject too long ({len(subject)} chars)")
        
        # Content validation
        content = step.get("content", "")
        if not content:
            errors.append(f"Step {step_num}: Content is required")
        elif len(content.split()) < 100:
            warnings.append(f"Step {step_num}: Content too short ({len(content.split())} words)")
        
        # Check for placeholder text
        placeholder_indicators = ["lorem ipsum", "placeholder", "[", "]", "{{", "}}"]
        content_lower = content.lower()
        for indicator in placeholder_indicators:
            if indicator in content_lower:
                errors.append(f"Step {step_num}: Contains placeholder text: {indicator}")
        
        # Check for unsubscribe link
        if "unsubscribe" not in content.lower():
            errors.append(f"Step {step_num}: Missing unsubscribe link")
        
        # Check for Kade persona compliance
        persona_violations = self._check_persona_compliance(content)
        if persona_violations:
            warnings.extend([f"Step {step_num}: {violation}" for violation in persona_violations])
        
        return errors, warnings
    
    def _validate_sequence_flow(self, sequence: Dict[str, Any]) -> List[str]:
        """Validate overall sequence flow and logic."""
        errors = []
        steps = sequence.get("steps", [])
        
        # Check for logical progression
        for i, step in enumerate(steps, 1):
            delay = step.get("delay", {})
            if not delay.get("value"):
                errors.append(f"Step {i}: Missing delay value")
        
        # Check for consistent timing
        delays = [step.get("delay", {}).get("value", 0) for step in steps]
        if any(d < 0 for d in delays):
            errors.append("Negative delays found in sequence")
        
        return errors
    
    def _check_persona_compliance(self, content: str) -> List[str]:
        """Check content for Kade persona compliance."""
        violations = []
        
        # Check for first-person references
        first_person_indicators = ["i think", "i believe", "in my opinion", "my experience"]
        content_lower = content.lower()
        for indicator in first_person_indicators:
            if indicator in content_lower:
                violations.append(f"First-person reference: {indicator}")
        
        # Check for personal anecdotes
        anecdote_indicators = ["when i", "i once", "my story", "personally"]
        for indicator in anecdote_indicators:
            if indicator in content_lower:
                violations.append(f"Personal anecdote: {indicator}")
        
        return violations
    
    def _calculate_quality_score(self, errors: int, warnings: int, steps: int) -> float:
        """Calculate overall quality score."""
        if steps == 0:
            return 0.0
        
        # Base score starts at 100
        score = 100.0
        
        # Deduct points for errors (more severe)
        score -= (errors * 10)
        
        # Deduct points for warnings (less severe)
        score -= (warnings * 2)
        
        # Ensure score doesn't go negative
        score = max(0.0, score)
        
        return score
    
    def _generate_recommendations(self, errors: List[str], warnings: List[str]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        if any("subject" in error.lower() for error in errors):
            recommendations.append("Review and improve subject lines for clarity and impact")
        
        if any("placeholder" in error.lower() for error in errors):
            recommendations.append("Replace all placeholder text with actual content")
        
        if any("unsubscribe" in error.lower() for error in errors):
            recommendations.append("Add unsubscribe links to all emails")
        
        if any("persona" in warning.lower() for warning in warnings):
            recommendations.append("Review content to maintain Kade persona consistency")
        
        if any("short" in warning.lower() for warning in warnings):
            recommendations.append("Expand content to provide more value to readers")
        
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
    
    def _get_next_steps(self, validation: Dict[str, Any]) -> List[str]:
        """Get next steps based on validation results."""
        next_steps = []
        
        if validation["is_valid"]:
            next_steps.extend([
                "Review sequence content for final approval",
                "Test sequence with sample subscribers",
                "Activate sequence in production"
            ])
        else:
            next_steps.extend([
                "Fix validation errors",
                "Review and improve content quality",
                "Re-run validation process"
            ])
        
        if not validation["meets_threshold"]:
            next_steps.append("Consider regenerating sequence with different parameters")
        
        return next_steps
