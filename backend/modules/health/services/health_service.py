"""
Health monitoring service implementation.
"""

import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import redis
import asyncio

import os
from core.config import settings
from core.database import SessionLocal
from ..models.health_models import SystemHealth, HealthMetric, ErrorLog, PerformanceMetric, Alert
from ..schemas.health_schemas import (
    HealthStatus, ComponentStatus, HealthCheckResponse,
    DatabaseHealth, RedisHealth, SystemMetrics,
    AlertCreate, AlertResponse, ErrorLogCreate
)

logger = logging.getLogger(__name__)


class HealthService:
    """Service for health monitoring operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.start_time = datetime.utcnow()
        self._redis_client = None
        self._app_version = None
        self._redis_url = None
    
    @property
    def app_version(self) -> str:
        """Get application version without modifying global settings"""
        if self._app_version is None:
            self._app_version = getattr(settings, 'APP_VERSION', None) or os.getenv('APP_VERSION', '1.0.0')
        return self._app_version
    
    @property
    def redis_url(self) -> str:
        """Get Redis URL without modifying global settings"""
        if self._redis_url is None:
            # First check if REDIS_URL is already in settings
            if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                self._redis_url = settings.REDIS_URL
            # Then check redis_url (lowercase)
            elif hasattr(settings, 'redis_url') and settings.redis_url:
                self._redis_url = settings.redis_url
            else:
                # Construct from components
                host = getattr(settings, 'REDIS_HOST', 'localhost')
                port = getattr(settings, 'REDIS_PORT', 6379)
                db = getattr(settings, 'REDIS_DB', 0)
                password = getattr(settings, 'REDIS_PASSWORD', None)
                
                if password:
                    self._redis_url = f"redis://:{password}@{host}:{port}/{db}"
                else:
                    self._redis_url = f"redis://{host}:{port}/{db}"
        
        return self._redis_url
    
    @property
    def redis_client(self):
        """Lazy initialization of Redis client"""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    self.redis_url,  # Use property instead of settings.REDIS_URL
                    decode_responses=True,
                    socket_connect_timeout=5
                )
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {e}")
        return self._redis_client
    
    async def check_health(self) -> HealthCheckResponse:
        """Perform comprehensive health check"""
        components = []
        
        # Check database
        db_health = await self.check_database_health()
        components.append(ComponentStatus(
            name="database",
            status=db_health.status,
            response_time_ms=db_health.response_time_ms,
            details={
                "active_connections": db_health.active_connections,
                "idle_connections": db_health.idle_connections,
                "can_connect": db_health.can_connect
            },
            last_checked=datetime.utcnow()
        ))
        
        # Check Redis
        redis_health = await self.check_redis_health()
        components.append(ComponentStatus(
            name="redis",
            status=redis_health.status,
            response_time_ms=redis_health.response_time_ms,
            details={
                "connected_clients": redis_health.connected_clients,
                "memory_usage_mb": redis_health.used_memory_mb,
                "can_connect": redis_health.can_connect
            },
            last_checked=datetime.utcnow()
        ))
        
        # Check API responsiveness
        api_status = await self.check_api_health()
        components.append(api_status)
        
        # Check background workers
        worker_status = await self.check_worker_health()
        components.append(worker_status)
        
        # Determine overall health
        unhealthy_count = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for c in components if c.status == HealthStatus.DEGRADED)
        
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Calculate uptime
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Store health status
        for component in components:
            self._store_component_health(component)
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=self.app_version,  # Use property instead of global settings
            uptime_seconds=uptime_seconds,
            components=components,
            checks_passed=len(components) - unhealthy_count - degraded_count,
            checks_failed=unhealthy_count
        )
    
    async def check_database_health(self) -> DatabaseHealth:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            result = self.db.execute(text("SELECT 1"))
            result.fetchone()
            
            # Get connection pool stats
            pool_status = self.db.get_bind().pool.status()
            
            # Parse pool status
            lines = pool_status.split('\n')
            pool_size = int(lines[0].split()[-1]) if lines else 0
            checked_out = int(lines[1].split()[-1]) if len(lines) > 1 else 0
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Get database version (database-agnostic)
            version = self._get_database_version()
            
            # Determine status
            if response_time_ms > 1000:
                status = HealthStatus.UNHEALTHY
            elif response_time_ms > 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return DatabaseHealth(
                status=status,
                connection_pool_size=pool_size,
                active_connections=checked_out,
                idle_connections=pool_size - checked_out,
                response_time_ms=response_time_ms,
                can_connect=True,
                version=version
            )
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return DatabaseHealth(
                status=HealthStatus.UNHEALTHY,
                connection_pool_size=0,
                active_connections=0,
                idle_connections=0,
                response_time_ms=(time.time() - start_time) * 1000,
                can_connect=False,
                version=None
            )
    
    async def check_redis_health(self) -> RedisHealth:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        
        try:
            if not self.redis_client:
                raise Exception("Redis client not initialized")
            
            # Test basic connectivity
            self.redis_client.ping()
            
            # Get Redis info
            info = self.redis_client.info()
            memory_info = self.redis_client.info("memory")
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Parse memory usage
            used_memory_mb = memory_info.get("used_memory", 0) / 1024 / 1024
            total_memory_mb = memory_info.get("total_system_memory", 0) / 1024 / 1024
            
            # Determine status
            memory_usage_percent = (used_memory_mb / total_memory_mb * 100) if total_memory_mb > 0 else 0
            
            if response_time_ms > 500 or memory_usage_percent > 90:
                status = HealthStatus.UNHEALTHY
            elif response_time_ms > 200 or memory_usage_percent > 75:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return RedisHealth(
                status=status,
                connected_clients=info.get("connected_clients", 0),
                used_memory_mb=used_memory_mb,
                total_memory_mb=total_memory_mb,
                response_time_ms=response_time_ms,
                can_connect=True,
                version=info.get("redis_version", "unknown")
            )
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return RedisHealth(
                status=HealthStatus.UNHEALTHY,
                connected_clients=0,
                used_memory_mb=0,
                total_memory_mb=0,
                response_time_ms=(time.time() - start_time) * 1000,
                can_connect=False,
                version=None
            )
    
    async def check_api_health(self) -> ComponentStatus:
        """Check API responsiveness"""
        # Check recent error rates
        recent_errors = self.db.query(ErrorLog).filter(
            ErrorLog.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        # Check average response times
        avg_response_time = self.db.query(
            func.avg(PerformanceMetric.response_time_ms)
        ).filter(
            PerformanceMetric.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).scalar() or 0
        
        # Determine status
        if recent_errors > 100 or avg_response_time > 2000:
            status = HealthStatus.UNHEALTHY
        elif recent_errors > 50 or avg_response_time > 1000:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        
        return ComponentStatus(
            name="api",
            status=status,
            response_time_ms=avg_response_time,
            details={
                "recent_errors": recent_errors,
                "avg_response_time_ms": avg_response_time
            },
            last_checked=datetime.utcnow()
        )
    
    async def check_worker_health(self) -> ComponentStatus:
        """Check background worker health"""
        # This would check Celery or other background worker status
        # For now, return a placeholder
        return ComponentStatus(
            name="workers",
            status=HealthStatus.HEALTHY,
            details={"active_tasks": 0, "pending_tasks": 0},
            last_checked=datetime.utcnow()
        )
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Database connections - use database-agnostic approach
        db_connections = self._get_database_connection_count()
        
        # Request metrics from last 5 minutes
        recent_metrics = self.db.query(
            func.count(PerformanceMetric.id).label("request_count"),
            func.avg(PerformanceMetric.response_time_ms).label("avg_response_time"),
            func.count(PerformanceMetric.id).filter(
                PerformanceMetric.status_code >= 400
            ).label("error_count")
        ).filter(
            PerformanceMetric.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).first()
        
        request_rate = (recent_metrics.request_count / 300) if recent_metrics else 0  # per second
        error_rate = (recent_metrics.error_count / 300) if recent_metrics else 0
        avg_response_time = recent_metrics.avg_response_time if recent_metrics else 0
        
        return SystemMetrics(
            cpu_usage_percent=cpu_percent,
            memory_usage_mb=memory.used / 1024 / 1024,
            memory_total_mb=memory.total / 1024 / 1024,
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / 1024 / 1024 / 1024,
            active_connections=db_connections,
            request_rate_per_second=request_rate,
            error_rate_per_second=error_rate,
            average_response_time_ms=avg_response_time
        )
    
    def create_alert(self, alert_data: AlertCreate) -> AlertResponse:
        """Create a new alert"""
        alert = Alert(
            alert_type=alert_data.alert_type,
            severity=alert_data.severity,
            component=alert_data.component,
            title=alert_data.title,
            description=alert_data.description,
            threshold_value=alert_data.threshold_value,
            actual_value=alert_data.actual_value,
            metadata=alert_data.metadata
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        # Trigger notifications based on severity
        if alert.severity == "critical":
            self._send_critical_alert(alert)
        
        return AlertResponse(
            id=str(alert.id),
            alert_type=alert.alert_type,
            severity=alert.severity,
            component=alert.component,
            title=alert.title,
            description=alert.description,
            threshold_value=alert.threshold_value,
            actual_value=alert.actual_value,
            metadata=alert.metadata,
            triggered_at=alert.triggered_at,
            acknowledged=alert.acknowledged,
            resolved=alert.resolved
        )
    
    def log_error(self, error_data: ErrorLogCreate) -> None:
        """Log an error for monitoring"""
        error_log = ErrorLog(
            error_type=error_data.error_type,
            error_message=error_data.error_message,
            stack_trace=error_data.stack_trace,
            endpoint=error_data.endpoint,
            method=error_data.method,
            status_code=error_data.status_code,
            user_id=error_data.user_id,
            restaurant_id=error_data.restaurant_id,
            request_id=error_data.request_id,
            tags=error_data.tags
        )
        
        self.db.add(error_log)
        self.db.commit()
        
        # Check if we need to create an alert
        self._check_error_rate_alert()
    
    def record_performance_metric(
        self,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: int,
        **kwargs
    ) -> None:
        """Record a performance metric"""
        metric = PerformanceMetric(
            endpoint=endpoint,
            method=method,
            response_time_ms=response_time_ms,
            status_code=status_code,
            **kwargs
        )
        
        self.db.add(metric)
        self.db.commit()
        
        # Check if we need to create a performance alert
        if response_time_ms > 5000:  # 5 seconds
            self._create_performance_alert(endpoint, response_time_ms)
    
    def _store_component_health(self, component: ComponentStatus) -> None:
        """Store component health status"""
        health = SystemHealth(
            component=component.name,
            status=component.status,
            response_time_ms=component.response_time_ms,
            details=component.details
        )
        
        self.db.add(health)
        self.db.commit()
    
    def _check_error_rate_alert(self) -> None:
        """Check if error rate exceeds threshold"""
        # Count errors in last 5 minutes
        error_count = self.db.query(ErrorLog).filter(
            ErrorLog.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        if error_count > 50:
            self.create_alert(AlertCreate(
                alert_type="error_rate",
                severity="critical" if error_count > 100 else "warning",
                component="api",
                title="High Error Rate Detected",
                description=f"{error_count} errors in the last 5 minutes",
                threshold_value=50,
                actual_value=error_count
            ))
    
    def _create_performance_alert(self, endpoint: str, response_time: float) -> None:
        """Create performance alert"""
        self.create_alert(AlertCreate(
            alert_type="performance",
            severity="warning",
            component="api",
            title=f"Slow Response Time on {endpoint}",
            description=f"Response time of {response_time}ms exceeds threshold",
            threshold_value=5000,
            actual_value=response_time,
            metadata={"endpoint": endpoint}
        ))
    
    def _send_critical_alert(self, alert: Alert) -> None:
        """Send critical alert notifications"""
        # This would integrate with notification services
        # For now, just log it
        logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.description}")
    
    def _get_database_connection_count(self) -> int:
        """Get database connection count in a database-agnostic way"""
        try:
            # Get the database URL to determine the backend
            db_url = str(self.db.bind.url)
            
            if "postgresql" in db_url or "postgres" in db_url:
                # PostgreSQL-specific query
                result = self.db.execute(
                    text("SELECT count(*) FROM pg_stat_activity")
                )
                return result.scalar() or 0
            elif "mysql" in db_url or "mariadb" in db_url:
                # MySQL/MariaDB-specific query
                result = self.db.execute(
                    text("SELECT COUNT(*) FROM information_schema.processlist")
                )
                return result.scalar() or 0
            elif "sqlite" in db_url:
                # SQLite doesn't have a connection count concept
                # Return 1 for the current connection
                return 1
            else:
                # Unknown database, try to get from connection pool
                pool = self.db.get_bind().pool
                if hasattr(pool, 'size'):
                    return pool.size()
                elif hasattr(pool, 'checkedout'):
                    return pool.checkedout()
                else:
                    # Default to 0 if we can't determine
                    return 0
                    
        except Exception as e:
            logger.warning(f"Could not get database connection count: {e}")
            # Return 0 on error rather than failing the entire metrics collection
            return 0
    
    def _get_database_version(self) -> Optional[str]:
        """Get database version in a database-agnostic way"""
        try:
            db_url = str(self.db.bind.url)
            
            if "postgresql" in db_url or "postgres" in db_url:
                # PostgreSQL version
                result = self.db.execute(text("SELECT version()"))
                return result.scalar()
            elif "mysql" in db_url or "mariadb" in db_url:
                # MySQL/MariaDB version
                result = self.db.execute(text("SELECT VERSION()"))
                return result.scalar()
            elif "sqlite" in db_url:
                # SQLite version
                result = self.db.execute(text("SELECT sqlite_version()"))
                return f"SQLite {result.scalar()}"
            else:
                # Unknown database
                return "Unknown"
                
        except Exception as e:
            logger.warning(f"Could not get database version: {e}")
            return None