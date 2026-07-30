"""
CODX Graph Builder

Graph construction and management for CODX knowledge engine
with Neo4j-style operations and optimization.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import asyncio
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, func
from sqlalchemy.orm import selectinload

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class GraphBuilder:
    """
    Graph builder for CODX knowledge engine.
    
    Constructs and manages knowledge graphs with
    Neo4j-style operations and optimization.
    """
    
    def __init__(self, db_session: AsyncSession):
        """Initialize graph builder."""
        self.db_session = db_session
        self.current_graph: Optional[KnowledgeGraph] = None
        self.node_cache: Dict[str, KnowledgeNode] = {}
        self.edge_cache: Dict[str, KnowledgeEdge] = {}
        self.graph_cache: Dict[str, KnowledgeGraph] = {}
        self.building_stats = {
            "nodes_created": 0,
            "edges_created": 0,
            "nodes_updated": 0,
            "edges_updated": 0,
            "errors": 0
        }
    
    async def create_graph(
        self,
        name: str,
        graph_type: GraphType,
        description: Optional[str] = None,
        root_node_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> KnowledgeGraph:
        """
        Create a new knowledge graph.
        
        Args:
            name: Graph name
            graph_type: Type of graph
            description: Graph description
            root_node_id: Root node ID
            metadata: Graph metadata
            configuration: Graph configuration
            tags: Graph tags
            
        Returns:
            Created KnowledgeGraph instance
        """
        try:
            # Create graph instance
            graph = KnowledgeGraph(
                name=name,
                description=description,
                graph_type=graph_type,
                status=GraphStatus.BUILDING,
                root_node_id=uuid.UUID(root_node_id) if root_node_id else None,
                metadata=metadata or {},
                configuration=configuration or {},
                tags=tags or []
            )
            
            # Save to database
            self.db_session.add(graph)
            await self.db_session.commit()
            await self.db_session.refresh(graph)
            
            # Set as current graph
            self.current_graph = graph
            self.graph_cache[str(graph.id)] = graph
            
            logger.info(
                "Knowledge graph created",
                graph_id=str(graph.id),
                name=name,
                graph_type=graph_type
            )
            
            return graph
            
        except Exception as e:
            logger.error(
                "Failed to create knowledge graph",
                error=str(e),
                name=name,
                graph_type=graph_type
            )
            raise BaseLayerError(f"Graph creation failed: {str(e)}") from e
    
    async def add_node(
        self,
        title: str,
        node_type: NodeType,
        content: Optional[str] = None,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        root_id: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        tags: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        source_url: Optional[str] = None,
        author: Optional[str] = None,
        created_by: Optional[str] = None,
        confidence_score: float = 1.0,
        quality_score: float = 1.0,
        relevance_score: float = 1.0
    ) -> KnowledgeNode:
        """
        Add a node to the current graph.
        
        Args:
            title: Node title
            node_type: Type of node
            content: Node content
            description: Node description
            parent_id: Parent node ID
            root_id: Root node ID
            keywords: Node keywords
            tags: Node tags
            metadata: Node metadata
            source: Source system
            source_url: Source URL
            author: Node author
            created_by: Creator
            confidence_score: Confidence score
            quality_score: Quality score
            relevance_score: Relevance score
            
        Returns:
            Created KnowledgeNode instance
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to add node to")
            
            # Create node instance
            node = KnowledgeNode(
                title=title,
                node_type=node_type,
                content=content,
                description=description,
                parent_id=uuid.UUID(parent_id) if parent_id else None,
                root_id=uuid.UUID(root_id) if root_id else None,
                keywords=keywords or [],
                tags=tags or {},
                metadata=metadata or {},
                source=source,
                source_url=source_url,
                author=author,
                created_by=created_by,
                confidence_score=confidence_score,
                quality_score=quality_score,
                relevance_score=relevance_score
            )
            
            # Set level and path
            if parent_id:
                parent_node = await self.get_node(parent_id)
                if parent_node:
                    node.level = parent_node.level + 1
                    node.path = f"{parent_node.path}/{node.id}" if parent_node.path else str(node.id)
                else:
                    node.level = 1
                    node.path = str(node.id)
            else:
                node.level = 0
                node.path = str(node.id)
            
            # Save to database
            self.db_session.add(node)
            await self.db_session.commit()
            await self.db_session.refresh(node)
            
            # Update graph statistics
            self.current_graph.add_node(node.id)
            self.current_graph.update_statistics()
            await self.db_session.commit()
            
            # Update cache
            self.node_cache[str(node.id)] = node
            self.building_stats["nodes_created"] += 1
            
            logger.info(
                "Node added to graph",
                graph_id=str(self.current_graph.id),
                node_id=str(node.id),
                title=title,
                node_type=node_type
            )
            
            return node
            
        except Exception as e:
            logger.error(
                "Failed to add node to graph",
                error=str(e),
                title=title,
                node_type=node_type
            )
            self.building_stats["errors"] += 1
            raise BaseLayerError(f"Node addition failed: {str(e)}") from e
    
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        confidence: float = 1.0,
        strength: float = 1.0,
        bidirectional: bool = False,
        label: Optional[str] = None,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None,
        evidence: Optional[str] = None,
        source: Optional[str] = None,
        created_by: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None
    ) -> KnowledgeEdge:
        """
        Add an edge to the current graph.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of edge
            weight: Edge weight
            confidence: Edge confidence
            strength: Edge strength
            bidirectional: Whether edge is bidirectional
            label: Edge label
            description: Edge description
            properties: Edge properties
            metadata: Edge metadata
            context: Edge context
            evidence: Edge evidence
            source: Edge source
            created_by: Edge creator
            valid_from: Valid from date
            valid_to: Valid to date
            
        Returns:
            Created KnowledgeEdge instance
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to add edge to")
            
            # Verify nodes exist
            source_node = await self.get_node(source_id)
            target_node = await self.get_node(target_id)
            
            if not source_node:
                raise BaseLayerError(f"Source node not found: {source_id}")
            
            if not target_node:
                raise BaseLayerError(f"Target node not found: {target_id}")
            
            # Create edge instance
            edge = KnowledgeEdge(
                source_id=uuid.UUID(source_id),
                target_id=uuid.UUID(target_id),
                edge_type=edge_type,
                weight=weight,
                confidence=confidence,
                strength=strength,
                bidirectional=bidirectional,
                label=label,
                description=description,
                properties=properties or {},
                metadata=metadata or {},
                context=context,
                evidence=evidence,
                source=source,
                created_by=created_by,
                valid_from=valid_from,
                valid_to=valid_to
            )
            
            # Save to database
            self.db_session.add(edge)
            await self.db_session.commit()
            await self.db_session.refresh(edge)
            
            # Update graph statistics
            self.current_graph.add_edge(edge.id)
            self.current_graph.update_statistics()
            await self.db_session.commit()
            
            # Update cache
            self.edge_cache[str(edge.id)] = edge
            self.building_stats["edges_created"] += 1
            
            logger.info(
                "Edge added to graph",
                graph_id=str(self.current_graph.id),
                edge_id=str(edge.id),
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type
            )
            
            return edge
            
        except Exception as e:
            logger.error(
                "Failed to add edge to graph",
                error=str(e),
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type
            )
            self.building_stats["errors"] += 1
            raise BaseLayerError(f"Edge addition failed: {str(e)}") from e
    
    async def update_node(
        self,
        node_id: str,
        updates: Dict[str, Any]
    ) -> KnowledgeNode:
        """
        Update an existing node in the current graph.
        
        Args:
            node_id: Node ID to update
            updates: Dictionary of updates
            
        Returns:
            Updated KnowledgeNode instance
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to update node in")
            
            # Get existing node
            node = await self.get_node(node_id)
            if not node:
                raise BaseLayerError(f"Node not found: {node_id}")
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(node, field):
                    setattr(node, field, value)
            
            # Update timestamp
            node.updated_at = datetime.now(timezone.utc)
            node.increment_update_count()
            
            # Save to database
            await self.db_session.commit()
            await self.db_session.refresh(node)
            
            # Update cache
            self.node_cache[str(node.id)] = node
            self.building_stats["nodes_updated"] += 1
            
            logger.info(
                "Node updated in graph",
                graph_id=str(self.current_graph.id),
                node_id=str(node.id),
                updates=list(updates.keys())
            )
            
            return node
            
        except Exception as e:
            logger.error(
                "Failed to update node in graph",
                error=str(e),
                node_id=node_id,
                updates=updates
            )
            self.building_stats["errors"] += 1
            raise BaseLayerError(f"Node update failed: {str(e)}") from e
    
    async def update_edge(
        self,
        edge_id: str,
        updates: Dict[str, Any]
    ) -> KnowledgeEdge:
        """
        Update an existing edge in the current graph.
        
        Args:
            edge_id: Edge ID to update
            updates: Dictionary of updates
            
        Returns:
            Updated KnowledgeEdge instance
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to update edge in")
            
            # Get existing edge
            edge = await self.get_edge(edge_id)
            if not edge:
                raise BaseLayerError(f"Edge not found: {edge_id}")
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(edge, field):
                    setattr(edge, field, value)
            
            # Update timestamp
            edge.updated_at = datetime.now(timezone.utc)
            edge.increment_update_count()
            
            # Save to database
            await self.db_session.commit()
            await self.db_session.refresh(edge)
            
            # Update cache
            self.edge_cache[str(edge.id)] = edge
            self.building_stats["edges_updated"] += 1
            
            logger.info(
                "Edge updated in graph",
                graph_id=str(self.current_graph.id),
                edge_id=str(edge.id),
                updates=list(updates.keys())
            )
            
            return edge
            
        except Exception as e:
            logger.error(
                "Failed to update edge in graph",
                error=str(e),
                edge_id=edge_id,
                updates=updates
            )
            self.building_stats["errors"] += 1
            raise BaseLayerError(f"Edge update failed: {str(e)}") from e
    
    async def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """
        Get a node by ID.
        
        Args:
            node_id: Node ID
            
        Returns:
            KnowledgeNode instance or None
        """
        try:
            # Check cache first
            if node_id in self.node_cache:
                return self.node_cache[node_id]
            
            # Query database
            query = select(KnowledgeNode).where(KnowledgeNode.id == uuid.UUID(node_id))
            result = await self.db_session.execute(query)
            node = result.scalar_one_or_none()
            
            if node:
                self.node_cache[node_id] = node
            
            return node
            
        except Exception as e:
            logger.error(
                "Failed to get node",
                error=str(e),
                node_id=node_id
            )
            return None
    
    async def get_edge(self, edge_id: str) -> Optional[KnowledgeEdge]:
        """
        Get an edge by ID.
        
        Args:
            edge_id: Edge ID
            
        Returns:
            KnowledgeEdge instance or None
        """
        try:
            # Check cache first
            if edge_id in self.edge_cache:
                return self.edge_cache[edge_id]
            
            # Query database
            query = select(KnowledgeEdge).where(KnowledgeEdge.id == uuid.UUID(edge_id))
            result = await self.db_session.execute(query)
            edge = result.scalar_one_or_none()
            
            if edge:
                self.edge_cache[edge_id] = edge
            
            return edge
            
        except Exception as e:
            logger.error(
                "Failed to get edge",
                error=str(e),
                edge_id=edge_id
            )
            return None
    
    async def get_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """
        Get a graph by ID.
        
        Args:
            graph_id: Graph ID
            
        Returns:
            KnowledgeGraph instance or None
        """
        try:
            # Check cache first
            if graph_id in self.graph_cache:
                return self.graph_cache[graph_id]
            
            # Query database with relationships
            query = select(KnowledgeGraph).options(
                selectinload(KnowledgeGraph.nodes),
                selectinload(KnowledgeGraph.edges)
            ).where(KnowledgeGraph.id == uuid.UUID(graph_id))
            
            result = await self.db_session.execute(query)
            graph = result.scalar_one_or_none()
            
            if graph:
                self.graph_cache[graph_id] = graph
                self.current_graph = graph
            
            return graph
            
        except Exception as e:
            logger.error(
                "Failed to get graph",
                error=str(e),
                graph_id=graph_id
            )
            return None
    
    async def list_nodes(
        self,
        graph_id: Optional[str] = None,
        node_types: Optional[List[NodeType]] = None,
        status: Optional[List[NodeStatus]] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeNode]:
        """
        List nodes in a graph.
        
        Args:
            graph_id: Graph ID (uses current if None)
            node_types: Filter by node types
            status: Filter by status
            keywords: Filter by keywords
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of KnowledgeNode instances
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return []
            
            # Build query
            query = select(KnowledgeNode).where(KnowledgeNode.root_id == uuid.UUID(target_graph_id))
            
            # Add filters
            if node_types:
                query = query.where(KnowledgeNode.node_type.in_(node_types))
            
            if status:
                query = query.where(KnowledgeNode.status.in_(status))
            
            if keywords:
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append(KnowledgeNode.keywords.any(keyword))
                query = query.where(or_(*keyword_conditions))
            
            # Add ordering and pagination
            query = query.order_by(desc(KnowledgeNode.created_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db_session.execute(query)
            nodes = result.scalars().all()
            
            return nodes
            
        except Exception as e:
            logger.error(
                "Failed to list nodes",
                error=str(e),
                graph_id=graph_id
            )
            return []
    
    async def list_edges(
        self,
        graph_id: Optional[str] = None,
        edge_types: Optional[List[EdgeType]] = None,
        status: Optional[List[EdgeStatus]] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeEdge]:
        """
        List edges in a graph.
        
        Args:
            graph_id: Graph ID (uses current if None)
            edge_types: Filter by edge types
            status: Filter by status
            source_id: Filter by source node ID
            target_id: Filter by target node ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of KnowledgeEdge instances
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return []
            
            # Build query with joins to nodes
            query = select(KnowledgeEdge).join(KnowledgeNode, KnowledgeEdge.source_id == KnowledgeNode.id).where(
                KnowledgeNode.root_id == uuid.UUID(target_graph_id)
            )
            
            # Add filters
            if edge_types:
                query = query.where(KnowledgeEdge.edge_type.in_(edge_types))
            
            if status:
                query = query.where(KnowledgeEdge.status.in_(status))
            
            if source_id:
                query = query.where(KnowledgeEdge.source_id == uuid.UUID(source_id))
            
            if target_id:
                query = query.where(KnowledgeEdge.target_id == uuid.UUID(target_id))
            
            # Add ordering and pagination
            query = query.order_by(desc(KnowledgeEdge.created_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db_session.execute(query)
            edges = result.scalars().all()
            
            return edges
            
        except Exception as e:
            logger.error(
                "Failed to list edges",
                error=str(e),
                graph_id=graph_id
            )
            return []
    
    async def delete_node(self, node_id: str) -> bool:
        """
        Delete a node from the current graph.
        
        Args:
            node_id: Node ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to delete node from")
            
            # Get node
            node = await self.get_node(node_id)
            if not node:
                return False
            
            # Archive node (soft delete)
            node.archive()
            await self.db_session.commit()
            
            # Update graph statistics
            self.current_graph.remove_node(node.id)
            self.current_graph.update_statistics()
            await self.db_session.commit()
            
            # Update cache
            if node_id in self.node_cache:
                del self.node_cache[node_id]
            
            logger.info(
                "Node deleted from graph",
                graph_id=str(self.current_graph.id),
                node_id=str(node.id)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete node from graph",
                error=str(e),
                node_id=node_id
            )
            return False
    
    async def delete_edge(self, edge_id: str) -> bool:
        """
        Delete an edge from the current graph.
        
        Args:
            edge_id: Edge ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if not self.current_graph:
                raise BaseLayerError("No active graph to delete edge from")
            
            # Get edge
            edge = await self.get_edge(edge_id)
            if not edge:
                return False
            
            # Archive edge (soft delete)
            edge.archive()
            await self.db_session.commit()
            
            # Update graph statistics
            self.current_graph.remove_edge(edge.id)
            self.current_graph.update_statistics()
            await self.db_session.commit()
            
            # Update cache
            if edge_id in self.edge_cache:
                del self.edge_cache[edge_id]
            
            logger.info(
                "Edge deleted from graph",
                graph_id=str(self.current_graph.id),
                edge_id=str(edge.id)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete edge from graph",
                error=str(e),
                edge_id=edge_id
            )
            return False
    
    async def activate_graph(self, graph_id: str) -> bool:
        """
        Activate a graph.
        
        Args:
            graph_id: Graph ID to activate
            
        Returns:
            True if activated successfully
        """
        try:
            graph = await self.get_graph(graph_id)
            if not graph:
                return False
            
            graph.activate()
            await self.db_session.commit()
            
            # Update cache
            if graph_id in self.graph_cache:
                self.graph_cache[graph_id] = graph
            
            logger.info(
                "Graph activated",
                graph_id=graph_id
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to activate graph",
                error=str(e),
                graph_id=graph_id
            )
            return False
    
    async def deactivate_graph(self, graph_id: str) -> bool:
        """
        Deactivate a graph.
        
        Args:
            graph_id: Graph ID to deactivate
            
        Returns:
            True if deactivated successfully
        """
        try:
            graph = await self.get_graph(graph_id)
            if not graph:
                return False
            
            graph.deactivate()
            await self.db_session.commit()
            
            # Update cache
            if graph_id in self.graph_cache:
                self.graph_cache[graph_id] = graph
            
            logger.info(
                "Graph deactivated",
                graph_id=graph_id
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to deactivate graph",
                error=str(e),
                graph_id=graph_id
            )
            return False
    
    async def get_graph_statistics(self, graph_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for a graph.
        
        Args:
            graph_id: Graph ID (uses current if None)
            
        Returns:
            Dictionary of graph statistics
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return {}
            
            graph = await self.get_graph(target_graph_id)
            if not graph:
                return {}
            
            # Update statistics
            graph.update_statistics()
            await self.db_session.commit()
            
            return graph.get_statistics()
            
        except Exception as e:
            logger.error(
                "Failed to get graph statistics",
                error=str(e),
                graph_id=graph_id
            )
            return {}
    
    async def validate_graph_structure(self, graph_id: Optional[str] = None) -> List[str]:
        """
        Validate graph structure and return errors.
        
        Args:
            graph_id: Graph ID (uses current if None)
            
        Returns:
            List of validation errors
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return ["No graph specified"]
            
            graph = await self.get_graph(target_graph_id)
            if not graph:
                return ["Graph not found"]
            
            # Validate graph structure
            errors = graph.validate_structure()
            
            # Additional validation checks
            if graph.node_count == 0:
                errors.append("Graph has no nodes")
            
            if graph.edge_count == 0 and graph.node_count > 1:
                errors.append("Graph has multiple nodes but no edges")
            
            # Check for orphaned nodes
            nodes = await self.list_nodes(target_graph_id, limit=1000)
            orphaned_count = 0
            
            for node in nodes:
                if node.parent_id is None and str(node.id) != graph.root_node_id:
                    orphaned_count += 1
            
            if orphaned_count > 0:
                errors.append(f"Graph has {orphaned_count} orphaned nodes")
            
            return errors
            
        except Exception as e:
            logger.error(
                "Failed to validate graph structure",
                error=str(e),
                graph_id=graph_id
            )
            return [f"Validation error: {str(e)}"]
    
    async def optimize_graph(self, graph_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Optimize graph structure and performance.
        
        Args:
            graph_id: Graph ID (uses current if None)
            
        Returns:
            Dictionary of optimization results
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return {"error": "No graph specified"}
            
            # Get graph and nodes
            graph = await self.get_graph(target_graph_id)
            if not graph:
                return {"error": "Graph not found"}
            
            nodes = await self.list_nodes(target_graph_id, limit=1000)
            edges = await self.list_edges(target_graph_id, limit=1000)
            
            optimization_results = {
                "original_stats": {
                    "nodes": len(nodes),
                    "edges": len(edges),
                    "density": graph.density
                },
                "optimizations": [],
                "performance_improvements": {},
                "recommendations": []
            }
            
            # Check for duplicate edges
            edge_pairs = set()
            duplicate_count = 0
            
            for edge in edges:
                pair = (str(edge.source_id), str(edge.target_id))
                if pair in edge_pairs:
                    duplicate_count += 1
                    optimization_results["optimizations"].append({
                        "type": "duplicate_edge",
                        "edge_id": str(edge.id),
                        "source": str(edge.source_id),
                        "target": str(edge.target_id)
                    })
                else:
                    edge_pairs.add(pair)
            
            if duplicate_count > 0:
                optimization_results["performance_improvements"]["duplicate_edges_removed"] = duplicate_count
                optimization_results["recommendations"].append(f"Remove {duplicate_count} duplicate edges")
            
            # Check for isolated nodes
            node_connections = {str(node.id): set() for node in nodes}
            
            for edge in edges:
                node_connections[str(edge.source_id)].add(str(edge.target_id))
                if edge.bidirectional:
                    node_connections[str(edge.target_id)].add(str(edge.source_id))
            
            isolated_count = 0
            for node_id, connections in node_connections.items():
                if len(connections) == 0:
                    isolated_count += 1
                    optimization_results["optimizations"].append({
                        "type": "isolated_node",
                        "node_id": node_id
                    })
            
            if isolated_count > 0:
                optimization_results["performance_improvements"]["isolated_nodes"] = isolated_count
                optimization_results["recommendations"].append(f"Connect {isolated_count} isolated nodes")
            
            # Calculate potential density improvement
            current_density = graph.density
            max_possible_edges = len(nodes) * (len(nodes) - 1)
            max_density = 1.0 if len(nodes) > 1 else 0.0
            
            optimization_results["performance_improvements"]["density_improvement"] = max_density - current_density
            
            return optimization_results
            
        except Exception as e:
            logger.error(
                "Failed to optimize graph",
                error=str(e),
                graph_id=graph_id
            )
            return {"error": f"Optimization failed: {str(e)}"}
    
    async def export_graph(
        self,
        graph_id: Optional[str] = None,
        format: str = "json",
        include_embeddings: bool = False,
        include_metadata: bool = True,
        max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export graph data.
        
        Args:
            graph_id: Graph ID (uses current if None)
            format: Export format (json, csv, neo4j, graphml)
            include_embeddings: Include embedding data
            include_metadata: Include metadata
            max_depth: Maximum depth to export
            
        Returns:
            Export data dictionary
        """
        try:
            # Use current graph if not specified
            target_graph_id = graph_id or (str(self.current_graph.id) if self.current_graph else None)
            
            if not target_graph_id:
                return {"error": "No graph specified"}
            
            graph = await self.get_graph(target_graph_id)
            if not graph:
                return {"error": "Graph not found"}
            
            # Get nodes and edges
            nodes = await self.list_nodes(target_graph_id, limit=10000)
            edges = await self.list_edges(target_graph_id, limit=10000)
            
            # Filter by depth if specified
            if max_depth is not None:
                nodes = [node for node in nodes if node.level <= max_depth]
            
            export_data = {
                "graph_id": target_graph_id,
                "format": format,
                "nodes": [],
                "edges": [],
                "metadata": {
                    "name": graph.name,
                    "type": graph.graph_type,
                    "created_at": graph.created_at.isoformat() if graph.created_at else None,
                    "exported_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Export nodes
            for node in nodes:
                node_data = {
                    "id": str(node.id),
                    "title": node.title,
                    "description": node.description,
                    "node_type": node.node_type,
                    "status": node.status,
                    "level": node.level,
                    "path": node.path,
                    "confidence_score": node.confidence_score,
                    "quality_score": node.quality_score,
                    "relevance_score": node.relevance_score,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                    "updated_at": node.updated_at.isoformat() if node.updated_at else None
                }
                
                if include_metadata:
                    node_data["keywords"] = node.keywords or []
                    node_data["tags"] = node.tags or {}
                    node_data["metadata"] = node.metadata or {}
                    node_data["source"] = node.source
                    node_data["source_url"] = node.source_url
                    node_data["author"] = node.author
                    node_data["created_by"] = node.created_by
                    node_data["access_count"] = node.access_count
                    node_data["update_count"] = node.update_count
                    node_data["last_accessed"] = node.last_accessed.isoformat() if node.last_accessed else None
                
                if include_embeddings:
                    node_data["embedding_id"] = str(node.embedding_id) if node.embedding_id else None
                    node_data["embedding_model"] = node.embedding_model
                    node_data["embedding_dimension"] = node.embedding_dimension
                
                export_data["nodes"].append(node_data)
            
            # Export edges
            for edge in edges:
                edge_data = {
                    "id": str(edge.id),
                    "source_id": str(edge.source_id),
                    "target_id": str(edge.target_id),
                    "edge_type": edge.edge_type,
                    "status": edge.status,
                    "weight": edge.weight,
                    "confidence": edge.confidence,
                    "strength": edge.strength,
                    "bidirectional": edge.bidirectional,
                    "label": edge.label,
                    "description": edge.description,
                    "created_at": edge.created_at.isoformat() if edge.created_at else None,
                    "updated_at": edge.updated_at.isoformat() if edge.updated_at else None
                }
                
                if include_metadata:
                    edge_data["properties"] = edge.properties or {}
                    edge_data["metadata"] = edge.metadata or {}
                    edge_data["context"] = edge.context
                    edge_data["evidence"] = edge.evidence
                    edge_data["source"] = edge.source
                    edge_data["created_by"] = edge.created_by
                    edge_data["access_count"] = edge.access_count
                    edge_data["update_count"] = edge.update_count
                    edge_data["last_accessed"] = edge.last_accessed.isoformat() if edge.last_accessed else None
                
                if edge.valid_from:
                    edge_data["valid_from"] = edge.valid_from.isoformat()
                
                if edge.valid_to:
                    edge_data["valid_to"] = edge.valid_to.isoformat()
                
                export_data["edges"].append(edge_data)
            
            # Format-specific processing
            if format == "csv":
                # Convert to CSV format
                export_data["nodes_csv"] = self._convert_nodes_to_csv(nodes)
                export_data["edges_csv"] = self._convert_edges_to_csv(edges)
            elif format == "neo4j":
                # Convert to Neo4j format
                export_data["neo4j"] = self._convert_to_neo4j(graph, nodes, edges)
            elif format == "graphml":
                # Convert to GraphML format
                export_data["graphml"] = self._convert_to_graphml(graph, nodes, edges)
            
            return export_data
            
        except Exception as e:
            logger.error(
                "Failed to export graph",
                error=str(e),
                graph_id=graph_id,
                format=format
            )
            return {"error": f"Export failed: {str(e)}"}
    
    def _convert_nodes_to_csv(self, nodes: List[KnowledgeNode]) -> str:
        """Convert nodes to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id", "title", "description", "node_type", "status",
            "level", "path", "confidence_score", "quality_score",
            "relevance_score", "created_at", "updated_at"
        ])
        
        # Write rows
        for node in nodes:
            writer.writerow([
                str(node.id),
                node.title,
                node.description or "",
                node.node_type,
                node.status,
                node.level,
                node.path or "",
                node.confidence_score,
                node.quality_score,
                node.relevance_score,
                node.created_at.isoformat() if node.created_at else "",
                node.updated_at.isoformat() if node.updated_at else ""
            ])
        
        return output.getvalue()
    
    def _convert_edges_to_csv(self, edges: List[KnowledgeEdge]) -> str:
        """Convert edges to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id", "source_id", "target_id", "edge_type", "status",
            "weight", "confidence", "strength", "bidirectional",
            "label", "description", "created_at", "updated_at"
        ])
        
        # Write rows
        for edge in edges:
            writer.writerow([
                str(edge.id),
                str(edge.source_id),
                str(edge.target_id),
                edge.edge_type,
                edge.status,
                edge.weight,
                edge.confidence,
                edge.strength,
                edge.bidirectional,
                edge.label or "",
                edge.description or "",
                edge.created_at.isoformat() if edge.created_at else "",
                edge.updated_at.isoformat() if edge.updated_at else ""
            ])
        
        return output.getvalue()
    
    def _convert_to_neo4j(self, graph: KnowledgeGraph, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> str:
        """Convert to Neo4j format."""
        neo4j_data = {
            "nodes": [],
            "relationships": []
        }
        
        # Convert nodes
        for node in nodes:
            neo4j_data["nodes"].append({
                "id": str(node.id),
                "labels": [node.node_type],
                "properties": {
                    "title": node.title,
                    "description": node.description,
                    "status": node.status,
                    "level": node.level,
                    "path": node.path,
                    "confidence_score": node.confidence_score,
                    "quality_score": node.quality_score,
                    "relevance_score": node.relevance_score,
                    "keywords": node.keywords or [],
                    "tags": node.tags or {},
                    "metadata": node.metadata or {},
                    "source": node.source,
                    "source_url": node.source_url,
                    "author": node.author,
                    "created_by": node.created_by,
                    "access_count": node.access_count,
                    "update_count": node.update_count,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                    "updated_at": node.updated_at.isoformat() if node.updated_at else None
                }
            })
        
        # Convert edges
        for edge in edges:
            neo4j_data["relationships"].append({
                "id": str(edge.id),
                "type": edge.edge_type,
                "startNode": str(edge.source_id),
                "endNode": str(edge.target_id),
                "properties": {
                    "weight": edge.weight,
                    "confidence": edge.confidence,
                    "strength": edge.strength,
                    "bidirectional": edge.bidirectional,
                    "label": edge.label,
                    "description": edge.description,
                    "properties": edge.properties or {},
                    "metadata": edge.metadata or {},
                    "context": edge.context,
                    "evidence": edge.evidence,
                    "source": edge.source,
                    "created_by": edge.created_by,
                    "access_count": edge.access_count,
                    "update_count": edge.update_count,
                    "created_at": edge.created_at.isoformat() if edge.created_at else None,
                    "updated_at": edge.updated_at.isoformat() if edge.updated_at else None
                }
            })
        
        return json.dumps(neo4j_data, indent=2)
    
    def _convert_to_graphml(self, graph: KnowledgeGraph, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> str:
        """Convert to GraphML format."""
        # GraphML header
        graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns 
         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="title" for="node" attr.name="title" attr.type="string"/>
  <key id="description" for="node" attr.name="description" attr.type="string"/>
  <key id="node_type" for="node" attr.name="node_type" attr.type="string"/>
  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>
  <key id="confidence" for="edge" attr.name="confidence" attr.type="double"/>
  <key id="strength" for="edge" attr.name="strength" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
'''
        
        # Add nodes
        for node in nodes:
            graphml += f'''
    <node id="{node.id}">
      <data key="title">{node.title}</data>
      <data key="description">{node.description or ""}</data>
      <data key="node_type">{node.node_type}</data>
    </node>'''
        
        # Add edges
        for edge in edges:
            graphml += f'''
    <edge source="{edge.source_id}" target="{edge.target_id}">
      <data key="weight">{edge.weight}</data>
      <data key="confidence">{edge.confidence}</data>
      <data key="strength">{edge.strength}</data>
    </edge>'''
        
        graphml += '''
  </graph>
</graphml>'''
        
        return graphml
    
    def get_building_stats(self) -> Dict[str, Any]:
        """Get current building statistics."""
        return {
            "nodes_created": self.building_stats["nodes_created"],
            "edges_created": self.building_stats["edges_created"],
            "nodes_updated": self.building_stats["nodes_updated"],
            "edges_updated": self.building_stats["edges_updated"],
            "errors": self.building_stats["errors"],
            "cache_size": {
                "nodes": len(self.node_cache),
                "edges": len(self.edge_cache),
                "graphs": len(self.graph_cache)
            }
        }
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self.node_cache.clear()
        self.edge_cache.clear()
        self.graph_cache.clear()
        
        logger.info(
            "Graph builder cache cleared",
            cache_size=self.get_building_stats()["cache_size"]
        )
    
    async def set_current_graph(self, graph_id: str) -> bool:
        """
        Set the current working graph.
        
        Args:
            graph_id: Graph ID to set as current
            
        Returns:
            True if set successfully
        """
        try:
            graph = await self.get_graph(graph_id)
            if graph:
                self.current_graph = graph
                logger.info(
                    "Current graph set",
                    graph_id=graph_id,
                    graph_name=graph.name
                )
                return True
            return False
            
        except Exception as e:
            logger.error(
                "Failed to set current graph",
                error=str(e),
                graph_id=graph_id
            )
            return False
