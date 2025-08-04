# backend/modules/payments/utils/retry_decorator.py

import asyncio
import logging
from typing import Callable, Any, Optional, Type, Tuple, Union
from functools import wraps
import random
import httpx
import stripe.error
from decimal import Decimal


logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        retryable_status_codes: Optional[Tuple[int, ...]] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or self._get_default_exceptions()
        self.retryable_status_codes = retryable_status_codes or (500, 502, 503, 504, 429)
    
    def _get_default_exceptions(self) -> Tuple[Type[Exception], ...]:
        """Get default retryable exceptions"""
        exceptions = [
            # Network errors
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            # HTTP client errors
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ]
        
        # Add Stripe-specific errors if available
        try:
            import stripe.error
            exceptions.extend([
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
            ])
        except ImportError:
            pass
        
        return tuple(exceptions)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for next retry attempt"""
        delay = min(
            self.initial_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter (±25%)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(delay, 0)


class ErrorClassification:
    """Error classification for retry decisions"""
    
    # Transient errors - should retry
    TRANSIENT_ERRORS = {
        # Network errors
        ConnectionError: "Network connection failed",
        TimeoutError: "Request timed out",
        asyncio.TimeoutError: "Async operation timed out",
        
        # HTTP errors
        httpx.ConnectError: "Failed to connect to server",
        httpx.ConnectTimeout: "Connection timeout",
        httpx.ReadTimeout: "Read timeout",
        httpx.WriteTimeout: "Write timeout",
        httpx.PoolTimeout: "Connection pool timeout",
    }
    
    # Permanent errors - should not retry
    PERMANENT_ERRORS = {
        ValueError: "Invalid input value",
        TypeError: "Invalid type",
        KeyError: "Missing required key",
        AttributeError: "Invalid attribute access",
    }
    
    # HTTP status codes
    TRANSIENT_STATUS_CODES = (
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    )
    
    PERMANENT_STATUS_CODES = (
        400,  # Bad Request
        401,  # Unauthorized
        403,  # Forbidden
        404,  # Not Found
        405,  # Method Not Allowed
        409,  # Conflict
        410,  # Gone
        422,  # Unprocessable Entity
    )
    
    @classmethod
    def classify_error(cls, error: Exception) -> Tuple[bool, str]:
        """
        Classify an error as transient or permanent
        
        Returns:
            Tuple of (is_transient, reason)
        """
        # Check explicit transient errors
        for error_type, reason in cls.TRANSIENT_ERRORS.items():
            if isinstance(error, error_type):
                return True, reason
        
        # Check explicit permanent errors
        for error_type, reason in cls.PERMANENT_ERRORS.items():
            if isinstance(error, error_type):
                return False, reason
        
        # Check HTTP status codes
        status_code = cls._extract_status_code(error)
        if status_code:
            if status_code in cls.TRANSIENT_STATUS_CODES:
                return True, f"HTTP {status_code} - Transient error"
            elif status_code in cls.PERMANENT_STATUS_CODES:
                return False, f"HTTP {status_code} - Permanent error"
        
        # Check gateway-specific errors
        if cls._is_gateway_transient_error(error):
            return True, "Gateway transient error"
        
        # Default to permanent (don't retry unknown errors)
        return False, "Unknown error type"
    
    @staticmethod
    def _extract_status_code(error: Exception) -> Optional[int]:
        """Extract HTTP status code from various error types"""
        # httpx errors
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return error.response.status_code
        
        # Stripe errors
        if hasattr(error, 'http_status'):
            return error.http_status
        
        # Generic HTTP errors
        if hasattr(error, 'status_code'):
            return error.status_code
        
        return None
    
    @staticmethod
    def _is_gateway_transient_error(error: Exception) -> bool:
        """Check if error is a transient gateway error"""
        error_class = error.__class__
        error_module = error_class.__module__ if hasattr(error_class, '__module__') else ''
        
        # Stripe transient errors
        if error_module.startswith('stripe'):
            try:
                import stripe.error
                if isinstance(error, (
                    stripe.error.APIConnectionError,
                    stripe.error.RateLimitError,
                    stripe.error.StripeError
                )):
                    # Check if it's a server error
                    if hasattr(error, 'http_status') and error.http_status >= 500:
                        return True
                    # Rate limit and connection errors are always transient
                    if isinstance(error, (stripe.error.APIConnectionError, stripe.error.RateLimitError)):
                        return True
            except ImportError:
                pass
        
        # Square errors (using httpx)
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code >= 500
        
        # PayPal errors
        if 'paypal' in str(error).lower() and 'timeout' in str(error).lower():
            return True
        
        return False


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """Check if an error is retryable based on classification"""
    is_transient, reason = ErrorClassification.classify_error(error)
    
    if is_transient:
        logger.debug(f"Error classified as transient: {reason}")
        return True
    else:
        logger.debug(f"Error classified as permanent: {reason}")
        return False


def retry_async(config: Optional[RetryConfig] = None):
    """
    Async retry decorator for payment gateway operations
    
    Usage:
        @retry_async(RetryConfig(max_attempts=5))
        async def make_payment():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Log attempt if not first
                    if attempt > 1:
                        logger.info(
                            f"Retry attempt {attempt}/{config.max_attempts} "
                            f"for {func.__name__}"
                        )
                    
                    # Execute the function
                    result = await func(*args, **kwargs)
                    
                    # Success - return result
                    if attempt > 1:
                        logger.info(f"Retry successful for {func.__name__}")
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    
                    # Check if retryable
                    if not is_retryable_error(e, config):
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        raise
                    
                    # Check if we have more attempts
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retry attempts ({config.max_attempts}) exceeded "
                            f"for {func.__name__}: {type(e).__name__}: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    logger.warning(
                        f"Retryable error in {func.__name__} "
                        f"(attempt {attempt}/{config.max_attempts}): "
                        f"{type(e).__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Unexpected retry logic error in {func.__name__}")
        
        return wrapper
    
    return decorator


def retry_sync(config: Optional[RetryConfig] = None):
    """
    Sync retry decorator for payment gateway operations
    
    Usage:
        @retry_sync(RetryConfig(max_attempts=5))
        def make_payment():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Log attempt if not first
                    if attempt > 1:
                        logger.info(
                            f"Retry attempt {attempt}/{config.max_attempts} "
                            f"for {func.__name__}"
                        )
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Success - return result
                    if attempt > 1:
                        logger.info(f"Retry successful for {func.__name__}")
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    
                    # Check if retryable
                    if not is_retryable_error(e, config):
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        raise
                    
                    # Check if we have more attempts
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retry attempts ({config.max_attempts}) exceeded "
                            f"for {func.__name__}: {type(e).__name__}: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    logger.warning(
                        f"Retryable error in {func.__name__} "
                        f"(attempt {attempt}/{config.max_attempts}): "
                        f"{type(e).__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    # Wait before retry
                    import time
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Unexpected retry logic error in {func.__name__}")
        
        return wrapper
    
    return decorator


# Convenience functions for common retry patterns

def payment_retry(max_attempts: int = 3) -> Callable:
    """Retry decorator specifically for payment operations"""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True
    )
    return retry_async(config)


def webhook_retry(max_attempts: int = 5) -> Callable:
    """Retry decorator specifically for webhook operations"""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=2.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True
    )
    return retry_async(config)