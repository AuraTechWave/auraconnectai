# backend/modules/analytics/services/ai_insights_service.py

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict, Counter
import statistics
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case

from ..schemas.ai_insights_schemas import (
    PeakTimeInsight,
    ProductInsight,
    CustomerInsight,
    TimePattern,
    ProductTrend,
    CustomerPattern,
    SeasonalityPattern,
    AnomalyDetection,
    AIInsightSummary,
    InsightType,
    ConfidenceLevel,
    InsightRequest,
)
from ..models.analytics_models import SalesAnalyticsSnapshot
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember
from core.cache import cache_manager as cache_service
from modules.analytics.utils.performance_monitor import (
    PerformanceMonitor,
    check_performance_threshold,
)
from .optimized_queries import OptimizedAnalyticsQueries

logger = logging.getLogger(__name__)


class AIInsightsService:
    """Service for generating AI-powered analytics insights"""

    def __init__(self, db: Session):
        self.db = db
        self.cache_ttl = 3600  # 1 hour cache

    async def generate_insights(self, request: InsightRequest) -> AIInsightSummary:
        """Generate comprehensive AI insights based on request"""

        # Build structured cache key
        insight_types_str = "_".join(sorted([t.value for t in request.insight_types]))
        date_from_str = request.date_from.isoformat() if request.date_from else "none"
        date_to_str = request.date_to.isoformat() if request.date_to else "none"
        cache_key = f"ai:insights:{insight_types_str}:{date_from_str}:{date_to_str}:{request.min_confidence.value}"

        if not request.force_refresh:
            cached = await cache_service.get(cache_key)
            if cached:
                return AIInsightSummary(**cached)

        # Determine date range
        end_date = request.date_to or datetime.now().date()
        start_date = request.date_from or (end_date - timedelta(days=30))

        summary = AIInsightSummary(
            analysis_period={"start": start_date, "end": end_date},
            overall_recommendations=[],
            next_update=datetime.now() + timedelta(hours=24),
        )

        # Generate requested insights
        if InsightType.PEAK_TIME in request.insight_types:
            summary.peak_times = await self._analyze_peak_times(start_date, end_date)
            summary.overall_recommendations.extend(
                summary.peak_times.recommendations[:2]
            )

        if InsightType.PRODUCT_TREND in request.insight_types:
            summary.product_insights = await self._analyze_product_trends(
                start_date, end_date
            )
            summary.overall_recommendations.extend(
                summary.product_insights.recommendations[:2]
            )

        if InsightType.CUSTOMER_PATTERN in request.insight_types:
            summary.customer_insights = await self._analyze_customer_patterns(
                start_date, end_date
            )
            summary.overall_recommendations.extend(
                summary.customer_insights.recommendations[:2]
            )

        if InsightType.SEASONALITY in request.insight_types:
            summary.seasonality = await self._detect_seasonality(start_date, end_date)

        if InsightType.ANOMALY in request.insight_types:
            summary.anomalies = await self._detect_anomalies(start_date, end_date)

        # Cache the results
        await cache_service.set(cache_key, summary.dict(), ttl=self.cache_ttl)

        return summary

    @PerformanceMonitor.monitor_query("peak_time_analysis")
    async def _analyze_peak_times(
        self, start_date: date, end_date: date
    ) -> PeakTimeInsight:
        """Analyze peak business hours and patterns"""
        import time

        start_time = time.time()

        # Query hourly order data
        hourly_data = (
            self.db.query(
                func.extract("hour", Order.order_date).label("hour"),
                func.extract("dow", Order.order_date).label("day_of_week"),
                func.count(Order.id).label("order_count"),
                func.sum(Order.total_amount).label("revenue"),
                func.count(func.distinct(Order.customer_id)).label("customer_count"),
            )
            .filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.status.in_(["completed", "paid"]),
                )
            )
            .group_by("hour", "day_of_week")
            .all()
        )

        # Process into time patterns
        patterns_by_hour = defaultdict(list)
        patterns_by_dow_hour = defaultdict(lambda: defaultdict(list))

        for row in hourly_data:
            pattern = TimePattern(
                hour=int(row.hour),
                day_of_week=(
                    int(row.day_of_week) if row.day_of_week is not None else None
                ),
                intensity=0,  # Calculate later
                order_count=row.order_count,
                revenue=row.revenue or Decimal("0"),
                customer_count=row.customer_count,
            )
            patterns_by_hour[row.hour].append(pattern)
            if row.day_of_week is not None:
                patterns_by_dow_hour[int(row.day_of_week)][row.hour].append(pattern)

        # Calculate intensities
        all_orders = [
            p.order_count for patterns in patterns_by_hour.values() for p in patterns
        ]
        max_orders = max(all_orders) if all_orders else 1

        # Find peak times
        hourly_averages = {}
        for hour, patterns in patterns_by_hour.items():
            avg_orders = statistics.mean([p.order_count for p in patterns])
            avg_revenue = statistics.mean([float(p.revenue) for p in patterns])
            avg_customers = statistics.mean([p.customer_count for p in patterns])

            hourly_averages[hour] = TimePattern(
                hour=hour,
                intensity=avg_orders / max_orders,
                order_count=int(avg_orders),
                revenue=Decimal(str(avg_revenue)),
                customer_count=int(avg_customers),
            )

        # Sort by intensity to find peaks
        sorted_hours = sorted(
            hourly_averages.items(), key=lambda x: x[1].intensity, reverse=True
        )

        # Identify primary and secondary peaks
        primary_peak = sorted_hours[0][1] if sorted_hours else None
        secondary_peak = sorted_hours[1][1] if len(sorted_hours) > 1 else None

        # Identify quiet periods (bottom 25%)
        quiet_threshold = len(sorted_hours) // 4
        quiet_periods = (
            [item[1] for item in sorted_hours[-quiet_threshold:]]
            if quiet_threshold > 0
            else []
        )

        # Weekly patterns
        weekly_pattern = {}
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for dow, hour_patterns in patterns_by_dow_hour.items():
            day_name = days[dow]
            day_peaks = []

            for hour, patterns in hour_patterns.items():
                if patterns:
                    avg_orders = statistics.mean([p.order_count for p in patterns])
                    avg_revenue = statistics.mean([float(p.revenue) for p in patterns])

                    day_peaks.append(
                        TimePattern(
                            hour=hour,
                            day_of_week=dow,
                            intensity=avg_orders / max_orders,
                            order_count=int(avg_orders),
                            revenue=Decimal(str(avg_revenue)),
                            customer_count=int(
                                statistics.mean([p.customer_count for p in patterns])
                            ),
                        )
                    )

            # Get top 3 peaks for each day
            day_peaks.sort(key=lambda x: x.intensity, reverse=True)
            weekly_pattern[day_name] = day_peaks[:3]

        # Generate recommendations
        recommendations = []
        if primary_peak:
            recommendations.append(
                f"Schedule maximum staff during {primary_peak.hour}:00-{primary_peak.hour+1}:00 "
                f"when you typically receive {primary_peak.order_count} orders"
            )

        if quiet_periods:
            quiet_hours = [f"{p.hour}:00" for p in quiet_periods[:3]]
            recommendations.append(
                f"Consider reduced staffing during quiet hours: {', '.join(quiet_hours)}"
            )

        # Check for lunch/dinner rush patterns
        lunch_hours = [h for h in hourly_averages.values() if 11 <= h.hour <= 14]
        dinner_hours = [h for h in hourly_averages.values() if 17 <= h.hour <= 20]

        if lunch_hours and dinner_hours:
            lunch_intensity = statistics.mean([h.intensity for h in lunch_hours])
            dinner_intensity = statistics.mean([h.intensity for h in dinner_hours])

            if lunch_intensity > 0.7:
                recommendations.append(
                    "Strong lunch rush detected - ensure kitchen is fully prepared by 11:00"
                )
            if dinner_intensity > 0.7:
                recommendations.append(
                    "Strong dinner rush detected - prepare for high volume from 17:00"
                )

        confidence = (
            ConfidenceLevel.HIGH if len(hourly_data) > 100 else ConfidenceLevel.MEDIUM
        )

        return PeakTimeInsight(
            primary_peak=primary_peak,
            secondary_peak=secondary_peak,
            quiet_periods=quiet_periods,
            weekly_pattern=weekly_pattern,
            confidence=confidence,
            recommendations=recommendations,
        )

    async def _analyze_product_trends(
        self, start_date: date, end_date: date
    ) -> ProductInsight:
        """Analyze product popularity trends and predictions"""

        # Calculate current period metrics
        current_period_data = self._get_product_metrics(start_date, end_date)

        # Calculate previous period for comparison
        period_length = (end_date - start_date).days
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_length)

        previous_period_data = self._get_product_metrics(prev_start, prev_end)

        # Build trend analysis
        product_trends = []

        for product_id, current_metrics in current_period_data.items():
            prev_metrics = previous_period_data.get(
                product_id,
                {
                    "quantity": 0,
                    "revenue": Decimal("0"),
                    "order_count": 0,
                    "rank": None,
                },
            )

            # Calculate trend metrics
            quantity_change = current_metrics["quantity"] - prev_metrics["quantity"]
            revenue_change = float(current_metrics["revenue"] - prev_metrics["revenue"])

            # Determine trend direction and strength
            if prev_metrics["quantity"] > 0:
                change_percentage = quantity_change / prev_metrics["quantity"]
                if change_percentage > 0.2:
                    trend_direction = "rising"
                    trend_strength = min(change_percentage, 1.0)
                elif change_percentage < -0.2:
                    trend_direction = "falling"
                    trend_strength = min(abs(change_percentage), 1.0)
                else:
                    trend_direction = "stable"
                    trend_strength = 0.1
            else:
                # New product
                trend_direction = (
                    "rising" if current_metrics["quantity"] > 10 else "stable"
                )
                trend_strength = 0.5

            # Simple demand prediction (could be enhanced with ML)
            if trend_direction == "rising":
                predicted_demand = int(
                    current_metrics["quantity"] * (1 + trend_strength * 0.3)
                )
            elif trend_direction == "falling":
                predicted_demand = int(
                    current_metrics["quantity"] * (1 - trend_strength * 0.2)
                )
            else:
                predicted_demand = current_metrics["quantity"]

            trend = ProductTrend(
                product_id=product_id,
                product_name=current_metrics["name"],
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                current_rank=current_metrics["rank"],
                previous_rank=prev_metrics.get("rank"),
                velocity=change_percentage if prev_metrics["quantity"] > 0 else 0,
                predicted_demand=predicted_demand,
            )

            product_trends.append(trend)

        # Sort and categorize trends
        product_trends.sort(key=lambda x: x.trend_strength, reverse=True)

        top_rising = [t for t in product_trends if t.trend_direction == "rising"][:10]
        top_falling = [t for t in product_trends if t.trend_direction == "falling"][:10]
        stable_performers = [
            t
            for t in product_trends
            if t.trend_direction == "stable" and t.current_rank <= 20
        ][:10]
        new_trending = [
            t
            for t in product_trends
            if t.previous_rank is None and t.current_rank <= 50
        ][:5]

        # Generate recommendations
        recommendations = []

        if top_rising:
            rising_names = [t.product_name for t in top_rising[:3]]
            recommendations.append(
                f"Increase inventory for rapidly growing products: {', '.join(rising_names)}"
            )

        if top_falling:
            falling_names = [t.product_name for t in top_falling[:3]]
            recommendations.append(
                f"Consider promotions or review pricing for declining products: {', '.join(falling_names)}"
            )

        if new_trending:
            recommendations.append(
                f"New products gaining traction - monitor closely and ensure adequate supply"
            )

        # Check for seasonal patterns
        seasonal_products = [t for t in product_trends if abs(t.velocity) > 0.5]
        if seasonal_products:
            recommendations.append(
                "Strong velocity changes detected - possible seasonal effects in play"
            )

        confidence = (
            ConfidenceLevel.HIGH if len(product_trends) > 20 else ConfidenceLevel.MEDIUM
        )

        return ProductInsight(
            top_rising=top_rising,
            top_falling=top_falling,
            stable_performers=stable_performers,
            new_trending=new_trending,
            confidence=confidence,
            analysis_period={"start": start_date, "end": end_date},
            recommendations=recommendations,
        )

    def _get_product_metrics(
        self, start_date: date, end_date: date
    ) -> Dict[int, Dict[str, Any]]:
        """Get product sales metrics for a period"""

        # Query product performance data
        product_data = (
            self.db.query(
                OrderItem.product_id,
                OrderItem.product_name,
                func.sum(OrderItem.quantity).label("total_quantity"),
                func.sum(OrderItem.total_price).label("total_revenue"),
                func.count(func.distinct(Order.id)).label("order_count"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.status.in_(["completed", "paid"]),
                )
            )
            .group_by(OrderItem.product_id, OrderItem.product_name)
            .order_by(desc("total_quantity"))
            .all()
        )

        # Process into metrics dict with rankings
        metrics = {}
        for rank, row in enumerate(product_data, 1):
            metrics[row.product_id] = {
                "name": row.product_name,
                "quantity": row.total_quantity,
                "revenue": row.total_revenue,
                "order_count": row.order_count,
                "rank": rank,
            }

        return metrics

    async def _analyze_customer_patterns(
        self, start_date: date, end_date: date
    ) -> CustomerInsight:
        """Analyze customer behavior patterns using optimized batch processing"""

        # Use optimized batch processing to avoid memory issues with large datasets
        customer_metrics = OptimizedAnalyticsQueries.get_customer_insights_batch(
            self.db, start_date, end_date, batch_size=1000
        )
        
        # Convert to list for further processing
        customer_data = list(customer_metrics.values())

        # Analyze patterns
        patterns_detected = []
        total_customers = len(customer_data)
        repeat_customers = sum(1 for c in customer_data if c["order_count"] > 1)

        # Calculate metrics
        repeat_customer_rate = (
            repeat_customers / total_customers if total_customers > 0 else 0
        )

        order_frequencies = []
        lifetime_values = defaultdict(list)

        for customer in customer_data:
            # Calculate order frequency (orders per month)
            days_active = customer["days_active"]
            months_active = max(days_active / 30, 1)
            frequency = customer["order_count"] / months_active
            order_frequencies.append(frequency)

            # Use pre-calculated segment from optimized query
            segment = customer["segment"]
            lifetime_values[segment].append(float(customer["total_spent"]))

        avg_order_frequency = (
            statistics.mean(order_frequencies) if order_frequencies else 0
        )

        # Detect patterns
        if repeat_customer_rate < 0.3:
            patterns_detected.append(
                CustomerPattern(
                    pattern_name="Low Retention",
                    description="Most customers only order once",
                    frequency="continuous",
                    impact_score=0.8,
                    examples=[{"metric": "repeat_rate", "value": repeat_customer_rate}],
                )
            )

        # Calculate CLV by segment
        clv_trends = {}
        for segment, values in lifetime_values.items():
            if values:
                clv_trends[segment] = statistics.mean(values)

        # Identify at-risk segments
        churn_risk_segments = []

        # Check for customers who haven't ordered recently
        recent_threshold = datetime.now() - timedelta(days=60)
        at_risk_count = sum(
            1 for c in customer_data if c["last_order"] < recent_threshold
        )

        if at_risk_count > total_customers * 0.2:
            churn_risk_segments.append(
                {
                    "segment": "inactive_60_days",
                    "count": at_risk_count,
                    "percentage": at_risk_count / total_customers,
                }
            )

        # Generate recommendations
        recommendations = []

        if repeat_customer_rate < 0.4:
            recommendations.append(
                "Implement loyalty program to improve retention - current repeat rate is only "
                f"{repeat_customer_rate:.1%}"
            )

        if churn_risk_segments:
            recommendations.append(
                f"Launch re-engagement campaign - {at_risk_count} customers haven't ordered in 60+ days"
            )

        if (
            "vip" in clv_trends
            and clv_trends["vip"] > statistics.mean(list(clv_trends.values())) * 2
        ):
            recommendations.append(
                "Focus on VIP customer retention - they generate significantly higher lifetime value"
            )

        confidence = (
            ConfidenceLevel.HIGH if total_customers > 100 else ConfidenceLevel.MEDIUM
        )

        return CustomerInsight(
            patterns_detected=patterns_detected,
            repeat_customer_rate=repeat_customer_rate,
            average_order_frequency=avg_order_frequency,
            churn_risk_segments=churn_risk_segments,
            lifetime_value_trends=clv_trends,
            confidence=confidence,
            recommendations=recommendations,
        )

    async def _detect_seasonality(
        self, start_date: date, end_date: date
    ) -> List[SeasonalityPattern]:
        """Detect seasonal patterns in sales data"""

        # This would ideally use more sophisticated time series analysis
        # For now, simple month-over-month comparison

        monthly_data = (
            self.db.query(
                func.extract("month", Order.order_date).label("month"),
                func.sum(Order.total_amount).label("revenue"),
                func.count(Order.id).label("order_count"),
            )
            .filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.status.in_(["completed", "paid"]),
                )
            )
            .group_by("month")
            .all()
        )

        if not monthly_data or len(monthly_data) < 3:
            return []

        # Calculate average revenue
        revenues = [float(m.revenue) for m in monthly_data]
        avg_revenue = statistics.mean(revenues)

        patterns = []

        # Simple seasonality detection
        for month_data in monthly_data:
            month_revenue = float(month_data.revenue)
            if month_revenue > avg_revenue * 1.3:
                # High season detected
                patterns.append(
                    SeasonalityPattern(
                        season_name=f"High Season Month {month_data.month}",
                        start_month=month_data.month,
                        end_month=month_data.month,
                        impact_multiplier=month_revenue / avg_revenue,
                        affected_products=[],  # Would need more analysis
                        historical_accuracy=0.7,
                    )
                )

        return patterns

    async def _detect_anomalies(
        self, start_date: date, end_date: date
    ) -> List[AnomalyDetection]:
        """Detect anomalies in sales patterns"""

        # Get daily sales data
        daily_data = (
            self.db.query(
                func.date(Order.order_date).label("date"),
                func.sum(Order.total_amount).label("revenue"),
                func.count(Order.id).label("order_count"),
            )
            .filter(
                and_(
                    Order.order_date >= start_date,
                    Order.order_date <= end_date,
                    Order.status.in_(["completed", "paid"]),
                )
            )
            .group_by("date")
            .all()
        )

        if len(daily_data) < 7:
            return []

        # Calculate statistics
        revenues = [float(d.revenue) for d in daily_data]
        order_counts = [d.order_count for d in daily_data]

        revenue_mean = statistics.mean(revenues)
        revenue_stdev = statistics.stdev(revenues)

        order_mean = statistics.mean(order_counts)
        order_stdev = statistics.stdev(order_counts)

        anomalies = []

        # Detect anomalies (values beyond 2 standard deviations)
        for day_data in daily_data:
            day_revenue = float(day_data.revenue)
            day_orders = day_data.order_count

            revenue_z_score = (
                abs((day_revenue - revenue_mean) / revenue_stdev)
                if revenue_stdev > 0
                else 0
            )
            order_z_score = (
                abs((day_orders - order_mean) / order_stdev) if order_stdev > 0 else 0
            )

            if revenue_z_score > 2 or order_z_score > 2:
                anomaly_type = (
                    "revenue_spike" if day_revenue > revenue_mean else "revenue_drop"
                )
                severity = "high" if revenue_z_score > 3 else "medium"

                deviation_percentage = (
                    (day_revenue - revenue_mean) / revenue_mean
                ) * 100

                # Try to identify potential causes
                potential_causes = []
                if day_data.date.weekday() in [5, 6]:  # Weekend
                    potential_causes.append("Weekend effect")
                if severity == "high":
                    potential_causes.append("Possible special event or system issue")

                anomalies.append(
                    AnomalyDetection(
                        anomaly_date=day_data.date,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        deviation_percentage=deviation_percentage,
                        potential_causes=potential_causes,
                        affected_metrics={
                            "revenue": day_revenue,
                            "orders": day_orders,
                            "revenue_z_score": revenue_z_score,
                        },
                    )
                )

        return anomalies


# AI Insights service factory function
def create_ai_insights_service(db: Session) -> AIInsightsService:
    """Create an AI insights service instance"""
    return AIInsightsService(db)
