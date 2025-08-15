# backend/modules/customers/services/payment_security.py

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import secrets
from typing import Optional
import logging

from core.config import settings


logger = logging.getLogger(__name__)


class PaymentTokenEncryption:
    """Secure encryption/decryption for payment tokens"""

    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for payment tokens"""
        # In production, this should be stored securely (e.g., AWS KMS, HashiCorp Vault)
        key_env_var = "PAYMENT_ENCRYPTION_KEY"

        if hasattr(settings, key_env_var):
            encoded_key = getattr(settings, key_env_var)
            try:
                return base64.urlsafe_b64decode(encoded_key.encode())
            except Exception as e:
                logger.warning(f"Invalid encryption key in settings: {e}")

        # Generate new key if not found
        password = secrets.token_bytes(32)
        salt = secrets.token_bytes(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))

        logger.warning(
            "Generated new payment encryption key. In production, store this securely: "
            f"{key.decode()}"
        )

        return key

    def encrypt_token(self, token: str) -> str:
        """Encrypt payment token"""
        try:
            encrypted_token = self.cipher_suite.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted_token).decode()
        except Exception as e:
            logger.error(f"Error encrypting payment token: {e}")
            raise ValueError("Failed to encrypt payment token")

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt payment token"""
        try:
            decoded_token = base64.urlsafe_b64decode(encrypted_token.encode())
            decrypted_token = self.cipher_suite.decrypt(decoded_token)
            return decrypted_token.decode()
        except Exception as e:
            logger.error(f"Error decrypting payment token: {e}")
            raise ValueError("Failed to decrypt payment token")

    def is_encrypted(self, token: str) -> bool:
        """Check if token is already encrypted"""
        try:
            # Try to decode base64 - encrypted tokens should be base64 encoded
            base64.urlsafe_b64decode(token.encode())
            # If successful, assume it's encrypted
            return True
        except Exception:
            # If decoding fails, assume it's plaintext
            return False


class SecurePaymentService:
    """Service for handling payment methods securely"""

    def __init__(self):
        self.encryption = PaymentTokenEncryption()

    def store_payment_token(self, token: str) -> str:
        """Securely store payment token"""
        if not token:
            raise ValueError("Payment token cannot be empty")

        # Never store actual card numbers or sensitive data
        if self._is_potentially_sensitive_data(token):
            raise ValueError("Cannot store potentially sensitive payment data")

        # Encrypt the token before storage
        encrypted_token = self.encryption.encrypt_token(token)

        logger.info("Payment token encrypted and stored securely")
        return encrypted_token

    def retrieve_payment_token(self, encrypted_token: str) -> str:
        """Retrieve and decrypt payment token"""
        if not encrypted_token:
            raise ValueError("Encrypted token cannot be empty")

        try:
            decrypted_token = self.encryption.decrypt_token(encrypted_token)
            return decrypted_token
        except Exception as e:
            logger.error(f"Failed to retrieve payment token: {e}")
            raise ValueError("Invalid or corrupted payment token")

    def _is_potentially_sensitive_data(self, data: str) -> bool:
        """Check if data might contain sensitive payment information"""
        # Remove spaces and dashes
        cleaned_data = data.replace(" ", "").replace("-", "")

        # Check if it looks like a credit card number (13-19 digits)
        if cleaned_data.isdigit() and 13 <= len(cleaned_data) <= 19:
            return True

        # Check for common patterns that might indicate sensitive data
        sensitive_patterns = [
            "4111111111111111",  # Test Visa
            "5555555555554444",  # Test Mastercard
            "378282246310005",  # Test Amex
        ]

        if any(pattern in cleaned_data for pattern in sensitive_patterns):
            return True

        return False

    def mask_card_number(self, card_number: str) -> str:
        """Mask card number for display purposes"""
        if not card_number or len(card_number) < 4:
            return "****"

        # Show only last 4 digits
        return "*" * (len(card_number) - 4) + card_number[-4:]

    def validate_payment_token(self, token: str) -> bool:
        """Validate payment token format"""
        if not token:
            return False

        # Basic validation - in production, you'd validate against payment processor format
        if len(token) < 10:
            return False

        # Check if it's properly encrypted
        if not self.encryption.is_encrypted(token):
            # If not encrypted, it should be a valid payment processor token
            # Add specific validation logic for your payment processor
            pass

        return True

    def generate_card_fingerprint(self, card_data: dict) -> str:
        """Generate unique fingerprint for card (for duplicate detection)"""
        # Create fingerprint from non-sensitive card data
        fingerprint_data = f"{card_data.get('last4', '')}{card_data.get('brand', '')}{card_data.get('exp_month', '')}{card_data.get('exp_year', '')}"

        # Hash the fingerprint data
        import hashlib

        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


# Global instance
payment_security = SecurePaymentService()


def encrypt_payment_data(payment_method_data: dict) -> dict:
    """Encrypt sensitive fields in payment method data"""
    encrypted_data = payment_method_data.copy()

    # Encrypt sensitive fields
    if "card_token" in encrypted_data and encrypted_data["card_token"]:
        encrypted_data["card_token"] = payment_security.store_payment_token(
            encrypted_data["card_token"]
        )

    if "wallet_id" in encrypted_data and encrypted_data["wallet_id"]:
        encrypted_data["wallet_id"] = payment_security.store_payment_token(
            encrypted_data["wallet_id"]
        )

    return encrypted_data


def decrypt_payment_data(payment_method_data: dict) -> dict:
    """Decrypt sensitive fields in payment method data"""
    decrypted_data = payment_method_data.copy()

    # Decrypt sensitive fields
    if "card_token" in decrypted_data and decrypted_data["card_token"]:
        try:
            decrypted_data["card_token"] = payment_security.retrieve_payment_token(
                decrypted_data["card_token"]
            )
        except ValueError:
            # If decryption fails, the token might already be decrypted or invalid
            logger.warning("Failed to decrypt card_token, using as-is")

    if "wallet_id" in decrypted_data and decrypted_data["wallet_id"]:
        try:
            decrypted_data["wallet_id"] = payment_security.retrieve_payment_token(
                decrypted_data["wallet_id"]
            )
        except ValueError:
            logger.warning("Failed to decrypt wallet_id, using as-is")

    return decrypted_data


# Security audit logging
def log_payment_access(
    user_id: int, customer_id: int, action: str, payment_method_id: Optional[int] = None
):
    """Log payment method access for security audit"""
    logger.info(
        f"Payment access: user={user_id}, customer={customer_id}, "
        f"action={action}, payment_method={payment_method_id}"
    )


# PCI DSS compliance helpers
class PCIComplianceHelper:
    """Helper functions for PCI DSS compliance"""

    @staticmethod
    def validate_card_holder_data_access(
        user_permissions: list, required_permission: str
    ) -> bool:
        """Validate user has permission to access cardholder data"""
        return required_permission in user_permissions

    @staticmethod
    def log_cardholder_data_access(user_id: int, action: str, resource: str):
        """Log cardholder data access for PCI compliance"""
        logger.info(
            f"PCI AUDIT: user={user_id}, action={action}, resource={resource}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    @staticmethod
    def mask_sensitive_logs(log_data: dict) -> dict:
        """Mask sensitive data in logs"""
        masked_data = log_data.copy()

        # Mask common sensitive fields
        sensitive_fields = ["card_number", "cvv", "pin", "password", "token"]

        for field in sensitive_fields:
            if field in masked_data:
                masked_data[field] = "***MASKED***"

        return masked_data
