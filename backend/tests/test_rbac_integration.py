"""
Integration tests for the RBAC (Role-Based Access Control) system.

Tests the RBAC routes and functionality with the actual FastAPI application.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.database import Base, get_db
from core.rbac_models import RBACUser, RBACRole, RBACPermission, SYSTEM_PERMISSIONS, SYSTEM_ROLES
from core.rbac_service import RBACService
from core.auth import get_password_hash, create_access_token
from app.main import app


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_rbac.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Get database session for testing."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(setup_database):
    """Create test client with isolated dependency overrides."""
    # Set up the override
    app.dependency_overrides[get_db] = override_get_db
    
    # Create the test client
    test_client = TestClient(app)
    
    yield test_client
    
    # Clean up the override
    app.dependency_overrides.clear()


@pytest.fixture
def rbac_service(db_session):
    """Create RBAC service instance."""
    return RBACService(db_session)


@pytest.fixture
def setup_rbac_system(db_session, rbac_service):
    """Setup basic RBAC system with roles and permissions."""
    # Create system permissions
    for perm_key, perm_name, perm_desc in SYSTEM_PERMISSIONS[:10]:  # First 10 permissions
        resource, action = perm_key.split(":")
        perm = RBACPermission(
            key=perm_key,
            name=perm_name,
            description=perm_desc,
            resource=resource,
            action=action,
            is_active=True,
            is_system_permission=True
        )
        db_session.add(perm)
    
    # Create system roles
    for role_name, role_display, role_desc in SYSTEM_ROLES[:5]:  # First 5 roles
        role = RBACRole(
            name=role_name,
            display_name=role_display,
            description=role_desc,
            is_active=True,
            is_system_role=True
        )
        db_session.add(role)
    
    db_session.commit()
    
    # Assign permissions to admin role
    admin_role = db_session.query(RBACRole).filter(RBACRole.name == "admin").first()
    permissions = db_session.query(RBACPermission).all()
    
    for perm in permissions:
        rbac_service.assign_permission_to_role(
            role_id=admin_role.id,
            permission_id=perm.id,
            granted_by_user_id=1
        )
    
    return {"admin_role": admin_role, "permissions": permissions}


@pytest.fixture
def test_admin_user(rbac_service, setup_rbac_system):
    """Create a test admin user."""
    admin_user = rbac_service.create_user(
        username="testadmin",
        email="admin@test.com",
        password="adminpass123",
        first_name="Test",
        last_name="Admin",
        accessible_tenant_ids=[1, 2, 3],
        default_tenant_id=1
    )
    
    # Assign admin role
    admin_role = setup_rbac_system["admin_role"]
    rbac_service.assign_role_to_user(
        user_id=admin_user.id,
        role_id=admin_role.id,
        granted_by_user_id=admin_user.id
    )
    
    return admin_user


@pytest.fixture
def test_regular_user(rbac_service):
    """Create a test regular user."""
    return rbac_service.create_user(
        username="testuser",
        email="user@test.com",
        password="userpass123",
        first_name="Test",
        last_name="User",
        accessible_tenant_ids=[1],
        default_tenant_id=1
    )


@pytest.fixture
def admin_token(test_admin_user):
    """Generate JWT token for admin user."""
    return create_access_token(
        data={
            "sub": test_admin_user.username,
            "user_id": test_admin_user.id,
            "roles": ["admin"],
            "tenant_ids": test_admin_user.accessible_tenant_ids
        }
    )


@pytest.fixture
def user_token(test_regular_user):
    """Generate JWT token for regular user."""
    return create_access_token(
        data={
            "sub": test_regular_user.username,
            "user_id": test_regular_user.id,
            "roles": [],
            "tenant_ids": test_regular_user.accessible_tenant_ids
        }
    )


class TestRBACUserEndpoints:
    """Test RBAC user management endpoints."""
    
    def test_create_user(self, client, admin_token, setup_database):
        """Test creating a new user via API."""
        response = client.post(
            "/rbac/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "newuser",
                "email": "newuser@test.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "User",
                "accessible_tenant_ids": [1, 2],
                "default_tenant_id": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["first_name"] == "New"
        assert data["last_name"] == "User"
        assert data["is_active"] is True
    
    def test_list_users(self, client, admin_token, test_regular_user):
        """Test listing users with pagination."""
        response = client.get(
            "/rbac/users?page=1&page_size=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["items"]) >= 2  # At least admin and regular user
    
    def test_get_user_permissions(self, client, admin_token, test_admin_user):
        """Test getting user permissions."""
        response = client.get(
            f"/rbac/users/{test_admin_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == test_admin_user.id
        assert len(data["permissions"]) > 0
        assert "admin" in data["roles"]
    
    def test_unauthorized_access(self, client, user_token):
        """Test that regular users cannot access RBAC management."""
        response = client.get(
            "/rbac/users",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 403


class TestRBACRoleEndpoints:
    """Test RBAC role management endpoints."""
    
    def test_create_role(self, client, admin_token, setup_database):
        """Test creating a new role."""
        response = client.post(
            "/rbac/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "test_role",
                "display_name": "Test Role",
                "description": "A test role",
                "tenant_ids": [1, 2]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_role"
        assert data["display_name"] == "Test Role"
        assert data["tenant_ids"] == [1, 2]
    
    def test_list_roles(self, client, admin_token):
        """Test listing roles."""
        response = client.get(
            "/rbac/roles",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check that system roles are present
        role_names = [role["name"] for role in data]
        assert "admin" in role_names
    
    def test_assign_role_to_user(self, client, admin_token, test_regular_user, db_session):
        """Test assigning a role to a user."""
        # Get manager role
        manager_role = db_session.query(RBACRole).filter(RBACRole.name == "manager").first()
        
        response = client.post(
            "/rbac/assign-role",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": test_regular_user.id,
                "role_id": manager_role.id,
                "tenant_id": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "manager" in data["message"]


class TestRBACPermissionEndpoints:
    """Test RBAC permission management endpoints."""
    
    def test_list_permissions(self, client, admin_token, setup_database):
        """Test listing permissions."""
        response = client.get(
            "/rbac/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify permission structure
        perm = data[0]
        assert "key" in perm
        assert "name" in perm
        assert "resource" in perm
        assert "action" in perm
    
    def test_filter_permissions_by_resource(self, client, admin_token):
        """Test filtering permissions by resource."""
        response = client.get(
            "/rbac/permissions?resource=user",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned permissions should be for 'user' resource
        for perm in data:
            assert perm["resource"] == "user"
    
    def test_check_permission(self, client, admin_token, test_admin_user):
        """Test checking if a user has a specific permission."""
        response = client.post(
            "/rbac/check-permission",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": test_admin_user.id,
                "permission_key": "user:read",
                "tenant_id": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["has_permission"] is True
        assert data["permission_key"] == "user:read"


class TestRBACDirectPermissions:
    """Test direct permission grants."""
    
    def test_grant_direct_permission(self, client, admin_token, test_regular_user, setup_database):
        """Test granting a direct permission to a user."""
        response = client.post(
            "/rbac/grant-direct-permission",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": test_regular_user.id,
                "permission_key": "special:action",
                "tenant_id": 1,
                "reason": "Temporary access for special task"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "permission_id" in data
        
        # Verify the user now has this permission
        check_response = client.post(
            "/rbac/check-permission",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": test_regular_user.id,
                "permission_key": "special:action",
                "tenant_id": 1
            }
        )
        
        assert check_response.status_code == 200
        assert check_response.json()["has_permission"] is True


class TestRBACBulkOperations:
    """Test bulk operations."""
    
    def test_bulk_assign_role(self, client, admin_token, test_regular_user, db_session, setup_database):
        """Test bulk assigning a role to multiple users."""
        # Create another user
        other_user = RBACUser(
            username="otheruser",
            email="other@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            accessible_tenant_ids=[1],
            default_tenant_id=1
        )
        db_session.add(other_user)
        db_session.commit()
        
        # Get viewer role
        viewer_role = db_session.query(RBACRole).filter(RBACRole.name == "viewer").first()
        
        response = client.post(
            "/rbac/users/bulk-assign-role",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_ids": [test_regular_user.id, other_user.id],
                "role_id": viewer_role.id,
                "tenant_id": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_count"] == 2
        assert data["role_name"] == "viewer"


class TestRBACSystemInfo:
    """Test system information endpoints."""
    
    def test_get_system_info(self, client, admin_token, setup_database):
        """Test getting RBAC system information."""
        response = client.get(
            "/rbac/system-info",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "roles" in data
        assert "permissions" in data
        assert "system_version" in data
        assert data["users"] >= 2  # At least admin and regular user
        assert data["roles"] >= 5  # We created 5 system roles
        assert data["permissions"] >= 10  # We created 10 system permissions


class TestRBACErrorHandling:
    """Test error handling in RBAC endpoints."""
    
    def test_create_duplicate_user(self, client, admin_token, test_regular_user):
        """Test creating a user with duplicate username."""
        response = client.post(
            "/rbac/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": test_regular_user.username,  # Duplicate
                "email": "different@test.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_invalid_role_assignment(self, client, admin_token, test_regular_user):
        """Test assigning a non-existent role."""
        response = client.post(
            "/rbac/assign-role",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": test_regular_user.id,
                "role_id": 99999  # Non-existent
            }
        )
        
        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]
    
    def test_missing_authentication(self, client):
        """Test accessing protected endpoints without authentication."""
        response = client.get("/rbac/users")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])