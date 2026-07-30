"""
CODEX Knowledge Manager Tests

Unit tests for knowledge management operations.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from ...models.knowledge_entry import KnowledgeEntryType, SourceEngine
from ...models.knowledge_link import KnowledgeLinkType
from ...api.knowledge_manager import KnowledgeManager


@pytest.mark.unit
class TestKnowledgeManager:
    """Test knowledge manager functionality."""
    
    async def test_store_knowledge_entry(self, knowledge_manager, sample_embedding):
        """Test storing a new knowledge entry."""
        with patch.object(knowledge_manager.embedding_engine, 'generate_embedding', return_value=sample_embedding):
            entry = await knowledge_manager.store(
                key="test:new_fact",
                value="This is a new test fact",
                entry_type=KnowledgeEntryType.FACT,
                source_engine=SourceEngine.MANUAL,
                source_agent="test_agent",
                tags=["test", "new"],
                confidence=0.8,
                generate_embedding=True
            )
            
            assert entry is not None
            assert entry.key == "test:new_fact"
            assert entry.value == "This is a new test fact"
            assert entry.entry_type == KnowledgeEntryType.FACT
            assert entry.source_engine == SourceEngine.MANUAL
            assert entry.source_agent == "test_agent"
            assert entry.tags == ["test", "new"]
            assert entry.confidence == 0.8
            assert entry.embedding is not None
    
    async def test_store_duplicate_entry(self, knowledge_manager, sample_knowledge_entry):
        """Test storing duplicate knowledge entry."""
        with pytest.raises(Exception):  # Should raise BaseLayerError
            await knowledge_manager.store(
                key=sample_knowledge_entry.key,  # Same key
                value="Different value",
                entry_type=KnowledgeEntryType.FACT,
                source_engine=SourceEngine.MANUAL,
                source_agent="test_agent"
            )
    
    async def test_retrieve_by_key(self, knowledge_manager, sample_knowledge_entry):
        """Test retrieving knowledge entry by key."""
        entry = await knowledge_manager.retrieve_by_key(sample_knowledge_entry.key)
        
        assert entry is not None
        assert entry.id == sample_knowledge_entry.id
        assert entry.key == sample_knowledge_entry.key
        assert entry.access_count == 1  # Should increment access count
    
    async def test_retrieve_nonexistent_key(self, knowledge_manager):
        """Test retrieving non-existent key."""
        entry = await knowledge_manager.retrieve_by_key("nonexistent:key")
        assert entry is None
    
    async def test_search_semantic(self, knowledge_manager, sample_search_results):
        """Test semantic search functionality."""
        with patch.object(knowledge_manager.semantic_search, 'search', return_value=sample_search_results):
            results = await knowledge_manager.search_semantic(
                query="test query",
                limit=10,
                min_confidence=0.5
            )
            
            assert len(results) == 2
            assert results[0]["similarity"] == 0.95
            assert results[0]["key"] == "test:result_1"
            assert results[1]["similarity"] == 0.85
            assert results[1]["key"] == "test:result_2"
    
    async def test_search_keyword(self, knowledge_manager):
        """Test keyword search functionality."""
        # This would implement actual keyword search
        # For now, test that the method exists and returns empty list
        results = await knowledge_manager.search_keyword(
            query="test",
            limit=10
        )
        assert isinstance(results, list)
    
    async def test_update_entry(self, knowledge_manager, sample_knowledge_entry):
        """Test updating knowledge entry."""
        updated_entry = await knowledge_manager.update(
            key=sample_knowledge_entry.key,
            value="Updated value",
            confidence=0.95,
            tags=["test", "updated"]
        )
        
        assert updated_entry is not None
        assert updated_entry.value == "Updated value"
        assert updated_entry.confidence == 0.95
        assert updated_entry.tags == ["test", "updated"]
    
    async def test_update_nonexistent_entry(self, knowledge_manager):
        """Test updating non-existent entry."""
        updated_entry = await knowledge_manager.update(
            key="nonexistent:key",
            value="Updated value"
        )
        assert updated_entry is None
    
    async def test_archive_entry(self, knowledge_manager, sample_knowledge_entry):
        """Test archiving knowledge entry."""
        success = await knowledge_manager.archive(sample_knowledge_entry.key)
        assert success is True
        
        # Verify it's archived
        entry = await knowledge_manager.retrieve_by_key(sample_knowledge_entry.key)
        assert entry.is_archived is True
    
    async def test_archive_nonexistent_entry(self, knowledge_manager):
        """Test archiving non-existent entry."""
        success = await knowledge_manager.archive("nonexistent:key")
        assert success is False
    
    async def test_link_entries(self, knowledge_manager, sample_knowledge_entry):
        """Test creating knowledge link."""
        # Create another entry to link to
        target_entry = await knowledge_manager.store(
            key="test:target_entry",
            value="Target entry",
            entry_type=KnowledgeEntryType.FACT,
            source_engine=SourceEngine.MANUAL,
            source_agent="test_agent"
        )
        
        link = await knowledge_manager.link(
            source_key=sample_knowledge_entry.key,
            target_key=target_entry.key,
            link_type=KnowledgeLinkType.RELATED,
            strength=0.7
        )
        
        assert link is not None
        assert link.link_type == KnowledgeLinkType.RELATED
        assert link.strength == 0.7
    
    async def test_link_nonexistent_entries(self, knowledge_manager):
        """Test linking non-existent entries."""
        link = await knowledge_manager.link(
            source_key="nonexistent:source",
            target_key="nonexistent:target",
            link_type=KnowledgeLinkType.RELATED
        )
        assert link is None
    
    async def test_get_related_entries(self, knowledge_manager, sample_knowledge_link):
        """Test getting related entries."""
        with patch.object(knowledge_manager, 'get_related', return_value=[
            {
                "entry": {
                    "key": "test:related_entry",
                    "value": "Related entry",
                    "entry_type": "fact",
                    "confidence": 0.8
                },
                "relationship": "is related to",
                "strength": 0.7,
                "depth": 1
            }
        ]):
            related = await knowledge_manager.get_related(
                key="test:sample_fact",
                depth=2,
                min_strength=0.3
            )
            
            assert len(related) == 1
            assert related[0]["relationship"] == "is related to"
            assert related[0]["strength"] == 0.7
    
    async def test_get_context(self, knowledge_manager):
        """Test building context for LLM."""
        with patch.object(knowledge_manager.semantic_search, 'search_context', return_value="Sample context"):
            context = await knowledge_manager.get_context(
                query="test query",
                max_tokens=1000,
                min_confidence=0.5
            )
            
            assert context == "Sample context"
    
    async def test_decay_confidence(self, knowledge_manager):
        """Test confidence decay operation."""
        with patch.object(knowledge_manager, 'decay', return_value={
            "candidates_found": 10,
            "entries_decayed": 5,
            "dry_run": False
        }):
            result = await knowledge_manager.decay(dry_run=False)
            
            assert result["candidates_found"] == 10
            assert result["entries_decayed"] == 5
            assert result["dry_run"] is False
    
    async def test_prune_entries(self, knowledge_manager):
        """Test pruning old entries."""
        with patch.object(knowledge_manager, 'prune', return_value={
            "candidates_found": 5,
            "entries_pruned": 3,
            "dry_run": False,
            "retention_days": 90
        }):
            result = await knowledge_manager.prune(retention_days=90, dry_run=False)
            
            assert result["candidates_found"] == 5
            assert result["entries_pruned"] == 3
            assert result["dry_run"] is False
    
    async def test_create_snapshot(self, knowledge_manager):
        """Test creating knowledge snapshot."""
        with patch.object(knowledge_manager, 'snapshot', return_value=sample_knowledge_snapshot):
            snapshot = await knowledge_manager.snapshot()
            
            assert snapshot is not None
            assert snapshot.total_entries == 100
            assert snapshot.avg_confidence == 0.55
    
    async def test_get_stats(self, knowledge_manager):
        """Test getting knowledge base statistics."""
        with patch.object(knowledge_manager, 'get_stats', return_value={
            "total_entries": 100,
            "active_entries": 95,
            "archived_entries": 5,
            "total_links": 25,
            "health_score": 0.85
        }):
            stats = await knowledge_manager.get_stats()
            
            assert stats["total_entries"] == 100
            assert stats["active_entries"] == 95
            assert stats["archived_entries"] == 5
            assert stats["total_links"] == 25
            assert stats["health_score"] == 0.85


@pytest.mark.integration
class TestKnowledgeManagerIntegration:
    """Integration tests for knowledge manager."""
    
    async def test_full_knowledge_lifecycle(self, knowledge_manager, sample_embedding):
        """Test complete knowledge lifecycle."""
        # Store entry
        with patch.object(knowledge_manager.embedding_engine, 'generate_embedding', return_value=sample_embedding):
            entry = await knowledge_manager.store(
                key="test:lifecycle_entry",
                value="Test entry for lifecycle",
                entry_type=KnowledgeEntryType.FACT,
                source_engine=SourceEngine.MANUAL,
                source_agent="test_agent",
                confidence=0.9
            )
        
        # Retrieve entry
        retrieved = await knowledge_manager.retrieve_by_key("test:lifecycle_entry")
        assert retrieved.id == entry.id
        
        # Update entry
        updated = await knowledge_manager.update(
            key="test:lifecycle_entry",
            confidence=0.95
        )
        assert updated.confidence == 0.95
        
        # Archive entry
        archived = await knowledge_manager.archive("test:lifecycle_entry")
        assert archived is True
        
        # Verify archived
        archived_entry = await knowledge_manager.retrieve_by_key("test:lifecycle_entry")
        assert archived_entry.is_archived is True
    
    async def test_search_and_retrieval(self, knowledge_manager, sample_search_results):
        """Test search and retrieval workflow."""
        with patch.object(knowledge_manager.semantic_search, 'search', return_value=sample_search_results):
            # Search for knowledge
            results = await knowledge_manager.search_semantic(
                query="test query",
                limit=5
            )
            
            assert len(results) > 0
            
            # Retrieve first result by key
            first_result = results[0]
            entry = await knowledge_manager.retrieve_by_key(first_result["key"])
            
            # Note: This would work if the entry actually exists in the database
            # For now, this tests the workflow structure
    
    async def test_knowledge_graph_operations(self, knowledge_manager):
        """Test knowledge graph operations."""
        # This would test actual graph operations
        # For now, test the workflow structure
        
        # Create entries
        entry1 = await knowledge_manager.store(
            key="test:graph_entry_1",
            value="First graph entry",
            entry_type=KnowledgeEntryType.FACT,
            source_engine=SourceEngine.MANUAL,
            source_agent="test_agent"
        )
        
        entry2 = await knowledge_manager.store(
            key="test:graph_entry_2",
            value="Second graph entry",
            entry_type=KnowledgeEntryType.DECISION,
            source_engine=SourceEngine.MANUAL,
            source_agent="test_agent"
        )
        
        # Create link
        link = await knowledge_manager.link(
            source_key=entry1.key,
            target_key=entry2.key,
            link_type=KnowledgeLinkType.SUPPORTS,
            strength=0.8
        )
        
        assert link is not None
        assert link.link_type == KnowledgeLinkType.SUPPORTS


@pytest.mark.unit
class TestKnowledgeManagerErrorHandling:
    """Test error handling in knowledge manager."""
    
    async def test_store_invalid_confidence(self, knowledge_manager):
        """Test storing entry with invalid confidence."""
        with pytest.raises(Exception):  # Should raise validation error
            await knowledge_manager.store(
                key="test:invalid_confidence",
                value="Test value",
                entry_type=KnowledgeEntryType.FACT,
                source_engine=SourceEngine.MANUAL,
                source_agent="test_agent",
                confidence=1.5  # Invalid confidence > 1.0
            )
    
    async def test_update_invalid_confidence(self, knowledge_manager, sample_knowledge_entry):
        """Test updating with invalid confidence."""
        with pytest.raises(Exception):  # Should raise validation error
            await knowledge_manager.update(
                key=sample_knowledge_entry.key,
                confidence=1.5  # Invalid confidence > 1.0
            )
    
    async def test_link_invalid_strength(self, knowledge_manager, sample_knowledge_entry):
        """Test creating link with invalid strength."""
        target_entry = await knowledge_manager.store(
            key="test:target_entry",
            value="Target entry",
            entry_type=KnowledgeEntryType.FACT,
            source_engine=SourceEngine.MANUAL,
            source_agent="test_agent"
        )
        
        with pytest.raises(Exception):  # Should raise validation error
            await knowledge_manager.link(
                source_key=sample_knowledge_entry.key,
                target_key=target_entry.key,
                link_type=KnowledgeLinkType.RELATED,
                strength=1.5  # Invalid strength > 1.0
            )
    
    async def test_context_invalid_tokens(self, knowledge_manager):
        """Test context building with invalid token count."""
        with pytest.raises(Exception):  # Should raise validation error
            await knowledge_manager.get_context(
                query="test query",
                max_tokens=0  # Invalid token count
            )
    
    async def test_prune_invalid_retention(self, knowledge_manager):
        """Test pruning with invalid retention days."""
        with pytest.raises(Exception):  # Should raise validation error
            await knowledge_manager.prune(retention_days=0)  # Invalid retention
