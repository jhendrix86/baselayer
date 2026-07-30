"""
MINT Gumroad Publisher Agent

Handles Gumroad API integration for publishing
digital products with error handling and retry logic.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from agents.core.agent_base import AgentBase
from agents.core.context import AgentContext, AgentConfig
from agents.memory.memory_interface import MemoryInterface
from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class GumroadProduct(BaseModel):
    """Gumroad product model."""
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


class GumroadClient:
    """Async Gumroad API client."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.gumroad.com/v2"):
        self.api_key: str = api_key
        self.base_url: str = base_url
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=base_url,
            headers=self.headers,
            timeout=30.0
        )
    
    async def create_product(self, product: GumroadProduct) -> Dict[str, Any]:
        """Create a new product on Gumroad."""
        try:
            response = await self.client.post(
                "/products",
                json=product.dict(exclude_none=True)
            )
            response.raise_for_status()
            
            logger.info(
                "Gumroad product created",
                product_name=product.name,
                price_cents=product.price_cents
            )
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Gumroad product creation failed",
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Gumroad product creation failed",
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def update_product(self, product_id: str, product: GumroadProduct) -> Dict[str, Any]:
        """Update an existing product on Gumroad."""
        try:
            response = await self.client.put(
                f"/products/{product_id}",
                json=product.dict(exclude_none=True)
            )
            response.raise_for_status()
            
            logger.info(
                "Gumroad product updated",
                product_id=product_id,
                product_name=product.name
            )
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Gumroad product update failed",
                product_id=product_id,
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Gumroad product update failed",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """Get product details from Gumroad."""
        try:
            response = await self.client.get(f"/products/{product_id}")
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get Gumroad product",
                product_id=product_id,
                status_code=e.response.status_code
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Failed to get Gumroad product",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def delete_product(self, product_id: str) -> Dict[str, Any]:
        """Delete a product from Gumroad."""
        try:
            response = await self.client.delete(f"/products/{product_id}")
            response.raise_for_status()
            
            logger.info(
                "Gumroad product deleted",
                product_id=product_id
            )
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to delete Gumroad product",
                product_id=product_id,
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Failed to delete Gumroad product",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def list_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List products from Gumroad."""
        try:
            response = await self.client.get("/products", params={"limit": limit})
            response.raise_for_status()
            
            return response.json().get("products", [])
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to list Gumroad products",
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Failed to list Gumroad products",
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def get_sales(self, product_id: str) -> List[Dict[str, Any]]:
        """Get sales data for a product."""
        try:
            response = await self.client.get(f"/products/{product_id}/sales")
            response.raise_for_status()
            
            return response.json().get("sales", [])
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get Gumroad sales",
                product_id=product_id,
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Failed to get Gumroad sales",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def get_analytics(self, product_id: str) -> Dict[str, Any]:
        """Get analytics for a product."""
        try:
            response = await self.client.get(f"/products/{product_id}/analytics")
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get Gumroad analytics",
                product_id=product_id,
                status_code=e.response.status_code,
                error=e.response.text
            )
            raise BaseLayerError(f"Gumroad API error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(
                "Failed to get Gumroad analytics",
                product_id=product_id,
                error=str(e)
            )
            raise BaseLayerError(f"Gumroad client error: {str(e)}") from e
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class GumroadPublisher(AgentBase):
    """
    Gumroad publishing agent for MINT engine.
    
    Handles product publishing to Gumroad with
    error handling, retry logic, and status tracking.
    """
    
    agent_name = "gumroad_publisher"
    agent_version = "1.0.0"
    
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__(config)
        self.api_key: Optional[str] = None
        self.gumroad_client: Optional[GumroadClient] = None
        
        # Publishing state
        self.publishing_queue: List[Dict[str, Any]] = []
        self.max_retries: int = 3
        self.retry_delay: int = 5  # seconds
    
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan Gumroad publishing approach.
        
        Args:
            input_data: Product information and publishing settings
            
        Returns:
            Dict containing publishing plan
        """
        try:
            # Extract product information
            product_id = input_data.get("product_id")
            title = input_data.get("title", "")
            description = input_data.get("description", "")
            price_cents = input_data.get("price_cents", 0)
            skip_review = input_data.get("skip_review", False)
            publish_immediately = input_data.get("publish_immediately", False)
            price_override_cents = input_data.get("price_override_cents")
            
            # Validate product exists and is ready
            validation_plan = {
                "verify_product_exists": True,
                "verify_product_status": "review",
                "verify_assets_complete": True,
                "verify_listing_optimized": True,
                "verify_pricing_set": price_cents > 0 or price_override_cents is not None
            }
            
            # Create publishing plan
            plan = {
                "product_id": product_id,
                "title": title,
                "description": description,
                "price_cents": price_cents,
                "price_override_cents": price_override_cents,
                "skip_review": skip_review,
                "publish_immediately": publish_immediately,
                "validation_plan": validation_plan,
                "publishing_strategy": "immediate" if publish_immediately else "scheduled",
                "gumroad_settings": {
                    "require_shipping": False,
                    "max_purchase_count": None,
                    "support_email": None,
                    "tags": []
                },
                "retry_strategy": {
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay,
                    "backoff": "exponential"
                },
                "estimated_duration": self._estimate_publishing_duration(
                    price_cents or price_override_cents
                )
            }
            
            logger.info(
                "Gumroad publishing plan created",
                product_id=product_id,
                strategy=plan["publishing_strategy"]
            )
            
            return plan
            
        except Exception as e:
            logger.error(
                "Failed to create publishing plan",
                error=str(e),
                input_data=input_data
            )
            raise BaseLayerError(f"Plan creation failed: {str(e)}") from e
    
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Gumroad publishing.
        
        Args:
            plan: Publishing plan from plan() phase
            
        Returns:
            Dict containing publishing results
        """
        try:
            # Initialize Gumroad client
            if not self.gumroad_client:
                self.api_key = self._get_api_key()
                self.gumroad_client = GumroadClient(self.api_key)
            
            product_id = plan["product_id"]
            title = plan["title"]
            description = plan["description"]
            price_cents = plan.get("price_override_cents") or plan["price_cents"]
            
            logger.info(
                "Starting Gumroad publishing",
                product_id=product_id,
                title=title
            )
            
            # Create Gumroad product
            gumroad_product = GumroadProduct(
                name=title,
                description=description,
                price_cents=price_cents,
                visible=True,
                require_shipping=plan["gumroad_settings"]["require_shipping"],
                tags=plan["gumroad_settings"]["tags"]
            )
            
            # Publish with retry logic
            gumroad_result = await self._publish_with_retry(
                gumroad_product,
                plan["retry_strategy"]
            )
            
            # Extract product ID and URL
            gumroad_product_id = gumroad_result.get("id")
            gumroad_url = gumroad_result.get("url")
            
            result = {
                "product_id": product_id,
                "gumroad_product_id": gumroad_product_id,
                "gumroad_url": gumroad_url,
                "publishing_status": "published",
                "publishing_strategy": plan["publishing_strategy"],
                "gumroad_response": gumroad_result,
                "success": bool(gumroad_product_id is not None),
                "error": None if gumroad_product_id else "Failed to create product"
            }
            
            logger.info(
                "Gumroad publishing completed",
                product_id=product_id,
                gumroad_product_id=gumroad_product_id,
                success=result["success"]
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Gumroad publishing execution failed",
                error=str(e),
                plan=plan
            )
            raise BaseLayerError(f"Publishing execution failed: {str(e)}") from e
    
    async def validate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate publishing results.
        
        Args:
            result: Publishing result from execute() phase
            
        Returns:
            Dict with validation results
        """
        try:
            gumroad_product_id = result.get("gumroad_product_id")
            gumroad_url = result.get("gumroad_url")
            success = result.get("success", False)
            
            validation_results = {
                "gumroad_product_created": {
                    "valid": gumroad_product_id is not None,
                    "error": None if gumroad_product_id else "No Gumroad product ID"
                },
                "gumroad_url_accessible": {
                    "valid": gumroad_url is not None if gumroad_url else "",
                    "error": None if gumroad_url else "No Gumroad URL"
                },
                "publishing_status": {
                    "valid": success,
                    "error": None if success else "Publishing failed"
                }
            }
            
            # Calculate overall validity
            all_valid = all(
                validation_results[check]["valid"]
                for check in validation_results
            )
            
            overall_score = sum(
                validation_results[check]["valid"]
                for check in validation_results
            ) / len(validation_results)
            
            logger.info(
                "Gumroad publishing validation completed",
                gumroad_product_id=gumroad_product_id,
                all_valid=all_valid
            )
            
            return {
                "valid": all_valid,
                "score": overall_score,
                "validation_results": validation_results,
                "errors": [
                    f"{check}: {result['error']}"
                    for check, result in validation_results.items()
                    if not result.get("valid", True)
                ]
            }
            
        except Exception as e:
            logger.error(
                "Gumroad publishing validation failed",
                error=str(e),
                result=result
            )
            return {
                "valid": False,
                "score": 0.0,
                "error": str(e)
            }
    
    async def report(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report publishing results.
        
        Args:
            result: Execution and validation results
            
        Returns:
            Dict containing report data
        """
        try:
            gumroad_product_id = result.get("gumroad_product_id")
            gumroad_url = result.get("gumroad_url")
            validation_results = result.get("validation_results", {})
            
            # Create report
            report = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "agent_version": self.agent_version,
                "execution_summary": {
                    "product_id": result.get("product_id"),
                    "publishing_strategy": result.get("publishing_strategy", ""),
                    "gumroad_product_id": gumroad_product_id,
                    "gumroad_url": gumroad_url,
                    "publishing_status": result.get("publishing_status", ""),
                    "validation_passed": validation_results.get("overall_valid", False),
                    "quality_score": validation_results.get("overall_score", 0.0)
                },
                "gumroad_details": {
                    "product_id": gumroad_product_id,
                    "url": gumroad_url,
                    "status": "published" if gumroad_product_id else "failed"
                },
                "validation_summary": validation_results,
                "recommendations": self._generate_recommendations(validation_results),
                "next_steps": self._generate_next_steps(validation_results.get("overall_valid", False)),
                "metrics": self._get_execution_metrics()
            }
            
            logger.info(
                "Gumroad publishing report created",
                gumroad_product_id=gumroad_product_id,
                validation_passed=validation_results.get("overall_valid", False)
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "Failed to create publishing report",
                error=str(e),
                result=result
            )
            return {
                "agent_id": self.agent_id,
                "error": str(e),
                "execution_summary": "Report generation failed"
            }
    
    def _get_api_key(self) -> str:
        """Get Gumroad API key from environment."""
        import os
        api_key = os.getenv("GUMROAD_ACCESS_TOKEN")
        
        if not api_key:
            raise BaseLayerError("GUMROAD_ACCESS_TOKEN environment variable not set")
        
        return api_key
    
    async def _publish_with_retry(
        self,
        product: GumroadProduct,
        retry_strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Publish product with retry logic."""
        last_error = None
        
        for attempt in range(retry_strategy["max_retries"] + 1):
            try:
                result = await self.gumroad_client.create_product(product)
                
                if attempt > 0:
                    logger.info(
                        "Gumroad product creation succeeded after retry",
                        attempt=attempt,
                        product_id=result.get("id")
                    )
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt < retry_strategy["max_retries"]:
                    delay = self._calculate_retry_delay(
                        attempt,
                        retry_strategy["retry_delay"],
                        retry_strategy["backoff"]
                    )
                    
                    logger.warning(
                        "Gumroad product creation failed, retrying",
                        attempt=attempt,
                        delay=delay,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Gumroad product creation failed after all retries",
                        attempts=attempt + 1,
                        error=str(e)
                    )
        
        # Return error if all retries failed
        return {
            "error": f"Failed after {retry_strategy['max_retries'] + 1} attempts: {str(last_error)}"
        }
    
    def _calculate_retry_delay(self, attempt: int, base_delay: int, backoff: str) -> int:
        """Calculate retry delay based on strategy."""
        if backoff == "exponential":
            return base_delay * (2 ** attempt)
        else:
            return base_delay
    
    def _estimate_publishing_duration(self, price_cents: int) -> int:
        """Estimate publishing duration in seconds."""
        # Base time plus additional time for higher-priced products
        base_time = 10  # seconds
        additional_time = (price_cents / 10000) * 20  # 20 extra seconds per $100
        
        return int(base_time + additional_time)
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for check_name, result in validation_results.items():
            if isinstance(result, dict) and not result.get("valid", True):
                if check_name == "gumroad_product_created":
                    recommendations.append("Verify Gumroad API credentials")
                elif check_name == "gumroad_url_accessible":
                    recommendations.append("Check product visibility and URL generation")
                elif check_name == "publishing_status":
                    recommendations.append("Retry publishing or check product status")
        
        return recommendations
    
    def _generate_next_steps(self, validation_passed: bool) -> List[str]:
        """Generate next steps based on validation."""
        if validation_passed:
            return [
                "Monitor Gumroad sales and analytics",
                "Update product information if needed",
                "Create promotional materials",
                "Set up email automation for buyers"
            ]
        else:
            return [
                "Fix validation issues",
                "Retry product publishing",
                "Verify product configuration",
                "Check Gumroad API status"
            ]
    
    async def close(self) -> None:
        """Clean up resources."""
        if self.gumroad_client:
            await self.gumroad_client.close()
            self.gumroad_client = None
        
        logger.info("Gumroad publisher closed")
