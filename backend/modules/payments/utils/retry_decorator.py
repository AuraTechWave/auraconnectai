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


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """Check if an error is retryable"""
    # Check if it's a retryable exception type
    if isinstance(error, config.retryable_exceptions):
        return True
    
    # Check HTTP status codes
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        if error.response.status_code in config.retryable_status_codes:
            return True
    
    # Check Stripe-specific errors
    if hasattr(error, '__class__') and error.__class__.__module__.startswith('stripe'):
        # Always retry connection and rate limit errors
        if isinstance(error, (stripe.error.APIConnectionError, stripe.error.RateLimitError)):
            return True
        
        # Check HTTP status for other Stripe errors
        if hasattr(error, 'http_status') and error.http_status in config.retryable_status_codes:
            return True
    
    # Check Square errors (they use httpx)
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code in config.retryable_status_codes:
            return True
    
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