"""
BaseLayer Multi-Agent Orchestration Models

Agent management, task execution, and performance metrics
for the Multi-Agent Orchestration subsystem.
"""

from datetime import datetime

import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class AgentType(str, Enum):
    """Agent types with different capabilities."""
    WORKER = "worker"
    COORDINATOR = "coordinator"
    SUPERVISOR = "supervisor"
    SPECIALIST = "specialist"
    GATEWAY = "gateway"


class AgentStatus(str, Enum):
    """Agent status."""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Agent(BaseModel):
    """
    Agent model for Multi-Agent Orchestration subsystem.
    
    Defines AI agents with capabilities, configuration, and performance tracking.
    """
    
    __tablename__ = "agents"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Agent name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Agent description"
    )
    
    # Type and status
    agent_type: Mapped[AgentType] = mapped_column(
        ENUM(AgentType, name="agent_type"),
        nullable=False,
        index=True,
        comment="Type of agent"
    )
    
    status: Mapped[AgentStatus] = mapped_column(
        ENUM(AgentStatus, name="agent_status"),
        nullable=False,
        default=AgentStatus.OFFLINE,
        index=True,
        comment="Current agent status"
    )
    
    # Configuration
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="qwen2.5-coder:3b",
        comment="AI model used by the agent"
    )
    
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Agent configuration parameters"
    )
    
    # Capabilities
    capabilities: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Agent capabilities and supported operations"
    )
    
    # Performance settings
    max_concurrent_tasks: Mapped[int] = mapped_column(
        String(3),
        nullable=False,
        default="5",
        comment="Maximum number of concurrent tasks"
    )
    
    timeout_seconds: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="300",
        comment="Default timeout for tasks in seconds"
    )
    
    retry_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Retry policy configuration"
    )
    
    # Resource requirements
    resource_requirements: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="CPU, memory, and other resource requirements"
    )
    
    # Health and monitoring
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Last heartbeat timestamp"
    )
    
    health_check_interval: Mapped[int] = mapped_column(
        String(5),
        nullable=False,
        default="30",
        comment="Health check interval in seconds"
    )
    
    # Load balancing
    current_load: Mapped[int] = mapped_column(
        String(3),
        nullable=False,
        default="0",
        comment="Current number of active tasks"
    )
    
    total_capacity: Mapped[int] = mapped_column(
        String(3),
        nullable=False,
        default="5",
        comment="Total task capacity"
    )
    
    # Governance and compliance
    governance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether governance approval is required for tasks"
    )
    
    audit_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        comment="Audit logging level"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="agents",
        foreign_keys=[BaseModel.created_by],
        lazy="select"
    )
    
    tasks = relationship(
        "AgentTask",
        back_populates="agent",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    metrics = relationship(
        "AgentMetrics",
        back_populates="agent",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_agent_name_deleted"),
        Index("idx_agent_type_status", "agent_type", "status"),
        Index("idx_agent_load", "current_load"),
        Index("idx_agent_heartbeat", "last_heartbeat"),
        {"comment": "AI agents for multi-agent orchestration"}
    )
    
    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"<Agent(name='{self.name}', type='{self.agent_type}', status='{self.status}')>"
    
    @property
    def is_online(self) -> bool:
        """Check if agent is online."""
        return self.status != AgentStatus.OFFLINE
    
    @property
    def is_available(self) -> bool:
        """Check if agent is available for tasks."""
        return self.status == AgentStatus.IDLE and int(self.current_load) < int(self.max_concurrent_tasks)
    
    @property
    def load_percentage(self) -> float:
        """Calculate current load as percentage."""
        if int(self.total_capacity) == 0:
            return 0.0
        return (int(self.current_load) / int(self.total_capacity)) * 100
    
    @property
    def can_accept_task(self) -> bool:
        """Check if agent can accept a new task."""
        return (
            self.is_online and
            self.status == AgentStatus.IDLE and
            int(self.current_load) < int(self.max_concurrent_tasks)
        )
    
    def go_online(self) -> None:
        """Bring the agent online."""
        self.status = AgentStatus.IDLE
        self.last_heartbeat = datetime.utcnow()
        self.increment_version()
    
    def go_offline(self) -> None:
        """Take the agent offline."""
        self.status = AgentStatus.OFFLINE
        self.current_load = "0"
        self.increment_version()
    
    def start_task(self) -> bool:
        """
        Start a task on the agent.
        
        Returns:
            bool: True if task was started successfully
        """
        if not self.can_accept_task:
            return False
        
        self.status = AgentStatus.BUSY
        self.current_load = str(int(self.current_load) + 1)
        self.last_heartbeat = datetime.utcnow()
        return True
    
    def complete_task(self) -> None:
        """Complete a task on the agent."""
        current_load = int(self.current_load)
        if current_load > 0:
            self.current_load = str(current_load - 1)
        
        if int(self.current_load) == 0:
            self.status = AgentStatus.IDLE
        
        self.last_heartbeat = datetime.utcnow()
    
    def fail_task(self) -> None:
        """Handle task failure."""
        current_load = int(self.current_load)
        if current_load > 0:
            self.current_load = str(current_load - 1)
        
        self.status = AgentStatus.ERROR
        self.last_heartbeat = datetime.utcnow()
    
    def update_heartbeat(self) -> None:
        """Update the agent heartbeat."""
        self.last_heartbeat = datetime.utcnow()
        
        # Reset error status if heartbeat is successful
        if self.status == AgentStatus.ERROR:
            self.status = AgentStatus.IDLE if int(self.current_load) == 0 else AgentStatus.BUSY
    
    def add_capability(
        self,
        name: str,
        description: str,
        input_types: list[str],
        output_types: list[str],
        parameters: Dict[str, Any] | None = None
    ) -> None:
        """
        Add a capability to the agent.
        
        Args:
            name: Capability name
            description: Capability description
            input_types: Supported input types
            output_types: Supported output types
            parameters: Capability parameters
        """
        if "capabilities" not in self.config:
            self.config["capabilities"] = {}
        
        self.config["capabilities"][name] = {
            "description": description,
            "input_types": input_types,
            "output_types": output_types,
            "parameters": parameters or {}
        }
        
        self.increment_version()
    
    def has_capability(self, capability_name: str) -> bool:
        """
        Check if agent has a specific capability.
        
        Args:
            capability_name: Name of the capability
            
        Returns:
            bool: True if capability exists
        """
        capabilities = self.config.get("capabilities", {})
        return capability_name in capabilities


class AgentTask(BaseModel):
    """
    Agent task model.
    
    Tracks individual tasks assigned to agents with execution status and results.
    """
    
    __tablename__ = "agent_tasks"
    
    # References
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the agent"
    )
    
    # Task details
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique task identifier"
    )
    
    task_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of task"
    )
    
    priority: Mapped[TaskPriority] = mapped_column(
        ENUM(TaskPriority, name="task_priority"),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
        comment="Task priority"
    )
    
    # Input and output
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Input data for the task"
    )
    
    output_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output data from the task"
    )
    
    # Status and timing
    status: Mapped[TaskStatus] = mapped_column(
        ENUM(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Current task status"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Task creation time"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Task start time"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Task completion time"
    )
    
    duration_seconds: Mapped[int] = mapped_column(
        String(10),
        nullable=True,
        comment="Task execution duration in seconds"
    )
    
    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if task failed"
    )
    
    error_details: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed error information"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    max_retries: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="3",
        comment="Maximum number of retry attempts"
    )
    
    # Progress tracking
    progress_percent: Mapped[int] = mapped_column(
        String(3),
        nullable=False,
        default="0",
        comment="Progress percentage (0-100)"
    )
    
    current_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Current step in task execution"
    )
    
    # Resource usage
    resource_usage: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Resource usage during task execution"
    )
    
    # Metadata
    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional task metadata"
    )
    
    # Relationships
    agent = relationship(
        "Agent",
        back_populates="tasks",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_task_agent_status", "agent_id", "status"),
        Index("idx_task_type_priority", "task_type", "priority"),
        Index("idx_task_created", "created_at"),
        {"comment": "Individual tasks assigned to agents"}
    )
    
    def __repr__(self) -> str:
        """String representation of the task."""
        return f"<AgentTask(task_id='{self.task_id}', type='{self.task_type}', status='{self.status}')>"
    
    @property
    def is_pending(self) -> bool:
        """Check if task is pending."""
        return self.status == TaskStatus.PENDING
    
    @property
    def is_running(self) -> bool:
        """Check if task is running."""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """Check if task has completed."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return int(self.retry_count) < int(self.max_retries)
    
    @property
    def duration(self) -> int | None:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def start(self) -> None:
        """Start the task."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.progress_percent = "0"
    
    def complete(self, output_data: Dict[str, Any]) -> None:
        """
        Complete the task successfully.
        
        Args:
            output_data: Output data from the task
        """
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.output_data = output_data
        self.progress_percent = "100"
        
        if self.started_at:
            self.duration_seconds = str(int((self.completed_at - self.started_at).total_seconds()))
    
    def fail(self, error_message: str, error_details: Dict[str, Any] | None = None) -> None:
        """
        Mark the task as failed.
        
        Args:
            error_message: Error message
            error_details: Detailed error information
        """
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        
        if error_details:
            self.error_details = error_details
        
        if self.started_at:
            self.duration_seconds = str(int((self.completed_at - self.started_at).total_seconds()))
    
    def cancel(self) -> None:
        """Cancel the task."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def retry(self) -> bool:
        """
        Retry the task.
        
        Returns:
            bool: True if task can be retried
        """
        if not self.can_retry:
            return False
        
        self.retry_count = str(int(self.retry_count) + 1)
        self.status = TaskStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.error_details = None
        self.progress_percent = "0"
        
        return True
    
    def update_progress(self, progress: int, step: str | None = None) -> None:
        """
        Update task progress.
        
        Args:
            progress: Progress percentage (0-100)
            step: Current step description
        """
        self.progress_percent = str(min(100, max(0, progress)))
        if step:
            self.current_step = step


class AgentMetrics(BaseModel):
    """
    Agent metrics model.
    
    Tracks performance metrics and statistics for agents.
    """
    
    __tablename__ = "agent_metrics"
    
    # References
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the agent"
    )
    
    # Metrics period
    period_start: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Start of metrics period"
    )
    
    period_end: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="End of metrics period"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="hourly",
        comment="Period type (hourly, daily, weekly, monthly)"
    )
    
    # Task metrics
    tasks_completed: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of completed tasks"
    )
    
    tasks_failed: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of failed tasks"
    )
    
    tasks_cancelled: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of cancelled tasks"
    )
    
    # Performance metrics
    average_task_duration: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Average task duration in seconds"
    )
    
    success_rate: Mapped[float] = mapped_column(
        String(5),
        nullable=True,
        comment="Task success rate (0.0-1.0)"
    )
    
    throughput: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Tasks per hour"
    )
    
    # Resource usage
    cpu_usage_avg: Mapped[float] = mapped_column(
        String(5),
        nullable=True,
        comment="Average CPU usage percentage"
    )
    
    memory_usage_avg: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Average memory usage in MB"
    )
    
    disk_io_avg: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Average disk I/O in MB/s"
    )
    
    network_io_avg: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Average network I/O in MB/s"
    )
    
    # Availability metrics
    uptime_seconds: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Total uptime in seconds"
    )
    
    downtime_seconds: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Total downtime in seconds"
    )
    
    availability_percentage: Mapped[float] = mapped_column(
        String(5),
        nullable=True,
        comment="Availability percentage"
    )
    
    # Relationships
    agent = relationship(
        "Agent",
        back_populates="metrics",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("agent_id", "period_start", "period_end", "period_type", name="uq_agent_metrics_period"),
        Index("idx_metrics_period", "period_start", "period_end"),
        Index("idx_metrics_performance", "success_rate", "throughput"),
        {"comment": "Agent performance metrics and statistics"}
    )
    
    def __repr__(self) -> str:
        """String representation of the metrics."""
        return f"<AgentMetrics(period='{self.period_type}', tasks={self.tasks_completed})>"
    
    def calculate_derived_metrics(self) -> None:
        """Calculate derived metrics from base metrics."""
        total_tasks = int(self.tasks_completed) + int(self.tasks_failed) + int(self.tasks_cancelled)
        
        # Success rate
        if total_tasks > 0:
            self.success_rate = str(int(self.tasks_completed) / total_tasks)
        
        # Availability percentage
        total_time = int(self.uptime_seconds) + int(self.downtime_seconds)
        if total_time > 0:
            self.availability_percentage = str(int(self.uptime_seconds) / total_time)
        
        # Throughput (tasks per hour)
        period_duration = (self.period_end - self.period_start).total_seconds()
        if period_duration > 0:
            self.throughput = str((int(self.tasks_completed) / period_duration) * 3600)
    
    def record_task_completion(self, duration: float) -> None:
        """
        Record a task completion.
        
        Args:
            duration: Task duration in seconds
        """
        self.tasks_completed = str(int(self.tasks_completed) + 1)
        
        # Update average duration
        current_avg = float(self.average_task_duration or 0)
        completed_count = int(self.tasks_completed)
        new_avg = ((current_avg * (completed_count - 1)) + duration) / completed_count
        self.average_task_duration = str(new_avg)
    
    def record_task_failure(self) -> None:
        """Record a task failure."""
        self.tasks_failed = str(int(self.tasks_failed) + 1)
    
    def record_task_cancellation(self) -> None:
        """Record a task cancellation."""
        self.tasks_cancelled = str(int(self.tasks_cancelled) + 1)
    
    def update_resource_usage(
        self,
        cpu_usage: float,
        memory_usage: float,
        disk_io: float,
        network_io: float
    ) -> None:
        """
        Update resource usage metrics.
        
        Args:
            cpu_usage: CPU usage percentage
            memory_usage: Memory usage in MB
            disk_io: Disk I/O in MB/s
            network_io: Network I/O in MB/s
        """
        # Simple average update (could be enhanced with more sophisticated aggregation)
        self.cpu_usage_avg = str(cpu_usage)
        self.memory_usage_avg = str(memory_usage)
        self.disk_io_avg = str(disk_io)
        self.network_io_avg = str(network_io)
