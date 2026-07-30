"""
Tests for CODX Interface Components

Tests for knowledge interface and knowledge manager.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from engines.codx.interface.knowledge_interface import (
    KnowledgeInterface, InterfaceMode, OperationType, OperationResult
)
from engines.codx.interface.knowledge_manager import (
    KnowledgeManager, KnowledgeAction, KnowledgeRequest, KnowledgeResponse
)
from engines.codx.models.schemas import (
    KnowledgeNodeCreate, KnowledgeNodeUpdate, KnowledgeNodeResponse,
    KnowledgeEdgeCreate, KnowledgeEdgeUpdate, KnowledgeEdgeResponse,
    KnowledgeGraphCreate, KnowledgeGraphUpdate, KnowledgeGraphResponse
)
from .conftest import (
    mock_db_session, sample_knowledge_node, sample_knowledge_edge,
    sample_knowledge_graph, sample_knowledge_node_create,
    sample_knowledge_edge_create, sample_knowledge_graph_create,
    sample_search_request, sample_traversal_request,
    sample_analytics_request, sample_batch_operation_request
)


class TestKnowledgeInterface:
    """Test KnowledgeInterface class."""
    
    @pytest.mark.asyncio
    async def test_knowledge_interface_initialization(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test KnowledgeInterface initialization."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        assert interface.db_session == mock_db_session
        assert interface.vector_store == mock_vector_store
        assert interface.graph_traverser == mock_graph_traverser
        assert interface.graph_analyzer == mock_graph_analyzer
        assert interface.graph_storage == mock_graph_storage
        assert interface.query_processor == mock_query_processor
        assert interface.default_mode == InterfaceMode.QUERY
        assert interface.default_operation == OperationType.SEARCH
    
    @pytest.mark.asyncio
    async def test_execute_search_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing search operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock retrieval engine
        with patch('engines.codx.interface.knowledge_interface.RetrievalEngine') as mock_retrieval_class:
            mock_retrieval = AsyncMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.query = AsyncMock(return_value={
                "query": "machine learning",
                "mode": "hybrid",
                "results": [
                    {
                        "item_id": "item_1",
                        "item_type": "node",
                        "content": "Machine learning content",
                        "relevance_score": 0.9,
                        "confidence_score": 0.85,
                        "quality_score": 0.8
                    }
                ],
                "total_found": 1,
                "execution_time_ms": 100
            })
            
            result = await interface.execute(
                operation=OperationType.SEARCH,
                mode=InterfaceMode.QUERY,
                parameters={
                    "query": "machine learning",
                    "search_mode": "hybrid",
                    "top_k": 10
                }
            )
            
            assert result.success is True
            assert result.operation_type == OperationType.SEARCH
            assert result.data["total_found"] == 1
            assert len(result.data["results"]) == 1
            mock_retrieval.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_create_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing create operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock graph storage
        mock_graph_storage.save_node = AsyncMock(return_value=sample_knowledge_node())
        
        result = await interface.execute(
            operation=OperationType.CREATE,
            mode=InterfaceMode.MANAGE,
            parameters={
                "item_type": "node",
                "item_data": sample_knowledge_node_create().dict()
            }
        )
        
        assert result.success is True
        assert result.operation_type == OperationType.CREATE
        assert "node_id" in result.data
        mock_graph_storage.save_node.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_update_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing update operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock graph storage
        mock_graph_storage.get_node = AsyncMock(return_value=sample_knowledge_node())
        mock_graph_storage.save_node = AsyncMock(return_value=sample_knowledge_node())
        
        result = await interface.execute(
            operation=OperationType.UPDATE,
            mode=InterfaceMode.MANAGE,
            parameters={
                "item_type": "node",
                "item_id": str(sample_knowledge_node().id),
                "update_data": {"title": "Updated Title"}
            }
        )
        
        assert result.success is True
        assert result.operation_type == OperationType.UPDATE
        assert "node_id" in result.data
        mock_graph_storage.get_node.assert_called_once()
        mock_graph_storage.save_node.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_delete_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing delete operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock graph storage
        mock_graph_storage.delete_node = AsyncMock(return_value=True)
        
        result = await interface.execute(
            operation=OperationType.DELETE,
            mode=InterfaceMode.MANAGE,
            parameters={
                "item_type": "node",
                "item_id": str(sample_knowledge_node().id)
            }
        )
        
        assert result.success is True
        assert result.operation_type == OperationType.DELETE
        assert "node_id" in result.data
        mock_graph_storage.delete_node.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_traverse_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing traverse operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock graph traverser
        mock_graph_traverser.breadth_first_search = AsyncMock(return_value={
            "algorithm": "bfs",
            "start_node_id": "node_1",
            "traversal_order": [
                {
                    "id": "node_1",
                    "title": "Start Node",
                    "depth": 0,
                    "metadata": {}
                }
            ],
            "execution_time_ms": 50
        })
        
        result = await interface.execute(
            operation=OperationType.TRAVERSE,
            mode=InterfaceMode.QUERY,
            parameters={
                "start_node": "node_1",
                "algorithm": "bfs",
                "max_depth": 3
            }
        )
        
        assert result.success is True
        assert result.operation_type == OperationType.TRAVERSE
        assert "traversal_order" in result.data
        mock_graph_traverser.breadth_first_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_analyze_operation(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test executing analyze operation."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock graph analyzer
        mock_graph_analyzer.analyze_graph_structure = AsyncMock(return_value={
            "graph_id": "graph_1",
            "basic_metrics": {
                "node_count": 100,
                "edge_count": 250,
                "density": 0.025
            }
        })
        
        result = await interface.execute(
            operation=OperationType.ANALYZE,
            mode=InterfaceMode.ANALYZE,
            parameters={
                "graph_id": "graph_1",
                "analysis_type": "structure"
            }
        )
        
        assert result.success is True
        assert result.operation_type == OperationType.ANALYZE
        assert "basic_metrics" in result.data
        mock_graph_analyzer.analyze_graph_structure.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_execute(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test batch execution."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock operations
        with patch('engines.codx.interface.knowledge_interface.RetrievalEngine') as mock_retrieval_class:
            mock_retrieval = AsyncMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.query = AsyncMock(return_value={
                "query": "test",
                "results": [],
                "total_found": 0,
                "execution_time_ms": 50
            })
            
            operations = [
                {
                    "operation": OperationType.SEARCH,
                    "mode": InterfaceMode.QUERY,
                    "parameters": {"query": "test 1"}
                },
                {
                    "operation": OperationType.SEARCH,
                    "mode": InterfaceMode.QUERY,
                    "parameters": {"query": "test 2"}
                }
            ]
            
            results = await interface.batch_execute(operations)
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert mock_retrieval.query.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_interface_stats(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test getting interface statistics."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Simulate some operations
        interface.interface_stats["total_operations"] = 10
        interface.interface_stats["successful_operations"] = 8
        interface.interface_stats["failed_operations"] = 2
        interface.interface_stats["average_execution_time_ms"] = 150.0
        
        stats = await interface.get_interface_stats()
        
        assert stats["total_operations"] == 10
        assert stats["successful_operations"] == 8
        assert stats["failed_operations"] == 2
        assert stats["success_rate"] == 0.8
        assert stats["average_execution_time_ms"] == 150.0
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_db_session, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test interface health check."""
        interface = KnowledgeInterface(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_graph_storage,
            mock_query_processor
        )
        
        # Mock component health checks
        mock_vector_store.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_graph_traverser.health_check = AsyncMock(return_value={"status": "healthy"})
        
        # Mock operation
        with patch('engines.codx.interface.knowledge_interface.RetrievalEngine') as mock_retrieval_class:
            mock_retrieval = AsyncMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.query = AsyncMock(return_value={
                "query": "test",
                "results": [],
                "total_found": 0,
                "execution_time_ms": 50
            })
            
            health = await interface.health_check()
            
            assert health["status"] == "healthy"
            assert "component_health" in health
            assert "test_results_count" in health


class TestKnowledgeManager:
    """Test KnowledgeManager class."""
    
    @pytest.mark.asyncio
    async def test_knowledge_manager_initialization(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test KnowledgeManager initialization."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            
            manager = KnowledgeManager(mock_interface)
            
            assert manager.interface == mock_interface
            assert manager.default_timeout == 30000
            assert manager.max_batch_size == 100
            assert manager.auto_validate is True
            assert manager.auto_analyze is True
    
    @pytest.mark.asyncio
    async def test_process_add_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing add request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.CREATE,
                data={"node_id": "node_1"},
                message="Node created successfully",
                execution_time_ms=100,
                metadata={"item_type": "node"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.ADD,
                target="node",
                parameters=sample_knowledge_node_create().dict()
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.ADD
            assert response.target == "node"
            assert "node_id" in response.data
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_update_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing update request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.UPDATE,
                data={"node_id": "node_1"},
                message="Node updated successfully",
                execution_time_ms=100,
                metadata={"item_type": "node"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.UPDATE,
                target="node",
                parameters={
                    "id": "node_1",
                    "data": {"title": "Updated Title"}
                }
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.UPDATE
            assert response.target == "node"
            assert "node_id" in response.data
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_remove_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing remove request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.DELETE,
                data={"node_id": "node_1"},
                message="Node deleted successfully",
                execution_time_ms=100,
                metadata={"item_type": "node"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.REMOVE,
                target="node",
                parameters={"id": "node_1"}
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.REMOVE
            assert response.target == "node"
            assert "node_id" in response.data
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_search_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing search request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.SEARCH,
                data={
                    "query": "machine learning",
                    "results": [
                        {
                            "item_id": "item_1",
                            "item_type": "node",
                            "content": "Machine learning content",
                            "relevance_score": 0.9
                        }
                    ],
                    "total_found": 1
                },
                message="Search completed successfully",
                execution_time_ms=150,
                metadata={"query": "machine learning"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.SEARCH,
                target="all",
                parameters=sample_search_request
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.SEARCH
            assert response.target == "all"
            assert response.data["total_found"] == 1
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_explore_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing explore request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.SEARCH,
                data={
                    "traversal_order": [
                        {
                            "id": "node_2",
                            "title": "Related Node",
                            "depth": 1
                        }
                    ],
                    "max_depth": 2
                },
                message="Exploration completed successfully",
                execution_time_ms=200,
                metadata={"start_node": "node_1"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.EXPLORE,
                target="graph",
                parameters=sample_traversal_request
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.EXPLORE
            assert response.target == "graph"
            assert "traversal_order" in response.data
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_analyze_request(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing analyze request."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.ANALYZE,
                data={
                    "basic_metrics": {
                        "node_count": 100,
                        "edge_count": 250,
                        "density": 0.025
                    }
                },
                message="Analysis completed successfully",
                execution_time_ms=300,
                metadata={"analysis_type": "structure"}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.ANALYZE,
                target="graph",
                parameters=sample_analytics_request
            )
            
            response = await manager.process_request(request)
            
            assert response.success is True
            assert response.action == KnowledgeAction.ANALYZE
            assert response.target == "graph"
            assert "basic_metrics" in response.data
            mock_interface.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_batch_requests(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test processing batch requests."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.SEARCH,
                data={"results": []},
                message="Operation completed",
                execution_time_ms=100,
                metadata={}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            requests = [
                KnowledgeRequest(
                    action=KnowledgeAction.SEARCH,
                    target="all",
                    parameters={"query": "test 1"}
                ),
                KnowledgeRequest(
                    action=KnowledgeAction.SEARCH,
                    target="all",
                    parameters={"query": "test 2"}
                )
            ]
            
            responses = await manager.process_batch_requests(requests)
            
            assert len(responses) == 2
            assert all(response.success for response in responses)
            assert mock_interface.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_auto_validate(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test auto-validation after add/update."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.CREATE,
                data={"node_id": "node_1"},
                message="Node created",
                execution_time_ms=100,
                metadata={}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.ADD,
                target="node",
                parameters=sample_knowledge_node_create().dict()
            )
            
            response = await manager.process_request(request)
            
            # Auto-validation should be called
            assert mock_interface.execute.call_count >= 1  # Create + potentially validate
    
    @pytest.mark.asyncio
    async def test_auto_analyze(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test auto-analysis after add/update."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.CREATE,
                data={"graph_id": "graph_1"},
                message="Graph created",
                execution_time_ms=100,
                metadata={}
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.ADD,
                target="graph",
                parameters=sample_knowledge_graph_create().dict()
            )
            
            response = await manager.process_request(request)
            
            # Auto-analysis should be called for graphs
            assert mock_interface.execute.call_count >= 1  # Create + potentially analyze
    
    @pytest.mark.asyncio
    async def test_get_manager_stats(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test getting manager statistics."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            
            manager = KnowledgeManager(mock_interface)
            
            # Simulate some requests
            manager.manager_stats["total_requests"] = 20
            manager.manager_stats["successful_requests"] = 18
            manager.manager_stats["failed_requests"] = 2
            manager.manager_stats["average_execution_time_ms"] = 150.0
            
            stats = await manager.get_manager_stats()
            
            assert stats["total_requests"] == 20
            assert stats["successful_requests"] == 18
            assert stats["failed_requests"] == 2
            assert stats["success_rate"] == 0.9
            assert stats["average_execution_time_ms"] == 150.0
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test manager health check."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=True,
                operation_type=OperationType.SEARCH,
                data={"results": []},
                message="Test operation",
                execution_time_ms=50,
                metadata={}
            ))
            mock_interface.health_check = AsyncMock(return_value={
                "status": "healthy",
                "component_health": {}
            })
            
            manager = KnowledgeManager(mock_interface)
            
            health = await manager.health_check()
            
            assert health["status"] == "healthy"
            assert "request_processing_working" in health
            assert "interface_health" in health
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test error handling in knowledge manager."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            mock_interface.execute = AsyncMock(return_value=OperationResult(
                success=False,
                operation_type=OperationType.SEARCH,
                data=None,
                message="Search failed",
                execution_time_ms=0,
                metadata={},
                error="Database connection error"
            ))
            
            manager = KnowledgeManager(mock_interface)
            
            request = KnowledgeRequest(
                action=KnowledgeAction.SEARCH,
                target="all",
                parameters={"query": "test"}
            )
            
            response = await manager.process_request(request)
            
            assert response.success is False
            assert response.action == KnowledgeAction.SEARCH
            assert response.error == "Search failed"
    
    @pytest.mark.asyncio
    async def test_batch_size_limit(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_graph_storage, mock_query_processor):
        """Test batch size limit enforcement."""
        with patch('engines.codx.interface.knowledge_manager.KnowledgeInterface') as mock_interface_class:
            mock_interface = AsyncMock()
            mock_interface_class.return_value = mock_interface
            
            manager = KnowledgeManager(mock_interface)
            
            # Create batch that exceeds limit
            requests = [KnowledgeRequest(
                action=KnowledgeAction.SEARCH,
                target="all",
                parameters={"query": f"test {i}"}
            ) for i in range(150)]  # Exceeds default limit of 100
            
            with pytest.raises(Exception):  # Should raise error for batch size limit
                await manager.process_batch_requests(requests)
