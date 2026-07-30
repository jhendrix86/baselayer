"""
MINT Product Template Models

SQLAlchemy models for product templates and generation patterns.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ProductTemplateType(str, Enum):
    """Product template types."""
    PDF_GUIDE = "pdf_guide"
    TEMPLATE_PACK = "template_pack"
    CHECKLIST = "checklist"
    CHEAT_SHEET = "cheat_sheet"
    PROMPT_LIBRARY = "prompt_library"
    CODE_SNIPPETS = "code_snippets"
    NOTION_TEMPLATE = "notion_template"


class ProductTemplate(Base):
    """
    Product template model for MINT engine.
    
    Defines templates for generating different types of digital products.
    """
    __tablename__ = "mint_product_templates"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    product_type = Column(String(50), nullable=False, default=ProductTemplateType.PDF_GUIDE)
    
    # Template configuration
    prompt_template_name = Column(String(100), nullable=False)
    structure = Column(JSON, nullable=False)  # Template structure and sections
    default_price_cents = Column(Integer, nullable=False, default=0)
    
    # Content specifications
    min_word_count = Column(Integer, default=1000)
    max_word_count = Column(Integer, default=10000)
    required_sections = Column(JSON, default=list)
    optional_sections = Column(JSON, default=list)
    
    # Generation settings
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    model_preference = Column(String(50), default="llama2:7b")
    
    # Tagging and categorization
    tags = Column(JSON, default=list)
    category = Column(String(50))
    target_audience = Column(String(200))
    difficulty_level = Column(String(20))  # beginner, intermediate, advanced
    
    # Usage tracking
    use_count = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    average_rating = Column(Float, default=0.0)
    
    # Quality controls
    min_quality_score = Column(Float, default=0.7)
    require_human_review = Column(Boolean, default=True)
    auto_approval_threshold = Column(Float, default=0.9)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_template_type', 'product_type'),
        Index('idx_template_category', 'category'),
        Index('idx_template_difficulty', 'difficulty_level'),
        Index('idx_template_created_at', 'created_at'),
        Index('idx_template_use_count', 'use_count'),
    )
    
    def __repr__(self) -> str:
        return f"<ProductTemplate(id={self.id}, name={self.name}, type={self.product_type})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "product_type": self.product_type,
            "prompt_template_name": self.prompt_template_name,
            "structure": self.structure,
            "default_price_cents": self.default_price_cents,
            "min_word_count": self.min_word_count,
            "max_word_count": self.max_word_count,
            "required_sections": self.required_sections,
            "optional_sections": self.optional_sections,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "model_preference": self.model_preference,
            "tags": self.tags,
            "category": self.category,
            "target_audience": self.target_audience,
            "difficulty_level": self.difficulty_level,
            "use_count": self.use_count,
            "success_rate": self.success_rate,
            "average_rating": self.average_rating,
            "min_quality_score": self.min_quality_score,
            "require_human_review": self.require_human_review,
            "auto_approval_threshold": self.auto_approval_threshold,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def default_price_dollars(self) -> float:
        """Get default price in dollars."""
        return self.default_price_cents / 100.0
    
    def increment_use_count(self) -> None:
        """Increment usage count."""
        self.use_count += 1
    
    def update_success_rate(self, success: bool) -> None:
        """Update success rate using exponential moving average."""
        alpha = 0.1  # Smoothing factor
        new_rate = 1.0 if success else 0.0
        self.success_rate = (alpha * new_rate) + ((1 - alpha) * self.success_rate)
    
    def update_rating(self, rating: float) -> None:
        """Update average rating."""
        if self.use_count == 0:
            self.average_rating = rating
        else:
            # Simple average (could use weighted average for more recent ratings)
            total_ratings = self.average_rating * (self.use_count - 1) + rating
            self.average_rating = total_ratings / self.use_count
    
    def get_section_count(self) -> int:
        """Get total number of sections."""
        required_count = len(self.required_sections or [])
        optional_count = len(self.optional_sections or [])
        return required_count + optional_count
    
    def get_complexity_score(self) -> float:
        """Calculate template complexity score."""
        # Factors: sections, word count, required sections
        section_score = min(self.get_section_count() / 10, 1.0)
        word_score = min(self.max_word_count / 5000, 1.0)
        required_score = len(self.required_sections or []) / 10
        
        return (section_score + word_score + required_score) / 3
    
    def is_suitable_for_audience(self, audience: str) -> bool:
        """Check if template is suitable for target audience."""
        if not self.target_audience:
            return True
        
        audience_lower = audience.lower()
        target_lower = self.target_audience.lower()
        
        # Simple keyword matching
        return any(keyword in audience_lower for keyword in target_lower.split())
    
    def get_generation_config(self) -> dict:
        """Get generation configuration for LLM."""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "model_preference": self.model_preference,
            "min_quality_score": self.min_quality_score,
            "require_human_review": self.require_human_review,
            "auto_approval_threshold": self.auto_approval_threshold
        }
    
    def validate_structure(self) -> list:
        """Validate template structure and return errors."""
        errors = []
        
        if not self.name:
            errors.append("Template name is required")
        
        if not self.prompt_template_name:
            errors.append("Prompt template name is required")
        
        if not self.structure:
            errors.append("Template structure is required")
        
        if self.min_word_count <= 0:
            errors.append("Minimum word count must be positive")
        
        if self.max_word_count <= self.min_word_count:
            errors.append("Maximum word count must be greater than minimum")
        
        if self.default_price_cents < 0:
            errors.append("Default price cannot be negative")
        
        if self.temperature < 0 or self.temperature > 2.0:
            errors.append("Temperature must be between 0 and 2")
        
        return errors


class ProductTemplateVersion(Base):
    """
    Product template version model.
    
    Tracks different versions of product templates.
    """
    __tablename__ = "mint_product_template_versions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to template
    template_id = Column(UUID(as_uuid=True), ForeignKey('mint_product_templates.id'), nullable=False)
    
    # Version information
    version = Column(String(20), nullable=False)
    changelog = Column(Text)
    
    # Versioned template data
    structure = Column(JSON, nullable=False)
    prompt_template_name = Column(String(100), nullable=False)
    required_sections = Column(JSON, default=list)
    optional_sections = Column(JSON, default=list)
    
    # Version metadata
    is_active = Column(Boolean, default=False)
    is_deprecated = Column(Boolean, default=False)
    deprecation_reason = Column(Text)
    
    # Usage tracking
    use_count = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    template = relationship("ProductTemplate", back_populates="versions")
    
    # Indexes
    __table_args__ = (
        Index('idx_template_version_template_id', 'template_id'),
        Index('idx_template_version_version', 'version'),
        Index('idx_template_version_is_active', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<ProductTemplateVersion(id={self.id}, template_id={self.template_id}, version={self.version})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "template_id": str(self.template_id),
            "version": self.version,
            "changelog": self.changelog,
            "structure": self.structure,
            "prompt_template_name": self.prompt_template_name,
            "required_sections": self.required_sections,
            "optional_sections": self.optional_sections,
            "is_active": self.is_active,
            "is_deprecated": self.is_deprecated,
            "deprecation_reason": self.deprecation_reason,
            "use_count": self.use_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def version_number(self) -> str:
        """Get semantic version number."""
        return self.version
    
    def activate(self) -> None:
        """Activate this version."""
        self.is_active = True
        self.is_deprecated = False
        self.deprecation_reason = None
    
    def deactivate(self, reason: str = None) -> None:
        """Deactivate this version."""
        self.is_active = False
        self.is_deprecated = True
        self.deprecation_reason = reason


# Add versions relationship to ProductTemplate
ProductTemplate.versions = relationship("ProductTemplateVersion", back_populates="template", cascade="all, delete-orphan")
