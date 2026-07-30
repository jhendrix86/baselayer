"""
EMAIL_CORE Subscriber Models

SQLAlchemy models for email subscribers with Brevo synchronization.
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


class SubscriberStatus(str, Enum):
    """Subscriber lifecycle status."""
    ACTIVE = "active"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


class SubscriberSource(str, Enum):
    """Subscriber acquisition sources."""
    LANDING_PAGE = "landing_page"
    GUMROAD = "gumroad"
    MANUAL = "manual"
    API = "api"
    IMPORT = "import"


class Subscriber(Base):
    """
    Email subscriber model for EMAIL_CORE engine.
    
    Tracks subscriber information, preferences, and engagement
    with Brevo synchronization.
    """
    __tablename__ = "email_core_subscribers"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Contact information
    email = Column(String(255), nullable=False, unique=True, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    
    # Status and source
    status = Column(String(20), nullable=False, default=SubscriberStatus.ACTIVE, index=True)
    source = Column(String(20), nullable=False, default=SubscriberSource.LANDING_PAGE, index=True)
    
    # Segmentation
    tags = Column(JSON, default=list, index=True)  # GIN index in PostgreSQL
    lead_magnet_id = Column(UUID(as_uuid=True), ForeignKey('email_core_lead_magnets.id'))
    
    # Brevo integration
    brevo_contact_id = Column(String(100), unique=True)
    brevo_list_ids = Column(JSON, default=list)
    
    # Timestamps
    subscribed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    unsubscribed_at = Column(DateTime(timezone=True))
    last_emailed_at = Column(DateTime(timezone=True))
    
    # Engagement metrics
    email_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    bounce_count = Column(Integer, default=0)
    complaint_count = Column(Integer, default=0)
    
    # Preferences
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    preferred_format = Column(String(10), default="html")  # html, text
    
    # Metadata
    metadata = Column(JSON, default=dict)
    custom_attributes = Column(JSON, default=dict)
    
    # Relationships
    lead_magnet = relationship("LeadMagnet", back_populates="subscribers")
    email_logs = relationship("EmailLog", back_populates="subscriber", cascade="all, delete-orphan")
    sequence_enrollments = relationship("SequenceEnrollment", back_populates="subscriber", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_subscriber_status', 'status'),
        Index('idx_subscriber_source', 'source'),
        Index('idx_subscriber_subscribed_at', 'subscribed_at'),
        Index('idx_subscriber_last_emailed', 'last_emailed_at'),
        Index('idx_subscriber_tags', 'tags'),  # PostgreSQL GIN index
    )
    
    def __repr__(self) -> str:
        masked_email = self.mask_email(self.email)
        return f"<Subscriber(id={self.id}, email={masked_email}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary with masked email."""
        return {
            "id": str(self.id),
            "email": self.mask_email(self.email),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "status": self.status,
            "source": self.source,
            "tags": self.tags,
            "lead_magnet_id": str(self.lead_magnet_id) if self.lead_magnet_id else None,
            "brevo_contact_id": self.brevo_contact_id,
            "subscribed_at": self.subscribed_at.isoformat() if self.subscribed_at else None,
            "unsubscribed_at": self.unsubscribed_at.isoformat() if self.unsubscribed_at else None,
            "last_emailed_at": self.last_emailed_at.isoformat() if self.last_emailed_at else None,
            "email_count": self.email_count,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "bounce_count": self.bounce_count,
            "complaint_count": self.complaint_count,
            "timezone": self.timezone,
            "language": self.language,
            "preferred_format": self.preferred_format,
            "metadata": self.metadata,
            "custom_attributes": self.custom_attributes
        }
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email for privacy in logs."""
        if '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked = local[0] + '*' * (len(local) - 1)
        else:
            masked = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked}@{domain}"
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return ""
    
    @property
    def is_active(self) -> bool:
        """Check if subscriber is active."""
        return self.status == SubscriberStatus.ACTIVE
    
    @property
    def can_receive_emails(self) -> bool:
        """Check if subscriber can receive emails."""
        return self.status in [SubscriberStatus.ACTIVE]
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (opens + clicks / sent)."""
        if self.email_count == 0:
            return 0.0
        return ((self.open_count + self.click_count) / self.email_count) * 100
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate."""
        if self.email_count == 0:
            return 0.0
        return (self.open_count / self.email_count) * 100
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate."""
        if self.open_count == 0:
            return 0.0
        return (self.click_count / self.open_count) * 100
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the subscriber."""
        if not self.tags:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the subscriber."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag: str) -> bool:
        """Check if subscriber has a specific tag."""
        return tag in (self.tags or [])
    
    def has_any_tag(self, tags: list) -> bool:
        """Check if subscriber has any of the specified tags."""
        if not self.tags or not tags:
            return False
        return any(tag in self.tags for tag in tags)
    
    def has_all_tags(self, tags: list) -> bool:
        """Check if subscriber has all of the specified tags."""
        if not self.tags or not tags:
            return False
        return all(tag in self.tags for tag in tags)
    
    def increment_email_count(self) -> None:
        """Increment email count."""
        self.email_count += 1
        self.last_emailed_at = datetime.now(timezone.utc)
    
    def increment_open_count(self) -> None:
        """Increment open count."""
        self.open_count += 1
    
    def increment_click_count(self) -> None:
        """Increment click count."""
        self.click_count += 1
    
    def increment_bounce_count(self) -> None:
        """Increment bounce count."""
        self.bounce_count += 1
    
    def increment_complaint_count(self) -> None:
        """Increment complaint count."""
        self.complaint_count += 1
    
    def unsubscribe(self, reason: str = None) -> None:
        """Unsubscribe the subscriber."""
        self.status = SubscriberStatus.UNSUBSCRIBED
        self.unsubscribed_at = datetime.now(timezone.utc)
        if reason:
            self.metadata = self.metadata or {}
            self.metadata["unsubscribe_reason"] = reason
    
    def mark_as_bounced(self, bounce_type: str = None) -> None:
        """Mark subscriber as bounced."""
        self.status = SubscriberStatus.BOUNCED
        self.increment_bounce_count()
        if bounce_type:
            self.metadata = self.metadata or {}
            self.metadata["bounce_type"] = bounce_type
    
    def mark_as_complained(self) -> None:
        """Mark subscriber as complained."""
        self.status = SubscriberStatus.COMPLAINED
        self.increment_complaint_count()
    
    def reactivate(self) -> None:
        """Reactivate a bounced or unsubscribed subscriber."""
        if self.status in [SubscriberStatus.UNSUBSCRIBED, SubscriberStatus.BOUNCED]:
            self.status = SubscriberStatus.ACTIVE
            self.unsubscribed_at = None
            # Reset bounce count on reactivation
            if self.status == SubscriberStatus.BOUNCED:
                self.bounce_count = 0
    
    def get_brevo_attributes(self) -> dict:
        """Get subscriber attributes for Brevo API."""
        attributes = {
            "FIRSTNAME": self.first_name or "",
            "LASTNAME": self.last_name or "",
            "SOURCE": self.source,
            "SUBSCRIBED_AT": self.subscribed_at.isoformat() if self.subscribed_at else None,
            "EMAIL_COUNT": self.email_count,
            "OPEN_COUNT": self.open_count,
            "CLICK_COUNT": self.click_count,
            "TIMEZONE": self.timezone,
            "LANGUAGE": self.language,
            "PREFERRED_FORMAT": self.preferred_format
        }
        
        # Add tags as a comma-separated string
        if self.tags:
            attributes["TAGS"] = ",".join(self.tags)
        
        # Add custom attributes
        if self.custom_attributes:
            attributes.update(self.custom_attributes)
        
        return attributes
    
    def update_from_brevo_data(self, brevo_data: dict) -> None:
        """Update subscriber from Brevo API data."""
        if "id" in brevo_data:
            self.brevo_contact_id = brevo_data["id"]
        
        if "attributes" in brevo_data:
            attributes = brevo_data["attributes"]
            
            # Update basic attributes
            if "FIRSTNAME" in attributes:
                self.first_name = attributes["FIRSTNAME"]
            if "LASTNAME" in attributes:
                self.last_name = attributes["LASTNAME"]
            if "TIMEZONE" in attributes:
                self.timezone = attributes["TIMEZONE"]
            if "LANGUAGE" in attributes:
                self.language = attributes["LANGUAGE"]
            if "PREFERRED_FORMAT" in attributes:
                self.preferred_format = attributes["PREFERRED_FORMAT"]
            
            # Update tags
            if "TAGS" in attributes and isinstance(attributes["TAGS"], str):
                self.tags = [tag.strip() for tag in attributes["TAGS"].split(",") if tag.strip()]
        
        # Update list memberships
        if "listIds" in brevo_data:
            self.brevo_list_ids = brevo_data["listIds"]


class LeadMagnet(Base):
    """
    Lead magnet model for tracking subscriber acquisition sources.
    
    Represents downloadable content or offers used to acquire subscribers.
    """
    __tablename__ = "email_core_lead_magnets"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    slug = Column(String(200), nullable=False, unique=True)
    
    # File information
    file_path = Column(String(500))
    file_name = Column(String(255))
    file_type = Column(String(10))  # pdf, zip, etc.
    file_size_bytes = Column(Integer)
    
    # Delivery settings
    delivery_email_template = Column(String(100))
    auto_add_tags = Column(JSON, default=list)
    welcome_sequence_id = Column(UUID(as_uuid=True))
    
    # Tracking
    download_count = Column(Integer, default=0)
    subscriber_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    subscribers = relationship("Subscriber", back_populates="lead_magnet")
    
    # Indexes
    __table_args__ = (
        Index('idx_lead_magnet_slug', 'slug'),
        Index('idx_lead_magnet_active', 'is_active'),
        Index('idx_lead_magnet_created_at', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<LeadMagnet(id={self.id}, name={self.name}, slug={self.slug})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "slug": self.slug,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "delivery_email_template": self.delivery_email_template,
            "auto_add_tags": self.auto_add_tags,
            "welcome_sequence_id": str(self.welcome_sequence_id) if self.welcome_sequence_id else None,
            "download_count": self.download_count,
            "subscriber_count": self.subscriber_count,
            "conversion_rate": self.conversion_rate,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def increment_download_count(self) -> None:
        """Increment download count."""
        self.download_count += 1
    
    def increment_subscriber_count(self) -> None:
        """Increment subscriber count."""
        self.subscriber_count += 1
        self.calculate_conversion_rate()
    
    def calculate_conversion_rate(self) -> None:
        """Calculate conversion rate."""
        if self.download_count > 0:
            self.conversion_rate = (self.subscriber_count / self.download_count) * 100
        else:
            self.conversion_rate = 0.0
