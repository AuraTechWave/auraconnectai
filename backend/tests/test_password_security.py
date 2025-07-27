"""
Comprehensive tests for password security system.

Tests password hashing, validation, reset workflow, and security features.
"""

import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.password_security import (
    EnhancedPasswordSecurity,
    PasswordStrength,
    PasswordValidationResult,
    password_security,
    validate_email_address
)
from backend.core.password_models import PasswordResetToken, PasswordHistory, SecurityAuditLog
from backend.core.rbac_models import RBACUser
from backend.app.main import app


client = TestClient(app)


class TestEnhancedPasswordSecurity:
    """Test the enhanced password security system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.password_security = EnhancedPasswordSecurity()
    
    def test_password_hashing_bcrypt(self):
        """Test password hashing with bcrypt."""
        password = "test_password_123!"
        hashed = self.password_security.hash_password(password, algorithm="bcrypt")
        
        assert hashed.startswith("$2b$")
        assert self.password_security.verify_password(password, hashed)
        assert not self.password_security.verify_password("wrong_password", hashed)
    
    @pytest.mark.skipif(not hasattr(password_security.pwd_context, "argon2"), 
                       reason="Argon2 not available")
    def test_password_hashing_argon2(self):
        """Test password hashing with Argon2."""
        password = "test_password_123!"
        hashed = self.password_security.hash_password(password, algorithm="argon2")
        
        assert hashed.startswith("$argon2")
        assert self.password_security.verify_password(password, hashed)
        assert not self.password_security.verify_password("wrong_password", hashed)
    
    def test_password_needs_rehash(self):
        """Test password rehash detection."""
        # Create a weak hash (simulated old algorithm)
        weak_hash = "$2b$04$" + "x" * 50  # Low rounds
        assert self.password_security.needs_rehash(weak_hash)
    
    def test_password_validation_weak(self):
        """Test validation of weak passwords."""
        weak_passwords = [
            "123",           # Too short
            "password",      # Common word
            "12345678",      # Only numbers
            "abcdefgh",      # Only lowercase
            "ABCDEFGH",      # Only uppercase
        ]
        
        for password in weak_passwords:
            result = self.password_security.validate_password(password)
            assert not result.is_valid or result.strength in [PasswordStrength.VERY_WEAK, PasswordStrength.WEAK]
            assert len(result.errors) > 0
    
    def test_password_validation_strong(self):
        """Test validation of strong passwords."""
        strong_passwords = [
            "MyStrongP@ssw0rd123!",
            "Tr0ub4dor&3",
            "C0rr3ct-H0rs3-B@tt3ry-St@pl3"
        ]
        
        for password in strong_passwords:
            result = self.password_security.validate_password(password)
            assert result.is_valid
            assert result.strength in [PasswordStrength.GOOD, PasswordStrength.STRONG]
            assert result.score >= 70
    
    def test_password_validation_personal_info(self):
        """Test password validation against personal information."""
        email = "john.doe@example.com"
        
        # Password containing email parts should be flagged
        result = self.password_security.validate_password("john123!", email)
        assert len(result.suggestions) > 0
        assert any("email" in suggestion.lower() for suggestion in result.suggestions)
    
    def test_password_validation_common_patterns(self):
        """Test detection of common password patterns."""
        common_patterns = [
            "password123",
            "123456789",
            "qwerty123",
            "admin2024"
        ]
        
        for password in common_patterns:
            result = self.password_security.validate_password(password)
            assert not result.is_valid
            assert any("common" in error.lower() for error in result.errors)
    
    def test_secure_password_generation(self):
        """Test secure password generation."""
        for length in [8, 12, 16, 24]:
            password = self.password_security.generate_secure_password(length)
            
            assert len(password) == length
            
            # Validate the generated password
            result = self.password_security.validate_password(password)
            assert result.is_valid
            assert result.strength in [PasswordStrength.GOOD, PasswordStrength.STRONG]
    
    def test_reset_token_generation(self):
        """Test password reset token generation."""
        user_id = 1
        email = "test@example.com"
        
        token = self.password_security.generate_reset_token(user_id, email)
        assert token is not None
        assert len(token) >= 32
        
        # Validate token
        reset_token = self.password_security.validate_reset_token(token)
        assert reset_token is not None
        assert reset_token.user_id == user_id
        assert reset_token.email == email
        assert not reset_token.is_used
    
    def test_reset_token_expiration(self):
        """Test reset token expiration."""
        user_id = 1
        email = "test@example.com"
        
        token = self.password_security.generate_reset_token(user_id, email)
        
        # Manually expire the token
        reset_token = self.password_security._reset_tokens[token]
        reset_token.expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Should be invalid now
        validated_token = self.password_security.validate_reset_token(token)
        assert validated_token is None
    
    def test_reset_token_single_use(self):
        """Test that reset tokens can only be used once."""
        user_id = 1
        email = "test@example.com"
        
        token = self.password_security.generate_reset_token(user_id, email)
        
        # Use the token
        assert self.password_security.use_reset_token(token)
        
        # Should be invalid now
        validated_token = self.password_security.validate_reset_token(token)
        assert validated_token is None
    
    def test_rate_limiting(self):
        """Test rate limiting for reset token generation."""
        user_id = 1
        email = "test@example.com"
        
        # Generate tokens up to the limit
        tokens = []
        for i in range(5):  # MAX_RESET_ATTEMPTS_PER_HOUR = 5
            token = self.password_security.generate_reset_token(user_id, email)
            if token:
                tokens.append(token)
        
        # Next attempt should be rate limited
        token = self.password_security.generate_reset_token(user_id, email)
        assert token is None
    
    def test_algorithm_info(self):
        """Test algorithm information extraction."""
        password = "test_password"
        hashed = self.password_security.hash_password(password)
        
        info = self.password_security.get_algorithm_info(hashed)
        assert "algorithm" in info
        assert info["algorithm"] in ["bcrypt", "argon2"]
        assert "needs_rehash" in info


class TestEmailValidation:
    """Test email validation functionality."""
    
    def test_valid_emails(self):
        """Test validation of valid email addresses."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "123@example.com"
        ]
        
        for email in valid_emails:
            assert validate_email_address(email)
    
    def test_invalid_emails(self):
        """Test validation of invalid email addresses."""
        invalid_emails = [
            "invalid.email",
            "@example.com",
            "user@",
            "user..name@example.com",
            "user@.com"
        ]
        
        for email in invalid_emails:
            assert not validate_email_address(email)


class TestPasswordRoutes:
    """Test password-related API endpoints."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_user = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "current_password_123!"
        }
    
    def test_validate_password_endpoint(self):
        """Test password validation endpoint."""
        response = client.post("/auth/password/validate", json={
            "password": "weak",
            "email": "test@example.com"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "is_valid" in data
        assert "strength" in data
        assert "score" in data
        assert "errors" in data
        assert "suggestions" in data
    
    def test_password_reset_request(self):
        """Test password reset request endpoint."""
        response = client.post("/auth/password/reset/request", json={
            "email": "test@example.com"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "email" in data
        assert data["email"] == "test@example.com"
    
    def test_password_reset_invalid_email(self):
        """Test password reset with invalid email format."""
        response = client.post("/auth/password/reset/request", json={
            "email": "invalid.email"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirmation with invalid token."""
        response = client.post("/auth/password/reset/confirm", json={
            "token": "invalid_token_123456789012345678901234",
            "new_password": "NewP@ssw0rd123!",
            "confirm_password": "NewP@ssw0rd123!"
        })
        
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]
    
    def test_password_reset_confirm_weak_password(self):
        """Test password reset confirmation with weak password."""
        # First generate a valid token (mocked)
        with patch('backend.modules.auth.routes.password_routes.hash_token') as mock_hash:
            mock_hash.return_value = "mocked_hash"
            
            response = client.post("/auth/password/reset/confirm", json={
                "token": "valid_token_123456789012345678901234",
                "new_password": "weak",
                "confirm_password": "weak"
            })
            
            assert response.status_code == 400
            assert "security requirements" in response.json()["detail"]
    
    def test_password_change_wrong_current(self):
        """Test password change with wrong current password."""
        # This would require authentication setup in a real test
        pass
    
    def test_generate_secure_password(self):
        """Test secure password generation endpoint."""
        # This would require authentication setup in a real test
        pass


class TestSecurityAuditLogging:
    """Test security audit logging functionality."""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session for testing."""
        return MagicMock(spec=Session)
    
    def test_security_event_logging(self, db_session):
        """Test logging of security events."""
        from backend.modules.auth.routes.password_routes import log_security_event
        
        event = log_security_event(
            db=db_session,
            event_type="password_reset_requested",
            success=True,
            user_id=1,
            email="test@example.com",
            ip_address="192.168.1.1",
            user_agent="Test Browser",
            event_details={"token_id": 123},
            risk_score=0
        )
        
        # Verify database calls
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        db_session.refresh.assert_called_once()


class TestPasswordHistory:
    """Test password history functionality."""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session for testing."""
        return MagicMock(spec=Session)
    
    def test_password_history_tracking(self, db_session):
        """Test password history tracking."""
        from backend.modules.auth.routes.password_routes import add_password_to_history
        
        add_password_to_history(
            db=db_session,
            user_id=1,
            password_hash="hashed_password",
            algorithm="bcrypt",
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        
        # Verify database calls
        db_session.add.assert_called()
        db_session.commit.assert_called()
    
    def test_password_reuse_prevention(self, db_session):
        """Test prevention of password reuse."""
        from backend.modules.auth.routes.password_routes import check_password_reuse
        
        # Mock query to return previous password
        mock_history = MagicMock()
        mock_history.password_hash = password_security.hash_password("old_password")
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_history]
        
        # Should detect reuse
        is_reused = check_password_reuse(db_session, 1, "old_password")
        assert is_reused
        
        # Should not detect reuse for new password
        is_reused = check_password_reuse(db_session, 1, "new_password_123!")
        assert not is_reused


class TestIntegrationScenarios:
    """Test complete password security workflows."""
    
    def test_complete_password_reset_workflow(self):
        """Test complete password reset workflow."""
        # This would require setting up test database and user
        pass
    
    def test_password_upgrade_on_login(self):
        """Test automatic password hash upgrade on login."""
        # This would test the enhanced authentication with rehashing
        pass
    
    def test_concurrent_reset_requests(self):
        """Test handling of concurrent reset requests."""
        # This would test race conditions and token management
        pass
    
    def test_security_monitoring(self):
        """Test security monitoring and alerting."""
        # This would test integration with monitoring systems
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])