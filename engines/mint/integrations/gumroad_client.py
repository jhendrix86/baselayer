"""
MINT Gumroad Integration

Async HTTP client for Gumroad API integration
with rate limiting, error handling, and caching.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class GumroadProduct(BaseModel):
    """Gumroad product data model."""
    id: str
    name: str
    description: Optional[str] = None
    price_cents: int
    url: Optional[str] = None
    visible: bool = True
    require_shipping: bool = False
    tags: List[str] = []
    max_purchase_count: Optional[int] = None
    support_email: Optional[str] = None
    published: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GumroadSale(BaseModel):
    """Gumroad sale data model."""
    id: str
    product_id: str
    email: str
    full_name: str
    price_cents: int
    fee_cents: int
    net_cents: int
    created_at: datetime
    refunded: bool = False
    refunded_at: Optional[datetime] = None


class GumroadAnalytics(BaseModel):
    """Gumroad analytics data model."""
    product_id: str
    views: int
    sales: int
    revenue_cents: int
    refunds: int
    conversion_rate: float
    date: datetime
    source: str = "gumroad"


class GumroadClient:
    """
    Async Gumroad API client with rate limiting and caching.
    
    Provides comprehensive Gumroad API integration with
    automatic retry, error handling, and response caching.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.gumroad.com/v2",
        timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 300  # 5 minutes
    ) -> None:
        """Initialize Gumroad client."""
        self.api_key: str = api_key
        self.base_url: str = base_url.rstrip('/')
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.cache_ttl: int = cache_ttl
        
        # HTTP client configuration
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "BaseLayer-MINT/1.0.0"
        }
        
        self.client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10
            )
        )
        
        # Rate limiting
        self.rate_limit: Dict[str, Any] = {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "current_minute_requests": 0,
            "current_hour_requests": 0,
            "minute_reset_time": datetime.now(timezone.utc),
            "hour_reset_time": datetime.now(timezone.utc)
        }
        
        # Response cache
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(
            "Gumroad client initialized",
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries
        )
    
    async def create_product(self, product_data: Dict[str, Any]) -> GumroadProduct:
        """
        Create a new product on Gumroad.
        
        Args:
            product_data: Product creation data
            
        Returns:
            Created GumroadProduct
        """
        try:
            # Check rate limits
            await self._check_rate_limit()
            
            # Make API request
            response = await self._make_request(
                "POST",
                "/products",
                json=product_data
            )
            
            # Parse response
            product_data = response.json()
            product = GumroadProduct(**product_data)
            
            logger.info(
                "Gumroad product created",
                product_id=product.id,
                name=product.name,
                price_cents=product.price_cents
            )
            
            return product
            
        except Exception as e:
            logger.error(
                "Failed to create Gumroad product",
                error=str(e),
                product_data=product_data
            )
            raise BaseLayerError(f"Product creation failed: {str(e)}") from e
    
    async def update_product(self, product_id: str, product_data: Dict[str, Any]) -> GumroadProduct:
        """
        Update an existing product on Gumroad.
        
        Args:
            product_id: Gumroad product ID
            product_data: Updated product data
            
        Returns:
            Updated GumroadProduct
        """
        try:
            # Check rate limits
            await self._check_rate_limit()
            
            # Make API request
            response = await self._make_request(
                "PUT",
                f"/products/{product_id}",
                json=product_data
            )
            
            # Parse response
            product_data = response.json()
            product = GumroadProduct(**product_data)
            
            logger.info(
                "Gumroad product updated",
                product_id=product_id,
                name=product.name,
                price_cents=product.price_cents
            )
            
            return product
            
        except Exception as e:
            logger.error(
                "Failed to update Gumroad product",
                product_id=product_id,
                error=str(e),
                product_data=product_data
            )
            raise BaseLayerError(f"Product update failed: {str(e)}") from e
    
    async def get_product(self, product_id: str) -> Optional[GumroadProduct]:
        """
        Get product details from Gumroad.
        
        Args:
            product_id: Gumroad product ID
            
        Returns:
            GumroadProduct or None if not found
        """
        try:
            # Check cache first
            cache_key = f"product:{product_id}"
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug(
                    "Product retrieved from cache",
                    product_id=product_id
                )
                return GumroadProduct(**cached)
            
            # Check rate limits
            await self._check_rate_limit()
            
            # Make API request
            response = await self._make_request(
                "GET",
                f"/products/{product_id}"
            )
            
            # Parse response
            product_data = response.json()
            product = GumroadProduct(**product_data)
            
            # Cache response
            self._set_cache(cache_key, product.dict())
            
            logger.debug(
                "Gumroad product retrieved",
                product_id=product_id,
                name=product.name
            )
            
            return product
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Gumroad product not found",
                    product_id=product_id
                )
                return None
            else:
                logger.error(
                    "Failed to get Gumroad product",
                    product_id=product_id,
                    error=str(e)
                )
                raise BaseLayerError(f"Product retrieval failed: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Failed to get Gumroad product",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Product retrieval failed: {str(e)}") from e
    
    async def delete_product(self, product_id: str) -> bool:
        """
        Delete a product from Gumroad.
        
        Args:
            product_id: Gumroad product ID
            
        Returns:
            True if deleted successfully
        """
        try:
            # Check rate limits
            await self._check_rate_limit()
            
            # Make API request
            response = await self._make_request(
                "DELETE",
                f"/products/{product_id}"
            )
            
            logger.info(
                "Gumroad product deleted",
                product_id=product_id
            )
            
            # Clear cache
            cache_key = f"product:{product_id}"
            self._clear_cache(cache_key)
            
            return True
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Gumroad product not found for deletion",
                    product_id=product_id
                )
                return False
            else:
                logger.error(
                    "Failed to delete Gumroad product",
                    product_id=product_id,
                    error=str(e)
                )
                raise BaseLayerError(f"Product deletion failed: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Failed to delete Gumroad product",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Product deletion failed: {str(e)}") from e
    
    async def list_products(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[GumroadProduct]:
        """
        List products from Gumroad.
        
        Args:
            limit: Maximum number of products to return
            offset: Number of products to skip
            search: Search query
            tags: Filter by tags
            
        Returns:
            List of GumroadProduct
        """
        try:
            # Check cache first
            cache_key = f"products:{limit}:{offset}:{search}:{tags}"
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug(
                    "Products retrieved from cache",
                    limit=limit,
                    offset=offset
                )
                return [GumroadProduct(**product) for product in cached]
            
            # Check rate limits
            await self._check_rate_limit()
            
            # Build query parameters
            params = {
                "limit": limit,
                "offset": offset
            }
            
            if search:
                params["search"] = search
            
            if tags:
                params["tags"] = ",".join(tags)
            
            # Make API request
            response = await self._make_request(
                "GET",
                "/products",
                params=params
            )
            
            # Parse response
            response_data = response.json()
            products_data = response_data.get("products", [])
            products = [GumroadProduct(**product) for product in products_data]
            
            # Cache response
            self._set_cache(cache_key, [product.dict() for product in products])
            
            logger.debug(
                "Gumroad products listed",
                count=len(products),
                limit=limit,
                offset=offset
            )
            
            return products
            
        except Exception as e:
            logger.error(
                "Failed to list Gumroad products",
                error=str(e),
                limit=limit,
                offset=offset
            )
            raise BaseLayerError(f"Product listing failed: {str(e)}") from e
    
    async def get_sales(
        self,
        product_id: str,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[GumroadSale]:
        """
        Get sales data for a product.
        
        Args:
            product_id: Gumroad product ID
            limit: Maximum number of sales to return
            offset: Number of sales to skip
            start_date: Filter sales from this date
            end_date: Filter sales to this date
            
        Returns:
            List of GumroadSale
        """
        try:
            # Check cache first
            cache_key = f"sales:{product_id}:{limit}:{offset}:{start_date}:{end_date}"
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug(
                    "Sales retrieved from cache",
                    product_id=product_id,
                    count=len(cached)
                )
                return [GumroadSale(**sale) for sale in cached]
            
            # Check rate limits
            await self._check_rate_limit()
            
            # Build query parameters
            params = {
                "limit": limit,
                "offset": offset
            }
            
            if start_date:
                params["start_date"] = start_date.isoformat()
            
            if end_date:
                params["end_date"] = end_date.isoformat()
            
            # Make API request
            response = await self._make_request(
                "GET",
                f"/products/{product_id}/sales",
                params=params
            )
            
            # Parse response
            response_data = response.json()
            sales_data = response_data.get("sales", [])
            sales = [GumroadSale(**sale) for sale in sales_data]
            
            # Cache response
            self._set_cache(cache_key, [sale.dict() for sale in sales])
            
            logger.debug(
                "Gumroad sales retrieved",
                product_id=product_id,
                count=len(sales)
            )
            
            return sales
            
        except Exception as e:
            logger.error(
                "Failed to get Gumroad sales",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Sales retrieval failed: {str(e)}") from e
    
    async def get_analytics(
        self,
        product_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[GumroadAnalytics]:
        """
        Get analytics data for a product.
        
        Args:
            product_id: Gumroad product ID
            start_date: Filter analytics from this date
            end_date: Filter analytics to this date
            
        Returns:
            List of GumroadAnalytics
        """
        try:
            # Check cache first
            cache_key = f"analytics:{product_id}:{start_date}:{end_date}"
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug(
                    "Analytics retrieved from cache",
                    product_id=product_id,
                    count=len(cached)
                )
                return [GumroadAnalytics(**analytics) for analytics in cached]
            
            # Check rate limits
            await self._check_rate_limit()
            
            # Build query parameters
            params = {}
            
            if start_date:
                params["start_date"] = start_date.isoformat()
            
            if end_date:
                params["end_date"] = end_date.isoformat()
            
            # Make API request
            response = await self._make_request(
                "GET",
                f"/products/{product_id}/analytics",
                params=params
            )
            
            # Parse response
            response_data = response.json()
            analytics_data = response_data.get("analytics", [])
            analytics = [GumroadAnalytics(**analytics) for analytics in analytics_data]
            
            # Cache response
            self._set_cache(cache_key, [analytics.dict() for analytics in analytics])
            
            logger.debug(
                "Gumroad analytics retrieved",
                product_id=product_id,
                count=len(analytics)
            )
            
            return analytics
            
        except Exception as e:
            logger.error(
                "Failed to get Gumroad analytics",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Analytics retrieval failed: {str(e)}") from e
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON payload
            params: Query parameters
            
        Returns:
            HTTP response
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    json=json,
                    params=params
                )
                response.raise_for_status()
                
                if attempt > 0:
                    logger.info(
                        "Request succeeded after retry",
                        method=method,
                        endpoint=endpoint,
                        attempt=attempt + 1
                    )
                
                return response
                
            except httpx.HTTPStatusError as e:
                last_error = e
                
                if attempt < self.max_retries:
                    # Don't retry on client errors (4xx)
                    if 400 <= e.response.status_code < 500:
                        break
                    
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        "Request failed, retrying",
                        method=method,
                        endpoint=endpoint,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        status_code=e.response.status_code
                    )
                    
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Request failed after all retries",
                        method=method,
                        endpoint=endpoint,
                        status_code=e.response.status_code,
                        error=e.response.text
                    )
                    raise
                    
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        "Request failed, retrying",
                        method=method,
                        endpoint=endpoint,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Request failed after all retries",
                        method=method,
                        endpoint=endpoint,
                        error=str(e)
                    )
                    raise
        
        # Should not reach here
        raise BaseLayerError(f"Request failed after {self.max_retries + 1} attempts: {str(last_error)}") from last_error
    
    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limits."""
        now = datetime.now(timezone.utc)
        
        # Reset minute counter
        if now - self.rate_limit["minute_reset_time"] >= timedelta(minutes=1):
            self.rate_limit["current_minute_requests"] = 0
            self.rate_limit["minute_reset_time"] = now
        
        # Reset hour counter
        if now - self.rate_limit["hour_reset_time"] >= timedelta(hours=1):
            self.rate_limit["current_hour_requests"] = 0
            self.rate_limit["hour_reset_time"] = now
        
        # Check limits
        if (self.rate_limit["current_minute_requests"] >= self.rate_limit["requests_per_minute"] or
            self.rate_limit["current_hour_requests"] >= self.rate_limit["requests_per_hour"]):
            
            # Calculate wait time
            minute_wait = (self.rate_limit["minute_reset_time"] + timedelta(minutes=1) - now).total_seconds()
            hour_wait = (self.rate_limit["hour_reset_time"] + timedelta(hours=1) - now).total_seconds()
            
            wait_time = max(minute_wait, hour_wait)
            
            logger.warning(
                "Rate limit reached, waiting",
                current_minute_requests=self.rate_limit["current_minute_requests"],
                current_hour_requests=self.rate_limit["current_hour_requests"],
                wait_time=wait_time
            )
            
            await asyncio.sleep(wait_time)
        
        # Increment counters
        self.rate_limit["current_minute_requests"] += 1
        self.rate_limit["current_hour_requests"] += 1
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache."""
        if key in self.cache:
            cache_entry = self.cache[key]
            
            # Check if cache is still valid
            if datetime.now(timezone.utc) - cache_entry["timestamp"] < timedelta(seconds=self.cache_ttl):
                return cache_entry["data"]
            else:
                # Remove expired cache entry
                del self.cache[key]
        
        return None
    
    def _set_cache(self, key: str, data: Any) -> None:
        """Set data in cache."""
        self.cache[key] = {
            "data": data,
            "timestamp": datetime.now(timezone.utc)
        }
    
    def _clear_cache(self, key: str) -> None:
        """Clear cache entry."""
        if key in self.cache:
            del self.cache[key]
    
    async def clear_all_cache(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.debug("All cache cleared")
    
    async def close(self) -> None:
        """Close HTTP client and clean up resources."""
        await self.client.aclose()
        self.cache.clear()
        
        logger.info("Gumroad client closed")
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        now = datetime.now(timezone.utc)
        
        return {
            "requests_per_minute": self.rate_limit["requests_per_minute"],
            "requests_per_hour": self.rate_limit["requests_per_hour"],
            "current_minute_requests": self.rate_limit["current_minute_requests"],
            "current_hour_requests": self.rate_limit["current_hour_requests"],
            "minute_reset_in": (self.rate_limit["minute_reset_time"] + timedelta(minutes=1) - now).total_seconds(),
            "hour_reset_in": (self.rate_limit["hour_reset_time"] + timedelta(hours=1) - now).total_seconds(),
            "cache_size": len(self.cache)
        }
