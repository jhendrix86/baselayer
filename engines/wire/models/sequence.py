"""
WIRE Sequence Models

SQLAlchemy models for email sequences with trigger conditions
and step management.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    JSON, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SequenceTrigger(str, Enum):
    """Sequence trigger conditions."""
    SUBSCRIPTION = "subscription"
    PURCHASE = "purchase"
    TAG_ADDED = "tag_added"
    MANUAL = "manual"
    DATE_BASED = "date_based"
    BEHAVIOR_BASED = "behavior_based"


class SequenceStatus(str, Enum):
    """Sequence lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Sequence(Base):
    """
    Email sequence model for WIRE engine.
    
    Defines automated email sequences with triggers,
    steps, and enrollment tracking.
    """
    __tablename__ = "wire_sequences"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    slug = Column(String(200), nullable=False, unique=True)
    
    # Trigger configuration
    trigger = Column(String(20), nullable=False, default=SequenceTrigger.SUBSCRIPTION)
    trigger_config = Column(JSON, default=dict)  # Specific trigger settings
    
    # Status and timing
    status = Column(String(20), nullable=False, default=SequenceStatus.DRAFT, index=True)
    timezone = Column(String(50), default="UTC")
    
    # Sequence content
    steps = Column(JSON, nullable=False)  # Array of step configurations
    
    # Enrollment settings
    max_enrollments = Column(Integer)  # Limit total enrollments
    enrollment_rate_limit = Column(Integer, default=100)  # Max per day
    auto_reenroll = Column(Boolean, default=False)  # Allow re-enrollment
    
    # Targeting
    segment_filters = Column(JSON, default=dict)  # Who can enroll
    exclusion_filters = Column(JSON, default=dict)  # Who to exclude
    
    # Analytics
    subscriber_count = Column(Integer, default=0)
    completion_rate = Column(Float, default=0.0)
    average_completion_time = Column(Float, default=0.0)  # In days
    
    # Performance metrics
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_unsubscribed = Column(Integer, default=0)
    
    # Settings
    send_on_weekends = Column(Boolean, default=True)
    send_time_start = Column(String(5), default="09:00")  # HH:MM format
    send_time_end = Column(String(5), default="17:00")    # HH:MM format
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    enrollments = relationship("SequenceEnrollment", back_populates="sequence", cascade="all, delete-orphan")
    email_logs = relationship("EmailLog", back_populates="sequence")
    
    # Indexes
    __table_args__ = (
        Index('idx_sequence_status', 'status'),
        Index('idx_sequence_trigger', 'trigger'),
        Index('idx_sequence_slug', 'slug'),
        Index('idx_sequence_created_at', 'created_at'),
        Index('idx_sequence_activated_at', 'activated_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Sequence(id={self.id}, name={self.name}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "slug": self.slug,
            "trigger": self.trigger,
            "trigger_config": self.trigger_config,
            "status": self.status,
            "timezone": self.timezone,
            "steps": self.steps,
            "max_enrollments": self.max_enrollments,
            "enrollment_rate_limit": self.enrollment_rate_limit,
            "auto_reenroll": self.auto_reenroll,
            "segment_filters": self.segment_filters,
            "exclusion_filters": self.exclusion_filters,
            "subscriber_count": self.subscriber_count,
            "completion_rate": self.completion_rate,
            "average_completion_time": self.average_completion_time,
            "total_sent": self.total_sent,
            "total_opened": self.total_opened,
            "total_clicked": self.total_clicked,
            "total_unsubscribed": self.total_unsubscribed,
            "send_on_weekends": self.send_on_weekends,
            "send_time_start": self.send_time_start,
            "send_time_end": self.send_time_end,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if sequence is active."""
        return self.status == SequenceStatus.ACTIVE
    
    @property
    def step_count(self) -> int:
        """Get number of steps in sequence."""
        return len(self.steps or [])
    
    @property
    def total_duration_days(self) -> int:
        """Get total duration of sequence in days."""
        if not self.steps:
            return 0
        
        total_days = 0
        for step in self.steps:
            delay = step.get("delay", {})
            if delay.get("unit") == "days":
                total_days += delay.get("value", 0)
            elif delay.get("unit") == "hours":
                total_days += delay.get("value", 0) / 24
            elif delay.get("unit") == "minutes":
                total_days += delay.get("value", 0) / (24 * 60)
        
        return int(total_days)
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_opened / self.total_sent) * 100
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate."""
        if self.total_opened == 0:
            return 0.0
        return (self.total_clicked / self.total_opened) * 100
    
    @property
    def unsubscribe_rate(self) -> float:
        """Calculate unsubscribe rate."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_unsubscribed / self.total_sent) * 100
    
    def get_step(self, step_number: int) -> Optional[dict]:
        """Get specific step by number."""
        if not self.steps or step_number < 1 or step_number > len(self.steps):
            return None
        return self.steps[step_number - 1]
    
    def get_step_delay(self, step_number: int) -> int:
        """Get step delay in minutes."""
        step = self.get_step(step_number)
        if not step:
            return 0
        
        delay = step.get("delay", {})
        value = delay.get("value", 0)
        unit = delay.get("unit", "days")
        
        if unit == "days":
            return value * 24 * 60
        elif unit == "hours":
            return value * 60
        elif unit == "minutes":
            return value
        else:
            return 0
    
    def can_enroll_subscriber(self, subscriber_filters: dict) -> bool:
        """Check if subscriber can be enrolled based on filters."""
        # Check segment filters
        if self.segment_filters:
            if not self._matches_filters(subscriber_filters, self.segment_filters):
                return False
        
        # Check exclusion filters
        if self.exclusion_filters:
            if self._matches_filters(subscriber_filters, self.exclusion_filters):
                return False
        
        # Check enrollment limit
        if self.max_enrollments and self.subscriber_count >= self.max_enrollments:
            return False
        
        return True
    
    def _matches_filters(self, subscriber_data: dict, filters: dict) -> bool:
        """Check if subscriber data matches filters."""
        # Simple filter matching - can be extended
        if "tags" in filters:
            required_tags = filters["tags"]
            subscriber_tags = subscriber_data.get("tags", [])
            
            if isinstance(required_tags, list):
                # Must have all required tags
                if not all(tag in subscriber_tags for tag in required_tags):
                    return False
            elif isinstance(required_tags, dict):
                if "any" in required_tags:
                    # Must have any of these tags
                    if not any(tag in subscriber_tags for tag in required_tags["any"]):
                        return False
                if "all" in required_tags:
                    # Must have all of these tags
                    if not all(tag in subscriber_tags for tag in required_tags["all"]):
                        return False
        
        if "source" in filters:
            if subscriber_data.get("source") not in filters["source"]:
                return False
        
        if "status" in filters:
            if subscriber_data.get("status") not in filters["status"]:
                return False
        
        return True
    
    def activate(self) -> None:
        """Activate sequence."""
        self.status = SequenceStatus.ACTIVE
        self.activated_at = datetime.now(timezone.utc)
    
    def pause(self) -> None:
        """Pause sequence."""
        self.status = SequenceStatus.PAUSED
    
    def archive(self) -> None:
        """Archive sequence."""
        self.status = SequenceStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
    
    def increment_subscriber_count(self) -> None:
        """Increment subscriber count."""
        self.subscriber_count += 1
    
    def update_analytics(self, sent: int = 0, opened: int = 0, clicked: int = 0, unsubscribed: int = 0) -> None:
        """Update analytics metrics."""
        self.total_sent += sent
        self.total_opened += opened
        self.total_clicked += clicked
        self.total_unsubscribed += unsubscribed
    
    def calculate_completion_rate(self) -> None:
        """Calculate completion rate from enrollments."""
        if self.subscriber_count == 0:
            self.completion_rate = 0.0
            return
        
        completed_count = sum(1 for enrollment in self.enrollments if enrollment.status == "completed")
        self.completion_rate = (completed_count / self.subscriber_count) * 100
    
    def validate_steps(self) -> List[str]:
        """Validate sequence steps and return errors."""
        errors = []
        
        if not self.steps:
            errors.append("Sequence must have at least one step")
            return errors
        
        for i, step in enumerate(self.steps, 1):
            # Check required fields
            if not step.get("subject"):
                errors.append(f"Step {i}: Subject is required")
            
            if not step.get("template_name"):
                errors.append(f"Step {i}: Template name is required")
            
            # Check delay
            delay = step.get("delay", {})
            if not delay.get("value"):
                errors.append(f"Step {i}: Delay value is required")
            
            if not delay.get("unit"):
                errors.append(f"Step {i}: Delay unit is required")
            
            if delay.get("unit") not in ["minutes", "hours", "days"]:
                errors.append(f"Step {i}: Invalid delay unit")
            
            # Check subject length
            subject = step.get("subject", "")
            if len(subject) > 60:
                errors.append(f"Step {i}: Subject too long (max 60 characters)")
            
            # Check for unsubscribe placeholder
            content = step.get("content", "")
            if "unsubscribe" not in content.lower():
                errors.append(f"Step {i}: Missing unsubscribe link")
        
        return errors
    
    def get_next_send_time(self, base_time: datetime, step_number: int) -> datetime:
        """Calculate next send time for a step."""
        delay_minutes = self.get_step_delay(step_number)
        next_time = base_time + timezone.timedelta(minutes=delay_minutes)
        
        # Check if sending is allowed at this time
        if not self._is_send_time_allowed(next_time):
            # Move to next allowed time
            next_time = self._get_next_allowed_send_time(next_time)
        
        return next_time
    
    def _is_send_time_allowed(self, send_time: datetime) -> bool:
        """Check if send time is within allowed hours."""
        if not self.send_on_weekends and send_time.weekday() >= 5:
            return False
        
        # Parse time ranges
        start_hour, start_min = map(int, self.send_time_start.split(":"))
        end_hour, end_min = map(int, self.send_time_end.split(":"))
        
        send_hour = send_time.hour
        send_min = send_time.minute
        
        # Convert to minutes for comparison
        send_minutes = send_hour * 60 + send_min
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        return start_minutes <= send_minutes <= end_minutes
    
    def _get_next_allowed_send_time(self, send_time: datetime) -> datetime:
        """Get next allowed send time."""
        # Move to next day if weekend
        while not self.send_on_weekends and send_time.weekday() >= 5:
            send_time += timezone.timedelta(days=1)
            send_time = send_time.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Adjust to allowed time range
        start_hour, start_min = map(int, self.send_time_start.split(":"))
        send_time = send_time.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        
        return send_time
    
    def get_trigger_description(self) -> str:
        """Get human-readable trigger description."""
        trigger_descriptions = {
            SequenceTrigger.SUBSCRIPTION: "When someone subscribes",
            SequenceTrigger.PURCHASE: "When someone makes a purchase",
            SequenceTrigger.TAG_ADDED: "When a tag is added",
            SequenceTrigger.MANUAL: "Manual enrollment",
            SequenceTrigger.DATE_BASED: "On a specific date",
            SequenceTrigger.BEHAVIOR_BASED: "Based on subscriber behavior"
        }
        
        base_desc = trigger_descriptions.get(self.trigger, self.trigger)
        
        # Add trigger config details
        if self.trigger_config:
            if self.trigger == SequenceTrigger.TAG_ADDED and "tag" in self.trigger_config:
                base_desc += f" ({self.trigger_config['tag']})"
            elif self.trigger == SequenceTrigger.DATE_BASED and "date" in self.trigger_config:
                base_desc += f" ({self.trigger_config['date']})"
        
        return base_desc
    
    def clone(self, new_name: str) -> 'Sequence':
        """Create a copy of this sequence."""
        new_sequence = Sequence(
            name=new_name,
            description=self.description,
            trigger=self.trigger,
            trigger_config=self.trigger_config.copy(),
            steps=[step.copy() for step in self.steps],
            segment_filters=self.segment_filters.copy() if self.segment_filters else {},
            exclusion_filters=self.exclusion_filters.copy() if self.exclusion_filters else {},
            send_on_weekends=self.send_on_weekends,
            send_time_start=self.send_time_start,
            send_time_end=self.send_time_end,
            timezone=self.timezone
        )
        
        return new_sequence
