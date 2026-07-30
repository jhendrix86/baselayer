"""
CODX Knowledge Manager

High-level knowledge management interface for CODX engine
with simplified API and advanced features.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
from dataclasses import dataclass
from enum import Enum

from .knowledge_interface import KnowledgeInterface, InterfaceMode, OperationType, OperationResult
from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class KnowledgeAction(str, Enum):
    """Knowledge management actions."""
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"
    SEARCH = "search"
    EXPLORE = "explore"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    VALIDATE = "validate"
    EXPORT = "export"
    IMPORT = "import"


@dataclass
class KnowledgeRequest:
    """Knowledge request data class."""
    action: KnowledgeAction
    target: str  # "node", "edge", "graph", "all"
    parameters: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class KnowledgeResponse:
    """Knowledge response data class."""
    success: bool
    action: KnowledgeAction
    target: str
    data: Any
    message: str
    execution_time_ms: int
    metadata: Dict[str, Any]
    error: Optional[str] = None


class KnowledgeManager:
    """
    High-level knowledge manager for CODX engine.
    
    Provides simplified API for common knowledge
    management operations with intelligent routing.
    """
    
    def __init__(self, knowledge_interface: KnowledgeInterface):
        """Initialize knowledge manager."""
        self.interface = knowledge_interface
        
        # Manager configuration
        self.default_timeout = 30000  # 30 seconds
        self.max_batch_size = 100
        self.auto_validate = True
        self.auto_analyze = True
        
        # Performance metrics
        self.manager_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_execution_time_ms": 0,
            "action_counts": {},
            "target_counts": {},
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Request cache
        self.request_cache: Dict[str, KnowledgeResponse] = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(
            "Knowledge manager initialized",
            auto_validate=self.auto_validate,
            auto_analyze=self.auto_analyze
        )
    
    async def process_request(
        self,
        request: KnowledgeRequest,
        use_cache: bool = True,
        timeout: Optional[int] = None
    ) -> KnowledgeResponse:
        """
        Process a knowledge management request.
        
        Args:
            request: Knowledge request to process
            use_cache: Whether to use cache
            timeout: Request timeout in milliseconds
            
        Returns:
            Knowledge response
        """
        start_time = datetime.now(timezone.utc)
        request_timeout = timeout or self.default_timeout
        
        try:
            self.manager_stats["total_requests"] += 1
            self.manager_stats["action_counts"][request.action] = self.manager_stats["action_counts"].get(request.action, 0) + 1
            self.manager_stats["target_counts"][request.target] = self.manager_stats["target_counts"].get(request.target, 0) + 1
            
            # Check cache first
            cache_key = self._generate_cache_key(request)
            if use_cache and self._is_cache_valid(cache_key):
                self.manager_stats["cache_hits"] += 1
                cached_response = self.request_cache[cache_key]
                
                logger.info(
                    "Request retrieved from cache",
                    action=request.action,
                    target=request.target
                )
                
                return cached_response
            
            self.manager_stats["cache_misses"] += 1
            
            # Process request based on action
            if request.action == KnowledgeAction.ADD:
                response = await self._process_add_request(request)
            elif request.action == KnowledgeAction.UPDATE:
                response = await self._process_update_request(request)
            elif request.action == KnowledgeAction.REMOVE:
                response = await self._process_remove_request(request)
            elif request.action == KnowledgeAction.SEARCH:
                response = await self._process_search_request(request)
            elif request.action == KnowledgeAction.EXPLORE:
                response = await self._process_explore_request(request)
            elif request.action == KnowledgeAction.ANALYZE:
                response = await self._process_analyze_request(request)
            elif request.action == KnowledgeAction.RECOMMEND:
                response = await self._process_recommend_request(request)
            elif request.action == KnowledgeAction.VALIDATE:
                response = await self._process_validate_request(request)
            elif request.action == KnowledgeAction.EXPORT:
                response = await self._process_export_request(request)
            elif request.action == KnowledgeAction.IMPORT:
                response = await self._process_import_request(request)
            else:
                raise BaseLayerError(f"Unsupported action: {request.action}")
            
            # Auto-validate if enabled
            if self.auto_validate and response.success and request.action in [KnowledgeAction.ADD, KnowledgeAction.UPDATE]:
                await self._auto_validate(request, response)
            
            # Auto-analyze if enabled
            if self.auto_analyze and response.success and request.action in [KnowledgeAction.ADD, KnowledgeAction.UPDATE]:
                await self._auto_analyze(request, response)
            
            # Update cache
            if use_cache:
                self._cache_response(cache_key, response)
            
            # Update statistics
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.manager_stats["successful_requests"] += 1
            self.manager_stats["average_execution_time_ms"] = (
                (self.manager_stats["average_execution_time_ms"] * (self.manager_stats["successful_requests"] - 1) + execution_time) /
                self.manager_stats["successful_requests"]
            )
            
            logger.info(
                "Request processed successfully",
                action=request.action,
                target=request.target,
                execution_time_ms=execution_time
            )
            
            return response
            
        except Exception as e:
            self.manager_stats["failed_requests"] += 1
            logger.error(
                "Request processing failed",
                error=str(e),
                action=request.action,
                target=request.target
            )
            
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            return KnowledgeResponse(
                success=False,
                action=request.action,
                target=request.target,
                data=None,
                message=f"Request failed: {str(e)}",
                execution_time_ms=execution_time,
                metadata={"parameters": request.parameters, "context": request.context or {}},
                error=str(e)
            )
    
    async def process_batch_requests(
        self,
        requests: List[KnowledgeRequest],
        use_cache: bool = True
    ) -> List[KnowledgeResponse]:
        """
        Process multiple knowledge requests in batch.
        
        Args:
            requests: List of knowledge requests
            use_cache: Whether to use cache
            
        Returns:
            List of knowledge responses
        """
        try:
            if len(requests) > self.max_batch_size:
                raise BaseLayerError(f"Batch size exceeds maximum: {len(requests)} > {self.max_batch_size}")
            
            # Process requests concurrently
            tasks = []
            for request in requests:
                task = self.process_request(request, use_cache=use_cache)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            knowledge_responses = []
            for response in responses:
                if isinstance(response, Exception):
                    knowledge_responses.append(KnowledgeResponse(
                        success=False,
                        action=KnowledgeAction.SEARCH,
                        target="unknown",
                        data=None,
                        message=f"Batch request failed: {str(response)}",
                        execution_time_ms=0,
                        metadata={},
                        error=str(response)
                    ))
                else:
                    knowledge_responses.append(response)
            
            logger.info(
                "Batch requests processed",
                total_requests=len(requests),
                successful_requests=len([r for r in knowledge_responses if r.success]),
                failed_requests=len([r for r in knowledge_responses if not r.success])
            )
            
            return knowledge_responses
            
        except Exception as e:
            logger.error(
                "Batch request processing failed",
                error=str(e),
                requests_count=len(requests)
            )
            raise BaseLayerError(f"Batch request processing failed: {str(e)}") from e
    
    async def _process_add_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process add request."""
        try:
            if request.target == "node":
                operation_result = await self.interface.execute(
                    operation=OperationType.CREATE,
                    mode=InterfaceMode.MANAGE,
                    parameters={
                        "item_type": "node",
                        "item_data": request.parameters
                    }
                )
                
                return KnowledgeResponse(
                    success=operation_result.success,
                    action=request.action,
                    target=request.target,
                    data=operation_result.data,
                    message=operation_result.message,
                    execution_time_ms=operation_result.execution_time_ms,
                    metadata=operation_result.metadata,
                    error=operation_result.error
                )
            
            elif request.target == "edge":
                operation_result = await self.interface.execute(
                    operation=OperationType.CREATE,
                    mode=InterfaceMode.MANAGE,
                    parameters={
                        "item_type": "edge",
                        "item_data": request.parameters
                    }
                )
                
                return KnowledgeResponse(
                    success=operation_result.success,
                    action=request.action,
                    target=request.target,
                    data=operation_result.data,
                    message=operation_result.message,
                    execution_time_ms=operation_result.execution_time_ms,
                    metadata=operation_result.metadata,
                    error=operation_result.error
                )
            
            elif request.target == "graph":
                operation_result = await self.interface.execute(
                    operation=OperationType.CREATE,
                    mode=InterfaceMode.MANAGE,
                    parameters={
                        "item_type": "graph",
                        "item_data": request.parameters
                    }
                )
                
                return KnowledgeResponse(
                    success=operation_result.success,
                    action=request.action,
                    target=request.target,
                    data=operation_result.data,
                    message=operation_result.message,
                    execution_time_ms=operation_result.execution_time_ms,
                    metadata=operation_result.metadata,
                    error=operation_result.error
                )
            
            else:
                raise BaseLayerError(f"Unsupported target for add: {request.target}")
                
        except Exception as e:
            logger.error(
                "Add request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Add request processing failed: {str(e)}") from e
    
    async def _process_update_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process update request."""
        try:
            item_id = request.parameters.get("id")
            update_data = request.parameters.get("data", {})
            
            if not item_id:
                raise BaseLayerError("Item ID required for update")
            
            operation_result = await self.interface.execute(
                operation=OperationType.UPDATE,
                mode=InterfaceMode.MANAGE,
                parameters={
                    "item_type": request.target,
                    "item_id": item_id,
                    "update_data": update_data
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Update request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Update request processing failed: {str(e)}") from e
    
    async def _process_remove_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process remove request."""
        try:
            item_id = request.parameters.get("id")
            
            if not item_id:
                raise BaseLayerError("Item ID required for remove")
            
            operation_result = await self.interface.execute(
                operation=OperationType.DELETE,
                mode=InterfaceMode.MANAGE,
                parameters={
                    "item_type": request.target,
                    "item_id": item_id
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Remove request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Remove request processing failed: {str(e)}") from e
    
    async def _process_search_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process search request."""
        try:
            query = request.parameters.get("query", "")
            search_mode = request.parameters.get("mode", "hybrid")
            top_k = request.parameters.get("top_k", 10)
            filters = request.parameters.get("filters", {})
            
            operation_result = await self.interface.execute(
                operation=OperationType.SEARCH,
                mode=InterfaceMode.QUERY,
                parameters={
                    "query": query,
                    "search_mode": search_mode,
                    "top_k": top_k,
                    "filters": filters
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Search request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Search request processing failed: {str(e)}") from e
    
    async def _process_explore_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process explore request."""
        try:
            start_node = request.parameters.get("start_node")
            max_depth = request.parameters.get("max_depth", 3)
            max_items = request.parameters.get("max_items", 50)
            
            if not start_node:
                raise BaseLayerError("Start node required for explore")
            
            operation_result = await self.interface.execute(
                operation=OperationType.SEARCH,
                mode=InterfaceMode.EXPLORE,
                parameters={
                    "start_node": start_node,
                    "max_depth": max_depth,
                    "max_items": max_items
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Explore request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Explore request processing failed: {str(e)}") from e
    
    async def _process_analyze_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process analyze request."""
        try:
            graph_id = request.parameters.get("graph_id")
            analysis_type = request.parameters.get("analysis_type", "structure")
            include_detailed = request.parameters.get("include_detailed", False)
            
            if not graph_id:
                raise BaseLayerError("Graph ID required for analyze")
            
            operation_result = await self.interface.execute(
                operation=OperationType.ANALYZE,
                mode=InterfaceMode.ANALYZE,
                parameters={
                    "graph_id": graph_id,
                    "analysis_type": analysis_type,
                    "include_detailed": include_detailed
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Analyze request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Analyze request processing failed: {str(e)}") from e
    
    async def _process_recommend_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process recommend request."""
        try:
            user_context = request.parameters.get("user_context", {})
            item_type = request.parameters.get("item_type", "node")
            top_k = request.parameters.get("top_k", 10)
            
            operation_result = await self.interface.execute(
                operation=OperationType.RECOMMEND,
                mode=InterfaceMode.QUERY,
                parameters={
                    "user_context": user_context,
                    "item_type": item_type,
                    "top_k": top_k
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Recommend request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Recommend request processing failed: {str(e)}") from e
    
    async def _process_validate_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process validate request."""
        try:
            item_id = request.parameters.get("id")
            validation_type = request.parameters.get("validation_type", "structure")
            
            if not item_id:
                raise BaseLayerError("Item ID required for validate")
            
            operation_result = await self.interface.execute(
                operation=OperationType.VALIDATE,
                mode=InterfaceMode.MANAGE,
                parameters={
                    "item_type": request.target,
                    "item_id": item_id,
                    "validation_type": validation_type
                }
            )
            
            return KnowledgeResponse(
                success=operation_result.success,
                action=request.action,
                target=request.target,
                data=operation_result.data,
                message=operation_result.message,
                execution_time_ms=operation_result.execution_time_ms,
                metadata=operation_result.metadata,
                error=operation_result.error
            )
            
        except Exception as e:
            logger.error(
                "Validate request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Validate request processing failed: {str(e)}") from e
    
    async def _process_export_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process export request."""
        try:
            item_id = request.parameters.get("id")
            export_format = request.parameters.get("format", "json")
            
            if not item_id:
                raise BaseLayerError("Item ID required for export")
            
            # This would implement export functionality
            # Placeholder for now
            export_data = {
                "item_id": item_id,
                "format": export_format,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "data": "Export data placeholder"
            }
            
            return KnowledgeResponse(
                success=True,
                action=request.action,
                target=request.target,
                data=export_data,
                message=f"Exported {request.target} in {export_format} format",
                execution_time_ms=0,
                metadata={"format": export_format, "item_id": item_id}
            )
            
        except Exception as e:
            logger.error(
                "Export request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Export request processing failed: {str(e)}") from e
    
    async def _process_import_request(self, request: KnowledgeRequest) -> KnowledgeResponse:
        """Process import request."""
        try:
            import_data = request.parameters.get("data")
            import_format = request.parameters.get("format", "json")
            
            if not import_data:
                raise BaseLayerError("Import data required")
            
            # This would implement import functionality
            # Placeholder for now
            import_result = {
                "imported_items": 1,
                "format": import_format,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "item_id": str(uuid.uuid4())
            }
            
            return KnowledgeResponse(
                success=True,
                action=request.action,
                target=request.target,
                data=import_result,
                message=f"Imported {request.target} from {import_format} format",
                execution_time_ms=0,
                metadata={"format": import_format, "imported_items": 1}
            )
            
        except Exception as e:
            logger.error(
                "Import request processing failed",
                error=str(e),
                target=request.target
            )
            raise BaseLayerError(f"Import request processing failed: {str(e)}") from e
    
    async def _auto_validate(self, request: KnowledgeRequest, response: KnowledgeResponse) -> None:
        """Auto-validate after add/update operations."""
        try:
            if response.success and response.data:
                item_id = response.data.get("node_id") or response.data.get("edge_id") or response.data.get("graph_id")
                
                if item_id:
                    validate_result = await self.interface.execute(
                        operation=OperationType.VALIDATE,
                        mode=InterfaceMode.MANAGE,
                        parameters={
                            "item_type": request.target,
                            "item_id": item_id,
                            "validation_type": "structure"
                        }
                    )
                    
                    if not validate_result.success:
                        logger.warning(
                            "Auto-validation failed",
                            item_id=item_id,
                            validation_errors=validate_result.data.get("errors", [])
                        )
            
        except Exception as e:
            logger.error(
                "Auto-validation failed",
                error=str(e),
                item_type=request.target
            )
    
    async def _auto_analyze(self, request: KnowledgeRequest, response: KnowledgeResponse) -> None:
        """Auto-analyze after add/update operations."""
        try:
            if response.success and response.data and request.target == "graph":
                graph_id = response.data.get("graph_id")
                
                if graph_id:
                    analyze_result = await self.interface.execute(
                        operation=OperationType.ANALYZE,
                        mode=InterfaceMode.ANALYZE,
                        parameters={
                            "graph_id": graph_id,
                            "analysis_type": "structure",
                            "include_detailed": False
                        }
                    )
                    
                    if analyze_result.success:
                        logger.info(
                            "Auto-analysis completed",
                            graph_id=graph_id,
                            analysis_data=analyze_result.data
                        )
            
        except Exception as e:
            logger.error(
                "Auto-analysis failed",
                error=str(e),
                item_type=request.target
            )
    
    def _generate_cache_key(self, request: KnowledgeRequest) -> str:
        """Generate cache key for request."""
        import hashlib
        key_data = {
            "action": request.action,
            "target": request.target,
            "parameters": request.parameters,
            "context": request.context or {}
        }
        key_json = str(key_data)  # Convert to string for hashing
        return hashlib.md5(key_json.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.request_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_response(self, cache_key: str, response: KnowledgeResponse) -> None:
        """Cache response."""
        self.request_cache[cache_key] = response
        self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
        
        # Cleanup old cache entries
        self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.now(timezone.utc)
        keys_to_remove = []
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age_seconds = (current_time - timestamp).total_seconds()
            if age_seconds > self.cache_ttl:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in self.request_cache:
                del self.request_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    async def get_manager_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_requests": self.manager_stats["total_requests"],
            "successful_requests": self.manager_stats["successful_requests"],
            "failed_requests": self.manager_stats["failed_requests"],
            "success_rate": (
                self.manager_stats["successful_requests"] / self.manager_stats["total_requests"]
                if self.manager_stats["total_requests"] > 0 else 0.0
            ),
            "average_execution_time_ms": self.manager_stats["average_execution_time_ms"],
            "action_counts": self.manager_stats["action_counts"],
            "target_counts": self.manager_stats["target_counts"],
            "cache_hits": self.manager_stats["cache_hits"],
            "cache_misses": self.manager_stats["cache_misses"],
            "cache_hit_rate": (
                self.manager_stats["cache_hits"] / 
                (self.manager_stats["cache_hits"] + self.manager_stats["cache_misses"])
                if (self.manager_stats["cache_hits"] + self.manager_stats["cache_misses"]) > 0 else 0.0
            ),
            "cache_size": len(self.request_cache)
        }
    
    def reset_stats(self) -> None:
        """Reset manager statistics."""
        self.manager_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_execution_time_ms": 0,
            "action_counts": {},
            "target_counts": {},
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info("Knowledge manager statistics reset")
    
    def clear_cache(self) -> None:
        """Clear request cache."""
        self.request_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Knowledge manager cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on knowledge manager."""
        try:
            # Test basic request
            test_request = KnowledgeRequest(
                action=KnowledgeAction.SEARCH,
                target="node",
                parameters={"query": "test", "top_k": 1}
            )
            
            test_response = await self.process_request(test_request, use_cache=False)
            
            # Test interface health
            interface_health = await self.interface.health_check()
            
            health_status = {
                "status": "healthy",
                "request_processing_working": test_response.success,
                "test_response_time_ms": test_response.execution_time_ms,
                "interface_health": interface_health,
                "cache_size": len(self.request_cache),
                "stats": await self.get_manager_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Knowledge manager health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Knowledge manager health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
