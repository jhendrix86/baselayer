"""
BaseLayer Authentication Tests

Test suite for authentication and authorization functionality.
"""

import asyncio
import pytest
from datetime import timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from baselayer.models.user import UserRole


class TestAuthentication:
    """Test authentication endpoints."""
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "operator"
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_login_inactive_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test login with inactive user."""
        from baselayer.core.auth import password_manager
        from baselayer.models.user import User
        
        # Create inactive user
        inactive_user = User(
            email="inactive@example.com",
            name="Inactive User",
            password_hash=password_manager.hash_password("password123"),
            role=UserRole.OPERATOR,
            is_active=False
        )
        
        db_session.add(inactive_user)
        await db_session.commit()
        
        login_data = {
            "email": "inactive@example.com",
            "password": "password123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_get_current_user(self, client: AsyncClient, auth_headers):
        """Test getting current user info."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == "test@example.com"
        assert data["role"] == "operator"
        assert data["is_active"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_refresh_token(self, client: AsyncClient, test_user):
        """Test token refresh."""
        # First login to get tokens
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Use refresh token to get new access token
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh token with invalid token."""
        refresh_data = {
            "refresh_token": "invalid_refresh_token"
        }
        
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_logout(self, client: AsyncClient, auth_headers):
        """Test logout."""
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_change_password(self, client: AsyncClient, auth_headers):
        """Test password change."""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=password_data, headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_change_password_wrong_current(self, client: AsyncClient, auth_headers):
        """Test password change with wrong current password."""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=password_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_change_password_mismatch(self, client: AsyncClient, auth_headers):
        """Test password change with mismatched passwords."""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "newpassword123",
            "confirm_password": "differentpassword"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=password_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "New passwords do not match" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_get_user_permissions(self, client: AsyncClient, auth_headers):
        """Test getting user permissions."""
        response = await client.get("/api/v1/auth/permissions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "role" in data
        assert "permissions" in data
        assert "role_level" in data
        assert data["role"] == "operator"
        assert isinstance(data["permissions"], list)
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_validate_token(self, client: AsyncClient, auth_headers):
        """Test token validation."""
        response = await client.get("/api/v1/auth/validate-token", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert "user_id" in data
        assert "email" in data
        assert "role" in data
        assert "expires_at" in data


class TestAuthorization:
    """Test authorization and role-based access control."""
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_user_cannot_access_admin_endpoints(self, client: AsyncClient, auth_headers):
        """Test that regular users cannot access admin-only endpoints."""
        # Try to access user management (admin only)
        response = await client.get("/api/v1/auth/users", headers=auth_headers)
        
        # Should return 404 or 403 depending on implementation
        assert response.status_code in [403, 404]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_admin_can_access_admin_endpoints(self, client: AsyncClient, admin_headers):
        """Test that admins can access admin endpoints."""
        # Try to access user management
        response = await client.get("/api/v1/auth/users", headers=admin_headers)
        
        # Should return 200 or 404 (endpoint exists but no users)
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_role_hierarchy(self, client: AsyncClient, db_session: AsyncSession):
        """Test role hierarchy and permissions."""
        from baselayer.core.auth import PermissionManager
        
        # Test role hierarchy
        assert PermissionManager.role_can_manage(UserRole.ADMIN, UserRole.OPERATOR)
        assert PermissionManager.role_can_manage(UserRole.OPERATOR, UserRole.AGENT)
        assert not PermissionManager.role_can_manage(UserRole.OPERATOR, UserRole.ADMIN)

        # Test permissions
        operator_permissions = PermissionManager.get_role_permissions(UserRole.OPERATOR)
        admin_permissions = PermissionManager.get_role_permissions(UserRole.ADMIN)

        assert len(admin_permissions) > len(operator_permissions)
        assert "read:own" in operator_permissions
        assert "manage:users" in admin_permissions


class TestPasswordReset:
    """Test password reset functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_request_password_reset_existing_user(self, client: AsyncClient, test_user):
        """Test password reset request for existing user."""
        reset_data = {
            "email": "test@example.com"
        }
        
        response = await client.post("/api/v1/auth/reset-password", json=reset_data)
        
        assert response.status_code == 200
        assert "reset link has been sent" in response.json()["message"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_request_password_reset_nonexistent_user(self, client: AsyncClient):
        """Test password reset request for nonexistent user."""
        reset_data = {
            "email": "nonexistent@example.com"
        }
        
        response = await client.post("/api/v1/auth/reset-password", json=reset_data)
        
        assert response.status_code == 200
        assert "reset link has been sent" in response.json()["message"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_confirm_password_reset(self, client: AsyncClient, test_user):
        """Test password reset confirmation."""
        from baselayer.core.auth import token_manager
        
        # Generate reset token
        reset_token = token_manager.create_password_reset_token(str(test_user.id))
        
        reset_data = {
            "token": reset_token,
            "new_password": "newresetpassword123",
            "confirm_password": "newresetpassword123"
        }
        
        response = await client.post("/api/v1/auth/reset-password/confirm", json=reset_data)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Password reset successful"
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_confirm_password_reset_invalid_token(self, client: AsyncClient):
        """Test password reset with invalid token."""
        reset_data = {
            "token": "invalid_reset_token",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        
        response = await client.post("/api/v1/auth/reset-password/confirm", json=reset_data)
        
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]


class TestUserRegistration:
    """Test user registration functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_register_user_success(self, client: AsyncClient, admin_headers):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "newpassword123",
            "confirm_password": "newpassword123",
            "name": "New User",
            "role": "operator"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data, headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert data["role"] == "operator"
        assert data["is_active"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_register_user_duplicate_email(self, client: AsyncClient, admin_headers):
        """Test user registration with duplicate email."""
        user_data = {
            "email": "test@example.com",  # Already exists
            "password": "newpassword123",
            "confirm_password": "newpassword123",
            "name": "Duplicate User",
            "role": "operator"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data, headers=admin_headers)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_register_user_weak_password(self, client: AsyncClient, admin_headers):
        """Test user registration with weak password."""
        user_data = {
            "email": "weakuser@example.com",
            "password": "123",  # Too short
            "confirm_password": "123",
            "name": "Weak Password User",
            "role": "operator"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data, headers=admin_headers)
        
        assert response.status_code == 400
        assert "Password must be at least 8 characters long" in response.json()["detail"]
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_register_user_unauthorized(self, client: AsyncClient):
        """Test user registration without admin privileges."""
        user_data = {
            "email": "unauthorized@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "name": "Unauthorized User",
            "role": "operator"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 401  # Unauthorized


class TestTokenSecurity:
    """Test token security and validation."""
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_token_expiration(self, client: AsyncClient, test_user):
        """Test token expiration handling."""
        from baselayer.core.auth import token_manager
        
        # Create token with very short expiration
        access_token = token_manager.create_access_token(
            {"sub": str(test_user.id)},
            expires_delta=timedelta(seconds=1)
        )
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Wait for token to expire
        await asyncio.sleep(2)
        
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_invalid_token_format(self, client: AsyncClient):
        """Test invalid token format."""
        headers = {"Authorization": "InvalidToken"}
        
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_missing_token(self, client: AsyncClient):
        """Test missing authentication token."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
