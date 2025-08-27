# backend/modules/pos_migration/utils/retry_utils.py

"""
Retry utilities with exponential backoff and rate limiting.
Provides decorators and utilities for resilient API calls.
"""

import asyncio
import functools
import logging
import time
from typing import TypeVar, Callable, Any, Optional, Dict, Tuple
from datetime import datetime, timedelta
import random

from core.exceptions import APIException

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: int, per: float = 60.0):
        """
        Initialize rate limiter.
        
        Args:
            rate: Number of allowed requests
            per: Time period in seconds (default: 60 seconds)
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Returns:
            True if tokens acquired, False if rate limit exceeded
        """
        async with self._lock:
            current = time.time()
            time_passed = current - self.last_check
            self.last_check = current
            
            # Add tokens based on time passed
            self.allowance += time_passed * (self.rate / self.per)
            
            # Cap at maximum rate
            if self.allowance > self.rate:
                self.allowance = self.rate
            
            # Check if we have enough tokens
            if self.allowance < tokens:
                return False
            
            self.allowance -= tokens
            return True
    
    async def wait_for_token(self, tokens: int = 1):
        """Wait until tokens are available"""
        while not await self.acquire(tokens):
            # Calculate wait time
            wait_time = (tokens - self.allowance) * (self.per / self.rate)
            await asyncio.sleep(wait_time)


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Tuple[type, ...] = (Exception,),
        exclude: Tuple[type, ...] = ()
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on
        self.exclude = exclude


def calculate_backoff(
    attempt: int,
    config: RetryConfig
) -> float:
    """Calculate exponential backoff delay"""
    
    delay = min(
        config.initial_delay * (config.exponential_base ** (attempt - 1)),
        config.max_delay
    )
    
    if config.jitter:
        # Add random jitter (0-25% of delay)
        delay *= (1 + random.random() * 0.25)
    
    return delay


def should_retry(
    exception: Exception,
    config: RetryConfig
) -> bool:
    """Determine if exception should trigger retry"""
    
    # Check if explicitly excluded
    if isinstance(exception, config.exclude):
        return False
    
    # Check if in retry list
    if isinstance(exception, config.retry_on):
        # Special handling for API exceptions
        if isinstance(exception, APIException):
            # Don't retry 4xx errors (except 429)
            if 400 <= exception.status_code < 500 and exception.status_code != 429:
                return False
        return True
    
    return False


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to async functions.
    
    Usage:
        @with_retry(RetryConfig(max_attempts=5))
        async def fetch_data():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if not should_retry(e, config):
                        logger.error(
                            f"{func.__name__} failed with non-retryable error: {e}"
                        )
                        raise
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {attempt} attempts: {e}"
                        )
                        raise
                    
                    delay = calculate_backoff(attempt, config)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop completed without result or exception")
        
        return wrapper
    return decorator


def with_rate_limit(limiter: RateLimiter, tokens: int = 1):
    """
    Decorator for rate limiting async functions.
    
    Usage:
        rate_limiter = RateLimiter(rate=100, per=60)  # 100 requests per minute
        
        @with_rate_limit(rate_limiter)
        async def api_call():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            await limiter.wait_for_token(tokens)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents repeated calls to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection"""
        
        async with self._lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                else:
                    raise APIException(
                        status_code=503,
                        detail="Circuit breaker is open - service unavailable"
                    )
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.expected_exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            self.failure_count = 0
            self.state = "closed"
    
    async def _on_failure(self):
        """Handle failed call"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should try to reset the circuit"""
        if self.last_failure_time is None:
            return False
            
        return (
            datetime.utcnow() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout


class BatchProcessor:
    """
    Process items in batches with retry and rate limiting.
    
    Useful for bulk operations that need to respect API limits.
    """
    
    def __init__(
        self,
        batch_size: int = 100,
        rate_limiter: Optional[RateLimiter] = None,
        retry_config: Optional[RetryConfig] = None,
        parallel_workers: int = 1
    ):
        self.batch_size = batch_size
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config or RetryConfig()
        self.parallel_workers = parallel_workers
    
    async def process_items(
        self,
        items: list,
        process_func: Callable[[list], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            process_func: Async function to process a batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with results and statistics
        """
        results = {
            "total_items": len(items),
            "processed": 0,
            "failed": 0,
            "errors": [],
            "duration": 0
        }
        
        start_time = time.time()
        
        # Create batches
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]
        
        # Process batches with worker pool
        semaphore = asyncio.Semaphore(self.parallel_workers)
        
        async def process_batch_with_limit(batch, batch_index):
            async with semaphore:
                return await self._process_single_batch(
                    batch, batch_index, process_func, results, progress_callback
                )
        
        # Process all batches
        tasks = [
            process_batch_with_limit(batch, i)
            for i, batch in enumerate(batches)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        results["duration"] = time.time() - start_time
        return results
    
    async def _process_single_batch(
        self,
        batch: list,
        batch_index: int,
        process_func: Callable,
        results: Dict[str, Any],
        progress_callback: Optional[Callable]
    ):
        """Process a single batch with retry logic"""
        
        # Apply rate limiting if configured
        if self.rate_limiter:
            await self.rate_limiter.wait_for_token()
        
        # Apply retry logic
        @with_retry(self.retry_config)
        async def process_with_retry():
            return await process_func(batch)
        
        try:
            await process_with_retry()
            results["processed"] += len(batch)
            
            if progress_callback:
                progress_callback(results["processed"], results["total_items"])
                
        except Exception as e:
            results["failed"] += len(batch)
            results["errors"].append({
                "batch_index": batch_index,
                "error": str(e),
                "items": len(batch)
            })
            logger.error(f"Batch {batch_index} failed: {e}")


# Pre-configured instances for common scenarios

# POS API rate limiters
square_rate_limiter = RateLimiter(rate=50, per=60)  # 50 req/min
toast_rate_limiter = RateLimiter(rate=100, per=60)  # 100 req/min
clover_rate_limiter = RateLimiter(rate=30, per=60)  # 30 req/min

# Retry configurations
api_retry_config = RetryConfig(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=30.0,
    retry_on=(APIException, ConnectionError, asyncio.TimeoutError),
    exclude=(ValueError, KeyError)
)

ai_retry_config = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=10.0,
    retry_on=(APIException,)
)