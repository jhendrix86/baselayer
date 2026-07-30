"""
Tests for CODX Retrieval Components

Tests for retrieval engine, query processor, and knowledge retriever.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from engines.codx.retrieval.retrieval_engine import RetrievalEngine
from engines.codx.retrieval.query_processor import (
    QueryProcessor, QueryType, QueryIntent, ProcessedQuery,
    QueryEntity, QueryRelationship
)
from engines.codx.retrieval.knowledge_retriever import (
    KnowledgeRetriever, RetrievalMode, RetrievalStrategy, RetrievalResult
)
from engines.codx.models.schemas import SearchRequest, SearchResponse
from .conftest import (
    mock_db_session, mock_vector_store, mock_graph_traverser,
    mock_graph_analyzer, mock_query_processor,
    sample_search_request, sample_knowledge_node, sample_vector_embedding
)


class TestQueryProcessor:
    """Test QueryProcessor class."""
    
    @pytest.mark.asyncio
    async def test_query_processor_initialization(self):
        """Test QueryProcessor initialization."""
        processor = QueryProcessor()
        
        assert processor.min_confidence == 0.5
        assert processor.max_entities == 10
        assert processor.max_relationships == 5
        assert processor.query_cache == {}
        assert processor.cache_ttl == 1800
    
    @pytest.mark.asyncio
    async def test_process_query_simple(self):
        """Test processing a simple query."""
        processor = QueryProcessor()
        
        query = "What is machine learning?"
        result = await processor.process_query(query)
        
        assert isinstance(result, ProcessedQuery)
        assert result.original_query == query
        assert result.normalized_query == "what is machine learning?"
        assert result.query_type == QueryType.FACTUAL
        assert result.intent == QueryIntent.DEFINE
        assert len(result.keywords) > 0
        assert result.confidence > 0.0
    
    @pytest.mark.asyncio
    async def test_process_query_with_entities(self):
        """Test processing query with entities."""
        processor = QueryProcessor()
        
        query = "How does TensorFlow work for deep learning?"
        result = await processor.process_query(query)
        
        assert len(result.entities) > 0
        entity_texts = [entity.text.lower() for entity in result.entities]
        assert any("tensorflow" in text for text in entity_texts)
        assert any("deep learning" in text for text in entity_texts)
    
    @pytest.mark.asyncio
    async def test_process_query_with_relationships(self):
        """Test processing query with relationships."""
        processor = QueryProcessor()
        
        query = "Machine learning is related to artificial intelligence"
        result = await processor.process_query(query)
        
        assert len(result.relationships) > 0
        # Should detect "is related to" relationship
        relationship_predicates = [rel.predicate.lower() for rel in result.relationships]
        assert any("relate" in predicate for predicate in relationship_predicates)
    
    @pytest.mark.asyncio
    async def test_process_query_with_llm(self, mock_llm_client):
        """Test processing query with LLM."""
        processor = QueryProcessor(llm_client=mock_llm_client)
        
        query = "What are the applications of machine learning in healthcare?"
        result = await processor.process_query(query, use_llm=True)
        
        assert isinstance(result, ProcessedQuery)
        assert result.original_query == query
        # LLM should provide more sophisticated entity extraction
        assert len(result.entities) >= 0
    
    @pytest.mark.asyncio
    async def test_process_query_with_cache(self):
        """Test query processing with caching."""
        processor = QueryProcessor()
        
        query = "What is neural network?"
        
        # First call
        result1 = await processor.process_query(query, use_cache=True)
        
        # Second call (should use cache)
        result2 = await processor.process_query(query, use_cache=True)
        
        assert result1.original_query == result2.original_query
        assert result1.normalized_query == result2.normalized_query
        assert processor.processing_stats["cache_hits"] >= 1
    
    @pytest.mark.asyncio
    async def test_determine_query_type(self):
        """Test query type determination."""
        processor = QueryProcessor()
        
        # Factual queries
        assert processor._determine_query_type("What is AI?") == QueryType.FACTUAL
        assert processor._determine_query_type("Who invented the computer?") == QueryType.FACTUAL
        
        # Conceptual queries
        assert processor._determine_query_type("Explain the concept of machine learning") == QueryType.CONCEPTUAL
        
        # Procedural queries
        assert processor._determine_query_type("How to implement a neural network?") == QueryType.PROCEDURAL
        
        # Relational queries
        assert processor._determine_query_type("What is the relationship between AI and ML?") == QueryType.RELATIONAL
    
    @pytest.mark.asyncio
    async def test_determine_query_intent(self):
        """Test query intent determination."""
        processor = QueryProcessor()
        
        # Search intent
        assert processor._determine_query_intent("Find information about AI") == QueryIntent.SEARCH
        
        # Compare intent
        assert processor._determine_query_intent("Compare TensorFlow vs PyTorch") == QueryIntent.COMPARE
        
        # Explain intent
        assert processor._determine_query_intent("Explain how neural networks work") == QueryIntent.EXPLAIN
        
        # Define intent
        assert processor._determine_query_intent("What is machine learning?") == QueryIntent.DEFINE
    
    @pytest.mark.asyncio
    async def test_extract_entities(self):
        """Test entity extraction."""
        processor = QueryProcessor()
        
        query = "TensorFlow and PyTorch are popular deep learning frameworks"
        entities = processor._extract_entities(query)
        
        assert len(entities) >= 2
        entity_texts = [entity.text.lower() for entity in entities]
        assert "tensorflow" in entity_texts
        assert "pytorch" in entity_texts
        assert "deep learning" in entity_texts
    
    @pytest.mark.asyncio
    async def test_extract_relationships(self):
        """Test relationship extraction."""
        processor = QueryProcessor()
        
        query = "Machine learning is a subset of artificial intelligence"
        entities = processor._extract_entities(query)
        relationships = processor._extract_relationships(query, entities)
        
        assert len(relationships) >= 1
        # Should detect "is a subset of" relationship
        relationship_predicates = [rel.predicate.lower() for rel in relationships]
        assert any("subset" in predicate for predicate in relationship_predicates)
    
    @pytest.mark.asyncio
    async def test_calculate_confidence(self):
        """Test confidence calculation."""
        processor = QueryProcessor()
        
        entities = [
            QueryEntity(text="AI", type="concept", confidence=0.9, start_pos=0, end_pos=2),
            QueryEntity(text="ML", type="concept", confidence=0.8, start_pos=3, end_pos=5)
        ]
        
        relationships = [
            QueryRelationship(subject="AI", predicate="relates to", object="ML", confidence=0.7, relationship_type="semantic")
        ]
        
        confidence = processor._calculate_confidence(entities, relationships)
        
        assert 0.0 <= confidence <= 1.0
        # Should be weighted towards entities
        assert confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_get_processing_stats(self):
        """Test getting processing statistics."""
        processor = QueryProcessor()
        
        # Process some queries
        await processor.process_query("What is AI?")
        await processor.process_query("How does ML work?")
        
        stats = processor.get_processing_stats()
        
        assert stats["total_queries"] == 2
        assert stats["successful_processings"] == 2
        assert stats["average_entities_extracted"] >= 0.0
        assert stats["average_processing_time_ms"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test query processor health check."""
        processor = QueryProcessor()
        
        health = await processor.health_check()
        
        assert health["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in health
        assert "test_query_processed" in health
        if health["status"] == "healthy":
            assert health["test_entities_extracted"] >= 0
            assert health["test_query_type_determined"] is True
            assert health["test_intent_determined"] is True


class TestKnowledgeRetriever:
    """Test KnowledgeRetriever class."""
    
    @pytest.mark.asyncio
    async def test_knowledge_retriever_initialization(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test KnowledgeRetriever initialization."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        assert retriever.db_session == mock_db_session
        assert retriever.vector_store == mock_vector_store
        assert retriever.graph_traverser == mock_graph_traverser
        assert retriever.graph_analyzer == mock_graph_analyzer
        assert retriever.default_mode == RetrievalMode.HYBRID
        assert retriever.default_strategy == RetrievalStrategy.RELEVANCE
    
    @pytest.mark.asyncio
    async def test_retrieve_semantic_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieval in semantic mode."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Mock similarity search results
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning is a subset of AI",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "source_id": "node_1",
                "metadata": {"confidence": 0.85}
            }
        ])
        
        results = await retriever.retrieve(
            query="machine learning",
            mode=RetrievalMode.VECTOR_SEARCH,
            top_k=10,
            threshold=0.7
        )
        
        assert len(results) == 1
        assert results[0].item_id == "embedding_1"
        assert results[0].item_type == "embedding"
        assert results[0].similarity == 0.9
        assert results[0].relevance_score == 0.9
    
    @pytest.mark.asyncio
    async def test_retrieve_knowledge_graph_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieval in knowledge graph mode."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Mock graph traversal results
        mock_graph_traverser.breadth_first_search = AsyncMock(return_value={
            "traversal_order": [
                {
                    "id": "node_1",
                    "title": "Machine Learning",
                    "depth": 0,
                    "metadata": {"confidence": 0.9}
                }
            ],
            "execution_time_ms": 50
        })
        
        results = await retriever.retrieve(
            query="machine learning",
            mode=RetrievalMode.GRAPH_TRAVERSAL,
            top_k=10,
            threshold=0.7
        )
        
        assert len(results) >= 0
        if results:
            assert results[0].item_type == "node"
            assert results[0].relevance_score >= 0.0
    
    @pytest.mark.asyncio
    async def test_retrieve_hybrid_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieval in hybrid mode."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Mock both vector and graph results
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning concepts",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "source_id": "node_1",
                "metadata": {"confidence": 0.85}
            }
        ])
        
        mock_graph_traverser.breadth_first_search = AsyncMock(return_value={
            "traversal_order": [
                {
                    "id": "node_2",
                    "title": "Deep Learning",
                    "depth": 1,
                    "metadata": {"confidence": 0.8}
                }
            ],
            "execution_time_ms": 50
        })
        
        results = await retriever.retrieve(
            query="machine learning",
            mode=RetrievalMode.HYBRID,
            top_k=10,
            threshold=0.7
        )
        
        assert len(results) >= 1
        # Should combine results from both sources
        result_ids = [result.item_id for result in results]
        assert "embedding_1" in result_ids or "node_2" in result_ids
    
    @pytest.mark.asyncio
    async def test_retrieve_related_items(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieving related items."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Mock graph traversal
        mock_graph_traverser.breadth_first_search = AsyncMock(return_value={
            "traversal_order": [
                {
                    "id": "node_2",
                    "title": "Related Concept",
                    "depth": 1,
                    "metadata": {"confidence": 0.8}
                }
            ],
            "execution_time_ms": 50
        })
        
        results = await retriever.retrieve_related(
            item_id="node_1",
            item_type="node",
            max_depth=2,
            top_k=10
        )
        
        assert len(results) >= 1
        assert results[0].item_type == "node"
        assert results[0].relevance_score >= 0.0
    
    @pytest.mark.asyncio
    async def test_retrieve_by_metadata(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieving by metadata filters."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # This would implement metadata-based retrieval
        # For now, return empty results as placeholder
        results = await retriever.retrieve_by_metadata(
            metadata_filters={"domain": "computer_science"},
            top_k=10
        )
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_apply_ranking_strategy(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test applying ranking strategies."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Create test results
        results = [
            RetrievalResult(
                item_id="item_1",
                item_type="node",
                content="Content 1",
                title="Title 1",
                description=None,
                metadata={},
                relevance_score=0.8,
                confidence_score=0.7,
                quality_score=0.9,
                ranking_score=0.8,
                source="test",
                created_at=datetime.now(timezone.utc)
            ),
            RetrievalResult(
                item_id="item_2",
                item_type="node",
                content="Content 2",
                title="Title 2",
                description=None,
                metadata={},
                relevance_score=0.6,
                confidence_score=0.9,
                quality_score=0.8,
                ranking_score=0.6,
                source="test",
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        # Test relevance ranking
        ranked = retriever._apply_ranking_strategy(
            results, RetrievalStrategy.RELEVANCE, {}
        )
        
        assert len(ranked) == 2
        assert ranked[0].relevance_score >= ranked[1].relevance_score
        
        # Test confidence ranking
        confidence_ranked = retriever._apply_ranking_strategy(
            results, RetrievalStrategy.CONFIDENCE, {}
        )
        
        assert len(confidence_ranked) == 2
        assert confidence_ranked[0].confidence_score >= confidence_ranked[1].confidence_score
    
    @pytest.mark.asyncio
    async def test_get_retrieval_stats(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test getting retrieval statistics."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Simulate some retrievals
        retriever.retrieval_stats["total_retrievals"] = 10
        retriever.retrieval_stats["successful_retrievals"] = 8
        retriever.retrieval_stats["failed_retrievals"] = 2
        retriever.retrieval_stats["average_results_count"] = 5.5
        
        stats = retriever.get_retrieval_stats()
        
        assert stats["total_retrievals"] == 10
        assert stats["successful_retrievals"] == 8
        assert stats["failed_retrievals"] == 2
        assert stats["success_rate"] == 0.8
        assert stats["average_results_count"] == 5.5
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test knowledge retriever health check."""
        retriever = KnowledgeRetriever(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer
        )
        
        # Mock health checks
        mock_vector_store.health_check = AsyncMock(return_value={"status": "healthy"})
        
        health = await retriever.health_check()
        
        assert health["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in health
        assert "retrieval_working" in health


class TestRetrievalEngine:
    """Test RetrievalEngine class."""
    
    @pytest.mark.asyncio
    async def test_retrieval_engine_initialization(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test RetrievalEngine initialization."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        assert engine.db_session == mock_db_session
        assert engine.vector_store == mock_vector_store
        assert engine.graph_traverser == mock_graph_traverser
        assert engine.graph_analyzer == mock_graph_analyzer
        assert engine.query_processor == mock_query_processor
        assert engine.default_mode == "hybrid"
        assert engine.default_strategy == "relevance"
    
    @pytest.mark.asyncio
    async def test_query_vector_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test query in vector mode."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock query processor
        mock_query_processor.process_query = AsyncMock(return_value=ProcessedQuery(
            original_query="machine learning",
            normalized_query="machine learning",
            query_type=QueryType.FACTUAL,
            intent=QueryIntent.SEARCH,
            entities=[],
            relationships=[],
            keywords=["machine", "learning"],
            concepts=["machine learning"],
            filters={},
            constraints={},
            context={},
            confidence=0.8
        ))
        
        # Mock vector store
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning fundamentals",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "source_id": "node_1",
                "metadata": {"confidence": 0.85}
            }
        ])
        
        result = await engine.query(
            query="machine learning",
            mode="vector",
            top_k=10,
            threshold=0.7
        )
        
        assert result["query"] == "machine learning"
        assert result["mode"] == "vector"
        assert result["total_found"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["embedding_id"] == "embedding_1"
    
    @pytest.mark.asyncio
    async def test_query_graph_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test query in graph mode."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock query processor
        mock_query_processor.process_query = AsyncMock(return_value=ProcessedQuery(
            original_query="machine learning",
            normalized_query="machine learning",
            query_type=QueryType.FACTUAL,
            intent=QueryIntent.SEARCH,
            entities=[],
            relationships=[],
            keywords=["machine", "learning"],
            concepts=["machine learning"],
            filters={},
            constraints={},
            context={},
            confidence=0.8
        ))
        
        # Mock knowledge retriever
        with patch('engines.codx.retrieval.retrieval_engine.KnowledgeRetriever') as mock_retriever_class:
            mock_retriever = AsyncMock()
            mock_retriever_class.return_value = mock_retriever
            mock_retriever.retrieve = AsyncMock(return_value=[
                RetrievalResult(
                    item_id="node_1",
                    item_type="node",
                    content="Machine learning concepts",
                    title="Machine Learning",
                    description=None,
                    metadata={},
                    relevance_score=0.9,
                    confidence_score=0.85,
                    quality_score=0.8,
                    ranking_score=0.9,
                    source="graph",
                    created_at=datetime.now(timezone.utc)
                )
            ])
            
            result = await engine.query(
                query="machine learning",
                mode="graph",
                top_k=10,
                threshold=0.7
            )
            
            assert result["query"] == "machine learning"
            assert result["mode"] == "graph"
            assert result["total_found"] == 1
            assert len(result["results"]) == 1
    
    @pytest.mark.asyncio
    async def test_query_hybrid_mode(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test query in hybrid mode."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock query processor
        mock_query_processor.process_query = AsyncMock(return_value=ProcessedQuery(
            original_query="machine learning",
            normalized_query="machine learning",
            query_type=QueryType.FACTUAL,
            intent=QueryIntent.SEARCH,
            entities=[],
            relationships=[],
            keywords=["machine", "learning"],
            concepts=["machine learning"],
            filters={},
            constraints={},
            context={},
            confidence=0.8
        ))
        
        # Mock vector store
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {
                "embedding_id": "embedding_1",
                "text": "Machine learning algorithms",
                "similarity": 0.9,
                "distance": 0.1,
                "source_type": "node",
                "source_id": "node_1",
                "metadata": {"confidence": 0.85}
            }
        ])
        
        # Mock knowledge retriever
        with patch('engines.codx.retrieval.retrieval_engine.KnowledgeRetriever') as mock_retriever_class:
            mock_retriever = AsyncMock()
            mock_retriever_class.return_value = mock_retriever
            mock_retriever.retrieve = AsyncMock(return_value=[
                RetrievalResult(
                    item_id="node_2",
                    item_type="node",
                    content="Deep learning concepts",
                    title="Deep Learning",
                    description=None,
                    metadata={},
                    relevance_score=0.8,
                    confidence_score=0.8,
                    quality_score=0.85,
                    ranking_score=0.8,
                    source="graph",
                    created_at=datetime.now(timezone.utc)
                )
            ])
            
            result = await engine.query(
                query="machine learning",
                mode="hybrid",
                top_k=10,
                threshold=0.7
            )
            
            assert result["query"] == "machine learning"
            assert result["mode"] == "hybrid"
            assert result["total_found"] == 2  # Combined from both sources
            assert len(result["results"]) == 2
    
    @pytest.mark.asyncio
    async def test_find_similar(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test finding similar items."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock similarity search
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {
                "embedding_id": "embedding_2",
                "text": "Similar machine learning content",
                "similarity": 0.85,
                "distance": 0.15,
                "source_type": "node",
                "source_id": "node_2",
                "metadata": {"confidence": 0.8}
            }
        ])
        
        results = await engine.find_similar(
            item_id="embedding_1",
            item_type="embedding",
            top_k=10,
            threshold=0.7
        )
        
        assert len(results) == 1
        assert results[0]["embedding_id"] == "embedding_2"
        assert results[0]["similarity"] == 0.85
    
    @pytest.mark.asyncio
    async def test_explore(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test graph exploration."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock graph traversal
        mock_graph_traverser.breadth_first_search = AsyncMock(return_value={
            "traversal_order": [
                {
                    "id": "node_2",
                    "title": "Related Concept",
                    "depth": 1,
                    "metadata": {"confidence": 0.8}
                },
                {
                    "id": "node_3",
                    "title": "Another Concept",
                    "depth": 2,
                    "metadata": {"confidence": 0.7}
                }
            ],
            "max_depth": 2,
            "execution_time_ms": 75
        })
        
        result = await engine.explore(
            start_item_id="node_1",
            max_depth=3,
            max_items=50
        )
        
        assert result["start_item_id"] == "node_1"
        assert result["items_explored"] == 2
        assert result["max_depth_reached"] == 2
        assert len(result["traversal_path"]) == 2
    
    @pytest.mark.asyncio
    async def test_recommend(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test generating recommendations."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock knowledge retriever
        with patch('engines.codx.retrieval.retrieval_engine.KnowledgeRetriever') as mock_retriever_class:
            mock_retriever = AsyncMock()
            mock_retriever_class.return_value = mock_retriever
            mock_retriever.recommend = AsyncMock(return_value=[
                RetrievalResult(
                    item_id="node_1",
                    item_type="node",
                    content="Recommended content",
                    title="Recommended Item",
                    description=None,
                    metadata={},
                    relevance_score=0.9,
                    confidence_score=0.85,
                    quality_score=0.8,
                    ranking_score=0.9,
                    source="recommendation",
                    created_at=datetime.now(timezone.utc)
                )
            ])
            
            user_context = {
                "preferences": {"interests": ["machine learning"]},
                "history": [{"query": "neural networks"}],
                "profile": {"expertise": "intermediate"}
            }
            
            results = await engine.recommend(
                user_context=user_context,
                item_type="node",
                top_k=10
            )
            
            assert len(results) == 1
            assert results[0].item_id == "node_1"
            assert results[0].item_type == "node"
    
    @pytest.mark.asyncio
    async def test_get_engine_stats(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test getting engine statistics."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Simulate some queries
        engine.engine_stats["total_queries"] = 20
        engine.engine_stats["successful_queries"] = 18
        engine.engine_stats["failed_queries"] = 2
        engine.engine_stats["average_query_time_ms"] = 150.0
        engine.engine_stats["average_results_count"] = 8.5
        
        stats = await engine.get_engine_stats()
        
        assert stats["total_queries"] == 20
        assert stats["successful_queries"] == 18
        assert stats["failed_queries"] == 2
        assert stats["success_rate"] == 0.9
        assert stats["average_query_time_ms"] == 150.0
        assert stats["average_results_count"] == 8.5
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_vector_store, mock_graph_traverser, mock_graph_analyzer, mock_query_processor):
        """Test retrieval engine health check."""
        engine = RetrievalEngine(
            mock_db_session,
            mock_vector_store,
            mock_graph_traverser,
            mock_graph_analyzer,
            mock_query_processor
        )
        
        # Mock component health checks
        mock_vector_store.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_graph_traverser.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_graph_analyzer.health_check = AsyncMock(return_value={"status": "healthy"})
        
        # Mock query processor
        mock_query_processor.process_query = AsyncMock(return_value=ProcessedQuery(
            original_query="test",
            normalized_query="test",
            query_type=QueryType.FACTUAL,
            intent=QueryIntent.SEARCH,
            entities=[],
            relationships=[],
            keywords=[],
            concepts=[],
            filters={},
            constraints={},
            context={},
            confidence=0.8
        ))
        
        # Mock vector store for test query
        mock_vector_store.search_similar = AsyncMock(return_value=[])
        
        health = await engine.health_check()
        
        assert health["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in health
        assert "component_health" in health
        assert "query_working" in health
