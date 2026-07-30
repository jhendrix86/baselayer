"""
PULSE Broadcast Writer Agent

AI-powered agent for generating newsletter and broadcast
content with Kade persona and engagement optimization.
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


class BroadcastWriter(AgentBase):
    """
    AI-powered broadcast content generator.
    
    Creates newsletter and broadcast content using LLM with
    Kade persona, engagement optimization, and quality controls.
    """
    
    agent_name = "broadcast_writer"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.quality_threshold = 0.8
        self.min_word_count = 300
        self.max_word_count = 800
        self.target_reading_time = 5  # minutes
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan broadcast content generation.
        
        Args:
            input_data: Broadcast brief with topics, audience, goals
            
        Returns:
            Dict containing broadcast plan
        """
        try:
            logger.info("Planning broadcast content", 
                       broadcast_name=input_data.get("name"),
                       broadcast_type=input_data.get("type"))
            
            # Extract broadcast requirements
            broadcast_name = input_data.get("name", "Untitled Broadcast")
            broadcast_type = input_data.get("type", "newsletter")
            target_audience = input_data.get("audience", "general subscribers")
            primary_topic = input_data.get("primary_topic", "")
            secondary_topics = input_data.get("secondary_topics", [])
            goals = input_data.get("goals", [])
            tone = input_data.get("tone", "professional")
            call_to_action = input_data.get("call_to_action", "")
            key_insights = input_data.get("key_insights", [])
            
            # Create content plan
            plan = {
                "broadcast_name": broadcast_name,
                "broadcast_type": broadcast_type,
                "target_audience": target_audience,
                "primary_topic": primary_topic,
                "secondary_topics": secondary_topics,
                "goals": goals,
                "tone": tone,
                "call_to_action": call_to_action,
                "key_insights": key_insights,
                "content_structure": self._plan_broadcast_structure(broadcast_type, goals),
                "engagement_strategy": self._plan_engagement_strategy(target_audience),
                "quality_requirements": self._get_quality_requirements(),
                "kade_persona_guidelines": self._get_persona_guidelines()
            }
            
            logger.info("Broadcast plan created", 
                       broadcast_name=broadcast_name,
                       structure=plan["content_structure"]["framework"])
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan broadcast content", error=str(e))
            raise BaseLayerError(f"Failed to plan broadcast content: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate broadcast content.
        
        Args:
            plan: Broadcast plan from planning phase
            
        Returns:
            Dict containing generated broadcast
        """
        try:
            logger.info("Executing broadcast content generation", 
                       broadcast_name=plan["broadcast_name"])
            
            # Generate main content
            content = await self._generate_broadcast_content(plan)
            
            # Generate subject lines
            subject_lines = await self._generate_subject_lines(plan, content)
            
            # Generate preview text
            preview_text = await self._generate_preview_text(plan, content)
            
            # Create complete broadcast
            broadcast = {
                "name": plan["broadcast_name"],
                "subject": subject_lines[0],  # Use best subject line
                "preview_text": preview_text,
                "content_md": content["markdown"],
                "content_html": content["html"],
                "content_text": content["plain_text"],
                "broadcast_type": plan["broadcast_type"],
                "template_name": "newsletter",
                "word_count": content["word_count"],
                "reading_time_minutes": content["reading_time"],
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "agent_version": self.agent_version,
                    "plan": plan,
                    "alternative_subjects": subject_lines[1:3]  # Top alternatives
                }
            }
            
            logger.info("Broadcast content generated", 
                       broadcast_name=plan["broadcast_name"],
                       word_count=broadcast["word_count"])
            
            return broadcast
            
        except Exception as e:
            logger.error("Failed to execute broadcast content generation", error=str(e))
            raise BaseLayerError(f"Failed to execute broadcast content generation: {e}")
    
    async def validate(self, broadcast: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate generated broadcast content.
        
        Args:
            broadcast: Generated broadcast data
            
        Returns:
            Dict with validation results
        """
        try:
            logger.info("Validating broadcast content", broadcast_name=broadcast.get("name"))
            
            validation_errors = []
            validation_warnings = []
            quality_score = 0.0
            
            # Basic structure validation
            structure_errors = self._validate_broadcast_structure(broadcast)
            validation_errors.extend(structure_errors)
            
            # Content validation
            content_errors, content_warnings = await self._validate_broadcast_content(broadcast)
            validation_errors.extend(content_errors)
            validation_warnings.extend(content_warnings)
            
            # Kade persona validation
            persona_errors = self._validate_kade_persona(broadcast)
            validation_errors.extend(persona_errors)
            
            # Engagement validation
            engagement_warnings = self._validate_engagement_elements(broadcast)
            validation_warnings.extend(engagement_warnings)
            
            # Calculate quality score
            quality_score = self._calculate_broadcast_quality_score(
                len(validation_errors), len(validation_warnings), broadcast
            )
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "quality_score": quality_score,
                "errors": validation_errors,
                "warnings": validation_warnings,
                "meets_threshold": quality_score >= self.quality_threshold,
                "content_metrics": self._get_content_metrics(broadcast),
                "engagement_predictions": self._predict_engagement(broadcast),
                "recommendations": self._generate_broadcast_recommendations(
                    validation_errors, validation_warnings
                )
            }
            
            logger.info("Broadcast validation completed", 
                       broadcast_name=broadcast.get("name"),
                       is_valid=validation_result["is_valid"],
                       quality_score=quality_score)
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate broadcast content", error=str(e))
            raise BaseLayerError(f"Failed to validate broadcast content: {e}")
    
    async def report(self, broadcast: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completion report.
        
        Args:
            broadcast: Generated broadcast
            validation: Validation results
            
        Returns:
            Dict with completion report
        """
        try:
            logger.info("Generating broadcast report")
            
            report = {
                "broadcast_id": str(uuid.uuid4()),
                "broadcast_name": broadcast.get("name"),
                "broadcast_type": broadcast.get("broadcast_type"),
                "status": "DRAFT" if validation["is_valid"] else "FAILED_VALIDATION",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "broadcast_data": broadcast,
                "validation_results": validation,
                "content_analysis": {
                    "word_count": broadcast.get("word_count", 0),
                    "reading_time": broadcast.get("reading_time_minutes", 0),
                    "subject_length": len(broadcast.get("subject", "")),
                    "preview_length": len(broadcast.get("preview_text", "")),
                    "content_sections": self._analyze_content_sections(broadcast),
                    "key_topics": self._extract_key_topics(broadcast)
                },
                "performance_predictions": {
                    "expected_open_rate": validation["engagement_predictions"]["open_rate"],
                    "expected_click_rate": validation["engagement_predictions"]["click_rate"],
                    "engagement_score": validation["engagement_predictions"]["overall_score"]
                },
                "implementation_notes": self._get_implementation_notes(broadcast),
                "next_steps": self._get_broadcast_next_steps(validation),
                "metadata": {
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    "processing_time": datetime.now(timezone.utc).isoformat()
                }
            }
            
            logger.info("Broadcast report generated", 
                       broadcast_name=broadcast.get("name"),
                       status=report["status"])
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate broadcast report", error=str(e))
            raise BaseLayerError(f"Failed to generate broadcast report: {e}")
    
    def _plan_broadcast_structure(self, broadcast_type: str, goals: List[str]) -> Dict[str, Any]:
        """Plan broadcast content structure."""
        if broadcast_type == "newsletter":
            return {
                "framework": "HOOK-VALUE-CTA",
                "sections": [
                    {
                        "name": "hook",
                        "purpose": "grab attention with compelling opening",
                        "estimated_words": 50
                    },
                    {
                        "name": "value_section_1",
                        "purpose": "deliver primary value/content",
                        "estimated_words": 200
                    },
                    {
                        "name": "value_section_2",
                        "purpose": "deliver secondary value/content",
                        "estimated_words": 200
                    },
                    {
                        "name": "cta",
                        "purpose": "clear call to action",
                        "estimated_words": 50
                    },
                    {
                        "name": "ps",
                        "purpose": "postscript with urgency/reminder",
                        "estimated_words": 30
                    }
                ]
            }
        else:
            return {
                "framework": "PROBLEM-SOLUTION-ACTION",
                "sections": [
                    {
                        "name": "problem",
                        "purpose": "identify reader's problem",
                        "estimated_words": 100
                    },
                    {
                        "name": "solution",
                        "purpose": "present solution/value",
                        "estimated_words": 300
                    },
                    {
                        "name": "action",
                        "purpose": "call to action",
                        "estimated_words": 100
                    }
                ]
            }
    
    def _plan_engagement_strategy(self, target_audience: str) -> Dict[str, Any]:
        """Plan engagement strategy based on audience."""
        return {
            "tone": "professional yet approachable",
            "language_complexity": "moderate",
            "content_density": "balanced",
            "engagement_hooks": [
                "thought-provoking questions",
                "surprising statistics",
                "actionable insights",
                "relevant examples"
            ],
            "personalization_elements": [
                "audience-specific references",
                "relevant pain points",
                "aspirational language"
            ]
        }
    
    def _get_quality_requirements(self) -> List[str]:
        """Get quality requirements for broadcast content."""
        return [
            "Minimum 300 words, maximum 800 words",
            "Clear value proposition",
            "Engaging hook in first 50 words",
            "Strong call to action",
            "Kade persona compliance",
            "No placeholder text",
            "CAN-SPAM compliance",
            "Mobile-friendly formatting"
        ]
    
    def _get_persona_guidelines(self) -> List[str]:
        """Get Kade persona guidelines."""
        return [
            "Professional and authoritative tone",
            "No personal anecdotes or stories",
            "No first-person references",
            "Focus on actionable advice",
            "Value-driven content",
            "Clear and concise language",
            "Expert-level insights"
        ]
    
    async def _generate_broadcast_content(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Generate main broadcast content."""
        try:
            # Create prompt context
            prompt_context = {
                "broadcast_name": plan["broadcast_name"],
                "broadcast_type": plan["broadcast_type"],
                "target_audience": plan["target_audience"],
                "primary_topic": plan["primary_topic"],
                "secondary_topics": plan["secondary_topics"],
                "goals": plan["goals"],
                "tone": plan["tone"],
                "call_to_action": plan["call_to_action"],
                "key_insights": plan["key_insights"],
                "content_structure": plan["content_structure"],
                "engagement_strategy": plan["engagement_strategy"],
                "word_count_target": self.target_reading_time * 200,  # 200 words per minute
                "persona_guidelines": plan["kade_persona_guidelines"]
            }
            
            # Render prompt template
            prompt = await prompt_engine.render_prompt(
                "newsletter_writer_v1.j2",
                prompt_context
            )
            
            # Generate content with LLM
            response = await ollama_client.chat(
                messages=[
                    {"role": "system", "content": "You are Kade, writing professional broadcast content."},
                    {"role": "user", "content": prompt}
                ],
                options=OllamaChatOptions(
                    temperature=0.7,
                    max_tokens=2500
                )
            )
            
            # Parse response
            parsed_content = await response_parser.parse_json(response.response)
            
            # Structure content
            content = {
                "markdown": parsed_content.get("content", ""),
                "html": parsed_content.get("html_content", ""),
                "plain_text": parsed_content.get("plain_text", ""),
                "word_count": len(parsed_content.get("content", "").split()),
                "reading_time": max(1, len(parsed_content.get("content", "").split()) // 200),
                "sections": parsed_content.get("sections", {})
            }
            
            return content
            
        except Exception as e:
            logger.error("Failed to generate broadcast content", error=str(e))
            raise BaseLayerError(f"Failed to generate broadcast content: {e}")
    
    async def _generate_subject_lines(self, plan: Dict[str, Any], content: Dict[str, Any]) -> List[str]:
        """Generate multiple subject line options."""
        try:
            prompt_context = {
                "broadcast_name": plan["broadcast_name"],
                "primary_topic": plan["primary_topic"],
                "key_insights": plan["key_insights"],
                "content_preview": content["markdown"][:200],  # First 200 chars
                "target_audience": plan["target_audience"]
            }
            
            # Render prompt template
            prompt = await prompt_engine.render_prompt(
                "subject_line_v1.j2",
                prompt_context
            )
            
            # Generate subject lines with LLM
            response = await ollama_client.chat(
                messages=[
                    {"role": "system", "content": "You are Kade, writing compelling email subject lines."},
                    {"role": "user", "content": prompt}
                ],
                options=OllamaChatOptions(
                    temperature=0.8,
                    max_tokens=500
                )
            )
            
            # Parse response
            parsed_subjects = await response_parser.parse_json(response.response)
            
            subject_lines = parsed_subjects.get("subject_lines", [])
            
            # Ensure we have at least one subject line
            if not subject_lines:
                subject_lines = [f"Kade Insights: {plan['primary_topic']}"]
            
            return subject_lines[:5]  # Return top 5 options
            
        except Exception as e:
            logger.error("Failed to generate subject lines", error=str(e))
            # Fallback subject line
            return [f"Kade Insights: {plan.get('primary_topic', 'Latest Update')}"]
    
    async def _generate_preview_text(self, plan: Dict[str, Any], content: Dict[str, Any]) -> str:
        """Generate preview text for email clients."""
        try:
            # Extract first sentence or create preview
            content_text = content.get("plain_text", content.get("markdown", ""))
            
            # Get first sentence
            sentences = content_text.split('.')
            if sentences and sentences[0].strip():
                preview = sentences[0].strip()
                # Truncate to 150 characters
                if len(preview) > 150:
                    preview = preview[:147] + "..."
            else:
                # Fallback preview
                preview = f"Latest insights on {plan.get('primary_topic', 'professional growth')}"
            
            return preview
            
        except Exception as e:
            logger.error("Failed to generate preview text", error=str(e))
            return f"Latest insights from Kade on {plan.get('primary_topic', 'professional topics')}"
    
    def _validate_broadcast_structure(self, broadcast: Dict[str, Any]) -> List[str]:
        """Validate basic broadcast structure."""
        errors = []
        
        if not broadcast.get("name"):
            errors.append("Broadcast name is required")
        
        if not broadcast.get("subject"):
            errors.append("Subject is required")
        
        if not broadcast.get("content_md"):
            errors.append("Markdown content is required")
        
        if not broadcast.get("content_html"):
            errors.append("HTML content is required")
        
        return errors
    
    async def _validate_broadcast_content(self, broadcast: Dict[str, Any]) -> tuple[List[str], List[str]]:
        """Validate broadcast content."""
        errors = []
        warnings = []
        
        content = broadcast.get("content_md", "")
        word_count = len(content.split())
        
        # Word count validation
        if word_count < self.min_word_count:
            errors.append(f"Content too short: {word_count} words (minimum {self.min_word_count})")
        elif word_count > self.max_word_count:
            warnings.append(f"Content long: {word_count} words (maximum {self.max_word_count})")
        
        # Subject validation
        subject = broadcast.get("subject", "")
        if len(subject) > 60:
            warnings.append(f"Subject long: {len(subject)} characters (recommend under 60)")
        
        # Check for placeholder text
        placeholder_indicators = ["lorem ipsum", "placeholder", "[", "]", "{{", "}}"]
        content_lower = content.lower()
        for indicator in placeholder_indicators:
            if indicator in content_lower:
                errors.append(f"Contains placeholder text: {indicator}")
        
        # Check for unsubscribe link
        if "unsubscribe" not in content.lower():
            errors.append("Missing unsubscribe link")
        
        # Check for value proposition
        if not any(value in content.lower() for value in ["learn", "discover", "get", "achieve"]):
            warnings.append("Could benefit from clearer value proposition")
        
        return errors, warnings
    
    def _validate_kade_persona(self, broadcast: Dict[str, Any]) -> List[str]:
        """Validate Kade persona compliance."""
        errors = []
        
        content = broadcast.get("content_md", "")
        content_lower = content.lower()
        
        # Check for first-person references
        first_person_indicators = ["i think", "i believe", "in my opinion", "my experience", "i have"]
        for indicator in first_person_indicators:
            if indicator in content_lower:
                errors.append(f"First-person reference: {indicator}")
        
        # Check for personal anecdotes
        anecdote_indicators = ["when i", "i once", "my story", "personally", "in my role"]
        for indicator in anecdote_indicators:
            if indicator in content_lower:
                errors.append(f"Personal anecdote: {indicator}")
        
        # Check for overly casual language
        casual_indicators = ["hey", "guys", "awesome", "cool", "super excited"]
        for indicator in casual_indicators:
            if indicator in content_lower:
                errors.append(f"Too casual: {indicator}")
        
        return errors
    
    def _validate_engagement_elements(self, broadcast: Dict[str, Any]) -> List[str]:
        """Validate engagement elements."""
        warnings = []
        
        content = broadcast.get("content_md", "")
        content_lower = content.lower()
        
        # Check for engagement hooks
        engagement_indicators = ["question", "did you know", "imagine", "what if", "how to"]
        if not any(indicator in content_lower for indicator in engagement_indicators):
            warnings.append("Could benefit from engagement hooks")
        
        # Check for clear call to action
        cta_indicators = ["click here", "learn more", "get started", "download", "sign up"]
        if not any(indicator in content_lower for indicator in cta_indicators):
            warnings.append("Could benefit from clearer call to action")
        
        # Check for formatting
        if not any(marker in content for marker in ["#", "##", "###", "*", "**"]):
            warnings.append("Could benefit from better formatting")
        
        return warnings
    
    def _calculate_broadcast_quality_score(self, errors: int, warnings: int, broadcast: Dict[str, Any]) -> float:
        """Calculate quality score for broadcast."""
        score = 100.0
        
        # Deduct points for errors
        score -= (errors * 12)
        
        # Deduct points for warnings
        score -= (warnings * 3)
        
        # Bonus for meeting word count targets
        word_count = broadcast.get("word_count", 0)
        if self.min_word_count <= word_count <= self.max_word_count:
            score += 5
        
        # Bonus for good subject length
        subject_len = len(broadcast.get("subject", ""))
        if subject_len <= 50:
            score += 3
        
        # Ensure score doesn't go negative or exceed 100
        score = max(0.0, min(100.0, score))
        
        return score
    
    def _get_content_metrics(self, broadcast: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed content metrics."""
        content = broadcast.get("content_md", "")
        
        return {
            "word_count": broadcast.get("word_count", 0),
            "character_count": len(content),
            "paragraph_count": len([p for p in content.split('\n') if p.strip()]),
            "sentence_count": len(content.split('.')),
            "average_sentence_length": len(content.split()) / max(1, len(content.split('.'))),
            "reading_time": broadcast.get("reading_time_minutes", 0),
            "subject_length": len(broadcast.get("subject", "")),
            "preview_length": len(broadcast.get("preview_text", ""))
        }
    
    def _predict_engagement(self, broadcast: Dict[str, Any]) -> Dict[str, Any]:
        """Predict engagement metrics."""
        # Simple prediction based on content characteristics
        base_open_rate = 25.0  # Base 25% open rate
        base_click_rate = 3.0   # Base 3% click rate
        
        # Adjust based on subject
        subject = broadcast.get("subject", "")
        if any(indicator in subject.lower() for indicator in ["free", "new", "guide", "tips"]):
            base_open_rate += 5
        
        # Adjust based on content length
        word_count = broadcast.get("word_count", 0)
        if 300 <= word_count <= 600:
            base_click_rate += 2
        
        # Adjust based on content quality indicators
        content = broadcast.get("content_md", "")
        if any(indicator in content.lower() for indicator in ["how to", "step", "guide"]):
            base_click_rate += 3
        
        overall_score = (base_open_rate / 50) * 0.6 + (base_click_rate / 10) * 0.4
        
        return {
            "open_rate": min(50.0, base_open_rate),
            "click_rate": min(15.0, base_click_rate),
            "overall_score": min(1.0, overall_score)
        }
    
    def _generate_broadcast_recommendations(self, errors: List[str], warnings: List[str]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        if any("subject" in error.lower() for error in errors):
            recommendations.append("Improve subject line for better open rates")
        
        if any("placeholder" in error.lower() for error in errors):
            recommendations.append("Replace all placeholder text with actual content")
        
        if any("unsubscribe" in error.lower() for error in errors):
            recommendations.append("Add unsubscribe link for CAN-SPAM compliance")
        
        if any("persona" in error.lower() for error in errors):
            recommendations.append("Review content for Kade persona compliance")
        
        if any("engagement" in warning.lower() for warning in warnings):
            recommendations.append("Add engagement hooks like questions or surprising facts")
        
        if any("call to action" in warning.lower() for warning in warnings):
            recommendations.append("Strengthen call to action for better conversion")
        
        return recommendations
    
    def _analyze_content_sections(self, broadcast: Dict[str, Any]) -> List[str]:
        """Analyze content sections."""
        content = broadcast.get("content_md", "")
        sections = []
        
        # Simple section analysis based on markdown headers
        lines = content.split('\n')
        current_section = ""
        
        for line in lines:
            if line.startswith('#'):
                if current_section:
                    sections.append(current_section.strip())
                current_section = line
            elif current_section:
                current_section += " " + line.strip()
        
        if current_section:
            sections.append(current_section.strip())
        
        return sections
    
    def _extract_key_topics(self, broadcast: Dict[str, Any]) -> List[str]:
        """Extract key topics from content."""
        content = broadcast.get("content_md", "").lower()
        
        # Simple keyword extraction (could be enhanced with NLP)
        business_topics = ["marketing", "sales", "strategy", "growth", "revenue"]
        tech_topics = ["software", "technology", "automation", "ai", "data"]
        personal_topics = ["productivity", "skills", "career", "leadership", "management"]
        
        topics = []
        for topic_list in [business_topics, tech_topics, personal_topics]:
            for topic in topic_list:
                if topic in content:
                    topics.append(topic)
        
        return topics[:5]  # Return top 5 topics
    
    def _get_implementation_notes(self, broadcast: Dict[str, Any]) -> List[str]:
        """Get implementation notes."""
        return [
            "Review content for brand voice consistency",
            "Test rendering across email clients",
            "Set up tracking links for call to action",
            "Prepare A/B test variants if needed",
            "Schedule optimal send time for audience",
            "Set up analytics tracking"
        ]
    
    def _get_broadcast_next_steps(self, validation: Dict[str, Any]) -> List[str]:
        """Get next steps based on validation."""
        next_steps = []
        
        if validation["is_valid"]:
            next_steps.extend([
                "Review content for final approval",
                "Set up A/B testing if desired",
                "Schedule broadcast for optimal time",
                "Prepare tracking and analytics",
                "Test email rendering"
            ])
        else:
            next_steps.extend([
                "Fix validation errors immediately",
                "Review content quality and persona compliance",
                "Improve engagement elements",
                "Re-run validation process"
            ])
        
        if not validation["meets_threshold"]:
            next_steps.append("Consider regenerating with different parameters")
        
        if validation["engagement_predictions"]["open_rate"] < 20:
            next_steps.append("Improve subject line for better open rates")
        
        return next_steps
