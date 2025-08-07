# backend/modules/menu/utils/performance_utils.py

"""
Performance utilities for recipe management.
Includes timing decorators, parallelization helpers, and monitoring tools.
"""

import time
import logging
import functools
import asyncio
from typing import Callable, Any, Dict, Optional, List, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

T = TypeVar('T')


class PerformanceThresholds:
    """Configurable performance thresholds in milliseconds"""
    WARNING = 500  # 500ms
    ERROR = 2000   # 2 seconds
    CRITICAL = 5000  # 5 seconds
    
    # Endpoint-specific thresholds
    ENDPOINTS = {
        'cost_analysis': {'warning': 300, 'error': 1000},
        'compliance_report': {'warning': 500, 'error': 2000},
        'bulk_recalculation': {'warning': 5000, 'error': 30000},
    }


def timing_logger(
    operation_name: Optional[str] = None,
    warning_threshold_ms: Optional[int] = None,
    error_threshold_ms: Optional[int] = None,
    include_args: bool = False
):
    """
    Decorator for timing function execution with configurable thresholds.
    
    Args:
        operation_name: Custom name for the operation
        warning_threshold_ms: Custom warning threshold (default: 500ms)
        error_threshold_ms: Custom error threshold (default: 2000ms)
        include_args: Whether to include function arguments in logs
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _execute_with_timing(
                func, operation_name, warning_threshold_ms, 
                error_threshold_ms, include_args, True, *args, **kwargs
            )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _execute_with_timing(
                func, operation_name, warning_threshold_ms,
                error_threshold_ms, include_args, False, *args, **kwargs
            )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def _execute_with_timing(
    func: Callable,
    operation_name: Optional[str],
    warning_threshold_ms: Optional[int],
    error_threshold_ms: Optional[int],
    include_args: bool,
    is_async: bool,
    *args,
    **kwargs
):
    """Execute function with timing and threshold logging"""
    op_name = operation_name or f"{func.__module__}.{func.__name__}"
    
    # Get endpoint-specific thresholds if available
    endpoint_thresholds = PerformanceThresholds.ENDPOINTS.get(
        func.__name__, {}
    )
    
    warn_ms = warning_threshold_ms or endpoint_thresholds.get(
        'warning', PerformanceThresholds.WARNING
    )
    error_ms = error_threshold_ms or endpoint_thresholds.get(
        'error', PerformanceThresholds.ERROR
    )
    
    start_time = time.time()
    
    # Build context for logging
    context = {'operation': op_name}
    if include_args:
        context['args'] = str(args)[:200]  # Truncate long args
        context['kwargs'] = str(kwargs)[:200]
    
    try:
        if is_async:
            result = asyncio.run(func(*args, **kwargs))
        else:
            result = func(*args, **kwargs)
        
        elapsed_ms = (time.time() - start_time) * 1000
        context['duration_ms'] = elapsed_ms
        
        # Log based on thresholds
        if elapsed_ms >= error_ms:
            logger.error(
                f"SLOW OPERATION: {op_name} took {elapsed_ms:.2f}ms "
                f"(threshold: {error_ms}ms)",
                extra=context
            )
        elif elapsed_ms >= warn_ms:
            logger.warning(
                f"Slow operation: {op_name} took {elapsed_ms:.2f}ms "
                f"(threshold: {warn_ms}ms)",
                extra=context
            )
        elif elapsed_ms >= PerformanceThresholds.WARNING * 0.8:  # 80% of warning
            logger.info(
                f"Operation approaching threshold: {op_name} took {elapsed_ms:.2f}ms",
                extra=context
            )
        else:
            logger.debug(
                f"Operation completed: {op_name} took {elapsed_ms:.2f}ms",
                extra=context
            )
        
        return result
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        context['duration_ms'] = elapsed_ms
        context['error'] = str(e)
        context['traceback'] = traceback.format_exc()
        
        logger.error(
            f"Operation failed: {op_name} after {elapsed_ms:.2f}ms - {str(e)}",
            extra=context
        )
        raise


class ParallelExecutor:
    """
    Helper class for parallel execution of CPU-bound operations.
    Supports both thread and process-based parallelization.
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_processes: bool = False,
        chunk_size: int = 100
    ):
        """
        Initialize parallel executor.
        
        Args:
            max_workers: Maximum number of workers (default: CPU count)
            use_processes: Use processes instead of threads for CPU-bound tasks
            chunk_size: Size of chunks for batch processing
        """
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.chunk_size = chunk_size
        self._executor = None
    
    def __enter__(self):
        if self.use_processes:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor:
            self._executor.shutdown(wait=True)
    
    @timing_logger("parallel_map", warning_threshold_ms=1000)
    def parallel_map(
        self,
        func: Callable[[T], Any],
        items: List[T],
        timeout: Optional[float] = None
    ) -> List[Union[Any, Exception]]:
        """
        Execute function on items in parallel.
        
        Args:
            func: Function to execute on each item
            items: List of items to process
            timeout: Timeout for each operation
            
        Returns:
            List of results (successful results or exceptions)
        """
        if not self._executor:
            raise RuntimeError("ParallelExecutor must be used as context manager")
        
        results = [None] * len(items)
        
        # Submit all tasks
        future_to_index = {
            self._executor.submit(func, item): i
            for i, item in enumerate(items)
        }
        
        # Collect results
        for future in as_completed(future_to_index, timeout=timeout):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Parallel execution failed for item {index}: {e}")
                results[index] = e
        
        return results
    
    @timing_logger("parallel_batch_process", warning_threshold_ms=2000)
    def parallel_batch_process(
        self,
        func: Callable[[List[T]], Any],
        items: List[T],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        Process items in parallel batches.
        
        Args:
            func: Function to process a batch of items
            items: All items to process
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of batch results
        """
        if not self._executor:
            raise RuntimeError("ParallelExecutor must be used as context manager")
        
        # Create batches
        batches = [
            items[i:i + self.chunk_size]
            for i in range(0, len(items), self.chunk_size)
        ]
        
        results = []
        completed = 0
        
        # Submit batch tasks
        future_to_batch = {
            self._executor.submit(func, batch): batch
            for batch in batches
        }
        
        # Process results
        for future in as_completed(future_to_batch):
            try:
                result = future.result()
                results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(batches))
                    
            except Exception as e:
                batch = future_to_batch[future]
                logger.error(
                    f"Batch processing failed for {len(batch)} items: {e}"
                )
                results.append(e)
        
        return results


def measure_memory_usage(func: Callable) -> Callable:
    """
    Decorator to measure memory usage of a function.
    Requires psutil to be installed.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            import psutil
            process = psutil.Process()
            
            # Memory before
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_delta = mem_after - mem_before
            
            logger.info(
                f"{func.__name__} memory usage: "
                f"before={mem_before:.2f}MB, after={mem_after:.2f}MB, "
                f"delta={mem_delta:.2f}MB"
            )
            
            return result
            
        except ImportError:
            logger.warning("psutil not installed, skipping memory measurement")
            return func(*args, **kwargs)
    
    return wrapper


class OperationTimer:
    """Context manager for timing operations with automatic logging"""
    
    def __init__(
        self,
        operation_name: str,
        warning_threshold_ms: int = 500,
        error_threshold_ms: int = 2000
    ):
        self.operation_name = operation_name
        self.warning_threshold_ms = warning_threshold_ms
        self.error_threshold_ms = error_threshold_ms
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed_ms = (self.end_time - self.start_time) * 1000
        
        context = {
            'operation': self.operation_name,
            'duration_ms': elapsed_ms,
            'success': exc_type is None
        }
        
        if exc_type:
            context['error'] = str(exc_val)
            logger.error(
                f"Operation failed: {self.operation_name} after {elapsed_ms:.2f}ms",
                extra=context
            )
        elif elapsed_ms >= self.error_threshold_ms:
            logger.error(
                f"SLOW OPERATION: {self.operation_name} took {elapsed_ms:.2f}ms",
                extra=context
            )
        elif elapsed_ms >= self.warning_threshold_ms:
            logger.warning(
                f"Slow operation: {self.operation_name} took {elapsed_ms:.2f}ms",
                extra=context
            )
        else:
            logger.debug(
                f"Operation completed: {self.operation_name} in {elapsed_ms:.2f}ms",
                extra=context
            )
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        elif self.start_time:
            return (time.time() - self.start_time) * 1000
        return 0