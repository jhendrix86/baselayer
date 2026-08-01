"""
BaseLayer Authentication & Authorization System

JWT-based authentication with role-based access control (RBAC)
for the BaseLayer multi-agent system.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from .config import get_settings
from .database import get_db_session
from ..models.user import User, UserRole

logger = get_logger(__name__)

# Security configuration
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Get settings
settings = get_settings()


class AuthenticationError(Exception):
    """Authentication related errors."""
    pass


class AuthorizationError(Exception):
    """Authorization related errors."""
    pass


class TokenManager:
    """JWT token management."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                raise AuthenticationError(f"Invalid token type: expected {token_type}")
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None or datetime.utcnow().timestamp() > exp:
                raise AuthenticationError("Token has expired")
            
            return payload
            
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
    
    def create_password_reset_token(self, user_id: str) -> str:
        """Create password reset token."""
        data = {
            "sub": user_id,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        return jwt.encode(data, self.secret_key, algorithm=self.algorithm)
    
    def verify_password_reset_token(self, token: str) -> str:
        """Verify password reset token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != "password_reset":
                raise AuthenticationError("Invalid reset token type")
            
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid reset token")
            
            return user_id
            
        except JWTError as e:
            raise AuthenticationError(f"Invalid reset token: {str(e)}")


class PasswordManager:
    """Password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)


class PermissionManager:
    """Permission and role management."""
    
    # Role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        UserRole.GUEST: 0,
        UserRole.USER: 1,
        UserRole.ADMIN: 2,
        UserRole.SUPER_ADMIN: 3,
        UserRole.SYSTEM: 4
    }
    
    # Default permissions for each role
    DEFAULT_PERMISSIONS = {
        UserRole.GUEST: [
            "read:public",
            "read:own_profile"
        ],
        UserRole.USER: [
            "read:own",
            "write:own",
            "read:shared",
            "create:workflows",
            "execute:workflows",
            "read:knowledge",
            "create:knowledge"
        ],
        UserRole.ADMIN: [
            "read:all",
            "write:all",
            "delete:all",
            "manage:users",
            "manage:workflows",
            "manage:agents",
            "manage:system"
        ],
        UserRole.SUPER_ADMIN: [
            "read:all",
            "write:all",
            "delete:all",
            "manage:users",
            "manage:roles",
            "manage:system",
            "manage:governance",
            "manage:infrastructure"
        ],
        UserRole.SYSTEM: [
            "read:all",
            "write:all",
            "delete:all",
            "manage:everything"
        ]
    }
    
    @staticmethod
    def has_permission(user_role: UserRole, required_permission: str) -> bool:
        """Check if user role has the required permission."""
        role_permissions = PermissionManager.DEFAULT_PERMISSIONS.get(user_role, [])
        return required_permission in role_permissions
    
    @staticmethod
    def can_access_resource(
        user_role: UserRole,
        resource_type: str,
        action: str,
        resource_owner_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if user can access a specific resource."""
        # Build permission string
        permission = f"{action}:{resource_type}"
        
        # Check for specific permissions
        if PermissionManager.has_permission(user_role, permission):
            return True
        
        # Check for wildcard permissions
        wildcard_permission = f"{action}:*"
        if PermissionManager.has_permission(user_role, wildcard_permission):
            return True
        
        # Check for own resource access
        if resource_owner_id and user_id and resource_owner_id == user_id:
            own_permission = f"{action}:own"
            return PermissionManager.has_permission(user_role, own_permission)
        
        return False
    
    @staticmethod
    def get_role_permissions(role: UserRole) -> List[str]:
        """Get all permissions for a role."""
        return PermissionManager.DEFAULT_PERMISSIONS.get(role, [])
    
    @staticmethod
    def role_can_manage(manager_role: UserRole, target_role: UserRole) -> bool:
        """Check if manager role can manage target role."""
        manager_level = PermissionManager.ROLE_HIERARCHY.get(manager_role, 0)
        target_level = PermissionManager.ROLE_HIERARCHY.get(target_role, 0)
        
        return manager_level > target_level


# Global instances
token_manager = TokenManager()
password_manager = PasswordManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Get current authenticated user."""
    try:
        # Verify token
        payload = token_manager.verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        # Get user from database
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_permission(permission: str):
    """Decorator to require specific permission."""
    def permission_checker(current_user: User = Depends(get_current_active_user)):
        if not PermissionManager.has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return current_user
    
    return permission_checker


def require_role(role: UserRole):
    """Decorator to require specific role."""
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role.value}"
            )
        return current_user
    
    return role_checker


def require_min_role(min_role: UserRole):
    """Decorator to require minimum role level."""
    def role_checker(current_user: User = Depends(get_current_active_user)):
        user_level = PermissionManager.ROLE_HIERARCHY.get(current_user.role, 0)
        required_level = PermissionManager.ROLE_HIERARCHY.get(min_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role level. Required: {min_role.value}"
            )
        return current_user
    
    return role_checker


class AuthenticationService:
    """Authentication service for user management."""
    
    def __init__(self):
        self.token_manager = token_manager
        self.password_manager = password_manager
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        db: AsyncSession
    ) -> Optional[User]:
        """Authenticate user with email and password."""
        try:
            # Get user by email
            result = await db.execute(
                select(User).where(User.email == email, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return None
            
            # Verify password
            if not self.password_manager.verify_password(password, user.password_hash):
                return None
            
            # Update last login
            user.last_login_at = datetime.utcnow()
            await db.commit()
            
            return user
            
        except Exception as e:
            logger.error(
                "User authentication failed",
                email=email,
                error=str(e)
            )
            return None
    
    async def create_user_tokens(self, user: User) -> Dict[str, Any]:
        """Create access and refresh tokens for user."""
        # Create access token
        access_token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "name": user.name
        }
        access_token = self.token_manager.create_access_token(access_token_data)
        
        # Create refresh token
        refresh_token_data = {
            "sub": str(user.id)
        }
        refresh_token = self.token_manager.create_refresh_token(refresh_token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.token_manager.access_token_expire_minutes * 60
        }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Create new access token from refresh token."""
        try:
            # Verify refresh token
            payload = self.token_manager.verify_token(refresh_token, "refresh")
            user_id = payload.get("sub")
            
            if user_id is None:
                raise AuthenticationError("Invalid refresh token")
            
            # Get user from database
            async with get_db_session() as db:
                result = await db.execute(
                    select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)
                )
                user = result.scalar_one_or_none()
                
                if user is None:
                    raise AuthenticationError("User not found or inactive")
                
                # Create new access token
                access_token_data = {
                    "sub": str(user.id),
                    "email": user.email,
                    "role": user.role.value,
                    "name": user.name
                }
                access_token = self.token_manager.create_access_token(access_token_data)
                
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": self.token_manager.access_token_expire_minutes * 60
                }
                
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
    
    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        db: AsyncSession
    ) -> bool:
        """Change user password."""
        try:
            # Verify current password
            if not self.password_manager.verify_password(current_password, user.password_hash):
                return False
            
            # Hash new password
            new_password_hash = self.password_manager.hash_password(new_password)
            
            # Update user
            user.password_hash = new_password_hash
            user.password_changed_at = datetime.utcnow()
            await db.commit()
            
            logger.info(
                "Password changed successfully",
                user_id=str(user.id)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Password change failed",
                user_id=str(user.id),
                error=str(e)
            )
            return False
    
    async def reset_password(
        self,
        token: str,
        new_password: str,
        db: AsyncSession
    ) -> bool:
        """Reset password using reset token."""
        try:
            # Verify reset token
            user_id = self.token_manager.verify_password_reset_token(token)
            
            # Get user
            result = await db.execute(
                select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                return False
            
            # Update password
            user.password_hash = self.password_manager.hash_password(new_password)
            user.password_changed_at = datetime.utcnow()
            await db.commit()
            
            logger.info(
                "Password reset successful",
                user_id=str(user.id)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Password reset failed",
                error=str(e)
            )
            return False


# Global authentication service instance
auth_service = AuthenticationService()
