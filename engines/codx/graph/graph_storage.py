"""
CODX Graph Storage

Graph storage and persistence for CODX knowledge engine
with database operations and caching.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import asyncio
import json
import pickle

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, func, update, delete
from sqlalchemy.orm import selectinload

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class GraphStorage:
    """
    Graph storage manager for CODX knowledge engine.
    
    Handles database operations, caching, and
    persistence for knowledge graphs, nodes, and edges.
    """
    
    def __init__(self, db_session: AsyncSession, cache_size: int = 1000):
        """Initialize graph storage."""
        self.db_session = db_session
        self.cache_size = cache_size
        
        # Caches
        self.graph_cache: Dict[str, KnowledgeGraph] = {}
        self.node_cache: Dict[str, KnowledgeNode] = {}
        self.edge_cache: Dict[str, KnowledgeEdge] = {}
        self.graph_metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # Cache timestamps
        self.graph_cache_timestamps: Dict[str, datetime] = {}
        self.node_cache_timestamps: Dict[str, datetime] = {}
        self.edge_cache_timestamps: Dict[str, datetime] = {}
        
        # Performance metrics
        self.storage_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "db_operations": 0,
            "cache_evictions": 0,
            "total_operations": 0
        }
    
    async def save_graph(self, graph: KnowledgeGraph) -> KnowledgeGraph:
        """
        Save a knowledge graph to database.
        
        Args:
            graph: KnowledgeGraph instance to save
            
        Returns:
            Saved KnowledgeGraph instance
        """
        try:
            # Check if graph exists
            existing_graph = await self.get_graph(str(graph.id))
            
            if existing_graph:
                # Update existing graph
                await self._update_graph_in_db(graph)
                self.storage_stats["db_operations"] += 1
            else:
                # Insert new graph
                self.db_session.add(graph)
                await self.db_session.commit()
                await self.db_session.refresh(graph)
                self.storage_stats["db_operations"] += 1
            
            # Update cache
            self._cache_graph(graph)
            
            logger.info(
                "Graph saved to database",
                graph_id=str(graph.id),
                graph_name=graph.name,
                graph_type=graph.graph_type
            )
            
            return graph
            
        except Exception as e:
            logger.error(
                "Failed to save graph to database",
                error=str(e),
                graph_id=str(graph.id)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"Graph save failed: {str(e)}") from e
    
    async def save_node(self, node: KnowledgeNode) -> KnowledgeNode:
        """
        Save a knowledge node to database.
        
        Args:
            node: KnowledgeNode instance to save
            
        Returns:
            Saved KnowledgeNode instance
        """
        try:
            # Check if node exists
            existing_node = await self.get_node(str(node.id))
            
            if existing_node:
                # Update existing node
                await self._update_node_in_db(node)
                self.storage_stats["db_operations"] += 1
            else:
                # Insert new node
                self.db_session.add(node)
                await self.db_session.commit()
                await self.db_session.refresh(node)
                self.storage_stats["db_operations"] += 1
            
            # Update cache
            self._cache_node(node)
            
            logger.info(
                "Node saved to database",
                node_id=str(node.id),
                node_title=node.title,
                node_type=node.node_type
            )
            
            return node
            
        except Exception as e:
            logger.error(
                "Failed to save node to database",
                error=str(e),
                node_id=str(node.id)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"Node save failed: {str(e)}") from e
    
    async def save_edge(self, edge: KnowledgeEdge) -> KnowledgeEdge:
        """
        Save a knowledge edge to database.
        
        Args:
            edge: KnowledgeEdge instance to save
            
        Returns:
            Saved KnowledgeEdge instance
        """
        try:
            # Check if edge exists
            existing_edge = await self.get_edge(str(edge.id))
            
            if existing_edge:
                # Update existing edge
                await self._update_edge_in_db(edge)
                self.storage_stats["db_operations"] += 1
            else:
                # Insert new edge
                self.db_session.add(edge)
                await self.db_session.commit()
                await self.db_session.refresh(edge)
                self.storage_stats["db_operations"] += 1
            
            # Update cache
            self._cache_edge(edge)
            
            logger.info(
                "Edge saved to database",
                edge_id=str(edge.id),
                edge_type=edge.edge_type,
                source_id=str(edge.source_id),
                target_id=str(edge.target_id)
            )
            
            return edge
            
        except Exception as e:
            logger.error(
                "Failed to save edge to database",
                error=str(e),
                edge_id=str(edge.id)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"Edge save failed: {str(e)}") from e
    
    async def save_nodes_batch(self, nodes: List[KnowledgeNode]) -> List[KnowledgeNode]:
        """
        Save multiple knowledge nodes to database.
        
        Args:
            nodes: List of KnowledgeNode instances to save
            
        Returns:
            List of saved KnowledgeNode instances
        """
        try:
            if not nodes:
                return []
            
            # Check which nodes already exist
            existing_node_ids = set()
            for node in nodes:
                existing_node = await self.get_node(str(node.id))
                if existing_node:
                    existing_node_ids.add(str(node.id))
            
            # Separate new and existing nodes
            new_nodes = [node for node in nodes if str(node.id) not in existing_node_ids]
            existing_nodes = [node for node in nodes if str(node.id) in existing_node_ids]
            
            # Save new nodes
            if new_nodes:
                self.db_session.add_all(new_nodes)
                await self.db_session.commit()
                self.storage_stats["db_operations"] += len(new_nodes)
            
            # Update existing nodes
            for node in existing_nodes:
                await self._update_node_in_db(node)
                self.storage_stats["db_operations"] += 1
            
            # Update cache for all nodes
            for node in nodes:
                self._cache_node(node)
            
            logger.info(
                "Batch nodes saved to database",
                total_nodes=len(nodes),
                new_nodes=len(new_nodes),
                existing_nodes=len(existing_nodes)
            )
            
            return nodes
            
        except Exception as e:
            logger.error(
                "Failed to save batch nodes to database",
                error=str(e),
                node_count=len(nodes)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"Batch node save failed: {str(e)}") from e
    
    async def save_edges_batch(self, edges: List[KnowledgeEdge]) -> List[KnowledgeEdge]:
        """
        Save multiple knowledge edges to database.
        
        Args:
            edges: List of KnowledgeEdge instances to save
            
        Returns:
            List of saved KnowledgeEdge instances
        """
        try:
            if not edges:
                return []
            
            # Check which edges already exist
            existing_edge_ids = set()
            for edge in edges:
                existing_edge = await self.get_edge(str(edge.id))
                if existing_edge:
                    existing_edge_ids.add(str(edge.id))
            
            # Separate new and existing edges
            new_edges = [edge for edge in edges if str(edge.id) not in existing_edge_ids]
            existing_edges = [edge for edge in edges if str(edge.id) in existing_edge_ids]
            
            # Save new edges
            if new_edges:
                self.db_session.add_all(new_edges)
                await self.db_session.commit()
                self.storage_stats["db_operations"] += len(new_edges)
            
            # Update existing edges
            for edge in existing_edges:
                await self._update_edge_in_db(edge)
                self.storage_stats["db_operations"] += 1
            
            # Update cache for all edges
            for edge in edges:
                self._cache_edge(edge)
            
            logger.info(
                "Batch edges saved to database",
                total_edges=len(edges),
                new_edges=len(new_edges),
                existing_edges=len(existing_edges)
            )
            
            return edges
            
        except Exception as e:
            logger.error(
                "Failed to save batch edges to database",
                error=str(e),
                edge_count=len(edges)
            )
            await self.db_session.rollback()
            raise BaseLayerError(f"Batch edge save failed: {str(e)}") from e
    
    async def get_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """
        Get a knowledge graph by ID.
        
        Args:
            graph_id: Graph ID to retrieve
            
        Returns:
            KnowledgeGraph instance or None
        """
        try:
            # Check cache first
            if graph_id in self.graph_cache:
                self.storage_stats["cache_hits"] += 1
                return self.graph_cache[graph_id]
            
            self.storage_stats["cache_misses"] += 1
            
            # Query database
            query = select(KnowledgeGraph).options(
                selectinload(KnowledgeGraph.nodes),
                selectinload(KnowledgeGraph.edges)
            ).where(KnowledgeGraph.id == uuid.UUID(graph_id))
            
            result = await self.db_session.execute(query)
            graph = result.scalar_one_or_none()
            
            if graph:
                self._cache_graph(graph)
            
            return graph
            
        except Exception as e:
            logger.error(
                "Failed to get graph from database",
                error=str(e),
                graph_id=graph_id
            )
            return None
    
    async def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """
        Get a knowledge node by ID.
        
        Args:
            node_id: Node ID to retrieve
            
        Returns:
            KnowledgeNode instance or None
        """
        try:
            # Check cache first
            if node_id in self.node_cache:
                self.storage_stats["cache_hits"] += 1
                return self.node_cache[node_id]
            
            self.storage_stats["cache_misses"] += 1
            
            # Query database
            query = select(KnowledgeNode).where(KnowledgeNode.id == uuid.UUID(node_id))
            
            result = await self.db_session.execute(query)
            node = result.scalar_one_or_none()
            
            if node:
                self._cache_node(node)
            
            return node
            
        except Exception as e:
            logger.error(
                "Failed to get node from database",
                error=str(e),
                node_id=node_id
            )
            return None
    
    async def get_edge(self, edge_id: str) -> Optional[KnowledgeEdge]:
        """
        Get a knowledge edge by ID.
        
        Args:
            edge_id: Edge ID to retrieve
            
        Returns:
            KnowledgeEdge instance or None
        """
        try:
            # Check cache first
            if edge_id in self.edge_cache:
                self.storage_stats["cache_hits"] += 1
                return self.edge_cache[edge_id]
            
            self.storage_stats["cache_misses"] += 1
            
            # Query database
            query = select(KnowledgeEdge).where(KnowledgeEdge.id == uuid.UUID(edge_id))
            
            result = await self.db_session.execute(query)
            edge = result.scalar_one_or_none()
            
            if edge:
                self._cache_edge(edge)
            
            return edge
            
        except Exception as e:
            logger.error(
                "Failed to get edge from database",
                error=str(e),
                edge_id=edge_id
            )
            return None
    
    async def list_graphs(
        self,
        graph_types: Optional[List[GraphType]] = None,
        status: Optional[List[GraphStatus]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeGraph]:
        """
        List knowledge graphs with filters.
        
        Args:
            graph_types: Filter by graph types
            status: Filter by status
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of KnowledgeGraph instances
        """
        try:
            # Build query
            query = select(KnowledgeGraph)
            
            # Add filters
            if graph_types:
                query = query.where(KnowledgeGraph.graph_type.in_(graph_types))
            
            if status:
                query = query.where(KnowledgeGraph.status.in_(status))
            
            # Add ordering and pagination
            query = query.order_by(desc(KnowledgeGraph.created_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db_session.execute(query)
            graphs = result.scalars().all()
            
            # Update cache
            for graph in graphs:
                self._cache_graph(graph)
            
            logger.info(
                "Graphs listed from database",
                graph_count=len(graphs),
                graph_types=graph_types,
                status=status
            )
            
            return graphs
            
        except Exception as e:
            logger.error(
                "Failed to list graphs from database",
                error=str(e),
                graph_types=graph_types,
                status=status
            )
            return []
    
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
        List knowledge nodes with filters.
        
        Args:
            graph_id: Filter by graph ID
            node_types: Filter by node types
            status: Filter by status
            keywords: Filter by keywords
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of KnowledgeNode instances
        """
        try:
            # Build query
            query = select(KnowledgeNode)
            
            # Add filters
            if graph_id:
                query = query.where(KnowledgeNode.root_id == uuid.UUID(graph_id))
            
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
            
            # Update cache
            for node in nodes:
                self._cache_node(node)
            
            logger.info(
                "Nodes listed from database",
                node_count=len(nodes),
                graph_id=graph_id,
                node_types=node_types
            )
            
            return nodes
            
        except Exception as e:
            logger.error(
                "Failed to list nodes from database",
                error=str(e),
                graph_id=graph_id,
                node_types=node_types
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
        List knowledge edges with filters.
        
        Args:
            graph_id: Filter by graph ID
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
            # Build query with joins
            query = select(KnowledgeEdge).join(
                KnowledgeNode, KnowledgeEdge.source_id == KnowledgeNode.id
            )
            
            # Add filters
            if graph_id:
                query = query.where(KnowledgeNode.root_id == uuid.UUID(graph_id))
            
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
            
            # Update cache
            for edge in edges:
                self._cache_edge(edge)
            
            logger.info(
                "Edges listed from database",
                edge_count=len(edges),
                graph_id=graph_id,
                edge_types=edge_types
            )
            
            return edges
            
        except Exception as e:
            logger.error(
                "Failed to list edges from database",
                error=str(e),
                graph_id=graph_id,
                edge_types=edge_types
            )
            return []
    
    async def delete_graph(self, graph_id: str) -> bool:
        """
        Delete a knowledge graph.
        
        Args:
            graph_id: Graph ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            # Get graph
            graph = await self.get_graph(graph_id)
            if not graph:
                return False
            
            # Delete from database
            query = delete(KnowledgeGraph).where(KnowledgeGraph.id == uuid.UUID(graph_id))
            await self.db_session.execute(query)
            await self.db_session.commit()
            
            # Remove from cache
            if graph_id in self.graph_cache:
                del self.graph_cache[graph_id]
            
            logger.info(
                "Graph deleted from database",
                graph_id=graph_id,
                graph_name=graph.name
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete graph from database",
                error=str(e),
                graph_id=graph_id
            )
            await self.db_session.rollback()
            return False
    
    async def delete_node(self, node_id: str) -> bool:
        """
        Delete a knowledge node.
        
        Args:
            node_id: Node ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            # Get node
            node = await self.get_node(node_id)
            if not node:
                return False
            
            # Delete from database
            query = delete(KnowledgeNode).where(KnowledgeNode.id == uuid.UUID(node_id))
            await self.db_session.execute(query)
            await self.db_session.commit()
            
            # Remove from cache
            if node_id in self.node_cache:
                del self.node_cache[node_id]
            
            logger.info(
                "Node deleted from database",
                node_id=node_id,
                node_title=node.title
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete node from database",
                error=str(e),
                node_id=node_id
            )
            await self.db_session.rollback()
            return False
    
    async def delete_edge(self, edge_id: str) -> bool:
        """
        Delete a knowledge edge.
        
        Args:
            edge_id: Edge ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            # Get edge
            edge = await self.get_edge(edge_id)
            if not edge:
                return False
            
            # Delete from database
            query = delete(KnowledgeEdge).where(KnowledgeEdge.id == uuid.UUID(edge_id))
            await self.db_session.execute(query)
            await self.db_session.commit()
            
            # Remove from cache
            if edge_id in self.edge_cache:
                del self.edge_cache[edge_id]
            
            logger.info(
                "Edge deleted from database",
                edge_id=edge_id,
                edge_type=edge.edge_type
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete edge from database",
                error=str(e),
                edge_id=edge_id
            )
            await self.db_session.rollback()
            return False
    
    async def search_nodes(
        self,
        query: str,
        search_fields: Optional[List[str]] = None,
        node_types: Optional[List[NodeType]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeNode]:
        """
        Search knowledge nodes by text query.
        
        Args:
            query: Search query string
            search_fields: Fields to search in
            node_types: Filter by node types
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of matching KnowledgeNode instances
        """
        try:
            # Default search fields
            if not search_fields:
                search_fields = ["title", "description", "content"]
            
            # Build search conditions
            search_conditions = []
            for field in search_fields:
                if field == "title":
                    search_conditions.append(KnowledgeNode.title.ilike(f"%{query}%"))
                elif field == "description":
                    search_conditions.append(KnowledgeNode.description.ilike(f"%{query}%"))
                elif field == "content":
                    search_conditions.append(KnowledgeNode.content.ilike(f"%{query}%"))
            
            # Build query
            db_query = select(KnowledgeNode).where(or_(*search_conditions))
            
            # Add filters
            if node_types:
                db_query = db_query.where(KnowledgeNode.node_type.in_(node_types))
            
            # Add ordering and pagination
            db_query = db_query.order_by(desc(KnowledgeNode.created_at))
            db_query = db_query.limit(limit).offset(offset)
            
            result = await self.db_session.execute(db_query)
            nodes = result.scalars().all()
            
            # Update cache
            for node in nodes:
                self._cache_node(node)
            
            logger.info(
                "Node search completed",
                query=query,
                results_count=len(nodes),
                search_fields=search_fields
            )
            
            return nodes
            
        except Exception as e:
            logger.error(
                "Failed to search nodes",
                error=str(e),
                query=query
            )
            return []
    
    async def search_edges(
        self,
        query: str,
        search_fields: Optional[List[str]] = None,
        edge_types: Optional[List[EdgeType]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeEdge]:
        """
        Search knowledge edges by text query.
        
        Args:
            query: Search query string
            search_fields: Fields to search in
            edge_types: Filter by edge types
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of matching KnowledgeEdge instances
        """
        try:
            # Default search fields
            if not search_fields:
                search_fields = ["label", "description", "context"]
            
            # Build search conditions
            search_conditions = []
            for field in search_fields:
                if field == "label":
                    search_conditions.append(KnowledgeEdge.label.ilike(f"%{query}%"))
                elif field == "description":
                    search_conditions.append(KnowledgeEdge.description.ilike(f"%{query}%"))
                elif field == "context":
                    search_conditions.append(KnowledgeEdge.context.ilike(f"%{query}%"))
            
            # Build query
            db_query = select(KnowledgeEdge).where(or_(*search_conditions))
            
            # Add filters
            if edge_types:
                db_query = db_query.where(KnowledgeEdge.edge_type.in_(edge_types))
            
            # Add ordering and pagination
            db_query = db_query.order_by(desc(KnowledgeEdge.created_at))
            db_query = db_query.limit(limit).offset(offset)
            
            result = await self.db_session.execute(db_query)
            edges = result.scalars().all()
            
            # Update cache
            for edge in edges:
                self._cache_edge(edge)
            
            logger.info(
                "Edge search completed",
                query=query,
                results_count=len(edges),
                search_fields=search_fields
            )
            
            return edges
            
        except Exception as e:
            logger.error(
                "Failed to search edges",
                error=str(e),
                query=query
            )
            return []
    
    async def _update_graph_in_db(self, graph: KnowledgeGraph) -> None:
        """Update graph in database."""
        query = update(KnowledgeGraph).where(KnowledgeGraph.id == graph.id)
        
        # Only update fields that have changed
        update_data = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if graph.name:
            update_data["name"] = graph.name
        
        if graph.description is not None:
            update_data["description"] = graph.description
        
        if graph.status:
            update_data["status"] = graph.status
        
        if graph.node_count is not None:
            update_data["node_count"] = graph.node_count
        
        if graph.edge_count is not None:
            update_data["edge_count"] = graph.edge_count
        
        await self.db_session.execute(query, update_data)
        await self.db_session.commit()
    
    async def _update_node_in_db(self, node: KnowledgeNode) -> None:
        """Update node in database."""
        query = update(KnowledgeNode).where(KnowledgeNode.id == node.id)
        
        # Only update fields that have changed
        update_data = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if node.title:
            update_data["title"] = node.title
        
        if node.description is not None:
            update_data["description"] = node.description
        
        if node.content is not None:
            update_data["content"] = node.content
        
        if node.status:
            update_data["status"] = node.status
        
        if node.confidence_score is not None:
            update_data["confidence_score"] = node.confidence_score
        
        if node.quality_score is not None:
            update_data["quality_score"] = node.quality_score
        
        if node.relevance_score is not None:
            update_data["relevance_score"] = node.relevance_score
        
        await self.db_session.execute(query, update_data)
        await self.db_session.commit()
    
    async def _update_edge_in_db(self, edge: KnowledgeEdge) -> None:
        """Update edge in database."""
        query = update(KnowledgeEdge).where(KnowledgeEdge.id == edge.id)
        
        # Only update fields that have changed
        update_data = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if edge.edge_type:
            update_data["edge_type"] = edge.edge_type
        
        if edge.label is not None:
            update_data["label"] = edge.label
        
        if edge.description is not None:
            update_data["description"] = edge.description
        
        if edge.status:
            update_data["status"] = edge.status
        
        if edge.weight is not None:
            update_data["weight"] = edge.weight
        
        if edge.confidence is not None:
            update_data["confidence"] = edge.confidence
        
        if edge.strength is not None:
            update_data["strength"] = edge.strength
        
        await self.db_session.execute(query, update_data)
        await self.db_session.commit()
    
    def _cache_graph(self, graph: KnowledgeGraph) -> None:
        """Cache a graph."""
        graph_id = str(graph.id)
        
        # Check cache size limit
        if len(self.graph_cache) >= self.cache_size:
            self._evict_oldest_graph()
        
        self.graph_cache[graph_id] = graph
        self.graph_cache_timestamps[graph_id] = datetime.now(timezone.utc)
        
        # Cache metadata
        metadata = {
            "name": graph.name,
            "type": graph.graph_type,
            "status": graph.status,
            "node_count": graph.node_count,
            "edge_count": graph.edge_count
        }
        self.graph_metadata_cache[graph_id] = metadata
    
    def _cache_node(self, node: KnowledgeNode) -> None:
        """Cache a node."""
        node_id = str(node.id)
        
        # Check cache size limit
        if len(self.node_cache) >= self.cache_size:
            self._evict_oldest_node()
        
        self.node_cache[node_id] = node
        self.node_cache_timestamps[node_id] = datetime.now(timezone.utc)
    
    def _cache_edge(self, edge: KnowledgeEdge) -> None:
        """Cache an edge."""
        edge_id = str(edge.id)
        
        # Check cache size limit
        if len(self.edge_cache) >= self.cache_size:
            self._evict_oldest_edge()
        
        self.edge_cache[edge_id] = edge
        self.edge_cache_timestamps[edge_id] = datetime.now(timezone.utc)
    
    def _evict_oldest_graph(self) -> None:
        """Evict oldest graph from cache."""
        if not self.graph_cache_timestamps:
            return
        
        oldest_graph_id = min(
            self.graph_cache_timestamps.keys(),
            key=lambda k: self.graph_cache_timestamps[k]
        )
        
        if oldest_graph_id in self.graph_cache:
            del self.graph_cache[oldest_graph_id]
        
        if oldest_graph_id in self.graph_cache_timestamps:
            del self.graph_cache_timestamps[oldest_graph_id]
        
        if oldest_graph_id in self.graph_metadata_cache:
            del self.graph_metadata_cache[oldest_graph_id]
        
        self.storage_stats["cache_evictions"] += 1
    
    def _evict_oldest_node(self) -> None:
        """Evict oldest node from cache."""
        if not self.node_cache_timestamps:
            return
        
        oldest_node_id = min(
            self.node_cache_timestamps.keys(),
            key=lambda k: self.node_cache_timestamps[k]
        )
        
        if oldest_node_id in self.node_cache:
            del self.node_cache[oldest_node_id]
        
        if oldest_node_id in self.node_cache_timestamps:
            del self.node_cache_timestamps[oldest_node_id]
        
        self.storage_stats["cache_evictions"] += 1
    
    def _evict_oldest_edge(self) -> None:
        """Evict oldest edge from cache."""
        if not self.edge_cache_timestamps:
            return
        
        oldest_edge_id = min(
            self.edge_cache_timestamps.keys(),
            key=lambda k: self.edge_cache_timestamps[k]
        )
        
        if oldest_edge_id in self.edge_cache:
            del self.edge_cache[oldest_edge_id]
        
        if oldest_edge_id in self.edge_cache_timestamps:
            del self.edge_cache_timestamps[oldest_edge_id]
        
        self.storage_stats["cache_evictions"] += 1
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self.graph_cache.clear()
        self.node_cache.clear()
        self.edge_cache.clear()
        self.graph_metadata_cache.clear()
        self.graph_cache_timestamps.clear()
        self.node_cache_timestamps.clear()
        self.edge_cache_timestamps.clear()
        
        logger.info("Graph storage caches cleared")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "cache_stats": {
                "graph_cache_size": len(self.graph_cache),
                "node_cache_size": len(self.node_cache),
                "edge_cache_size": len(self.edge_cache),
                "cache_hits": self.storage_stats["cache_hits"],
                "cache_misses": self.storage_stats["cache_misses"],
                "cache_evictions": self.storage_stats["cache_evictions"],
                "hit_rate": (
                    self.storage_stats["cache_hits"] / 
                    (self.storage_stats["cache_hits"] + self.storage_stats["cache_misses"])
                    if (self.storage_stats["cache_hits"] + self.storage_stats["cache_misses"]) > 0 else 0
                )
            },
            "database_stats": {
                "db_operations": self.storage_stats["db_operations"],
                "total_operations": self.storage_stats["total_operations"]
            },
            "performance_metrics": {
                "cache_efficiency": (
                    self.storage_stats["cache_hits"] / 
                    self.storage_stats["total_operations"]
                    if self.storage_stats["total_operations"] > 0 else 0
                )
            }
        }
    
    def reset_stats(self) -> None:
        """Reset storage statistics."""
        self.storage_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "db_operations": 0,
            "cache_evictions": 0,
            "total_operations": 0
        }
