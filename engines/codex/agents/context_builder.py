"""
CODEX Context Builder Agent

AgentBase implementation for building LLM context from
relevant knowledge entries within token budget constraints.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..api.knowledge_manager import KnowledgeManager
from ..models.knowledge_entry import KnowledgeEntry

logger = get_logger(__name__)


class ContextBuilder(AgentBase):
    """
    Agent for building LLM context from relevant knowledge entries.
    
    Retrieves semantically relevant knowledge, ranks by relevance
    and confidence, and packs into context within token budget
    for LLM injection.
    """
    
    agent_name = "context_builder"
    agent_version = "1.0.0"
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        memory_interface: Optional[MemoryInterface] = None
    ):
        """Initialize context builder agent."""
        super().__init__(config)
        self.knowledge_manager = knowledge_manager
        self.memory_interface = memory_interface
        
        # Context building parameters
        self.default_max_tokens = 4000
        self.default_min_confidence = 0.5
        self.default_limit = 50
        
        # Token estimation (rough approximation: 1 token ≈ 4 characters)
        self.chars_per_token = 4
        
        logger.info("ContextBuilder initialized")
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan context building strategy.
        
        Args:
            input_data: Contains query and token budget
            
        Returns:
            Context building plan
        """
        try:
            logger.info("Planning context building", 
                       query_length=len(input_data.get("query", "")))
            
            query = input_data.get("query", "")
            max_tokens = input_data.get("max_tokens", self.default_max_tokens)
            min_confidence = input_data.get("min_confidence", self.default_min_confidence)
            tags = input_data.get("tags", [])
            
            # Analyze query and create plan
            plan = {
                "query": query,
                "max_tokens": max_tokens,
                "min_confidence": min_confidence,
                "tags": tags,
                "search_strategy": self._determine_search_strategy(query),
                "retrieval_limit": self._calculate_retrieval_limit(max_tokens),
                "ranking_method": "relevance_confidence_weighted",
                "formatting_options": self._get_formatting_options(),
                "quality_checks": self._get_quality_checks(),
                "estimated_entries": max_tokens // 100  # Rough estimate
            }
            
            logger.info("Context building plan created", 
                       max_tokens=max_tokens,
                       retrieval_limit=plan["retrieval_limit"])
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan context building", error=str(e))
            raise BaseLayerError(f"Failed to plan context building: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute context building.
        
        Args:
            plan: Context building plan
            
        Returns:
            Built context
        """
        try:
            logger.info("Executing context building", 
                       max_tokens=plan["max_tokens"])
            
            # Retrieve relevant knowledge
            search_results = await self._retrieve_relevant_knowledge(plan)
            
            # Rank and select entries
            selected_entries = await self._rank_and_select_entries(search_results, plan)
            
            # Pack into context
            context = await self._pack_context(selected_entries, plan)
            
            # Validate context
            validation_result = await self._validate_context(context, plan)
            
            results = {
                "query": plan["query"],
                "max_tokens": plan["max_tokens"],
                "retrieved_entries": len(search_results),
                "selected_entries": len(selected_entries),
                "context": context,
                "actual_tokens": validation_result["actual_tokens"],
                "token_efficiency": validation_result["token_efficiency"],
                "quality_score": validation_result["quality_score"],
                "entries": [
                    {
                        "key": entry["key"],
                        "similarity": entry["similarity"],
                        "confidence": entry["confidence"],
                        "tokens": len(entry["formatted_text"]) // self.chars_per_token
                    }
                    for entry in selected_entries
                ]
            }
            
            logger.info("Context building executed", 
                       retrieved=len(search_results),
                       selected=len(selected_entries),
                       actual_tokens=results["actual_tokens"])
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute context building", error=str(e))
            raise BaseLayerError(f"Failed to execute context building: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate built context.
        
        Args:
            results: Context building results
            
        Returns:
            Validation results
        """
        try:
            logger.info("Validating built context")
            
            validation_errors = []
            
            # Check for required fields
            if not results.get("context"):
                validation_errors.append("No context generated")
            
            if not results.get("entries"):
                validation_errors.append("No entries included in context")
            
            # Check token efficiency
            token_efficiency = results.get("token_efficiency", 0.0)
            if token_efficiency < 0.7:
                validation_errors.append(f"Low token efficiency: {token_efficiency:.2%}")
            
            # Check quality score
            quality_score = results.get("quality_score", 0.0)
            if quality_score < 0.6:
                validation_errors.append(f"Low quality score: {quality_score:.2f}")
            
            # Check if context is too short
            actual_tokens = results.get("actual_tokens", 0)
            max_tokens = results.get("max_tokens", 0)
            
            if actual_tokens < max_tokens * 0.3:
                validation_errors.append(f"Context too short: {actual_tokens}/{max_tokens} tokens")
            
            # Check if context is too long
            if actual_tokens > max_tokens:
                validation_errors.append(f"Context exceeds token limit: {actual_tokens}/{max_tokens}")
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "context_summary": {
                    "query": results.get("query"),
                    "max_tokens": max_tokens,
                    "actual_tokens": actual_tokens,
                    "token_efficiency": token_efficiency,
                    "quality_score": quality_score,
                    "entries_included": len(results.get("entries", []))
                }
            }
            
            logger.info("Context validation completed", 
                       is_valid=validation_result["is_valid"],
                       errors_count=len(validation_errors))
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate context", error=str(e))
            raise BaseLayerError(f"Failed to validate context: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate context building report.
        
        Args:
            results: Context building results
            validation: Validation results
            
        Returns:
            Execution report
        """
        try:
            logger.info("Generating context building report")
            
            report = {
                "context_id": str(uuid.uuid4()),
                "context_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "performance_metrics": self._calculate_performance_metrics(results, validation),
                "recommendations": self._get_context_recommendations(results, validation),
                "metadata": {
                    "query": results.get("query"),
                    "max_tokens": results.get("max_tokens"),
                    "search_strategy": results.get("search_strategy"),
                    "ranking_method": results.get("ranking_method")
                }
            }
            
            logger.info("Context building report generated", 
                       context_id=report["context_id"],
                       actual_tokens=results.get("actual_tokens", 0))
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate context report", error=str(e))
            raise BaseLayerError(f"Failed to generate context report: {e}")
    
    async def _retrieve_relevant_knowledge(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge entries."""
        try:
            # Use semantic search
            search_results = await self.knowledge_manager.search_semantic(
                query=plan["query"],
                limit=plan["retrieval_limit"],
                min_confidence=plan["min_confidence"],
                tags=plan["tags"],
                exclude_archived=True,
                threshold=0.3  # Lower threshold for more candidates
            )
            
            logger.debug("Knowledge retrieved", 
                       query_length=len(plan["query"]),
                       results_found=len(search_results))
            
            return search_results
            
        except Exception as e:
            logger.error("Failed to retrieve relevant knowledge", error=str(e))
            return []
    
    async def _rank_and_select_entries(
        self, 
        search_results: List[Dict[str, Any]], 
        plan: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank and select entries for context."""
        try:
            # Calculate combined score for each entry
            for result in search_results:
                # Weighted combination of similarity and confidence
                similarity_score = result["similarity"]
                confidence_score = result["confidence"]
                
                # Access frequency boost
                access_boost = min(0.1, result["access_count"] / 1000)
                
                # Recency boost
                recency_boost = 0.0
                if result.get("last_accessed_at"):
                    days_since_access = (datetime.now(timezone.utc) - result["last_accessed_at"]).days
                    if days_since_access < 7:
                        recency_boost = 0.05
                
                # Combined score
                combined_score = (
                    similarity_score * 0.6 +
                    confidence_score * 0.3 +
                    access_boost +
                    recency_boost
                )
                
                result["combined_score"] = combined_score
                result["formatted_text"] = self._format_entry_for_context(result)
            
            # Sort by combined score
            ranked_results = sorted(search_results, key=lambda x: x["combined_score"], reverse=True)
            
            # Select entries within token budget
            selected_entries = []
            current_tokens = 0
            max_tokens = plan["max_tokens"]
            
            for result in ranked_results:
                entry_tokens = len(result["formatted_text"]) // self.chars_per_token
                
                if current_tokens + entry_tokens <= max_tokens:
                    result["estimated_tokens"] = entry_tokens
                    selected_entries.append(result)
                    current_tokens += entry_tokens
                else:
                    break
            
            logger.debug("Entries ranked and selected", 
                       retrieved=len(search_results),
                       selected=len(selected_entries),
                       tokens_used=current_tokens)
            
            return selected_entries
            
        except Exception as e:
            logger.error("Failed to rank and select entries", error=str(e))
            return []
    
    async def _pack_context(self, selected_entries: List[Dict[str, Any]], plan: Dict[str, Any]) -> str:
        """Pack selected entries into context string."""
        try:
            if not selected_entries:
                return "No relevant knowledge found for the given query."
            
            # Build context header
            context_parts = [
                f"Knowledge Context (retrieved {len(selected_entries)} entries, "
                f"~{sum(len(e['formatted_text']) for e in selected_entries) // self.chars_per_token} tokens):\n"
            ]
            
            # Add entries
            for i, entry in enumerate(selected_entries, 1):
                entry_text = (
                    f"{i}. Key: {entry['key']}\n"
                    f"   Value: {entry['value']}\n"
                    f"   (similarity: {entry['similarity']:.3f}, "
                    f"confidence: {entry['confidence']:.3f}, "
                    f"source: {entry['source_engine']})\n"
                )
                context_parts.append(entry_text)
            
            context = "".join(context_parts)
            
            logger.debug("Context packed", 
                       entries=len(selected_entries),
                       context_length=len(context))
            
            return context
            
        except Exception as e:
            logger.error("Failed to pack context", error=str(e))
            return "Error building knowledge context."
    
    async def _validate_context(self, context: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate built context."""
        try:
            # Estimate actual tokens
            actual_tokens = len(context) // self.chars_per_token
            max_tokens = plan["max_tokens"]
            
            # Calculate token efficiency
            token_efficiency = actual_tokens / max_tokens if max_tokens > 0 else 0.0
            
            # Calculate quality score based on content
            quality_score = self._calculate_quality_score(context)
            
            return {
                "actual_tokens": actual_tokens,
                "token_efficiency": token_efficiency,
                "quality_score": quality_score,
                "is_within_limit": actual_tokens <= max_tokens,
                "is_reasonable_length": actual_tokens >= max_tokens * 0.3
            }
            
        except Exception as e:
            logger.error("Failed to validate context", error=str(e))
            return {
                "actual_tokens": 0,
                "token_efficiency": 0.0,
                "quality_score": 0.0,
                "is_within_limit": False,
                "is_reasonable_length": False
            }
    
    def _determine_search_strategy(self, query: str) -> str:
        """Determine best search strategy for query."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["how to", "what is", "why", "when"]):
            return "semantic_primary"
        elif any(word in query_lower for word in ["pattern", "trend", "relationship"]):
            return "semantic_with_graph"
        elif any(word in query_lower for word in ["recent", "latest", "new"]):
            return "semantic_with_recency_boost"
        else:
            return "semantic_standard"
    
    def _calculate_retrieval_limit(self, max_tokens: int) -> int:
        """Calculate optimal retrieval limit based on token budget."""
        # Retrieve more candidates than needed to allow for selection
        # Rough estimate: average entry ~100 tokens
        estimated_entries_per_token = 100
        
        # Retrieve 3x more than needed for good selection
        needed_entries = max_tokens // estimated_entries_per_token
        retrieval_limit = min(needed_entries * 3, self.default_limit)
        
        return max(retrieval_limit, 10)  # Minimum 10 entries
    
    def _get_formatting_options(self) -> Dict[str, Any]:
        """Get formatting options for context."""
        return {
            "include_metadata": True,
            "include_similarity": True,
            "include_confidence": True,
            "include_source": True,
            "format_style": "numbered_list",
            "separator": "\n"
        }
    
    def _get_quality_checks(self) -> List[str]:
        """Get quality check criteria."""
        return [
            "token_limit_check",
            "content_coherence",
            "relevance_validation",
            "format_consistency"
        ]
    
    def _format_entry_for_context(self, entry: Dict[str, Any]) -> str:
        """Format entry for context display."""
        # Truncate very long values
        value = entry["value"]
        if len(value) > 500:
            value = value[:497] + "..."
        
        return value
    
    def _calculate_quality_score(self, context: str) -> float:
        """Calculate quality score for context."""
        score = 0.0
        
        # Length appropriateness (0.3)
        context_length = len(context)
        if 100 <= context_length <= 2000:
            score += 0.3
        elif context_length < 100:
            score += context_length / 100 * 0.3
        else:
            score += max(0, (2000 - context_length) / 1000 * 0.3)
        
        # Structure quality (0.3)
        if "Knowledge Context" in context and "Key:" in context and "Value:" in context:
            score += 0.3
        elif "Key:" in context and "Value:" in context:
            score += 0.2
        elif context.count("\n") >= 3:
            score += 0.1
        
        # Content richness (0.4)
        unique_lines = len(set(line.strip() for line in context.split("\n") if line.strip()))
        total_lines = len([line for line in context.split("\n") if line.strip()])
        
        if total_lines > 0:
            score += (unique_lines / total_lines) * 0.4
        
        return min(1.0, score)
    
    def _calculate_performance_metrics(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance metrics for context building."""
        retrieved = results.get("retrieved_entries", 0)
        selected = results.get("selected_entries", 0)
        actual_tokens = results.get("actual_tokens", 0)
        max_tokens = results.get("max_tokens", 0)
        
        return {
            "retrieval_count": retrieved,
            "selection_rate": selected / max(retrieved, 1),
            "token_utilization": actual_tokens / max(max_tokens, 1),
            "selection_efficiency": selected / max(retrieved, 1),
            "quality_score": validation.get("context_summary", {}).get("quality_score", 0.0),
            "token_efficiency": validation.get("context_summary", {}).get("token_efficiency", 0.0)
        }
    
    def _get_context_recommendations(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get recommendations for context building improvement."""
        recommendations = []
        
        if validation.get("context_summary", {}).get("token_efficiency", 0.0) < 0.7:
            recommendations.append("Consider increasing retrieval limit for better token utilization")
        
        if validation.get("context_summary", {}).get("quality_score", 0.0) < 0.6:
            recommendations.append("Review entry formatting and selection criteria")
        
        if results.get("selected_entries", 0) < results.get("retrieved_entries", 0) * 0.3:
            recommendations.append("Many retrieved entries not selected - consider adjusting ranking weights")
        
        if validation.get("context_summary", {}).get("actual_tokens", 0) < results.get("max_tokens", 0) * 0.3:
            recommendations.append("Context is much shorter than token limit - could include more relevant entries")
        
        return recommendations
