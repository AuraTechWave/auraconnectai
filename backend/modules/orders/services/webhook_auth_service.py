# backend/modules/orders/services/webhook_auth_service.py

"""
Webhook authentication and verification service.

Handles signature verification for various external POS providers.
"""

import hmac
import hashlib
import base64
import json
import logging
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.modules.orders.models.external_pos_models import ExternalPOSProvider
from backend.modules.orders.enums.external_pos_enums import (
    ExternalPOSProvider as POSProviderEnum,
    AuthenticationType
)

logger = logging.getLogger(__name__)


class WebhookAuthService:
    """Service for authenticating incoming webhooks from external POS systems"""
    
    def __init__(self, db: Session):
        self.db = db
        self.timestamp_tolerance_seconds = 300  # 5 minutes
        
    async def verify_webhook_request(
        self,
        provider_code: str,
        headers: Dict[str, str],
        body: bytes,
        request_signature: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Verify incoming webhook request.
        
        Returns:
            Tuple of (is_valid, error_message, verification_details)
        """
        # Get provider configuration
        provider = self.db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.provider_code == provider_code,
            ExternalPOSProvider.is_active == True
        ).first()
        
        if not provider:
            return False, f"Unknown or inactive provider: {provider_code}", None
            
        try:
            # Route to appropriate verification method
            if provider.auth_type == AuthenticationType.HMAC_SHA256:
                return await self._verify_hmac_sha256(provider, headers, body, request_signature)
            elif provider.auth_type == AuthenticationType.HMAC_SHA512:
                return await self._verify_hmac_sha512(provider, headers, body, request_signature)
            elif provider.auth_type == AuthenticationType.API_KEY:
                return await self._verify_api_key(provider, headers)
            elif provider.auth_type == AuthenticationType.BEARER_TOKEN:
                return await self._verify_bearer_token(provider, headers)
            else:
                return False, f"Unsupported auth type: {provider.auth_type}", None
                
        except Exception as e:
            logger.error(f"Error verifying webhook for {provider_code}: {str(e)}")
            return False, f"Verification error: {str(e)}", None
    
    async def _verify_hmac_sha256(
        self,
        provider: ExternalPOSProvider,
        headers: Dict[str, str],
        body: bytes,
        request_signature: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify HMAC-SHA256 signature"""
        auth_config = provider.auth_config
        secret = auth_config.get("webhook_secret", "")
        signature_header = auth_config.get("signature_header", "X-Webhook-Signature")
        
        # Get signature from headers if not provided
        if not request_signature:
            request_signature = headers.get(signature_header.lower(), "")
            
        if not request_signature:
            return False, f"Missing signature header: {signature_header}", None
            
        # Provider-specific signature verification
        if provider.provider_code == POSProviderEnum.SQUARE:
            return await self._verify_square_signature(
                secret, headers, body, request_signature
            )
        elif provider.provider_code == POSProviderEnum.STRIPE:
            return await self._verify_stripe_signature(
                secret, headers, body, request_signature
            )
        else:
            # Generic HMAC-SHA256 verification
            expected_signature = hmac.new(
                secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Some providers prefix with "sha256="
            if request_signature.startswith("sha256="):
                request_signature = request_signature[7:]
                
            is_valid = hmac.compare_digest(expected_signature, request_signature)
            
            return (
                is_valid,
                None if is_valid else "Invalid signature",
                {"signature_algorithm": "hmac-sha256"}
            )
    
    async def _verify_square_signature(
        self,
        secret: str,
        headers: Dict[str, str],
        body: bytes,
        signature: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify Square webhook signature"""
        # Square uses HMAC-SHA256 with specific formatting
        request_body = body.decode('utf-8')
        string_to_sign = headers.get('x-square-signature', '') + request_body
        
        expected_signature = base64.b64encode(
            hmac.new(
                secret.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        is_valid = hmac.compare_digest(expected_signature, signature)
        
        return (
            is_valid,
            None if is_valid else "Invalid Square signature",
            {
                "signature_algorithm": "square-hmac-sha256",
                "provider": "square"
            }
        )
    
    async def _verify_stripe_signature(
        self,
        secret: str,
        headers: Dict[str, str],
        body: bytes,
        signature: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify Stripe webhook signature"""
        # Stripe signature format: t=timestamp,v1=signature
        timestamp = None
        signatures = []
        
        for element in signature.split(','):
            key, value = element.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)
                
        if not timestamp or not signatures:
            return False, "Invalid Stripe signature format", None
            
        # Check timestamp to prevent replay attacks
        try:
            timestamp_int = int(timestamp)
            current_time = int(datetime.utcnow().timestamp())
            if abs(current_time - timestamp_int) > self.timestamp_tolerance_seconds:
                return False, "Webhook timestamp too old", None
        except ValueError:
            return False, "Invalid timestamp", None
            
        # Compute expected signature
        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
        expected_signature = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Check if any provided signature matches
        is_valid = any(
            hmac.compare_digest(expected_signature, sig) 
            for sig in signatures
        )
        
        return (
            is_valid,
            None if is_valid else "Invalid Stripe signature",
            {
                "signature_algorithm": "stripe-hmac-sha256",
                "provider": "stripe",
                "timestamp": timestamp
            }
        )
    
    async def _verify_hmac_sha512(
        self,
        provider: ExternalPOSProvider,
        headers: Dict[str, str],
        body: bytes,
        request_signature: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify HMAC-SHA512 signature"""
        auth_config = provider.auth_config
        secret = auth_config.get("webhook_secret", "")
        signature_header = auth_config.get("signature_header", "X-Webhook-Signature")
        
        if not request_signature:
            request_signature = headers.get(signature_header.lower(), "")
            
        if not request_signature:
            return False, f"Missing signature header: {signature_header}", None
            
        expected_signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha512
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_signature, request_signature)
        
        return (
            is_valid,
            None if is_valid else "Invalid signature",
            {"signature_algorithm": "hmac-sha512"}
        )
    
    async def _verify_api_key(
        self,
        provider: ExternalPOSProvider,
        headers: Dict[str, str]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify API key authentication"""
        auth_config = provider.auth_config
        expected_key = auth_config.get("api_key", "")
        key_header = auth_config.get("api_key_header", "X-API-Key")
        
        provided_key = headers.get(key_header.lower(), "")
        
        if not provided_key:
            return False, f"Missing API key header: {key_header}", None
            
        is_valid = hmac.compare_digest(expected_key, provided_key)
        
        return (
            is_valid,
            None if is_valid else "Invalid API key",
            {"auth_method": "api_key"}
        )
    
    async def _verify_bearer_token(
        self,
        provider: ExternalPOSProvider,
        headers: Dict[str, str]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify Bearer token authentication"""
        auth_config = provider.auth_config
        expected_token = auth_config.get("bearer_token", "")
        
        auth_header = headers.get("authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return False, "Missing or invalid Authorization header", None
            
        provided_token = auth_header[7:]  # Remove "Bearer " prefix
        
        is_valid = hmac.compare_digest(expected_token, provided_token)
        
        return (
            is_valid,
            None if is_valid else "Invalid bearer token",
            {"auth_method": "bearer_token"}
        )
    
    def generate_test_signature(
        self,
        provider_code: str,
        body: Dict[str, Any],
        timestamp: Optional[int] = None
    ) -> Optional[Dict[str, str]]:
        """Generate test signature for webhook testing"""
        provider = self.db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.provider_code == provider_code
        ).first()
        
        if not provider:
            return None
            
        auth_config = provider.auth_config
        body_str = json.dumps(body, separators=(',', ':'))
        body_bytes = body_str.encode()
        
        if provider.auth_type == AuthenticationType.HMAC_SHA256:
            secret = auth_config.get("webhook_secret", "")
            
            if provider.provider_code == POSProviderEnum.STRIPE:
                # Stripe format
                if not timestamp:
                    timestamp = int(datetime.utcnow().timestamp())
                signed_payload = f"{timestamp}.{body_str}"
                signature = hmac.new(
                    secret.encode(),
                    signed_payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                return {
                    "Stripe-Signature": f"t={timestamp},v1={signature}"
                }
            else:
                # Generic HMAC
                signature = hmac.new(
                    secret.encode(),
                    body_bytes,
                    hashlib.sha256
                ).hexdigest()
                signature_header = auth_config.get("signature_header", "X-Webhook-Signature")
                return {
                    signature_header: f"sha256={signature}"
                }
                
        elif provider.auth_type == AuthenticationType.API_KEY:
            key_header = auth_config.get("api_key_header", "X-API-Key")
            return {
                key_header: auth_config.get("api_key", "")
            }
            
        elif provider.auth_type == AuthenticationType.BEARER_TOKEN:
            return {
                "Authorization": f"Bearer {auth_config.get('bearer_token', '')}"
            }
            
        return None