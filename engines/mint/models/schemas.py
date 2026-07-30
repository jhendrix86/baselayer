"""
MINT Pydantic Schemas

Request and response schemas for MINT API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ProductCreate(BaseModel):
    """Product creation request schema."""
    title: str = Field(..., min_length=5, max_length=200, description="Product title")
    subtitle: Optional[str] = Field(None, max_length=300, description="Product subtitle")
    description: str = Field(..., min_length=50, description="Product description")
    product_type: str = Field(..., description="Product type")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    tags: List[str] = Field(default_factory=list, max_items=10, description="Product tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('title')
    def validate_title(cls, v):
        """Validate title format."""
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('product_type')
    def validate_product_type(cls, v):
        """Validate product type."""
        from .product import ProductType
        valid_types = [pt.value for pt in ProductType]
        if v not in valid_types:
            raise ValueError(f'Invalid product type. Must be one of: {valid_types}')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags format."""
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        
        for tag in v:
            if not tag.strip():
                raise ValueError('Tags cannot be empty')
            if len(tag) > 50:
                raise ValueError('Tag cannot exceed 50 characters')
        
        return [tag.strip() for tag in v if tag.strip()]
    
    @validator('price_cents')
    def validate_price(cls, v):
        """Validate price."""
        if v < 0:
            raise ValueError('Price cannot be negative')
        if v > 999999:  # $9999.99 max
            raise ValueError('Price cannot exceed $9999.99')
        return v


class ProductUpdate(BaseModel):
    """Product update request schema."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, min_length=50)
    product_type: Optional[str] = None
    price_cents: Optional[int] = Field(None, ge=0)
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError('Title cannot be empty')
            return v.strip()
        return v
    
    @validator('product_type')
    def validate_product_type(cls, v):
        if v is not None:
            from .product import ProductType
            valid_types = [pt.value for pt in ProductType]
            if v not in valid_types:
                raise ValueError(f'Invalid product type. Must be one of: {valid_types}')
            return v
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if len(v) > 10:
                raise ValueError('Maximum 10 tags allowed')
            
            for tag in v:
                if not tag.strip():
                    raise ValueError('Tags cannot be empty')
                if len(tag) > 50:
                    raise ValueError('Tag cannot exceed 50 characters')
            
            return [tag.strip() for tag in v if tag.strip()]
        return v
    
    @validator('price_cents')
    def validate_price(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError('Price cannot be negative')
            if v > 999999:
                raise ValueError('Price cannot exceed $9999.99')
            return v
        return v


class ProductResponse(BaseModel):
    """Product response schema."""
    id: str
    title: str
    subtitle: Optional[str]
    description: str
    product_type: str
    status: str
    price_cents: int
    currency: str
    slug: str
    tags: List[str]
    gumroad_product_id: Optional[str]
    gumroad_url: Optional[str]
    file_paths: List[str]
    metadata: Dict[str, Any]
    download_count: int
    revenue_cents: int
    created_at: datetime
    updated_at: datetime
    listed_at: Optional[datetime]
    version: str
    
    @validator('price_cents', pre=True)
    def format_price(cls, v):
        """Format price for display."""
        return v / 100.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ProductListResponse(BaseModel):
    """Product list response schema."""
    products: List[ProductResponse]
    total: int
    page: int
    size: int
    pages: int
    
    @validator('page')
    def validate_page(cls, v):
        return max(1, v)
    
    @validator('size')
    def validate_size(cls, v):
        return min(100, max(1, v))


class ProductTemplateCreate(BaseModel):
    """Product template creation schema."""
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    product_type: str = Field(..., description="Template product type")
    prompt_template_name: str = Field(..., min_length=3, max_length=100)
    structure: Dict[str, Any] = Field(..., description="Template structure")
    default_price_cents: int = Field(..., ge=0)
    tags: List[str] = Field(default_factory=list, max_items=10)
    min_word_count: int = Field(default=1000, ge=100)
    max_word_count: int = Field(default=10000, ge=500)
    required_sections: List[str] = Field(default_factory=list)
    optional_sections: List[str] = Field(default_factory=list)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=8000)
    model_preference: str = Field(default="llama2:7b")
    category: Optional[str] = Field(None, max_length=50)
    target_audience: Optional[str] = Field(None, max_length=200)
    difficulty_level: Optional[str] = Field(None)
    min_quality_score: float = Field(default=0.7, ge=0.0, le=1.0)
    require_human_review: bool = Field(default=True)
    auto_approval_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Template name cannot be empty')
        return v.strip()
    
    @validator('product_type')
    def validate_product_type(cls, v):
        from .product_template import ProductTemplateType
        valid_types = [pt.value for pt in ProductTemplateType]
        if v not in valid_types:
            raise ValueError(f'Invalid product type. Must be one of: {valid_types}')
        return v
    
    @validator('max_word_count')
    def validate_word_count(cls, v):
        if v <= 1000:
            raise ValueError('Maximum word count must be greater than minimum')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        
        for tag in v:
            if not tag.strip():
                raise ValueError('Tags cannot be empty')
            if len(tag) > 50:
                raise ValueError('Tag cannot exceed 50 characters')
        
        return [tag.strip() for tag in v if tag.strip()]


class ProductTemplateResponse(BaseModel):
    """Product template response schema."""
    id: str
    name: str
    description: Optional[str]
    product_type: str
    prompt_template_name: str
    structure: Dict[str, Any]
    default_price_cents: int
    min_word_count: int
    max_word_count: int
    required_sections: List[str]
    optional_sections: List[str]
    temperature: float
    max_tokens: int
    model_preference: str
    tags: List[str]
    category: Optional[str]
    target_audience: Optional[str]
    difficulty_level: Optional[str]
    use_count: int
    success_rate: float
    average_rating: float
    min_quality_score: float
    require_human_review: bool
    auto_approval_threshold: float
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    @validator('default_price_cents', pre=True)
    def format_price(cls, v):
        return v / 100.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AnalyticsResponse(BaseModel):
    """Analytics response schema."""
    product_id: str
    date: datetime
    views: int
    sales: int
    revenue_cents: int
    revenue_dollars: float
    refunds: int
    conversion_rate: float
    source: str
    unique_visitors: int
    page_views: int
    add_to_cart: int
    checkout_started: int
    gross_revenue_cents: int
    net_revenue_cents: int
    fees_cents: int
    gross_revenue_dollars: float
    net_revenue_dollars: float
    fees_dollars: float
    
    @validator('revenue_cents', pre=True)
    def format_revenue(cls, v):
        return v / 100.0
    
    @validator('gross_revenue_cents', pre=True)
    def format_gross_revenue(cls, v):
        return v / 100.0
    
    @validator('net_revenue_cents', pre=True)
    def format_net_revenue(cls, v):
        return v / 100.0
    
    @validator('fees_cents', pre=True)
    def format_fees(cls, v):
        return v / 100.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ProductGenerationRequest(BaseModel):
    """Product generation request schema."""
    product_type: str = Field(..., description="Type of product to generate")
    brief: str = Field(..., min_length=10, max_length=1000, description="Product brief or description")
    target_audience: Optional[str] = Field(None, max_length=200)
    price_range: Optional[str] = Field(None, description="Price range (free, low, medium, high)")
    word_count_target: Optional[int] = Field(None, ge=500, le=20000)
    template_id: Optional[str] = None
    skip_review: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('product_type')
    def validate_product_type(cls, v):
        from .product import ProductType
        valid_types = [pt.value for pt in ProductType]
        if v not in valid_types:
            raise ValueError(f'Invalid product type. Must be one of: {valid_types}')
        return v
    
    @validator('brief')
    def validate_brief(cls, v):
        if not v.strip():
            raise ValueError('Brief cannot be empty')
        return v.strip()


class ProductGenerationResponse(BaseModel):
    """Product generation response schema."""
    product_id: str
    generation_id: str
    status: str
    progress: float
    current_step: Optional[str]
    estimated_completion: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ProductPublishRequest(BaseModel):
    """Product publish request schema."""
    product_id: str
    skip_review: bool = Field(default=False)
    publish_immediately: bool = Field(default=False)
    price_override_cents: Optional[int] = Field(None, ge=0)
    
    @validator('product_id')
    def validate_product_id(cls, v):
        if not v.strip():
            raise ValueError('Product ID cannot be empty')
        return v.strip()


class ProductPublishResponse(BaseModel):
    """Product publish response schema."""
    product_id: str
    gumroad_product_id: str
    gumroad_url: str
    status: str
    published_at: Optional[datetime]
    error: Optional[str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ProductRegenerateRequest(BaseModel):
    """Product regenerate request schema."""
    product_id: str
    sections: Optional[List[str]] = None
    template_id: Optional[str] = None
    force_regenerate: bool = Field(default=False)
    
    @validator('product_id')
    def validate_product_id(cls, v):
        if not v.strip():
            raise ValueError('Product ID cannot be empty')
        return v.strip()


class ProductRegenerateResponse(BaseModel):
    """Product regenerate response schema."""
    product_id: str
    regeneration_id: str
    status: str
    progress: float
    regenerated_sections: List[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class SuccessResponse(BaseModel):
    """Standard success response schema."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = Field(None)
    sort_order: Optional[str] = Field(default="desc", regex="^(asc|desc)$")
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError('Sort order must be either "asc" or "desc"')
        return v


class FilterParams(BaseModel):
    """Filter parameters."""
    product_type: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    price_min: Optional[int] = Field(None, ge=0)
    price_max: Optional[int] = Field(None, ge=0)
    search: Optional[str] = None
    
    @validator('product_type')
    def validate_product_type(cls, v):
        if v is not None:
            from .product import ProductType
            valid_types = [pt.value for pt in ProductType]
            if v not in valid_types:
                raise ValueError(f'Invalid product type. Must be one of: {valid_types}')
            return v
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            from .product import ProductStatus
            valid_statuses = [ps.value for ps in ProductStatus]
            if v not in valid_statuses:
                raise ValueError(f'Invalid status. Must be one of: {valid_statuses}')
            return v
        return v
    
    @validator('price_min')
    def validate_price_min(cls, v):
        if v is not None and v < 0:
            raise ValueError('Minimum price cannot be negative')
        return v
    
    @validator('price_max')
    def validate_price_max(cls, v):
        if v is not None and v < 0:
            raise ValueError('Maximum price cannot be negative')
        return v
