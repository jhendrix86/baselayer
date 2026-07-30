"""
BaseLayer Core Loop Models

Workflow orchestration, execution tracking, and step management
for the Core Loop subsystem.
"""

from datetime import datetime

import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowPriority(str, Enum):
    """Workflow priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StepType(str, Enum):
    """Workflow step types."""
    TASK = "task"
    DECISION = "decision"
    PARALLEL = "parallel"
    DELAY = "delay"
    WEBHOOK = "webhook"
    AGENT = "agent"


class ScheduleType(str, Enum):
    """Workflow schedule types."""
    ONCE = "once"
    RECURRING = "recurring"
    CRON = "cron"


class BackoffType(str, Enum):
    """Retry backoff strategies."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class Workflow(BaseModel):
    """
    Workflow model for Core Loop orchestration.
    
    Defines automated workflows with steps, schedules, and execution tracking.
    """
    
    __tablename__ = "workflows"
    
    # Basic workflow information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Workflow name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Workflow description"
    )
    
    # Status and priority
    status: Mapped[WorkflowStatus] = mapped_column(
        ENUM(WorkflowStatus, name="workflow_status"),
        nullable=False,
        default=WorkflowStatus.DRAFT,
        index=True,
        comment="Current workflow status"
    )
    
    priority: Mapped[WorkflowPriority] = mapped_column(
        ENUM(WorkflowPriority, name="workflow_priority"),
        nullable=False,
        default=WorkflowPriority.MEDIUM,
        index=True,
        comment="Workflow priority"
    )
    
    # Configuration
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Workflow configuration including steps and variables"
    )
    
    # Scheduling
    schedule_type: Mapped[ScheduleType] = mapped_column(
        ENUM(ScheduleType, name="schedule_type"),
        nullable=True,
        comment="Type of scheduling"
    )
    
    schedule_expression: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Schedule expression (cron, interval, etc.)"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Timezone for scheduling"
    )
    
    # Execution settings
    timeout_seconds: Mapped[int] = mapped_column(
        String(20),
        nullable=True,
        comment="Timeout in seconds for workflow execution"
    )
    
    max_retries: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="3",
        comment="Maximum number of retry attempts"
    )
    
    retry_backoff_type: Mapped[BackoffType] = mapped_column(
        ENUM(BackoffType, name="retry_backoff_type"),
        nullable=False,
        default=BackoffType.EXPONENTIAL,
        comment="Retry backoff strategy"
    )
    
    retry_delay_seconds: Mapped[int] = mapped_column(
        String(20),
        nullable=False,
        default="60",
        comment="Base delay between retries in seconds"
    )
    
    # Governance and compliance
    governance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether governance approval is required"
    )
    
    audit_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        comment="Audit logging level"
    )
    
    # Metadata
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Workflow category"
    )
    
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Workflow tags for categorization"
    )
    
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Workflow version"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="workflows",
        foreign_keys=[BaseModel.created_by],
        lazy="select"
    )
    
    executions = relationship(
        "WorkflowExecution",
        back_populates="workflow",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_workflow_name_deleted"),
        Index("idx_workflow_status_priority", "status", "priority"),
        Index("idx_workflow_category", "category"),
        Index("idx_workflow_created_at", "created_at"),
        {"comment": "Workflow definitions for Core Loop orchestration"}
    )
    
    def __repr__(self) -> str:
        """String representation of the workflow."""
        return f"<Workflow(name='{self.name}', status='{self.status}', priority='{self.priority}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if workflow is active."""
        return self.status == WorkflowStatus.ACTIVE
    
    @property
    def can_execute(self) -> bool:
        """Check if workflow can be executed."""
        return self.status in {WorkflowStatus.ACTIVE, WorkflowStatus.COMPLETED}
    
    def activate(self) -> None:
        """Activate the workflow."""
        self.status = WorkflowStatus.ACTIVE
        self.increment_version()
    
    def pause(self) -> None:
        """Pause the workflow."""
        self.status = WorkflowStatus.PAUSED
        self.increment_version()
    
    def cancel(self) -> None:
        """Cancel the workflow."""
        self.status = WorkflowStatus.CANCELLED
        self.increment_version()
    
    def get_step_config(self, step_id: str) -> Dict[str, Any] | None:
        """
        Get configuration for a specific step.
        
        Args:
            step_id: ID of the step
            
        Returns:
            Dict[str, Any] | None: Step configuration or None if not found
        """
        steps = self.config.get("steps", [])
        for step in steps:
            if step.get("id") == step_id:
                return step
        return None
    
    def add_step(
        self,
        step_id: str,
        name: str,
        step_type: StepType,
        config: Dict[str, Any],
        dependencies: list[str] | None = None
    ) -> None:
        """
        Add a step to the workflow.
        
        Args:
            step_id: Unique step identifier
            name: Step name
            step_type: Type of step
            config: Step configuration
            dependencies: List of step dependencies
        """
        if "steps" not in self.config:
            self.config["steps"] = []
        
        step = {
            "id": step_id,
            "name": name,
            "type": step_type.value,
            "config": config,
            "dependencies": dependencies or [],
            "timeout": self.timeout_seconds,
            "retry_policy": {
                "max_attempts": int(self.max_retries),
                "backoff_type": self.retry_backoff_type.value,
                "base_delay": int(self.retry_delay_seconds)
            }
        }
        
        self.config["steps"].append(step)
        self.increment_version()
    
    def remove_step(self, step_id: str) -> bool:
        """
        Remove a step from the workflow.
        
        Args:
            step_id: ID of the step to remove
            
        Returns:
            bool: True if step was removed, False if not found
        """
        if "steps" not in self.config:
            return False
        
        original_length = len(self.config["steps"])
        self.config["steps"] = [
            step for step in self.config["steps"]
            if step.get("id") != step_id
        ]
        
        if len(self.config["steps"]) < original_length:
            self.increment_version()
            return True
        
        return False


class WorkflowExecution(BaseModel):
    """
    Workflow execution tracking model.
    
    Tracks individual workflow executions with status, logs, and metrics.
    """
    
    __tablename__ = "workflow_executions"
    
    # Execution reference
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the workflow"
    )
    
    # Execution details
    execution_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique execution identifier"
    )
    
    # Status and timing
    status: Mapped[WorkflowStatus] = mapped_column(
        ENUM(WorkflowStatus, name="execution_status"),
        nullable=False,
        default=WorkflowStatus.DRAFT,
        index=True,
        comment="Current execution status"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Execution start time"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Execution completion time"
    )
    
    duration_seconds: Mapped[int] = mapped_column(
        String(20),
        nullable=True,
        comment="Total execution duration in seconds"
    )
    
    # Input and output
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Input data for the execution"
    )
    
    output_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output data from the execution"
    )
    
    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if execution failed"
    )
    
    error_details: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed error information"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    # Progress tracking
    current_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of currently executing step"
    )
    
    progress_percent: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Progress percentage (0-100)"
    )
    
    # Metrics
    steps_completed: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of completed steps"
    )
    
    steps_failed: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of failed steps"
    )
    
    # Relationships
    workflow = relationship(
        "Workflow",
        back_populates="executions",
        lazy="select"
    )
    
    step_executions = relationship(
        "WorkflowStepExecution",
        back_populates="execution",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_execution_workflow_status", "workflow_id", "status"),
        Index("idx_execution_started_at", "started_at"),
        Index("idx_execution_progress", "progress_percent"),
        {"comment": "Workflow execution tracking and monitoring"}
    )
    
    def __repr__(self) -> str:
        """String representation of the execution."""
        return f"<WorkflowExecution(execution_id='{self.execution_id}', status='{self.status}')>"
    
    @property
    def is_running(self) -> bool:
        """Check if execution is currently running."""
        return self.status == WorkflowStatus.ACTIVE
    
    @property
    def is_completed(self) -> bool:
        """Check if execution has completed (successfully or not)."""
        return self.status in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}
    
    @property
    def duration(self) -> int | None:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def start(self, input_data: Dict[str, Any] | None = None) -> None:
        """
        Start the workflow execution.
        
        Args:
            input_data: Input data for the execution
        """
        self.status = WorkflowStatus.ACTIVE
        self.started_at = datetime.utcnow()
        self.progress_percent = "0"
        self.steps_completed = "0"
        self.steps_failed = "0"
        
        if input_data:
            self.input_data = input_data
    
    def complete(self, output_data: Dict[str, Any] | None = None) -> None:
        """
        Complete the workflow execution successfully.
        
        Args:
            output_data: Output data from the execution
        """
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress_percent = "100"
        
        if output_data:
            self.output_data = output_data
        
        if self.started_at:
            self.duration_seconds = str(int((self.completed_at - self.started_at).total_seconds()))
    
    def fail(self, error_message: str, error_details: Dict[str, Any] | None = None) -> None:
        """
        Mark the execution as failed.
        
        Args:
            error_message: Error message
            error_details: Detailed error information
        """
        self.status = WorkflowStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        
        if error_details:
            self.error_details = error_details
        
        if self.started_at:
            self.duration_seconds = str(int((self.completed_at - self.started_at).total_seconds()))
    
    def update_progress(self, step_id: str, progress: int) -> None:
        """
        Update execution progress.
        
        Args:
            step_id: ID of the current step
            progress: Progress percentage (0-100)
        """
        self.current_step = step_id
        self.progress_percent = str(min(100, max(0, progress)))


class WorkflowStep(BaseModel):
    """
    Individual workflow step model.
    
    Defines reusable workflow steps with configuration and validation.
    """
    
    __tablename__ = "workflow_steps"
    
    # Step identification
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the workflow"
    )
    
    step_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique step identifier within workflow"
    )
    
    # Step details
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Step name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Step description"
    )
    
    step_type: Mapped[StepType] = mapped_column(
        ENUM(StepType, name="step_type"),
        nullable=False,
        index=True,
        comment="Type of workflow step"
    )
    
    # Configuration
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Step configuration parameters"
    )
    
    # Dependencies
    dependencies: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of step dependencies"
    )
    
    # Timing and retry
    timeout_seconds: Mapped[int] = mapped_column(
        String(20),
        nullable=True,
        comment="Step timeout in seconds"
    )
    
    retry_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Retry policy configuration"
    )
    
    # Validation
    input_schema: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Input validation schema"
    )
    
    output_schema: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output validation schema"
    )
    
    # Relationships
    workflow = relationship(
        "Workflow",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_id", name="uq_workflow_step"),
        Index("idx_step_type", "step_type"),
        {"comment": "Individual workflow steps with configuration"}
    )
    
    def __repr__(self) -> str:
        """String representation of the workflow step."""
        return f"<WorkflowStep(step_id='{self.step_id}', type='{self.step_type}')>"
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate input data against the step's schema.
        
        Args:
            data: Input data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # TODO: Implement JSON schema validation
        return True
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """
        Validate output data against the step's schema.
        
        Args:
            data: Output data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # TODO: Implement JSON schema validation
        return True


class WorkflowStepExecution(BaseModel):
    """
    Workflow step execution tracking model.
    
    Tracks individual step executions within a workflow execution.
    """
    
    __tablename__ = "workflow_step_executions"
    
    # References
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the workflow execution"
    )
    
    step_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Step identifier"
    )
    
    # Execution details
    status: Mapped[WorkflowStatus] = mapped_column(
        ENUM(WorkflowStatus, name="step_execution_status"),
        nullable=False,
        default=WorkflowStatus.DRAFT,
        index=True,
        comment="Current step execution status"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Step execution start time"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Step execution completion time"
    )
    
    duration_seconds: Mapped[int] = mapped_column(
        String(20),
        nullable=True,
        comment="Step execution duration in seconds"
    )
    
    # Data
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Input data for the step"
    )
    
    output_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output data from the step"
    )
    
    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if step failed"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    # Relationships
    execution = relationship(
        "WorkflowExecution",
        back_populates="step_executions",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("execution_id", "step_id", name="uq_execution_step"),
        Index("idx_step_execution_status", "status"),
        Index("idx_step_execution_started", "started_at"),
        {"comment": "Individual step execution tracking"}
    )
    
    def __repr__(self) -> str:
        """String representation of the step execution."""
        return f"<WorkflowStepExecution(step_id='{self.step_id}', status='{self.status}')>"
    
    @property
    def duration(self) -> int | None:
        """Calculate step execution duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
