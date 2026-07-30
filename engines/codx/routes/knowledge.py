"""
CODX Knowledge API Routes

FastAPI routes for CODX knowledge engine
with comprehensive CRUD and query operations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from ..models.schemas import (
    KnowledgeNodeCreate, KnowledgeNodeUpdate, KnowledgeNodeResponse,
    KnowledgeEdgeCreate, KnowledgeEdgeUpdate, KnowledgeEdgeResponse,
    KnowledgeGraphCreate, KnowledgeGraphUpdate, KnowledgeGraphResponse,
    VectorEmbeddingCreate, VectorEmbeddingUpdate, VectorEmbeddingResponse,
    SearchRequest, SearchResponse, TraversalRequest, TraversalResponse,
    AnalyticsRequest, AnalyticsResponse, ExportRequest, ExportResponse,
    BatchOperationRequest, BatchOperationResponse, HealthResponse,
    ErrorResponse, SuccessResponse, PaginationParams
)
from ..interface.knowledge_manager import KnowledgeManager, KnowledgeAction, KnowledgeRequest, KnowledgeResponse
from ..interface.knowledge_interface import KnowledgeInterface, OperationType, InterfaceMode
from ..retrieval.retrieval_engine import RetrievalEngine
from ..vector.vector_store import VectorStore
from ..vector.similarity_search import SimilaritySearch
from ..graph.graph_traversal import GraphTraverser
from ..graph.graph_analytics import GraphAnalyzer
from ..graph.graph_storage import GraphStorage
from ..retrieval.query_processor import QueryProcessor
from backend.shared.dependencies import get_db_session, get_current_user
from backend.shared.errors import BaseLayerError
from backend.shared.logger import get_logger

logger = get_logger(__name__)

# Create router
knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Pydantic models for API requests/responses
class QueryRequest(BaseModel):
    """Query request model."""
    query: str = Field(..., description="Search query")
    mode: Optional[str] = Field("hybrid", description="Search mode")
    strategy: Optional[str] = Field("relevance", description="Ranking strategy")
    top_k: Optional[int] = Field(10, description="Number of results")
    threshold: Optional[float] = Field(0.7, description="Similarity threshold")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Search preferences")
    context: Optional[Dict[str, Any]] = Field(None, description="Query context")
    use_cache: Optional[bool] = Field(True, description="Use cache")
    include_explanations: Optional[bool] = Field(False, description="Include explanations")

class QueryResponse(BaseModel):
    """Query response model."""
    query: str
    mode: str
    strategy: str
    results: List[Dict[str, Any]]
    total_found: int
    execution_time_ms: int
    from_cache: bool
    processed_query: Optional[Dict[str, Any]] = None
    timestamp: str
    metadata: Dict[str, Any]

class NodeCreateRequest(BaseModel):
    """Node creation request model."""
    title: str = Field(..., description="Node title")
    node_type: str = Field("concept", description="Node type")
    content: Optional[str] = Field(None, description="Node content")
    description: Optional[str] = Field(None, description="Node description")
    keywords: Optional[List[str]] = Field([], description="Node keywords")
    tags: Optional[Dict[str, Any]] = Field({}, description="Node tags")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Node metadata")
    source: Optional[str] = Field("", description="Node source")
    author: Optional[str] = Field("", description="Node author")
    created_by: Optional[str] = Field("", description="Created by")
    confidence_score: Optional[float] = Field(1.0, description="Confidence score")
    quality_score: Optional[float] = Field(1.0, description="Quality score")
    relevance_score: Optional[float] = Field(1.0, description="Relevance score")

class EdgeCreateRequest(BaseModel):
    """Edge creation request model."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    edge_type: str = Field("relates_to", description="Edge type")
    weight: Optional[float] = Field(1.0, description="Edge weight")
    confidence: Optional[float] = Field(1.0, description="Edge confidence")
    strength: Optional[float] = Field(1.0, description="Edge strength")
    bidirectional: Optional[bool] = Field(False, description="Is bidirectional")
    label: Optional[str] = Field("", description="Edge label")
    description: Optional[str] = Field(None, description="Edge description")
    properties: Optional[Dict[str, Any]] = Field({}, description="Edge properties")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Edge metadata")
    context: Optional[str] = Field("", description="Edge context")
    evidence: Optional[str] = Field("", description="Edge evidence")
    source: Optional[str] = Field("", description="Edge source")
    created_by: Optional[str] = Field("", description="Created by")

class GraphCreateRequest(BaseModel):
    """Graph creation request model."""
    name: str = Field(..., description="Graph name")
    description: Optional[str] = Field(None, description="Graph description")
    graph_type: str = Field("concept_graph", description="Graph type")
    root_node_id: Optional[str] = Field(None, description="Root node ID")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Graph metadata")
    configuration: Optional[Dict[str, Any]] = Field({}, description="Graph configuration")
    tags: Optional[List[str]] = Field([], description="Graph tags")

class TraversalRequest(BaseModel):
    """Traversal request model."""
    start_node_id: str = Field(..., description="Starting node ID")
    algorithm: Optional[str] = Field("bfs", description="Traversal algorithm")
    max_depth: Optional[int] = Field(3, description="Maximum depth")
    max_nodes: Optional[int] = Field(100, description="Maximum nodes")
    edge_types: Optional[List[str]] = Field(None, description="Edge types to traverse")
    include_metadata: Optional[bool] = Field(True, description="Include metadata")

class AnalyticsRequest(BaseModel):
    """Analytics request model."""
    graph_id: str = Field(..., description="Graph ID")
    analysis_type: Optional[str] = Field("structure", description="Analysis type")
    include_detailed: Optional[bool] = Field(False, description="Include detailed analysis")
    time_range: Optional[Dict[str, str]] = Field(None, description="Time range")

class ExportRequest(BaseModel):
    """Export request model."""
    graph_id: str = Field(..., description="Graph ID")
    format: Optional[str] = Field("json", description="Export format")
    include_metadata: Optional[bool] = Field(True, description="Include metadata")
    filters: Optional[Dict[str, Any]] = Field(None, description="Export filters")

class BatchOperationRequest(BaseModel):
    """Batch operation request model."""
    operations: List[Dict[str, Any]] = Field(..., description="Operations to perform")
    use_cache: Optional[bool] = Field(True, description="Use cache")
    timeout: Optional[int] = Field(30000, description="Timeout in milliseconds")

# Dependency to get knowledge manager
async def get_knowledge_manager(db_session = Depends(get_db_session)) -> KnowledgeManager:
    """Get knowledge manager instance."""
    try:
        # Initialize components (in a real app, these would be singletons)
        vector_store = VectorStore(db_session)
        similarity_search = SimilaritySearch(vector_store)
        graph_traverser = GraphTraverser(db_session)
        graph_analyzer = GraphAnalyzer(db_session)
        graph_storage = GraphStorage(db_session)
        query_processor = QueryProcessor()
        retrieval_engine = RetrievalEngine(
            db_session, vector_store, similarity_search, 
            graph_traverser, graph_analyzer, query_processor
        )
        knowledge_interface = KnowledgeInterface(
            db_session, vector_store, similarity_search, graph_traverser,
            graph_analyzer, graph_storage, retrieval_engine, query_processor
        )
        knowledge_manager = KnowledgeManager(knowledge_interface)
        
        return knowledge_manager
    except Exception as e:
        logger.error("Failed to initialize knowledge manager", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to initialize knowledge manager")

# Query endpoints
@knowledge_router.post("/query", response_model=QueryResponse)
async def query_knowledge(
    request: QueryRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Query knowledge base."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.SEARCH,
            target="all",
            parameters={
                "query": request.query,
                "mode": request.mode,
                "strategy": request.strategy,
                "top_k": request.top_k,
                "threshold": request.threshold,
                "filters": request.filters,
                "preferences": request.preferences
            },
            context=request.context
        )
        
        # Process request
        response = await knowledge_manager.process_request(
            request=knowledge_request,
            use_cache=request.use_cache
        )
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return QueryResponse(
            query=request.query,
            mode=request.mode,
            strategy=request.strategy,
            results=response.data.get("results", []),
            total_found=response.data.get("total_found", 0),
            execution_time_ms=response.execution_time_ms,
            from_cache=response.data.get("from_cache", False),
            processed_query=response.data.get("processed_query"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=response.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Query failed", error=str(e), query=request.query)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@knowledge_router.get("/search", response_model=QueryResponse)
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    mode: str = Query("hybrid", description="Search mode"),
    strategy: str = Query("relevance", description="Ranking strategy"),
    top_k: int = Query(10, description="Number of results"),
    threshold: float = Query(0.7, description="Similarity threshold"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Search knowledge base (GET endpoint)."""
    try:
        request = QueryRequest(
            query=q,
            mode=mode,
            strategy=strategy,
            top_k=top_k,
            threshold=threshold
        )
        
        return await query_knowledge(request, knowledge_manager, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search failed", error=str(e), query=q)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Node endpoints
@knowledge_router.post("/nodes", response_model=KnowledgeNodeResponse)
async def create_node(
    request: NodeCreateRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Create a knowledge node."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.ADD,
            target="node",
            parameters={
                "title": request.title,
                "node_type": request.node_type,
                "content": request.content,
                "description": request.description,
                "keywords": request.keywords,
                "tags": request.tags,
                "metadata": request.metadata,
                "source": request.source,
                "author": request.author,
                "created_by": request.created_by,
                "confidence_score": request.confidence_score,
                "quality_score": request.quality_score,
                "relevance_score": request.relevance_score
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return KnowledgeNodeResponse(
            id=response.data.get("node_id"),
            title=request.title,
            node_type=request.node_type,
            content=request.content,
            description=request.description,
            keywords=request.keywords,
            tags=request.tags,
            metadata=request.metadata,
            source=request.source,
            author=request.author,
            created_by=request.created_by,
            confidence_score=request.confidence_score,
            quality_score=request.quality_score,
            relevance_score=request.relevance_score,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Node creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Node creation failed: {str(e)}")

@knowledge_router.get("/nodes/{node_id}", response_model=KnowledgeNodeResponse)
async def get_node(
    node_id: str = Path(..., description="Node ID"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get a knowledge node by ID."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.SEARCH,
            target="node",
            parameters={
                "query": f"id:{node_id}",
                "top_k": 1
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success or not response.data.get("results"):
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Get first result
        node_data = response.data["results"][0]
        
        return KnowledgeNodeResponse(**node_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Node retrieval failed", error=str(e), node_id=node_id)
        raise HTTPException(status_code=500, detail=f"Node retrieval failed: {str(e)}")

@knowledge_router.put("/nodes/{node_id}", response_model=KnowledgeNodeResponse)
async def update_node(
    node_id: str = Path(..., description="Node ID"),
    request: NodeCreateRequest = Body(..., description="Node update data"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Update a knowledge node."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.UPDATE,
            target="node",
            parameters={
                "id": node_id,
                "data": {
                    "title": request.title,
                    "node_type": request.node_type,
                    "content": request.content,
                    "description": request.description,
                    "keywords": request.keywords,
                    "tags": request.tags,
                    "metadata": request.metadata,
                    "source": request.source,
                    "author": request.author,
                    "confidence_score": request.confidence_score,
                    "quality_score": request.quality_score,
                    "relevance_score": request.relevance_score
                }
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Return updated node
        return await get_node(node_id, knowledge_manager, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Node update failed", error=str(e), node_id=node_id)
        raise HTTPException(status_code=500, detail=f"Node update failed: {str(e)}")

@knowledge_router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str = Path(..., description="Node ID"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Delete a knowledge node."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.REMOVE,
            target="node",
            parameters={
                "id": node_id
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return {"message": "Node deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Node deletion failed", error=str(e), node_id=node_id)
        raise HTTPException(status_code=500, detail=f"Node deletion failed: {str(e)}")

@knowledge_router.get("/nodes", response_model=List[KnowledgeNodeResponse])
async def list_nodes(
    limit: int = Query(50, description="Limit"),
    offset: int = Query(0, description="Offset"),
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """List knowledge nodes."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.SEARCH,
            target="node",
            parameters={
                "query": "",
                "top_k": limit,
                "filters": {"node_type": node_type} if node_type else None
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        nodes = []
        for node_data in response.data.get("results", []):
            nodes.append(KnowledgeNodeResponse(**node_data))
        
        return nodes
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Node listing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Node listing failed: {str(e)}")

# Edge endpoints
@knowledge_router.post("/edges", response_model=KnowledgeEdgeResponse)
async def create_edge(
    request: EdgeCreateRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Create a knowledge edge."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.ADD,
            target="edge",
            parameters={
                "source_id": request.source_id,
                "target_id": request.target_id,
                "edge_type": request.edge_type,
                "weight": request.weight,
                "confidence": request.confidence,
                "strength": request.strength,
                "bidirectional": request.bidirectional,
                "label": request.label,
                "description": request.description,
                "properties": request.properties,
                "metadata": request.metadata,
                "context": request.context,
                "evidence": request.evidence,
                "source": request.source,
                "created_by": request.created_by
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return KnowledgeEdgeResponse(
            id=response.data.get("edge_id"),
            source_id=request.source_id,
            target_id=request.target_id,
            edge_type=request.edge_type,
            weight=request.weight,
            confidence=request.confidence,
            strength=request.strength,
            bidirectional=request.bidirectional,
            label=request.label,
            description=request.description,
            properties=request.properties,
            metadata=request.metadata,
            context=request.context,
            evidence=request.evidence,
            source=request.source,
            created_by=request.created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Edge creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Edge creation failed: {str(e)}")

@knowledge_router.get("/edges/{edge_id}", response_model=KnowledgeEdgeResponse)
async def get_edge(
    edge_id: str = Path(..., description="Edge ID"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get a knowledge edge by ID."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.SEARCH,
            target="edge",
            parameters={
                "query": f"id:{edge_id}",
                "top_k": 1
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success or not response.data.get("results"):
            raise HTTPException(status_code=404, detail="Edge not found")
        
        # Get first result
        edge_data = response.data["results"][0]
        
        return KnowledgeEdgeResponse(**edge_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Edge retrieval failed", error=str(e), edge_id=edge_id)
        raise HTTPException(status_code=500, detail=f"Edge retrieval failed: {str(e)}")

@knowledge_router.delete("/edges/{edge_id}")
async def delete_edge(
    edge_id: str = Path(..., description="Edge ID"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Delete a knowledge edge."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.REMOVE,
            target="edge",
            parameters={
                "id": edge_id
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        return {"message": "Edge deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Edge deletion failed", error=str(e), edge_id=edge_id)
        raise HTTPException(status_code=500, detail=f"Edge deletion failed: {str(e)}")

# Graph endpoints
@knowledge_router.post("/graphs", response_model=KnowledgeGraphResponse)
async def create_graph(
    request: GraphCreateRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Create a knowledge graph."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.ADD,
            target="graph",
            parameters={
                "name": request.name,
                "description": request.description,
                "graph_type": request.graph_type,
                "root_node_id": request.root_node_id,
                "metadata": request.metadata,
                "configuration": request.configuration,
                "tags": request.tags
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return KnowledgeGraphResponse(
            id=response.data.get("graph_id"),
            name=request.name,
            description=request.description,
            graph_type=request.graph_type,
            root_node_id=request.root_node_id,
            metadata=request.metadata,
            configuration=request.configuration,
            tags=request.tags,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Graph creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Graph creation failed: {str(e)}")

@knowledge_router.get("/graphs/{graph_id}", response_model=KnowledgeGraphResponse)
async def get_graph(
    graph_id: str = Path(..., description="Graph ID"),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get a knowledge graph by ID."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.SEARCH,
            target="graph",
            parameters={
                "query": f"id:{graph_id}",
                "top_k": 1
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success or not response.data.get("results"):
            raise HTTPException(status_code=404, detail="Graph not found")
        
        # Get first result
        graph_data = response.data["results"][0]
        
        return KnowledgeGraphResponse(**graph_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Graph retrieval failed", error=str(e), graph_id=graph_id)
        raise HTTPException(status_code=500, detail=f"Graph retrieval failed: {str(e)}")

# Traversal endpoints
@knowledge_router.post("/traverse", response_model=TraversalResponse)
async def traverse_graph(
    request: TraversalRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Traverse knowledge graph."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.EXPLORE,
            target="graph",
            parameters={
                "start_node": request.start_node_id,
                "algorithm": request.algorithm,
                "max_depth": request.max_depth,
                "max_items": request.max_nodes,
                "include_metadata": request.include_metadata,
                "edge_types": request.edge_types
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return TraversalResponse(
            traversal_id=str(uuid.uuid4()),
            start_node_id=request.start_node_id,
            algorithm=request.algorithm,
            results=response.data,
            execution_time_ms=response.execution_time_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=response.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Graph traversal failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Graph traversal failed: {str(e)}")

# Analytics endpoints
@knowledge_router.post("/analytics", response_model=AnalyticsResponse)
async def analyze_graph(
    request: AnalyticsRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Analyze knowledge graph."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.ANALYZE,
            target="graph",
            parameters={
                "graph_id": request.graph_id,
                "analysis_type": request.analysis_type,
                "include_detailed": request.include_detailed,
                "time_range": request.time_range
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return AnalyticsResponse(
            analysis_id=str(uuid.uuid4()),
            graph_id=request.graph_id,
            analysis_type=request.analysis_type,
            results=response.data,
            execution_time_ms=response.execution_time_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=response.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Graph analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Graph analysis failed: {str(e)}")

# Batch operations endpoint
@knowledge_router.post("/batch", response_model=BatchOperationResponse)
async def batch_operations(
    request: BatchOperationRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Execute batch operations."""
    try:
        # Convert operations to knowledge requests
        knowledge_requests = []
        for op in request.operations:
            action = KnowledgeAction(op.get("action", "search"))
            target = op.get("target", "all")
            parameters = op.get("parameters", {})
            context = op.get("context")
            
            knowledge_request = KnowledgeRequest(
                action=action,
                target=target,
                parameters=parameters,
                context=context
            )
            knowledge_requests.append(knowledge_request)
        
        # Process batch
        responses = await knowledge_manager.process_batch_requests(
            requests=knowledge_requests,
            use_cache=request.use_cache
        )
        
        # Convert to API response
        results = []
        for response in responses:
            results.append({
                "success": response.success,
                "action": response.action,
                "target": response.target,
                "data": response.data,
                "message": response.message,
                "execution_time_ms": response.execution_time_ms,
                "error": response.error
            })
        
        return BatchOperationResponse(
            batch_id=str(uuid.uuid4()),
            operations_count=len(request.operations),
            successful_count=len([r for r in responses if r.success]),
            failed_count=len([r for r in responses if not r.success]),
            results=results,
            execution_time_ms=sum(r.execution_time_ms for r in responses),
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"operations": request.operations}
        )
        
    except Exception as e:
        logger.error("Batch operations failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch operations failed: {str(e)}")

# Health endpoint
@knowledge_router.get("/health", response_model=HealthResponse)
async def health_check(
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """Health check endpoint."""
    try:
        health_status = await knowledge_manager.health_check()
        
        return HealthResponse(
            status=health_status.get("status", "unknown"),
            timestamp=health_status.get("timestamp"),
            components=health_status.get("component_health", {}),
            metrics=health_status.get("stats", {}),
            details=health_status
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            components={},
            metrics={},
            details={"error": str(e)}
        )

# Export endpoint
@knowledge_router.post("/export", response_model=ExportResponse)
async def export_knowledge(
    request: ExportRequest,
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Export knowledge data."""
    try:
        # Create knowledge request
        knowledge_request = KnowledgeRequest(
            action=KnowledgeAction.EXPORT,
            target="graph",
            parameters={
                "graph_id": request.graph_id,
                "format": request.format,
                "include_metadata": request.include_metadata,
                "filters": request.filters
            }
        )
        
        # Process request
        response = await knowledge_manager.process_request(knowledge_request)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)
        
        # Convert to API response
        return ExportResponse(
            export_id=str(uuid.uuid4()),
            graph_id=request.graph_id,
            format=request.format,
            data=response.data,
            execution_time_ms=response.execution_time_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=response.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
