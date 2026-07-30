"""
CODX Graph Analytics

Graph analytics and insights for CODX knowledge engine
with comprehensive metrics and analysis.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import asyncio
import math
from collections import defaultdict, Counter

from ..models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from ..models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from ..models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class GraphAnalyzer:
    """
    Graph analyzer for CODX knowledge engine.
    
    Provides comprehensive analytics and insights
    for knowledge graphs including structure,
    performance, and usage metrics.
    """
    
    def __init__(self, db_session):
        """Initialize graph analyzer."""
        self.db_session = db_session
        self.analytics_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = None
    
    async def analyze_graph_structure(
        self,
        graph_id: str,
        include_detailed: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze graph structure and topology.
        
        Args:
            graph_id: Graph ID to analyze
            include_detailed: Include detailed node/edge analysis
            
        Returns:
            Graph structure analysis results
        """
        try:
            # Check cache first
            cache_key = f"structure_{graph_id}_{include_detailed}"
            if self._is_cache_valid(cache_key):
                return self.analytics_cache[cache_key]
            
            # Get graph and nodes/edges
            graph = await self._get_graph(graph_id)
            if not graph:
                return {"error": "Graph not found"}
            
            nodes = await self._get_graph_nodes(graph_id)
            edges = await self._get_graph_edges(graph_id)
            
            # Basic structure metrics
            analysis = {
                "graph_id": graph_id,
                "basic_metrics": {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "density": self._calculate_density(len(nodes), len(edges), graph.is_directed),
                    "is_connected": await self._is_connected(nodes, edges),
                    "is_cyclic": self._has_cycles(nodes, edges, graph.is_directed),
                    "max_depth": self._calculate_max_depth(nodes),
                    "average_path_length": self._calculate_average_path_length(nodes, edges)
                },
                "degree_analysis": self._analyze_degrees(nodes, edges),
                "clustering_analysis": self._analyze_clustering(nodes, edges),
                "component_analysis": self._analyze_components(nodes, edges, graph.is_directed),
                "centrality_analysis": self._analyze_centrality(nodes, edges) if include_detailed else {},
                "path_analysis": self._analyze_paths(nodes, edges) if include_detailed else {},
                "topology_analysis": self._analyze_topology(nodes, edges, graph.is_directed)
            }
            
            # Add detailed analysis if requested
            if include_detailed:
                analysis["node_analysis"] = await self._analyze_nodes_detailed(nodes)
                analysis["edge_analysis"] = await self._analyze_edges_detailed(edges)
                analysis["subgraph_analysis"] = self._analyze_subgraphs(nodes, edges)
                analysis["motif_analysis"] = self._analyze_motifs(nodes, edges)
            
            # Cache results
            self._cache_result(cache_key, analysis)
            
            logger.info(
                "Graph structure analysis completed",
                graph_id=graph_id,
                node_count=len(nodes),
                edge_count=len(edges)
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                "Graph structure analysis failed",
                error=str(e),
                graph_id=graph_id
            )
            raise BaseLayerError(f"Graph structure analysis failed: {str(e)}") from e
    
    async def analyze_graph_performance(
        self,
        graph_id: str,
        time_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze graph performance metrics.
        
        Args:
            graph_id: Graph ID to analyze
            time_range: Time range for analysis
            
        Returns:
            Graph performance analysis results
        """
        try:
            # Check cache first
            cache_key = f"performance_{graph_id}_{str(time_range)}"
            if self._is_cache_valid(cache_key):
                return self.analytics_cache[cache_key]
            
            # Get graph
            graph = await self._get_graph(graph_id)
            if not graph:
                return {"error": "Graph not found"}
            
            # Get performance data
            performance_data = {
                "graph_id": graph_id,
                "traversal_performance": graph.traversal_performance or {},
                "query_performance": graph.query_performance or {},
                "index_performance": graph.index_performance or {},
                "usage_metrics": {
                    "access_count": graph.access_count,
                    "query_count": graph.query_count,
                    "last_accessed": graph.last_accessed.isoformat() if graph.last_accessed else None,
                    "last_updated": graph.last_updated.isoformat() if graph.last_updated else None
                },
                "time_series_analysis": await self._analyze_time_series(graph_id, time_range),
                "bottleneck_analysis": await self._analyze_bottlenecks(graph_id, time_range),
                "optimization_suggestions": await self._generate_optimization_suggestions(graph_id)
            }
            
            # Cache results
            self._cache_result(cache_key, performance_data)
            
            logger.info(
                "Graph performance analysis completed",
                graph_id=graph_id,
                access_count=graph.access_count,
                query_count=graph.query_count
            )
            
            return performance_data
            
        except Exception as e:
            logger.error(
                "Graph performance analysis failed",
                error=str(e),
                graph_id=graph_id
            )
            raise BaseLayerError(f"Graph performance analysis failed: {str(e)}") from e
    
    async def analyze_graph_usage(
        self,
        graph_id: str,
        time_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze graph usage patterns and statistics.
        
        Args:
            graph_id: Graph ID to analyze
            time_range: Time range for analysis
            
        Returns:
            Graph usage analysis results
        """
        try:
            # Check cache first
            cache_key = f"usage_{graph_id}_{str(time_range)}"
            if self._is_cache_valid(cache_key):
                return self.analytics_cache[cache_key]
            
            # Get graph and usage data
            graph = await self._get_graph(graph_id)
            if not graph:
                return {"error": "Graph not found"}
            
            nodes = await self._get_graph_nodes(graph_id)
            edges = await self._get_graph_edges(graph_id)
            
            # Analyze usage patterns
            usage_data = {
                "graph_id": graph_id,
                "access_patterns": await self._analyze_access_patterns(graph_id, time_range),
                "node_usage": await self._analyze_node_usage(nodes, time_range),
                "edge_usage": await self._analyze_edge_usage(edges, time_range),
                "query_patterns": await self._analyze_query_patterns(graph_id, time_range),
                "user_behavior": await self._analyze_user_behavior(graph_id, time_range),
                "growth_metrics": await self._analyze_growth_metrics(graph_id, time_range),
                "engagement_metrics": await self._analyze_engagement_metrics(graph_id, time_range)
            }
            
            # Cache results
            self._cache_result(cache_key, usage_data)
            
            logger.info(
                "Graph usage analysis completed",
                graph_id=graph_id,
                access_count=graph.access_count
            )
            
            return usage_data
            
        except Exception as e:
            logger.error(
                "Graph usage analysis failed",
                error=str(e),
                graph_id=graph_id
            )
            raise BaseLayerError(f"Graph usage analysis failed: {str(e)}") from e
    
    async def compare_graphs(
        self,
        graph_ids: List[str],
        comparison_metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple graphs across various metrics.
        
        Args:
            graph_ids: List of graph IDs to compare
            comparison_metrics: List of metrics to compare
            
        Returns:
            Graph comparison results
        """
        try:
            if len(graph_ids) < 2:
                return {"error": "At least 2 graphs required for comparison"}
            
            # Default comparison metrics
            if not comparison_metrics:
                comparison_metrics = [
                    "node_count", "edge_count", "density", "clustering_coefficient",
                    "average_path_length", "access_count", "query_count"
                ]
            
            # Get all graphs
            graphs = {}
            for graph_id in graph_ids:
                graph = await self._get_graph(graph_id)
                if graph:
                    graphs[graph_id] = graph
            
            if len(graphs) < 2:
                return {"error": "No valid graphs found for comparison"}
            
            # Compare graphs
            comparison_results = {
                "graph_ids": graph_ids,
                "comparison_metrics": comparison_metrics,
                "graph_data": {},
                "differences": {},
                "similarities": {},
                "rankings": {}
            }
            
            # Collect data for each graph
            for graph_id, graph in graphs.items():
                nodes = await self._get_graph_nodes(graph_id)
                edges = await self._get_graph_edges(graph_id)
                
                graph_data = {
                    "basic_info": {
                        "id": graph_id,
                        "name": graph.name,
                        "type": graph.graph_type,
                        "status": graph.status,
                        "created_at": graph.created_at.isoformat() if graph.created_at else None
                    },
                    "metrics": {
                        "node_count": len(nodes),
                        "edge_count": len(edges),
                        "density": self._calculate_density(len(nodes), len(edges), graph.is_directed),
                        "clustering_coefficient": self._calculate_clustering_coefficient(nodes, edges),
                        "average_path_length": self._calculate_average_path_length(nodes, edges),
                        "max_depth": self._calculate_max_depth(nodes),
                        "access_count": graph.access_count,
                        "query_count": graph.query_count,
                        "last_accessed": graph.last_accessed.isoformat() if graph.last_accessed else None
                    }
                }
                
                comparison_results["graph_data"][graph_id] = graph_data
            
            # Calculate differences and similarities
            metric_values = {}
            for metric in comparison_metrics:
                metric_values[metric] = {}
                for graph_id in graph_ids:
                    graph_data = comparison_results["graph_data"].get(graph_id)
                    if graph_data:
                        metric_values[metric][graph_id] = graph_data["metrics"].get(metric, 0)
            
            # Calculate rankings
            for metric in comparison_metrics:
                values = metric_values.get(metric, {})
                if values:
                    sorted_graphs = sorted(values.items(), key=lambda x: x[1], reverse=True)
                    comparison_results["rankings"][metric] = sorted_graphs
            
            # Find differences and similarities
            graph_id_list = list(graphs.keys())
            for i, graph_id_1 in enumerate(graph_id_list):
                for graph_id_2 in graph_id_list[i+1:]:
                    differences = []
                    similarities = []
                    
                    for metric in comparison_metrics:
                        values = metric_values.get(metric, {})
                        if values:
                            val1 = values.get(graph_id_1, 0)
                            val2 = values.get(graph_id_2, 0)
                            
                            if val1 != val2:
                                diff = abs(val1 - val2)
                                differences.append({
                                    "metric": metric,
                                    "difference": diff,
                                    "graph1_value": val1,
                                    "graph2_value": val2
                                })
                            else:
                                similarities.append(metric)
                    
                    comparison_results["differences"][f"{graph_id_1}_vs_{graph_id_2}"] = differences
                    comparison_results["similarities"][f"{graph_id_1}_vs_{graph_id_2}"] = similarities
            
            logger.info(
                "Graph comparison completed",
                graph_ids=graph_ids,
                metrics_compared=len(comparison_metrics)
            )
            
            return comparison_results
            
        except Exception as e:
            logger.error(
                "Graph comparison failed",
                error=str(e),
                graph_ids=graph_ids
            )
            raise BaseLayerError(f"Graph comparison failed: {str(e)}") from e
    
    def _calculate_density(self, node_count: int, edge_count: int, is_directed: bool) -> float:
        """Calculate graph density."""
        if node_count <= 1:
            return 0.0
        
        max_edges = node_count * (node_count - 1)
        if is_directed:
            max_edges = node_count * (node_count - 1)
        
        return edge_count / max_edges if max_edges > 0 else 0.0
    
    async def _is_connected(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> bool:
        """Check if graph is connected."""
        if not nodes:
            return True
        
        # Build adjacency list
        adjacency = defaultdict(set)
        for edge in edges:
            adjacency[str(edge.source_id)].add(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].add(str(edge.source_id))
        
        # BFS to check connectivity
        visited = set()
        queue = [str(nodes[0].id)]
        visited.add(str(nodes[0].id))
        
        while queue:
            current = queue.pop(0)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return len(visited) == len(nodes)
    
    def _has_cycles(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge], is_directed: bool) -> bool:
        """Check if graph has cycles."""
        if len(nodes) <= 1:
            return False
        
        # Build adjacency list
        adjacency = defaultdict(list)
        for edge in edges:
            adjacency[str(edge.source_id)].append(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].append(str(edge.source_id))
        
        # DFS to detect cycles
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in adjacency[node_id]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.discard(node_id)
            return False
        
        for node in nodes:
            if str(node.id) not in visited:
                if dfs(str(node.id)):
                    return True
        
        return False
    
    def _calculate_max_depth(self, nodes: List[KnowledgeNode]) -> int:
        """Calculate maximum depth in graph."""
        if not nodes:
            return 0
        
        return max(node.level for node in nodes)
    
    def _calculate_average_path_length(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> float:
        """Calculate average path length."""
        if len(nodes) <= 1:
            return 0.0
        
        # Simplified calculation based on density
        density = self._calculate_density(len(nodes), len(edges), False)
        if density == 0:
            return float('inf')
        
        # Approximate average path length
        return len(nodes) / (density * len(nodes))
    
    def _analyze_degrees(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze node degrees."""
        if not nodes:
            return {}
        
        # Calculate degrees
        degrees = {}
        for node in nodes:
            degrees[str(node.id)] = 0
        
        for edge in edges:
            degrees[str(edge.source_id)] += 1
            if edge.bidirectional:
                degrees[str(edge.target_id)] += 1
        
        # Calculate statistics
        degree_values = list(degrees.values())
        degree_stats = {
            "average_degree": sum(degree_values) / len(degree_values) if degree_values else 0,
            "max_degree": max(degree_values) if degree_values else 0,
            "min_degree": min(degree_values) if degree_values else 0,
            "degree_distribution": Counter(degree_values),
            "nodes_by_degree": {}
        }
        
        # Group nodes by degree
        for node_id, degree in degrees.items():
            if degree not in degree_stats["nodes_by_degree"]:
                degree_stats["nodes_by_degree"][degree] = []
            degree_stats["nodes_by_degree"][degree].append(node_id)
        
        return degree_stats
    
    def _analyze_clustering(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze clustering coefficients."""
        if len(nodes) <= 2:
            return {"clustering_coefficient": 0.0}
        
        # Build adjacency list
        adjacency = defaultdict(set)
        for edge in edges:
            adjacency[str(edge.source_id)].add(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].add(str(edge.source_id))
        
        # Calculate clustering coefficients
        clustering_coeffs = {}
        for node in nodes:
            neighbors = adjacency[str(node.id)]
            if len(neighbors) < 2:
                clustering_coeffs[str(node.id)] = 0.0
                continue
            
            # Count edges between neighbors
            neighbor_edges = 0
            for i, neighbor1 in enumerate(neighbors):
                for neighbor2 in neighbors[i+1:]:
                    if neighbor2 in adjacency[neighbor1]:
                        neighbor_edges += 1
            
            # Calculate clustering coefficient
            possible_edges = len(neighbors) * (len(neighbors) - 1)
            clustering_coeffs[str(node.id)] = neighbor_edges / possible_edges if possible_edges > 0 else 0.0
        
        # Calculate overall clustering coefficient
        clustering_values = list(clustering_coeffs.values())
        overall_clustering = sum(clustering_values) / len(clustering_values) if clustering_values else 0.0
        
        return {
            "clustering_coefficient": overall_clustering,
            "node_clustering": clustering_coeffs,
            "average_clustering": overall_clustering,
            "max_clustering": max(clustering_values) if clustering_values else 0.0,
            "min_clustering": min(clustering_values) if clustering_values else 0.0
        }
    
    def _calculate_clustering_coefficient(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> float:
        """Calculate global clustering coefficient."""
        clustering_analysis = self._analyze_clustering(nodes, edges)
        return clustering_analysis.get("clustering_coefficient", 0.0)
    
    def _analyze_components(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge], is_directed: bool) -> Dict[str, Any]:
        """Analyze connected components."""
        if not nodes:
            return {"component_count": 0}
        
        # Build adjacency list
        adjacency = defaultdict(list)
        for edge in edges:
            adjacency[str(edge.source_id)].append(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].append(str(edge.source_id))
        
        # Find connected components
        visited = set()
        components = []
        
        for node in nodes:
            if str(node.id) not in visited:
                component = []
                stack = [str(node.id)]
                visited.add(str(node.id))
                
                while stack:
                    current = stack.pop()
                    component.append(current)
                    
                    for neighbor in adjacency[current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
                
                components.append(component)
        
        # Calculate component statistics
        component_sizes = [len(comp) for comp in components]
        
        return {
            "component_count": len(components),
            "components": components,
            "component_sizes": component_sizes,
            "largest_component_size": max(component_sizes) if component_sizes else 0,
            "smallest_component_size": min(component_sizes) if component_sizes else 0,
            "average_component_size": sum(component_sizes) / len(component_sizes) if component_sizes else 0.0,
            "is_fully_connected": len(components) == 1
        }
    
    def _analyze_centrality(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze centrality measures."""
        if not nodes:
            return {}
        
        # Build adjacency list
        adjacency = defaultdict(list)
        for edge in edges:
            adjacency[str(edge.source_id)].append(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].append(str(edge.source_id))
        
        # Calculate degree centrality
        degree_centrality = {}
        for node in nodes:
            degree_centrality[str(node.id)] = len(adjacency[str(node.id)])
        
        # Normalize degree centrality
        max_degree = max(degree_centrality.values()) if degree_centrality else 1
        normalized_degree_centrality = {
            node_id: degree / max_degree 
            for node_id, degree in degree_centrality.items()
        }
        
        return {
            "degree_centrality": degree_centrality,
            "normalized_degree_centrality": normalized_degree_centrality,
            "highest_degree_nodes": [
                node_id for node_id, degree in degree_centrality.items() 
                if degree == max_degree
            ]
        }
    
    def _analyze_paths(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze path characteristics."""
        if len(nodes) <= 1:
            return {"average_path_length": 0.0, "diameter": 0}
        
        # Simplified path analysis
        density = self._calculate_density(len(nodes), len(edges), False)
        avg_path_length = self._calculate_average_path_length(nodes, edges)
        
        # Estimate diameter (simplified)
        diameter = int(len(nodes) / density) if density > 0 else len(nodes) - 1
        
        return {
            "average_path_length": avg_path_length,
            "diameter": diameter,
            "radius": diameter // 2,
            "longest_paths": []
        }
    
    def _analyze_topology(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge], is_directed: bool) -> Dict[str, Any]:
        """Analyze graph topology."""
        return {
            "graph_type": "directed" if is_directed else "undirected",
            "is_sparse": self._calculate_density(len(nodes), len(edges), is_directed) < 0.1,
            "is_dense": self._calculate_density(len(nodes), len(edges), is_directed) > 0.5,
            "has_self_loops": any(str(edge.source_id) == str(edge.target_id) for edge in edges),
            "is_complete": self._is_complete_graph(len(nodes), len(edges), is_directed),
            "is_regular": self._is_regular_graph(nodes, edges),
            "is_bipartite": self._is_bipartite_graph(nodes, edges)
        }
    
    def _is_complete_graph(self, node_count: int, edge_count: int, is_directed: bool) -> bool:
        """Check if graph is complete."""
        if node_count <= 1:
            return True
        
        max_edges = node_count * (node_count - 1)
        if not is_directed:
            max_edges = max_edges // 2
        
        return edge_count >= max_edges
    
    def _is_regular_graph(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> bool:
        """Check if graph is regular."""
        if not nodes:
            return True
        
        # Calculate degrees
        degrees = {}
        for node in nodes:
            degrees[str(node.id)] = 0
        
        for edge in edges:
            degrees[str(edge.source_id)] += 1
            if edge.bidirectional:
                degrees[str(edge.target_id)] += 1
        
        # Check if all degrees are equal
        degree_values = set(degrees.values())
        return len(degree_values) == 1
    
    def _is_bipartite_graph(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> bool:
        """Check if graph is bipartite."""
        if not nodes:
            return True
        
        # Build adjacency list
        adjacency = defaultdict(list)
        for edge in edges:
            adjacency[str(edge.source_id)].append(str(edge.target_id))
            if edge.bidirectional:
                adjacency[str(edge.target_id)].append(str(edge.source_id))
        
        # Try to color graph with 2 colors
        colors = {}
        
        def can_color(node_id: str, color: int) -> bool:
            for neighbor in adjacency[node_id]:
                if neighbor in colors and colors[neighbor] == color:
                    return False
            return True
        
        for node in nodes:
            node_id = str(node.id)
            for color in [0, 1]:
                if can_color(node_id, color):
                    colors[node_id] = color
                    break
            else:
                return False
        
        return True
    
    async def _analyze_nodes_detailed(self, nodes: List[KnowledgeNode]) -> Dict[str, Any]:
        """Analyze nodes in detail."""
        if not nodes:
            return {}
        
        # Node type distribution
        type_distribution = Counter(node.node_type for node in nodes)
        
        # Status distribution
        status_distribution = Counter(node.status for node in nodes)
        
        # Quality distribution
        quality_scores = [node.quality_score for node in nodes]
        confidence_scores = [node.confidence_score for node in nodes]
        
        return {
            "type_distribution": dict(type_distribution),
            "status_distribution": dict(status_distribution),
            "quality_metrics": {
                "average_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                "max_quality": max(quality_scores) if quality_scores else 0,
                "min_quality": min(quality_scores) if quality_scores else 0,
                "quality_distribution": Counter(quality_scores)
            },
            "confidence_metrics": {
                "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                "max_confidence": max(confidence_scores) if confidence_scores else 0,
                "min_confidence": min(confidence_scores) if confidence_scores else 0,
                "confidence_distribution": Counter(confidence_scores)
            },
            "level_distribution": Counter(node.level for node in nodes),
            "keyword_analysis": self._analyze_keywords(nodes),
            "source_analysis": self._analyze_sources(nodes)
        }
    
    async def _analyze_edges_detailed(self, edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze edges in detail."""
        if not edges:
            return {}
        
        # Edge type distribution
        type_distribution = Counter(edge.edge_type for edge in edges)
        
        # Weight distribution
        weights = [edge.weight for edge in edges]
        confidences = [edge.confidence for edge in edges]
        strengths = [edge.strength for edge in edges]
        
        return {
            "type_distribution": dict(type_distribution),
            "weight_metrics": {
                "average_weight": sum(weights) / len(weights) if weights else 0,
                "max_weight": max(weights) if weights else 0,
                "min_weight": min(weights) if weights else 0,
                "weight_distribution": Counter(weights)
            },
            "confidence_metrics": {
                "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
                "max_confidence": max(confidences) if confidences else 0,
                "min_confidence": min(confidences) if confidences else 0,
                "confidence_distribution": Counter(confidences)
            },
            "strength_metrics": {
                "average_strength": sum(strengths) / len(strengths) if strengths else 0,
                "max_strength": max(strengths) if strengths else 0,
                "min_strength": min(strengths) if strengths else 0,
                "strength_distribution": Counter(strengths)
            },
            "bidirectional_ratio": len([e for e in edges if e.bidirectional]) / len(edges),
            "temporal_analysis": self._analyze_temporal_edges(edges)
        }
    
    def _analyze_keywords(self, nodes: List[KnowledgeNode]) -> Dict[str, Any]:
        """Analyze keywords across nodes."""
        all_keywords = []
        for node in nodes:
            if node.keywords:
                all_keywords.extend(node.keywords)
        
        keyword_counts = Counter(all_keywords)
        
        return {
            "total_keywords": len(all_keywords),
            "unique_keywords": len(keyword_counts),
            "most_common": keyword_counts.most_common(10),
            "keyword_distribution": dict(keyword_counts)
        }
    
    def _analyze_sources(self, nodes: List[KnowledgeNode]) -> Dict[str, Any]:
        """Analyze sources across nodes."""
        sources = [node.source for node in nodes if node.source]
        authors = [node.author for node in nodes if node.author]
        
        return {
            "source_distribution": Counter(sources),
            "author_distribution": Counter(authors),
            "total_sources": len(set(sources)),
            "total_authors": len(set(authors))
        }
    
    def _analyze_temporal_edges(self, edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze temporal aspects of edges."""
        temporal_edges = [edge for edge in edges if edge.valid_from or edge.valid_to]
        
        if not temporal_edges:
            return {"temporal_edges": 0, "permanent_edges": len(edges)}
        
        return {
            "temporal_edges": len(temporal_edges),
            "permanent_edges": len(edges) - len(temporal_edges),
            "valid_from_range": [edge.valid_from.isoformat() for edge in temporal_edges if edge.valid_from],
            "valid_to_range": [edge.valid_to.isoformat() for edge in temporal_edges if edge.valid_to]
        }
    
    def _analyze_subgraphs(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze subgraphs."""
        # Simplified subgraph analysis
        return {
            "potential_subgraphs": len(nodes) // 3,  # Estimate
            "largest_potential_subgraph": len(nodes) // 2,
            "subgraph_density": self._calculate_density(len(nodes), len(edges), False)
        }
    
    def _analyze_motifs(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> Dict[str, Any]:
        """Analyze graph motifs."""
        # Simplified motif analysis
        return {
            "triangles": self._count_triangles(nodes, edges),
            "squares": self._count_squares(nodes, edges),
            "stars": self._count_stars(nodes, edges)
        }
    
    def _count_triangles(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> int:
        """Count triangle motifs."""
        # Simplified triangle counting
        return len(edges) // 3  # Estimate
    
    def _count_squares(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> int:
        """Count square motifs."""
        return len(edges) // 4  # Estimate
    
    def _count_stars(self, nodes: List[KnowledgeNode], edges: List[KnowledgeEdge]) -> int:
        """Count star motifs."""
        if not nodes:
            return 0
        
        # Count nodes with degree > 2
        degrees = {}
        for node in nodes:
            degrees[str(node.id)] = 0
        
        for edge in edges:
            degrees[str(edge.source_id)] += 1
            if edge.bidirectional:
                degrees[str(edge.target_id)] += 1
        
        return len([d for d in degrees.values() if d > 2])
    
    async def _analyze_time_series(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze time series data."""
        # Placeholder for time series analysis
        return {
            "time_range": time_range,
            "trend_analysis": {},
            "seasonal_patterns": {},
            "anomaly_detection": []
        }
    
    async def _analyze_bottlenecks(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze performance bottlenecks."""
        # Placeholder for bottleneck analysis
        return {
            "bottleneck_nodes": [],
            "bottleneck_edges": [],
            "performance_issues": []
        }
    
    async def _generate_optimization_suggestions(self, graph_id: str) -> List[str]:
        """Generate optimization suggestions."""
        # Placeholder for optimization suggestions
        return [
            "Consider adding more edges to increase connectivity",
            "Review node clustering for better organization",
            "Optimize traversal algorithms for better performance"
        ]
    
    async def _analyze_access_patterns(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze access patterns."""
        # Placeholder for access pattern analysis
        return {
            "peak_hours": [],
            "popular_nodes": [],
            "access_frequency": {}
        }
    
    async def _analyze_node_usage(self, nodes: List[KnowledgeNode], time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze node usage."""
        if not nodes:
            return {}
        
        access_counts = [node.access_count for node in nodes]
        
        return {
            "total_accesses": sum(access_counts),
            "average_accesses": sum(access_counts) / len(access_counts) if access_counts else 0,
            "most_accessed": max(access_counts) if access_counts else 0,
            "least_accessed": min(access_counts) if access_counts else 0,
            "access_distribution": Counter(access_counts)
        }
    
    async def _analyze_edge_usage(self, edges: List[KnowledgeEdge], time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze edge usage."""
        if not edges:
            return {}
        
        access_counts = [edge.access_count for edge in edges]
        
        return {
            "total_accesses": sum(access_counts),
            "average_accesses": sum(access_counts) / len(access_counts) if access_counts else 0,
            "most_accessed": max(access_counts) if access_counts else 0,
            "least_accessed": min(access_counts) if access_counts else 0,
            "access_distribution": Counter(access_counts)
        }
    
    async def _analyze_query_patterns(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze query patterns."""
        # Placeholder for query pattern analysis
        return {
            "query_types": {},
            "query_frequency": {},
            "popular_queries": []
        }
    
    async def _analyze_user_behavior(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze user behavior."""
        # Placeholder for user behavior analysis
        return {
            "user_segments": [],
            "behavior_patterns": {},
            "engagement_metrics": {}
        }
    
    async def _analyze_growth_metrics(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze growth metrics."""
        # Placeholder for growth analysis
        return {
            "growth_rate": 0.0,
            "new_nodes": 0,
            "new_edges": 0,
            "growth_trend": "stable"
        }
    
    async def _analyze_engagement_metrics(self, graph_id: str, time_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze engagement metrics."""
        # Placeholder for engagement analysis
        return {
            "engagement_score": 0.0,
            "retention_rate": 0.0,
            "interaction_patterns": {}
        }
    
    async def _get_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """Get graph by ID."""
        query = select(KnowledgeGraph).where(KnowledgeGraph.id == uuid.UUID(graph_id))
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_graph_nodes(self, graph_id: str) -> List[KnowledgeNode]:
        """Get all nodes for a graph."""
        query = select(KnowledgeNode).where(KnowledgeNode.root_id == uuid.UUID(graph_id))
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def _get_graph_edges(self, graph_id: str) -> List[KnowledgeEdge]:
        """Get all edges for a graph."""
        # This would need a join with nodes to get edges for a specific graph
        # Placeholder implementation
        query = select(KnowledgeEdge).limit(1000)
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is valid."""
        if cache_key not in self.analytics_cache:
            return False
        
        if self.last_cache_update is None:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.last_cache_update).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache analysis result."""
        self.analytics_cache[cache_key] = result
        self.last_cache_update = datetime.now(timezone.utc)
    
    def clear_cache(self) -> None:
        """Clear analytics cache."""
        self.analytics_cache.clear()
        self.last_cache_update = None
        
        logger.info("Analytics cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.analytics_cache),
            "cache_ttl": self.cache_ttl,
            "last_update": self.last_cache_update.isoformat() if self.last_cache_update else None
        }
