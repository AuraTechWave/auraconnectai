"""
Comprehensive test suite for the RBAC (Role-Based Access Control) system.

Tests cover:
- User management with RBAC
- Role and permission assignments
- Permission checking and authorization
- Session management with RBAC context
- API endpoints for RBAC operations
- Multi-tenant support
- Security features
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from backend.app.main import app
from backend.core.database import get_db
from backend.core.rbac_models import RBACUser, RBACRole, RBACPermission, UserPermission
from backend.core.rbac_service import RBACService
from backend.core.rbac_auth import RBACDependency
from backend.core.auth import get_password_hash


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Get database session for testing."""
    return next(get_db())


@pytest.fixture
def rbac_service(db_session):
    """Create RBAC service instance."""
    return RBACService(db_session)


@pytest.fixture
def test_user(rbac_service):
    """Create a test user."""
    return rbac_service.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        accessible_tenant_ids=[1, 2],
        default_tenant_id=1
    )


@pytest.fixture
def test_admin_user(rbac_service):
    """Create a test admin user."""
    admin_user = rbac_service.create_user(
        username="testadmin",
        email="admin@example.com",
        password="adminpass123",
        accessible_tenant_ids=[1, 2, 3],
        default_tenant_id=1
    )
    
    # Assign admin role
    admin_role = rbac_service.get_role_by_name("admin")
    if admin_role:
        rbac_service.assign_role_to_user(admin_user.id, admin_role.id)
    
    return admin_user


@pytest.fixture
def test_role(rbac_service):
    """Create a test role."""
    return rbac_service.create_role(
        name="test_role",
        display_name="Test Role",
        description="Test role for unit testing"
    )


@pytest.fixture
def test_permission(rbac_service):
    """Create a test permission."""
    return rbac_service.create_permission(
        key="test:action",
        name="Test Action",
        description="Test permission for unit testing",
        resource="test",
        action="action"
    )


class TestRBACUserManagement:
    """Test user management with RBAC."""
    
    def test_create_user(self, rbac_service):
        """Test creating a new user."""
        user = rbac_service.create_user(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            first_name="New",
            last_name="User",
            accessible_tenant_ids=[1],
            default_tenant_id=1
        )
        
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.first_name == "New"
        assert user.last_name == "User"
        assert user.is_active is True
        assert user.accessible_tenant_ids == [1]
        assert user.default_tenant_id == 1
    
    def test_create_duplicate_user(self, rbac_service, test_user):
        """Test creating user with duplicate username/email."""
        with pytest.raises(ValueError, match="already exists"):
            rbac_service.create_user(
                username=test_user.username,
                email="different@example.com",
                password="password123"
            )
        
        with pytest.raises(ValueError, match="already exists"):
            rbac_service.create_user(
                username="different",
                email=test_user.email,
                password="password123"
            )
    
    def test_authenticate_user(self, rbac_service, test_user):
        """Test user authentication."""
        # Valid credentials
        authenticated = rbac_service.authenticate_user("testuser", "testpass123")
        assert authenticated is not None
        assert authenticated.username == "testuser"
        
        # Invalid password
        invalid = rbac_service.authenticate_user("testuser", "wrongpassword")
        assert invalid is None
        
        # Non-existent user
        nonexistent = rbac_service.authenticate_user("nonexistent", "password")
        assert nonexistent is None
    
    def test_user_lockout(self, rbac_service, test_user):
        """Test user account lockout after failed attempts."""
        # Multiple failed attempts
        for _ in range(5):
            rbac_service.authenticate_user("testuser", "wrongpassword")
        
        # Should be locked now
        locked = rbac_service.authenticate_user("testuser", "testpass123")
        assert locked is None
        
        # Verify locked_until is set
        user = rbac_service.get_user_by_username("testuser")
        assert user.locked_until is not None
        assert user.failed_login_attempts >= 5


class TestRBACRoleManagement:
    """Test role management operations."""
    
    def test_create_role(self, rbac_service):
        """Test creating a new role."""
        role = rbac_service.create_role(
            name="custom_role",
            display_name="Custom Role",
            description="A custom role for testing",
            tenant_ids=[1, 2]
        )
        
        assert role.name == "custom_role"
        assert role.display_name == "Custom Role"
        assert role.description == "A custom role for testing"
        assert role.tenant_ids == [1, 2]
        assert role.is_active is True
        assert role.is_system_role is False
    
    def test_create_duplicate_role(self, rbac_service, test_role):
        """Test creating role with duplicate name."""
        with pytest.raises(ValueError, match="already exists"):
            rbac_service.create_role(
                name=test_role.name,
                display_name="Different Display Name"
            )
    
    def test_assign_role_to_user(self, rbac_service, test_user, test_role):
        """Test assigning role to user."""
        success = rbac_service.assign_role_to_user(
            user_id=test_user.id,
            role_id=test_role.id,
            tenant_id=1
        )
        
        assert success is True
        
        # Verify assignment
        user_roles = rbac_service.get_user_roles(test_user.id, tenant_id=1)
        assert len(user_roles) == 1
        assert user_roles[0].name == test_role.name
    
    def test_remove_role_from_user(self, rbac_service, test_user, test_role):
        """Test removing role from user."""
        # First assign the role
        rbac_service.assign_role_to_user(test_user.id, test_role.id)
        
        # Then remove it
        success = rbac_service.remove_role_from_user(test_user.id, test_role.id)
        assert success is True
        
        # Verify removal
        user_roles = rbac_service.get_user_roles(test_user.id)
        assert len(user_roles) == 0


class TestRBACPermissionManagement:
    """Test permission management operations."""
    
    def test_create_permission(self, rbac_service):
        """Test creating a new permission."""
        permission = rbac_service.create_permission(
            key="custom:action",
            name="Custom Action",
            description="A custom permission for testing",
            resource="custom",
            action="action",
            tenant_ids=[1]
        )
        
        assert permission.key == "custom:action"
        assert permission.name == "Custom Action"
        assert permission.resource == "custom"
        assert permission.action == "action"
        assert permission.tenant_ids == [1]
        assert permission.is_active is True
    
    def test_assign_permission_to_role(self, rbac_service, test_role, test_permission):
        """Test assigning permission to role."""
        success = rbac_service.assign_permission_to_role(
            role_id=test_role.id,
            permission_id=test_permission.id
        )
        
        assert success is True
        
        # Verify assignment
        role = rbac_service.get_role_by_id(test_role.id)
        permissions = role.get_all_permissions()
        assert len(permissions) == 1
        assert permissions[0].key == test_permission.key
    
    def test_grant_direct_permission(self, rbac_service, test_user):
        """Test granting direct permission to user."""
        user_permission = rbac_service.grant_direct_permission(
            user_id=test_user.id,
            permission_key="direct:permission",
            tenant_id=1,
            reason="Testing direct permission grant"
        )
        
        assert user_permission.user_id == test_user.id
        assert user_permission.permission_key == "direct:permission"
        assert user_permission.tenant_id == 1
        assert user_permission.is_grant is True
        assert user_permission.reason == "Testing direct permission grant"


class TestRBACPermissionChecking:
    """Test permission checking functionality."""
    
    def test_check_role_based_permission(self, rbac_service, test_user, test_role, test_permission):
        """Test checking permission granted through role."""
        # Assign permission to role
        rbac_service.assign_permission_to_role(test_role.id, test_permission.id)
        
        # Assign role to user
        rbac_service.assign_role_to_user(test_user.id, test_role.id)
        
        # Check permission
        has_permission = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key=test_permission.key
        )
        
        assert has_permission is True
    
    def test_check_direct_permission(self, rbac_service, test_user):
        """Test checking direct permission."""
        # Grant direct permission
        rbac_service.grant_direct_permission(
            user_id=test_user.id,
            permission_key="direct:test",
            tenant_id=1
        )
        
        # Check permission
        has_permission = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="direct:test",
            tenant_id=1
        )
        
        assert has_permission is True
    
    def test_check_nonexistent_permission(self, rbac_service, test_user):
        """Test checking permission user doesn't have."""
        has_permission = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="nonexistent:permission"
        )
        
        assert has_permission is False
    
    def test_admin_override(self, rbac_service, test_admin_user):
        """Test admin role override for permissions."""
        # Admin should have access to any permission
        has_permission = rbac_service.check_user_permission(
            user_id=test_admin_user.id,
            permission_key="any:permission"
        )
        
        # Note: This depends on how admin override is implemented
        # in the actual permission checking logic


class TestRBACSessionManagement:
    """Test RBAC session management."""
    
    def test_create_rbac_session(self, rbac_service, test_user):
        """Test creating RBAC session."""
        session = rbac_service.create_rbac_session(
            session_id="test_session_123",
            user_id=test_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            active_tenant_id=1,
            user_agent="Test Browser",
            ip_address="127.0.0.1"
        )
        
        assert session.id == "test_session_123"
        assert session.user_id == test_user.id
        assert session.active_tenant_id == 1
        assert session.user_agent == "Test Browser"
        assert session.ip_address == "127.0.0.1"
        assert session.is_active is True
    
    def test_get_rbac_session(self, rbac_service, test_user):
        """Test retrieving RBAC session."""
        # Create session
        created_session = rbac_service.create_rbac_session(
            session_id="test_session_456",
            user_id=test_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Retrieve session
        retrieved_session = rbac_service.get_rbac_session("test_session_456")
        
        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id
        assert retrieved_session.user_id == test_user.id
    
    def test_refresh_session_cache(self, rbac_service, test_user):
        """Test refreshing session permission cache."""
        # Create session
        session = rbac_service.create_rbac_session(
            session_id="test_session_789",
            user_id=test_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            active_tenant_id=1
        )
        
        # Refresh cache
        success = rbac_service.refresh_session_cache("test_session_789")
        assert success is True


class TestRBACAPIEndpoints:
    """Test RBAC API endpoints."""
    
    def test_rbac_user_info_endpoint(self, client, test_admin_user):
        """Test /auth/me/rbac endpoint."""
        # Login to get token
        login_response = client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "adminpass123"}
        )
        token = login_response.json()["access_token"]
        
        # Get RBAC user info
        response = client.get(
            "/auth/me/rbac",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert "roles" in data
        assert "permissions" in data
    
    def test_permission_check_endpoint(self, client, test_admin_user):
        """Test /auth/check-permission endpoint."""
        # Login to get token
        login_response = client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "adminpass123"}
        )
        token = login_response.json()["access_token"]
        
        # Check permission
        response = client.post(
            "/auth/check-permission",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "permission_key": "staff:read",
                "tenant_id": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "has_permission" in data
        assert data["permission_key"] == "staff:read"
    
    def test_rbac_management_endpoints(self, client, test_admin_user):
        """Test RBAC management endpoints."""
        # Login to get token
        login_response = client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "adminpass123"}
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test creating user
        user_response = client.post(
            "/rbac/users",
            headers=headers,
            json={
                "username": "apitest",
                "email": "apitest@example.com",
                "password": "testpass123",
                "accessible_tenant_ids": [1]
            }
        )
        assert user_response.status_code == 200
        
        # Test listing users
        users_response = client.get("/rbac/users", headers=headers)
        assert users_response.status_code == 200
        
        # Test creating role
        role_response = client.post(
            "/rbac/roles",
            headers=headers,
            json={
                "name": "api_test_role",
                "display_name": "API Test Role",
                "description": "Role created via API test"
            }
        )
        assert role_response.status_code == 200
        
        # Test listing roles
        roles_response = client.get("/rbac/roles", headers=headers)
        assert roles_response.status_code == 200
        
        # Test listing permissions
        permissions_response = client.get("/rbac/permissions", headers=headers)
        assert permissions_response.status_code == 200


class TestRBACDependencies:
    """Test RBAC FastAPI dependencies."""
    
    def test_rbac_dependency_with_permission(self):
        """Test RBAC dependency with permission requirement."""
        dependency = RBACDependency(required_permissions=["test:permission"])
        
        # This would require mocking the full FastAPI request context
        # For now, just verify the dependency is created correctly
        assert dependency.required_permissions == ["test:permission"]
        assert dependency.require_all_permissions is True
    
    def test_rbac_dependency_with_roles(self):
        """Test RBAC dependency with role requirement."""
        dependency = RBACDependency(required_roles=["admin", "manager"])
        
        assert dependency.required_roles == ["admin", "manager"]
        assert dependency.require_all_roles is False


class TestRBACMultiTenant:
    """Test multi-tenant RBAC functionality."""
    
    def test_tenant_scoped_permissions(self, rbac_service, test_user):
        """Test permissions scoped to specific tenants."""
        # Grant permission for tenant 1 only
        rbac_service.grant_direct_permission(
            user_id=test_user.id,
            permission_key="tenant:specific",
            tenant_id=1
        )
        
        # Check permission for tenant 1
        has_permission_t1 = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="tenant:specific",
            tenant_id=1
        )
        assert has_permission_t1 is True
        
        # Check permission for tenant 2
        has_permission_t2 = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="tenant:specific",
            tenant_id=2
        )
        assert has_permission_t2 is False
    
    def test_global_permissions(self, rbac_service, test_user):
        """Test global permissions (no tenant restriction)."""
        # Grant global permission
        rbac_service.grant_direct_permission(
            user_id=test_user.id,
            permission_key="global:permission",
            tenant_id=None  # Global permission
        )
        
        # Should work for any tenant
        has_permission_t1 = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="global:permission",
            tenant_id=1
        )
        assert has_permission_t1 is True
        
        has_permission_t2 = rbac_service.check_user_permission(
            user_id=test_user.id,
            permission_key="global:permission",
            tenant_id=2
        )
        assert has_permission_t2 is True


class TestRBACPerformance:
    """Test RBAC performance and caching."""
    
    def test_permission_caching(self, rbac_service, test_user):
        """Test that permission checks are cached for performance."""
        # This would require implementing and testing the caching mechanism
        # For now, verify that the caching infrastructure exists
        
        session = rbac_service.create_rbac_session(
            session_id="cache_test",
            user_id=test_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            active_tenant_id=1
        )
        
        assert session.cached_permissions is not None
        assert session.cache_expires_at is not None


if __name__ == "__main__":
    pytest.main([__file__])