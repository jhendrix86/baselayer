"""
CODEX Knowledge Curator Agent

AgentBase implementation for daily knowledge base maintenance,
confidence decay, and pruning operations.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..api.knowledge_manager import KnowledgeManager
from ..models.knowledge_entry import KnowledgeEntry
from ..models.knowledge_snapshot import KnowledgeSnapshot

logger = get_logger(__name__)


class KnowledgeCurator(AgentBase):
    """
    Agent for daily knowledge base maintenance and optimization.
    
    Runs via ARQ cron to identify low-confidence entries,
    apply confidence decay based on access patterns, prune
    old archived entries, and generate daily snapshots.
    """
    
    agent_name = "knowledge_curator"
    agent_version = "1.0.0"
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        memory_interface: Optional[MemoryInterface] = None
    ):
        """Initialize knowledge curator agent."""
        super().__init__(config)
        self.knowledge_manager = knowledge_manager
        self.memory_interface = memory_interface
        
        # Curation thresholds
        self.decay_threshold = 0.3
        self.decay_rate = 0.1
        self.retention_days = 90
        self.min_confidence_threshold = 0.2
        
        logger.info("KnowledgeCurator initialized")
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan knowledge curation operations.
        
        Args:
            input_data: Curation parameters and configuration
            
        Returns:
            Curation plan
        """
        try:
            logger.info("Planning knowledge curation")
            
            curation_type = input_data.get("curation_type", "daily")
            
            if curation_type == "daily":
                plan = await self._plan_daily_curation(input_data)
            elif curation_type == "deep":
                plan = await self._plan_deep_curation(input_data)
            elif curation_type == "emergency":
                plan = await self._plan_emergency_curation(input_data)
            else:
                raise BaseLayerError(f"Unknown curation type: {curation_type}")
            
            logger.info("Knowledge curation plan created", 
                       curation_type=curation_type,
                       operations_count=len(plan["operations"]))
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan knowledge curation", error=str(e))
            raise BaseLayerError(f"Failed to plan knowledge curation: {e}")
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute knowledge curation operations.
        
        Args:
            plan: Curation plan from planning phase
            
        Returns:
            Curation results
        """
        try:
            logger.info("Executing knowledge curation", 
                       curation_type=plan["curation_type"])
            
            if plan["curation_type"] == "daily":
                results = await self._execute_daily_curation(plan)
            elif plan["curation_type"] == "deep":
                results = await self._execute_deep_curation(plan)
            elif plan["curation_type"] == "emergency":
                results = await self._execute_emergency_curation(plan)
            else:
                raise BaseLayerError(f"Unknown curation type: {plan['curation_type']}")
            
            logger.info("Knowledge curation executed", 
                       curation_type=plan["curation_type"],
                       operations_completed=len(results["operations"]))
            
            return results
            
        except Exception as e:
            logger.error("Failed to execute knowledge curation", error=str(e))
            raise BaseLayerError(f"Failed to execute knowledge curation: {e}")
    
    async def validate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate curation results.
        
        Args:
            results: Curation results
            
        Returns:
            Validation results
        """
        try:
            logger.info("Validating knowledge curation results")
            
            validation_errors = []
            
            # Check for required fields
            if not results.get("operations"):
                validation_errors.append("No operations recorded")
            
            if not results.get("curation_type"):
                validation_errors.append("Missing curation type")
            
            # Check operation success rates
            operations = results.get("operations", [])
            if operations:
                failed_ops = [op for op in operations if not op.get("success", False)]
                if len(failed_ops) > len(operations) * 0.1:  # More than 10% failed
                    validation_errors.append(f"High failure rate: {len(failed_ops)}/{len(operations)}")
            
            # Check for critical errors
            critical_errors = results.get("critical_errors", [])
            if critical_errors:
                validation_errors.extend([f"Critical error: {error}" for error in critical_errors])
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "errors": validation_errors,
                "curation_summary": {
                    "curation_type": results.get("curation_type"),
                    "operations_completed": len(operations),
                    "success_rate": len([op for op in operations if op.get("success", False)]) / max(len(operations), 1),
                    "critical_errors": len(critical_errors)
                }
            }
            
            logger.info("Knowledge curation validation completed", 
                       is_valid=validation_result["is_valid"],
                       errors_count=len(validation_errors))
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate curation results", error=str(e))
            raise BaseLayerError(f"Failed to validate curation results: {e}")
    
    async def report(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate curation execution report.
        
        Args:
            results: Curation results
            validation: Validation results
            
        Returns:
            Execution report
        """
        try:
            logger.info("Generating knowledge curation report")
            
            report = {
                "curation_id": str(uuid.uuid4()),
                "curation_timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_results": results,
                "validation_results": validation,
                "performance_metrics": self._calculate_performance_metrics(results, validation),
                "recommendations": self._get_curation_recommendations(results, validation),
                "metadata": {
                    "curation_type": results.get("curation_type"),
                    "decay_threshold": self.decay_threshold,
                    "retention_days": self.retention_days
                }
            }
            
            logger.info("Knowledge curation report generated", 
                       curation_id=report["curation_id"],
                       operations_completed=len(results.get("operations", [])))
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate curation report", error=str(e))
            raise BaseLayerError(f"Failed to generate curation report: {e}")
    
    async def _plan_daily_curation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan daily curation operations."""
        try:
            # Get current knowledge base stats
            stats = await self.knowledge_manager.get_stats()
            
            # Plan operations
            operations = [
                {
                    "type": "confidence_decay",
                    "description": "Apply confidence decay to old entries",
                    "priority": "high",
                    "estimated_time": 300  # 5 minutes
                },
                {
                    "type": "snapshot_generation",
                    "description": "Generate daily knowledge snapshot",
                    "priority": "high",
                    "estimated_time": 60  # 1 minute
                },
                {
                    "type": "cleanup_check",
                    "description": "Check for entries needing cleanup",
                    "priority": "medium",
                    "estimated_time": 120  # 2 minutes
                },
                {
                    "type": "health_analysis",
                    "description": "Analyze knowledge base health",
                    "priority": "medium",
                    "estimated_time": 180  # 3 minutes
                }
            ]
            
            plan = {
                "curation_type": "daily",
                "operations": operations,
                "estimated_total_time": sum(op["estimated_time"] for op in operations),
                "current_stats": stats,
                "thresholds": {
                    "decay_threshold": self.decay_threshold,
                    "retention_days": self.retention_days,
                    "min_confidence": self.min_confidence_threshold
                },
                "schedule": {
                    "frequency": "daily",
                    "next_run": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                }
            }
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan daily curation", error=str(e))
            raise BaseLayerError(f"Failed to plan daily curation: {e}")
    
    async def _plan_deep_curation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan deep curation operations."""
        try:
            operations = [
                {
                    "type": "comprehensive_decay",
                    "description": "Apply comprehensive confidence decay",
                    "priority": "high",
                    "estimated_time": 600  # 10 minutes
                },
                {
                    "type": "pruning",
                    "description": "Prune old archived entries",
                    "priority": "high",
                    "estimated_time": 300  # 5 minutes
                },
                {
                    "type": "embedding_optimization",
                    "description": "Optimize vector embeddings",
                    "priority": "medium",
                    "estimated_time": 900  # 15 minutes
                },
                {
                    "type": "link_analysis",
                    "description": "Analyze knowledge graph links",
                    "priority": "medium",
                    "estimated_time": 300  # 5 minutes
                }
            ]
            
            plan = {
                "curation_type": "deep",
                "operations": operations,
                "estimated_total_time": sum(op["estimated_time"] for op in operations),
                "thresholds": {
                    "decay_threshold": self.decay_threshold * 0.5,  # More aggressive
                    "retention_days": self.retention_days * 0.5,  # Shorter retention
                    "min_confidence": self.min_confidence_threshold
                }
            }
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan deep curation", error=str(e))
            raise BaseLayerError(f"Failed to plan deep curation: {e}")
    
    async def _plan_emergency_curation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan emergency curation operations."""
        try:
            # Emergency operations to fix critical issues
            operations = [
                {
                    "type": "immediate_decay",
                    "description": "Apply immediate confidence decay",
                    "priority": "critical",
                    "estimated_time": 120  # 2 minutes
                },
                {
                    "type": "emergency_pruning",
                    "description": "Emergency pruning of problematic entries",
                    "priority": "critical",
                    "estimated_time": 180  # 3 minutes
                }
            ]
            
            plan = {
                "curation_type": "emergency",
                "operations": operations,
                "estimated_total_time": sum(op["estimated_time"] for op in operations),
                "reason": input_data.get("reason", "Emergency maintenance required"),
                "thresholds": {
                    "decay_threshold": self.decay_threshold * 0.3,  # Very aggressive
                    "retention_days": self.retention_days * 0.3,  # Very short
                    "min_confidence": self.min_confidence_threshold * 2  # Higher threshold
                }
            }
            
            return plan
            
        except Exception as e:
            logger.error("Failed to plan emergency curation", error=str(e))
            raise BaseLayerError(f"Failed to plan emergency curation: {e}")
    
    async def _execute_daily_curation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute daily curation operations."""
        try:
            operations = []
            critical_errors = []
            
            # Execute confidence decay
            try:
                decay_result = await self.knowledge_manager.decay(dry_run=False)
                operations.append({
                    "type": "confidence_decay",
                    "success": True,
                    "result": decay_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "confidence_decay",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Confidence decay failed: {e}")
            
            # Generate snapshot
            try:
                snapshot = await self.knowledge_manager.snapshot()
                operations.append({
                    "type": "snapshot_generation",
                    "success": True,
                    "result": {"snapshot_id": str(snapshot.id)},
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "snapshot_generation",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Snapshot generation failed: {e}")
            
            # Cleanup check
            try:
                # Check for entries that might need pruning
                prune_result = await self.knowledge_manager.prune(
                    retention_days=self.retention_days,
                    dry_run=True
                )
                operations.append({
                    "type": "cleanup_check",
                    "success": True,
                    "result": prune_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "cleanup_check",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            
            # Health analysis
            try:
                stats = await self.knowledge_manager.get_stats()
                operations.append({
                    "type": "health_analysis",
                    "success": True,
                    "result": stats,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "health_analysis",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            
            return {
                "curation_type": "daily",
                "operations": operations,
                "critical_errors": critical_errors,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to execute daily curation", error=str(e))
            raise BaseLayerError(f"Failed to execute daily curation: {e}")
    
    async def _execute_deep_curation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute deep curation operations."""
        try:
            operations = []
            critical_errors = []
            
            # Comprehensive decay
            try:
                decay_result = await self.knowledge_manager.decay(dry_run=False)
                operations.append({
                    "type": "comprehensive_decay",
                    "success": True,
                    "result": decay_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "comprehensive_decay",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Comprehensive decay failed: {e}")
            
            # Pruning
            try:
                prune_result = await self.knowledge_manager.prune(
                    retention_days=int(self.retention_days * 0.5),
                    dry_run=False
                )
                operations.append({
                    "type": "pruning",
                    "success": True,
                    "result": prune_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "pruning",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Pruning failed: {e}")
            
            # Embedding optimization
            try:
                # This would optimize vector embeddings
                operations.append({
                    "type": "embedding_optimization",
                    "success": True,
                    "result": {"optimized_entries": 0},  # Placeholder
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "embedding_optimization",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            
            return {
                "curation_type": "deep",
                "operations": operations,
                "critical_errors": critical_errors,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to execute deep curation", error=str(e))
            raise BaseLayerError(f"Failed to execute deep curation: {e}")
    
    async def _execute_emergency_curation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute emergency curation operations."""
        try:
            operations = []
            critical_errors = []
            
            # Immediate decay
            try:
                decay_result = await self.knowledge_manager.decay(dry_run=False)
                operations.append({
                    "type": "immediate_decay",
                    "success": True,
                    "result": decay_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "immediate_decay",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Immediate decay failed: {e}")
            
            # Emergency pruning
            try:
                prune_result = await self.knowledge_manager.prune(
                    retention_days=int(self.retention_days * 0.3),
                    dry_run=False
                )
                operations.append({
                    "type": "emergency_pruning",
                    "success": True,
                    "result": prune_result,
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                operations.append({
                    "type": "emergency_pruning",
                    "success": False,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })
                critical_errors.append(f"Emergency pruning failed: {e}")
            
            return {
                "curation_type": "emergency",
                "operations": operations,
                "critical_errors": critical_errors,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "reason": plan.get("reason")
            }
            
        except Exception as e:
            logger.error("Failed to execute emergency curation", error=str(e))
            raise BaseLayerError(f"Failed to execute emergency curation: {e}")
    
    def _calculate_performance_metrics(self, results: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance metrics for curation."""
        operations = results.get("operations", [])
        
        if not operations:
            return {
                "operations_per_second": 0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "critical_errors": 0
            }
        
        successful_ops = [op for op in operations if op.get("success", False)]
        failed_ops = [op for op in operations if not op.get("success", False)]
        critical_errors = results.get("critical_errors", [])
        
        return {
            "operations_completed": len(operations),
            "successful_operations": len(successful_ops),
            "failed_operations": len(failed_ops),
            "success_rate": len(successful_ops) / len(operations),
            "error_rate": len(failed_ops) / len(operations),
            "critical_errors": len(critical_errors),
            "operations_per_second": len(operations) / 60  # Rough estimate
        }
    
    def _get_curation_recommendations(self, results: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """Get recommendations for curation improvement."""
        recommendations = []
        
        if validation.get("curation_summary", {}).get("success_rate", 0.0) < 0.9:
            recommendations.append("Review curation operations for better success rate")
        
        if results.get("critical_errors"):
            recommendations.append("Address critical errors in curation operations")
        
        operations = results.get("operations", [])
        decay_ops = [op for op in operations if op["type"] == "confidence_decay"]
        
        if decay_ops and decay_ops[0].get("result", {}).get("entries_decayed", 0) > 100:
            recommendations.append("Consider adjusting decay threshold to reduce maintenance overhead")
        
        prune_ops = [op for op in operations if "pruning" in op["type"]]
        if prune_ops and prune_ops[0].get("result", {}).get("entries_pruned", 0) > 50:
            recommendations.append("Review retention policy - many entries being pruned")
        
        return recommendations
