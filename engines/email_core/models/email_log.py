"""
EMAIL_CORE Email Log Models

SQLAlchemy models for email delivery and engagement tracking.
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


class EmailType(str, Enum):
    """Email types for categorization."""
    SEQUENCE = "sequence"
    BROADCAST = "broadcast"
    TRANSACTIONAL = "transactional"
    WELCOME = "welcome"
    NEWSLETTER = "newsletter"
    PRODUCT_LAUNCH = "product_launch"


class EmailStatus(str, Enum):
    """Email delivery status."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailLog(Base):
    """
    Email delivery and engagement log model.
    
    Tracks all email sending activity and engagement metrics
    for analytics and compliance purposes.
    """
    __tablename__ = "email_core_email_logs"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey('email_core_subscribers.id'), nullable=False)
    sequence_id = Column(UUID(as_uuid=True), ForeignKey('wire_sequences.id'))
    broadcast_id = Column(UUID(as_uuid=True), ForeignKey('pulse_broadcasts.id'))
    
    # Email information
    email_type = Column(String(20), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    preview_text = Column(String(150))
    
    # Template and content
    template_name = Column(String(100))
    template_version = Column(String(20))
    content_html = Column(Text)
    content_text = Column(Text)
    
    # Delivery tracking
    brevo_message_id = Column(String(100), unique=True)
    status = Column(String(20), nullable=False, default=EmailStatus.QUEUED, index=True)
    
    # Timestamps
    queued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    opened_at = Column(DateTime(timezone=True))
    clicked_at = Column(DateTime(timezone=True))
    bounced_at = Column(DateTime(timezone=True))
    complained_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    
    # Engagement metrics
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    
    # Delivery details
    delivery_provider = Column(String(20), default="brevo")
    delivery_attempts = Column(Integer, default=0)
    last_delivery_attempt = Column(DateTime(timezone=True))
    
    # Bounce and complaint details
    bounce_type = Column(String(50))  # hard, soft, transient
    bounce_reason = Column(Text)
    complaint_type = Column(String(50))  # spam, abuse, unsubscribe
    
    # Click tracking
    click_urls = Column(JSON, default=list)  # Track clicked URLs
    click_user_agent = Column(String(500))
    click_ip_address = Column(String(45))  # IPv6 compatible
    
    # Open tracking
    open_user_agent = Column(String(500))
    open_ip_address = Column(String(45))
    open_location = Column(JSON)  # Country, city from IP
    
    # Metadata
    metadata = Column(JSON, default=dict)
    campaign_data = Column(JSON, default=dict)  # A/B test data, etc.
    
    # Relationships
    subscriber = relationship("Subscriber", back_populates="email_logs")
    sequence = relationship("Sequence", back_populates="email_logs")
    broadcast = relationship("Broadcast", back_populates="email_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_email_log_subscriber', 'subscriber_id'),
        Index('idx_email_log_type', 'email_type'),
        Index('idx_email_log_status', 'status'),
        Index('idx_email_log_queued_at', 'queued_at'),
        Index('idx_email_log_sent_at', 'sent_at'),
        Index('idx_email_log_brevo_id', 'brevo_message_id'),
        Index('idx_email_log_sequence', 'sequence_id'),
        Index('idx_email_log_broadcast', 'broadcast_id'),
    )
    
    def __repr__(self) -> str:
        return f"<EmailLog(id={self.id}, type={self.email_type}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "subscriber_id": str(self.subscriber_id),
            "sequence_id": str(self.sequence_id) if self.sequence_id else None,
            "broadcast_id": str(self.broadcast_id) if self.broadcast_id else None,
            "email_type": self.email_type,
            "subject": self.subject,
            "preview_text": self.preview_text,
            "template_name": self.template_name,
            "template_version": self.template_version,
            "brevo_message_id": self.brevo_message_id,
            "status": self.status,
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "bounced_at": self.bounced_at.isoformat() if self.bounced_at else None,
            "complained_at": self.complained_at.isoformat() if self.complained_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "delivery_provider": self.delivery_provider,
            "delivery_attempts": self.delivery_attempts,
            "last_delivery_attempt": self.last_delivery_attempt.isoformat() if self.last_delivery_attempt else None,
            "bounce_type": self.bounce_type,
            "bounce_reason": self.bounce_reason,
            "complaint_type": self.complaint_type,
            "click_urls": self.click_urls,
            "click_user_agent": self.click_user_agent,
            "click_ip_address": self.click_ip_address,
            "open_user_agent": self.open_user_agent,
            "open_ip_address": self.open_ip_address,
            "open_location": self.open_location,
            "metadata": self.metadata,
            "campaign_data": self.campaign_data
        }
    
    @property
    def is_delivered(self) -> bool:
        """Check if email was delivered."""
        return self.status in [EmailStatus.DELIVERED, EmailStatus.OPENED, EmailStatus.CLICKED]
    
    @property
    def is_opened(self) -> bool:
        """Check if email was opened."""
        return self.status in [EmailStatus.OPENED, EmailStatus.CLICKED]
    
    @property
    def is_clicked(self) -> bool:
        """Check if email was clicked."""
        return self.status == EmailStatus.CLICKED
    
    @property
    def is_bounced(self) -> bool:
        """Check if email bounced."""
        return self.status == EmailStatus.BOUNCED
    
    @property
    def is_failed(self) -> bool:
        """Check if email failed to deliver."""
        return self.status in [EmailStatus.FAILED, EmailStatus.BOUNCED, EmailStatus.COMPLAINED]
    
    @property
    def delivery_time_seconds(self) -> int:
        """Calculate delivery time in seconds."""
        if self.sent_at and self.delivered_at:
            return int((self.delivered_at - self.sent_at).total_seconds())
        return 0
    
    @property
    def engagement_time_seconds(self) -> int:
        """Calculate time to first engagement (open or click)."""
        if self.delivered_at and self.opened_at:
            return int((self.opened_at - self.delivered_at).total_seconds())
        elif self.delivered_at and self.clicked_at:
            return int((self.clicked_at - self.delivered_at).total_seconds())
        return 0
    
    def mark_as_sent(self, brevo_message_id: str) -> None:
        """Mark email as sent."""
        self.status = EmailStatus.SENT
        self.brevo_message_id = brevo_message_id
        self.sent_at = datetime.now(timezone.utc)
        self.delivery_attempts += 1
        self.last_delivery_attempt = self.sent_at
    
    def mark_as_delivered(self) -> None:
        """Mark email as delivered."""
        if self.status != EmailStatus.SENT:
            return
        
        self.status = EmailStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)
    
    def mark_as_opened(self, user_agent: str = None, ip_address: str = None, location: dict = None) -> None:
        """Mark email as opened."""
        if self.status not in [EmailStatus.DELIVERED, EmailStatus.OPENED]:
            return
        
        if self.status == EmailStatus.DELIVERED:
            self.opened_at = datetime.now(timezone.utc)
            self.status = EmailStatus.OPENED
        
        self.open_count += 1
        if user_agent:
            self.open_user_agent = user_agent
        if ip_address:
            self.open_ip_address = ip_address
        if location:
            self.open_location = location
    
    def mark_as_clicked(self, url: str, user_agent: str = None, ip_address: str = None) -> None:
        """Mark email as clicked."""
        if self.status not in [EmailStatus.OPENED, EmailStatus.CLICKED]:
            return
        
        self.status = EmailStatus.CLICKED
        if not self.clicked_at:
            self.clicked_at = datetime.now(timezone.utc)
        
        self.click_count += 1
        
        # Track clicked URLs
        if not self.click_urls:
            self.click_urls = []
        if url not in self.click_urls:
            self.click_urls.append(url)
        
        if user_agent:
            self.click_user_agent = user_agent
        if ip_address:
            self.click_ip_address = ip_address
    
    def mark_as_bounced(self, bounce_type: str, bounce_reason: str = None) -> None:
        """Mark email as bounced."""
        self.status = EmailStatus.BOUNCED
        self.bounced_at = datetime.now(timezone.utc)
        self.bounce_type = bounce_type
        if bounce_reason:
            self.bounce_reason = bounce_reason
    
    def mark_as_complained(self, complaint_type: str = None) -> None:
        """Mark email as complained."""
        self.status = EmailStatus.COMPLAINED
        self.complained_at = datetime.now(timezone.utc)
        if complaint_type:
            self.complaint_type = complaint_type
    
    def mark_as_failed(self, error_message: str = None) -> None:
        """Mark email as failed."""
        self.status = EmailStatus.FAILED
        self.failed_at = datetime.now(timezone.utc)
        self.delivery_attempts += 1
        self.last_delivery_attempt = self.failed_at
        
        if error_message:
            self.metadata = self.metadata or {}
            self.metadata["failure_reason"] = error_message
    
    def retry_delivery(self) -> None:
        """Prepare email for retry delivery."""
        self.status = EmailStatus.QUEUED
        self.delivery_attempts += 1
        self.last_delivery_attempt = datetime.now(timezone.utc)
        
        # Reset timestamps
        self.sent_at = None
        self.delivered_at = None
        self.opened_at = None
        self.clicked_at = None
        self.bounced_at = None
        self.complained_at = None
        self.failed_at = None
    
    def add_campaign_data(self, key: str, value: any) -> None:
        """Add campaign data for A/B testing or analytics."""
        if not self.campaign_data:
            self.campaign_data = {}
        self.campaign_data[key] = value
    
    def get_brevo_webhook_data(self) -> dict:
        """Get webhook data for Brevo integration."""
        return {
            "messageId": self.brevo_message_id,
            "to": self.subscriber.email if self.subscriber else None,
            "subject": self.subject,
            "event": self.status,
            "timestamp": self.get_latest_timestamp(),
            "reason": self.bounce_reason or self.complaint_type,
            "details": {
                "email_type": self.email_type,
                "template": self.template_name,
                "attempts": self.delivery_attempts
            }
        }
    
    def get_latest_timestamp(self) -> str:
        """Get the latest timestamp as ISO string."""
        timestamps = [
            self.queued_at, self.sent_at, self.delivered_at,
            self.opened_at, self.clicked_at, self.bounced_at,
            self.complained_at, self.failed_at
        ]
        
        # Filter out None values and get the latest
        valid_timestamps = [ts for ts in timestamps if ts is not None]
        if valid_timestamps:
            return max(valid_timestamps).isoformat()
        
        return self.queued_at.isoformat() if self.queued_at else None
    
    def get_engagement_summary(self) -> dict:
        """Get engagement summary for analytics."""
        return {
            "delivered": self.is_delivered,
            "opened": self.is_opened,
            "clicked": self.is_clicked,
            "bounced": self.is_bounced,
            "failed": self.is_failed,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "delivery_time_seconds": self.delivery_time_seconds,
            "engagement_time_seconds": self.engagement_time_seconds,
            "unique_clicks": len(self.click_urls or []),
            "delivery_attempts": self.delivery_attempts
        }


class EmailCampaign(Base):
    """
    Email campaign model for A/B testing and analytics.
    
    Groups related emails for campaign-level analytics.
    """
    __tablename__ = "email_core_campaigns"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Campaign information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    campaign_type = Column(String(20), nullable=False)  # ab_test, multivariate, standard
    
    # Test configuration
    test_variables = Column(JSON, default=dict)  # Variables being tested
    test_groups = Column(JSON, default=list)  # Test group configurations
    
    # Targeting
    segment_filters = Column(JSON, default=dict)
    sample_size = Column(Integer)
    
    # Status and timing
    status = Column(String(20), default="draft")  # draft, running, completed, cancelled
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    
    # Results
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    
    # Statistical significance
    confidence_level = Column(Float, default=0.95)
    statistical_significance = Column(Boolean, default=False)
    winning_variant = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_campaign_type', 'campaign_type'),
        Index('idx_campaign_status', 'status'),
        Index('idx_campaign_start_time', 'start_time'),
        Index('idx_campaign_created_at', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<EmailCampaign(id={self.id}, name={self.name}, type={self.campaign_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "campaign_type": self.campaign_type,
            "test_variables": self.test_variables,
            "test_groups": self.test_groups,
            "segment_filters": self.segment_filters,
            "sample_size": self.sample_size,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_sent": self.total_sent,
            "total_delivered": self.total_delivered,
            "total_opened": self.total_opened,
            "total_clicked": self.total_clicked,
            "confidence_level": self.confidence_level,
            "statistical_significance": self.statistical_significance,
            "winning_variant": self.winning_variant,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def delivery_rate(self) -> float:
        """Calculate delivery rate."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_delivered / self.total_sent) * 100
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate."""
        if self.total_delivered == 0:
            return 0.0
        return (self.total_opened / self.total_delivered) * 100
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate."""
        if self.total_opened == 0:
            return 0.0
        return (self.total_clicked / self.total_opened) * 100
    
    def increment_sent(self, count: int = 1) -> None:
        """Increment sent count."""
        self.total_sent += count
    
    def increment_delivered(self, count: int = 1) -> None:
        """Increment delivered count."""
        self.total_delivered += count
    
    def increment_opened(self, count: int = 1) -> None:
        """Increment opened count."""
        self.total_opened += count
    
    def increment_clicked(self, count: int = 1) -> None:
        """Increment clicked count."""
        self.total_clicked += count
    
    def calculate_results(self, group_results: dict) -> None:
        """Calculate campaign results and determine winner."""
        if not group_results or len(group_results) < 2:
            return
        
        # Simple winner calculation based on conversion rate
        best_group = None
        best_rate = 0.0
        
        for group_id, results in group_results.items():
            if results.get("delivered", 0) > 0:
                rate = results.get("clicked", 0) / results.get("delivered", 1)
                if rate > best_rate:
                    best_rate = rate
                    best_group = group_id
        
        if best_group:
            self.winning_variant = {
                "group_id": best_group,
                "conversion_rate": best_rate,
                "results": group_results[best_group]
            }
            self.statistical_significance = True
