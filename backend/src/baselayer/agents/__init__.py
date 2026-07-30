"""
BaseLayer Multi-Agent Orchestration

Agent management, coordination, and communication
for the Multi-Agent Orchestration subsystem.
"""

from .orchestrator import AgentOrchestrator
from .lifecycle import AgentLifecycleManager
from .coordinator import TaskCoordinator
from .communicator import AgentCommunicator
from .monitor import AgentMonitor
from .scaler import AgentScaler
from .exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentLifecycleError,
    AgentCommunicationError,
    TaskCoordinationError,
    AgentScalingError,
)

__all__ = [
    # Core components
    "AgentOrchestrator",
    "AgentLifecycleManager",
    "TaskCoordinator",
    "AgentCommunicator",
    "AgentMonitor",
    "AgentScaler",
    # Exceptions
    "AgentError",
    "AgentNotFoundError",
    "AgentLifecycleError",
    "AgentCommunicationError",
    "TaskCoordinationError",
    "AgentScalingError",
]
