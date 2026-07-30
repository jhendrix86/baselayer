"""
BaseLayer Agent State Machine

Agent state definitions, transitions, and history tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from baselayer.core.logging import get_logger

logger = get_logger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StateMachine:
    """
    Agent state machine with valid transitions and history.
    
    Ensures agents follow proper lifecycle and provides
    audit trail of all state changes.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS: Dict[AgentState, List[AgentState]] = {
        AgentState.IDLE: [AgentState.PLANNING, AgentState.CANCELLED],
        AgentState.PLANNING: [AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.EXECUTING: [AgentState.VALIDATING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.VALIDATING: [AgentState.REPORTING, AgentState.FAILED, AgentState.CANCELLED],
        AgentState.REPORTING: [AgentState.COMPLETE, AgentState.FAILED],
        AgentState.COMPLETE: [AgentState.IDLE, AgentState.PLANNING],
        AgentState.FAILED: [AgentState.IDLE, AgentState.PLANNING],
        AgentState.CANCELLED: [AgentState.IDLE],
    }
    
    # Terminal states (no further transitions)
    TERMINAL_STATES: List[AgentState] = [
        AgentState.COMPLETE,
        AgentState.FAILED,
        AgentState.CANCELLED
    ]
    
    # Active states (agent is working)
    ACTIVE_STATES: List[AgentState] = [
        AgentState.PLANNING,
        AgentState.EXECUTING,
        AgentState.VALIDATING,
        AgentState.REPORTING
    ]
    
    def __init__(self, initial_state: AgentState = AgentState.IDLE) -> None:
        """Initialize state machine with initial state."""
        self.current_state: AgentState = initial_state
        self.state_history: List[StateTransition] = []
        self.transition_count: int = 0
        
        # Record initial state
        self._record_transition(None, initial_state)
        
        logger.debug(
            "State machine initialized",
            initial_state=initial_state.value
        )
    
    def can_transition_to(self, target_state: AgentState) -> bool:
        """
        Check if transition to target state is valid.
        
        Args:
            target_state: Target state to transition to
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        return target_state in valid_targets
    
    def transition_to(
        self,
        target_state: AgentState,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Transition to target state if valid.
        
        Args:
            target_state: Target state to transition to
            reason: Optional reason for transition
            metadata: Optional metadata for transition
            
        Returns:
            True if transition succeeded, False otherwise
        """
        if not self.can_transition_to(target_state):
            logger.error(
                "Invalid state transition",
                from_state=self.current_state.value,
                to_state=target_state.value,
                reason=reason
            )
            return False
        
        # Record transition
        self._record_transition(
            self.current_state,
            target_state,
            reason,
            metadata
        )
        
        # Update current state
        old_state = self.current_state
        self.current_state = target_state
        self.transition_count += 1
        
        logger.info(
            "State transition",
            from_state=old_state.value,
            to_state=target_state.value,
            transition_count=self.transition_count,
            reason=reason
        )
        
        return True
    
    def is_terminal(self) -> bool:
        """Check if current state is terminal."""
        return self.current_state in self.TERMINAL_STATES
    
    def is_active(self) -> bool:
        """Check if agent is currently active (working)."""
        return self.current_state in self.ACTIVE_STATES
    
    def is_idle(self) -> bool:
        """Check if agent is idle."""
        return self.current_state == AgentState.IDLE
    
    def get_state_info(self) -> Dict[str, any]:
        """Get current state information."""
        return {
            "current_state": self.current_state.value,
            "is_terminal": self.is_terminal(),
            "is_active": self.is_active(),
            "is_idle": self.is_idle(),
            "transition_count": self.transition_count,
            "valid_transitions": [
                state.value for state in self.VALID_TRANSITIONS.get(self.current_state, [])
            ]
        }
    
    def get_recent_transitions(self, limit: int = 10) -> List['StateTransition']:
        """Get recent state transitions."""
        return self.state_history[-limit:]
    
    def reset(self, initial_state: AgentState = AgentState.IDLE) -> None:
        """Reset state machine to initial state."""
        old_state = self.current_state
        
        self.current_state = initial_state
        self.state_history = []
        self.transition_count = 0
        
        # Record reset
        self._record_transition(None, initial_state, "state_machine_reset")
        
        logger.info(
            "State machine reset",
            from_state=old_state.value,
            to_state=initial_state.value
        )
    
    def _record_transition(
        self,
        from_state: Optional[AgentState],
        to_state: AgentState,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record a state transition in history."""
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            reason=reason,
            metadata=metadata or {}
        )
        
        self.state_history.append(transition)
        
        # Keep history size manageable
        if len(self.state_history) > 1000:
            self.state_history = self.state_history[-500:]


class StateTransition:
    """
    Record of a single state transition.
    
    Immutable dataclass that captures when and why
    a state transition occurred.
    """
    
    def __init__(
        self,
        from_state: Optional[AgentState],
        to_state: AgentState,
        timestamp: datetime,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Initialize state transition record."""
        self.from_state: Optional[AgentState] = from_state
        self.to_state: AgentState = to_state
        self.timestamp: datetime = timestamp
        self.reason: Optional[str] = reason
        self.metadata: Dict[str, any] = metadata or {}
        self.duration_ms: Optional[float] = None
    
    def set_duration(self, duration_ms: float) -> None:
        """Set the duration of this state."""
        self.duration_ms = duration_ms
    
    def to_dict(self) -> Dict[str, any]:
        """Convert transition to dictionary."""
        return {
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms
        }
    
    def __str__(self) -> str:
        """String representation of transition."""
        from_str = self.from_state.value if self.from_state else "START"
        to_str = self.to_state.value
        
        if self.reason:
            return f"{from_str} -> {to_str} ({self.reason})"
        else:
            return f"{from_str} -> {to_str}"


class StateHistory:
    """
    Manages state transition history with analytics.
    
    Provides insights into agent behavior patterns
    and performance metrics.
    """
    
    def __init__(self, max_history: int = 1000) -> None:
        """Initialize state history manager."""
        self.transitions: List[StateTransition] = []
        self.max_history: int = max_history
    
    def add_transition(self, transition: StateTransition) -> None:
        """Add a transition to history."""
        self.transitions.append(transition)
        
        # Maintain history size
        if len(self.transitions) > self.max_history:
            self.transitions = self.transitions[-self.max_history:]
    
    def get_transition_count(self, state: Optional[AgentState] = None) -> int:
        """Get count of transitions to/from a state."""
        if state is None:
            return len(self.transitions)
        
        count = 0
        for transition in self.transitions:
            if transition.to_state == state or transition.from_state == state:
                count += 1
        
        return count
    
    def get_average_duration(self, state: AgentState) -> Optional[float]:
        """Get average duration spent in a state."""
        durations = [
            transition.duration_ms for transition in self.transitions
            if transition.to_state == state and transition.duration_ms is not None
        ]
        
        if not durations:
            return None
        
        return sum(durations) / len(durations)
    
    def get_failure_rate(self) -> float:
        """Calculate failure rate (transitions to FAILED state)."""
        if not self.transitions:
            return 0.0
        
        failures = sum(
            1 for transition in self.transitions
            if transition.to_state == AgentState.FAILED
        )
        
        return (failures / len(self.transitions)) * 100
    
    def get_most_common_transitions(self, limit: int = 5) -> List[tuple]:
        """Get most common state transitions."""
        transition_counts = {}
        
        for transition in self.transitions:
            if transition.from_state:
                key = (transition.from_state, transition.to_state)
                transition_counts[key] = transition_counts.get(key, 0) + 1
        
        # Sort by count and return top N
        sorted_transitions = sorted(
            transition_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            (f"{t[0].value} -> {t[1].value}", count)
            for (t, count) in sorted_transitions[:limit]
        ]
    
    def get_recent_failures(self, hours: int = 24) -> List[StateTransition]:
        """Get recent failures within specified hours."""
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        
        return [
            transition for transition in self.transitions
            if (transition.to_state == AgentState.FAILED and
                transition.timestamp.timestamp() > cutoff)
        ]
    
    def clear(self) -> None:
        """Clear all transition history."""
        self.transitions = []
        
        logger.info("State history cleared")
    
    def get_analytics(self) -> Dict[str, any]:
        """Get comprehensive analytics of state history."""
        return {
            "total_transitions": len(self.transitions),
            "failure_rate": self.get_failure_rate(),
            "most_common_transitions": self.get_most_common_transitions(),
            "recent_failures_24h": len(self.get_recent_failures(24)),
            "recent_failures_1h": len(self.get_recent_failures(1)),
            "state_durations": {
                state.value: self.get_average_duration(state)
                for state in AgentState
                if self.get_average_duration(state) is not None
            }
        }
