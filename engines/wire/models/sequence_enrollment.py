"""
WIRE Sequence Enrollment Models

SQLAlchemy models for tracking subscriber enrollment
in email sequences.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    JSON, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class EnrollmentStatus(str, Enum):
    """Enrollment status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class SequenceEnrollment(Base):
    """
    Sequence enrollment model for WIRE engine.
    
    Tracks subscriber enrollment in sequences,
    progress, and completion status.
    """
    __tablename__ = "wire_sequence_enrollments"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey('email_core_subscribers.id'), nullable=False)
    sequence_id = Column(UUID(as_uuid=True), ForeignKey('wire_sequences.id'), nullable=False)
    
    # Enrollment status
    status = Column(String(20), nullable=False, default=EnrollmentStatus.ACTIVE, index=True)
    current_step = Column(Integer, default=1)  # 1-based step number
    total_steps = Column(Integer)  # Total steps in sequence at enrollment time
    
    # Timestamps
    enrolled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime(timezone=True))
    last_step_at = Column(DateTime(timezone=True))
    next_step_at = Column(DateTime(timezone=True), index=True)
    cancelled_at = Column(DateTime(timezone=True))
    paused_at = Column(DateTime(timezone=True))
    
    # Progress tracking
    steps_completed = Column(JSON, default=list)  # Array of completed step numbers
    steps_sent = Column(JSON, default=list)      # Array of sent step numbers
    steps_opened = Column(JSON, default=list)     # Array of opened step numbers
    steps_clicked = Column(JSON, default=list)    # Array of clicked step numbers
    
    # Performance metrics
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_unsubscribed = Column(Integer, default=0)
    
    # Enrollment metadata
    enrollment_source = Column(String(50))  # How they were enrolled
    enrollment_data = Column(JSON, default=dict)  # Data at enrollment time
    pause_reason = Column(Text)
    cancel_reason = Column(Text)
    
    # Completion tracking
    completion_percentage = Column(Float, default=0.0)
    average_engagement_time = Column(Float, default=0.0)  # Minutes to first engagement
    
    # Relationships
    subscriber = relationship("Subscriber", back_populates="sequence_enrollments")
    sequence = relationship("Sequence", back_populates="enrollments")
    
    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('subscriber_id', 'sequence_id', name='uq_subscriber_sequence'),
        Index('idx_enrollment_subscriber', 'subscriber_id'),
        Index('idx_enrollment_sequence', 'sequence_id'),
        Index('idx_enrollment_status', 'status'),
        Index('idx_enrollment_enrolled_at', 'enrolled_at'),
        Index('idx_enrollment_next_step', 'next_step_at'),
        Index('idx_enrollment_current_step', 'current_step'),
    )
    
    def __repr__(self) -> str:
        return f"<SequenceEnrollment(id={self.id}, subscriber_id={self.subscriber_id}, sequence_id={self.sequence_id}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "subscriber_id": str(self.subscriber_id),
            "sequence_id": str(self.sequence_id),
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "enrolled_at": self.enrolled_at.isoformat() if self.enrolled_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_step_at": self.last_step_at.isoformat() if self.last_step_at else None,
            "next_step_at": self.next_step_at.isoformat() if self.next_step_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "steps_completed": self.steps_completed,
            "steps_sent": self.steps_sent,
            "steps_opened": self.steps_opened,
            "steps_clicked": self.steps_clicked,
            "total_sent": self.total_sent,
            "total_opened": self.total_opened,
            "total_clicked": self.total_clicked,
            "total_unsubscribed": self.total_unsubscribed,
            "enrollment_source": self.enrollment_source,
            "enrollment_data": self.enrollment_data,
            "pause_reason": self.pause_reason,
            "cancel_reason": self.cancel_reason,
            "completion_percentage": self.completion_percentage,
            "average_engagement_time": self.average_engagement_time
        }
    
    @property
    def is_active(self) -> bool:
        """Check if enrollment is active."""
        return self.status == EnrollmentStatus.ACTIVE
    
    @property
    def is_completed(self) -> bool:
        """Check if enrollment is completed."""
        return self.status == EnrollmentStatus.COMPLETED
    
    @property
    def is_paused(self) -> bool:
        """Check if enrollment is paused."""
        return self.status == EnrollmentStatus.PAUSED
    
    @property
    def is_cancelled(self) -> bool:
        """Check if enrollment is cancelled."""
        return self.status == EnrollmentStatus.CANCELLED
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if not self.total_steps or self.total_steps == 0:
            return 0.0
        
        completed_steps = len(self.steps_completed or [])
        return (completed_steps / self.total_steps) * 100
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate for this enrollment."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_opened / self.total_sent) * 100
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate for this enrollment."""
        if self.total_opened == 0:
            return 0.0
        return (self.total_clicked / self.total_opened) * 100
    
    @property
    def unsubscribe_rate(self) -> float:
        """Calculate unsubscribe rate for this enrollment."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_unsubscribed / self.total_sent) * 100
    
    @property
    def days_since_enrollment(self) -> float:
        """Calculate days since enrollment."""
        if not self.enrolled_at:
            return 0.0
        
        now = datetime.now(timezone.utc)
        delta = now - self.enrolled_at
        return delta.total_seconds() / (24 * 60 * 60)
    
    @property
    def days_since_last_step(self) -> float:
        """Calculate days since last step."""
        if not self.last_step_at:
            return self.days_since_enrollment
        
        now = datetime.now(timezone.utc)
        delta = now - self.last_step_at
        return delta.total_seconds() / (24 * 60 * 60)
    
    def advance_to_next_step(self) -> bool:
        """Advance to next step if available."""
        if not self.total_steps or self.current_step >= self.total_steps:
            return False
        
        self.current_step += 1
        self.last_step_at = datetime.now(timezone.utc)
        
        # Update completion percentage
        self.completion_percentage = self.progress_percentage
        
        return True
    
    def complete_step(self, step_number: int) -> None:
        """Mark a step as completed."""
        if step_number not in (self.steps_completed or []):
            if not self.steps_completed:
                self.steps_completed = []
            self.steps_completed.append(step_number)
        
        # Update completion percentage
        self.completion_percentage = self.progress_percentage
        
        # Check if sequence is complete
        if self.total_steps and len(self.steps_completed) >= self.total_steps:
            self.complete()
    
    def mark_step_sent(self, step_number: int) -> None:
        """Mark a step as sent."""
        if step_number not in (self.steps_sent or []):
            if not self.steps_sent:
                self.steps_sent = []
            self.steps_sent.append(step_number)
        
        self.total_sent += 1
        self.last_step_at = datetime.now(timezone.utc)
    
    def mark_step_opened(self, step_number: int) -> None:
        """Mark a step as opened."""
        if step_number not in (self.steps_opened or []):
            if not self.steps_opened:
                self.steps_opened = []
            self.steps_opened.append(step_number)
        
        self.total_opened += 1
        
        # Calculate engagement time if this is the first engagement
        if self.average_engagement_time == 0 and self.enrolled_at:
            delta = datetime.now(timezone.utc) - self.enrolled_at
            self.average_engagement_time = delta.total_seconds() / 60
    
    def mark_step_clicked(self, step_number: int) -> None:
        """Mark a step as clicked."""
        if step_number not in (self.steps_clicked or []):
            if not self.steps_clicked:
                self.steps_clicked = []
            self.steps_clicked.append(step_number)
        
        self.total_clicked += 1
    
    def mark_unsubscribed(self) -> None:
        """Mark as unsubscribed."""
        self.total_unsubscribed += 1
    
    def pause(self, reason: str = None) -> None:
        """Pause enrollment."""
        self.status = EnrollmentStatus.PAUSED
        self.paused_at = datetime.now(timezone.utc)
        if reason:
            self.pause_reason = reason
    
    def resume(self) -> None:
        """Resume paused enrollment."""
        if self.status == EnrollmentStatus.PAUSED:
            self.status = EnrollmentStatus.ACTIVE
            self.paused_at = None
            self.pause_reason = None
    
    def cancel(self, reason: str = None) -> None:
        """Cancel enrollment."""
        self.status = EnrollmentStatus.CANCELLED
        self.cancelled_at = datetime.now(timezone.utc)
        if reason:
            self.cancel_reason = reason
    
    def complete(self) -> None:
        """Complete enrollment."""
        self.status = EnrollmentStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.completion_percentage = 100.0
        self.next_step_at = None
    
    def restart(self) -> None:
        """Restart enrollment from beginning."""
        self.status = EnrollmentStatus.ACTIVE
        self.current_step = 1
        self.steps_completed = []
        self.steps_sent = []
        self.steps_opened = []
        self.steps_clicked = []
        self.total_sent = 0
        self.total_opened = 0
        self.total_clicked = 0
        self.total_unsubscribed = 0
        self.completion_percentage = 0.0
        self.average_engagement_time = 0.0
        self.completed_at = None
        self.last_step_at = None
        self.cancelled_at = None
        self.paused_at = None
        self.pause_reason = None
        self.cancel_reason = None
    
    def skip_to_step(self, step_number: int) -> bool:
        """Skip to a specific step."""
        if not self.total_steps or step_number < 1 or step_number > self.total_steps:
            return False
        
        # Mark all previous steps as completed
        for i in range(1, step_number):
            self.complete_step(i)
        
        self.current_step = step_number
        self.last_step_at = datetime.now(timezone.utc)
        self.completion_percentage = self.progress_percentage
        
        return True
    
    def get_step_status(self, step_number: int) -> str:
        """Get status of a specific step."""
        if step_number in (self.steps_clicked or []):
            return "clicked"
        elif step_number in (self.steps_opened or []):
            return "opened"
        elif step_number in (self.steps_sent or []):
            return "sent"
        elif step_number in (self.steps_completed or []):
            return "completed"
        elif step_number < self.current_step:
            return "completed"
        elif step_number == self.current_step:
            return "current"
        else:
            return "pending"
    
    def get_progress_summary(self) -> dict:
        """Get progress summary for this enrollment."""
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": len(self.steps_completed or []),
            "sent_steps": len(self.steps_sent or []),
            "opened_steps": len(self.steps_opened or []),
            "clicked_steps": len(self.steps_clicked or []),
            "completion_percentage": self.completion_percentage,
            "status": self.status,
            "days_since_enrollment": self.days_since_enrollment,
            "days_since_last_step": self.days_since_last_step,
            "open_rate": self.open_rate,
            "click_rate": self.click_rate,
            "unsubscribe_rate": self.unsubscribe_rate,
            "average_engagement_time": self.average_engagement_time
        }
    
    def should_send_next_step(self) -> bool:
        """Check if next step should be sent now."""
        if not self.is_active:
            return False
        
        if not self.next_step_at:
            return False
        
        return datetime.now(timezone.utc) >= self.next_step_at
    
    def calculate_next_step_time(self, sequence_steps: list) -> datetime:
        """Calculate when the next step should be sent."""
        if not self.is_active or not sequence_steps:
            return None
        
        # Get the current step configuration
        if self.current_step < 1 or self.current_step > len(sequence_steps):
            return None
        
        current_step_config = sequence_steps[self.current_step - 1]
        delay = current_step_config.get("delay", {})
        
        # Calculate delay in minutes
        delay_value = delay.get("value", 0)
        delay_unit = delay.get("unit", "days")
        
        if delay_unit == "days":
            delay_minutes = delay_value * 24 * 60
        elif delay_unit == "hours":
            delay_minutes = delay_value * 60
        else:  # minutes
            delay_minutes = delay_value
        
        # Calculate next send time
        base_time = self.last_step_at or self.enrolled_at
        next_time = base_time + timezone.timedelta(minutes=delay_minutes)
        
        self.next_step_at = next_time
        return next_time
    
    def get_engagement_timeline(self) -> list:
        """Get timeline of engagement events."""
        timeline = []
        
        if self.enrolled_at:
            timeline.append({
                "event": "enrolled",
                "timestamp": self.enrolled_at.isoformat(),
                "step": None
            })
        
        # Add step events
        for i, step in enumerate(self.steps_sent or [], 1):
            timeline.append({
                "event": "sent",
                "timestamp": self.last_step_at.isoformat() if self.last_step_at else None,
                "step": step
            })
        
        for step in self.steps_opened or []:
            timeline.append({
                "event": "opened",
                "timestamp": self.last_step_at.isoformat() if self.last_step_at else None,
                "step": step
            })
        
        for step in self.steps_clicked or []:
            timeline.append({
                "event": "clicked",
                "timestamp": self.last_step_at.isoformat() if self.last_step_at else None,
                "step": step
            })
        
        if self.completed_at:
            timeline.append({
                "event": "completed",
                "timestamp": self.completed_at.isoformat(),
                "step": None
            })
        
        if self.cancelled_at:
            timeline.append({
                "event": "cancelled",
                "timestamp": self.cancelled_at.isoformat(),
                "step": None
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"] or "")
        
        return timeline
    
    def export_data(self) -> dict:
        """Export enrollment data for analysis."""
        return {
            "enrollment": self.to_dict(),
            "progress": self.get_progress_summary(),
            "timeline": self.get_engagement_timeline(),
            "step_statuses": {
                str(step): self.get_step_status(step)
                for step in range(1, (self.total_steps or 0) + 1)
            }
        }
