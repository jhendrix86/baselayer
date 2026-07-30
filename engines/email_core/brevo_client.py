"""
EMAIL_CORE Brevo Client

Async Brevo API v3 client with rate limiting, error handling,
and 300/day free tier management.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class BrevoContact(BaseModel):
    """Brevo contact data model."""
    id: Optional[str] = None
    email: str
    attributes: Dict[str, Any] = {}
    listIds: List[int] = []
    updateEnabled: bool = True
    smtpBlacklistSender: List[str] = []


class BrevoEmail(BaseModel):
    """Brevo email data model."""
    sender: Dict[str, str]
    to: List[Dict[str, str]]
    subject: str
    htmlContent: Optional[str] = None
    textContent: Optional[str] = None
    replyTo: Optional[Dict[str, str]] = None
    attachment: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None


class BrevoCampaign(BaseModel):
    """Brevo campaign data model."""
    name: str
    subject: str
    htmlContent: str
    sender: Dict[str, str]
    replyTo: Optional[Dict[str, str]] = None
    toFilter: Optional[Dict[str, Any]] = None
    attachmentUrl: Optional[str] = None
    inlineImage: Optional[List[Dict[str, Any]]] = None
    recipients: Optional[Dict[str, Any]] = None
    scheduledAt: Optional[str] = None


class BrevoWebhook(BaseModel):
    """Brevo webhook data model."""
    event: str
    messageId: str
    to: str
    subject: str
    timestamp: str
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class BrevoClient:
    """
    Async Brevo API client with rate limiting and caching.
    
    Provides comprehensive Brevo API integration with
    automatic retry, error handling, and daily limit management.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.brevo.com/v3",
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        daily_limit: int = 300
    ) -> None:
        """Initialize Brevo client."""
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.daily_limit = daily_limit
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "api-key": self.api_key,
                "content-type": "application/json",
                "accept": "application/json"
            }
        )
        
        logger.info("BrevoClient initialized", base_url=self.base_url, daily_limit=self.daily_limit)
    
    async def __aenter__(self) -> 'BrevoClient':
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 0
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = urljoin(self.base_url, endpoint)
        
        try:
            if method.upper() == "GET":
                response = await self._client.get(url, params=params)
            elif method.upper() == "POST":
                response = await self._client.post(url, json=data)
            elif method.upper() == "PUT":
                response = await self._client.put(url, json=data)
            elif method.upper() == "DELETE":
                response = await self._client.delete(url)
            else:
                raise BaseLayerError(f"Unsupported HTTP method: {method}")
            
            # Check for rate limiting
            if response.status_code == 429:
                if retries < self.max_retries:
                    wait_time = self.backoff_factor * (2 ** retries)
                    logger.warning("Rate limited, retrying", wait_time=wait_time, retry=retries + 1)
                    await asyncio.sleep(wait_time)
                    return await self._make_request(method, endpoint, data, params, retries + 1)
                else:
                    raise BaseLayerError("Rate limit exceeded after maximum retries")
            
            # Handle response
            if response.status_code >= 400:
                error_data = response.text
                try:
                    error_json = response.json()
                    error_data = error_json.get("message", error_data)
                except:
                    pass
                
                raise BaseLayerError(f"Brevo API error ({response.status_code}): {error_data}")
            
            return response.json()
            
        except httpx.HTTPError as e:
            if retries < self.max_retries:
                wait_time = self.backoff_factor * (2 ** retries)
                logger.warning("HTTP error, retrying", error=str(e), wait_time=wait_time, retry=retries + 1)
                await asyncio.sleep(wait_time)
                return await self._make_request(method, endpoint, data, params, retries + 1)
            else:
                raise BaseLayerError(f"HTTP error after retries: {e}")
    
    async def check_daily_limit(self, redis_client=None) -> Dict[str, Any]:
        """Check daily email limit using Redis counter."""
        if not redis_client:
            # If no Redis client, assume we're within limit
            return {"sent_today": 0, "remaining": self.daily_limit, "within_limit": True}
        
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key = f"brevo:daily_limit:{today}"
            
            # Get current count
            sent_today = await redis_client.get(key)
            sent_today = int(sent_today) if sent_today else 0
            
            remaining = max(0, self.daily_limit - sent_today)
            within_limit = sent_today < self.daily_limit
            
            return {
                "sent_today": sent_today,
                "remaining": remaining,
                "within_limit": within_limit,
                "reset_time": (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to check daily limit", error=str(e))
            # Assume within limit on error
            return {"sent_today": 0, "remaining": self.daily_limit, "within_limit": True}
    
    async def increment_daily_limit(self, redis_client=None, count: int = 1) -> bool:
        """Increment daily email limit counter."""
        if not redis_client:
            return True
        
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key = f"brevo:daily_limit:{today}"
            
            # Increment counter with expiry
            await redis_client.incr(key, count)
            await redis_client.expire(key, 86400)  # 24 hours
            
            return True
            
        except Exception as e:
            logger.error("Failed to increment daily limit", error=str(e))
            return False
    
    # Contact Management
    
    async def create_contact(self, contact: BrevoContact) -> Dict[str, Any]:
        """Create a new contact."""
        try:
            data = contact.dict(exclude_unset=True)
            result = await self._make_request("POST", "/contacts", data)
            
            logger.info("Contact created", email=contact.email, contact_id=result.get("id"))
            return result
            
        except Exception as e:
            logger.error("Failed to create contact", email=contact.email, error=str(e))
            raise BaseLayerError(f"Failed to create contact: {e}")
    
    async def get_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """Get contact by email."""
        try:
            result = await self._make_request("GET", f"/contacts/{email}")
            return result
            
        except BaseLayerError as e:
            if "404" in str(e):
                return None
            raise
        except Exception as e:
            logger.error("Failed to get contact", email=email, error=str(e))
            raise BaseLayerError(f"Failed to get contact: {e}")
    
    async def update_contact(self, email: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Update contact attributes."""
        try:
            data = {"attributes": attributes}
            result = await self._make_request("PUT", f"/contacts/{email}", data)
            
            logger.info("Contact updated", email=email)
            return result
            
        except Exception as e:
            logger.error("Failed to update contact", email=email, error=str(e))
            raise BaseLayerError(f"Failed to update contact: {e}")
    
    async def delete_contact(self, email: str) -> Dict[str, Any]:
        """Delete contact."""
        try:
            result = await self._make_request("DELETE", f"/contacts/{email}")
            
            logger.info("Contact deleted", email=email)
            return result
            
        except Exception as e:
            logger.error("Failed to delete contact", email=email, error=str(e))
            raise BaseLayerError(f"Failed to delete contact: {e}")
    
    async def add_contact_to_list(self, email: str, list_id: int) -> Dict[str, Any]:
        """Add contact to list."""
        try:
            data = {"emails": [email]}
            result = await self._make_request("POST", f"/contacts/lists/{list_id}/contacts/add", data)
            
            logger.info("Contact added to list", email=email, list_id=list_id)
            return result
            
        except Exception as e:
            logger.error("Failed to add contact to list", email=email, list_id=list_id, error=str(e))
            raise BaseLayerError(f"Failed to add contact to list: {e}")
    
    async def remove_contact_from_list(self, email: str, list_id: int) -> Dict[str, Any]:
        """Remove contact from list."""
        try:
            data = {"emails": [email]}
            result = await self._make_request("POST", f"/contacts/lists/{list_id}/contacts/remove", data)
            
            logger.info("Contact removed from list", email=email, list_id=list_id)
            return result
            
        except Exception as e:
            logger.error("Failed to remove contact from list", email=email, list_id=list_id, error=str(e))
            raise BaseLayerError(f"Failed to remove contact from list: {e}")
    
    # Email Sending
    
    async def send_transactional_email(self, email: BrevoEmail, redis_client=None) -> Dict[str, Any]:
        """Send transactional email with daily limit check."""
        # Check daily limit
        limit_info = await self.check_daily_limit(redis_client)
        if not limit_info["within_limit"]:
            raise BaseLayerError(f"Daily limit exceeded. Sent: {limit_info['sent_today']}, Limit: {self.daily_limit}")
        
        try:
            data = email.dict(exclude_unset=True)
            result = await self._make_request("POST", "/smtp/email", data)
            
            # Increment daily limit counter
            await self.increment_daily_limit(redis_client)
            
            logger.info("Transactional email sent", message_id=result.get("messageId"), to=email.to[0]["email"])
            return result
            
        except Exception as e:
            logger.error("Failed to send transactional email", to=email.to[0]["email"], error=str(e))
            raise BaseLayerError(f"Failed to send transactional email: {e}")
    
    async def send_email_batch(
        self,
        emails: List[BrevoEmail],
        redis_client=None,
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Send emails in batches with rate limiting."""
        results = []
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            # Check daily limit before each batch
            limit_info = await self.check_daily_limit(redis_client)
            if not limit_info["within_limit"]:
                logger.warning("Daily limit reached, stopping batch", sent=len(results), total=len(emails))
                break
            
            # Send batch
            batch_results = []
            for email in batch:
                try:
                    result = await self.send_transactional_email(email, redis_client)
                    batch_results.append(result)
                except Exception as e:
                    logger.error("Failed to send email in batch", to=email.to[0]["email"], error=str(e))
                    batch_results.append({"error": str(e)})
            
            results.extend(batch_results)
            
            # Rate limiting between batches
            if i + batch_size < len(emails):
                await asyncio.sleep(1)
        
        logger.info("Email batch sent", sent=len(results), total=len(emails))
        return results
    
    # Campaign Management
    
    async def create_campaign(self, campaign: BrevoCampaign) -> Dict[str, Any]:
        """Create email campaign."""
        try:
            data = campaign.dict(exclude_unset=True)
            result = await self._make_request("POST", "/emailCampaigns", data)
            
            logger.info("Campaign created", name=campaign.name, campaign_id=result.get("id"))
            return result
            
        except Exception as e:
            logger.error("Failed to create campaign", name=campaign.name, error=str(e))
            raise BaseLayerError(f"Failed to create campaign: {e}")
    
    async def send_campaign_now(self, campaign_id: int) -> Dict[str, Any]:
        """Send campaign immediately."""
        try:
            result = await self._make_request("POST", f"/emailCampaigns/{campaign_id}/sendNow")
            
            logger.info("Campaign sent", campaign_id=campaign_id)
            return result
            
        except Exception as e:
            logger.error("Failed to send campaign", campaign_id=campaign_id, error=str(e))
            raise BaseLayerError(f"Failed to send campaign: {e}")
    
    async def get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """Get campaign statistics."""
        try:
            result = await self._make_request("GET", f"/emailCampaigns/{campaign_id}/stats")
            return result
            
        except Exception as e:
            logger.error("Failed to get campaign stats", campaign_id=campaign_id, error=str(e))
            raise BaseLayerError(f"Failed to get campaign stats: {e}")
    
    async def get_transactional_stats(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get transactional email statistics."""
        try:
            params = {
                "startDate": start_date,
                "endDate": end_date
            }
            result = await self._make_request("GET", "/smtp/statistics", params=params)
            return result
            
        except Exception as e:
            logger.error("Failed to get transactional stats", start_date=start_date, end_date=end_date, error=str(e))
            raise BaseLayerError(f"Failed to get transactional stats: {e}")
    
    # Webhook Handling
    
    def parse_webhook(self, webhook_data: Dict[str, Any]) -> BrevoWebhook:
        """Parse webhook data."""
        try:
            return BrevoWebhook(**webhook_data)
        except Exception as e:
            logger.error("Failed to parse webhook", data=webhook_data, error=str(e))
            raise BaseLayerError(f"Failed to parse webhook: {e}")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        try:
            result = await self._make_request("GET", "/account")
            return result
            
        except Exception as e:
            logger.error("Failed to get account info", error=str(e))
            raise BaseLayerError(f"Failed to get account info: {e}")
    
    async def get_lists(self) -> List[Dict[str, Any]]:
        """Get all contact lists."""
        try:
            result = await self._make_request("GET", "/contacts/lists")
            return result.get("lists", [])
            
        except Exception as e:
            logger.error("Failed to get lists", error=str(e))
            raise BaseLayerError(f"Failed to get lists: {e}")
    
    async def create_list(self, name: str, folder_id: Optional[int] = None) -> Dict[str, Any]:
        """Create contact list."""
        try:
            data = {"name": name}
            if folder_id:
                data["folderId"] = folder_id
            
            result = await self._make_request("POST", "/contacts/lists", data)
            
            logger.info("List created", name=name, list_id=result.get("id"))
            return result
            
        except Exception as e:
            logger.error("Failed to create list", name=name, error=str(e))
            raise BaseLayerError(f"Failed to create list: {e}")


# Global Brevo client instance
brevo_client = None


def get_brevo_client() -> BrevoClient:
    """Get global Brevo client instance."""
    global brevo_client
    
    if brevo_client is None:
        import os
        api_key = os.getenv("BREVO_API_KEY")
        if not api_key:
            raise BaseLayerError("BREVO_API_KEY environment variable not set")
        
        brevo_client = BrevoClient(api_key=api_key)
    
    return brevo_client
