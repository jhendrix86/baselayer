"""
EMAIL_CORE Brevo Client Tests

Unit tests for Brevo API client functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from ..brevo_client import BrevoClient, BrevoEmail, get_brevo_client
from ..brevo_client import BrevoAPIError, BrevoRateLimitError, BrevoDailyLimitError


@pytest.mark.unit
class TestBrevoClient:
    """Test Brevo client functionality."""
    
    def test_brevo_client_initialization(self):
        """Test Brevo client initialization."""
        client = BrevoClient(api_key="test_key")
        
        assert client.api_key == "test_key"
        assert client.base_url == "https://api.brevo.com/v3"
        assert client.daily_limit == 300
        assert client.session is not None
    
    def test_brevo_client_with_custom_limit(self):
        """Test Brevo client with custom daily limit."""
        client = BrevoClient(api_key="test_key", daily_limit=500)
        
        assert client.daily_limit == 500
    
    def test_get_brevo_client_singleton(self):
        """Test Brevo client singleton pattern."""
        client1 = get_brevo_client()
        client2 = get_brevo_client()
        
        # Should return the same instance (with proper implementation)
        # This test would need the actual singleton implementation
    
    @pytest.mark.asyncio
    async def test_send_transactional_email_success(self, mock_brevo_client, mock_redis_client):
        """Test successful transactional email sending."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = {
            "messageId": "test_msg_123"
        }
        client.session.post.return_value = mock_response
        
        email_data = BrevoEmail(
            sender={
                "name": "Test Sender",
                "email": "sender@example.com"
            },
            to=[{
                "name": "Test Recipient",
                "email": "recipient@example.com"
            }],
            subject="Test Subject",
            htmlContent="<html><body>Test content</body></html>",
            textContent="Test content"
        )
        
        result = await client.send_transactional_email(email_data, mock_redis_client)
        
        assert result["messageId"] == "test_msg_123"
        assert "status" in result or "messageId" in result
        client.session.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_transactional_email_rate_limit(self, mock_brevo_client, mock_redis_client):
        """Test rate limit handling."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock rate limit response
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "60"}
        client.session.post.return_value = mock_response
        
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        with pytest.raises(BrevoRateLimitError):
            await client.send_transactional_email(email_data, mock_redis_client)
    
    @pytest.mark.asyncio
    async def test_send_transactional_email_daily_limit(self, mock_brevo_client, mock_redis_client):
        """Test daily limit handling."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock daily limit exceeded
        mock_redis_client.get.return_value = "300"  # At limit
        
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        with pytest.raises(BrevoDailyLimitError):
            await client.send_transactional_email(email_data, mock_redis_client)
    
    @pytest.mark.asyncio
    async def test_create_contact_success(self, mock_brevo_client):
        """Test successful contact creation."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = {
            "id": "contact_123",
            "email": "test@example.com"
        }
        client.session.post.return_value = mock_response
        
        contact_data = {
            "email": "test@example.com",
            "attributes": {
                "FIRSTNAME": "Test",
                "LASTNAME": "User"
            }
        }
        
        result = await client.create_contact(contact_data)
        
        assert result["id"] == "contact_123"
        assert result["email"] == "test@example.com"
        client.session.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_contact_success(self, mock_brevo_client):
        """Test successful contact update."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "id": "contact_123",
            "email": "updated@example.com"
        }
        client.session.put.return_value = mock_response
        
        contact_id = "contact_123"
        contact_data = {
            "attributes": {
                "FIRSTNAME": "Updated"
            }
        }
        
        result = await client.update_contact(contact_id, contact_data)
        
        assert result["id"] == "contact_123"
        client.session.put.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_contact_success(self, mock_brevo_client):
        """Test successful contact deletion."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 204
        client.session.delete.return_value = mock_response
        
        contact_id = "contact_123"
        
        result = await client.delete_contact(contact_id)
        
        assert result["id"] == "contact_123"
        client.session.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_contacts_success(self, mock_brevo_client):
        """Test successful contacts retrieval."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "contacts": [
                {
                    "id": "contact_1",
                    "email": "test1@example.com"
                },
                {
                    "id": "contact_2", 
                    "email": "test2@example.com"
                }
            ],
            "count": 2
        }
        client.session.get.return_value = mock_response
        
        result = await client.get_contacts(limit=50, offset=0)
        
        assert len(result["contacts"]) == 2
        assert result["count"] == 2
        assert result["contacts"][0]["email"] == "test1@example.com"
        client.session.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_daily_limit(self, mock_redis_client):
        """Test daily limit checking."""
        client = BrevoClient(api_key="test_key", daily_limit=300)
        
        # Test no emails sent today
        mock_redis_client.get.return_value = None
        limit_info = await client.check_daily_limit()
        
        assert limit_info["sent_today"] == 0
        assert limit_info["remaining"] == 300
        assert limit_info["within_limit"] is True
        
        # Test some emails sent
        mock_redis_client.get.return_value = "150"
        limit_info = await client.check_daily_limit()
        
        assert limit_info["sent_today"] == 150
        assert limit_info["remaining"] == 150
        assert limit_info["within_limit"] is True
        
        # Test limit reached
        mock_redis_client.get.return_value = "300"
        limit_info = await client.check_daily_limit()
        
        assert limit_info["sent_today"] == 300
        assert limit_info["remaining"] == 0
        assert limit_info["within_limit"] is False
    
    @pytest.mark.asyncio
    async def test_increment_daily_counter(self, mock_redis_client):
        """Test daily counter increment."""
        client = BrevoClient(api_key="test_key")
        
        await client.increment_daily_counter()
        
        mock_redis_client.incr.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_parse_webhook(self, mock_brevo_client):
        """Test webhook parsing."""
        client = BrevoClient(api_key="test_key")
        
        webhook_data = {
            "event": "delivered",
            "messageId": "msg_123",
            "to": "recipient@example.com",
            "subject": "Test Subject",
            "timestamp": "2023-05-02T10:00:00Z",
            "details": {
                "ip_address": "192.168.1.1",
                "user_agent": "Test Agent"
            }
        }
        
        webhook = client.parse_webhook(webhook_data)
        
        assert webhook.event == "delivered"
        assert webhook.messageId == "msg_123"
        assert webhook.to == "recipient@example.com"
        assert webhook.subject == "Test Subject"
        assert webhook.details["ip_address"] == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, mock_brevo_client):
        """Test retry mechanism with exponential backoff."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock rate limit responses then success
        responses = [
            AsyncMock(status=429, headers={"Retry-After": "1"}),
            AsyncMock(status=429, headers={"Retry-After": "2"}),
            AsyncMock(status=201, json=lambda: {"messageId": "success"})
        ]
        client.session.post.return_value = responses[0]
        
        # This would test the retry logic
        # Implementation would need actual retry mechanism
        pass
    
    @pytest.mark.asyncio
    async def test_batch_send_emails(self, mock_brevo_client, mock_redis_client):
        """Test batch email sending."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful responses
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = {"messageId": "batch_msg"}
        client.session.post.return_value = mock_response
        
        emails = [
            BrevoEmail(
                sender={"name": "Test", "email": "test@example.com"},
                to=[{"name": f"Recipient {i}", "email": f"recipient{i}@example.com"}],
                subject=f"Subject {i}",
                htmlContent=f"<html><body>Content {i}</body></html>"
            )
            for i in range(3)
        ]
        
        results = await client.batch_send_emails(emails, mock_redis_client)
        
        assert len(results) == 3
        assert all("messageId" in result for result in results)


@pytest.mark.unit
class TestBrevoEmail:
    """Test Brevo email data model."""
    
    def test_brevo_email_creation(self):
        """Test Brevo email creation."""
        email = BrevoEmail(
            sender={
                "name": "Test Sender",
                "email": "sender@example.com"
            },
            to=[{
                "name": "Test Recipient",
                "email": "recipient@example.com"
            }],
            subject="Test Subject",
            htmlContent="<html><body>Test</body></html>",
            textContent="Test"
        )
        
        assert email.sender["name"] == "Test Sender"
        assert email.sender["email"] == "sender@example.com"
        assert email.to[0]["name"] == "Test Recipient"
        assert email.to[0]["email"] == "recipient@example.com"
        assert email.subject == "Test Subject"
        assert email.htmlContent == "<html><body>Test</body></html>"
        assert email.textContent == "Test"
    
    def test_brevo_email_validation(self):
        """Test Brevo email validation."""
        # Valid email
        valid_email = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        # This would test validation logic
        # Implementation would need actual validation methods
        assert valid_email.sender is not None
        assert valid_email.to is not None
        assert valid_email.subject is not None


@pytest.mark.integration
class TestBrevoClientIntegration:
    """Test Brevo client integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_email_workflow(self, mock_brevo_client, mock_redis_client):
        """Test complete email sending workflow."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock successful responses
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = {"messageId": "workflow_msg"}
        client.session.post.return_value = mock_response
        
        # Check daily limit
        limit_info = await client.check_daily_limit()
        assert limit_info["within_limit"] is True
        
        # Send email
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Integration Test",
            htmlContent="<html><body>Integration test content</body></html>"
        )
        
        result = await client.send_transactional_email(email_data, mock_redis_client)
        
        assert "messageId" in result
        
        # Verify counter was incremented
        mock_redis_client.incr.assert_called()
    
    @pytest.mark.asyncio
    async def test_contact_sync_workflow(self, mock_brevo_client):
        """Test contact synchronization workflow."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock API responses
        mock_get_response = AsyncMock()
        mock_get_response.status = 200
        mock_get_response.json.return_value = {
            "contacts": [],
            "count": 0
        }
        
        mock_post_response = AsyncMock()
        mock_post_response.status = 201
        mock_post_response.json.return_value = {
            "id": "sync_contact_123",
            "email": "sync@example.com"
        }
        
        client.session.get.return_value = mock_get_response
        client.session.post.return_value = mock_post_response
        
        # Check if contact exists
        existing = await client.get_contacts(limit=1)
        assert existing["count"] == 0
        
        # Create new contact
        contact_data = {
            "email": "sync@example.com",
            "attributes": {
                "FIRSTNAME": "Sync",
                "LASTNAME": "User"
            }
        }
        
        result = await client.create_contact(contact_data)
        
        assert result["id"] == "sync_contact_123"
        assert result["email"] == "sync@example.com"


@pytest.mark.unit
class TestBrevoClientErrors:
    """Test Brevo client error handling."""
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_brevo_client):
        """Test API error handling."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock API error response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json.return_value = {
            "code": "invalid_parameter",
            "message": "Invalid parameter"
        }
        client.session.post.return_value = mock_response
        
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        with pytest.raises(BrevoAPIError):
            await client.send_transactional_email(email_data)
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, mock_brevo_client):
        """Test authentication error handling."""
        client = BrevoClient(api_key="invalid_key")
        client.session = AsyncMock()
        
        # Mock authentication error
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.json.return_value = {
            "code": "invalid_api_key",
            "message": "Invalid API key"
        }
        client.session.post.return_value = mock_response
        
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        with pytest.raises(BrevoAPIError):
            await client.send_transactional_email(email_data)
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, mock_brevo_client):
        """Test network error handling."""
        client = BrevoClient(api_key="test_key")
        client.session = AsyncMock()
        
        # Mock network error
        import aiohttp
        client.session.post.side_effect = aiohttp.ClientError("Network error")
        
        email_data = BrevoEmail(
            sender={"name": "Test", "email": "test@example.com"},
            to=[{"name": "Recipient", "email": "recipient@example.com"}],
            subject="Test",
            htmlContent="<html><body>Test</body></html>"
        )
        
        with pytest.raises(BrevoAPIError):
            await client.send_transactional_email(email_data)
