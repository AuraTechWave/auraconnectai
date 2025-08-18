"""
Middleware for collecting performance metrics.
"""

import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import traceback

from core.database import SessionLocal
from ..services.health_service import HealthService
from ..schemas.health_schemas import ErrorLogCreate

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request performance and errors.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Initialize metrics
        db_query_count = 0
        db_query_time_ms = 0
        cache_hits = 0
        cache_misses = 0
        
        # Track metrics in request state
        request.state.db_query_count = 0
        request.state.db_query_time_ms = 0
        request.state.cache_hits = 0
        request.state.cache_misses = 0
        
        response = None
        error_logged = False
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Get metrics from request state
            db_query_count = getattr(request.state, 'db_query_count', 0)
            db_query_time_ms = getattr(request.state, 'db_query_time_ms', 0)
            cache_hits = getattr(request.state, 'cache_hits', 0)
            cache_misses = getattr(request.state, 'cache_misses', 0)
            
            # Skip health check endpoints to avoid recursive metrics
            if not request.url.path.startswith("/api/v1/health"):
                # Record performance metric
                await self._record_metric(
                    request=request,
                    response=response,
                    response_time_ms=response_time_ms,
                    db_query_count=db_query_count,
                    db_query_time_ms=db_query_time_ms,
                    cache_hits=cache_hits,
                    cache_misses=cache_misses,
                    request_id=request_id
                )
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            # Log error
            response_time_ms = (time.time() - start_time) * 1000
            
            if not request.url.path.startswith("/api/v1/health"):
                await self._log_error(
                    request=request,
                    error=e,
                    response_time_ms=response_time_ms,
                    request_id=request_id
                )
                error_logged = True
            
            # Re-raise the exception
            raise
        
        finally:
            # Clean up request state
            if hasattr(request.state, 'db_query_count'):
                delattr(request.state, 'db_query_count')
            if hasattr(request.state, 'db_query_time_ms'):
                delattr(request.state, 'db_query_time_ms')
            if hasattr(request.state, 'cache_hits'):
                delattr(request.state, 'cache_hits')
            if hasattr(request.state, 'cache_misses'):
                delattr(request.state, 'cache_misses')
    
    async def _record_metric(
        self,
        request: Request,
        response: Response,
        response_time_ms: float,
        db_query_count: int,
        db_query_time_ms: float,
        cache_hits: int,
        cache_misses: int,
        request_id: str
    ):
        """Record performance metric to database"""
        db = SessionLocal()
        try:
            service = HealthService(db)
            
            # Get request details
            user_id = None
            restaurant_id = None
            
            if hasattr(request.state, 'user'):
                user_id = getattr(request.state.user, 'id', None)
                restaurant_id = getattr(request.state.user, 'restaurant_id', None)
            
            # Calculate sizes
            request_size = int(request.headers.get('content-length', 0))
            response_size = int(response.headers.get('content-length', 0))
            
            # Record metric
            service.record_performance_metric(
                endpoint=str(request.url.path),
                method=request.method,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                db_query_count=db_query_count,
                db_query_time_ms=db_query_time_ms,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                user_id=user_id,
                restaurant_id=restaurant_id,
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"Failed to record performance metric: {e}")
        finally:
            db.close()
    
    async def _log_error(
        self,
        request: Request,
        error: Exception,
        response_time_ms: float,
        request_id: str
    ):
        """Log error to database"""
        db = SessionLocal()
        try:
            service = HealthService(db)
            
            # Get request details
            user_id = None
            restaurant_id = None
            
            if hasattr(request.state, 'user'):
                user_id = getattr(request.state.user, 'id', None)
                restaurant_id = getattr(request.state.user, 'restaurant_id', None)
            
            # Create error log
            error_data = ErrorLogCreate(
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                endpoint=str(request.url.path),
                method=request.method,
                status_code=500,  # Default to 500 for unhandled errors
                user_id=user_id,
                restaurant_id=restaurant_id,
                request_id=request_id,
                tags={
                    "response_time_ms": response_time_ms,
                    "url": str(request.url),
                    "headers": dict(request.headers)
                }
            )
            
            service.log_error(error_data)
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
        finally:
            db.close()


class DatabaseQueryMiddleware:
    """
    Middleware to track database query metrics.
    
    This should be added to SQLAlchemy events to track query performance.
    """
    
    @staticmethod
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Called before a query is executed"""
        conn.info.setdefault('query_start_time', []).append(time.time())
    
    @staticmethod
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Called after a query is executed"""
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        
        # Try to get the current request from context
        # This would need to be implemented based on your application structure
        # For now, we'll skip this part
        pass