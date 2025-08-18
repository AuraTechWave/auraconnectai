"""
Test configuration for health monitoring tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_db
from app.main import app
from modules.auth.services import create_access_token


@pytest.fixture(scope="module")
def test_db():
    """Create a test database"""
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test_health.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestingSessionLocal()
    
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def admin_token():
    """Create an admin token for testing"""
    # Create a token with admin permissions
    token_data = {
        "sub": "1",  # Admin user ID
        "username": "admin",
        "scopes": ["admin"],
        "permissions": ["system.admin", "settings.view", "settings.manage"]
    }
    
    return create_access_token(data=token_data)


@pytest.fixture
def db(test_db):
    """Get database session"""
    return test_db