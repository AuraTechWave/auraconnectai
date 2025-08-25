"""
Security Utilities for POS Migration

Handles encryption, data masking, and compliance checks.
"""

import hashlib
import json
import logging
import re
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os

from core.config import settings

logger = logging.getLogger(__name__)

# Encryption key (should be stored securely in production)
ENCRYPTION_KEY = os.getenv("POS_MIGRATION_ENCRYPTION_KEY", None)
if not ENCRYPTION_KEY:
    # Generate a key for development (DO NOT use in production)
    ENCRYPTION_KEY = Fernet.generate_key()
    logger.warning("Using generated encryption key - not suitable for production!")

cipher_suite = Fernet(ENCRYPTION_KEY)


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """
    Encrypt POS credentials for secure storage.
    
    Args:
        credentials: Dictionary containing API keys, tokens, etc.
    
    Returns:
        Encrypted credentials as base64 string
    """
    try:
        # Convert to JSON
        json_creds = json.dumps(credentials)
        
        # Encrypt
        encrypted = cipher_suite.encrypt(json_creds.encode())
        
        # Return as base64 string
        return base64.b64encode(encrypted).decode('utf-8')
    
    except Exception as e:
        logger.error(f"Failed to encrypt credentials: {e}")
        raise ValueError("Credential encryption failed")


def decrypt_credentials(encrypted_creds: str) -> Dict[str, Any]:
    """
    Decrypt POS credentials for use.
    
    Args:
        encrypted_creds: Base64 encrypted credentials string
    
    Returns:
        Decrypted credentials dictionary
    """
    try:
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_creds.encode('utf-8'))
        
        # Decrypt
        decrypted = cipher_suite.decrypt(encrypted_bytes)
        
        # Parse JSON
        return json.loads(decrypted.decode('utf-8'))
    
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {e}")
        raise ValueError("Credential decryption failed")


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive information in data for logging/display.
    
    Args:
        data: Dictionary potentially containing sensitive data
    
    Returns:
        Dictionary with masked sensitive fields
    """
    sensitive_patterns = {
        'api_key': r'.*key.*',
        'token': r'.*token.*',
        'password': r'.*pass.*',
        'secret': r'.*secret.*',
        'credential': r'.*cred.*',
        'ssn': r'.*ssn.*',
        'tax_id': r'.*tax.*',
        'bank': r'.*bank.*',
        'account': r'.*account.*',
        'card': r'.*card.*',
    }
    
    masked_data = {}
    
    for key, value in data.items():
        # Check if field name matches sensitive patterns
        is_sensitive = False
        for pattern_name, pattern in sensitive_patterns.items():
            if re.match(pattern, key.lower()):
                is_sensitive = True
                break
        
        if is_sensitive:
            if isinstance(value, str):
                # Mask all but first 2 and last 2 characters
                if len(value) > 4:
                    masked_data[key] = f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
                else:
                    masked_data[key] = "*" * len(value)
            else:
                masked_data[key] = "***MASKED***"
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked_data[key] = mask_sensitive_data(value)
        elif isinstance(value, list):
            # Handle lists
            masked_data[key] = [
                mask_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked_data[key] = value
    
    return masked_data


def validate_data_compliance(
    data: Dict[str, Any],
    entity_type: str
) -> Dict[str, Any]:
    """
    Validate data for compliance requirements (GDPR, PCI, etc.).
    
    Args:
        data: Data to validate
        entity_type: Type of entity being processed
    
    Returns:
        Compliance validation results
    """
    issues = []
    warnings = []
    
    # PCI DSS compliance for payment data
    if entity_type in ["payments", "cards", "transactions"]:
        if "card_number" in data:
            if not is_card_number_masked(data["card_number"]):
                issues.append({
                    "type": "pci_violation",
                    "field": "card_number",
                    "message": "Unmasked card number detected"
                })
        
        if "cvv" in data:
            issues.append({
                "type": "pci_violation",
                "field": "cvv",
                "message": "CVV should never be stored"
            })
    
    # GDPR compliance for customer data
    if entity_type == "customers":
        pii_fields = ["email", "phone", "address", "date_of_birth"]
        for field in pii_fields:
            if field in data and not data.get(f"{field}_consent"):
                warnings.append({
                    "type": "gdpr_warning",
                    "field": field,
                    "message": f"No consent flag for {field}"
                })
    
    # Check for test/mock data
    if contains_mock_data(data):
        warnings.append({
            "type": "mock_data",
            "message": "Potential mock/test data detected"
        })
    
    return {
        "compliant": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "checked_at": datetime.utcnow().isoformat()
    }


def is_card_number_masked(card_number: str) -> bool:
    """Check if credit card number is properly masked."""
    if not card_number:
        return True
    
    # Should show only first 6 and last 4 digits
    if re.match(r'^\d{6}\*+\d{4}$', card_number):
        return True
    
    # Or be fully masked
    if re.match(r'^\*+$', card_number):
        return True
    
    return False


def contains_mock_data(data: Dict[str, Any]) -> bool:
    """
    Detect if data contains mock/test values.
    
    Args:
        data: Data to check
    
    Returns:
        True if mock data patterns detected
    """
    mock_patterns = [
        r'test',
        r'demo',
        r'sample',
        r'example',
        r'dummy',
        r'fake',
        r'lorem\s*ipsum',
        r'john\s*doe',
        r'jane\s*doe',
        r'foo\s*bar',
        r'123\s*456',
        r'0000',
        r'1111',
        r'9999',
    ]
    
    # Convert data to string for pattern matching
    data_str = json.dumps(data).lower()
    
    for pattern in mock_patterns:
        if re.search(pattern, data_str):
            return True
    
    # Check for sequential numbers (common in test data)
    if re.search(r'(12345|98765|11111|00000)', data_str):
        return True
    
    # Check for test email domains
    test_domains = ['@test.', '@example.', '@demo.', '@sample.']
    for domain in test_domains:
        if domain in data_str:
            return True
    
    return False


def sanitize_for_export(
    data: List[Dict[str, Any]],
    export_format: str,
    user_role: str
) -> List[Dict[str, Any]]:
    """
    Sanitize data based on export format and user role.
    
    Args:
        data: List of records to export
        export_format: Format of export (csv, json, pdf)
        user_role: Role of user requesting export
    
    Returns:
        Sanitized data suitable for export
    """
    sanitized = []
    
    for record in data:
        # Apply role-based filtering
        if user_role != "admin":
            # Remove sensitive fields for non-admin users
            sensitive_fields = [
                "source_credentials",
                "api_key",
                "secret_key",
                "error_details",
                "stack_trace"
            ]
            for field in sensitive_fields:
                record.pop(field, None)
        
        # Mask remaining sensitive data
        record = mask_sensitive_data(record)
        
        # Format-specific sanitization
        if export_format == "csv":
            # Flatten nested structures for CSV
            record = flatten_dict(record)
        
        sanitized.append(record)
    
    return sanitized


def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = '',
    sep: str = '_'
) -> Dict[str, Any]:
    """
    Flatten nested dictionary for CSV export.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key for recursion
        sep: Separator for nested keys
    
    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert list to comma-separated string
            items.append((new_key, ', '.join(str(i) for i in v)))
        else:
            items.append((new_key, v))
    
    return dict(items)


def generate_data_hash(data: Dict[str, Any]) -> str:
    """
    Generate hash of data for integrity checking.
    
    Args:
        data: Data to hash
    
    Returns:
        SHA-256 hash of data
    """
    # Sort keys for consistent hashing
    sorted_data = json.dumps(data, sort_keys=True)
    
    # Generate SHA-256 hash
    hash_object = hashlib.sha256(sorted_data.encode())
    return hash_object.hexdigest()


def verify_data_integrity(
    data: Dict[str, Any],
    expected_hash: str
) -> bool:
    """
    Verify data integrity using hash.
    
    Args:
        data: Data to verify
        expected_hash: Expected hash value
    
    Returns:
        True if data matches expected hash
    """
    actual_hash = generate_data_hash(data)
    return actual_hash == expected_hash


class DataClassification:
    """Classify data sensitivity levels."""
    
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    
    @staticmethod
    def classify_field(field_name: str, value: Any) -> str:
        """
        Classify sensitivity level of a field.
        
        Args:
            field_name: Name of the field
            value: Field value
        
        Returns:
            Classification level
        """
        field_lower = field_name.lower()
        
        # Restricted - Highest sensitivity
        restricted_patterns = [
            r'ssn', r'tax_id', r'bank_account',
            r'routing_number', r'card_number', r'cvv'
        ]
        for pattern in restricted_patterns:
            if re.search(pattern, field_lower):
                return DataClassification.RESTRICTED
        
        # Confidential
        confidential_patterns = [
            r'password', r'api_key', r'secret',
            r'token', r'credential', r'salary'
        ]
        for pattern in confidential_patterns:
            if re.search(pattern, field_lower):
                return DataClassification.CONFIDENTIAL
        
        # Internal
        internal_patterns = [
            r'email', r'phone', r'address',
            r'birth', r'name'
        ]
        for pattern in internal_patterns:
            if re.search(pattern, field_lower):
                return DataClassification.INTERNAL
        
        # Default to public
        return DataClassification.PUBLIC


from datetime import datetime