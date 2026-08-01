"""
BaseLayer User Management API

User management endpoints for administrators.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import timedelta
from structlog import get_logger

from ...core.auth import (
    auth_service,
    get_current_active_user,
    require_permission,
    require_min_role,
    password_manager
)
from ...core.database import get_db_session
from ...models.user import User, UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])


class UserCreateRequest(BaseModel):
    """User creation request model."""
    email: EmailStr
    name: str
    role: UserRole
    password: str
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """User update request model."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    updated_at: datetime


class UserListResponse(BaseModel):
    """User list response model."""
    users: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> UserListResponse:
    """
    List users with pagination and filtering.
    
    Args:
        page: Page number
        size: Page size
        role: Filter by role
        is_active: Filter by active status
        search: Search by name or email
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        UserListResponse: Paginated user list
    """
    # Build query
    query = select(User)
    
    # Apply filters
    if role:
        query = query.where(User.role == role)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (User.name.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    query = query.order_by(User.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Build response
    user_responses = [
        UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            updated_at=user.updated_at
        )
        for user in users
    ]
    
    pages = (total + size - 1) // size
    
    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    """
    Get user by ID.
    
    Args:
        user_id: User ID
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        UserResponse: User information
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        updated_at=user.updated_at
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    """
    Create a new user.
    
    Args:
        user_data: User creation data
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        UserResponse: Created user information
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=password_manager.hash_password(user_data.password),
        role=user_data.role,
        is_active=user_data.is_active
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(
        "User created by admin",
        user_id=str(new_user.id),
        email=new_user.email,
        role=new_user.role.value,
        created_by=str(current_user.id)
    )
    
    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name,
        role=new_user.role.value,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        last_login_at=new_user.last_login_at,
        updated_at=new_user.updated_at
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    """
    Update user information.
    
    Args:
        user_id: User ID
        user_data: User update data
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        UserResponse: Updated user information
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deactivation
    if str(user.id) == str(current_user.id) and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Update user fields
    if user_data.name is not None:
        user.name = user_data.name
    
    if user_data.email is not None:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_uuid)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        user.email = user_data.email
    
    if user_data.role is not None:
        user.role = user_data.role
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(
        "User updated by admin",
        user_id=str(user.id),
        email=user.email,
        updated_by=str(current_user.id)
    )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        updated_at=user.updated_at
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """
    Delete a user (super admin only).
    
    Args:
        user_id: User ID
        current_user: Current authenticated user (admin)
        db: Database session

    Returns:
        Dict[str, str]: Deletion confirmation
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if str(user.id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete by deactivating
    user.is_active = False
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.warning(
        "User deleted by admin",
        user_id=str(user.id),
        email=user.email,
        deleted_by=str(current_user.id)
    )
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """
    Reset user password (admin only).
    
    Args:
        user_id: User ID
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        Dict[str, str]: Password reset confirmation
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Admins can't reset another admin's password -- only their own account
    # management flow (change-password) applies to peers at the top role.
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to reset admin passwords"
        )
    
    # Generate temporary password
    import secrets
    temp_password = secrets.token_urlsafe(12)
    
    # Update password
    user.password_hash = password_manager.hash_password(temp_password)
    user.password_changed_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.warning(
        "User password reset by admin",
        user_id=str(user.id),
        email=user.email,
        reset_by=str(current_user.id)
    )
    
    # In production, would send email with temporary password
    # For now, return it (remove this in production)
    return {
        "message": "Password reset successfully",
        "temporary_password": temp_password  # Remove this in production
    }


@router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get user activity summary.
    
    Args:
        user_id: User ID
        days: Number of days to look back
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        Dict[str, Any]: User activity summary
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # In a real implementation, would query audit logs, workflow executions, etc.
    # For now, return mock data
    activity_data = {
        "user_id": str(user.id),
        "period_days": days,
        "login_count": 15,
        "last_login": user.last_login_at.isoformat() if user.last_login_at else None,
        "workflow_executions": 42,
        "knowledge_entries_created": 8,
        "api_requests": 1250,
        "compliance_score": 95.5,
        "activity_trend": "increasing"
    }
    
    return activity_data


@router.get("/stats/summary")
async def get_user_stats(
    current_user: User = Depends(require_min_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get user statistics summary.
    
    Args:
        current_user: Current authenticated user (admin+)
        db: Database session
        
    Returns:
        Dict[str, Any]: User statistics
    """
    # Get user counts by role
    role_counts = {}
    for role in UserRole:
        result = await db.execute(
            select(func.count(User.id)).where(User.role == role)
        )
        count = result.scalar()
        role_counts[role.value] = count
    
    # Get active/inactive counts
    active_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_count = active_result.scalar()
    
    inactive_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == False)
    )
    inactive_count = inactive_result.scalar()
    
    # Get recent registrations
    recent_cutoff = datetime.utcnow() - timedelta(days=30)
    recent_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= recent_cutoff)
    )
    recent_count = recent_result.scalar()
    
    stats = {
        "total_users": sum(role_counts.values()),
        "active_users": active_count,
        "inactive_users": inactive_count,
        "recent_registrations": recent_count,
        "role_distribution": role_counts,
        "last_updated": datetime.utcnow().isoformat()
    }
    
    return stats
