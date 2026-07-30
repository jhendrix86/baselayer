"""
CODX Knowledge Interface

Knowledge interface for CODX knowledge engine
with unified API and high-level operations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
from dataclasses import dataclass
from enum import Enum

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from ..models.vector_embedding import VectorEmbedding, EmbeddingModel, EmbeddingStatus
from ..vector.vector_store import VectorStore
from ..vector.similarity_search import SimilaritySearch, SearchMode, SearchResult
from ..graph.graph_traversal import GraphTraverser, TraversalAlgorithm
from ..graph.graph_analytics import GraphAnalyzer
from ..graph.graph_storage import GraphStorage
from ..retrieval.retrieval_engine import RetrievalEngine
from ..retrieval.query_processor import QueryProcessor
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class InterfaceMode(str, Enum):
    """Interface operation modes."""
    QUERY = "query"
    EXPLORE = "explore"
    ANALYZE = "analyze"
    MANAGE = "manage"
    VISUALIZE = "visualize"
    EXPORT = "export"
    IMPORT = "import"


class OperationType(str, Enum):
    """Operation types."""
    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    TRAVERSE = "traverse"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    VALIDATE = "validate"


@dataclass
class OperationResult:
    """Operation result data class."""
    success: bool
    operation_type: OperationType
    data: Any
    message: str
    execution_time_ms: int
    metadata: Dict[str, Any]
    error: Optional[str] = None


class KnowledgeInterface:
    """
    High-level knowledge interface for CODX engine.
    
    Provides unified API for all CODX operations
    including search, analysis, management, and visualization.
    """
    
    def __init__(
        self,
        db_session,
        vector_store: VectorStore,
        similarity_search: SimilaritySearch,
        graph_traverser: GraphTraverser,
        graph_analyzer: GraphAnalyzer,
        graph_storage: GraphStorage,
        retrieval_engine: RetrievalEngine,
        query_processor: QueryProcessor
    ):
        """Initialize knowledge interface."""
        self.db_session = db_session
        self.vector_store = vector_store
        self.similarity_search = similarity_search
        self.graph_traverser = graph_traverser
        self.graph_analyzer = graph_analyzer
        self.graph_storage = graph_storage
        self.retrieval_engine = retrieval_engine
        self.query_processor = query_processor
        
        # Interface configuration
        self.default_mode = InterfaceMode.QUERY
        self.default_operation = OperationType.SEARCH
        self.max_results = 100
        self.default_timeout = 30000  # 30 seconds
        
        # Performance metrics
        self.interface_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "average_execution_time_ms": 0,
            "operation_counts": {},
            "mode_usage": {},
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Operation cache
        self.operation_cache: Dict[str, OperationResult] = {}
        self.cache_ttl = 600  # 10 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(
            "Knowledge interface initialized",
            default_mode=self.default_mode,
            default_operation=self.default_operation
        )
    
    async def execute(
        self,
        operation: OperationType,
        mode: InterfaceMode = InterfaceMode.QUERY,
        parameters: Dict[str, Any] = None,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        timeout: Optional[int] = None
    ) -> OperationResult:
        """
        Execute a knowledge operation.
        
        Args:
            operation: Type of operation to execute
            mode: Interface mode
            parameters: Operation parameters
            context: Operation context
            use_cache: Whether to use cache
            timeout: Operation timeout in milliseconds
            
        Returns:
            Operation result
        """
        start_time = datetime.now(timezone.utc)
        operation_timeout = timeout or self.default_timeout
        
        try:
            self.interface_stats["total_operations"] += 1
            self.interface_stats["operation_counts"][operation] = self.interface_stats["operation_counts"].get(operation, 0) + 1
            self.interface_stats["mode_usage"][mode] = self.interface_stats["mode_usage"].get(mode, 0) + 1
            
            # Check cache first
            cache_key = self._generate_cache_key(operation, mode, parameters, context)
            if use_cache and self._is_cache_valid(cache_key):
                self.interface_stats["cache_hits"] += 1
                cached_result = self.operation_cache[cache_key]
                
                logger.info(
                    "Operation retrieved from cache",
                    operation=operation,
                    mode=mode,
                    cache_key=cache_key
                )
                
                return cached_result
            
            self.interface_stats["cache_misses"] += 1
            
            # Execute operation based on type
            if operation == OperationType.SEARCH:
                result = await self._execute_search_operation(mode, parameters, context)
            elif operation == OperationType.CREATE:
                result = await self._execute_create_operation(mode, parameters, context)
            elif operation == OperationType.UPDATE:
                result = await self._execute_update_operation(mode, parameters, context)
            elif operation == OperationType.DELETE:
                result = await self._execute_delete_operation(mode, parameters, context)
            elif operation == OperationType.TRAVERSE:
                result = await self._execute_traverse_operation(mode, parameters, context)
            elif operation == OperationType.ANALYZE:
                result = await self._execute_analyze_operation(mode, parameters, context)
            elif operation == OperationType.RECOMMEND:
                result = await self._execute_recommend_operation(mode, parameters, context)
            elif operation == OperationType.VALIDATE:
                result = await self._execute_validate_operation(mode, parameters, context)
            else:
                raise BaseLayerError(f"Unsupported operation: {operation}")
            
            # Update cache
            if use_cache:
                self._cache_operation(cache_key, result)
            
            # Update statistics
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.interface_stats["successful_operations"] += 1
            self.interface_stats["average_execution_time_ms"] = (
                (self.interface_stats["average_execution_time_ms"] * (self.interface_stats["successful_operations"] - 1) + execution_time) /
                self.interface_stats["successful_operations"]
            )
            
            logger.info(
                "Operation executed successfully",
                operation=operation,
                mode=mode,
                execution_time_ms=execution_time
            )
            
            return result
            
        except Exception as e:
            self.interface_stats["failed_operations"] += 1
            logger.error(
                "Operation execution failed",
                error=str(e),
                operation=operation,
                mode=mode
            )
            
            return OperationResult(
                success=False,
                operation_type=operation,
                data=None,
                message=f"Operation failed: {str(e)}",
                execution_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                metadata={"parameters": parameters or {}, "context": context or {}},
                error=str(e)
            )
    
    async def _execute_search_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute search operation."""
        try:
            query = parameters.get("query", "")
            search_mode = parameters.get("search_mode", "hybrid")
            top_k = parameters.get("top_k", self.max_results)
            threshold = parameters.get("threshold", 0.7)
            filters = parameters.get("filters", {})
            
            if mode == InterfaceMode.QUERY:
                # Use retrieval engine
                results = await self.retrieval_engine.query(
                    query=query,
                    mode=search_mode,
                    top_k=top_k,
                    threshold=threshold,
                    filters=filters,
                    context=context
                )
                
                return OperationResult(
                    success=True,
                    operation_type=OperationType.SEARCH,
                    data=results,
                    message=f"Found {len(results)} results",
                    execution_time_ms=0,
                    metadata={"query": query, "search_mode": search_mode}
                )
            
            elif mode == InterfaceMode.EXPLORE:
                # Use graph traversal
                start_node = parameters.get("start_node")
                max_depth = parameters.get("max_depth", 3)
                
                if start_node:
                    traversal_result = await self.graph_traverser.breadth_first_search(
                        start_node_id=start_node,
                        max_depth=max_depth,
                        max_nodes=top_k,
                        include_metadata=True
                    )
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.SEARCH,
                        data=traversal_result,
                        message=f"Explored {len(traversal_result['traversal_order'])} nodes",
                        execution_time_ms=traversal_result.get("execution_time_ms", 0),
                        metadata={"start_node": start_node, "max_depth": max_depth}
                    )
            
            else:
                # Default to vector search
                search_results = await self.similarity_search.search(
                    query=query,
                    top_k=top_k,
                    threshold=threshold,
                    filters=filters
                )
                
                return OperationResult(
                    success=True,
                    operation_type=OperationType.SEARCH,
                    data=search_results,
                    message=f"Found {len(search_results)} similar items",
                    execution_time_ms=0,
                    metadata={"query": query, "search_mode": "vector"}
                )
                
        except Exception as e:
            logger.error(
                "Search operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Search operation failed: {str(e)}") from e
    
    async def _execute_create_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute create operation."""
        try:
            if mode == InterfaceMode.MANAGE:
                item_type = parameters.get("item_type", "node")
                item_data = parameters.get("item_data", {})
                
                if item_type == "node":
                    # Create knowledge node
                    node = KnowledgeNode(
                        title=item_data.get("title", ""),
                        node_type=item_data.get("node_type", NodeType.CONCEPT),
                        content=item_data.get("content", ""),
                        description=item_data.get("description", ""),
                        keywords=item_data.get("keywords", []),
                        tags=item_data.get("tags", {}),
                        metadata=item_data.get("metadata", {}),
                        source=item_data.get("source", ""),
                        author=item_data.get("author", ""),
                        created_by=item_data.get("created_by", ""),
                        confidence_score=item_data.get("confidence_score", 1.0),
                        quality_score=item_data.get("quality_score", 1.0),
                        relevance_score=item_data.get("relevance_score", 1.0)
                    )
                    
                    saved_node = await self.graph_storage.save_node(node)
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.CREATE,
                        data={"node_id": str(saved_node.id)},
                        message=f"Created node: {saved_node.title}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "node_id": str(saved_node.id)}
                    )
                
                elif item_type == "edge":
                    # Create knowledge edge
                    edge = KnowledgeEdge(
                        source_id=uuid.UUID(item_data.get("source_id")),
                        target_id=uuid.UUID(item_data.get("target_id")),
                        edge_type=item_data.get("edge_type", EdgeType.RELATES_TO),
                        weight=item_data.get("weight", 1.0),
                        confidence=item_data.get("confidence", 1.0),
                        strength=item_data.get("strength", 1.0),
                        bidirectional=item_data.get("bidirectional", False),
                        label=item_data.get("label", ""),
                        description=item_data.get("description", ""),
                        properties=item_data.get("properties", {}),
                        metadata=item_data.get("metadata", {}),
                        context=item_data.get("context", ""),
                        evidence=item_data.get("evidence", ""),
                        source=item_data.get("source", ""),
                        created_by=item_data.get("created_by", "")
                    )
                    
                    saved_edge = await self.graph_storage.save_edge(edge)
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.CREATE,
                        data={"edge_id": str(saved_edge.id)},
                        message=f"Created edge: {saved_edge.edge_type}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "edge_id": str(saved_edge.id)}
                    )
                
                elif item_type == "graph":
                    # Create knowledge graph
                    graph = KnowledgeGraph(
                        name=item_data.get("name", ""),
                        description=item_data.get("description", ""),
                        graph_type=item_data.get("graph_type", GraphType.CONCEPT_GRAPH),
                        root_node_id=uuid.UUID(item_data.get("root_node_id")) if item_data.get("root_node_id") else None,
                        metadata=item_data.get("metadata", {}),
                        configuration=item_data.get("configuration", {}),
                        tags=item_data.get("tags", [])
                    )
                    
                    saved_graph = await self.graph_storage.save_graph(graph)
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.CREATE,
                        data={"graph_id": str(saved_graph.id)},
                        message=f"Created graph: {saved_graph.name}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "graph_id": str(saved_graph.id)}
                    )
                
                else:
                    raise BaseLayerError(f"Unsupported item type for creation: {item_type}")
            
            else:
                raise BaseLayerError(f"Create operation not supported in mode: {mode}")
                
        except Exception as e:
            logger.error(
                "Create operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Create operation failed: {str(e)}") from e
    
    async def _execute_update_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute update operation."""
        try:
            if mode == InterfaceMode.MANAGE:
                item_type = parameters.get("item_type", "node")
                item_id = parameters.get("item_id")
                update_data = parameters.get("update_data", {})
                
                if item_type == "node":
                    # Update knowledge node
                    existing_node = await self.graph_storage.get_node(item_id)
                    if not existing_node:
                        raise BaseLayerError(f"Node not found: {item_id}")
                    
                    # Apply updates
                    for field, value in update_data.items():
                        if hasattr(existing_node, field):
                            setattr(existing_node, field, value)
                    
                    existing_node.updated_at = datetime.now(timezone.utc)
                    existing_node.increment_update_count()
                    
                    updated_node = await self.graph_storage.save_node(existing_node)
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.UPDATE,
                        data={"node_id": str(updated_node.id)},
                        message=f"Updated node: {updated_node.title}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "node_id": str(updated_node.id)}
                    )
                
                elif item_type == "edge":
                    # Update knowledge edge
                    existing_edge = await self.graph_storage.get_edge(item_id)
                    if not existing_edge:
                        raise BaseLayerError(f"Edge not found: {item_id}")
                    
                    # Apply updates
                    for field, value in update_data.items():
                        if hasattr(existing_edge, field):
                            setattr(existing_edge, field, value)
                    
                    existing_edge.updated_at = datetime.now(timezone.utc)
                    existing_edge.increment_update_count()
                    
                    updated_edge = await self.graph_storage.save_edge(existing_edge)
                    
                    return OperationResult(
                        success=True,
                        operation_type=OperationType.UPDATE,
                        data={"edge_id": str(updated_edge.id)},
                        message=f"Updated edge: {updated_edge.edge_type}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "edge_id": str(updated_edge.id)}
                    )
                
                else:
                    raise BaseLayerError(f"Unsupported item type for update: {item_type}")
            
            else:
                raise BaseLayerError(f"Update operation not supported in mode: {mode}")
                
        except Exception as e:
            logger.error(
                "Update operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Update operation failed: {str(e)}") from e
    
    async def _execute_delete_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute delete operation."""
        try:
            if mode == InterfaceMode.MANAGE:
                item_type = parameters.get("item_type", "node")
                item_id = parameters.get("item_id")
                
                if item_type == "node":
                    # Delete knowledge node
                    success = await self.graph_storage.delete_node(item_id)
                    
                    return OperationResult(
                        success=success,
                        operation_type=OperationType.DELETE,
                        data={"node_id": item_id},
                        message=f"Deleted node: {item_id}" if success else f"Failed to delete node: {item_id}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "node_id": item_id}
                    )
                
                elif item_type == "edge":
                    # Delete knowledge edge
                    success = await self.graph_storage.delete_edge(item_id)
                    
                    return OperationResult(
                        success=success,
                        operation_type=OperationType.DELETE,
                        data={"edge_id": item_id},
                        message=f"Deleted edge: {item_id}" if success else f"Failed to delete edge: {item_id}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "edge_id": item_id}
                    )
                
                elif item_type == "graph":
                    # Delete knowledge graph
                    success = await self.graph_storage.delete_graph(item_id)
                    
                    return OperationResult(
                        success=success,
                        operation_type=OperationType.DELETE,
                        data={"graph_id": item_id},
                        message=f"Deleted graph: {item_id}" if success else f"Failed to delete graph: {item_id}",
                        execution_time_ms=0,
                        metadata={"item_type": item_type, "graph_id": item_id}
                    )
                
                else:
                    raise BaseLayerError(f"Unsupported item type for deletion: {item_type}")
            
            else:
                raise BaseLayerError(f"Delete operation not supported in mode: {mode}")
                
        except Exception as e:
            logger.error(
                "Delete operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Delete operation failed: {str(e)}") from e
    
    async def _execute_traverse_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute traverse operation."""
        try:
            start_node = parameters.get("start_node")
            algorithm = parameters.get("algorithm", TraversalAlgorithm.BFS)
            max_depth = parameters.get("max_depth", 5)
            max_nodes = parameters.get("max_nodes", 100)
            edge_types = parameters.get("edge_types", [])
            
            if algorithm == TraversalAlgorithm.BFS:
                traversal_result = await self.graph_traverser.breadth_first_search(
                    start_node_id=start_node,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                    edge_types=edge_types,
                    include_metadata=True
                )
            elif algorithm == TraversalAlgorithm.DFS:
                traversal_result = await self.graph_traverser.depth_first_search(
                    start_node_id=start_node,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                    edge_types=edge_types,
                    include_metadata=True
                )
            elif algorithm == TraversalAlgorithm.DIJKSTRA:
                target_node = parameters.get("target_node")
                if not target_node:
                    raise BaseLayerError("Target node required for Dijkstra traversal")
                
                traversal_result = await self.graph_traverser.dijkstra_shortest_path(
                    start_node_id=start_node,
                    target_node_id=target_node,
                    edge_types=edge_types,
                    include_metadata=True
                )
            else:
                raise BaseLayerError(f"Unsupported traversal algorithm: {algorithm}")
            
            return OperationResult(
                success=True,
                operation_type=OperationType.TRAVERSE,
                data=traversal_result,
                message=f"Traversal completed with {algorithm}",
                execution_time_ms=traversal_result.get("execution_time_ms", 0),
                metadata={"algorithm": algorithm, "start_node": start_node}
            )
            
        except Exception as e:
            logger.error(
                "Traverse operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Traverse operation failed: {str(e)}") from e
    
    async def _execute_analyze_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute analyze operation."""
        try:
            if mode == InterfaceMode.ANALYZE:
                graph_id = parameters.get("graph_id")
                analysis_type = parameters.get("analysis_type", "structure")
                include_detailed = parameters.get("include_detailed", False)
                
                if not graph_id:
                    raise BaseLayerError("Graph ID required for analysis")
                
                if analysis_type == "structure":
                    analysis_result = await self.graph_analyzer.analyze_graph_structure(
                        graph_id=graph_id,
                        include_detailed=include_detailed
                    )
                elif analysis_type == "performance":
                    time_range = parameters.get("time_range")
                    analysis_result = await self.graph_analyzer.analyze_graph_performance(
                        graph_id=graph_id,
                        time_range=time_range
                    )
                elif analysis_type == "usage":
                    time_range = parameters.get("time_range")
                    analysis_result = await self.graph_analyzer.analyze_graph_usage(
                        graph_id=graph_id,
                        time_range=time_range
                    )
                else:
                    raise BaseLayerError(f"Unsupported analysis type: {analysis_type}")
                
                return OperationResult(
                    success=True,
                    operation_type=OperationType.ANALYZE,
                    data=analysis_result,
                    message=f"Analysis completed: {analysis_type}",
                    execution_time_ms=0,
                    metadata={"analysis_type": analysis_type, "graph_id": graph_id}
                )
            
            else:
                raise BaseLayerError(f"Analyze operation not supported in mode: {mode}")
                
        except Exception as e:
            logger.error(
                "Analyze operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Analyze operation failed: {str(e)}") from e
    
    async def _execute_recommend_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute recommend operation."""
        try:
            user_context = parameters.get("user_context", {})
            item_type = parameters.get("item_type", "node")
            top_k = parameters.get("top_k", 10)
            
            recommendations = await self.retrieval_engine.recommend(
                user_context=user_context,
                item_type=item_type,
                top_k=top_k
            )
            
            return OperationResult(
                success=True,
                operation_type=OperationType.RECOMMEND,
                data=recommendations,
                message=f"Generated {len(recommendations)} recommendations",
                execution_time_ms=0,
                metadata={"user_context_keys": list(user_context.keys()), "item_type": item_type}
            )
            
        except Exception as e:
            logger.error(
                "Recommend operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Recommend operation failed: {str(e)}") from e
    
    async def _execute_validate_operation(
        self,
        mode: InterfaceMode,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> OperationResult:
        """Execute validate operation."""
        try:
            validation_type = parameters.get("validation_type", "structure")
            item_id = parameters.get("item_id")
            item_type = parameters.get("item_type", "graph")
            
            if validation_type == "structure":
                if item_type == "graph":
                    errors = await self.graph_analyzer.validate_graph_structure(item_id)
                    
                    return OperationResult(
                        success=len(errors) == 0,
                        operation_type=OperationType.VALIDATE,
                        data={"errors": errors, "is_valid": len(errors) == 0},
                        message=f"Graph validation completed: {len(errors)} errors found",
                        execution_time_ms=0,
                        metadata={"validation_type": validation_type, "item_id": item_id}
                    )
                else:
                    raise BaseLayerError(f"Structure validation not supported for item type: {item_type}")
            
            else:
                raise BaseLayerError(f"Unsupported validation type: {validation_type}")
                
        except Exception as e:
            logger.error(
                "Validate operation failed",
                error=str(e),
                mode=mode
            )
            raise BaseLayerError(f"Validate operation failed: {str(e)}") from e
    
    def _generate_cache_key(
        self,
        operation: OperationType,
        mode: InterfaceMode,
        parameters: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for operation."""
        import hashlib
        key_data = {
            "operation": operation,
            "mode": mode,
            "parameters": parameters or {},
            "context": context or {}
        }
        key_json = str(key_data)  # Convert to string for hashing
        return hashlib.md5(key_json.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.operation_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_operation(self, cache_key: str, result: OperationResult) -> None:
        """Cache operation result."""
        self.operation_cache[cache_key] = result
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
            if key in self.operation_cache:
                del self.operation_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    async def batch_execute(
        self,
        operations: List[Dict[str, Any]],
        use_cache: bool = True
    ) -> List[OperationResult]:
        """
        Execute multiple operations in batch.
        
        Args:
            operations: List of operation specifications
            use_cache: Whether to use cache
            
        Returns:
            List of operation results
        """
        try:
            # Execute operations concurrently
            tasks = []
            for op_spec in operations:
                task = self.execute(
                    operation=op_spec.get("operation", OperationType.SEARCH),
                    mode=op_spec.get("mode", InterfaceMode.QUERY),
                    parameters=op_spec.get("parameters", {}),
                    context=op_spec.get("context"),
                    use_cache=use_cache
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            operation_results = []
            for result in results:
                if isinstance(result, Exception):
                    operation_results.append(OperationResult(
                        success=False,
                        operation_type=OperationType.SEARCH,
                        data=None,
                        message=f"Operation failed: {str(result)}",
                        execution_time_ms=0,
                        metadata={},
                        error=str(result)
                    ))
                else:
                    operation_results.append(result)
            
            logger.info(
                "Batch operations completed",
                total_operations=len(operations),
                successful_operations=len([r for r in operation_results if r.success]),
                failed_operations=len([r for r in operation_results if not r.success])
            )
            
            return operation_results
            
        except Exception as e:
            logger.error(
                "Batch operations failed",
                error=str(e),
                operations_count=len(operations)
            )
            raise BaseLayerError(f"Batch operations failed: {str(e)}") from e
    
    async def get_interface_stats(self) -> Dict[str, Any]:
        """Get interface statistics."""
        return {
            "total_operations": self.interface_stats["total_operations"],
            "successful_operations": self.interface_stats["successful_operations"],
            "failed_operations": self.interface_stats["failed_operations"],
            "success_rate": (
                self.interface_stats["successful_operations"] / self.interface_stats["total_operations"]
                if self.interface_stats["total_operations"] > 0 else 0.0
            ),
            "average_execution_time_ms": self.interface_stats["average_execution_time_ms"],
            "operation_counts": self.interface_stats["operation_counts"],
            "mode_usage": self.interface_stats["mode_usage"],
            "cache_hits": self.interface_stats["cache_hits"],
            "cache_misses": self.interface_stats["cache_misses"],
            "cache_hit_rate": (
                self.interface_stats["cache_hits"] / 
                (self.interface_stats["cache_hits"] + self.interface_stats["cache_misses"])
                if (self.interface_stats["cache_hits"] + self.interface_stats["cache_misses"]) > 0 else 0.0
            ),
            "cache_size": len(self.operation_cache)
        }
    
    def reset_stats(self) -> None:
        """Reset interface statistics."""
        self.interface_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "average_execution_time_ms": 0,
            "operation_counts": {},
            "mode_usage": {},
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info("Interface statistics reset")
    
    def clear_cache(self) -> None:
        """Clear operation cache."""
        self.operation_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Knowledge interface cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on knowledge interface."""
        try:
            # Test basic operation
            test_operation = await self.execute(
                operation=OperationType.SEARCH,
                mode=InterfaceMode.QUERY,
                parameters={"query": "test", "top_k": 1},
                use_cache=False
            )
            
            # Test component health
            vector_health = await self.vector_store.health_check()
            similarity_health = await self.similarity_search.health_check()
            graph_health = await self.graph_traverser.health_check()
            retriever_health = await self.retrieval_engine.health_check()
            
            health_status = {
                "status": "healthy",
                "operation_working": test_operation.success,
                "test_results_count": len(test_operation.data) if test_operation.data else 0,
                "component_health": {
                    "vector_store": vector_health,
                    "similarity_search": similarity_health,
                    "graph_traverser": graph_health,
                    "retrieval_engine": retriever_health
                },
                "cache_size": len(self.operation_cache),
                "stats": await self.get_interface_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Knowledge interface health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Knowledge interface health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
