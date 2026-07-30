"""
CODEX Knowledge Ingester Agent

AgentBase implementation for extracting and storing knowledge
from various sources like text, URLs, and structured data.
"""

import uuid
import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..api.knowledge_manager import KnowledgeManager
from ..models.knowledge_entry import KnowledgeEntryType, SourceEngine

logger = get_logger(__name__)


class KnowledgeIngester(AgentBase):
    """
    Agent for extracting and storing knowledge from various sources.
    
    Processes raw text, URLs, and structured data to extract
    key facts, categorize them, assign tags and confidence scores,
    and store them in the knowledge base.
    """
    
    agent_name = "knowledge_ingester"
    agent_version = "1.0.0"
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        memory_interface: Optional[MemoryInterface] = None
    ):
        """Initialize knowledge ingester agent."""
        super().__init__(config)
        self.knowledge_manager = knowledge_manager
        self.memory_interface = memory_interface
        
        # Ingestion patterns for different content types
        self.fact_patterns = [
            r"(.+?)\s+(?:is|are|was|were)\s+(.+?)\.",  # X is Y
            r"(.+?)\s+(?:has|have)\s+(.+?)\.",  # X has Y
            r"(.+?)\s+(?:can|could|will|would)\s+(.+?)\.",  # X can Y
            r"(.+?)\s+(?:should|must|shall)\s+(.+?)\.",  # X should Y
        ]
        
        self.decision_patterns = [
            r"(.+?)\s+(?:decided|chose|selected)\s+(.+?)\.",
            r"(.+?)\s+(?:determined|concluded)\s+(.+?)\.",
            r"(.+?)\s+(?:agreed|approved)\s+(.+?)\.",
        ]
        
        self.pattern_patterns = [
            r"(.+?)\s+(?:follows|matches)\s+(.+?)\.",
            r"(.+?)\s+(?:indicates|suggests)\s+(.+?)\.",
            r"(.+?)\s+(?:results in|leads to)\s+(.+?)\.",
        ]
        
        logger.info("KnowledgeIngester initialized")
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan knowledge extraction from input data.
        
        Args:
            input_data: Contains source data (text, URL, structured data)
            
        Returns:
            Extraction plan
        """
        try:
            logger.info("Planning knowledge extraction", 
                       source_type=input_data.get("source_type"))
            
            source_type = input_data.get("source_type", "text")
            source_data = input_data.get("source_data", "")
            
            # Analyze source and create extraction plan
            plan = {
                "source_type": source_type,
                "source_data_length": len(source_data),
                "extraction_strategy": self._determine_extraction_strategy(source_type, source_data),
                "expected_entries": self._estimate_entry_count(source_data),
                "processing_steps": self._get_processing_steps(source_type),
                "quality_checks": self._get_quality_checks(),
                "metadata": {
                    "source": input_data.get("source", "unknown"),
                    "engine": input_data.get("engine", "manual"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            logger.info("Knowledge extraction plan created", 
                       source_type=source_type,
                       expected_entries=plan["expected_entries"])
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan knowledge extraction", error=str(e))
            raise BaseLayerError(f"Failed to plan knowledge extraction: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute knowledge extraction and storage.
        
        Args:
            plan: Extraction plan from planning phase
            
        Returns:
            Extraction results
        """
        try:
            logger.info("Executing knowledge extraction", 
                       source_type=plan["source_type"])
            
            source_data = plan.get("source_data", "")
            source_type = plan["source_type"]
            
            # Extract knowledge based on source type
            if source_type == "text":
                extracted_entries = await self._extract_from_text(source_data, plan)
            elif source_type == "url":
                extracted_entries = await self._extract_from_url(source_data, plan)
            elif source_type == "structured":
                extracted_entries = await self._extract_from_structured(source_data, plan)
            else:
                raise BaseLayerError(f"Unsupported source type: {source_type}")
            
            # Store extracted entries
            stored_entries = []
            duplicates_found = []
            
            for entry in extracted_entries:
                # Check for duplicates
                duplicate = await self._check_for_duplicate(entry)
                if duplicate:
                    duplicates_found.append(entry["key"])
                    continue
                
                # Store entry
                try:
                    stored_entry = await self.knowledge_manager.store(
                        key=entry["key"],
                        value=entry["value"],
                        entry_type=entry["entry_type"],
                        source_engine=SourceEngine(plan["metadata"]["engine"]),
                        source_agent=self.agent_name,
                        tags=entry["tags"],
                        confidence=entry["confidence"],
                        generate_embedding=True
                    )
                    stored_entries.append(stored_entry.to_dict())
                    
                except Exception as e:
                    logger.error("Failed to store extracted entry", 
                               key=entry["key"], 
                               error=str(e))
            
            results = {
                "source_type": plan["source_type"],
                "extracted_entries": len(extracted_entries),
                "stored_entries": len(stored_entries),
                "duplicates_found": len(duplicates_found),
                "stored_entry_keys": [entry["key"] for entry in stored_entries],
                "duplicates": duplicates_found,
                "processing_time": plan.get("processing_time", 0),
                "metadata": plan["metadata"]
            }
            
            logger.info("Knowledge extraction executed", 
                       source_type=plan["source_type"],
                       stored=len(stored_entries),
                       duplicates=len(duplicates_found))
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute knowledge extraction", error=str(e))
            raise BaseLayerError(f"Failed to execute knowledge extraction: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extraction results.
        
        Args:
            results: Extraction results
            
        Returns:
            Validation results
        """
        try:
            logger.info("Validating knowledge extraction results")
            
            validation_errors = []
            
            # Check for required fields
            if not results.get("stored_entries"):
                validation_errors.append("No entries were stored")
            
            if not results.get("stored_entry_keys"):
                validation_errors.append("No entry keys recorded")
            
            # Check extraction quality
            extracted_count = results.get("extracted_entries", 0)
            stored_count = results.get("stored_entries", 0)
            
            if stored_count == 0 and extracted_count > 0:
                validation_errors.append("All extracted entries failed to store")
            
            # Check duplicate rate
            duplicate_rate = results.get("duplicates_found", 0) / max(extracted_count, 1)
            if duplicate_rate > 0.5:
                validation_errors.append(f"High duplicate rate: {duplicate_rate:.2%}")
            
            # Check for minimum success rate
            success_rate = stored_count / max(extracted_count, 1)
            if success_rate < 0.5:
                validation_errors.append(f"Low success rate: {success_rate:.2%}")
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "extraction_summary": {
                    "source_type": results.get("source_type"),
                    "extracted_entries": extracted_count,
                    "stored_entries": stored_count,
                    "duplicates_found": results.get("duplicates_found", 0),
                    "success_rate": success_rate,
                    "duplicate_rate": duplicate_rate
                }
            }
            
            logger.info("Knowledge extraction validation completed", 
                       is_valid=validation_result["is_valid"],
                       errors_count=len(validation_errors))
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate extraction results", error=str(e))
            raise BaseLayerError(f"Failed to validate extraction results: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate extraction execution report.
        
        Args:
            results: Extraction results
            validation: Validation results
            
        Returns:
            Execution report
        """
        try:
            logger.info("Generating knowledge extraction report")
            
            report = {
                "extraction_id": str(uuid.uuid4()),
                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "quality_metrics": self._calculate_quality_metrics(results, validation),
                "recommendations": self._get_recommendations(results, validation),
                "metadata": {
                    "source_type": results.get("source_type"),
                    "processing_time": results.get("processing_time", 0),
                    "duplicate_rate": results.get("duplicates_found", 0) / max(results.get("extracted_entries", 1), 1)
                }
            }
            
            logger.info("Knowledge extraction report generated", 
                       extraction_id=report["extraction_id"],
                       stored_entries=results.get("stored_entries", 0))
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate extraction report", error=str(e))
            raise BaseLayerError(f"Failed to generate extraction report: {e}")
    
    async def _extract_from_text(self, text: str, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge from raw text."""
        entries = []
        
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        for sentence in sentences:
            # Extract facts
            for pattern in self.fact_patterns:
                matches = re.findall(pattern, sentence)
                for match in matches:
                    if len(match) >= 2:
                        entry = {
                            "key": self._generate_key(match[0], "fact"),
                            "value": f"{match[0]} is {match[1]}",
                            "entry_type": KnowledgeEntryType.FACT,
                            "confidence": 0.8,
                            "tags": self._extract_tags(sentence),
                            "source": plan["metadata"]["source"]
                        }
                        entries.append(entry)
            
            # Extract decisions
            for pattern in self.decision_patterns:
                matches = re.findall(pattern, sentence)
                for match in matches:
                    if len(match) >= 2:
                        entry = {
                            "key": self._generate_key(match[0], "decision"),
                            "value": f"{match[0]} decided to {match[1]}",
                            "entry_type": KnowledgeEntryType.DECISION,
                            "confidence": 0.9,
                            "tags": self._extract_tags(sentence),
                            "source": plan["metadata"]["source"]
                        }
                        entries.append(entry)
            
            # Extract patterns
            for pattern in self.pattern_patterns:
                matches = re.findall(pattern, sentence)
                for match in matches:
                    if len(match) >= 2:
                        entry = {
                            "key": self._generate_key(match[0], "pattern"),
                            "value": f"{match[0]} leads to {match[1]}",
                            "entry_type": KnowledgeEntryType.PATTERN,
                            "confidence": 0.7,
                            "tags": self._extract_tags(sentence),
                            "source": plan["metadata"]["source"]
                        }
                        entries.append(entry)
        
        return entries
    
    async def _extract_from_url(self, url: str, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge from URL content."""
        # This would implement web scraping
        # For now, return empty list as placeholder
        logger.warning("URL extraction not implemented", url=url)
        return []
    
    async def _extract_from_structured(self, data: str, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge from structured data (JSON, etc.)."""
        entries = []
        
        try:
            import json
            structured_data = json.loads(data)
            
            # Extract key-value pairs
            if isinstance(structured_data, dict):
                for key, value in structured_data.items():
                    if isinstance(value, (str, int, float, bool)):
                        entry = {
                            "key": f"structured:{key}",
                            "value": f"{key}: {value}",
                            "entry_type": KnowledgeEntryType.FACT,
                            "confidence": 0.9,
                            "tags": ["structured", "json"],
                            "source": plan["metadata"]["source"]
                        }
                        entries.append(entry)
            
        except json.JSONDecodeError:
            logger.error("Failed to parse structured data")
        
        return entries
    
    def _determine_extraction_strategy(self, source_type: str, source_data: str) -> str:
        """Determine the best extraction strategy."""
        if source_type == "text":
            if len(source_data) > 1000:
                return "comprehensive_text_analysis"
            else:
                return "simple_pattern_matching"
        elif source_type == "url":
            return "web_content_extraction"
        elif source_type == "structured":
            return "structured_data_parsing"
        else:
            return "generic_extraction"
    
    def _estimate_entry_count(self, source_data: str) -> int:
        """Estimate number of entries that will be extracted."""
        # Rough estimation based on text length
        sentences = len(re.split(r'[.!?]+', source_data))
        return max(1, sentences // 3)  # Assume 1 entry per 3 sentences
    
    def _get_processing_steps(self, source_type: str) -> List[str]:
        """Get processing steps for source type."""
        steps = [
            "preprocess_source_data",
            "extract_knowledge_patterns",
            "categorize_entries",
            "assign_confidence_scores",
            "generate_tags",
            "validate_entries"
        ]
        
        if source_type == "url":
            steps.insert(0, "fetch_web_content")
        elif source_type == "structured":
            steps.insert(0, "parse_structured_data")
        
        return steps
    
    def _get_quality_checks(self) -> List[str]:
        """Get quality check criteria."""
        return [
            "minimum_confidence_threshold",
            "duplicate_detection",
            "content_length_validation",
            "tag_relevance_check",
            "key_uniqueness"
        ]
    
    def _generate_key(self, content: str, entry_type: str) -> str:
        """Generate a unique key for the entry."""
        # Create a hash of the content
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Create a readable key
        clean_content = re.sub(r'[^\w\s-]', '', content)[:50]
        key = f"{entry_type}:{clean_content}:{content_hash}"
        
        return key
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extract relevant tags from text."""
        tags = []
        
        # Look for common keywords
        keywords = [
            "important", "critical", "urgent", "note", "reminder",
            "decision", "action", "task", "goal", "objective",
            "process", "procedure", "method", "approach",
            "result", "outcome", "conclusion", "summary"
        ]
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword in text_lower:
                tags.append(keyword)
        
        return tags
    
    async def _check_for_duplicate(self, entry: Dict[str, Any]) -> bool:
        """Check if entry already exists."""
        try:
            existing = await self.knowledge_manager.retrieve_by_key(entry["key"])
            return existing is not None
        except Exception:
            return False
    
    def _calculate_quality_metrics(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quality metrics for the extraction."""
        extracted = results.get("extracted_entries", 0)
        stored = results.get("stored_entries", 0)
        duplicates = results.get("duplicates_found", 0)
        
        return {
            "extraction_efficiency": stored / max(extracted, 1),
            "duplicate_rate": duplicates / max(extracted, 1),
            "storage_success_rate": stored / max(extracted, 1),
            "quality_score": validation.get("extraction_summary", {}).get("success_rate", 0.0)
        }
    
    def _get_recommendations(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get recommendations for improvement."""
        recommendations = []
        
        if validation.get("extraction_summary", {}).get("success_rate", 0.0) < 0.8:
            recommendations.append("Improve extraction patterns for better success rate")
        
        if results.get("duplicates_found", 0) > results.get("extracted_entries", 0) * 0.3:
            recommendations.append("Review duplicate detection and key generation")
        
        if results.get("stored_entries", 0) == 0:
            recommendations.append("Check source data format and extraction logic")
        
        return recommendations
