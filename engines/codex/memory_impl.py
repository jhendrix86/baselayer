"""
CODEX Memory Interface Implementation

Concrete implementation of MemoryInterface from the agents framework
that connects to the CODEX knowledge storage system.
"""

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from agents.memory.memory_interface import MemoryInterface
from .api.knowledge_manager import KnowledgeManager
from .models.knowledge_entry import KnowledgeEntryType, SourceEngine

logger = get_logger(__name__)


class CodexMemoryInterface(MemoryInterface):
    """
    Concrete MemoryInterface implementation using CODEX knowledge system.
    
    Provides persistent memory storage and retrieval for all agents
    through the CODEX knowledge base.
    """
    
    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        agent_name: str,
        engine_name: str
    ):
        """
        Initialize memory interface.
        
        Args:
            knowledge_manager: CODEX knowledge manager instance
            agent_name: Name of the agent using this interface
            engine_name: Name of the engine the agent belongs to
        """
        self.knowledge_manager = knowledge_manager
        self.agent_name = agent_name
        self.engine_name = engine_name
        
        logger.info("CodexMemoryInterface initialized", 
                   agent_name=agent_name,
                   engine_name=engine_name)
    
    async def store(
        self,
        key: str,
        value: str,
        entry_type: str = "fact",
        confidence: float = 1.0,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Store a memory entry.
        
        Args:
            key: Unique key for the memory
            value: Memory content
            entry_type: Type of memory entry
            confidence: Confidence score (0.0-1.0)
            tags: Optional tags
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert string entry_type to enum
            entry_type_enum = KnowledgeEntryType(entry_type)
            
            # Convert engine name to enum
            engine_enum = SourceEngine(self.engine_name.lower())
            
            # Generate prefixed key to avoid collisions
            prefixed_key = f"{self.agent_name}:{key}"
            
            # Add agent and engine tags
            full_tags = tags or []
            full_tags.extend([self.agent_name, self.engine_name])
            
            # Store in knowledge base
            entry = await self.knowledge_manager.store(
                key=prefixed_key,
                value=value,
                entry_type=entry_type_enum,
                source_engine=engine_enum,
                source_agent=self.agent_name,
                tags=full_tags,
                confidence=confidence,
                generate_embedding=True
            )
            
            logger.debug("Memory stored", 
                        agent_name=self.agent_name,
                        key=key,
                        entry_type=entry_type)
            
            return True
            
        except Exception as e:
            logger.error("Failed to store memory", 
                        agent_name=self.agent_name,
                        key=key,
                        error=str(e))
            return False
    
    async def retrieve(self, key: str) -> Optional[str]:
        """
        Retrieve a memory entry by key.
        
        Args:
            key: Memory key
            
        Returns:
            Memory value or None
        """
        try:
            # Generate prefixed key
            prefixed_key = f"{self.agent_name}:{key}"
            
            # Retrieve from knowledge base
            entry = await self.knowledge_manager.retrieve_by_key(prefixed_key)
            
            if entry:
                return entry.value
            
            return None
            
        except Exception as e:
            logger.error("Failed to retrieve memory", 
                        agent_name=self.agent_name,
                        key=key,
                        error=str(e))
            return None
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memory entries.
        
        Args:
            query: Search query
            limit: Maximum results
            min_confidence: Minimum confidence
            tags: Filter by tags
            
        Returns:
            List of matching memory entries
        """
        try:
            # Add agent and engine tags to filter
            full_tags = tags or []
            full_tags.extend([self.agent_name, self.engine_name])
            
            # Search in knowledge base
            results = await self.knowledge_manager.search_semantic(
                query=query,
                limit=limit,
                min_confidence=min_confidence,
                tags=full_tags,
                exclude_archived=True
            )
            
            # Convert to memory format
            memories = []
            for result in results:
                # Extract original key (remove agent prefix)
                original_key = result["key"].replace(f"{self.agent_name}:", "", 1)
                
                memory = {
                    "key": original_key,
                    "value": result["value"],
                    "entry_type": result["entry_type"],
                    "confidence": result["confidence"],
                    "similarity": result["similarity"],
                    "access_count": result["access_count"],
                    "created_at": result["created_at"],
                    "last_accessed_at": result["last_accessed_at"]
                }
                memories.append(memory)
            
            logger.debug("Memory search completed", 
                        agent_name=self.agent_name,
                        query_length=len(query),
                        results_found=len(memories))
            
            return memories
            
        except Exception as e:
            logger.error("Failed to search memory", 
                        agent_name=self.agent_name,
                        query=query,
                        error=str(e))
            return []
    
    async def update(
        self,
        key: str,
        value: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Update a memory entry.
        
        Args:
            key: Memory key
            value: New value (optional)
            confidence: New confidence (optional)
            tags: New tags (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate prefixed key
            prefixed_key = f"{self.agent_name}:{key}"
            
            # Add agent and engine tags
            full_tags = tags or []
            full_tags.extend([self.agent_name, self.engine_name])
            
            # Update in knowledge base
            entry = await self.knowledge_manager.update(
                key=prefixed_key,
                value=value,
                confidence=confidence,
                tags=full_tags,
                regenerate_embedding=bool(value)
            )
            
            logger.debug("Memory updated", 
                        agent_name=self.agent_name,
                        key=key)
            
            return entry is not None
            
        except Exception as e:
            logger.error("Failed to update memory", 
                        agent_name=self.agent_name,
                        key=key,
                        error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete (archive) a memory entry.
        
        Args:
            key: Memory key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate prefixed key
            prefixed_key = f"{self.agent_name}:{key}"
            
            # Archive in knowledge base
            success = await self.knowledge_manager.archive(prefixed_key)
            
            if success:
                logger.debug("Memory deleted", 
                           agent_name=self.agent_name,
                           key=key)
            
            return success
            
        except Exception as e:
            logger.error("Failed to delete memory", 
                        agent_name=self.agent_name,
                        key=key,
                        error=str(e))
            return False
    
    async def get_context(
        self,
        query: str,
        max_tokens: int = 4000,
        min_confidence: float = 0.5
    ) -> str:
        """
        Get relevant context for LLM.
        
        Args:
            query: Context query
            max_tokens: Maximum tokens
            min_confidence: Minimum confidence
            
        Returns:
            Formatted context string
        """
        try:
            # Add agent and engine tags
            tags = [self.agent_name, self.engine_name]
            
            # Get context from knowledge base
            context = await self.knowledge_manager.get_context(
                query=query,
                max_tokens=max_tokens,
                min_confidence=min_confidence,
                tags=tags
            )
            
            logger.debug("Memory context retrieved", 
                        agent_name=self.agent_name,
                        query_length=len(query),
                        context_length=len(context))
            
            return context
            
        except Exception as e:
            logger.error("Failed to get memory context", 
                        agent_name=self.agent_name,
                        query=query,
                        error=str(e))
            return f"Error retrieving memory context for {self.agent_name}."
    
    async def link_memories(
        self,
        source_key: str,
        target_key: str,
        relationship: str = "related",
        strength: float = 0.5
    ) -> bool:
        """
        Create a relationship between two memories.
        
        Args:
            source_key: Source memory key
            target_key: Target memory key
            relationship: Type of relationship
            strength: Relationship strength
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate prefixed keys
            source_prefixed = f"{self.agent_name}:{source_key}"
            target_prefixed = f"{self.agent_name}:{target_key}"
            
            # Convert relationship type
            from .models.knowledge_link import KnowledgeLinkType
            link_type = KnowledgeLinkType(relationship.lower())
            
            # Create link in knowledge base
            link = await self.knowledge_manager.link(
                source_key=source_prefixed,
                target_key=target_prefixed,
                link_type=link_type,
                strength=strength
            )
            
            if link:
                logger.debug("Memory link created", 
                           agent_name=self.agent_name,
                           source_key=source_key,
                           target_key=target_key,
                           relationship=relationship)
            
            return link is not None
            
        except Exception as e:
            logger.error("Failed to link memories", 
                        agent_name=self.agent_name,
                        source_key=source_key,
                        target_key=target_key,
                        error=str(e))
            return False
    
    async def get_related_memories(
        self,
        key: str,
        max_depth: int = 2,
        min_strength: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Get memories related to a specific memory.
        
        Args:
            key: Memory key
            max_depth: Maximum traversal depth
            min_strength: Minimum relationship strength
            
        Returns:
            List of related memories
        """
        try:
            # Generate prefixed key
            prefixed_key = f"{self.agent_name}:{key}"
            
            # Get related entries from knowledge base
            related = await self.knowledge_manager.get_related(
                key=prefixed_key,
                depth=max_depth,
                min_strength=min_strength
            )
            
            # Convert to memory format
            memories = []
            for item in related:
                # Extract original key (remove agent prefix)
                original_key = item["entry"]["key"].replace(f"{self.agent_name}:", "", 1)
                
                memory = {
                    "key": original_key,
                    "value": item["entry"]["value"],
                    "entry_type": item["entry"]["entry_type"],
                    "confidence": item["entry"]["confidence"],
                    "relationship": item["relationship"],
                    "strength": item["strength"],
                    "depth": item["depth"],
                    "path": [k.replace(f"{self.agent_name}:", "", 1) for k in item["path"]]
                }
                memories.append(memory)
            
            logger.debug("Related memories retrieved", 
                        agent_name=self.agent_name,
                        key=key,
                        results_found=len(memories))
            
            return memories
            
        except Exception as e:
            logger.error("Failed to get related memories", 
                        agent_name=self.agent_name,
                        key=key,
                        error=str(e))
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics for this agent.
        
        Returns:
            Statistics dictionary
        """
        try:
            # Search for agent's memories
            agent_memories = await self.search(
                query="",
                limit=1000,  # Get all
                min_confidence=0.0,
                tags=[self.agent_name]
            )
            
            # Calculate statistics
            total_memories = len(agent_memories)
            
            if total_memories == 0:
                return {
                    "agent_name": self.agent_name,
                    "engine_name": self.engine_name,
                    "total_memories": 0,
                    "avg_confidence": 0.0,
                    "memory_types": {},
                    "total_accesses": 0
                }
            
            # Calculate confidence average
            total_confidence = sum(m["confidence"] for m in agent_memories)
            avg_confidence = total_confidence / total_memories
            
            # Count by type
            memory_types = {}
            total_accesses = 0
            
            for memory in agent_memories:
                entry_type = memory["entry_type"]
                memory_types[entry_type] = memory_types.get(entry_type, 0) + 1
                total_accesses += memory["access_count"]
            
            stats = {
                "agent_name": self.agent_name,
                "engine_name": self.engine_name,
                "total_memories": total_memories,
                "avg_confidence": avg_confidence,
                "memory_types": memory_types,
                "total_accesses": total_accesses
            }
            
            logger.debug("Memory stats retrieved", 
                        agent_name=self.agent_name,
                        stats=stats)
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get memory stats", 
                        agent_name=self.agent_name,
                        error=str(e))
            return {"error": str(e)}
    
    async def cleanup(self, days_threshold: int = 30) -> Dict[str, Any]:
        """
        Clean up old or low-confidence memories.
        
        Args:
            days_threshold: Days threshold for cleanup
            
        Returns:
            Cleanup results
        """
        try:
            # Get agent's memories for decay
            agent_memories = await self.search(
                query="",
                limit=1000,
                min_confidence=0.0,
                tags=[self.agent_name]
            )
            
            decayed_count = 0
            pruned_count = 0
            
            for memory in agent_memories:
                # Get full entry for decay calculation
                prefixed_key = f"{self.agent_name}:{memory['key']}"
                entry = await self.knowledge_manager.retrieve_by_key(prefixed_key)
                
                if entry:
                    # Check if should decay
                    if entry.should_decay():
                        # Decay confidence
                        old_confidence = entry.confidence
                        new_confidence = entry.calculate_decay_score()
                        entry.update_confidence(new_confidence)
                        await self.knowledge_manager.db.commit()
                        decayed_count += 1
                    
                    # Check if should prune (archived and old)
                    if entry.is_archived and entry.should_prune():
                        # Delete entry
                        await self.knowledge_manager.db.delete(entry)
                        await self.knowledge_manager.db.commit()
                        pruned_count += 1
            
            results = {
                "agent_name": self.agent_name,
                "memories_processed": len(agent_memories),
                "decayed_count": decayed_count,
                "pruned_count": pruned_count,
                "days_threshold": days_threshold
            }
            
            logger.info("Memory cleanup completed", results=results)
            
            return results
            
        except Exception as e:
            logger.error("Failed to cleanup memories", 
                        agent_name=self.agent_name,
                        error=str(e))
            return {"error": str(e)}
    
    async def export_memories(self) -> List[Dict[str, Any]]:
        """
        Export all memories for this agent.
        
        Returns:
            List of memory entries
        """
        try:
            # Get all agent memories
            agent_memories = await self.search(
                query="",
                limit=1000,
                min_confidence=0.0,
                tags=[self.agent_name]
            )
            
            # Add additional metadata
            exported_memories = []
            for memory in agent_memories:
                exported_memory = memory.copy()
                exported_memory["agent_name"] = self.agent_name
                exported_memory["engine_name"] = self.engine_name
                exported_memory["exported_at"] = datetime.now(timezone.utc).isoformat()
                exported_memories.append(exported_memory)
            
            logger.info("Memories exported", 
                        agent_name=self.agent_name,
                        count=len(exported_memories))
            
            return exported_memories
            
        except Exception as e:
            logger.error("Failed to export memories", 
                        agent_name=self.agent_name,
                        error=str(e))
            return []
    
    async def import_memories(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Import memories into this agent's memory.
        
        Args:
            memories: List of memory entries to import
            
        Returns:
            Import results
        """
        try:
            imported_count = 0
            failed_count = 0
            errors = []
            
            for memory in memories:
                try:
                    # Validate required fields
                    if not all(key in memory for key in ["key", "value", "entry_type"]):
                        errors.append(f"Missing required fields in memory: {memory.get('key', 'unknown')}")
                        failed_count += 1
                        continue
                    
                    # Store memory
                    success = await self.store(
                        key=memory["key"],
                        value=memory["value"],
                        entry_type=memory["entry_type"],
                        confidence=memory.get("confidence", 1.0),
                        tags=memory.get("tags")
                    )
                    
                    if success:
                        imported_count += 1
                    else:
                        errors.append(f"Failed to store memory: {memory['key']}")
                        failed_count += 1
                        
                except Exception as e:
                    errors.append(f"Error importing memory {memory.get('key', 'unknown')}: {str(e)}")
                    failed_count += 1
            
            results = {
                "agent_name": self.agent_name,
                "memories_processed": len(memories),
                "imported_count": imported_count,
                "failed_count": failed_count,
                "errors": errors
            }
            
            logger.info("Memories imported", results=results)
            
            return results
            
        except Exception as e:
            logger.error("Failed to import memories", 
                        agent_name=self.agent_name,
                        error=str(e))
            return {"error": str(e)}
