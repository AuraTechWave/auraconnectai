# backend/modules/ai_recommendations/metrics/model_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from functools import wraps
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Counters
ai_model_requests_total = Counter(
    'ai_model_requests_total',
    'Total number of AI model requests',
    ['model_type', 'domain', 'endpoint']
)

ai_model_successes_total = Counter(
    'ai_model_successes_total',
    'Total number of successful AI model responses',
    ['model_type', 'domain', 'endpoint']
)

ai_model_failures_total = Counter(
    'ai_model_failures_total',
    'Total number of failed AI model requests',
    ['model_type', 'domain', 'endpoint', 'error_type']
)

ai_feedback_received_total = Counter(
    'ai_feedback_received_total',
    'Total number of feedback entries received',
    ['model_type', 'domain', 'feedback_type', 'rating']
)

ai_feedback_throttled_total = Counter(
    'ai_feedback_throttled_total',
    'Total number of throttled feedback attempts',
    ['reason']
)

# Histograms
ai_model_response_time = Histogram(
    'ai_model_response_time_seconds',
    'AI model response time in seconds',
    ['model_type', 'domain', 'endpoint'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

ai_model_confidence_score = Histogram(
    'ai_model_confidence_score',
    'Distribution of AI model confidence scores',
    ['model_type', 'domain'],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# Gauges
ai_model_active_requests = Gauge(
    'ai_model_active_requests',
    'Current number of active AI model requests',
    ['model_type', 'domain']
)

ai_feedback_average_rating = Gauge(
    'ai_feedback_average_rating',
    'Average feedback rating for AI suggestions',
    ['model_type', 'domain', 'time_window']
)

ai_model_success_rate = Gauge(
    'ai_model_success_rate',
    'Success rate of AI model requests',
    ['model_type', 'domain', 'time_window']
)

# Summary
ai_suggestion_value_impact = Summary(
    'ai_suggestion_value_impact',
    'Business value impact of AI suggestions',
    ['model_type', 'domain', 'metric_type']
)


class AIModelMetrics:
    """Collector for AI model metrics"""
    
    def __init__(self):
        self.request_timestamps: Dict[str, datetime] = {}
        self.feedback_cache: Dict[str, list] = {}
        self.success_cache: Dict[str, list] = {}
    
    def track_request_start(
        self,
        request_id: str,
        model_type: str,
        domain: str,
        endpoint: str
    ):
        """Track the start of a model request"""
        self.request_timestamps[request_id] = datetime.utcnow()
        
        ai_model_requests_total.labels(
            model_type=model_type,
            domain=domain,
            endpoint=endpoint
        ).inc()
        
        ai_model_active_requests.labels(
            model_type=model_type,
            domain=domain
        ).inc()
    
    def track_request_end(
        self,
        request_id: str,
        model_type: str,
        domain: str,
        endpoint: str,
        success: bool,
        error_type: Optional[str] = None,
        confidence_score: Optional[float] = None
    ):
        """Track the end of a model request"""
        if request_id in self.request_timestamps:
            start_time = self.request_timestamps.pop(request_id)
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            ai_model_response_time.labels(
                model_type=model_type,
                domain=domain,
                endpoint=endpoint
            ).observe(duration)
        
        ai_model_active_requests.labels(
            model_type=model_type,
            domain=domain
        ).dec()
        
        if success:
            ai_model_successes_total.labels(
                model_type=model_type,
                domain=domain,
                endpoint=endpoint
            ).inc()
            
            if confidence_score is not None:
                ai_model_confidence_score.labels(
                    model_type=model_type,
                    domain=domain
                ).observe(confidence_score)
            
            # Cache for success rate calculation
            cache_key = f"{model_type}:{domain}"
            if cache_key not in self.success_cache:
                self.success_cache[cache_key] = []
            self.success_cache[cache_key].append({
                'timestamp': datetime.utcnow(),
                'success': True
            })
        else:
            ai_model_failures_total.labels(
                model_type=model_type,
                domain=domain,
                endpoint=endpoint,
                error_type=error_type or "unknown"
            ).inc()
            
            # Cache for success rate calculation
            cache_key = f"{model_type}:{domain}"
            if cache_key not in self.success_cache:
                self.success_cache[cache_key] = []
            self.success_cache[cache_key].append({
                'timestamp': datetime.utcnow(),
                'success': False
            })
        
        # Update success rate gauges
        self._update_success_rate_gauges(model_type, domain)
    
    def track_feedback(
        self,
        model_type: str,
        domain: str,
        feedback_type: str,
        rating: int,
        value_impact: Optional[float] = None
    ):
        """Track feedback for AI suggestions"""
        ai_feedback_received_total.labels(
            model_type=model_type,
            domain=domain,
            feedback_type=feedback_type,
            rating=str(rating)
        ).inc()
        
        # Cache feedback for average calculation
        cache_key = f"{model_type}:{domain}"
        if cache_key not in self.feedback_cache:
            self.feedback_cache[cache_key] = []
        
        self.feedback_cache[cache_key].append({
            'timestamp': datetime.utcnow(),
            'rating': rating,
            'value_impact': value_impact
        })
        
        # Update average rating gauges
        self._update_feedback_gauges(model_type, domain)
        
        # Track value impact if provided
        if value_impact is not None:
            ai_suggestion_value_impact.labels(
                model_type=model_type,
                domain=domain,
                metric_type="revenue_impact"
            ).observe(value_impact)
    
    def track_feedback_throttled(self, reason: str):
        """Track throttled feedback attempts"""
        ai_feedback_throttled_total.labels(reason=reason).inc()
    
    def _update_success_rate_gauges(self, model_type: str, domain: str):
        """Update success rate gauges for different time windows"""
        cache_key = f"{model_type}:{domain}"
        if cache_key not in self.success_cache:
            return
        
        now = datetime.utcnow()
        time_windows = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7)
        }
        
        for window_name, window_delta in time_windows.items():
            cutoff_time = now - window_delta
            recent_requests = [
                r for r in self.success_cache[cache_key]
                if r['timestamp'] > cutoff_time
            ]
            
            if recent_requests:
                success_count = sum(1 for r in recent_requests if r['success'])
                success_rate = success_count / len(recent_requests)
                
                ai_model_success_rate.labels(
                    model_type=model_type,
                    domain=domain,
                    time_window=window_name
                ).set(success_rate)
        
        # Clean up old entries
        week_ago = now - timedelta(days=7)
        self.success_cache[cache_key] = [
            r for r in self.success_cache[cache_key]
            if r['timestamp'] > week_ago
        ]
    
    def _update_feedback_gauges(self, model_type: str, domain: str):
        """Update average feedback rating gauges"""
        cache_key = f"{model_type}:{domain}"
        if cache_key not in self.feedback_cache:
            return
        
        now = datetime.utcnow()
        time_windows = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7)
        }
        
        for window_name, window_delta in time_windows.items():
            cutoff_time = now - window_delta
            recent_feedback = [
                f for f in self.feedback_cache[cache_key]
                if f['timestamp'] > cutoff_time
            ]
            
            if recent_feedback:
                avg_rating = sum(f['rating'] for f in recent_feedback) / len(recent_feedback)
                
                ai_feedback_average_rating.labels(
                    model_type=model_type,
                    domain=domain,
                    time_window=window_name
                ).set(avg_rating)
        
        # Clean up old entries
        week_ago = now - timedelta(days=7)
        self.feedback_cache[cache_key] = [
            f for f in self.feedback_cache[cache_key]
            if f['timestamp'] > week_ago
        ]


# Create singleton metrics collector
ai_model_metrics = AIModelMetrics()


# Decorator for tracking model requests
def track_model_request(model_type: str, domain: str, endpoint: str):
    """Decorator to track AI model request metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import uuid
            request_id = str(uuid.uuid4())
            
            # Track request start
            ai_model_metrics.track_request_start(
                request_id, model_type, domain, endpoint
            )
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Extract confidence score if available
                confidence_score = None
                if hasattr(result, 'confidence_score'):
                    confidence_score = result.confidence_score
                elif isinstance(result, dict) and 'confidence_score' in result:
                    confidence_score = result['confidence_score']
                
                # Track success
                ai_model_metrics.track_request_end(
                    request_id, model_type, domain, endpoint,
                    success=True,
                    confidence_score=confidence_score
                )
                
                return result
                
            except Exception as e:
                # Track failure
                ai_model_metrics.track_request_end(
                    request_id, model_type, domain, endpoint,
                    success=False,
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator


# Helper functions
def track_model_error(model_type: str, domain: str, endpoint: str, error: Exception):
    """Track a model error"""
    ai_model_failures_total.labels(
        model_type=model_type,
        domain=domain,
        endpoint=endpoint,
        error_type=type(error).__name__
    ).inc()


def track_feedback_received(
    model_type: str,
    domain: str,
    feedback_type: str,
    rating: int,
    value_impact: Optional[float] = None
):
    """Track feedback received"""
    ai_model_metrics.track_feedback(
        model_type, domain, feedback_type, rating, value_impact
    )