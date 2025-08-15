# backend/modules/analytics/services/trend_service.py

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, case, text
from dataclasses import dataclass

from ..models.analytics_models import (
    SalesAnalyticsSnapshot,
    SalesMetric,
    AggregationPeriod,
)
from ..schemas.analytics_schemas import SalesFilterRequest

logger = logging.getLogger(__name__)


@dataclass
class TrendPoint:
    """Single point in a trend line"""

    date: date
    value: float
    previous_value: Optional[float] = None
    change_percentage: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class TrendService:
    """Optimized service for calculating trends using pre-aggregated data"""

    def __init__(self, db: Session):
        self.db = db

    def get_revenue_trend(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[TrendPoint]:
        """
        Get revenue trend using optimized snapshot queries.

        Args:
            start_date: Start date for trend
            end_date: End date for trend
            granularity: daily, weekly, monthly
            staff_ids: Optional filter by staff
            category_ids: Optional filter by categories
        """
        try:
            # Use snapshots for performance
            query = self._build_trend_query(
                metric="total_revenue",
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                staff_ids=staff_ids,
                category_ids=category_ids,
            )

            results = query.all()
            return self._format_trend_points(results, "revenue")

        except Exception as e:
            logger.error(f"Error calculating revenue trend: {e}")
            return []

    def get_order_trend(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[TrendPoint]:
        """Get order count trend using optimized snapshot queries"""
        try:
            query = self._build_trend_query(
                metric="total_orders",
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                staff_ids=staff_ids,
                category_ids=category_ids,
            )

            results = query.all()
            return self._format_trend_points(results, "orders")

        except Exception as e:
            logger.error(f"Error calculating order trend: {e}")
            return []

    def get_customer_trend(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[TrendPoint]:
        """Get customer count trend using optimized snapshot queries"""
        try:
            query = self._build_trend_query(
                metric="unique_customers",
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                staff_ids=staff_ids,
                category_ids=category_ids,
            )

            results = query.all()
            return self._format_trend_points(results, "customers")

        except Exception as e:
            logger.error(f"Error calculating customer trend: {e}")
            return []

    def get_multi_metric_trend(
        self,
        start_date: date,
        end_date: date,
        metrics: List[str],
        granularity: str = "daily",
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> Dict[str, List[TrendPoint]]:
        """
        Get multiple metrics in a single optimized query.

        More efficient than calling individual trend methods.
        """
        try:
            # Build aggregated query for all metrics
            period_func = self._get_period_function(granularity)

            query = self.db.query(
                period_func.label("period"),
                func.sum(SalesAnalyticsSnapshot.total_revenue).label("total_revenue"),
                func.sum(SalesAnalyticsSnapshot.total_orders).label("total_orders"),
                func.sum(SalesAnalyticsSnapshot.unique_customers).label(
                    "unique_customers"
                ),
                func.avg(SalesAnalyticsSnapshot.average_order_value).label(
                    "avg_order_value"
                ),
                func.sum(SalesAnalyticsSnapshot.total_items_sold).label("total_items"),
                func.sum(SalesAnalyticsSnapshot.total_discounts).label(
                    "total_discounts"
                ),
            ).filter(
                and_(
                    SalesAnalyticsSnapshot.snapshot_date >= start_date,
                    SalesAnalyticsSnapshot.snapshot_date <= end_date,
                    SalesAnalyticsSnapshot.period_type
                    == self._get_period_type(granularity),
                )
            )

            # Apply filters
            if staff_ids:
                query = query.filter(SalesAnalyticsSnapshot.staff_id.in_(staff_ids))
            if category_ids:
                query = query.filter(
                    SalesAnalyticsSnapshot.category_id.in_(category_ids)
                )

            query = query.group_by(period_func).order_by(period_func)
            results = query.all()

            # Format results for each metric
            trend_data = {}
            for metric in metrics:
                trend_points = []
                previous_value = None

                for result in results:
                    value = self._extract_metric_value(result, metric)

                    # Calculate change percentage
                    change_percentage = None
                    if previous_value is not None and previous_value != 0:
                        change_percentage = (
                            (value - previous_value) / previous_value
                        ) * 100

                    trend_points.append(
                        TrendPoint(
                            date=(
                                result.period
                                if isinstance(result.period, date)
                                else result.period.date()
                            ),
                            value=float(value),
                            previous_value=(
                                float(previous_value) if previous_value else None
                            ),
                            change_percentage=(
                                float(change_percentage) if change_percentage else None
                            ),
                        )
                    )

                    previous_value = value

                trend_data[metric] = trend_points

            return trend_data

        except Exception as e:
            logger.error(f"Error calculating multi-metric trend: {e}")
            return {metric: [] for metric in metrics}

    def get_comparative_trend(
        self,
        start_date: date,
        end_date: date,
        metric: str,
        comparison_entities: Dict[str, List[int]],
        granularity: str = "daily",
    ) -> Dict[str, List[TrendPoint]]:
        """
        Get comparative trends for different entities.

        Args:
            start_date: Start date
            end_date: End date
            metric: Metric to compare (revenue, orders, customers)
            comparison_entities: {"staff": [1,2,3], "category": [1,2]}
            granularity: Time granularity
        """
        try:
            comparative_data = {}

            # Get trends for staff comparison
            if "staff" in comparison_entities:
                for staff_id in comparison_entities["staff"]:
                    trend_key = f"staff_{staff_id}"
                    trend_data = self._get_entity_trend(
                        start_date, end_date, metric, granularity, staff_ids=[staff_id]
                    )
                    comparative_data[trend_key] = trend_data

            # Get trends for category comparison
            if "category" in comparison_entities:
                for category_id in comparison_entities["category"]:
                    trend_key = f"category_{category_id}"
                    trend_data = self._get_entity_trend(
                        start_date,
                        end_date,
                        metric,
                        granularity,
                        category_ids=[category_id],
                    )
                    comparative_data[trend_key] = trend_data

            return comparative_data

        except Exception as e:
            logger.error(f"Error calculating comparative trend: {e}")
            return {}

    def get_trend_statistics(self, trend_points: List[TrendPoint]) -> Dict[str, Any]:
        """
        Calculate statistical information about a trend.

        Returns min, max, average, standard deviation, trend direction, etc.
        """
        if not trend_points:
            return {}

        values = [point.value for point in trend_points]
        changes = [
            point.change_percentage
            for point in trend_points
            if point.change_percentage is not None
        ]

        # Basic statistics
        min_value = min(values)
        max_value = max(values)
        avg_value = sum(values) / len(values)

        # Standard deviation
        variance = sum((x - avg_value) ** 2 for x in values) / len(values)
        std_deviation = variance**0.5

        # Trend direction (linear regression slope approximation)
        n = len(values)
        if n > 1:
            x_values = list(range(n))
            slope = (
                n * sum(i * v for i, v in zip(x_values, values))
                - sum(x_values) * sum(values)
            ) / (n * sum(i * i for i in x_values) - sum(x_values) ** 2)
            trend_direction = (
                "increasing"
                if slope > 0.1
                else "decreasing" if slope < -0.1 else "stable"
            )
        else:
            slope = 0
            trend_direction = "stable"

        # Growth rate (first to last)
        growth_rate = None
        if len(values) > 1 and values[0] != 0:
            growth_rate = ((values[-1] - values[0]) / values[0]) * 100

        # Volatility (average of absolute changes)
        volatility = (
            sum(abs(change) for change in changes) / len(changes) if changes else 0
        )

        return {
            "min_value": min_value,
            "max_value": max_value,
            "average_value": avg_value,
            "standard_deviation": std_deviation,
            "trend_direction": trend_direction,
            "slope": slope,
            "growth_rate": growth_rate,
            "volatility": volatility,
            "data_points": len(values),
            "period_coverage": {
                "start_date": trend_points[0].date.isoformat(),
                "end_date": trend_points[-1].date.isoformat(),
                "days": (trend_points[-1].date - trend_points[0].date).days + 1,
            },
        }

    # Private helper methods

    def _build_trend_query(
        self,
        metric: str,
        start_date: date,
        end_date: date,
        granularity: str,
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ):
        """Build optimized query for trend calculation"""

        period_func = self._get_period_function(granularity)
        metric_column = getattr(SalesAnalyticsSnapshot, metric)

        query = self.db.query(
            period_func.label("period"), func.sum(metric_column).label("value")
        ).filter(
            and_(
                SalesAnalyticsSnapshot.snapshot_date >= start_date,
                SalesAnalyticsSnapshot.snapshot_date <= end_date,
                SalesAnalyticsSnapshot.period_type
                == self._get_period_type(granularity),
            )
        )

        # Apply entity filters
        if staff_ids:
            query = query.filter(SalesAnalyticsSnapshot.staff_id.in_(staff_ids))
        if category_ids:
            query = query.filter(SalesAnalyticsSnapshot.category_id.in_(category_ids))

        return query.group_by(period_func).order_by(period_func)

    def _get_entity_trend(
        self,
        start_date: date,
        end_date: date,
        metric: str,
        granularity: str,
        staff_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[TrendPoint]:
        """Get trend for specific entities"""

        query = self._build_trend_query(
            metric, start_date, end_date, granularity, staff_ids, category_ids
        )

        results = query.all()
        return self._format_trend_points(results, metric)

    def _get_period_function(self, granularity: str):
        """Get SQL function for period grouping"""

        if granularity == "weekly":
            return func.date_trunc("week", SalesAnalyticsSnapshot.snapshot_date)
        elif granularity == "monthly":
            return func.date_trunc("month", SalesAnalyticsSnapshot.snapshot_date)
        else:  # daily
            return SalesAnalyticsSnapshot.snapshot_date

    def _get_period_type(self, granularity: str) -> AggregationPeriod:
        """Map granularity to aggregation period"""

        mapping = {
            "daily": AggregationPeriod.DAILY,
            "weekly": AggregationPeriod.WEEKLY,
            "monthly": AggregationPeriod.MONTHLY,
        }
        return mapping.get(granularity, AggregationPeriod.DAILY)

    def _format_trend_points(
        self, results: List[Any], metric_type: str
    ) -> List[TrendPoint]:
        """Format query results into TrendPoint objects"""

        trend_points = []
        previous_value = None

        for result in results:
            value = float(result.value or 0)

            # Calculate change percentage
            change_percentage = None
            if previous_value is not None and previous_value != 0:
                change_percentage = ((value - previous_value) / previous_value) * 100

            # Handle different date types
            result_date = result.period
            if hasattr(result_date, "date"):
                result_date = result_date.date()

            trend_points.append(
                TrendPoint(
                    date=result_date,
                    value=value,
                    previous_value=previous_value,
                    change_percentage=change_percentage,
                    metadata={"metric_type": metric_type},
                )
            )

            previous_value = value

        return trend_points

    def _extract_metric_value(self, result: Any, metric: str) -> float:
        """Extract the correct metric value from query result"""

        metric_mapping = {
            "revenue": "total_revenue",
            "orders": "total_orders",
            "customers": "unique_customers",
            "aov": "avg_order_value",
            "items": "total_items",
            "discounts": "total_discounts",
        }

        column_name = metric_mapping.get(metric, metric)
        return float(getattr(result, column_name, 0) or 0)


# Service factory function
def create_trend_service(db: Session) -> TrendService:
    """Create a trend service instance"""
    return TrendService(db)
