# backend/modules/menu/tests/conftest.py

"""
Pytest configuration for recipe management tests.
Provides common fixtures and test setup.
"""

import pytest
from typing import Dict, Tuple, Any
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from core.auth import User
from main import app


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_db_session() -> Mock:
    """Create a mock database session"""
    session: Mock = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.flush = Mock()
    session.delete = Mock()
    return session


@pytest.fixture
def auth_headers(request: pytest.FixtureRequest) -> Tuple[Dict[str, str], User]:
    """Generate authorization headers for different user types"""
    user_type: str = getattr(request, 'param', 'chef')
    
    user_configs: Dict[str, Dict[str, Any]] = {
        'admin': {
            'id': 1,
            'email': 'admin@test.com',
            'permissions': ['menu:create', 'menu:read', 'menu:update', 'menu:delete', 
                           'admin:recipes', 'manager:recipes']
        },
        'manager': {
            'id': 2,
            'email': 'manager@test.com',
            'permissions': ['menu:create', 'menu:read', 'menu:update', 'menu:delete', 
                           'manager:recipes']
        },
        'chef': {
            'id': 3,
            'email': 'chef@test.com',
            'permissions': ['menu:create', 'menu:read', 'menu:update']
        },
        'waiter': {
            'id': 4,
            'email': 'waiter@test.com',
            'permissions': ['menu:read']
        },
        'unauthorized': {
            'id': 5,
            'email': 'unauthorized@test.com',
            'permissions': []
        }
    }
    
    config: Dict[str, Any] = user_configs.get(user_type, user_configs['chef'])
    user: User = User(**config)
    
    # Mock the auth dependency
    with patch('core.auth.get_current_user', return_value=user):
        return {"Authorization": "Bearer test-token"}, user


@pytest.fixture
def mock_recipe_service() -> Mock:
    """Create a mock recipe service"""
    service: Mock = Mock()
    
    # Setup common method returns
    service.create_recipe.return_value = Mock(id=1, name="Test Recipe")
    service.get_recipe_by_id.return_value = Mock(id=1, name="Test Recipe")
    service.update_recipe.return_value = Mock(id=1, name="Updated Recipe")
    service.delete_recipe.return_value = True
    service.search_recipes.return_value = ([], 0)
    service.recalculate_all_recipe_costs.return_value = {"updated": 10, "failed": 0}
    
    return service


@pytest.fixture(autouse=True)
def reset_mocks() -> None:
    """Reset all mocks before each test"""
    yield
    # Cleanup after test if needed


# Parametrized fixtures for testing different user types
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate test cases for different user types"""
    if "user_type" in metafunc.fixturenames:
        metafunc.parametrize("user_type", ["admin", "manager", "chef", "waiter", "unauthorized"])