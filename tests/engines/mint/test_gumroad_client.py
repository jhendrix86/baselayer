"""
MINT Gumroad Client Tests

Test suite for GumroadClient including
API integration, error handling, and rate limiting.
"""

import pytest
import pytest_asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import asyncio

from agents.agents.gumroad_publisher import GumroadClient, GumroadProduct
from tests.engines.mint.conftest import (
    sample_gumroad_product,
    sample_gumroad_response,
    log_capture
)


class TestGumroadClient:
    """Test suite for GumroadClient."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization with API key."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        assert client.api_key == api_key
        assert client.base_url == "https://api.gumroad.com/v2"
        assert client.timeout == 30
        assert client.max_retries == 3
        assert client.cache_ttl == 300
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == f"Bearer {api_key}"
        assert client.headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_client_initialization_custom_config(self):
        """Test client initialization with custom configuration."""
        api_key = "test-api-key-123"
        client = GumroadClient(
            api_key=api_key,
            base_url="https://api.gumroad.com/v3",
            timeout=60,
            max_retries=5,
            cache_ttl=600
        )
        
        assert client.api_key == api_key
        assert client.base_url == "https://api.gumroad.com/v3"
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.cache_ttl == 600
    
    @pytest.mark.asyncio
    async def test_create_product_success(self):
        """Test successful product creation."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': sample_gumroad_response,
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            product_data = sample_gumroad_product.dict()
            
            result = await client.create_product(product_data)
            
            assert isinstance(result, dict)
            assert result["id"] == "gumroad-product-123"
            assert result["name"] == "Test Digital Product"
            assert result["price_cents"] == 999
    
    @pytest.mark.asyncio
    async def test_create_product_http_error(self):
        """Test product creation with HTTP error."""
        api_key = "test-api-key-123"
        
        # Mock HTTP error response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 400,
                'text': '{"error": "Invalid request"}',
                'raise_for_status.side_effect': Exception("HTTP 400")
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            product_data = sample_gumroad_product.dict()
            
            with pytest.raises(Exception):
                await client.create_product(product_data)
    
    @pytest.mark.asyncio
    async def test_update_product_success(self):
        """Test successful product update."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    **sample_gumroad_response,
                    "name": "Updated Product Name"
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            product_data = {"name": "Updated Product Name"}
            
            result = await client.update_product("test-product-id", product_data)
            
            assert isinstance(result, dict)
            assert result["id"] == "gumroad-product-123"
            assert result["name"] == "Updated Product Name"
    
    @pytest.mark.asyncio
    async def test_get_product_success(self):
        """Test successful product retrieval."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': sample_gumroad_response,
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.get_product("test-product-id")
            
            assert isinstance(result, dict)
            assert result["id"] == "gumroad-product-123"
            assert result["name"] == "Test Digital Product"
    
    @pytest.mark.asyncio
    async def test_get_product_not_found(self):
        """Test product retrieval when not found."""
        api_key = "test-api-key-123"
        
        # Mock 404 response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 404,
                'text': '{"error": "Product not found"}',
                'raise_for_status.side_effect': Exception("HTTP 404")
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.get_product("nonexistent-product-id")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_product_success(self):
        """Test successful product deletion."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {"success": True},
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.delete_product("test-product-id")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_product_not_found(self):
        """Test product deletion when not found."""
        api_key = "test-api-key-123"
        
        # Mock 404 response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 404,
                'text': '{"error": "Product not found"}',
                'raise_for_status.side_effect': Exception("HTTP 404")
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.delete_product("nonexistent-product-id")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_list_products_success(self):
        """Test successful product listing."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "products": [sample_gumroad_response]
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.list_products(limit=10)
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "gumroad-product-123"
    
    @pytest.mark.asyncio
    async def test_list_products_with_filters(self):
        """Test product listing with filters."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "products": [sample_gumroad_response]
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.list_products(
                limit=10,
                search="test",
                tags=["digital", "guide"]
            )
            
            assert isinstance(result, list)
            assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_get_sales_success(self):
        """Test successful sales retrieval."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "sales": [
                        {
                            "id": "sale-1",
                            "product_id": "test-product-id",
                            "email": "buyer@example.com",
                            "full_name": "Test Buyer",
                            "price_cents": 999,
                            "fee_cents": 100,
                            "net_cents": 899,
                            "created_at": "2024-01-01T00:00:00Z",
                            "refunded": False
                        }
                    ]
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.get_sales("test-product-id")
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "sale-1"
            assert result[0]["product_id"] == "test-product-id"
    
    @pytest.mark.asyncio
    async def test_get_sales_with_date_range(self):
        """Test sales retrieval with date range."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "sales": []
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.get_sales(
                "test-product-id",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 31, tzinfo=timezone.utc)
            )
            
            assert isinstance(result, list)
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_get_analytics_success(self):
        """Test successful analytics retrieval."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "analytics": [
                        {
                            "product_id": "test-product-id",
                            "views": 1000,
                            "sales": 50,
                            "revenue_cents": 49950,
                            "refunds": 2,
                            "conversion_rate": 5.0,
                            "date": "2024-01-01",
                            "source": "gumroad"
                        }
                    ]
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.get_analytics("test-product-id")
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["product_id"] == "test-product-id"
            assert result[0]["views"] == 1000
            assert result[0]["sales"] == 50
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Test rate limit check
        await client._check_rate_limit()
        
        assert client.rate_limit["current_minute_requests"] == 1
        assert client.rate_limit["current_hour_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_rate_limit_reset(self):
        """Test rate limit reset functionality."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Set high request counts
        client.rate_limit["current_minute_requests"] = 60
        client.rate_limit["current_hour_requests"] = 1000
        client.rate_limit["minute_reset_time"] = datetime.now(timezone.utc)
        client.rate_limit["hour_reset_time"] = datetime.now(timezone.utc)
        
        # Mock time to be in the future
        future_time = datetime.now(timezone.utc).timestamp() + 61
        with pytest.mock.patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.fromtimestamp(future_time, tz=timezone.utc)
            
            await client._check_rate_limit()
            
            # Should reset counters
            assert client.rate_limit["current_minute_requests"] == 1
            assert client.rate_limit["current_hour_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test cache operations."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Test cache set
        test_data = {"test": "data", "timestamp": datetime.now(timezone.utc).isoformat()}
        client._set_cache("test-key", test_data)
        
        assert "test-key" in client.cache
        assert client.cache["test-key"]["data"] == test_data
        
        # Test cache get
        cached_data = client._get_from_cache("test-key")
        assert cached_data == test_data
        
        # Test cache miss
        miss_data = client._get_from_cache("nonexistent-key")
        assert miss_data is None
        
        # Test cache clear
        client._clear_cache("test-key")
        assert "test-key" not in client.cache
    
    @pytest.mark.asyncio
    async def test_cache_expiry(self):
        """Test cache expiry functionality."""
        api_key = "test-api-key-123"
        client = GumroadClient(cache_ttl=1)  # 1 second TTL
        
        # Set cache
        test_data = {"test": "data"}
        client._set_cache("test-key", test_data)
        
        # Should be available immediately
        cached_data = client._get_from_cache("test-key")
        assert cached_data == test_data
        
        # Wait for expiry
        await asyncio.sleep(2)
        
        # Should be expired
        expired_data = client._get_from_cache("test-key")
        assert expired_data is None
    
    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic for failed requests."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key, max_retries=2)
        
        # Mock request that fails twice then succeeds
        call_count = 0
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                raise Exception(f"Attempt {call_count} failed")
            else:
                return type('MockResponse', (), {
                    'status_code': 200,
                    'json.return_value': sample_gumroad_response,
                    'raise_for_status.return_value': None
                })()
        
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.request.side_effect = mock_request
            
            result = await client.get_product("test-product-id")
            
            assert isinstance(result, dict)
            assert result["id"] == "gumroad-product-123"
            assert call_count == 3  # 2 failures + 1 success
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test retry exhaustion."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key, max_retries=2)
        
        # Mock request that always fails
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.request.side_effect = Exception("Always fails")
            
            with pytest.raises(Exception):
                await client.get_product("test-product-id")
    
    @pytest.mark.asyncio
    async def test_request_with_parameters(self):
        """Test request with query parameters."""
        api_key = "test-api-key-123"
        
        # Mock successful response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': {
                    "products": [sample_gumroad_response]
                },
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            result = await client.list_products(
                limit=10,
                offset=20,
                search="test query",
                tags=["digital", "guide"]
            )
            
            assert isinstance(result, list)
            assert len(result) == 1
            
            # Verify request was made with correct parameters
            mock_client.return_value.request.assert_called_once()
            call_args = mock_client.return_value.request.call_args
            assert "params" in call_args[1]
            assert call_args[1]["params"]["limit"] == 10
            assert call_args[1]["params"]["offset"] == 20
            assert call_args[1]["params"]["search"] == "test query"
            assert call_args[1]["params"]["tags"] == "digital,guide"
    
    @pytest.mark.asyncio
    async def test_rate_limit_status(self):
        """Test rate limit status reporting."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Make some requests to update counters
        await client._check_rate_limit()
        await client._check_rate_limit()
        
        status = client.get_rate_limit_status()
        
        assert status["requests_per_minute"] == 60
        assert status["requests_per_hour"] == 1000
        assert status["current_minute_requests"] == 2
        assert status["current_hour_requests"] == 2
        assert status["minute_reset_in"] > 0
        assert status["hour_reset_in"] > 0
        assert status["cache_size"] == 0
    
    @pytest.mark.asyncio
    async def test_cache_clear_all(self):
        """Test clearing all cache."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Add some cache entries
        client._set_cache("key1", {"data": "1"})
        client._set_cache("key2", {"data": "2"})
        client._set_cache("key3", {"data": "3"})
        
        assert len(client.cache) == 3
        
        # Clear all cache
        await client.clear_all_cache()
        
        assert len(client.cache) == 0
    
    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test client cleanup."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Add some cache entries
        client._set_cache("test-key", {"data": "test"})
        
        # Close client
        await client.close()
        
        # Cache should be cleared
        assert len(client.cache) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_4xx(self):
        """Test error handling for 4xx responses."""
        api_key = "test-api-key-123"
        
        # Mock 4xx response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 422,
                'text': '{"error": "Validation failed"}',
                'raise_for_status.side_effect': Exception("HTTP 422")
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            
            with pytest.raises(Exception):
                await client.create_product({"invalid": "data"})
    
    @pytest.mark.asyncio
    async def test_error_handling_5xx(self):
        """Test error handling for 5xx responses."""
        api_key = "test-api-key-123"
        
        # Mock 5xx response
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 500,
                'text': '{"error": "Internal server error"}',
                'raise_for_status.side_effect': Exception("HTTP 500")
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            client = GumroadClient(api_key)
            
            with pytest.raises(Exception):
                await client.create_product(sample_gumroad_product.dict())
    
    @pytest.mark.asyncio
    async def test_logging(self, log_capture):
        """Test logging functionality."""
        api_key = "test-api-key-123"
        client = GumroadClient(api_key)
        
        # Start capturing logs
        log_capture.start()
        
        # Make a request
        with pytest.mock.patch('httpx.AsyncClient') as mock_client:
            mock_response = asyncio.Future()
            mock_response.set_result(type('MockResponse', (), {
                'status_code': 200,
                'json.return_value': sample_gumroad_response,
                'raise_for_status.return_value': None
            })())
            
            mock_client.return_value.request.return_value = mock_response
            
            result = await client.get_product("test-product-id")
        
        # Stop capturing logs
        log_capture.stop()
        
        # Check that logs were captured
        messages = log_capture.get_messages("INFO")
        assert len(messages) > 0
        
        # Check for specific log messages
        info_messages = [msg for msg in messages if "Gumroad product retrieved" in msg["message"]]
        assert len(info_messages) > 0
