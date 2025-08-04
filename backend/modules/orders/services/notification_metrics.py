# backend/modules/orders/services/notification_metrics.py

from prometheus_client import Counter, Gauge, Histogram, Info
from typing import Optional
import time
from functools import wraps


class NotificationMetrics:
    """Prometheus metrics for notification system monitoring"""
    
    # Counters
    notifications_sent = Counter(
        'notifications_sent_total',
        'Total number of notifications sent',
        ['channel', 'event_type', 'status']
    )
    
    notification_retries = Counter(
        'notification_retries_total',
        'Total number of notification retries',
        ['channel', 'retry_count']
    )
    
    notification_failures = Counter(
        'notification_failures_total',
        'Total number of notification failures',
        ['channel', 'error_type']
    )
    
    websocket_connections = Counter(
        'websocket_connections_total',
        'Total WebSocket connections',
        ['server_id', 'event_type']  # event_type: connect/disconnect
    )
    
    websocket_messages = Counter(
        'websocket_messages_total',
        'Total WebSocket messages sent',
        ['server_id', 'message_type']
    )
    
    worker_errors = Counter(
        'notification_worker_errors_total',
        'Total errors in notification workers',
        ['worker_type', 'error_type']
    )
    
    # Gauges
    retry_queue_length = Gauge(
        'notification_retry_queue_length',
        'Current length of retry queue',
        ['channel']
    )
    
    active_websocket_connections = Gauge(
        'websocket_connections_active',
        'Current number of active WebSocket connections',
        ['server_id']
    )
    
    healthy_channels = Gauge(
        'notification_channels_healthy',
        'Number of healthy notification channels'
    )
    
    total_channels = Gauge(
        'notification_channels_total',
        'Total number of notification channels'
    )
    
    # Histograms
    notification_send_duration = Histogram(
        'notification_send_duration_seconds',
        'Time taken to send notifications',
        ['channel'],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )
    
    retry_processing_duration = Histogram(
        'notification_retry_processing_duration_seconds',
        'Time taken to process retry batches',
        buckets=(1, 5, 10, 30, 60, 120, 300)
    )
    
    websocket_message_latency = Histogram(
        'websocket_message_latency_seconds',
        'Latency of WebSocket message delivery',
        ['server_id'],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0)
    )
    
    # Info
    notification_system_info = Info(
        'notification_system',
        'Notification system information'
    )
    
    def __init__(self):
        # Set system info
        self.notification_system_info.info({
            'version': '1.0.0',
            'retry_strategy': 'exponential_backoff'
        })
    
    # Notification metrics methods
    def record_notification_sent(self, channel: str, event_type: str, status: str = "success"):
        """Record a notification being sent"""
        self.notifications_sent.labels(
            channel=channel,
            event_type=event_type,
            status=status
        ).inc()
    
    def record_notification_retry(self, channel: str, retry_count: int):
        """Record a notification retry attempt"""
        self.notification_retries.labels(
            channel=channel,
            retry_count=str(retry_count)
        ).inc()
    
    def record_notification_failure(self, channel: str, error_type: str):
        """Record a notification failure"""
        self.notification_failures.labels(
            channel=channel,
            error_type=error_type
        ).inc()
    
    def record_notification_duration(self, channel: str, duration: float):
        """Record time taken to send a notification"""
        self.notification_send_duration.labels(channel=channel).observe(duration)
    
    # Retry queue metrics
    def set_retry_queue_length(self, length: int, channel: Optional[str] = None):
        """Update retry queue length"""
        if channel:
            self.retry_queue_length.labels(channel=channel).set(length)
        else:
            self.retry_queue_length.labels(channel="all").set(length)
    
    def record_retry_batch_processed(self, count: int, duration: Optional[float] = None):
        """Record retry batch processing"""
        if duration:
            self.retry_processing_duration.observe(duration)
    
    # WebSocket metrics
    def record_websocket_connection(self, server_id: str, event_type: str = "connect"):
        """Record WebSocket connection event"""
        self.websocket_connections.labels(
            server_id=server_id,
            event_type=event_type
        ).inc()
    
    def set_active_websocket_connections(self, server_id: str, count: int):
        """Update active WebSocket connection count"""
        self.active_websocket_connections.labels(server_id=server_id).set(count)
    
    def record_websocket_message(self, server_id: str, message_type: str):
        """Record WebSocket message sent"""
        self.websocket_messages.labels(
            server_id=server_id,
            message_type=message_type
        ).inc()
    
    def record_websocket_latency(self, server_id: str, latency: float):
        """Record WebSocket message latency"""
        self.websocket_message_latency.labels(server_id=server_id).observe(latency)
    
    # Channel health metrics
    def set_healthy_channels(self, count: int):
        """Update healthy channel count"""
        self.healthy_channels.set(count)
    
    def set_total_channels(self, count: int):
        """Update total channel count"""
        self.total_channels.set(count)
    
    # Worker metrics
    def increment_worker_errors(self, worker_type: str, error_type: Optional[str] = None):
        """Increment worker error count"""
        self.worker_errors.labels(
            worker_type=worker_type,
            error_type=error_type or "unknown"
        ).inc()
    
    # Stats aggregation
    def record_notification_stats(self, channel: str, sent: int, delivered: int, failed: int):
        """Record aggregated notification statistics"""
        if sent > 0:
            self.record_notification_sent(channel, "aggregate", "sent")
        if delivered > 0:
            self.record_notification_sent(channel, "aggregate", "delivered")
        if failed > 0:
            self.record_notification_failure(channel, "aggregate")


# Decorator for timing operations
def track_notification_duration(channel: str):
    """Decorator to track notification send duration"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = NotificationMetrics()
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_notification_duration(channel, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_notification_duration(channel, duration)
                metrics.record_notification_failure(channel, type(e).__name__)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = NotificationMetrics()
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_notification_duration(channel, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_notification_duration(channel, duration)
                metrics.record_notification_failure(channel, type(e).__name__)
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Metrics endpoint setup
def setup_metrics_endpoint(app):
    """Setup Prometheus metrics endpoint for FastAPI"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi import Response
    
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )


# Export singleton instance
notification_metrics = NotificationMetrics()