"""
PULSE Broadcast Models

SQLAlchemy models for email broadcasts and newsletters
with segmentation and scheduling support.
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


class BroadcastStatus(str, Enum):
    """Broadcast lifecycle status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BroadcastType(str, Enum):
    """Broadcast types."""
    NEWSLETTER = "newsletter"
    PRODUCT_LAUNCH = "product_launch"
    ANNOUNCEMENT = "announcement"
    PROMOTION = "promotion"
    SURVEY = "survey"


class Broadcast(Base):
    """
    Email broadcast model for PULSE engine.
    
    Represents newsletters and one-off email broadcasts
    with segmentation and scheduling capabilities.
    """
    __tablename__ = "pulse_broadcasts"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(200), nullable=False)
    subject = Column(String(255), nullable=False)
    preview_text = Column(String(150))
    description = Column(Text)
    
    # Content
    content_md = Column(Text, nullable=False)  # Markdown source
    content_html = Column(Text, nullable=False)  # Rendered HTML
    content_text = Column(Text)  # Plain text fallback
    
    # Broadcast configuration
    broadcast_type = Column(String(20), nullable=False, default=BroadcastType.NEWSLETTER)
    template_name = Column(String(100), default="newsletter")
    
    # Targeting and segmentation
    segment_filters = Column(JSON, default=dict)  # Who to send to
    exclusion_filters = Column(JSON, default=dict)  # Who to exclude
    test_segment = Column(JSON, default=dict)  # Test segment for A/B testing
    
    # Status and scheduling
    status = Column(String(20), nullable=False, default=BroadcastStatus.DRAFT, index=True)
    scheduled_at = Column(DateTime(timezone=True), index=True)
    sent_at = Column(DateTime(timezone=True))
    
    # Delivery settings
    sender_name = Column(String(100), default="Kade Digital")
    sender_email = Column(String(255), default="noreply@example.com")
    reply_to_email = Column(String(255))
    
    # Performance tracking
    recipient_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    bounce_count = Column(Integer, default=0)
    unsubscribe_count = Column(Integer, default=0)
    complaint_count = Column(Integer, default=0)
    
    # A/B testing
    is_ab_test = Column(Boolean, default=False)
    test_variants = Column(JSON, default=list)  # A/B test variants
    test_winner = Column(JSON)  # Winning variant data
    
    # Campaign settings
    campaign_name = Column(String(200))  # For analytics grouping
    campaign_tags = Column(JSON, default=list)
    
    # Quality controls
    word_count = Column(Integer, default=0)
    reading_time_minutes = Column(Integer, default=0)
    spam_score = Column(Float, default=0.0)
    
    # Scheduling preferences
    send_timezone = Column(String(50), default="UTC")
    send_time_start = Column(String(5), default="09:00")  # HH:MM format
    send_time_end = Column(String(5), default="17:00")    # HH:MM format
    send_on_weekends = Column(Boolean, default=True)
    
    # Rate limiting
    send_rate_limit = Column(Integer, default=100)  # Emails per minute
    batch_size = Column(Integer, default=1000)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    created_by = Column(String(100))
    last_modified_by = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    email_logs = relationship("EmailLog", back_populates="broadcast")
    
    # Indexes
    __table_args__ = (
        Index('idx_broadcast_status', 'status'),
        Index('idx_broadcast_type', 'broadcast_type'),
        Index('idx_broadcast_scheduled_at', 'scheduled_at'),
        Index('idx_broadcast_sent_at', 'sent_at'),
        Index('idx_broadcast_created_at', 'created_at'),
        Index('idx_broadcast_campaign', 'campaign_name'),
    )
    
    def __repr__(self) -> str:
        return f"<Broadcast(id={self.id}, name={self.name}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "subject": self.subject,
            "preview_text": self.preview_text,
            "description": self.description,
            "content_md": self.content_md,
            "content_html": self.content_html,
            "content_text": self.content_text,
            "broadcast_type": self.broadcast_type,
            "template_name": self.template_name,
            "segment_filters": self.segment_filters,
            "exclusion_filters": self.exclusion_filters,
            "test_segment": self.test_segment,
            "status": self.status,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "reply_to_email": self.reply_to_email,
            "recipient_count": self.recipient_count,
            "sent_count": self.sent_count,
            "delivered_count": self.delivered_count,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "bounce_count": self.bounce_count,
            "unsubscribe_count": self.unsubscribe_count,
            "complaint_count": self.complaint_count,
            "is_ab_test": self.is_ab_test,
            "test_variants": self.test_variants,
            "test_winner": self.test_winner,
            "campaign_name": self.campaign_name,
            "campaign_tags": self.campaign_tags,
            "word_count": self.word_count,
            "reading_time_minutes": self.reading_time_minutes,
            "spam_score": self.spam_score,
            "send_timezone": self.send_timezone,
            "send_time_start": self.send_time_start,
            "send_time_end": self.send_time_end,
            "send_on_weekends": self.send_on_weekends,
            "send_rate_limit": self.send_rate_limit,
            "batch_size": self.batch_size,
            "metadata": self.metadata,
            "created_by": self.created_by,
            "last_modified_by": self.last_modified_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_draft(self) -> bool:
        """Check if broadcast is in draft status."""
        return self.status == BroadcastStatus.DRAFT
    
    @property
    def is_scheduled(self) -> bool:
        """Check if broadcast is scheduled."""
        return self.status == BroadcastStatus.SCHEDULED
    
    @property
    def is_sent(self) -> bool:
        """Check if broadcast has been sent."""
        return self.status == BroadcastStatus.SENT
    
    @property
    def is_sending(self) -> bool:
        """Check if broadcast is currently sending."""
        return self.status == BroadcastStatus.SENDING
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate."""
        if self.delivered_count == 0:
            return 0.0
        return (self.open_count / self.delivered_count) * 100
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate."""
        if self.open_count == 0:
            return 0.0
        return (self.click_count / self.open_count) * 100
    
    @property
    def bounce_rate(self) -> float:
        """Calculate bounce rate."""
        if self.sent_count == 0:
            return 0.0
        return (self.bounce_count / self.sent_count) * 100
    
    @property
    def unsubscribe_rate(self) -> float:
        """Calculate unsubscribe rate."""
        if self.delivered_count == 0:
            return 0.0
        return (self.unsubscribe_count / self.delivered_count) * 100
    
    @property
    def delivery_rate(self) -> float:
        """Calculate delivery rate."""
        if self.sent_count == 0:
            return 0.0
        return (self.delivered_count / self.sent_count) * 100
    
    def schedule(self, send_time: datetime, creator: str = None) -> None:
        """Schedule broadcast for sending."""
        self.status = BroadcastStatus.SCHEDULED
        self.scheduled_at = send_time
        if creator:
            self.last_modified_by = creator
    
    def unschedule(self) -> None:
        """Unschedule broadcast."""
        self.status = BroadcastStatus.DRAFT
        self.scheduled_at = None
    
    def start_sending(self) -> None:
        """Mark broadcast as sending."""
        self.status = BroadcastStatus.SENDING
        self.sent_at = datetime.now(timezone.utc)
    
    def mark_as_sent(self) -> None:
        """Mark broadcast as sent."""
        self.status = BroadcastStatus.SENT
        self.sent_at = datetime.now(timezone.utc)
    
    def cancel(self, reason: str = None) -> None:
        """Cancel broadcast."""
        self.status = BroadcastStatus.CANCELLED
        if reason:
            self.metadata = self.metadata or {}
            self.metadata["cancellation_reason"] = reason
    
    def fail(self, error_message: str = None) -> None:
        """Mark broadcast as failed."""
        self.status = BroadcastStatus.FAILED
        if error_message:
            self.metadata = self.metadata or {}
            self.metadata["failure_reason"] = error_message
    
    def update_content(self, subject: str, content_md: str, content_html: str, modifier: str = None) -> None:
        """Update broadcast content."""
        self.subject = subject
        self.content_md = content_md
        self.content_html = content_html
        self.word_count = len(content_md.split())
        self.reading_time_minutes = max(1, self.word_count // 200)  # Assume 200 words per minute
        if modifier:
            self.last_modified_by = modifier
    
    def increment_sent(self, count: int = 1) -> None:
        """Increment sent count."""
        self.sent_count += count
    
    def increment_delivered(self, count: int = 1) -> None:
        """Increment delivered count."""
        self.delivered_count += count
    
    def increment_opened(self, count: int = 1) -> None:
        """Increment open count."""
        self.open_count += count
    
    def increment_clicked(self, count: int = 1) -> None:
        """Increment click count."""
        self.click_count += count
    
    def increment_bounced(self, count: int = 1) -> None:
        """Increment bounce count."""
        self.bounce_count += count
    
    def increment_unsubscribed(self, count: int = 1) -> None:
        """Increment unsubscribe count."""
        self.unsubscribe_count += count
    
    def increment_complained(self, count: int = 1) -> None:
        """Increment complaint count."""
        self.complaint_count += count
    
    def calculate_spam_score(self) -> float:
        """Calculate spam score based on content."""
        score = 0.0
        
        content_lower = self.content_html.lower()
        
        # Spam trigger words
        spam_triggers = [
            "free money", "click here", "act now", "limited time",
            "urgent", "congratulations", "winner", "!!!", "$$$"
        ]
        
        for trigger in spam_triggers:
            if trigger in content_lower:
                score += 0.1
        
        # Check for excessive capitalization
        caps_words = [word for word in content_lower.split() if word.isupper() and len(word) > 3]
        score += len(caps_words) * 0.05
        
        # Check for excessive punctuation
        excessive_punct = content_lower.count('!!!') + content_lower.count('$$$')
        score += excessive_punct * 0.1
        
        # Check subject length
        if len(self.subject) > 50:
            score += 0.1
        
        # Check for balance of text and images
        img_tags = content_lower.count('<img')
        if img_tags > 5:
            score += 0.1
        
        return min(1.0, score)
    
    def validate_content(self) -> List[str]:
        """Validate broadcast content and return errors."""
        errors = []
        
        # Basic content validation
        if not self.subject:
            errors.append("Subject is required")
        elif len(self.subject) > 255:
            errors.append("Subject too long (max 255 characters)")
        
        if not self.content_html:
            errors.append("HTML content is required")
        
        if not self.content_md:
            errors.append("Markdown content is required")
        
        # Word count validation
        if self.word_count < 100:
            errors.append("Content too short (minimum 100 words)")
        elif self.word_count > 10000:
            errors.append("Content too long (maximum 10,000 words)")
        
        # CAN-SPAM compliance
        if "unsubscribe" not in self.content_html.lower():
            errors.append("Missing unsubscribe link")
        
        if not any(addr in self.content_html.lower() for addr in ["address", "street", "suite"]):
            errors.append("Missing physical address")
        
        # Spam score check
        self.spam_score = self.calculate_spam_score()
        if self.spam_score > 0.5:
            errors.append(f"High spam score: {self.spam_score:.2f}")
        
        # Kade persona compliance
        persona_violations = self._check_persona_compliance()
        errors.extend(persona_violations)
        
        return errors
    
    def _check_persona_compliance(self) -> List[str]:
        """Check Kade persona compliance."""
        violations = []
        
        content_lower = self.content_html.lower()
        
        # Check for first-person references
        first_person_indicators = ["i think", "i believe", "in my opinion", "my experience"]
        for indicator in first_person_indicators:
            if indicator in content_lower:
                violations.append(f"First-person reference: {indicator}")
        
        # Check for personal anecdotes
        anecdote_indicators = ["when i", "i once", "my story", "personally"]
        for indicator in anecdote_indicators:
            if indicator in content_lower:
                violations.append(f"Personal anecdote: {indicator}")
        
        # Check for placeholder text
        placeholder_indicators = ["lorem ipsum", "placeholder", "[", "]", "{{", "}}"]
        for indicator in placeholder_indicators:
            if indicator in content_lower:
                violations.append(f"Placeholder text: {indicator}")
        
        return violations
    
    def get_segment_summary(self) -> dict:
        """Get summary of segment filters."""
        return {
            "target_segment": self.segment_filters,
            "exclusion_segment": self.exclusion_filters,
            "estimated_recipients": self.recipient_count,
            "segment_complexity": self._calculate_segment_complexity()
        }
    
    def _calculate_segment_complexity(self) -> str:
        """Calculate segment complexity."""
        filters = self.segment_filters or {}
        
        complexity = 0
        if filters.get("tags"):
            complexity += len(filters["tags"])
        if filters.get("status"):
            complexity += 1
        if filters.get("date_range"):
            complexity += 2
        if filters.get("engagement"):
            complexity += 2
        
        if complexity <= 2:
            return "simple"
        elif complexity <= 5:
            return "moderate"
        else:
            return "complex"
    
    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        return {
            "delivery_metrics": {
                "sent": self.sent_count,
                "delivered": self.delivered_count,
                "delivery_rate": self.delivery_rate
            },
            "engagement_metrics": {
                "opens": self.open_count,
                "clicks": self.click_count,
                "open_rate": self.open_rate,
                "click_rate": self.click_rate
            },
            "negative_metrics": {
                "bounces": self.bounce_count,
                "unsubscribes": self.unsubscribe_count,
                "complaints": self.complaint_count,
                "bounce_rate": self.bounce_rate,
                "unsubscribe_rate": self.unsubscribe_rate
            },
            "content_metrics": {
                "word_count": self.word_count,
                "reading_time": self.reading_time_minutes,
                "spam_score": self.spam_score
            }
        }
    
    def clone(self, new_name: str) -> 'Broadcast':
        """Create a copy of this broadcast."""
        new_broadcast = Broadcast(
            name=new_name,
            subject=f"COPY: {self.subject}",
            preview_text=self.preview_text,
            description=self.description,
            content_md=self.content_md,
            content_html=self.content_html,
            content_text=self.content_text,
            broadcast_type=self.broadcast_type,
            template_name=self.template_name,
            segment_filters=self.segment_filters.copy() if self.segment_filters else {},
            exclusion_filters=self.exclusion_filters.copy() if self.exclusion_filters else {},
            sender_name=self.sender_name,
            sender_email=self.sender_email,
            reply_to_email=self.reply_to_email,
            campaign_name=self.campaign_name,
            campaign_tags=self.campaign_tags.copy() if self.campaign_tags else [],
            send_timezone=self.send_timezone,
            send_time_start=self.send_time_start,
            send_time_end=self.send_time_end,
            send_on_weekends=self.send_on_weekends,
            send_rate_limit=self.send_rate_limit,
            batch_size=self.batch_size,
            metadata=self.metadata.copy() if self.metadata else {}
        )
        
        return new_broadcast
    
    def get_test_variants_summary(self) -> dict:
        """Get summary of A/B test variants."""
        if not self.is_ab_test or not self.test_variants:
            return {"has_test": False}
        
        return {
            "has_test": True,
            "variants": self.test_variants,
            "winner": self.test_winner,
            "variant_count": len(self.test_variants)
        }
    
    def add_campaign_tag(self, tag: str) -> None:
        """Add a campaign tag."""
        if not self.campaign_tags:
            self.campaign_tags = []
        
        if tag not in self.campaign_tags:
            self.campaign_tags.append(tag)
    
    def remove_campaign_tag(self, tag: str) -> None:
        """Remove a campaign tag."""
        if self.campaign_tags and tag in self.campaign_tags:
            self.campaign_tags.remove(tag)
    
    def get_sending_window(self) -> tuple:
        """Get sending window as time range."""
        start_hour, start_min = map(int, self.send_time_start.split(":"))
        end_hour, end_min = map(int, self.send_time_end.split(":"))
        
        return (start_hour * 60 + start_min, end_hour * 60 + end_min)
