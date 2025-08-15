# backend/modules/orders/utils/security_utils.py

"""
Security utilities for webhook handling.

Provides functions for masking sensitive data in logs and responses.
"""

import re
from typing import Any, Dict, Union, List
import copy


def mask_sensitive_string(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive string, showing only first few characters.

    Args:
        value: The string to mask
        visible_chars: Number of characters to show at the beginning

    Returns:
        Masked string
    """
    if not value or len(value) <= visible_chars:
        return "***"

    return value[:visible_chars] + "*" * (len(value) - visible_chars)


def mask_sensitive_dict(
    data: Dict[str, Any], sensitive_keys: List[str] = None
) -> Dict[str, Any]:
    """
    Recursively mask sensitive values in a dictionary.

    Args:
        data: Dictionary to mask
        sensitive_keys: List of key patterns to mask (uses default if None)

    Returns:
        Dictionary with masked values
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "secret",
            "password",
            "token",
            "api_key",
            "apikey",
            "auth",
            "authorization",
            "bearer",
            "credential",
            "private",
            "signature",
            "webhook_secret",
            "bearer_token",
            "card_number",
            "cvv",
            "ssn",
            "account_number",
        ]

    if not isinstance(data, dict):
        return data

    masked_data = copy.deepcopy(data)

    def _mask_recursive(obj: Any, parent_key: str = "") -> Any:
        if isinstance(obj, dict):
            for key, value in obj.items():
                lower_key = key.lower()
                # Check if key matches any sensitive pattern
                if any(sensitive in lower_key for sensitive in sensitive_keys):
                    if isinstance(value, str):
                        obj[key] = mask_sensitive_string(value)
                    elif isinstance(value, dict):
                        # For nested auth configs, mask all string values
                        obj[key] = {
                            k: mask_sensitive_string(v) if isinstance(v, str) else v
                            for k, v in value.items()
                        }
                    else:
                        obj[key] = "***"
                else:
                    obj[key] = _mask_recursive(value, key)
        elif isinstance(obj, list):
            return [_mask_recursive(item, parent_key) for item in obj]

        return obj

    return _mask_recursive(masked_data)


def mask_url_credentials(url: str) -> str:
    """
    Mask credentials in a URL.

    Args:
        url: URL that might contain credentials

    Returns:
        URL with masked credentials
    """
    # Pattern to match credentials in URL
    pattern = r"(https?://)([^:]+):([^@]+)@"
    replacement = r"\1***:***@"
    return re.sub(pattern, replacement, url)


def mask_headers(
    headers: Dict[str, str], sensitive_headers: List[str] = None
) -> Dict[str, str]:
    """
    Mask sensitive header values.

    Args:
        headers: Headers dictionary
        sensitive_headers: List of header names to mask (uses default if None)

    Returns:
        Headers with masked values
    """
    if sensitive_headers is None:
        sensitive_headers = [
            "authorization",
            "x-api-key",
            "x-auth-token",
            "x-webhook-signature",
            "stripe-signature",
            "x-square-signature",
            "x-toast-api-key",
            "x-clover-api-key",
            "cookie",
            "set-cookie",
        ]

    masked_headers = {}
    for key, value in headers.items():
        if key.lower() in [h.lower() for h in sensitive_headers]:
            # Special handling for Authorization header
            if key.lower() == "authorization" and value.startswith("Bearer "):
                masked_headers[key] = f"Bearer {mask_sensitive_string(value[7:])}"
            else:
                masked_headers[key] = mask_sensitive_string(value)
        else:
            masked_headers[key] = value

    return masked_headers


def safe_log_dict(data: Union[Dict, Any], max_length: int = 1000) -> str:
    """
    Safely convert a dictionary to string for logging with sensitive data masked.

    Args:
        data: Data to log
        max_length: Maximum length of the string

    Returns:
        Safe string representation
    """
    if not isinstance(data, dict):
        return str(data)[:max_length]

    masked_data = mask_sensitive_dict(data)
    result = str(masked_data)

    if len(result) > max_length:
        result = result[: max_length - 3] + "..."

    return result
