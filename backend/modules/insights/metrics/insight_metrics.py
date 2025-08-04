# backend/modules/insights/metrics/insight_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary
from datetime import datetime
from typing import Optional, Dict, Any
import time

from ..models.insight_models import InsightType, InsightSeverity, InsightDomain


# Counters
insights_generated_total = Counter(
    'insights_generated_total',
    'Total number of insights generated',
    ['type', 'severity', 'domain', 'generator']
)

insights_acknowledged_total = Counter(
    'insights_acknowledged_total',
    'Total number of insights acknowledged',
    ['type', 'severity', 'domain']
)

insights_resolved_total = Counter(
    'insights_resolved_total',
    'Total number of insights resolved',
    ['type', 'severity', 'domain']
)

insights_dismissed_total = Counter(
    'insights_dismissed_total',
    'Total number of insights dismissed',
    ['type', 'severity', 'domain']
)

insight_ratings_total = Counter(
    'insight_ratings_total',
    'Total number of insight ratings',
    ['rating', 'type', 'domain']
)

insight_notifications_sent_total = Counter(
    'insight_notifications_sent_total',
    'Total notifications sent for insights',
    ['channel', 'severity']
)

insight_notifications_failed_total = Counter(
    'insight_notifications_failed_total',
    'Total failed notifications for insights',
    ['channel', 'severity', 'error_type']
)

# Histograms
insight_generation_duration = Histogram(
    'insight_generation_duration_seconds',
    'Time taken to generate insights',
    ['generator', 'domain'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

insight_value_distribution = Histogram(
    'insight_estimated_value_dollars',
    'Distribution of estimated insight values',
    ['type', 'domain'],
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
)

insight_impact_score_distribution = Histogram(
    'insight_impact_score',
    'Distribution of insight impact scores',
    ['type', 'domain'],
    buckets=(10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

time_to_acknowledge = Histogram(
    'insight_time_to_acknowledge_hours',
    'Time between insight generation and acknowledgment',
    ['severity', 'domain'],
    buckets=(0.25, 0.5, 1, 2, 4, 8, 12, 24, 48, 72)
)

time_to_resolve = Histogram(
    'insight_time_to_resolve_hours',
    'Time between insight generation and resolution',
    ['severity', 'domain'],
    buckets=(1, 4, 8, 12, 24, 48, 72, 168, 336)
)

# Gauges
active_insights_count = Gauge(
    'active_insights_count',
    'Current number of active insights',
    ['severity', 'domain']
)

unacknowledged_insights_age = Gauge(
    'unacknowledged_insights_oldest_hours',
    'Age of oldest unacknowledged insight in hours',
    ['severity']
)

insight_acceptance_rate = Gauge(
    'insight_acceptance_rate',
    'Rate of insights marked as useful vs dismissed',
    ['type', 'domain', 'time_window']
)

# Summary
insight_thread_length = Summary(
    'insight_thread_length',
    'Number of insights in a thread',
    ['category']
)


class InsightMetricsCollector:
    """Collector for insight-related metrics"""
    
    def __init__(self):
        self.generation_timers: Dict[str, float] = {}
    
    def start_generation_timer(self, generator: str) -> str:
        """Start timing insight generation"""
        timer_id = f"{generator}_{datetime.utcnow().timestamp()}"
        self.generation_timers[timer_id] = time.time()
        return timer_id
    
    def record_insight_generated(
        self,
        timer_id: str,
        insight_type: InsightType,
        severity: InsightSeverity,
        domain: InsightDomain,
        generator: str,
        impact_score: Optional[float] = None,
        estimated_value: Optional[float] = None
    ):
        """Record metrics for generated insight"""
        
        # Record generation
        insights_generated_total.labels(
            type=insight_type.value,
            severity=severity.value,
            domain=domain.value,
            generator=generator
        ).inc()
        
        # Record generation time
        if timer_id in self.generation_timers:
            duration = time.time() - self.generation_timers.pop(timer_id)
            insight_generation_duration.labels(
                generator=generator,
                domain=domain.value
            ).observe(duration)
        
        # Record impact score
        if impact_score is not None:
            insight_impact_score_distribution.labels(
                type=insight_type.value,
                domain=domain.value
            ).observe(impact_score)
        
        # Record estimated value
        if estimated_value is not None:
            insight_value_distribution.labels(
                type=insight_type.value,
                domain=domain.value
            ).observe(float(estimated_value))
    
    def record_insight_acknowledged(
        self,
        insight_type: InsightType,
        severity: InsightSeverity,
        domain: InsightDomain,
        time_to_ack_hours: float
    ):
        """Record insight acknowledgment"""
        
        insights_acknowledged_total.labels(
            type=insight_type.value,
            severity=severity.value,
            domain=domain.value
        ).inc()
        
        time_to_acknowledge.labels(
            severity=severity.value,
            domain=domain.value
        ).observe(time_to_ack_hours)
    
    def record_insight_resolved(
        self,
        insight_type: InsightType,
        severity: InsightSeverity,
        domain: InsightDomain,
        time_to_resolve_hours: float
    ):
        """Record insight resolution"""
        
        insights_resolved_total.labels(
            type=insight_type.value,
            severity=severity.value,
            domain=domain.value
        ).inc()
        
        time_to_resolve.labels(
            severity=severity.value,
            domain=domain.value
        ).observe(time_to_resolve_hours)
    
    def record_insight_dismissed(
        self,
        insight_type: InsightType,
        severity: InsightSeverity,
        domain: InsightDomain
    ):
        """Record insight dismissal"""
        
        insights_dismissed_total.labels(
            type=insight_type.value,
            severity=severity.value,
            domain=domain.value
        ).inc()
    
    def record_insight_rating(
        self,
        rating: str,
        insight_type: InsightType,
        domain: InsightDomain
    ):
        """Record insight rating"""
        
        insight_ratings_total.labels(
            rating=rating,
            type=insight_type.value,
            domain=domain.value
        ).inc()
    
    def record_notification_sent(
        self,
        channel: str,
        severity: InsightSeverity
    ):
        """Record successful notification"""
        
        insight_notifications_sent_total.labels(
            channel=channel,
            severity=severity.value
        ).inc()
    
    def record_notification_failed(
        self,
        channel: str,
        severity: InsightSeverity,
        error_type: str
    ):
        """Record failed notification"""
        
        insight_notifications_failed_total.labels(
            channel=channel,
            severity=severity.value,
            error_type=error_type
        ).inc()
    
    def update_active_insights(
        self,
        counts_by_severity_domain: Dict[tuple, int]
    ):
        """Update active insights gauge"""
        
        # Reset all to handle deletions
        active_insights_count._metrics.clear()
        
        for (severity, domain), count in counts_by_severity_domain.items():
            active_insights_count.labels(
                severity=severity,
                domain=domain
            ).set(count)
    
    def update_oldest_unacknowledged(
        self,
        oldest_by_severity: Dict[str, float]
    ):
        """Update oldest unacknowledged insight age"""
        
        for severity, age_hours in oldest_by_severity.items():
            unacknowledged_insights_age.labels(
                severity=severity
            ).set(age_hours)
    
    def update_acceptance_rates(
        self,
        rates_by_type_domain: Dict[tuple, Dict[str, float]]
    ):
        """Update insight acceptance rates"""
        
        for (insight_type, domain), rates in rates_by_type_domain.items():
            for time_window, rate in rates.items():
                insight_acceptance_rate.labels(
                    type=insight_type,
                    domain=domain,
                    time_window=time_window
                ).set(rate)
    
    def record_thread_length(
        self,
        category: str,
        length: int
    ):
        """Record insight thread length"""
        
        insight_thread_length.labels(
            category=category
        ).observe(length)


# Create singleton collector
insight_metrics = InsightMetricsCollector()


# Decorator for tracking insight generation
def track_insight_generation(generator: str):
    """Decorator to track insight generation metrics"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            timer_id = insight_metrics.start_generation_timer(generator)
            
            try:
                result = await func(*args, **kwargs)
                
                # If result is an insight or list of insights, record metrics
                if hasattr(result, 'type') and hasattr(result, 'severity'):
                    insight_metrics.record_insight_generated(
                        timer_id,
                        result.type,
                        result.severity,
                        result.domain,
                        generator,
                        result.impact_score,
                        result.estimated_value
                    )
                elif isinstance(result, list) and result and hasattr(result[0], 'type'):
                    for insight in result:
                        insight_metrics.record_insight_generated(
                            timer_id,
                            insight.type,
                            insight.severity,
                            insight.domain,
                            generator,
                            insight.impact_score,
                            insight.estimated_value
                        )
                
                return result
                
            except Exception as e:
                # Clean up timer on error
                insight_metrics.generation_timers.pop(timer_id, None)
                raise
        
        return wrapper
    return decorator