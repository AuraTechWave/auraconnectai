"""
Webhook signature validation and security.

Provides HMAC-based signature validation for incoming webhooks to ensure
they come from authorized sources.
"""

import hmac
import hashlib
import time
import json
import logging
from typing import Optional, Dict, Union
from datetime import datetime
from fastapi import Request, HTTPException, Header
from pydantic import BaseModel

from .security_config import (
    WEBHOOK_SIGNATURE_REQUIRED,
    WEBHOOK_SIGNATURE_HEADER,
    WEBHOOK_TIMESTAMP_HEADER,
    WEBHOOK_TIMESTAMP_TOLERANCE,
    IS_PRODUCTION
)
from .audit_logger import audit_logger

logger = logging.getLogger(__name__)


class WebhookSignatureValidator:
    """
    Validates webhook signatures using HMAC-SHA256.
    
    Each webhook source should have its own secret key stored securely.
    """
    
    def __init__(self):
        # Store webhook secrets by source
        # In production, these should come from secure configuration
        self.webhook_secrets: Dict[str, str] = {}
        self._load_webhook_secrets()
    
    def _load_webhook_secrets(self):
        """Load webhook secrets from secure configuration."""
        import os
        
        # Load secrets for different webhook sources
        # Format: WEBHOOK_SECRET_<SOURCE> environment variable
        webhook_sources = ["SQUARE", "TOAST", "CLOVER", "STRIPE", "TWILIO"]
        
        for source in webhook_sources:
            secret_key = f"WEBHOOK_SECRET_{source}"
            secret = os.getenv(secret_key)
            if secret:
                self.webhook_secrets[source.lower()] = secret
                logger.info(f"Loaded webhook secret for {source}")
            else:
                logger.warning(f"No webhook secret found for {source}")
    
    def register_webhook_secret(self, source: str, secret: str):
        """Register a webhook secret for a specific source."""
        self.webhook_secrets[source.lower()] = secret
    
    async def validate_signature(
        self,
        request: Request,
        source: str,
        body: bytes,
        signature_header: Optional[str] = None,
        timestamp_header: Optional[str] = None
    ) -> bool:
        """
        Validate webhook signature.
        
        Args:
            request: The FastAPI request object
            source: The webhook source (e.g., "square", "toast")
            body: The raw request body bytes
            signature_header: Optional custom signature header name
            timestamp_header: Optional custom timestamp header name
            
        Returns:
            True if signature is valid, raises HTTPException otherwise
        """
        # Skip validation in development if not required
        if not WEBHOOK_SIGNATURE_REQUIRED and not IS_PRODUCTION:
            logger.warning(f"Webhook signature validation skipped for {source} (development mode)")
            return True
        
        # Get webhook secret
        secret = self.webhook_secrets.get(source.lower())
        if not secret:
            logger.error(f"No webhook secret configured for source: {source}")
            raise HTTPException(
                status_code=401,
                detail="Webhook source not configured"
            )
        
        # Get signature from header
        sig_header = signature_header or WEBHOOK_SIGNATURE_HEADER
        signature = request.headers.get(sig_header)
        if not signature:
            await self._log_validation_failure(request, source, "Missing signature header")
            raise HTTPException(
                status_code=401,
                detail="Missing webhook signature"
            )
        
        # Get timestamp from header (if provided)
        ts_header = timestamp_header or WEBHOOK_TIMESTAMP_HEADER
        timestamp_str = request.headers.get(ts_header)
        
        # Validate timestamp if provided
        if timestamp_str:
            try:
                timestamp = int(timestamp_str)
                current_time = int(time.time())
                
                # Check if timestamp is within tolerance
                if abs(current_time - timestamp) > WEBHOOK_TIMESTAMP_TOLERANCE:
                    await self._log_validation_failure(
                        request, source, "Timestamp outside tolerance window"
                    )
                    raise HTTPException(
                        status_code=401,
                        detail="Webhook timestamp too old"
                    )
            except ValueError:
                await self._log_validation_failure(request, source, "Invalid timestamp format")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook timestamp"
                )
        
        # Calculate expected signature
        expected_signature = self._calculate_signature(
            secret, body, timestamp_str
        )
        
        # Compare signatures
        if not self._secure_compare(signature, expected_signature):
            await self._log_validation_failure(request, source, "Invalid signature")
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        
        # Log successful validation
        logger.info(f"Webhook signature validated for source: {source}")
        return True
    
    def _calculate_signature(
        self,
        secret: str,
        body: bytes,
        timestamp: Optional[str] = None
    ) -> str:
        """Calculate HMAC-SHA256 signature."""
        # Create payload to sign
        if timestamp:
            # Include timestamp in signature to prevent replay attacks
            # Combine timestamp and body at the bytes level to avoid encoding issues
            timestamp_bytes = timestamp.encode('utf-8')
            separator_bytes = b'.'
            payload_bytes = timestamp_bytes + separator_bytes + body
        else:
            payload_bytes = body
        
        # Calculate HMAC-SHA256
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _secure_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        return hmac.compare_digest(a, b)
    
    async def _log_validation_failure(
        self,
        request: Request,
        source: str,
        reason: str
    ):
        """Log webhook validation failure for security monitoring."""
        client_ip = request.client.host if request.client else "unknown"
        
        await audit_logger.log_security_event(
            event_type="webhook_validation_failure",
            severity="medium",
            description=f"Webhook validation failed for {source}: {reason}",
            client_ip=client_ip,
            metadata={
                "source": source,
                "reason": reason,
                "path": str(request.url.path),
                "headers": dict(request.headers)
            }
        )


class WebhookRequest(BaseModel):
    """Base model for webhook requests with signature validation."""
    
    class Config:
        # Allow extra fields for flexibility
        extra = "allow"
    
    @classmethod
    async def validate_and_parse(
        cls,
        request: Request,
        source: str,
        validator: WebhookSignatureValidator
    ):
        """
        Validate webhook signature and parse request body.
        
        Usage:
            webhook_data = await WebhookRequest.validate_and_parse(
                request, "square", webhook_validator
            )
        """
        # Read raw body
        body = await request.body()
        
        # Validate signature
        await validator.validate_signature(request, source, body)
        
        # Parse body
        try:
            data = json.loads(body)
            return cls(**data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in webhook body"
            )
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse webhook body: {str(e)}"
            )


# FastAPI dependency for webhook validation
async def validate_webhook_signature(
    request: Request,
    source: str = Header(..., alias="X-Webhook-Source"),
    signature: str = Header(..., alias="X-Webhook-Signature"),
    timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp")
):
    """
    FastAPI dependency to validate webhook signatures.
    
    Usage:
        @app.post("/webhooks/square")
        async def handle_square_webhook(
            request: Request,
            _: None = Depends(lambda req: validate_webhook_signature(req, "square"))
        ):
            ...
    """
    # Get validator from app state
    validator: WebhookSignatureValidator = request.app.state.webhook_validator
    
    # Read body
    body = await request.body()
    
    # Validate signature
    await validator.validate_signature(
        request, source, body,
        signature_header="X-Webhook-Signature",
        timestamp_header="X-Webhook-Timestamp"
    )
    
    # Store body for later use
    request.state.webhook_body = body


# Global webhook validator instance
webhook_validator = WebhookSignatureValidator()