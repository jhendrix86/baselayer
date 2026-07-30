"""
Tests for CODX Knowledge Engine Models

Tests for SQLAlchemy models and Pydantic schemas.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from engines.codx.models.knowledge_node import KnowledgeNode, NodeType, NodeStatus
from engines.codx.models.knowledge_edge import KnowledgeEdge, EdgeType, EdgeStatus
from engines.codx.models.knowledge_graph import KnowledgeGraph, GraphType, GraphStatus
from engines.codx.models.vector_embedding import VectorEmbedding, EmbeddingModel, EmbeddingStatus
from engines.codx.models.schemas import (
    KnowledgeNodeCreate, KnowledgeNodeUpdate, KnowledgeNodeResponse,
    KnowledgeEdgeCreate, KnowledgeEdgeUpdate, KnowledgeEdgeResponse,
    KnowledgeGraphCreate, KnowledgeGraphUpdate, KnowledgeGraphResponse,
    VectorEmbeddingCreate, VectorEmbeddingUpdate, VectorEmbeddingResponse
)
from .conftest import (
    sample_knowledge_node, sample_knowledge_edge, sample_knowledge_graph,
    sample_vector_embedding, sample_knowledge_node_create,
    sample_knowledge_edge_create, sample_knowledge_graph_create,
    sample_vector_embedding_create
)


class TestKnowledgeNode:
    """Test KnowledgeNode model."""
    
    def test_knowledge_node_creation(self, sample_knowledge_node):
        """Test KnowledgeNode model creation."""
        assert sample_knowledge_node.id is not None
        assert sample_knowledge_node.title == "Machine Learning"
        assert sample_knowledge_node.node_type == NodeType.CONCEPT
        assert sample_knowledge_node.status == NodeStatus.ACTIVE
        assert sample_knowledge_node.confidence_score == 0.9
        assert sample_knowledge_node.quality_score == 0.85
        assert sample_knowledge_node.relevance_score == 0.8
        assert sample_knowledge_node.level == 1
        assert sample_knowledge_node.access_count == 10
        assert sample_knowledge_node.update_count == 2
    
    def test_knowledge_node_to_dict(self, sample_knowledge_node):
        """Test KnowledgeNode to_dict method."""
        node_dict = sample_knowledge_node.to_dict()
        
        assert isinstance(node_dict, dict)
        assert node_dict["id"] == str(sample_knowledge_node.id)
        assert node_dict["title"] == sample_knowledge_node.title
        assert node_dict["node_type"] == sample_knowledge_node.node_type
        assert node_dict["status"] == sample_knowledge_node.status
        assert node_dict["confidence_score"] == sample_knowledge_node.confidence_score
        assert node_dict["quality_score"] == sample_knowledge_node.quality_score
        assert node_dict["relevance_score"] == sample_knowledge_node.relevance_score
    
    def test_knowledge_node_to_tree(self, sample_knowledge_node):
        """Test KnowledgeNode to_tree method."""
        tree_data = sample_knowledge_node.to_tree()
        
        assert isinstance(tree_data, dict)
        assert tree_data["id"] == str(sample_knowledge_node.id)
        assert tree_data["title"] == sample_knowledge_node.title
        assert tree_data["node_type"] == sample_knowledge_node.node_type
        assert tree_data["level"] == sample_knowledge_node.level
        assert tree_data["path"] == sample_knowledge_node.path
        assert "children" in tree_data
    
    def test_knowledge_node_increment_access(self, sample_knowledge_node):
        """Test KnowledgeNode increment_access_count method."""
        initial_count = sample_knowledge_node.access_count
        sample_knowledge_node.increment_access_count()
        
        assert sample_knowledge_node.access_count == initial_count + 1
        assert sample_knowledge_node.last_accessed is not None
    
    def test_knowledge_node_increment_update(self, sample_knowledge_node):
        """Test KnowledgeNode increment_update_count method."""
        initial_count = sample_knowledge_node.update_count
        sample_knowledge_node.increment_update_count()
        
        assert sample_knowledge_node.update_count == initial_count + 1
        assert sample_knowledge_node.last_updated is not None
    
    def test_knowledge_node_validation(self):
        """Test KnowledgeNode validation."""
        # Test valid node
        node = KnowledgeNode(
            title="Test Node",
            node_type=NodeType.CONCEPT,
            content="Test content"
        )
        assert node.title == "Test Node"
        assert node.node_type == NodeType.CONCEPT
        
        # Test invalid node type
        with pytest.raises(ValueError):
            KnowledgeNode(
                title="Test Node",
                node_type="invalid_type",
                content="Test content"
            )


class TestKnowledgeEdge:
    """Test KnowledgeEdge model."""
    
    def test_knowledge_edge_creation(self, sample_knowledge_edge):
        """Test KnowledgeEdge model creation."""
        assert sample_knowledge_edge.id is not None
        assert sample_knowledge_edge.edge_type == EdgeType.RELATES_TO
        assert sample_knowledge_edge.status == EdgeStatus.ACTIVE
        assert sample_knowledge_edge.weight == 0.8
        assert sample_knowledge_edge.confidence == 0.9
        assert sample_knowledge_edge.strength == 0.7
        assert sample_knowledge_edge.bidirectional is False
        assert sample_knowledge_edge.access_count == 5
        assert sample_knowledge_edge.update_count == 1
    
    def test_knowledge_edge_to_dict(self, sample_knowledge_edge):
        """Test KnowledgeEdge to_dict method."""
        edge_dict = sample_knowledge_edge.to_dict()
        
        assert isinstance(edge_dict, dict)
        assert edge_dict["id"] == str(sample_knowledge_edge.id)
        assert edge_dict["source_id"] == str(sample_knowledge_edge.source_id)
        assert edge_dict["target_id"] == str(sample_knowledge_edge.target_id)
        assert edge_dict["edge_type"] == sample_knowledge_edge.edge_type
        assert edge_dict["weight"] == sample_knowledge_edge.weight
        assert edge_dict["confidence"] == sample_knowledge_edge.confidence
    
    def test_knowledge_edge_to_cypher(self, sample_knowledge_edge):
        """Test KnowledgeEdge to_cypher method."""
        cypher_query = sample_knowledge_edge.to_cypher()
        
        assert isinstance(cypher_query, str)
        assert "CREATE" in cypher_query
        assert "MATCH" in cypher_query
        assert str(sample_knowledge_edge.source_id) in cypher_query
        assert str(sample_knowledge_edge.target_id) in cypher_query
    
    def test_knowledge_edge_to_graphviz(self, sample_knowledge_edge):
        """Test KnowledgeEdge to_graphviz method."""
        graphviz_data = sample_knowledge_edge.to_graphviz()
        
        assert isinstance(graphviz_data, str)
        assert "->" in graphviz_data
        assert str(sample_knowledge_edge.source_id) in graphviz_data
        assert str(sample_knowledge_edge.target_id) in graphviz_data
    
    def test_knowledge_edge_to_networkx(self, sample_knowledge_edge):
        """Test KnowledgeEdge to_networkx method."""
        nx_data = sample_knowledge_edge.to_networkx()
        
        assert isinstance(nx_data, dict)
        assert "source" in nx_data
        assert "target" in nx_data
        assert nx_data["source"] == str(sample_knowledge_edge.source_id)
        assert nx_data["target"] == str(sample_knowledge_edge.target_id)
    
    def test_knowledge_edge_similarity(self, sample_knowledge_edge):
        """Test KnowledgeEdge calculate_similarity method."""
        other_edge = KnowledgeEdge(
            source_id=sample_knowledge_edge.source_id,
            target_id=sample_knowledge_edge.target_id,
            edge_type=EdgeType.RELATES_TO,
            weight=0.8,
            confidence=0.9
        )
        
        similarity = sample_knowledge_edge.calculate_similarity(other_edge)
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
    
    def test_knowledge_edge_increment_access(self, sample_knowledge_edge):
        """Test KnowledgeEdge increment_access_count method."""
        initial_count = sample_knowledge_edge.access_count
        sample_knowledge_edge.increment_access_count()
        
        assert sample_knowledge_edge.access_count == initial_count + 1
        assert sample_knowledge_edge.last_accessed is not None
    
    def test_knowledge_edge_increment_update(self, sample_knowledge_edge):
        """Test KnowledgeEdge increment_update_count method."""
        initial_count = sample_knowledge_edge.update_count
        sample_knowledge_edge.increment_update_count()
        
        assert sample_knowledge_edge.update_count == initial_count + 1
        assert sample_knowledge_edge.last_updated is not None


class TestKnowledgeGraph:
    """Test KnowledgeGraph model."""
    
    def test_knowledge_graph_creation(self, sample_knowledge_graph):
        """Test KnowledgeGraph model creation."""
        assert sample_knowledge_graph.id is not None
        assert sample_knowledge_graph.name == "Computer Science Knowledge Graph"
        assert sample_knowledge_graph.graph_type == GraphType.CONCEPT_GRAPH
        assert sample_knowledge_graph.status == GraphStatus.ACTIVE
        assert sample_knowledge_graph.node_count == 100
        assert sample_knowledge_graph.edge_count == 250
        assert sample_knowledge_graph.max_depth == 5
        assert sample_knowledge_graph.is_connected is True
        assert sample_knowledge_graph.is_cyclic is True
    
    def test_knowledge_graph_to_dict(self, sample_knowledge_graph):
        """Test KnowledgeGraph to_dict method."""
        graph_dict = sample_knowledge_graph.to_dict()
        
        assert isinstance(graph_dict, dict)
        assert graph_dict["id"] == str(sample_knowledge_graph.id)
        assert graph_dict["name"] == sample_knowledge_graph.name
        assert graph_dict["graph_type"] == sample_knowledge_graph.graph_type
        assert graph_dict["status"] == sample_knowledge_graph.status
        assert graph_dict["node_count"] == sample_knowledge_graph.node_count
        assert graph_dict["edge_count"] == sample_knowledge_graph.edge_count
    
    def test_knowledge_graph_to_networkx(self, sample_knowledge_graph):
        """Test KnowledgeGraph to_networkx method."""
        nx_data = sample_knowledge_graph.to_networkx()
        
        assert isinstance(nx_data, dict)
        assert "nodes" in nx_data
        assert "edges" in nx_data
        assert isinstance(nx_data["nodes"], list)
        assert isinstance(nx_data["edges"], list)
    
    def test_knowledge_graph_to_cypher_schema(self, sample_knowledge_graph):
        """Test KnowledgeGraph to_cypher_schema method."""
        cypher_schema = sample_knowledge_graph.to_cypher_schema()
        
        assert isinstance(cypher_schema, str)
        assert "CREATE" in cypher_schema
        assert "NODE" in cypher_schema
        assert "RELATIONSHIP" in cypher_schema
    
    def test_knowledge_graph_calculate_density(self, sample_knowledge_graph):
        """Test KnowledgeGraph calculate_density method."""
        density = sample_knowledge_graph.calculate_density()
        
        assert isinstance(density, float)
        assert 0.0 <= density <= 1.0
    
    def test_knowledge_graph_calculate_clustering(self, sample_knowledge_graph):
        """Test KnowledgeGraph calculate_clustering_coefficient method."""
        clustering = sample_knowledge_graph.calculate_clustering_coefficient()
        
        assert isinstance(clustering, float)
        assert 0.0 <= clustering <= 1.0
    
    def test_knowledge_graph_validate_structure(self, sample_knowledge_graph):
        """Test KnowledgeGraph validate_structure method."""
        validation = sample_knowledge_graph.validate_structure()
        
        assert isinstance(validation, dict)
        assert "valid" in validation
        assert "errors" in validation
        assert isinstance(validation["errors"], list)


class TestVectorEmbedding:
    """Test VectorEmbedding model."""
    
    def test_vector_embedding_creation(self, sample_vector_embedding):
        """Test VectorEmbedding model creation."""
        assert sample_vector_embedding.id is not None
        assert sample_vector_embedding.text == "Machine learning is a subset of artificial intelligence"
        assert sample_vector_embedding.embedding_model == "text-embedding-ada-002"
        assert sample_vector_embedding.embedding_dimension == 1536
        assert len(sample_vector_embedding.embedding_vector) == 1536
        assert sample_vector_embedding.source_type == "node"
        assert sample_vector_embedding.status == EmbeddingStatus.ACTIVE
        assert sample_vector_embedding.similarity_threshold == 0.7
        assert sample_vector_embedding.retrieval_score == 0.85
    
    def test_vector_embedding_to_dict(self, sample_vector_embedding):
        """Test VectorEmbedding to_dict method."""
        embedding_dict = sample_vector_embedding.to_dict()
        
        assert isinstance(embedding_dict, dict)
        assert embedding_dict["id"] == str(sample_vector_embedding.id)
        assert embedding_dict["text"] == sample_vector_embedding.text
        assert embedding_dict["embedding_model"] == sample_vector_embedding.embedding_model
        assert embedding_dict["embedding_dimension"] == sample_vector_embedding.embedding_dimension
        assert embedding_dict["status"] == sample_vector_embedding.status
    
    def test_vector_embedding_normalize(self, sample_vector_embedding):
        """Test VectorEmbedding normalize method."""
        sample_vector_embedding.normalize()
        
        # Check if vector is normalized (L2 norm should be 1.0)
        norm = sum(x * x for x in sample_vector_embedding.embedding_vector) ** 0.5
        assert abs(norm - 1.0) < 1e-6
    
    def test_vector_embedding_calculate_similarity(self, sample_vector_embedding):
        """Test VectorEmbedding calculate_similarity method."""
        other_embedding = VectorEmbedding(
            text="AI is transforming technology",
            embedding_model="text-embedding-ada-002",
            embedding_dimension=1536,
            embedding_vector=[0.1] * 1536
        )
        
        similarity = sample_vector_embedding.calculate_similarity(other_embedding)
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
    
    def test_vector_embedding_calculate_distance(self, sample_vector_embedding):
        """Test VectorEmbedding calculate_distance method."""
        other_embedding = VectorEmbedding(
            text="AI is transforming technology",
            embedding_model="text-embedding-ada-002",
            embedding_dimension=1536,
            embedding_vector=[0.1] * 1536
        )
        
        distance = sample_vector_embedding.calculate_distance(other_embedding)
        assert isinstance(distance, float)
        assert distance >= 0.0
    
    def test_vector_embedding_update_retrieval_score(self, sample_vector_embedding):
        """Test VectorEmbedding update_retrieval_score method."""
        new_score = 0.95
        sample_vector_embedding.update_retrieval_score(new_score)
        
        assert sample_vector_embedding.retrieval_score == new_score
        assert sample_vector_embedding.updated_at is not None


class TestSchemas:
    """Test Pydantic schemas."""
    
    def test_knowledge_node_create_schema(self, sample_knowledge_node_create):
        """Test KnowledgeNodeCreate schema."""
        node_create = KnowledgeNodeCreate(**sample_knowledge_node_create.dict())
        
        assert node_create.title == sample_knowledge_node_create.title
        assert node_create.node_type == sample_knowledge_node_create.node_type
        assert node_create.content == sample_knowledge_node_create.content
        assert node_create.confidence_score == sample_knowledge_node_create.confidence_score
        assert node_create.quality_score == sample_knowledge_node_create.quality_score
    
    def test_knowledge_node_response_schema(self, sample_knowledge_node):
        """Test KnowledgeNodeResponse schema."""
        node_response = KnowledgeNodeResponse(
            id=str(sample_knowledge_node.id),
            title=sample_knowledge_node.title,
            node_type=sample_knowledge_node.node_type,
            content=sample_knowledge_node.content,
            confidence_score=sample_knowledge_node.confidence_score,
            quality_score=sample_knowledge_node.quality_score,
            relevance_score=sample_knowledge_node.relevance_score,
            created_at=sample_knowledge_node.created_at,
            updated_at=sample_knowledge_node.updated_at
        )
        
        assert node_response.id == str(sample_knowledge_node.id)
        assert node_response.title == sample_knowledge_node.title
        assert node_response.node_type == sample_knowledge_node.node_type
        assert node_response.confidence_score == sample_knowledge_node.confidence_score
    
    def test_knowledge_edge_create_schema(self, sample_knowledge_edge_create):
        """Test KnowledgeEdgeCreate schema."""
        edge_create = KnowledgeEdgeCreate(**sample_knowledge_edge_create.dict())
        
        assert edge_create.source_id == sample_knowledge_edge_create.source_id
        assert edge_create.target_id == sample_knowledge_edge_create.target_id
        assert edge_create.edge_type == sample_knowledge_edge_create.edge_type
        assert edge_create.weight == sample_knowledge_edge_create.weight
        assert edge_create.confidence == sample_knowledge_edge_create.confidence
    
    def test_knowledge_edge_response_schema(self, sample_knowledge_edge):
        """Test KnowledgeEdgeResponse schema."""
        edge_response = KnowledgeEdgeResponse(
            id=str(sample_knowledge_edge.id),
            source_id=str(sample_knowledge_edge.source_id),
            target_id=str(sample_knowledge_edge.target_id),
            edge_type=sample_knowledge_edge.edge_type,
            weight=sample_knowledge_edge.weight,
            confidence=sample_knowledge_edge.confidence,
            strength=sample_knowledge_edge.strength,
            bidirectional=sample_knowledge_edge.bidirectional,
            created_at=sample_knowledge_edge.created_at,
            updated_at=sample_knowledge_edge.updated_at
        )
        
        assert edge_response.id == str(sample_knowledge_edge.id)
        assert edge_response.source_id == str(sample_knowledge_edge.source_id)
        assert edge_response.target_id == str(sample_knowledge_edge.target_id)
        assert edge_response.edge_type == sample_knowledge_edge.edge_type
    
    def test_knowledge_graph_create_schema(self, sample_knowledge_graph_create):
        """Test KnowledgeGraphCreate schema."""
        graph_create = KnowledgeGraphCreate(**sample_knowledge_graph_create.dict())
        
        assert graph_create.name == sample_knowledge_graph_create.name
        assert graph_create.graph_type == sample_knowledge_graph_create.graph_type
        assert graph_create.description == sample_knowledge_graph_create.description
        assert graph_create.root_node_id == sample_knowledge_graph_create.root_node_id
    
    def test_knowledge_graph_response_schema(self, sample_knowledge_graph):
        """Test KnowledgeGraphResponse schema."""
        graph_response = KnowledgeGraphResponse(
            id=str(sample_knowledge_graph.id),
            name=sample_knowledge_graph.name,
            graph_type=sample_knowledge_graph.graph_type,
            status=sample_knowledge_graph.status,
            node_count=sample_knowledge_graph.node_count,
            edge_count=sample_knowledge_graph.edge_count,
            created_at=sample_knowledge_graph.created_at,
            updated_at=sample_knowledge_graph.updated_at
        )
        
        assert graph_response.id == str(sample_knowledge_graph.id)
        assert graph_response.name == sample_knowledge_graph.name
        assert graph_response.graph_type == sample_knowledge_graph.graph_type
        assert graph_response.node_count == sample_knowledge_graph.node_count
    
    def test_vector_embedding_create_schema(self, sample_vector_embedding_create):
        """Test VectorEmbeddingCreate schema."""
        embedding_create = VectorEmbeddingCreate(**sample_vector_embedding_create.dict())
        
        assert embedding_create.text == sample_vector_embedding_create.text
        assert embedding_create.embedding_model == sample_vector_embedding_create.embedding_model
        assert embedding_create.embedding_dimension == sample_vector_embedding_create.embedding_dimension
        assert embedding_create.source_type == sample_vector_embedding_create.source_type
        assert embedding_create.similarity_threshold == sample_vector_embedding_create.similarity_threshold
    
    def test_vector_embedding_response_schema(self, sample_vector_embedding):
        """Test VectorEmbeddingResponse schema."""
        embedding_response = VectorEmbeddingResponse(
            id=str(sample_vector_embedding.id),
            text=sample_vector_embedding.text,
            embedding_model=sample_vector_embedding.embedding_model,
            embedding_dimension=sample_vector_embedding.embedding_dimension,
            source_type=sample_vector_embedding.source_type,
            similarity_threshold=sample_vector_embedding.similarity_threshold,
            retrieval_score=sample_vector_embedding.retrieval_score,
            status=sample_vector_embedding.status,
            created_at=sample_vector_embedding.created_at,
            updated_at=sample_vector_embedding.updated_at
        )
        
        assert embedding_response.id == str(sample_vector_embedding.id)
        assert embedding_response.text == sample_vector_embedding.text
        assert embedding_response.embedding_model == sample_vector_embedding.embedding_model
        assert embedding_response.similarity_threshold == sample_vector_embedding.similarity_threshold
    
    def test_schema_validation_errors(self):
        """Test schema validation errors."""
        # Test invalid node type
        with pytest.raises(ValidationError):
            KnowledgeNodeCreate(
                title="Test",
                node_type="invalid_type",
                content="Test content"
            )
        
        # Test invalid confidence score
        with pytest.raises(ValidationError):
            KnowledgeNodeCreate(
                title="Test",
                node_type=NodeType.CONCEPT,
                content="Test content",
                confidence_score=1.5  # Invalid: > 1.0
            )
        
        # Test invalid edge weight
        with pytest.raises(ValidationError):
            KnowledgeEdgeCreate(
                source_id=str(uuid.uuid4()),
                target_id=str(uuid.uuid4()),
                edge_type=EdgeType.RELATES_TO,
                weight=-1.0  # Invalid: < 0
            )
        
        # Test invalid embedding dimension
        with pytest.raises(ValidationError):
            VectorEmbeddingCreate(
                text="Test",
                embedding_model="text-embedding-ada-002",
                embedding_dimension=-1,  # Invalid: < 0
                embedding_vector=[0.1] * 1536
            )
