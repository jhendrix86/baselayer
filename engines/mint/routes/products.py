"""
MINT Products API Routes

FastAPI routes for product management,
creation, updates, and Gumroad integration.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError
from baselayer.core.middleware import success_response, error_response

from ..models.product import Product, ProductStatus, ProductType
from ..models.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    ProductGenerationRequest, ProductGenerationResponse,
    ProductPublishRequest, ProductPublishResponse,
    ProductRegenerateRequest, ProductRegenerateResponse,
    PaginationParams, FilterParams, ErrorResponse
)
from ..product_creation_pipeline import create_product_creation_pipeline
from ..product_update_pipeline import create_product_update_pipeline
from ..integrations.gumroad_client import GumroadClient

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/products", tags=["products"])


# Dependency to get database session
async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    # This would be implemented based on your database setup
    # For now, return None
    return None


# Dependency to get Gumroad client
async def get_gumroad_client() -> GumroadClient:
    """Get Gumroad client dependency."""
    import os
    api_key = os.getenv("GUMROAD_ACCESS_TOKEN")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gumroad API key not configured"
        )
    
    return GumroadClient(api_key)


@router.get("/", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    product_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    search: Optional[str] = Query(None),
    price_min: Optional[int] = Query(None, ge=0),
    price_max: Optional[int] = Query(None, ge=0),
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductListResponse:
    """
    List products with pagination and filtering.
    
    Supports filtering by type, status, tags, price range,
    and search functionality.
    """
    try:
        # Build query filters
        filters = []
        
        if product_type:
            filters.append(Product.product_type == product_type)
        
        if status:
            filters.append(Product.status == status)
        
        if tags:
            # JSON contains any of the tags
            tag_filters = [Product.tags.contains([tag]) for tag in tags]
            filters.append(or_(*tag_filters))
        
        if search:
            # Search in title, description, and tags
            search_filter = or_(
                Product.title.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.tags.contains([search])
            )
            filters.append(search_filter)
        
        if price_min is not None:
            filters.append(Product.price_cents >= price_min)
        
        if price_max is not None:
            filters.append(Product.price_cents <= price_max)
        
        # Build query
        query = select(Product).where(and_(*filters))
        
        # Add sorting
        if sort_by == "created_at":
            if sort_order == "desc":
                query = query.order_by(desc(Product.created_at))
            else:
                query = query.order_by(asc(Product.created_at))
        elif sort_by == "title":
            if sort_order == "desc":
                query = query.order_by(desc(Product.title))
            else:
                query = query.order_by(asc(Product.title))
        elif sort_by == "price":
            if sort_order == "desc":
                query = query.order_by(desc(Product.price_cents))
            else:
                query = query.order_by(asc(Product.price_cents))
        else:
            # Default to created_at desc
            query = query.order_by(desc(Product.created_at))
        
        # Add pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        # Execute query
        # result = await db_session.execute(query)
        # products = result.scalars().all()
        
        # For now, return empty list
        products = []
        total = 0
        
        # Convert to response models
        product_responses = [
            ProductResponse(**product.to_dict())
            for product in products
        ]
        
        # Calculate total pages
        pages = (total + size - 1) // size
        
        return ProductListResponse(
            products=product_responses,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
        
    except Exception as e:
        logger.error(
            "Failed to list products",
            error=str(e),
            page=page,
            size=size
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list products: {str(e)}"
        )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductResponse:
    """
    Get a specific product by ID.
    
    Returns complete product information including
    assets, analytics, and Gumroad details.
    """
    try:
        # Get product from database
        # query = select(Product).where(Product.id == product_id)
        # result = await db_session.execute(query)
        # product = result.scalar_one_or_none()
        
        # For now, return error
        if not True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        
        # Convert to response model
        # return ProductResponse(**product.to_dict())
        
        # For now, return error
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get product",
            error=str(e),
            product_id=product_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product: {str(e)}"
        )


@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductResponse:
    """
    Create a new product.
    
    Creates product with initial status 'draft'
    and generates unique slug.
    """
    try:
        # Create product instance
        product = Product(
            title=product_data.title,
            subtitle=product_data.subtitle,
            description=product_data.description,
            product_type=product_data.product_type,
            price_cents=product_data.price_cents,
            tags=product_data.tags,
            metadata=product_data.metadata,
            status=ProductStatus.DRAFT,
            slug=Product.generate_slug()  # Would use title
        )
        
        # Save to database
        # db_session.add(product)
        # await db_session.commit()
        # await db_session.refresh(product)
        
        # For now, return mock response
        return ProductResponse(
            id=str(uuid.uuid4()),
            title=product_data.title,
            subtitle=product_data.subtitle,
            description=product_data.description,
            product_type=product_data.product_type,
            status=ProductStatus.DRAFT,
            price_cents=product_data.price_cents,
            currency="USD",
            slug=product.slug,
            tags=product_data.tags,
            metadata=product_data.metadata,
            download_count=0,
            revenue_cents=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            version="1.0.0"
        )
        
    except Exception as e:
        logger.error(
            "Failed to create product",
            error=str(e),
            product_data=product_data.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {str(e)}"
        )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductResponse:
    """
    Update an existing product.
    
    Updates product fields while maintaining
    audit trail and version control.
    """
    try:
        # Get existing product
        # query = select(Product).where(Product.id == product_id)
        # result = await db_session.execute(query)
        # product = result.scalar_one_or_none()
        
        if not True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        
        # Update fields
        # if product_data.title is not None:
        #     product.title = product_data.title
        #     product.slug = product.generate_slug()
        # if product_data.subtitle is not None:
        #     product.subtitle = product_data.subtitle
        # if product_data.description is not None:
        #     product.description = product_data.description
        # if product_data.product_type is not None:
        #     product.product_type = product_data.product_type
        # if product_data.price_cents is not None:
        #     product.price_cents = product_data.price_cents
        # if product_data.tags is not None:
        #     product.tags = product_data.tags
        # if product_data.metadata is not None:
        #     product.metadata = product_data.metadata
        
        # product.updated_at = datetime.now(timezone.utc)
        
        # Save changes
        # await db_session.commit()
        # await db_session.refresh(product)
        
        # For now, return mock response
        return ProductResponse(
            id=product_id,
            title=product_data.title or "Updated Product",
            subtitle=product_data.subtitle,
            description=product_data.description or "Updated description",
            product_type=product_data.product_type or ProductType.PDF_GUIDE,
            status=ProductStatus.DRAFT,
            price_cents=product_data.price_cents or 0,
            currency="USD",
            slug="updated-product",
            tags=product_data.tags or [],
            metadata=product_data.metadata or {},
            download_count=0,
            revenue_cents=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            version="1.0.1"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update product",
            error=str(e),
            product_id=product_id,
            product_data=product_data.dict(exclude_none=True)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update product: {str(e)}"
        )


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Delete a product.
    
    Soft deletes product by setting status to archived.
    """
    try:
        # Get existing product
        # query = select(Product).where(Product.id == product_id)
        # result = await db_session.execute(query)
        # product = result.scalar_one_or_none()
        
        if not True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        
        # Soft delete
        # product.status = ProductStatus.ARCHIVED
        # product.updated_at = datetime.now(timezone.utc)
        
        # await db_session.commit()
        
        return success_response(
            message=f"Product {product_id} deleted successfully",
            data={"product_id": product_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete product",
            error=str(e),
            product_id=product_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}"
        )


@router.post("/generate", response_model=ProductGenerationResponse)
async def generate_product(
    request: ProductGenerationRequest,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductGenerationResponse:
    """
    Generate a new product using AI.
    
    Creates product content, packages it,
    optimizes listing, and prepares for publishing.
    """
    try:
        # Create product creation pipeline
        pipeline = create_product_creation_pipeline(db_session=db_session)
        
        # Start async generation
        generation_id = await pipeline.create_product_async(
            input_data=request.dict(),
            context=None
        )
        
        return ProductGenerationResponse(
            product_id=str(uuid.uuid4()),
            generation_id=generation_id,
            status="generating",
            progress=0.0,
            current_step="initializing",
            estimated_completion=datetime.now(timezone.utc),
            result=None,
            error=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(
            "Failed to start product generation",
            error=str(e),
            request=request.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start product generation: {str(e)}"
        )


@router.get("/generate/{generation_id}", response_model=ProductGenerationResponse)
async def get_generation_status(
    generation_id: str,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductGenerationResponse:
    """
    Get status of product generation.
    
    Returns current progress, step, and results
    if generation is complete.
    """
    try:
        # Create pipeline to get status
        pipeline = create_product_creation_pipeline(db_session=db_session)
        
        # Get generation status
        status = await pipeline.get_creation_status(generation_id)
        
        return ProductGenerationResponse(
            product_id=status.get("product_id", ""),
            generation_id=generation_id,
            status=status.get("status", "unknown"),
            progress=status.get("progress", 0.0),
            current_step=status.get("current_step"),
            estimated_completion=None,
            result=status.get("product_info") if status.get("status") == "completed" else None,
            error=status.get("error"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(
            "Failed to get generation status",
            error=str(e),
            generation_id=generation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get generation status: {str(e)}"
        )


@router.post("/publish", response_model=ProductPublishResponse)
async def publish_product(
    request: ProductPublishRequest,
    db_session: AsyncSession = Depends(get_db_session),
    gumroad_client: GumroadClient = Depends(get_gumroad_client)
) -> ProductPublishResponse:
    """
    Publish a product to Gumroad.
    
    Validates product completeness, creates Gumroad
    listing, and updates product status.
    """
    try:
        # Get product from database
        # query = select(Product).where(Product.id == request.product_id)
        # result = await db_session.execute(query)
        # product = result.scalar_one_or_none()
        
        if not True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {request.product_id} not found"
            )
        
        # Create Gumroad product
        from ..integrations.gumroad_client import GumroadProduct
        gumroad_product = GumroadProduct(
            name="Product Name",  # Would use product.title
            description="Product description",  # Would use product.description
            price_cents=request.price_override_cents or 0,
            visible=True,
            require_shipping=False,
            tags=[]
        )
        
        # Publish to Gumroad
        gumroad_result = await gumroad_client.create_product(gumroad_product.dict())
        
        # Update product with Gumroad info
        # product.gumroad_product_id = gumroad_result.get("id")
        # product.gumroad_url = gumroad_result.get("url")
        # product.status = ProductStatus.LISTED
        # product.listed_at = datetime.now(timezone.utc)
        # product.updated_at = datetime.now(timezone.utc)
        
        # await db_session.commit()
        
        return ProductPublishResponse(
            product_id=request.product_id,
            gumroad_product_id=gumroad_result.get("id", ""),
            gumroad_url=gumroad_result.get("url", ""),
            status="published",
            published_at=datetime.now(timezone.utc),
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to publish product",
            error=str(e),
            request=request.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish product: {str(e)}"
        )


@router.post("/regenerate", response_model=ProductRegenerateResponse)
async def regenerate_product(
    request: ProductRegenerateRequest,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductRegenerateResponse:
    """
    Regenerate product content.
    
    Regenerates specific sections or entire product
    with updated content and improved quality.
    """
    try:
        # Get product from database
        # query = select(Product).where(Product.id == request.product_id)
        # result = await db_session.execute(query)
        # product = result.scalar_one_or_none()
        
        if not True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {request.product_id} not found"
            )
        
        # Create product update pipeline
        pipeline = create_product_update_pipeline(db_session=db_session)
        
        # Start async regeneration
        regeneration_id = await pipeline.update_product_async(
            input_data=request.dict(),
            context=None
        )
        
        return ProductRegenerateResponse(
            product_id=request.product_id,
            regeneration_id=regeneration_id,
            status="regenerating",
            progress=0.0,
            regenerated_sections=request.sections or [],
            result=None,
            error=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to start product regeneration",
            error=str(e),
            request=request.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start product regeneration: {str(e)}"
        )


@router.get("/regenerate/{regeneration_id}", response_model=ProductRegenerateResponse)
async def get_regeneration_status(
    regeneration_id: str,
    db_session: AsyncSession = Depends(get_db_session)
) -> ProductRegenerateResponse:
    """
    Get status of product regeneration.
    
    Returns current progress, step, and results
    if regeneration is complete.
    """
    try:
        # Create pipeline to get status
        pipeline = create_product_update_pipeline(db_session=db_session)
        
        # Get regeneration status
        status = await pipeline.get_update_status(regeneration_id)
        
        return ProductRegenerateResponse(
            product_id=status.get("product_id", ""),
            regeneration_id=regeneration_id,
            status=status.get("status", "unknown"),
            progress=status.get("progress", 0.0),
            regenerated_sections=status.get("product_info", {}).get("updated_sections", []),
            result=status.get("product_info") if status.get("status") == "completed" else None,
            error=status.get("error"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(
            "Failed to get regeneration status",
            error=str(e),
            regeneration_id=regeneration_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get regeneration status: {str(e)}"
        )


@router.get("/types")
async def get_product_types() -> List[str]:
    """
    Get available product types.
    
    Returns list of supported product types
    for validation and UI display.
    """
    try:
        return [pt.value for pt in ProductType]
        
    except Exception as e:
        logger.error(
            "Failed to get product types",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product types: {str(e)}"
        )


@router.get("/statuses")
async def get_product_statuses() -> List[str]:
    """
    Get available product statuses.
    
    Returns list of supported product statuses
    for validation and UI display.
    """
    try:
        return [ps.value for ps in ProductStatus]
        
    except Exception as e:
        logger.error(
            "Failed to get product statuses",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product statuses: {str(e)}"
        )


@router.get("/analytics/{product_id}")
async def get_product_analytics(
    product_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get analytics for a specific product.
    
    Returns sales, views, revenue, and other
    metrics for the specified time period.
    """
    try:
        # Get Gumroad client
        gumroad_client = await get_gumroad_client()
        
        # Get analytics from Gumroad
        analytics = await gumroad_client.get_analytics(
            product_id=product_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return success_response(
            message=f"Analytics retrieved for product {product_id}",
            data=analytics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get product analytics",
            error=str(e),
            product_id=product_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product analytics: {str(e)}"
        )
