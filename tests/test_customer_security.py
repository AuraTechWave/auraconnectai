# tests/test_customer_security.py

import pytest
import bcrypt
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from backend.modules.customers.services.security_service import CustomerSecurityService


class TestCustomerSecurityService:
    """Test suite for customer security service"""
    
    def test_hash_password_success(self):
        """Test successful password hashing"""
        password = "SecurePassword123!"
        hashed = CustomerSecurityService.hash_password(password)
        
        # Assertions
        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 50  # Bcrypt hashes are typically 60 characters
        assert password != hashed  # Original password should not equal hash
        
        # Verify the hash can be used for verification
        assert CustomerSecurityService.verify_password(password, hashed)
    
    def test_hash_password_empty(self):
        """Test hashing empty password raises error"""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            CustomerSecurityService.hash_password("")
    
    def test_verify_password_success(self):
        """Test successful password verification"""
        password = "TestPassword123!"
        hashed = CustomerSecurityService.hash_password(password)
        
        # Test correct password
        assert CustomerSecurityService.verify_password(password, hashed) == True
        
        # Test incorrect password
        assert CustomerSecurityService.verify_password("WrongPassword", hashed) == False
    
    def test_verify_password_invalid_inputs(self):
        """Test password verification with invalid inputs"""
        # Test empty password
        assert CustomerSecurityService.verify_password("", "somehash") == False
        
        # Test empty hash
        assert CustomerSecurityService.verify_password("password", "") == False
        
        # Test both empty
        assert CustomerSecurityService.verify_password("", "") == False
        
        # Test malformed hash
        assert CustomerSecurityService.verify_password("password", "invalid_hash") == False
    
    def test_validate_password_strength_strong(self):
        """Test validation of strong password"""
        strong_password = "SecureP@ssw0rd123!"
        result = CustomerSecurityService.validate_password_strength(strong_password)
        
        assert result["is_valid"] == True
        assert result["strength"] == "strong"
        assert result["score"] >= 6
        assert len(result["errors"]) == 0
    
    def test_validate_password_strength_weak(self):
        """Test validation of weak password"""
        weak_password = "123"
        result = CustomerSecurityService.validate_password_strength(weak_password)
        
        assert result["is_valid"] == False
        assert result["strength"] == "weak"
        assert result["score"] < 4
        assert len(result["errors"]) > 0
        assert "Password must be at least 8 characters long" in result["errors"]
    
    def test_validate_password_strength_common(self):
        """Test validation rejects common passwords"""
        common_password = "password123"
        result = CustomerSecurityService.validate_password_strength(common_password)
        
        assert result["is_valid"] == False
        assert "Password is too common" in result["errors"]
    
    def test_validate_password_strength_repeated_chars(self):
        """Test validation catches repeated characters"""
        repeated_password = "Passssword123!"
        result = CustomerSecurityService.validate_password_strength(repeated_password)
        
        assert "Password should not contain repeated characters" in result["errors"]
    
    def test_generate_secure_token(self):
        """Test secure token generation"""
        token1 = CustomerSecurityService.generate_secure_token(32)
        token2 = CustomerSecurityService.generate_secure_token(32)
        
        # Assertions
        assert len(token1) == 32
        assert len(token2) == 32
        assert token1 != token2  # Should be unique
        assert token1.isalnum()  # Should only contain alphanumeric characters
    
    def test_generate_referral_code(self):
        """Test referral code generation"""
        code1 = CustomerSecurityService.generate_referral_code(8)
        code2 = CustomerSecurityService.generate_referral_code(8)
        
        # Assertions
        assert len(code1) == 8
        assert len(code2) == 8
        assert code1 != code2  # Should be unique
        assert code1.isupper()  # Should be uppercase
        assert '0' not in code1 and 'O' not in code1  # Confusing chars excluded
        assert '1' not in code1 and 'I' not in code1  # Confusing chars excluded
    
    def test_mask_sensitive_data(self):
        """Test masking of sensitive data"""
        # Test phone number
        phone = "1234567890"
        masked = CustomerSecurityService.mask_sensitive_data(phone, 4)
        assert masked == "******7890"
        
        # Test email
        email_part = "john.doe"
        masked_email = CustomerSecurityService.mask_sensitive_data(email_part, 2)
        assert masked_email == "*****oe"
        
        # Test short data
        short_data = "123"
        masked_short = CustomerSecurityService.mask_sensitive_data(short_data, 4)
        assert masked_short == "***"
        
        # Test empty data
        empty_masked = CustomerSecurityService.mask_sensitive_data("", 4)
        assert empty_masked == ""
    
    def test_sanitize_customer_response(self):
        """Test sanitization of customer response data"""
        customer_data = {
            "id": 1,
            "email": "test@example.com",
            "first_name": "John",
            "password_hash": "hashed_password",
            "reset_token": "secret_token",
            "phone": "1234567890",
            "api_key": "secret_api_key"
        }
        
        sanitized = CustomerSecurityService.sanitize_customer_response(customer_data)
        
        # Assertions
        assert "password_hash" not in sanitized
        assert "reset_token" not in sanitized
        assert "api_key" not in sanitized
        assert sanitized["id"] == 1
        assert sanitized["email"] == "test@example.com"
        assert sanitized["first_name"] == "John"
        assert "phone_masked" in sanitized
        assert "email_masked" in sanitized
        assert sanitized["phone_masked"] == "******7890"
        assert sanitized["email_masked"] == "**st@example.com"
    
    def test_check_account_lockout_not_locked(self):
        """Test account lockout check when not locked"""
        result = CustomerSecurityService.check_account_lockout(
            failed_attempts=2,
            last_failed_attempt=datetime.utcnow(),
            max_attempts=5
        )
        
        assert result["is_locked"] == False
        assert result["remaining_attempts"] == 3
        assert result["lockout_until"] is None
    
    def test_check_account_lockout_locked(self):
        """Test account lockout check when locked"""
        recent_failure = datetime.utcnow() - timedelta(minutes=10)
        
        result = CustomerSecurityService.check_account_lockout(
            failed_attempts=5,
            last_failed_attempt=recent_failure,
            lockout_duration_minutes=30,
            max_attempts=5
        )
        
        assert result["is_locked"] == True
        assert result["remaining_attempts"] == 0
        assert result["lockout_until"] is not None
        assert result["minutes_remaining"] > 0
    
    def test_check_account_lockout_expired(self):
        """Test account lockout check when lockout has expired"""
        old_failure = datetime.utcnow() - timedelta(minutes=35)
        
        result = CustomerSecurityService.check_account_lockout(
            failed_attempts=5,
            last_failed_attempt=old_failure,
            lockout_duration_minutes=30,
            max_attempts=5
        )
        
        assert result["is_locked"] == False
        assert result["lockout_until"] is not None  # Still set, but expired
    
    def test_validate_data_retention_compliance_active(self):
        """Test data retention compliance for active customer"""
        active_customer = {
            "last_login": datetime.utcnow() - timedelta(days=30),
            "updated_at": datetime.utcnow() - timedelta(days=10)
        }
        
        result = CustomerSecurityService.validate_data_retention_compliance(active_customer)
        
        assert result["compliant"] == True
        assert result["action_required"] is None
    
    def test_validate_data_retention_compliance_inactive(self):
        """Test data retention compliance for inactive customer"""
        inactive_customer = {
            "last_login": datetime.utcnow() - timedelta(days=800),
            "updated_at": datetime.utcnow() - timedelta(days=750)
        }
        
        result = CustomerSecurityService.validate_data_retention_compliance(inactive_customer)
        
        assert result["compliant"] == False
        assert result["action_required"] == "data_retention_review"
        assert result["inactive_days"] > 730
        assert "recommendation" in result
    
    @patch('backend.modules.customers.services.security_service.logger')
    def test_log_security_event(self, mock_logger):
        """Test security event logging"""
        CustomerSecurityService.log_security_event(
            customer_id=1,
            event_type="login_attempt",
            details="Failed login attempt",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        # Verify logging was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "Customer: 1" in log_message
        assert "login_attempt" in log_message
        assert "192.168.1.1" in log_message


class TestPasswordComplexity:
    """Test different password complexity scenarios"""
    
    def test_password_with_all_requirements(self):
        """Test password that meets all requirements"""
        password = "MyP@ssW0rd2024!"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert result["is_valid"] == True
        assert result["strength"] in ["medium", "strong"]
        assert len(result["errors"]) == 0
    
    def test_password_missing_uppercase(self):
        """Test password missing uppercase letters"""
        password = "myp@ssw0rd2024!"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert "Password must contain at least one uppercase letter" in result["errors"]
    
    def test_password_missing_lowercase(self):
        """Test password missing lowercase letters"""
        password = "MYP@SSW0RD2024!"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert "Password must contain at least one lowercase letter" in result["errors"]
    
    def test_password_missing_numbers(self):
        """Test password missing numbers"""
        password = "MyP@ssWord!"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert "Password must contain at least one number" in result["errors"]
    
    def test_password_missing_special_chars(self):
        """Test password missing special characters"""
        password = "MyPassWord2024"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert "Password must contain at least one special character" in result["errors"]
    
    def test_very_long_password(self):
        """Test very long password gets bonus points"""
        password = "ThisIsAVeryLongAndSecurePassword123!@#"
        result = CustomerSecurityService.validate_password_strength(password)
        
        assert result["is_valid"] == True
        assert result["strength"] == "strong"
        assert result["score"] >= 6


class TestSecurityIntegration:
    """Integration tests for security components"""
    
    def test_end_to_end_password_workflow(self):
        """Test complete password workflow from creation to verification"""
        original_password = "SecurePassword123!"
        
        # Step 1: Validate password strength
        validation = CustomerSecurityService.validate_password_strength(original_password)
        assert validation["is_valid"] == True
        
        # Step 2: Hash the password
        hashed = CustomerSecurityService.hash_password(original_password)
        assert hashed != original_password
        
        # Step 3: Verify the password
        assert CustomerSecurityService.verify_password(original_password, hashed) == True
        assert CustomerSecurityService.verify_password("wrong_password", hashed) == False
    
    def test_customer_data_sanitization_workflow(self):
        """Test complete customer data sanitization workflow"""
        raw_customer_data = {
            "id": 1,
            "email": "john.doe@example.com",
            "phone": "5551234567",
            "first_name": "John",
            "last_name": "Doe",
            "password_hash": "$2b$12$abcdef...",
            "reset_token": "secret123",
            "api_key": "key_12345",
            "two_factor_secret": "secret_2fa"
        }
        
        # Sanitize for API response
        sanitized = CustomerSecurityService.sanitize_customer_response(raw_customer_data)
        
        # Verify all sensitive fields are removed
        sensitive_fields = ['password_hash', 'reset_token', 'api_key', 'two_factor_secret']
        for field in sensitive_fields:
            assert field not in sanitized
            
        # Verify safe fields remain
        safe_fields = ['id', 'email', 'first_name', 'last_name']
        for field in safe_fields:
            assert field in sanitized
            
        # Verify masked versions are added
        assert 'phone_masked' in sanitized
        assert 'email_masked' in sanitized


if __name__ == "__main__":
    pytest.main([__file__])