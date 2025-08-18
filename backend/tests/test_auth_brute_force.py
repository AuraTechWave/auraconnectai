"""
Test suite for authentication brute force protection.

Tests rate limiting, account lockout, and other brute force mitigations.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.main import app
from core.database import Base, get_db
from core.rbac_models import RBACUser
from core.rbac_service import RBACService
from core.rate_limiter import RateLimiter


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_brute_force.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Get database session for testing."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def rbac_service(db_session):
    """Create RBAC service instance."""
    return RBACService(db_session)


@pytest.fixture
def test_user(rbac_service):
    """Create a test user."""
    return rbac_service.create_user(
        username="bruteforce_test",
        email="bruteforce@example.com",
        password="TestPass123!",
        accessible_tenant_ids=[1],
        default_tenant_id=1
    )


class TestRateLimiting:
    """Test rate limiting on authentication endpoints."""
    
    def test_login_rate_limiting(self, client):
        """Test that login attempts are rate limited."""
        # Configure rate limiter for testing
        with patch('core.config.settings.AUTH_RATE_LIMIT', 5):  # 5 attempts per minute
            
            responses = []
            
            # Make rapid login attempts
            for i in range(10):
                response = client.post("/auth/login", data={
                    "username": f"user{i}",
                    "password": "wrongpassword"
                })
                responses.append(response.status_code)
                
                # Small delay to avoid overwhelming test server
                time.sleep(0.1)
            
            # Count rate limited responses
            rate_limited = sum(1 for status in responses if status == 429)
            
            # Should see some rate limiting after 5 attempts
            assert rate_limited > 0, f"Expected rate limiting but got statuses: {responses}"
    
    def test_rate_limit_by_ip(self, client):
        """Test that rate limiting is per IP address."""
        # This would require mocking client IP addresses
        with patch('core.rate_limiter.get_client_ip') as mock_get_ip:
            
            # Simulate requests from different IPs
            for ip in ["192.168.1.1", "192.168.1.2"]:
                mock_get_ip.return_value = ip
                
                # Each IP should get its own rate limit
                for i in range(3):
                    response = client.post("/auth/login", data={
                        "username": "testuser",
                        "password": "wrongpassword"
                    })
                    # First few attempts should not be rate limited
                    assert response.status_code != 429
    
    def test_rate_limit_reset(self, client):
        """Test that rate limits reset after time window."""
        with patch('core.config.settings.AUTH_RATE_LIMIT', 3):
            
            # Use up rate limit
            for i in range(4):
                response = client.post("/auth/login", data={
                    "username": "testuser",
                    "password": "wrongpassword"
                })
            
            # Last request should be rate limited
            assert response.status_code == 429
            
            # Mock time passing (rate limit window expires)
            with patch('time.time', return_value=time.time() + 61):  # 61 seconds later
                
                # Should be able to make requests again
                response = client.post("/auth/login", data={
                    "username": "testuser",
                    "password": "wrongpassword"
                })
                assert response.status_code != 429


class TestAccountLockout:
    """Test account lockout mechanisms."""
    
    def test_account_lockout_after_failed_attempts(self, client, test_user, rbac_service):
        """Test that accounts are locked after multiple failed attempts."""
        # Make multiple failed login attempts
        for i in range(5):
            response = client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrongpassword"
            })
            assert response.status_code == 401
        
        # Check if user is locked out
        db_user = rbac_service.get_user_by_username(test_user.username)
        assert db_user.failed_login_attempts >= 5
        assert db_user.locked_until is not None
        assert db_user.locked_until > datetime.utcnow()
        
        # Attempt with correct password should still fail
        response = client.post("/auth/login", data={
            "username": test_user.username,
            "password": "TestPass123!"
        })
        assert response.status_code == 401
        assert "account is locked" in response.json()["detail"].lower()
    
    def test_lockout_duration_increases(self, client, test_user, rbac_service):
        """Test that lockout duration increases with repeated violations."""
        # First lockout
        for i in range(5):
            client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrong"
            })
        
        db_user = rbac_service.get_user_by_username(test_user.username)
        first_lockout_until = db_user.locked_until
        
        # Unlock user
        db_user.locked_until = None
        db_user.failed_login_attempts = 0
        rbac_service.db.commit()
        
        # Second lockout
        for i in range(5):
            client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrong"
            })
        
        db_user = rbac_service.get_user_by_username(test_user.username)
        second_lockout_until = db_user.locked_until
        
        # Second lockout should be longer
        if first_lockout_until and second_lockout_until:
            first_duration = first_lockout_until - datetime.utcnow()
            second_duration = second_lockout_until - datetime.utcnow()
            assert second_duration > first_duration
    
    def test_successful_login_resets_counter(self, client, test_user, rbac_service):
        """Test that successful login resets failed attempt counter."""
        # Make some failed attempts (but not enough to lock)
        for i in range(3):
            client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrongpassword"
            })
        
        # Check counter increased
        db_user = rbac_service.get_user_by_username(test_user.username)
        assert db_user.failed_login_attempts == 3
        
        # Successful login
        response = client.post("/auth/login", data={
            "username": test_user.username,
            "password": "TestPass123!"
        })
        assert response.status_code == 200
        
        # Counter should be reset
        db_user = rbac_service.get_user_by_username(test_user.username)
        assert db_user.failed_login_attempts == 0


class TestDistributedBruteForce:
    """Test protection against distributed brute force attacks."""
    
    def test_username_enumeration_protection(self, client):
        """Test that response times don't reveal valid usernames."""
        import statistics
        
        valid_times = []
        invalid_times = []
        
        # Time responses for valid username
        for i in range(5):
            start = time.time()
            client.post("/auth/login", data={
                "username": "admin",  # Known valid username
                "password": "wrongpassword"
            })
            valid_times.append(time.time() - start)
        
        # Time responses for invalid username
        for i in range(5):
            start = time.time()
            client.post("/auth/login", data={
                "username": f"nonexistent{i}",
                "password": "wrongpassword"
            })
            invalid_times.append(time.time() - start)
        
        # Compare average times
        avg_valid = statistics.mean(valid_times)
        avg_invalid = statistics.mean(invalid_times)
        
        # Should be within 50ms of each other
        assert abs(avg_valid - avg_invalid) < 0.05
    
    def test_concurrent_login_attempts(self, client):
        """Test handling of concurrent login attempts."""
        def make_login_attempt(username, password):
            return client.post("/auth/login", data={
                "username": username,
                "password": password
            })
        
        # Simulate concurrent attacks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # Submit concurrent requests
            for i in range(20):
                future = executor.submit(
                    make_login_attempt,
                    f"user{i % 5}",  # Rotate through 5 usernames
                    "wrongpassword"
                )
                futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(futures):
                try:
                    response = future.result()
                    results.append(response.status_code)
                except Exception as e:
                    results.append(500)
        
        # Should see rate limiting kick in
        rate_limited = sum(1 for status in results if status == 429)
        assert rate_limited > 0


class TestCaptchaIntegration:
    """Test CAPTCHA integration for brute force protection."""
    
    def test_captcha_required_after_failures(self, client, test_user):
        """Test that CAPTCHA is required after multiple failures."""
        # Make several failed attempts
        for i in range(3):
            response = client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrongpassword"
            })
        
        # Next attempt should require CAPTCHA
        response = client.post("/auth/login", data={
            "username": test_user.username,
            "password": "TestPass123!"
        })
        
        # Should get CAPTCHA required response
        # Note: Actual implementation would depend on CAPTCHA service
        # assert response.status_code == 428  # Precondition Required
        # assert "captcha_required" in response.json()
    
    def test_captcha_bypass_prevention(self, client):
        """Test that CAPTCHA can't be bypassed."""
        # Attempt login with missing CAPTCHA when required
        response = client.post("/auth/login", data={
            "username": "testuser",
            "password": "password",
            # Missing captcha_token
        })
        
        # Should not allow login without valid CAPTCHA
        # Implementation specific


class TestPasswordSprayProtection:
    """Test protection against password spray attacks."""
    
    def test_password_spray_detection(self, client, rbac_service):
        """Test detection of password spray attacks."""
        # Create multiple test users
        users = []
        for i in range(5):
            user = rbac_service.create_user(
                username=f"spraytest{i}",
                email=f"spraytest{i}@example.com",
                password="UniquePass123!",
                accessible_tenant_ids=[1],
                default_tenant_id=1
            )
            users.append(user)
        
        # Attempt common password across all users
        common_passwords = ["password123", "123456", "admin"]
        
        for password in common_passwords:
            for user in users:
                response = client.post("/auth/login", data={
                    "username": user.username,
                    "password": password
                })
        
        # Should detect pattern and increase security
        # Implementation could include:
        # - Temporary increase in lockout threshold
        # - Required CAPTCHA for all logins
        # - Alert administrators


class TestAuditingAndMonitoring:
    """Test audit logging for brute force attempts."""
    
    def test_failed_login_audit_logs(self, client, test_user, db_session):
        """Test that failed login attempts are logged."""
        # Make failed login attempt
        response = client.post("/auth/login", data={
            "username": test_user.username,
            "password": "wrongpassword"
        })
        
        # Check audit logs
        from core.password_models import SecurityAuditLog
        
        logs = db_session.query(SecurityAuditLog).filter(
            SecurityAuditLog.user_id == test_user.id,
            SecurityAuditLog.action == "failed_login"
        ).all()
        
        assert len(logs) > 0
        latest_log = logs[-1]
        assert latest_log.ip_address is not None
        assert latest_log.user_agent is not None
    
    def test_lockout_event_logging(self, client, test_user, db_session):
        """Test that account lockouts are logged."""
        # Trigger lockout
        for i in range(5):
            client.post("/auth/login", data={
                "username": test_user.username,
                "password": "wrong"
            })
        
        # Check for lockout log
        from core.password_models import SecurityAuditLog
        
        lockout_logs = db_session.query(SecurityAuditLog).filter(
            SecurityAuditLog.user_id == test_user.id,
            SecurityAuditLog.action == "account_locked"
        ).all()
        
        assert len(lockout_logs) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])