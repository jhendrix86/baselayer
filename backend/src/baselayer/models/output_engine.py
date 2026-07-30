"""
BaseLayer Output Engineering Models

Output templates, generation tracking, and delivery management
for the Output Engineering subsystem.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class OutputType(str, Enum):
    """Output types."""
    REPORT = "report"
    DOCUMENT = "document"
    EMAIL = "email"
    NOTIFICATION = "notification"
    DASHBOARD = "dashboard"
    EXPORT = "export"


class OutputFormat(str, Enum):
    """Output formats."""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


class DeliveryMethod(str, Enum):
    """Delivery methods."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    FILE = "file"
    API = "api"
    FTP = "ftp"
    SMS = "sms"


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class OutputTemplate(BaseModel):
    """
    Output template model for Output Engineering subsystem.
    
    Defines reusable templates for generating various types of outputs.
    """
    
    __tablename__ = "output_templates"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Template name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Template description"
    )
    
    # Type and format
    output_type: Mapped[OutputType] = mapped_column(
        ENUM(OutputType, name="output_type"),
        nullable=False,
        index=True,
        comment="Type of output"
    )
    
    output_format: Mapped[OutputFormat] = mapped_column(
        ENUM(OutputFormat, name="output_format"),
        nullable=False,
        index=True,
        comment="Output format"
    )
    
    # Template content
    template_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template content with placeholders"
    )
    
    # Variables and configuration
    variables: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Template variables with types and defaults"
    )
    
    # Styling and formatting
    styling_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Styling and formatting configuration"
    )
    
    # Generation settings
    generation_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Generation-specific configuration"
    )
    
    # Version control
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Template version"
    )
    
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("output_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent template for versioning"
    )
    
    # Delivery configuration
    default_delivery_methods: Mapped[list[DeliveryMethod]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Default delivery methods"
    )
    
    delivery_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Delivery configuration"
    )
    
    # Governance and compliance
    governance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether governance approval is required"
    )
    
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of user who approved the template"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when template was approved"
    )
    
    # Usage metrics
    usage_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the template has been used"
    )
    
    last_used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when template was last used"
    )
    
    # Metadata
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tags for categorization"
    )
    
    author: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Template author"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the template is active"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="output_templates",
        foreign_keys=[BaseModel.created_by],
        lazy="select"
    )
    
    parent = relationship(
        "OutputTemplate",
        remote_side="OutputTemplate.id",
        back_populates="children",
        lazy="select"
    )
    
    children = relationship(
        "OutputTemplate",
        back_populates="parent",
        lazy="select"
    )
    
    generated_outputs = relationship(
        "GeneratedOutput",
        back_populates="template",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_output_template_name_deleted"),
        Index("idx_template_type_format", "output_type", "output_format"),
        Index("idx_template_usage", "usage_count"),
        Index("idx_template_tags", "tags", postgresql_using="gin"),
        {"comment": "Output templates for generating various types of content"}
    )
    
    def __repr__(self) -> str:
        """String representation of the output template."""
        return f"<OutputTemplate(name='{self.name}', type='{self.output_type}', format='{self.output_format}')>"
    
    @property
    def is_approved(self) -> bool:
        """Check if template is approved."""
        return self.approved_at is not None
    
    @property
    def requires_governance(self) -> bool:
        """Check if template requires governance approval."""
        return self.governance_required and not self.is_approved
    
    def approve(self, approved_by: uuid.UUID) -> None:
        """
        Approve the template.
        
        Args:
            approved_by: ID of user approving the template
        """
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()
        self.increment_version()
    
    def render(self, variables: Dict[str, Any]) -> str:
        """
        Render the template with provided variables.
        
        Args:
            variables: Variables to substitute in template
            
        Returns:
            str: Rendered template content
        """
        content = self.template_content
        
        # Simple variable substitution
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            content = content.replace(placeholder, str(var_value))
        
        return content
    
    def record_usage(self) -> None:
        """Record template usage."""
        self.usage_count = str(int(self.usage_count) + 1)
        self.last_used_at = datetime.utcnow()
    
    def add_variable(
        self,
        name: str,
        var_type: str,
        required: bool = False,
        default_value: Any = None,
        description: str = ""
    ) -> None:
        """
        Add a variable to the template.
        
        Args:
            name: Variable name
            var_type: Variable type
            required: Whether variable is required
            default_value: Default value
            description: Variable description
        """
        if not self.variables:
            self.variables = {}
        
        self.variables[name] = {
            "type": var_type,
            "required": required,
            "default_value": default_value,
            "description": description
        }
        
        self.increment_version()
    
    def validate_variables(self, variables: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate variables against template requirements.
        
        Args:
            variables: Variables to validate
            
        Returns:
            tuple[bool, list[str]]: (is_valid, error_messages)
        """
        errors = []
        
        if not self.variables:
            return True, errors
        
        # Check required variables
        for var_name, var_def in self.variables.items():
            if var_def.get("required", False) and var_name not in variables:
                errors.append(f"Required variable '{var_name}' is missing")
        
        return len(errors) == 0, errors


class GeneratedOutput(BaseModel):
    """
    Generated output model.
    
    Tracks individual output generation with content and delivery status.
    """
    
    __tablename__ = "generated_outputs"
    
    # References
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("output_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the output template"
    )
    
    # Generation details
    output_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique output identifier"
    )
    
    generation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Generation batch identifier"
    )
    
    # Content
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Output title"
    )
    
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Generated output content"
    )
    
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 hash of content for integrity"
    )
    
    # Variables used
    variables_used: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Variables used in generation"
    )
    
    # Generation metadata
    generation_time: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Generation time in milliseconds"
    )
    
    file_size_bytes: Mapped[int] = mapped_column(
        String(15),
        nullable=True,
        comment="File size in bytes"
    )
    
    page_count: Mapped[int] = mapped_column(
        String(5),
        nullable=True,
        comment="Number of pages (for documents)"
    )
    
    # Status and timing
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="generated",
        comment="Generation status"
    )
    
    generated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Generation timestamp"
    )
    
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Expiration timestamp"
    )
    
    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if generation failed"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    # Access control
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="public",
        comment="Access level for the output"
    )
    
    allowed_users: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of allowed user IDs"
    )
    
    # Relationships
    template = relationship(
        "OutputTemplate",
        back_populates="generated_outputs",
        lazy="select"
    )
    
    delivery_logs = relationship(
        "DeliveryLog",
        back_populates="output",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_output_template_status", "template_id", "status"),
        Index("idx_output_generation", "generation_id"),
        Index("idx_output_generated", "generated_at"),
        Index("idx_output_expires", "expires_at"),
        {"comment": "Generated outputs with content and delivery tracking"}
    )
    
    def __repr__(self) -> str:
        """String representation of the generated output."""
        return f"<GeneratedOutput(output_id='{self.output_id}', title='{self.title}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if output has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def can_access(self, user_id: str) -> bool:
        """
        Check if user can access the output.
        
        Args:
            user_id: User ID to check
            
        Returns:
            bool: True if user can access
        """
        if self.access_level == "public":
            return True
        
        if self.access_level == "private":
            return user_id in self.allowed_users
        
        return False
    
    def set_expiration(self, hours: int) -> None:
        """
        Set expiration time.
        
        Args:
            hours: Hours until expiration
        """
        self.expires_at = datetime.utcnow() + datetime.timedelta(hours=hours)
    
    def grant_access(self, user_id: str) -> None:
        """
        Grant access to a user.
        
        Args:
            user_id: User ID to grant access to
        """
        if user_id not in self.allowed_users:
            self.allowed_users.append(user_id)
    
    def revoke_access(self, user_id: str) -> None:
        """
        Revoke access from a user.
        
        Args:
            user_id: User ID to revoke access from
        """
        if user_id in self.allowed_users:
            self.allowed_users.remove(user_id)


class DeliveryLog(BaseModel):
    """
    Delivery log model.
    
    Tracks delivery attempts and status for generated outputs.
    """
    
    __tablename__ = "delivery_logs"
    
    # References
    output_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("generated_outputs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the generated output"
    )
    
    # Delivery details
    delivery_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique delivery identifier"
    )
    
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        ENUM(DeliveryMethod, name="delivery_method"),
        nullable=False,
        index=True,
        comment="Delivery method used"
    )
    
    # Recipient information
    recipient: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Delivery recipient (email, webhook URL, etc.)"
    )
    
    recipient_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="email",
        comment="Type of recipient (email, webhook, api, etc.)"
    )
    
    # Delivery configuration
    delivery_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Delivery-specific configuration"
    )
    
    # Status and timing
    status: Mapped[DeliveryStatus] = mapped_column(
        ENUM(DeliveryStatus, name="delivery_status"),
        nullable=False,
        default=DeliveryStatus.PENDING,
        index=True,
        comment="Current delivery status"
    )
    
    initiated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Delivery initiation time"
    )
    
    delivered_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Delivery completion time"
    )
    
    retry_count: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="0",
        comment="Number of retry attempts"
    )
    
    max_retries: Mapped[int] = mapped_column(
        String(2),
        nullable=False,
        default="3",
        comment="Maximum number of retry attempts"
    )
    
    next_retry_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp for next retry attempt"
    )
    
    # Response information
    response_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP response code or delivery status code"
    )
    
    response_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Response message from delivery service"
    )
    
    # Error handling
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if delivery failed"
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if delivery failed"
    )
    
    error_details: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed error information"
    )
    
    # Tracking
    tracking_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Delivery tracking ID"
    )
    
    delivery_receipt: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Delivery receipt information"
    )
    
    # Relationships
    output = relationship(
        "GeneratedOutput",
        back_populates="delivery_logs",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_delivery_output_status", "output_id", "status"),
        Index("idx_delivery_method", "delivery_method"),
        Index("idx_delivery_initiated", "initiated_at"),
        Index("idx_delivery_retry", "next_retry_at"),
        {"comment": "Delivery logs for output tracking"}
    )
    
    def __repr__(self) -> str:
        """String representation of the delivery log."""
        return f"<DeliveryLog(delivery_id='{self.delivery_id}', method='{self.delivery_method}', status='{self.status}')>"
    
    @property
    def is_pending(self) -> bool:
        """Check if delivery is pending."""
        return self.status == DeliveryStatus.PENDING
    
    @property
    def is_delivered(self) -> bool:
        """Check if delivery was successful."""
        return self.status == DeliveryStatus.DELIVERED
    
    @property
    def is_failed(self) -> bool:
        """Check if delivery failed."""
        return self.status == DeliveryStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """Check if delivery can be retried."""
        return int(self.retry_count) < int(self.max_retries)
    
    @property
    def should_retry_now(self) -> bool:
        """Check if delivery should be retried now."""
        return (
            self.is_failed and
            self.can_retry and
            self.next_retry_at is not None and
            datetime.utcnow() >= self.next_retry_at
        )
    
    def deliver(self, response_code: str, response_message: str = "", tracking_id: str | None = None) -> None:
        """
        Mark delivery as successful.
        
        Args:
            response_code: Response code from delivery service
            response_message: Response message
            tracking_id: Delivery tracking ID
        """
        self.status = DeliveryStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        self.response_code = response_code
        self.response_message = response_message
        self.tracking_id = tracking_id
    
    def fail(self, error_code: str, error_message: str, error_details: Dict[str, Any] | None = None) -> None:
        """
        Mark delivery as failed.
        
        Args:
            error_code: Error code
            error_message: Error message
            error_details: Detailed error information
        """
        self.status = DeliveryStatus.FAILED
        self.error_code = error_code
        self.error_message = error_message
        
        if error_details:
            self.error_details = error_details
        
        # Schedule retry if possible
        if self.can_retry:
            self.schedule_retry()
    
    def schedule_retry(self) -> None:
        """Schedule the next retry attempt."""
        if not self.can_retry:
            return
        
        self.retry_count = str(int(self.retry_count) + 1)
        self.status = DeliveryStatus.RETRYING
        
        # Exponential backoff: 1min, 2min, 4min, 8min, etc.
        retry_delay_minutes = 2 ** (int(self.retry_count) - 1)
        self.next_retry_at = datetime.utcnow() + datetime.timedelta(minutes=retry_delay_minutes)
    
    def cancel(self) -> None:
        """Cancel the delivery."""
        self.status = DeliveryStatus.CANCELLED
        self.next_retry_at = None
