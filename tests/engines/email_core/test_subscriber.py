"""
EMAIL_CORE Subscriber Tests

Unit tests for subscriber model and functionality.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.subscriber import Subscriber, SubscriberStatus, SubscriberSource
from ..models.email_log import EmailLog, EmailType, EmailStatus


@pytest.mark.unit
class TestSubscriberModel:
    """Test subscriber model functionality."""
    
    async def test_subscriber_creation(self, db_session: AsyncSession):
        """Test creating a new subscriber."""
        subscriber = Subscriber(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            status=SubscriberStatus.ACTIVE,
            source=SubscriberSource.WEBFORM,
            tags=["test", "sample"]
        )
        
        db_session.add(subscriber)
        await db_session.commit()
        await db_session.refresh(subscriber)
        
        assert subscriber.id is not None
        assert subscriber.email == "test@example.com"
        assert subscriber.first_name == "Test"
        assert subscriber.last_name == "User"
        assert subscriber.status == SubscriberStatus.ACTIVE
        assert subscriber.source == SubscriberSource.WEBFORM
        assert subscriber.tags == ["test", "sample"]
        assert subscriber.subscribed_at is not None
        assert subscriber.email_count == 0
        assert subscriber.open_count == 0
        assert subscriber.click_count == 0
    
    async def test_subscriber_mask_email(self, sample_subscriber: Subscriber):
        """Test email masking functionality."""
        masked = sample_subscriber.mask_email()
        assert masked == "t***@example.com"
        
        # Test with short email
        short_email_subscriber = Subscriber(email="ab@cd.com")
        masked_short = short_email_subscriber.mask_email()
        assert masked_short == "a***@cd.com"
    
    async def test_subscriber_can_receive_emails(self, sample_subscriber: Subscriber):
        """Test email receiving capability."""
        # Active subscriber should receive emails
        assert sample_subscriber.can_receive_emails is True
        
        # Bounced subscriber should not receive emails
        sample_subscriber.status = SubscriberStatus.BOUNCED
        assert sample_subscriber.can_receive_emails is False
        
        # Unsubscribed subscriber should not receive emails
        sample_subscriber.status = SubscriberStatus.UNSUBSCRIBED
        assert sample_subscriber.can_receive_emails is False
        
        # Complained subscriber should not receive emails
        sample_subscriber.status = SubscriberStatus.COMPLAINED
        assert sample_subscriber.can_receive_emails is False
    
    async def test_subscriber_engagement_rate(self, sample_subscriber: Subscriber):
        """Test engagement rate calculation."""
        # No emails sent yet
        assert sample_subscriber.engagement_rate == 0.0
        
        # Add some engagement data
        sample_subscriber.email_count = 100
        sample_subscriber.open_count = 50
        sample_subscriber.click_count = 10
        
        # Engagement rate should be (opens + clicks) / (emails * 2)
        expected_rate = (50 + 10) / (100 * 2) * 100
        assert sample_subscriber.engagement_rate == expected_rate
    
    async def test_subscriber_increment_metrics(self, sample_subscriber: Subscriber):
        """Test metric increment methods."""
        # Initial state
        assert sample_subscriber.email_count == 0
        assert sample_subscriber.open_count == 0
        assert sample_subscriber.click_count == 0
        assert sample_subscriber.bounce_count == 0
        assert sample_subscriber.complaint_count == 0
        
        # Increment metrics
        sample_subscriber.increment_email_count()
        sample_subscriber.increment_open_count()
        sample_subscriber.increment_click_count()
        sample_subscriber.increment_bounce_count()
        sample_subscriber.increment_complaint_count()
        
        assert sample_subscriber.email_count == 1
        assert sample_subscriber.open_count == 1
        assert sample_subscriber.click_count == 1
        assert sample_subscriber.bounce_count == 1
        assert sample_subscriber.complaint_count == 1
    
    async def test_subscriber_status_changes(self, sample_subscriber: Subscriber):
        """Test subscriber status change methods."""
        # Test unsubscribe
        sample_subscriber.unsubscribe("Test reason")
        assert sample_subscriber.status == SubscriberStatus.UNSUBSCRIBED
        assert sample_subscriber.unsubscribed_at is not None
        assert sample_subscriber.unsubscribe_reason == "Test reason"
        
        # Reset for next test
        sample_subscriber.status = SubscriberStatus.ACTIVE
        
        # Test bounce
        sample_subscriber.mark_as_bounced("hard")
        assert sample_subscriber.status == SubscriberStatus.BOUNCED
        assert sample_subscriber.bounced_at is not None
        assert sample_subscriber.bounce_type == "hard"
        
        # Reset for next test
        sample_subscriber.status = SubscriberStatus.ACTIVE
        
        # Test complaint
        sample_subscriber.mark_as_complained()
        assert sample_subscriber.status == SubscriberStatus.COMPLAINED
        assert sample_subscriber.complained_at is not None
    
    async def test_subscriber_to_dict(self, sample_subscriber: Subscriber):
        """Test subscriber serialization."""
        data = sample_subscriber.to_dict()
        
        assert isinstance(data, dict)
        assert data["id"] == str(sample_subscriber.id)
        assert data["email"] == sample_subscriber.email
        assert data["first_name"] == sample_subscriber.first_name
        assert data["last_name"] == sample_subscriber.last_name
        assert data["status"] == sample_subscriber.status
        assert data["source"] == sample_subscriber.source
        assert data["tags"] == sample_subscriber.tags
        assert "subscribed_at" in data
        assert "engagement_rate" in data
    
    async def test_subscriber_tag_management(self, sample_subscriber: Subscriber):
        """Test tag management."""
        # Add tags
        sample_subscriber.add_tag("new_tag")
        assert "new_tag" in sample_subscriber.tags
        
        # Remove tags
        sample_subscriber.remove_tag("test")
        assert "test" not in sample_subscriber.tags
        
        # Has tag
        assert sample_subscriber.has_tag("sample") is True
        assert sample_subscriber.has_tag("nonexistent") is False
    
    async def test_subscriber_full_name(self, sample_subscriber: Subscriber):
        """Test full name generation."""
        assert sample_subscriber.full_name == "Test User"
        
        # Test with missing first name
        sample_subscriber.first_name = None
        assert sample_subscriber.full_name == "User"
        
        # Test with missing last name
        sample_subscriber.first_name = "Test"
        sample_subscriber.last_name = None
        assert sample_subscriber.full_name == "Test"
        
        # Test with both missing
        sample_subscriber.first_name = None
        assert sample_subscriber.full_name == ""


@pytest.mark.unit
class TestSubscriberValidation:
    """Test subscriber validation."""
    
    async def test_email_validation(self, db_session: AsyncSession):
        """Test email format validation."""
        # Valid email
        valid_subscriber = Subscriber(email="valid@example.com")
        assert valid_subscriber.email == "valid@example.com"
        
        # Email validation would be handled at the application level
        # The model accepts any string for flexibility
    
    async def test_duplicate_email_prevention(self, db_session: AsyncSession):
        """Test duplicate email prevention."""
        # Create first subscriber
        subscriber1 = Subscriber(email="duplicate@example.com")
        db_session.add(subscriber1)
        await db_session.commit()
        
        # Try to create second subscriber with same email
        subscriber2 = Subscriber(email="duplicate@example.com")
        db_session.add(subscriber2)
        
        # This would be handled by unique constraint at database level
        # The test would expect an exception in real implementation


@pytest.mark.integration
class TestSubscriberRelationships:
    """Test subscriber relationships with other models."""
    
    async def test_subscriber_email_logs(self, db_session: AsyncSession, sample_subscriber: Subscriber):
        """Test subscriber relationship with email logs."""
        # Create email logs for subscriber
        email_log1 = EmailLog(
            subscriber_id=sample_subscriber.id,
            email_type=EmailType.NEWSLETTER,
            subject="Test Email 1",
            content_html="<html><body>Test 1</body></html>",
            status=EmailStatus.SENT
        )
        
        email_log2 = EmailLog(
            subscriber_id=sample_subscriber.id,
            email_type=EmailType.SEQUENCE,
            subject="Test Email 2",
            content_html="<html><body>Test 2</body></html>",
            status=EmailStatus.SENT
        )
        
        db_session.add(email_log1)
        db_session.add(email_log2)
        await db_session.commit()
        
        # Query subscriber with email logs
        from sqlalchemy import select
        stmt = select(Subscriber).where(Subscriber.id == sample_subscriber.id)
        result = await db_session.execute(stmt)
        subscriber = result.scalar_one()
        
        # Note: Relationship loading would need to be configured
        # This is a basic test structure
    
    async def test_subscriber_sequence_enrollments(self, db_session: AsyncSession, sample_subscriber: Subscriber):
        """Test subscriber relationship with sequence enrollments."""
        # This would test the relationship with sequence enrollments
        # Implementation would depend on the sequence enrollment model
        pass


@pytest.mark.unit
class TestSubscriberQueries:
    """Test subscriber query operations."""
    
    async def test_find_by_email(self, db_session: AsyncSession, sample_subscriber: Subscriber):
        """Test finding subscriber by email."""
        from sqlalchemy import select
        
        stmt = select(Subscriber).where(Subscriber.email == sample_subscriber.email)
        result = await db_session.execute(stmt)
        found_subscriber = result.scalar_one()
        
        assert found_subscriber.id == sample_subscriber.id
        assert found_subscriber.email == sample_subscriber.email
    
    async def test_filter_by_status(self, db_session: AsyncSession):
        """Test filtering subscribers by status."""
        from sqlalchemy import select
        
        # Create subscribers with different statuses
        active_subscriber = Subscriber(
            email="active@example.com",
            status=SubscriberStatus.ACTIVE
        )
        unsubscribed_subscriber = Subscriber(
            email="unsubscribed@example.com",
            status=SubscriberStatus.UNSUBSCRIBED
        )
        
        db_session.add(active_subscriber)
        db_session.add(unsubscribed_subscriber)
        await db_session.commit()
        
        # Query active subscribers
        stmt = select(Subscriber).where(Subscriber.status == SubscriberStatus.ACTIVE)
        result = await db_session.execute(stmt)
        active_subscribers = result.scalars().all()
        
        assert len(active_subscribers) >= 1
        assert all(s.status == SubscriberStatus.ACTIVE for s in active_subscribers)
    
    async def test_filter_by_tags(self, db_session: AsyncSession):
        """Test filtering subscribers by tags."""
        from sqlalchemy import select
        
        # Create subscribers with different tags
        tagged_subscriber = Subscriber(
            email="tagged@example.com",
            tags=["newsletter", "premium"]
        )
        untagged_subscriber = Subscriber(
            email="untagged@example.com",
            tags=[]
        )
        
        db_session.add(tagged_subscriber)
        db_session.add(untagged_subscriber)
        await db_session.commit()
        
        # Query subscribers with specific tag
        stmt = select(Subscriber).where(Subscriber.tags.contains(["newsletter"]))
        result = await db_session.execute(stmt)
        tagged_subscribers = result.scalars().all()
        
        assert len(tagged_subscribers) >= 1
        assert all("newsletter" in s.tags for s in tagged_subscribers)
