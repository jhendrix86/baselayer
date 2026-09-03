"""
BaseLayer Authentication API

JWT-based authentication endpoints for user management.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from structlog import get_logger

from ...core.auth import (
    auth_service,
    get_current_active_user,
    require_permission,
    require_min_role
)
from ...core.config import get_settings
from ...core.database import get_db_session
from ...models.user import User, UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Refresh token response model."""
    access_token: str
    token_type: str
    expires_in: int


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str
    new_password: str
    confirm_password: str


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""
    email: EmailStr


class ResetPasswordConfirmRequest(BaseModel):
    """Reset password confirmation model."""
    token: str
    new_password: str
    confirm_password: str


class RegisterRequest(BaseModel):
    """User registration request model."""
    email: EmailStr
    password: str
    confirm_password: str
    name: str
    role: UserRole = UserRole.VIEWER


class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
) -> LoginResponse:
    """
    Authenticate user and return tokens.
    
    Args:
        login_data: Login credentials
        db: Database session
        
    Returns:
        LoginResponse: Authentication tokens and user info
    """
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
            db=db
        )
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        tokens = await auth_service.create_user_tokens(user)
        
        # Build user response
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_login_at": user.last_login
        }
        
        logger.info(
            "User logged in successfully",
            user_id=str(user.id),
            email=user.email
        )
        
        return LoginResponse(
            user=user_data,
            **tokens
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Login failed",
            email=login_data.email,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session)
) -> RefreshTokenResponse:
    """
    Refresh access token using refresh token.

    Args:
        refresh_data: Refresh token data
        db: Database session

    Returns:
        RefreshTokenResponse: New access token
    """
    try:
        tokens = await auth_service.refresh_access_token(refresh_data.refresh_token, db)
        
        logger.info("Access token refreshed successfully")
        
        return RefreshTokenResponse(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Token refresh failed",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Logout user (client-side token invalidation).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, str]: Logout confirmation
    """
    logger.info(
        "User logged out",
        user_id=str(current_user.id)
    )
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserResponse: User information
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login
    )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """
    Change user password.
    
    Args:
        password_data: Password change data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dict[str, str]: Change password confirmation
    """
    # Validate password confirmation
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )
    
    # Validate password strength
    if len(password_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Change password
    success = await auth_service.change_password(
        user=current_user,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    logger.info(
        "Password changed successfully",
        user_id=str(current_user.id)
    )
    
    return {"message": "Password changed successfully"}


@router.post("/reset-password")
async def request_password_reset(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """
    Request password reset email.
    
    Args:
        reset_data: Password reset request
        db: Database session
        
    Returns:
        Dict[str, str]: Reset request confirmation
    """
    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == reset_data.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        # Don't reveal if user exists or not
        return {"message": "If an account with that email exists, a reset link has been sent"}
    
    # Generate reset token
    reset_token = auth_service.token_manager.create_password_reset_token(str(user.id))
    
    # In a real implementation, would send email with reset link
    # For now, just log the token (in production, this should be sent via email)
    logger.info(
        "Password reset requested",
        user_id=str(user.id),
        email=user.email,
        reset_token=reset_token  # Remove this in production
    )
    
    return {"message": "If an account with that email exists, a reset link has been sent"}


@router.post("/reset-password/confirm")
async def confirm_password_reset(
    reset_data: ResetPasswordConfirmRequest,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """
    Confirm password reset with token.
    
    Args:
        reset_data: Password reset confirmation
        db: Database session
        
    Returns:
        Dict[str, str]: Reset confirmation
    """
    # Validate password confirmation
    if reset_data.new_password != reset_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Validate password strength
    if len(reset_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Reset password
    success = await auth_service.reset_password(
        token=reset_data.token,
        new_password=reset_data.new_password,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    logger.info("Password reset completed successfully")
    
    return {"message": "Password reset successful"}


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: RegisterRequest,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    """
    Register a new user (admin only).

    Args:
        user_data: User registration data
        current_user: Authenticated admin performing the registration
        db: Database session

    Returns:
        UserResponse: Created user information
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password confirmation
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Validate password strength
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Create new user. User.username is a required, unique column with no
    # equivalent field on RegisterRequest - derive it from the email's
    # local part (collisions across e.g. john@gmail.com / john@yahoo.com
    # aren't handled here; there's no username-availability flow to fall
    # back to yet).
    new_user = User(
        username=user_data.email.split("@")[0],
        email=user_data.email,
        full_name=user_data.name,
        password_hash=auth_service.password_manager.hash_password(user_data.password),
        role=user_data.role,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(
        "User registered successfully",
        user_id=str(new_user.id),
        email=new_user.email,
        role=new_user.role.value
    )

    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.full_name,
        role=new_user.role.value,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        last_login_at=new_user.last_login
    )


@router.get("/permissions")
async def get_user_permissions(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get current user permissions.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: User permissions and role info
    """
    from ...core.auth import PermissionManager
    
    permissions = PermissionManager.get_role_permissions(current_user.role)
    
    return {
        "user_id": str(current_user.id),
        "role": current_user.role.value,
        "permissions": permissions,
        "role_level": PermissionManager.ROLE_HIERARCHY.get(current_user.role, 0)
    }


@router.get("/validate-token")
async def validate_token(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Validate current token and return user info.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Token validation result
    """
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
        "expires_at": datetime.utcnow() + timedelta(minutes=get_settings().access_token_expire_minutes)
    }
