"""
Test to verify that dependency overrides are properly isolated between test modules.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create two mock apps to simulate different test modules
app1 = FastAPI()
app2 = FastAPI()

# Mock database dependency
def get_db():
    pass

# Mock override functions
def override_db_1():
    return "db1"

def override_db_2():
    return "db2"


def test_dependency_isolation():
    """Test that dependency overrides don't conflict between test clients."""
    
    # First test client with its own override
    app1.dependency_overrides[get_db] = override_db_1
    client1 = TestClient(app1)
    
    # Second test client with different override
    app2.dependency_overrides[get_db] = override_db_2
    client2 = TestClient(app2)
    
    # Verify each has its own override
    assert app1.dependency_overrides[get_db] == override_db_1
    assert app2.dependency_overrides[get_db] == override_db_2
    
    # Clean up
    app1.dependency_overrides.clear()
    app2.dependency_overrides.clear()
    
    # Verify cleanup worked
    assert len(app1.dependency_overrides) == 0
    assert len(app2.dependency_overrides) == 0


def test_fixture_cleanup_pattern():
    """Test the pattern we're using in our fixtures."""
    app = FastAPI()
    
    # Simulate fixture setup
    app.dependency_overrides[get_db] = override_db_1
    assert len(app.dependency_overrides) == 1
    
    # Simulate fixture teardown
    app.dependency_overrides.clear()
    assert len(app.dependency_overrides) == 0
    
    # Simulate another fixture
    app.dependency_overrides[get_db] = override_db_2
    assert app.dependency_overrides[get_db] == override_db_2
    
    # Clean up again
    app.dependency_overrides.clear()
    assert len(app.dependency_overrides) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])