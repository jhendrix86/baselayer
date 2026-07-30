"""
BaseLayer Agent Context

Immutable context object for agent execution with
task data, configuration, and metadata.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pydantic import BaseModel


class AgentConfig(BaseModel):
    """Base configuration for agents."""
    max_retries: int = 3
    timeout_seconds: int = 300
    memory_limit_mb: int = 256
    log_level: str = "INFO"
    enable_metrics: bool = True


@dataclass(frozen=True)
class AgentContext:
    """
    Immutable context object for agent execution.
    
    Contains all necessary information for an agent to execute
    a task, including input data, configuration, and metadata.
    """
    task_id: str
    task_type: str
    input_data: Dict[str, Any]
    memory_interface: 'MemoryInterface'  # Forward reference
    config: AgentConfig
    request_id: str
    parent_agent_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "input_data": self.input_data,
            "config": self.config.dict(),
            "request_id": self.request_id,
            "parent_agent_id": self.parent_agent_id,
            "pipeline_id": self.pipeline_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentContext':
        """Create context from dictionary."""
        
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            input_data=data["input_data"],
            memory_interface=data["memory_interface"],
            config=AgentConfig(**data["config"]),
            request_id=data["request_id"],
            parent_agent_id=data.get("parent_agent_id"),
            pipeline_id=data.get("pipeline_id"),
            metadata=data.get("metadata", {})
        )
    
    def with_updates(self, **updates) -> 'AgentContext':
        """Create new context with updated fields."""
        current_dict = self.to_dict()
        current_dict.update(updates)
        return self.from_dict(current_dict)
