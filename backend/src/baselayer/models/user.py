"""
BaseLayer User Model

User management with roles, permissions, and authentication tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from .base import BaseModel, UUIDType
from ..core.config import get_settings


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    AGENT = "agent"


class User(BaseModel):
    """
    User model with authentication, roles, and profile information.
    
    Supports multiple authentication methods and role-based access control
    for the BaseLayer governance system.
    """
    
    __tablename__ = "users"
    
    # Basic user information
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique username for login"
    )
    
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User email address"
    )
    
    full_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User's full name"
    )
    
    # Authentication fields
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Hashed password for local authentication"
    )
    
    api_key_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Hashed API key for programmatic access"
    )
    
    # Role and permissions
    role: Mapped[UserRole] = mapped_column(
        ENUM(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.VIEWER,
        index=True,
        comment="User role determining permissions"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the user account is active"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the user email is verified"
    )
    
    # Security and tracking
    last_login: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp of last successful login"
    )
    
    last_login_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of last login"
    )
    
    failed_login_attempts: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of consecutive failed login attempts"
    )
    
    locked_until: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp until which account is locked"
    )
    
    # Profile and preferences
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to user's avatar image"
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="User's preferred timezone"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="User's preferred language"
    )
    
    theme: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="light",
        comment="User's preferred theme (light/dark)"
    )
    
    # Notification preferences
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether user receives email notifications"
    )
    
    push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user receives push notifications"
    )
    
    # Governance and compliance
    compliance_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        comment="Compliance level for governance requirements"
    )
    
    audit_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user actions require audit logging"
    )
    
    # Relationships
    workflows = relationship(
        "Workflow",
        back_populates="created_by_user",
        foreign_keys="Workflow.created_by",
        lazy="select"
    )
    
    revenue_streams = relationship(
        "RevenueStream",
        back_populates="created_by_user",
        foreign_keys="RevenueStream.created_by",
        lazy="select"
    )
    
    knowledge_entries = relationship(
        "KnowledgeEntry",
        back_populates="created_by_user",
        foreign_keys="KnowledgeEntry.created_by",
        lazy="select"
    )
    
    protocols = relationship(
        "Protocol",
        back_populates="created_by_user",
        foreign_keys="Protocol.created_by",
        lazy="select"
    )
    
    agents = relationship(
        "Agent",
        back_populates="created_by_user",
        foreign_keys="Agent.created_by",
        lazy="select"
    )
    
    governance_rules = relationship(
        "GovernanceRule",
        back_populates="created_by_user",
        foreign_keys="GovernanceRule.created_by",
        lazy="select"
    )
    
    output_templates = relationship(
        "OutputTemplate",
        back_populates="created_by_user",
        foreign_keys="OutputTemplate.created_by",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("username", "deleted_at", name="uq_user_username_deleted"),
        UniqueConstraint("email", "deleted_at", name="uq_user_email_deleted"),
        Index("idx_user_role_active", "role", "is_active"),
        Index("idx_user_last_login", "last_login"),
        Index("idx_user_created_at", "created_at"),
        {"comment": "User accounts with authentication and role-based access control"}
    )
    
    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(username='{self.username}', email='{self.email}', role='{self.role}')>"
    
    def to_dict(self, exclude_fields: list[str] | None = None) -> Dict[str, Any]:
        """
        Convert user to dictionary, excluding sensitive fields.
        
        Args:
            exclude_fields: List of field names to exclude
            
        Returns:
            Dict[str, Any]: Dictionary representation of the user
        """
        # Always exclude sensitive fields
        sensitive_fields = {"password_hash", "api_key_hash"}
        if exclude_fields:
            exclude_fields = set(exclude_fields) | sensitive_fields
        else:
            exclude_fields = sensitive_fields
        
        result = super().to_dict(exclude_fields=list(exclude_fields))
        
        # Add computed fields
        result["is_locked"] = self.is_locked
        result["has_password"] = bool(self.password_hash)
        result["has_api_key"] = bool(self.api_key_hash)
        
        return result
    
    @property
    def is_locked(self) -> bool:
        """Check if the user account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    @property
    def is_admin(self) -> bool:
        """Check if the user has admin role."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_operator(self) -> bool:
        """Check if the user has operator or higher role."""
        return self.role in {UserRole.ADMIN, UserRole.OPERATOR}
    
    @property
    def can_create_workflows(self) -> bool:
        """Check if user can create workflows."""
        return self.role in {UserRole.ADMIN, UserRole.OPERATOR}
    
    @property
    def can_manage_users(self) -> bool:
        """Check if user can manage other users."""
        return self.role == UserRole.ADMIN
    
    @property
    def can_view_audit_logs(self) -> bool:
        """Check if user can view audit logs."""
        return self.role in {UserRole.ADMIN, UserRole.OPERATOR}
    
    @property
    def can_manage_governance(self) -> bool:
        """Check if user can manage governance rules."""
        return self.role == UserRole.ADMIN
    
    def record_login(self, ip_address: str | None = None) -> None:
        """
        Record a successful login attempt.
        
        Args:
            ip_address: IP address of the login attempt
        """
        self.last_login = datetime.utcnow()
        self.last_login_ip = ip_address
        self.failed_login_attempts = "0"
        self.locked_until = None
    
    def record_failed_login(self) -> bool:
        """
        Record a failed login attempt.
        
        Returns:
            bool: True if the account should be locked
        """
        settings = get_settings()
        max_attempts = 5  # Could be configurable
        
        current_attempts = int(self.failed_login_attempts or "0")
        current_attempts += 1
        self.failed_login_attempts = str(current_attempts)
        
        # Lock account after max attempts
        if current_attempts >= max_attempts:
            lock_duration_minutes = 30  # Could be configurable
            self.locked_until = datetime.utcnow() + datetime.timedelta(minutes=lock_duration_minutes)
            return True
        
        return False
    
    def unlock_account(self) -> None:
        """Unlock the user account."""
        self.failed_login_attempts = "0"
        self.locked_until = None
    
    def change_role(self, new_role: UserRole, changed_by: uuid.UUID) -> None:
        """
        Change the user's role.
        
        Args:
            new_role: The new role to assign
            changed_by: ID of the user making the change
        """
        self.role = new_role
        self.updated_by = changed_by
        self.increment_version()
    
    def update_preferences(
        self,
        timezone: str | None = None,
        language: str | None = None,
        theme: str | None = None,
        email_notifications: bool | None = None,
        push_notifications: bool | None = None,
        updated_by: uuid.UUID | None = None
    ) -> None:
        """
        Update user preferences.
        
        Args:
            timezone: User's preferred timezone
            language: User's preferred language
            theme: User's preferred theme
            email_notifications: Email notification preference
            push_notifications: Push notification preference
            updated_by: ID of the user making the change
        """
        if timezone is not None:
            self.timezone = timezone
        if language is not None:
            self.language = language
        if theme is not None:
            self.theme = theme
        if email_notifications is not None:
            self.email_notifications = email_notifications
        if push_notifications is not None:
            self.push_notifications = push_notifications
        
        if updated_by:
            self.updated_by = updated_by
        
        self.increment_version()
