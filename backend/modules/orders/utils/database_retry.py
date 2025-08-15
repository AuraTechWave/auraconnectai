# backend/modules/orders/utils/database_retry.py

import asyncio
import logging
from typing import TypeVar, Callable, Optional, Tuple, Set
from functools import wraps
from sqlalchemy.exc import OperationalError, DBAPIError
import random

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Database error codes that indicate retry-able conditions
RETRY_ERROR_CODES: Set[str] = {
    # PostgreSQL
    "40001",  # serialization_failure
    "40P01",  # deadlock_detected
    "55P03",  # lock_not_available
    "57014",  # query_canceled (often due to statement timeout)
    # MySQL
    "1205",  # Lock wait timeout exceeded
    "1213",  # Deadlock found when trying to get lock
    # SQLite (for testing)
    "database is locked",
    "database table is locked",
}


def is_retryable_error(error: Exception) -> bool:
    """
    Check if a database error is retryable

    Args:
        error: The exception to check

    Returns:
        True if the error indicates a transient condition that may succeed on retry
    """
    if isinstance(error, (OperationalError, DBAPIError)):
        # Check error message
        error_str = str(error).lower()
        if any(code in error_str for code in ["deadlock", "serialization", "lock"]):
            return True

        # Check specific error codes if available
        if hasattr(error, "orig") and hasattr(error.orig, "pgcode"):
            # PostgreSQL error code
            return error.orig.pgcode in RETRY_ERROR_CODES
        elif hasattr(error, "orig") and hasattr(error.orig, "args"):
            # MySQL/SQLite error code
            error_code = str(error.orig.args[0]) if error.orig.args else ""
            return any(code in error_code for code in RETRY_ERROR_CODES)

    return False


async def retry_on_deadlock(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    **kwargs,
) -> T:
    """
    Retry a function on deadlock or serialization errors with exponential backoff

    Args:
        func: The async function to retry
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
        jitter: Add random jitter to prevent thundering herd
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if not is_retryable_error(e) or attempt == max_retries:
                # Not retryable or last attempt
                raise

            last_exception = e

            # Calculate delay with exponential backoff
            if attempt > 0:
                actual_delay = min(delay, max_delay)
                if jitter:
                    # Add random jitter (0-25% of delay)
                    actual_delay *= 1 + random.random() * 0.25

                logger.warning(
                    f"Database deadlock/lock error on attempt {attempt + 1}/{max_retries + 1}. "
                    f"Retrying in {actual_delay:.2f}s. Error: {str(e)}"
                )

                await asyncio.sleep(actual_delay)
                delay *= backoff_factor

    # Should never reach here, but for type safety
    if last_exception:
        raise last_exception


def with_deadlock_retry(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator to automatically retry functions on deadlock/serialization errors

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
        jitter: Add random jitter to prevent thundering herd

    Example:
        @with_deadlock_retry(max_retries=5)
        async def update_inventory(self, ...):
            # Database operations that might deadlock
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_on_deadlock(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
                **kwargs,
            )

        return wrapper

    return decorator


class DatabaseRetryContext:
    """
    Context manager for retry logic with session management

    Example:
        async with DatabaseRetryContext(db_session) as retry_ctx:
            # Perform database operations
            inventory = retry_ctx.session.query(Inventory).with_for_update().first()
            inventory.quantity -= 10
            retry_ctx.session.commit()
    """

    def __init__(
        self,
        session,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 2.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.session = session
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self._attempt = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val and is_retryable_error(exc_val):
            self._attempt += 1
            if self._attempt <= self.max_retries:
                # Rollback the failed transaction
                self.session.rollback()

                # Calculate delay
                delay = self.initial_delay * (
                    self.backoff_factor ** (self._attempt - 1)
                )
                actual_delay = min(delay, self.max_delay)
                if self.jitter:
                    actual_delay *= 1 + random.random() * 0.25

                logger.warning(
                    f"Database deadlock/lock error on attempt {self._attempt}/{self.max_retries}. "
                    f"Retrying in {actual_delay:.2f}s. Error: {str(exc_val)}"
                )

                await asyncio.sleep(actual_delay)

                # Suppress the exception to retry
                return True

        # Don't suppress other exceptions or if max retries exceeded
        return False
