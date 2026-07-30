"""
CODX Graph Traversal

Graph traversal algorithms and pathfinding
for CODX knowledge engine.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import asyncio
import heapq
from collections import deque, defaultdict

from ..models.knowledge_node import KnowledgeNode
from ..models.knowledge_edge import KnowledgeEdge, EdgeType
from ..models.knowledge_graph import KnowledgeGraph, TraversalAlgorithm
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class GraphTraverser:
    """
    Graph traverser for CODX knowledge engine.
    
    Implements various traversal algorithms including
    BFS, DFS, Dijkstra, A*, and more.
    """
    
    def __init__(self, db_session):
        """Initialize graph traverser."""
        self.db_session = db_session
        self.visited_nodes: Set[str] = set()
        self.visited_edges: Set[str] = set()
        self.traversal_stats = {
            "nodes_visited": 0,
            "edges_traversed": 0,
            "execution_time_ms": 0,
            "algorithm": "",
            "start_node": None,
            "target_node": None
        }
    
    async def breadth_first_search(
        self,
        start_node_id: str,
        max_depth: Optional[int] = None,
        max_nodes: Optional[int] = None,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Perform breadth-first search (BFS) traversal.
        
        Args:
            start_node_id: Starting node ID
            max_depth: Maximum depth to traverse
            max_nodes: Maximum number of nodes to visit
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            Traversal results dictionary
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get start node
            start_node = await self._get_node(start_node_id)
            if not start_node:
                raise BaseLayerError(f"Start node not found: {start_node_id}")
            
            # Initialize BFS queue
            queue = deque([(str(start_node.id), 0)])  # (node_id, depth)
            visited = {str(start_node.id)}
            traversal_order = []
            node_distances = {str(start_node.id): 0}
            
            while queue:
                node_id, depth = queue.popleft()
                
                # Check depth limit
                if max_depth is not None and depth > max_depth:
                    continue
                
                # Check node limit
                if max_nodes is not None and len(traversal_order) >= max_nodes:
                    break
                
                current_node = await self._get_node(node_id)
                if not current_node:
                    continue
                
                # Add to traversal order
                node_data = {
                    "id": str(current_node.id),
                    "title": current_node.title,
                    "node_type": current_node.node_type,
                    "level": current_node.level,
                    "depth": depth
                }
                
                if include_metadata:
                    node_data.update({
                        "keywords": current_node.keywords or [],
                        "tags": current_node.tags or {},
                        "metadata": current_node.metadata or {},
                        "confidence_score": current_node.confidence_score,
                        "quality_score": current_node.quality_score,
                        "relevance_score": current_node.relevance_score,
                        "created_at": current_node.created_at.isoformat() if current_node.created_at else None,
                        "updated_at": current_node.updated_at.isoformat() if current_node.updated_at else None
                    })
                
                traversal_order.append(node_data)
                
                # Get outgoing edges
                outgoing_edges = await self._get_outgoing_edges(
                    str(current_node.id),
                    edge_types
                )
                
                # Add neighbors to queue
                for edge in outgoing_edges:
                    neighbor_id = str(edge.target_id)
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, depth + 1))
                        node_distances[neighbor_id] = depth + 1
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(visited),
                "edges_traversed": len(outgoing_edges),
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.BFS,
                "start_node": start_node_id,
                "node_distances": node_distances
            })
            
            result = {
                "algorithm": TraversalAlgorithm.BFS,
                "start_node_id": start_node_id,
                "traversal_order": traversal_order,
                "node_distances": node_distances,
                "max_depth": max(node_distances.values()) if node_distances else 0,
                "total_nodes": len(visited),
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "max_depth": max_depth,
                    "max_nodes": max_nodes,
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata
                }
            }
            
            logger.info(
                "BFS traversal completed",
                start_node=start_node_id,
                nodes_visited=len(visited),
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "BFS traversal failed",
                error=str(e),
                start_node=start_node_id
            )
            raise BaseLayerError(f"BFS traversal failed: {str(e)}") from e
    
    async def depth_first_search(
        self,
        start_node_id: str,
        max_depth: Optional[int] = None,
        max_nodes: Optional[int] = None,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Perform depth-first search (DFS) traversal.
        
        Args:
            start_node_id: Starting node ID
            max_depth: Maximum depth to traverse
            max_nodes: Maximum number of nodes to visit
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            Traversal results dictionary
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get start node
            start_node = await self._get_node(start_node_id)
            if not start_node:
                raise BaseLayerError(f"Start node not found: {start_node_id}")
            
            # Initialize DFS stack
            stack = [(str(start_node.id), 0, [str(start_node.id)])]  # (node_id, depth, path)
            visited = {str(start_node.id)}
            traversal_order = []
            
            while stack:
                node_id, depth, path = stack.pop()
                
                # Check depth limit
                if max_depth is not None and depth > max_depth:
                    continue
                
                # Check node limit
                if max_nodes is not None and len(traversal_order) >= max_nodes:
                    break
                
                current_node = await self._get_node(node_id)
                if not current_node:
                    continue
                
                # Add to traversal order
                node_data = {
                    "id": str(current_node.id),
                    "title": current_node.title,
                    "node_type": current_node.node_type,
                    "level": current_node.level,
                    "depth": depth,
                    "path": path.copy()
                }
                
                if include_metadata:
                    node_data.update({
                        "keywords": current_node.keywords or [],
                        "tags": current_node.tags or {},
                        "metadata": current_node.metadata or {},
                        "confidence_score": current_node.confidence_score,
                        "quality_score": current_node.quality_score,
                        "relevance_score": current_node.relevance_score,
                        "created_at": current_node.created_at.isoformat() if current_node.created_at else None,
                        "updated_at": current_node.updated_at.isoformat() if current_node.updated_at else None
                    })
                
                traversal_order.append(node_data)
                
                # Get outgoing edges
                outgoing_edges = await self._get_outgoing_edges(
                    str(current_node.id),
                    edge_types
                )
                
                # Add neighbors to stack (reverse order for DFS)
                for edge in reversed(outgoing_edges):
                    neighbor_id = str(edge.target_id)
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        new_path = path + [neighbor_id]
                        stack.append((neighbor_id, depth + 1, new_path))
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(visited),
                "edges_traversed": len(outgoing_edges),
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.DFS,
                "start_node": start_node_id
            })
            
            result = {
                "algorithm": TraversalAlgorithm.DFS,
                "start_node_id": start_node_id,
                "traversal_order": traversal_order,
                "max_depth": max(node["depth"] for node in traversal_order) if traversal_order else 0,
                "total_nodes": len(visited),
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "max_depth": max_depth,
                    "max_nodes": max_nodes,
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata
                }
            }
            
            logger.info(
                "DFS traversal completed",
                start_node=start_node_id,
                nodes_visited=len(visited),
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "DFS traversal failed",
                error=str(e),
                start_node=start_node_id
            )
            raise BaseLayerError(f"DFS traversal failed: {str(e)}") from e
    
    async def dijkstra_shortest_path(
        self,
        start_node_id: str,
        target_node_id: str,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Find shortest path using Dijkstra's algorithm.
        
        Args:
            start_node_id: Starting node ID
            target_node_id: Target node ID
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            Shortest path results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get start and target nodes
            start_node = await self._get_node(start_node_id)
            target_node = await self._get_node(target_node_id)
            
            if not start_node:
                raise BaseLayerError(f"Start node not found: {start_node_id}")
            
            if not target_node:
                raise BaseLayerError(f"Target node not found: {target_node_id}")
            
            # Initialize Dijkstra's algorithm
            distances = {str(start_node.id): 0.0}
            previous_nodes = {str(start_node.id): None}
            unvisited = set()
            heap = [(0.0, str(start_node.id))]
            
            # Get all nodes
            all_nodes = await self._get_all_nodes()
            for node in all_nodes:
                if str(node.id) != str(start_node.id):
                    unvisited.add(str(node.id))
            
            while heap:
                current_distance, current_node_id = heapq.heappop(heap)
                
                if current_node_id == str(target_node.id):
                    break
                
                if current_node_id not in unvisited:
                    continue
                
                current_node = await self._get_node(current_node_id)
                if not current_node:
                    continue
                
                # Get outgoing edges
                outgoing_edges = await self._get_outgoing_edges(
                    current_node_id,
                    edge_types
                )
                
                # Update distances to neighbors
                for edge in outgoing_edges:
                    neighbor_id = str(edge.target_id)
                    if neighbor_id not in unvisited:
                        continue
                    
                    distance = current_distance + edge.weight
                    if neighbor_id not in distances or distance < distances[neighbor_id]:
                        distances[neighbor_id] = distance
                        previous_nodes[neighbor_id] = current_node_id
                        heapq.heappush(heap, (distance, neighbor_id))
                
                unvisited.discard(current_node_id)
            
            # Reconstruct path
            if str(target_node.id) not in distances:
                return {
                    "algorithm": TraversalAlgorithm.DIJKSTRA,
                    "start_node_id": start_node_id,
                    "target_node_id": target_node_id,
                    "path": [],
                    "distance": float('inf'),
                    "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                    "error": "No path found"
                }
            
            # Reconstruct path from target to start
            path = []
            current_node_id = str(target_node.id)
            
            while current_node_id is not None:
                path.insert(0, current_node_id)
                current_node_id = previous_nodes.get(current_node_id)
            
            path.reverse()
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(distances),
                "edges_traversed": len(path) - 1,
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.DIJKSTRA,
                "start_node": start_node_id,
                "target_node": target_node_id
            })
            
            result = {
                "algorithm": TraversalAlgorithm.DIJKSTRA,
                "start_node_id": start_node_id,
                "target_node_id": target_node_id,
                "path": path,
                "distance": distances[str(target_node.id)],
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata,
                    "nodes_explored": len(distances)
                }
            }
            
            logger.info(
                "Dijkstra shortest path completed",
                start_node=start_node_id,
                target_node=target_node_id,
                path_length=len(path),
                distance=distances[str(target_node.id)],
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Dijkstra shortest path failed",
                error=str(e),
                start_node=start_node_id,
                target_node=target_node_id
            )
            raise BaseLayerError(f"Dijkstra shortest path failed: {str(e)}") from e
    
    async def a_star_pathfinding(
        self,
        start_node_id: str,
        target_node_id: str,
        heuristic_func: Optional[callable] = None,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Find shortest path using A* algorithm.
        
        Args:
            start_node_id: Starting node ID
            target_node_id: Target node ID
            heuristic_func: Heuristic function for A*
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            A* pathfinding results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get start and target nodes
            start_node = await self._get_node(start_node_id)
            target_node = await self._get_node(target_node_id)
            
            if not start_node:
                raise BaseLayerError(f"Start node not found: {start_node_id}")
            
            if not target_node:
                raise BaseLayerError(f"Target node not found: {target_node_id}")
            
            # Default heuristic (straight-line distance based on level)
            if heuristic_func is None:
                def heuristic(node_id: str) -> float:
                    node = await self._get_node(node_id)
                    if not node:
                        return 0.0
                    return abs(node.level - target_node.level)
            
            # Initialize A* algorithm
            g_scores = {str(start_node.id): 0.0}  # Cost from start
            f_scores = {str(start_node.id): heuristic(str(start_node.id))}  # Heuristic to target
            f_scores_total = {str(start_node.id): f_scores[str(start_node.id)]}  # g + f
            previous_nodes = {str(start_node.id): None}
            open_set = [(f_scores_total[str(start_node.id)], str(start_node.id))]
            closed_set = set()
            
            while open_set:
                current_f_total, current_node_id = heapq.heappop(open_set)
                
                if current_node_id == str(target_node.id):
                    break
                
                if current_node_id in closed_set:
                    continue
                
                closed_set.add(current_node_id)
                
                current_node = await self._get_node(current_node_id)
                if not current_node:
                    continue
                
                # Get outgoing edges
                outgoing_edges = await self._get_outgoing_edges(
                    current_node_id,
                    edge_types
                )
                
                # Update scores for neighbors
                for edge in outgoing_edges:
                    neighbor_id = str(edge.target_id)
                    if neighbor_id in closed_set:
                        continue
                    
                    tentative_g_score = g_scores[current_node_id] + edge.weight
                    tentative_f_score = heuristic(neighbor_id)
                    tentative_f_total = tentative_g_score + tentative_f_score
                    
                    if (neighbor_id not in f_scores or 
                        tentative_f_total < f_scores_total[neighbor_id]):
                        
                        f_scores[neighbor_id] = tentative_f_score
                        f_scores_total[neighbor_id] = tentative_f_total
                        previous_nodes[neighbor_id] = current_node_id
                        heapq.heappush(open_set, (tentative_f_total, neighbor_id))
            
            # Reconstruct path
            if str(target_node.id) not in g_scores:
                return {
                    "algorithm": TraversalAlgorithm.A_STAR,
                    "start_node_id": start_node_id,
                    "target_node_id": target_node_id,
                    "path": [],
                    "distance": float('inf'),
                    "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                    "error": "No path found"
                }
            
            # Reconstruct path from target to start
            path = []
            current_node_id = str(target_node.id)
            
            while current_node_id is not None:
                path.insert(0, current_node_id)
                current_node_id = previous_nodes.get(current_node_id)
            
            path.reverse()
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(closed_set),
                "edges_traversed": len(path) - 1,
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.A_STAR,
                "start_node": start_node_id,
                "target_node": target_node_id
            })
            
            result = {
                "algorithm": TraversalAlgorithm.A_STAR,
                "start_node_id": start_node_id,
                "target_node_id": target_node_id,
                "path": path,
                "distance": g_scores[str(target_node.id)],
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata,
                    "nodes_explored": len(closed_set),
                    "heuristic": "level_difference" if heuristic_func is None else "custom"
                }
            }
            
            logger.info(
                "A* pathfinding completed",
                start_node=start_node_id,
                target_node=target_node_id,
                path_length=len(path),
                distance=g_scores[str(target_node.id)],
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "A* pathfinding failed",
                error=str(e),
                start_node=start_node_id,
                target_node=target_node_id
            )
            raise BaseLayerError(f"A* pathfinding failed: {str(e)}") from e
    
    async def topological_sort(
        self,
        start_node_id: Optional[str] = None,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Perform topological sort on directed acyclic graph.
        
        Args:
            start_node_id: Starting node ID (optional)
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            Topological sort results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get all nodes
            all_nodes = await self._get_all_nodes()
            node_ids = [str(node.id) for node in all_nodes]
            
            # Build adjacency list
            adjacency = defaultdict(list)
            in_degree = defaultdict(int)
            
            for node_id in node_ids:
                outgoing_edges = await self._get_outgoing_edges(node_id, edge_types)
                for edge in outgoing_edges:
                    adjacency[node_id].append(str(edge.target_id))
                    in_degree[str(edge.target_id)] += 1
            
            # Kahn's algorithm for topological sort
            queue = deque([node_id for node_id in node_ids if in_degree[node_id] == 0])
            topological_order = []
            
            while queue:
                current_node_id = queue.popleft()
                topological_order.append(current_node_id)
                
                for neighbor_id in adjacency[current_node_id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        queue.append(neighbor_id)
            
            # Check for cycles
            if len(topological_order) != len(node_ids):
                return {
                    "algorithm": TraversalAlgorithm.TOPOLOGICAL_SORT,
                    "start_node_id": start_node_id,
                    "topological_order": [],
                    "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                    "error": "Graph contains cycles",
                    "metadata": {
                        "edge_types": [et.value for et in edge_types] if edge_types else [],
                        "include_metadata": include_metadata
                    }
                }
            
            # Filter by start node if specified
            if start_node_id:
                start_index = topological_order.index(start_node_id) if start_node_id in topological_order else -1
                topological_order = topological_order[start_index + 1:] if start_index >= 0 else topological_order
            
            # Get node details
            node_details = {}
            if include_metadata:
                for node_id in topological_order:
                    node = await self._get_node(node_id)
                    if node:
                        node_details[node_id] = {
                            "id": node_id,
                            "title": node.title,
                            "node_type": node.node_type,
                            "level": node.level,
                            "keywords": node.keywords or [],
                            "tags": node.tags or {},
                            "metadata": node.metadata or {},
                            "confidence_score": node.confidence_score,
                            "quality_score": node.quality_score,
                            "relevance_score": node.relevance_score,
                            "created_at": node.created_at.isoformat() if node.created_at else None,
                            "updated_at": node.updated_at.isoformat() if node.updated_at else None
                        }
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(topological_order),
                "edges_traversed": len(topological_order) - 1,
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.TOPOLOGICAL_SORT,
                "start_node": start_node_id
            })
            
            result = {
                "algorithm": TraversalAlgorithm.TOPOLOGICAL_SORT,
                "start_node_id": start_node_id,
                "topological_order": topological_order,
                "node_details": node_details if include_metadata else {},
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata,
                    "is_dag": True
                }
            }
            
            logger.info(
                "Topological sort completed",
                start_node=start_node_id,
                nodes_sorted=len(topological_order),
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Topological sort failed",
                error=str(e),
                start_node=start_node_id
            )
            raise BaseLayerError(f"Topological sort failed: {str(e)}") from e
    
    async def find_strongly_connected_components(
        self,
        edge_types: Optional[List[EdgeType]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Find strongly connected components using Kosaraju's algorithm.
        
        Args:
            edge_types: Filter by edge types
            include_metadata: Include node and edge metadata
            
        Returns:
            Strongly connected components results
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get all nodes
            all_nodes = await self._get_all_nodes()
            node_ids = [str(node.id) for node in all_nodes]
            
            # Build adjacency list
            adjacency = defaultdict(list)
            for node_id in node_ids:
                outgoing_edges = await self._get_outgoing_edges(node_id, edge_types)
                for edge in outgoing_edges:
                    adjacency[node_id].append(str(edge.target_id))
            
            # Kosaraju's algorithm
            index = 0
            indices = {node_id: index for index, node_id in enumerate(node_ids)}
            lowlink = [0] * len(node_ids)
            
            def dfs(v: str, visited: Set[str], stack: List[str]) -> None:
                visited.add(v)
                stack.append(v)
                
                for w in adjacency[v]:
                    if w not in visited:
                        dfs(w, visited, stack)
            
            # First DFS to assign indices
            visited = set()
            for v in node_ids:
                if v not in visited:
                    dfs(v, visited, [])
            
            # Second DFS on reversed graph
            reversed_adjacency = defaultdict(list)
            for v in node_ids:
                for w in adjacency[v]:
                    reversed_adjacency[w].append(v)
            
            visited = set()
            for v in reversed(node_ids):
                if v not in visited:
                    dfs(v, visited, [])
            
            # Find strongly connected components
            visited = set()
            components = []
            
            for v in node_ids:
                if v not in visited:
                    component = []
                    stack = [v]
                    visited.add(v)
                    
                    while stack:
                        w = stack.pop()
                        if w not in visited:
                            dfs(w, visited, component)
                    
                    components.append(component)
            
            # Get component details
            component_details = []
            if include_metadata:
                for component in components:
                    component_nodes = []
                    for node_id in component:
                        node = await self._get_node(node_id)
                        if node:
                            component_nodes.append({
                                "id": node_id,
                                "title": node.title,
                                "node_type": node.node_type,
                                "level": node.level,
                                "keywords": node.keywords or [],
                                "tags": node.tags or {},
                                "metadata": node.metadata or {},
                                "confidence_score": node.confidence_score,
                                "quality_score": node.quality_score,
                                "relevance_score": node.relevance_score,
                                "created_at": node.created_at.isoformat() if node.created_at else None,
                                "updated_at": node.updated_at.isoformat() if node.updated_at else None
                            })
                    
                    component_details.append(component_nodes)
            
            # Update statistics
            self.traversal_stats.update({
                "nodes_visited": len(node_ids),
                "edges_traversed": len([edge for edges in adjacency.values() for edge in edges]),
                "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "algorithm": TraversalAlgorithm.STRONGLY_CONNECTED
            })
            
            result = {
                "algorithm": TraversalAlgorithm.STRONGLY_CONNECTED,
                "components": components,
                "component_details": component_details if include_metadata else {},
                "component_count": len(components),
                "execution_time_ms": self.traversal_stats["execution_time_ms"],
                "metadata": {
                    "edge_types": [et.value for et in edge_types] if edge_types else [],
                    "include_metadata": include_metadata
                }
            }
            
            logger.info(
                "Strongly connected components found",
                component_count=len(components),
                execution_time_ms=self.traversal_stats["execution_time_ms"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Strongly connected components failed",
                error=str(e)
            )
            raise BaseLayerError(f"Strongly connected components failed: {str(e)}") from e
    
    async def _get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get node by ID."""
        query = select(KnowledgeNode).where(KnowledgeNode.id == uuid.UUID(node_id))
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_edge(self, edge_id: str) -> Optional[KnowledgeEdge]:
        """Get edge by ID."""
        query = select(KnowledgeEdge).where(KnowledgeEdge.id == uuid.UUID(edge_id))
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_outgoing_edges(
        self,
        node_id: str,
        edge_types: Optional[List[EdgeType]] = None
    ) -> List[KnowledgeEdge]:
        """Get outgoing edges from a node."""
        query = select(KnowledgeEdge).where(KnowledgeEdge.source_id == uuid.UUID(node_id))
        
        if edge_types:
            query = query.where(KnowledgeEdge.edge_type.in_(edge_types))
        
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def _get_all_nodes(self) -> List[KnowledgeNode]:
        """Get all nodes."""
        query = select(KnowledgeNode).where(KnowledgeNode.status == "active")
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    def get_traversal_stats(self) -> Dict[str, Any]:
        """Get current traversal statistics."""
        return self.traversal_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset traversal statistics."""
        self.traversal_stats = {
            "nodes_visited": 0,
            "edges_traversed": 0,
            "execution_time_ms": 0,
            "algorithm": "",
            "start_node": None,
            "target_node": None
        }
